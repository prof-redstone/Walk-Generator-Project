"""
score_calculator.py

Calcule les vecteurs de score (SSV - Segment Score Vector) pour chaque edge du graphe.

Le vecteur de score a 6 dimensions:
[0] vegetalisation    - Presence d'arbres et elements vegetaux
[1] accessibilite     - Denivele, escaliers, largeur trottoirs
[2] securite          - Largeur de la rue
[3] culture           - Monuments, architecture (nombre de photos)
[4] denivele          - Differentiel d'altitude (penalite pour montees/descentes)
[5] cyclabilite       - Pistes cyclables, parkings velo

Chaque score est normalise entre -1 et 1 pour faciliter la comparaison.
"""

import osmnx as ox
import networkx as nx
import numpy as np
import pickle
from typing import Tuple, Dict, List
from shapely.geometry import Point, LineString
from shapely.ops import nearest_points
import os
from pathlib import Path


def find_project_root():
    """
    Trouve la racine du projet en remontant jusqu'a trouver le dossier 'projet'
    """
    current = Path(__file__).resolve().parent
    
    # Remonter jusqu'a trouver le dossier 'projet' ou atteindre la racine
    while current.name != 'projet' and current.parent != current:
        current = current.parent
    
    if current.name == 'projet':
        return current
    
    # Si on n'a pas trouve, utiliser le chemin actuel
    return Path.cwd()


PROJECT_ROOT = find_project_root()


def load_graph(filepath: str = None):
    """Charge le graphe traite"""
    if filepath is None:
        filepath = PROJECT_ROOT / "data" / "processed" / "graph.pkl"
    else:
        filepath = Path(filepath)
    
    print(f"Chemin du graphe: {filepath}")
    
    if not filepath.exists():
        raise FileNotFoundError(
            f"Graphe non trouve: {filepath}\n"
            f"Racine du projet detectee: {PROJECT_ROOT}\n"
            f"Verifiez que le fichier existe bien a cet emplacement."
        )
    
    with open(filepath, 'rb') as f:
        G, metadata = pickle.load(f)
    return G, metadata


def load_pois(filepath: str = None):
    """Charge les POIs traites"""
    if filepath is None:
        filepath = PROJECT_ROOT / "data" / "processed" / "pois.pkl"
    else:
        filepath = Path(filepath)
    
    print(f"Chemin des POIs: {filepath}")
    
    if not filepath.exists():
        print(f"Attention: POIs non trouves dans {filepath}")
        return []
    
    with open(filepath, 'rb') as f:
        pois = pickle.load(f)
    return pois


def get_edge_geometry(G: nx.Graph, u: int, v: int, edge_data: dict) -> LineString:
    """
    Recupere ou construit la geometrie d'un edge
    
    Args:
        G: Graphe
        u, v: Noeuds de l'edge
        edge_data: Donnees de l'edge
        
    Returns:
        LineString representant l'edge
    """
    # Si la geometrie existe deja
    if 'geometry' in edge_data:
        return edge_data['geometry']
    
    # Sinon, creer une ligne droite entre les deux noeuds
    node_u = G.nodes[u]
    node_v = G.nodes[v]
    
    return LineString([
        (node_u['x'], node_u['y']),
        (node_v['x'], node_v['y'])
    ])


def calculate_vegetation_score(G: nx.Graph, u: int, v: int, edge_data: dict, 
                               pois: List[dict], radius: float = 5.0) -> float:
    """
    Score de vegetalisation: compte les elements naturels autour de l'edge
    
    Args:
        G: Graphe
        u, v: Noeuds de l'edge
        edge_data: Donnees de l'edge
        pois: Liste des POIs
        radius: Rayon de recherche en metres
        
    Returns:
        Score normalise entre 0 et 1
    """
    geometry = get_edge_geometry(G, u, v, edge_data)
    
    # Compter les POIs de type nature a proximite
    nature_count = 0
    
    for poi in pois:
        # Filtrer les POIs de categorie nature
        if poi.get('category') != 'nature':
            continue
        
        poi_point = Point(poi['x'], poi['y'])
        distance = geometry.distance(poi_point)
        
        if distance <= radius:
            nature_count += 1
    
    # Normalisation: on considere que 10 arbres dans 5m = score maximal
    # Utiliser une fonction sigmoide pour normaliser
    max_vegetation = 10.0
    score = min(nature_count / max_vegetation, 1.0)
    
    return score


def calculate_accessibility_score(G: nx.Graph, u: int, v: int, edge_data: dict) -> float:
    """
    Score d'accessibilite: penalise les escaliers et les pentes fortes
    
    Args:
        G: Graphe
        u, v: Noeuds de l'edge
        edge_data: Donnees de l'edge
        
    Returns:
        Score normalise entre -1 et 1 (negatif = mauvais pour accessibilite)
    """
    score = 0.0
    
    # 1. ESCALIERS - tres penalisant
    if edge_data.get('highway') == 'steps':
        return -1.0  # Score minimal pour escaliers
    
    # 2. DENIVELE
    node_u = G.nodes[u]
    node_v = G.nodes[v]
    
    # Recuperer les altitudes si disponibles
    elev_u = node_u.get('elevation', 0.0)
    elev_v = node_v.get('elevation', 0.0)
    
    elevation_diff = abs(elev_v - elev_u)
    length = edge_data.get('length', 1.0)
    
    # Calculer la pente en pourcentage
    if length > 0:
        slope_percent = (elevation_diff / length) * 100
    else:
        slope_percent = 0.0
    
    # Penaliser les pentes fortes
    # 0-5% : excellente accessibilite (score proche de 1)
    # 5-10% : bonne (score 0.5)
    # >10% : mauvaise (score negatif)
    if slope_percent < 5:
        score = 1.0 - (slope_percent / 5) * 0.2  # 1.0 -> 0.8
    elif slope_percent < 10:
        score = 0.8 - ((slope_percent - 5) / 5) * 0.6  # 0.8 -> 0.2
    else:
        score = 0.2 - min((slope_percent - 10) / 10, 1.2)  # 0.2 -> -1.0
    
    # 3. LARGEUR DU TROTTOIR (si disponible dans OSM)
    sidewalk_width = edge_data.get('sidewalk:width', None)
    if sidewalk_width:
        try:
            width = float(sidewalk_width)
            # Largeur ideale >= 2m
            if width >= 2.0:
                score += 0.2
            elif width >= 1.5:
                score += 0.1
        except (ValueError, TypeError):
            pass
    
    # Bonus si marque comme accessible
    if edge_data.get('wheelchair') == 'yes':
        score += 0.2
    
    return np.clip(score, -1.0, 1.0)


def calculate_safety_score(G: nx.Graph, u: int, v: int, edge_data: dict) -> float:
    """
    Score de securite: base sur la largeur de la rue
    
    Note: Critere subjectif - a ameliorer avec feedback utilisateurs
    
    Args:
        G: Graphe
        u, v: Noeuds de l'edge
        edge_data: Donnees de l'edge
        
    Returns:
        Score normalise entre 0 et 1
    """
    score = 0.5  # Score neutre par defaut
    
    # 1. TYPE DE RUE
    highway_type = edge_data.get('highway', 'residential')
    
    # Rues pietonnes et zones residentielles = plus sur
    safe_types = ['pedestrian', 'footway', 'path', 'living_street']
    if highway_type in safe_types:
        score = 0.9
    elif highway_type in ['residential', 'service']:
        score = 0.7
    elif highway_type in ['primary', 'secondary', 'tertiary']:
        score = 0.4
    elif highway_type in ['trunk', 'motorway']:
        score = 0.1
    
    # 2. LARGEUR DE LA RUE
    width = edge_data.get('width', None)
    if width:
        try:
            width_val = float(width)
            # Rues tres larges peuvent etre moins sures (beaucoup de trafic)
            # Rues tres etroites peuvent etre plus intimes mais potentiellement moins safe
            if 3 <= width_val <= 8:  # Largeur ideale
                score += 0.1
            elif width_val > 15:  # Tres large
                score -= 0.2
        except (ValueError, TypeError):
            pass
    
    # 3. ECLAIRAGE
    if edge_data.get('lit') == 'yes':
        score += 0.15
    
    # 4. PRESENCE DE TROTTOIRS
    if edge_data.get('sidewalk') in ['both', 'yes', 'left', 'right']:
        score += 0.1
    
    # 5. ZONE 30 / Zone de rencontre
    if edge_data.get('maxspeed') in ['30', '20', '10']:
        score += 0.15
    
    return np.clip(score, 0.0, 1.0)


def calculate_culture_score(G: nx.Graph, u: int, v: int, edge_data: dict,
                            pois: List[dict], radius: float = 20.0) -> float:
    """
    Score culturel/architectural: nombre de POIs culturels a proximite
    
    Note: Dans une version future, pourrait utiliser le nombre de photos postees
    
    Args:
        G: Graphe
        u, v: Noeuds de l'edge
        edge_data: Donnees de l'edge
        pois: Liste des POIs
        radius: Rayon de recherche en metres
        
    Returns:
        Score normalise entre 0 et 1
    """
    geometry = get_edge_geometry(G, u, v, edge_data)
    
    # Compter les POIs culturels a proximite
    cultural_count = 0
    cultural_categories = ['monument', 'tourism', 'heritage']
    
    for poi in pois:
        # Filtrer les POIs culturels
        if poi.get('category') not in cultural_categories:
            continue
        
        poi_point = Point(poi['x'], poi['y'])
        distance = geometry.distance(poi_point)
        
        if distance <= radius:
            # Ponderer par la distance (plus proche = meilleur)
            weight = 1.0 - (distance / radius)
            cultural_count += weight
    
    # Normalisation: 5 monuments dans 20m = score maximal
    max_cultural = 5.0
    score = min(cultural_count / max_cultural, 1.0)
    
    return score


def calculate_slope_score(G: nx.Graph, u: int, v: int, edge_data: dict) -> float:
    """
    Score de denivele: penalise les montees/descentes importantes
    
    Note: Different de l'accessibilite car ici on penalise TOUTES les variations,
    meme pour des personnes valides (moins agreable de monter/descendre)
    
    Args:
        G: Graphe
        u, v: Noeuds de l'edge
        edge_data: Donnees de l'edge
        
    Returns:
        Score normalise entre -1 et 1 (negatif = beaucoup de denivele)
    """
    node_u = G.nodes[u]
    node_v = G.nodes[v]
    
    # Recuperer les altitudes
    elev_u = node_u.get('elevation', 0.0)
    elev_v = node_v.get('elevation', 0.0)
    
    elevation_diff = abs(elev_v - elev_u)
    length = edge_data.get('length', 1.0)
    
    # Calculer la pente
    if length > 0:
        slope_percent = (elevation_diff / length) * 100
    else:
        slope_percent = 0.0
    
    # Penaliser progressivement
    # 0-3% : excellent (plat)
    # 3-8% : acceptable
    # >8% : desagreable
    if slope_percent < 3:
        score = 1.0
    elif slope_percent < 8:
        score = 1.0 - ((slope_percent - 3) / 5) * 0.8  # 1.0 -> 0.2
    else:
        score = 0.2 - min((slope_percent - 8) / 10, 1.2)  # 0.2 -> -1.0
    
    return np.clip(score, -1.0, 1.0)


def calculate_bikeability_score(G: nx.Graph, u: int, v: int, edge_data: dict,
                               pois: List[dict], radius: float = 50.0) -> float:
    """
    Score de cyclabilite: pistes cyclables, parkings velo
    
    Args:
        G: Graphe
        u, v: Noeuds de l'edge
        edge_data: Donnees de l'edge
        pois: Liste des POIs
        radius: Rayon de recherche pour parkings velo
        
    Returns:
        Score normalise entre 0 et 1
    """
    score = 0.0
    
    # 1. INFRASTRUCTURE CYCLABLE
    highway_type = edge_data.get('highway', '')
    
    # Piste cyclable dediee
    if highway_type in ['cycleway', 'path']:
        score = 1.0
    
    # Bande cyclable sur la route
    cycleway = edge_data.get('cycleway', '')
    if cycleway in ['lane', 'track', 'opposite_lane', 'opposite_track']:
        score = 0.8
    elif cycleway in ['shared_lane', 'shared']:
        score = 0.5
    
    # Zone partagee avec voitures
    if edge_data.get('bicycle') == 'yes':
        score = max(score, 0.4)
    
    # 2. PARKING VELO A PROXIMITE
    geometry = get_edge_geometry(G, u, v, edge_data)
    
    for poi in pois:
        # Chercher les parkings velo dans les POIs
        amenity = poi.get('amenity', '')
        if amenity == 'bicycle_parking':
            poi_point = Point(poi['x'], poi['y'])
            distance = geometry.distance(poi_point)
            
            if distance <= radius:
                score += 0.2
                break  # Un seul parking suffit
    
    # 3. ZONES 30 / VOIES CALMES (bonus pour cyclabilite)
    if edge_data.get('maxspeed') in ['30', '20', '10']:
        score += 0.1
    
    return np.clip(score, 0.0, 1.0)


def calculate_all_scores(G: nx.Graph, pois: List[dict], 
                        verbose: bool = True) -> nx.Graph:
    """
    Calcule tous les scores pour tous les edges du graphe
    
    Args:
        G: Graphe
        pois: Liste des POIs
        verbose: Afficher la progression
        
    Returns:
        G: Graphe avec scores calcules
    """
    print("\n" + "=" * 70)
    print("CALCUL DES VECTEURS DE SCORE (SSV)")
    print("=" * 70)
    
    total_edges = G.number_of_edges()
    
    for i, (u, v, edge_data) in enumerate(G.edges(data=True)):
        # Calculer chaque dimension du score
        scores = np.array([
            calculate_vegetation_score(G, u, v, edge_data, pois),
            calculate_accessibility_score(G, u, v, edge_data),
            calculate_safety_score(G, u, v, edge_data),
            calculate_culture_score(G, u, v, edge_data, pois),
            calculate_slope_score(G, u, v, edge_data),
            calculate_bikeability_score(G, u, v, edge_data, pois)
        ])
        
        # Assigner le vecteur de score
        edge_data['score_vector'] = scores
        
        # Afficher progression
        if verbose and (i + 1) % 1000 == 0:
            print(f"   Progression: {i+1}/{total_edges} edges traites "
                  f"({100*(i+1)/total_edges:.1f}%)")
    
    print(f"OK: Scores calcules pour {total_edges} edges")
    
    return G


def save_scored_graph(G: nx.Graph, metadata: dict, filepath: str = None):
    """
    Sauvegarde le graphe avec les scores
    
    Args:
        G: Graphe avec scores
        metadata: Metadonnees
        filepath: Chemin de sauvegarde
    """
    if filepath is None:
        filepath = PROJECT_ROOT / "data" / "processed" / "graph.pkl"
    else:
        filepath = Path(filepath)
    
    print(f"\nSauvegarde du graphe avec scores...")
    print(f"Destination: {filepath}")
    
    # Creer le dossier si necessaire
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    with open(filepath, 'wb') as f:
        pickle.dump((G, metadata), f)
    
    print(f"OK: Graphe sauvegarde dans: {filepath}")


def analyze_scores(G: nx.Graph):
    """
    Analyse statistique des scores calcules
    
    Args:
        G: Graphe avec scores
    """
    print("\n" + "=" * 70)
    print("ANALYSE DES SCORES")
    print("=" * 70)
    
    score_labels = [
        "Vegetalisation",
        "Accessibilite", 
        "Securite",
        "Culture",
        "Denivele",
        "Cyclabilite"
    ]
    
    # Collecter tous les scores
    all_scores = []
    for u, v, edge_data in G.edges(data=True):
        all_scores.append(edge_data['score_vector'])
    
    all_scores = np.array(all_scores)
    
    # Statistiques par dimension
    for i, label in enumerate(score_labels):
        scores_dim = all_scores[:, i]
        print(f"\n{label}:")
        print(f"   Min:    {scores_dim.min():.3f}")
        print(f"   Max:    {scores_dim.max():.3f}")
        print(f"   Moyenne: {scores_dim.mean():.3f}")
        print(f"   Mediane: {np.median(scores_dim):.3f}")
        print(f"   Std:    {scores_dim.std():.3f}")
    
    print("\n" + "=" * 70)


def main():
    """
    Pipeline complet de calcul des scores
    """
    # 1. Charger le graphe
    print("Chargement du graphe...")
    G, metadata = load_graph()
    
    # 2. Charger les POIs
    print("Chargement des POIs...")
    pois = load_pois()
    print(f"OK: {len(pois)} POIs charges")
    
    # 3. Calculer les scores
    G = calculate_all_scores(G, pois, verbose=True)
    
    # 4. Analyser les resultats
    analyze_scores(G)
    
    # 5. Sauvegarder
    save_scored_graph(G, metadata)
    
    print("\nCalcul des scores termine avec succes!")


if __name__ == "__main__":
    main()