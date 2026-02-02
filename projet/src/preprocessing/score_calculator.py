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
    """Trouve la racine du projet"""
    current = Path(__file__).resolve().parent
    
    while current.name != 'projet' and current.parent != current:
        current = current.parent
    
    if current.name == 'projet':
        return current
    
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
            f"Racine du projet detectee: {PROJECT_ROOT}"
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
        pois_data = pickle.load(f)
    
    # Convertir en liste de dictionnaires si necessaire
    if isinstance(pois_data, list):
        # Si c'est deja une liste, verifier le format
        if len(pois_data) > 0:
            if isinstance(pois_data[0], str):
                # Format incorrect, retourner liste vide
                print("Format POIs incorrect, ignore")
                return []
        return pois_data
    
    return []


def get_edge_geometry(G: nx.MultiDiGraph, u: int, v: int, key: int, edge_data: dict) -> LineString:
    """Recupere ou construit la geometrie d'un edge"""
    if 'geometry' in edge_data:
        return edge_data['geometry']
    
    node_u = G.nodes[u]
    node_v = G.nodes[v]
    
    return LineString([
        (node_u['x'], node_u['y']),
        (node_v['x'], node_v['y'])
    ])


def calculate_vegetation_score(G: nx.MultiDiGraph, u: int, v: int, key: int, 
                               edge_data: dict, pois: List[dict], radius: float = 5.0) -> float:
    """Score de vegetalisation"""
    geometry = get_edge_geometry(G, u, v, key, edge_data)
    
    nature_count = 0
    
    for poi in pois:
        if not isinstance(poi, dict):
            continue
            
        if poi.get('category') != 'nature':
            continue
        
        if 'x' not in poi or 'y' not in poi:
            continue
        
        poi_point = Point(poi['x'], poi['y'])
        distance = geometry.distance(poi_point)
        
        if distance <= radius:
            nature_count += 1
    
    max_vegetation = 10.0
    score = min(nature_count / max_vegetation, 1.0)
    
    return score


def calculate_accessibility_score(G: nx.MultiDiGraph, u: int, v: int, key: int, edge_data: dict) -> float:
    """Score d'accessibilite"""
    score = 0.0
    
    if edge_data.get('highway') == 'steps':
        return -1.0
    
    node_u = G.nodes[u]
    node_v = G.nodes[v]
    
    elev_u = node_u.get('elevation', 0.0)
    elev_v = node_v.get('elevation', 0.0)
    
    elevation_diff = abs(elev_v - elev_u)
    length = edge_data.get('length', 1.0)
    
    if length > 0:
        slope_percent = (elevation_diff / length) * 100
    else:
        slope_percent = 0.0
    
    if slope_percent < 5:
        score = 1.0 - (slope_percent / 5) * 0.2
    elif slope_percent < 10:
        score = 0.8 - ((slope_percent - 5) / 5) * 0.6
    else:
        score = 0.2 - min((slope_percent - 10) / 10, 1.2)
    
    if edge_data.get('wheelchair') == 'yes':
        score += 0.2
    
    return np.clip(score, -1.0, 1.0)


def calculate_safety_score(G: nx.MultiDiGraph, u: int, v: int, key: int, edge_data: dict) -> float:
    """Score de securite"""
    score = 0.5
    
    highway_type = edge_data.get('highway', 'residential')
    
    safe_types = ['pedestrian', 'footway', 'path', 'living_street']
    if highway_type in safe_types:
        score = 0.9
    elif highway_type in ['residential', 'service']:
        score = 0.7
    elif highway_type in ['primary', 'secondary', 'tertiary']:
        score = 0.4
    elif highway_type in ['trunk', 'motorway']:
        score = 0.1
    
    if edge_data.get('lit') == 'yes':
        score += 0.15
    
    if edge_data.get('sidewalk') in ['both', 'yes', 'left', 'right']:
        score += 0.1
    
    if edge_data.get('maxspeed') in ['30', '20', '10']:
        score += 0.15
    
    return np.clip(score, 0.0, 1.0)


def calculate_culture_score(G: nx.MultiDiGraph, u: int, v: int, key: int, edge_data: dict,
                            pois: List[dict], radius: float = 20.0) -> float:
    """Score culturel"""
    geometry = get_edge_geometry(G, u, v, key, edge_data)
    
    cultural_count = 0
    cultural_categories = ['monument', 'tourism', 'heritage']
    
    for poi in pois:
        if not isinstance(poi, dict):
            continue
            
        if poi.get('category') not in cultural_categories:
            continue
        
        if 'x' not in poi or 'y' not in poi:
            continue
        
        poi_point = Point(poi['x'], poi['y'])
        distance = geometry.distance(poi_point)
        
        if distance <= radius:
            weight = 1.0 - (distance / radius)
            cultural_count += weight
    
    max_cultural = 5.0
    score = min(cultural_count / max_cultural, 1.0)
    
    return score


def calculate_slope_score(G: nx.MultiDiGraph, u: int, v: int, key: int, edge_data: dict) -> float:
    """Score de denivele"""
    node_u = G.nodes[u]
    node_v = G.nodes[v]
    
    elev_u = node_u.get('elevation', 0.0)
    elev_v = node_v.get('elevation', 0.0)
    
    elevation_diff = abs(elev_v - elev_u)
    length = edge_data.get('length', 1.0)
    
    if length > 0:
        slope_percent = (elevation_diff / length) * 100
    else:
        slope_percent = 0.0
    
    if slope_percent < 3:
        score = 1.0
    elif slope_percent < 8:
        score = 1.0 - ((slope_percent - 3) / 5) * 0.8
    else:
        score = 0.2 - min((slope_percent - 8) / 10, 1.2)
    
    return np.clip(score, -1.0, 1.0)


def calculate_bikeability_score(G: nx.MultiDiGraph, u: int, v: int, key: int, edge_data: dict,
                               pois: List[dict], radius: float = 50.0) -> float:
    """Score de cyclabilite"""
    score = 0.0
    
    highway_type = edge_data.get('highway', '')
    
    if highway_type in ['cycleway', 'path']:
        score = 1.0
    
    cycleway = edge_data.get('cycleway', '')
    if cycleway in ['lane', 'track', 'opposite_lane', 'opposite_track']:
        score = 0.8
    elif cycleway in ['shared_lane', 'shared']:
        score = 0.5
    
    if edge_data.get('bicycle') == 'yes':
        score = max(score, 0.4)
    
    geometry = get_edge_geometry(G, u, v, key, edge_data)
    
    for poi in pois:
        if not isinstance(poi, dict):
            continue
            
        amenity = poi.get('amenity', '')
        if amenity == 'bicycle_parking':
            if 'x' not in poi or 'y' not in poi:
                continue
                
            poi_point = Point(poi['x'], poi['y'])
            distance = geometry.distance(poi_point)
            
            if distance <= radius:
                score += 0.2
                break
    
    if edge_data.get('maxspeed') in ['30', '20', '10']:
        score += 0.1
    
    return np.clip(score, 0.0, 1.0)


def calculate_all_scores(G: nx.MultiDiGraph, pois: List[dict], 
                        verbose: bool = True) -> nx.MultiDiGraph:
    """Calcule tous les scores pour tous les edges du graphe"""
    print("\n" + "=" * 70)
    print("CALCUL DES VECTEURS DE SCORE (SSV)")
    print("=" * 70)
    
    total_edges = G.number_of_edges()
    
    for i, (u, v, key, edge_data) in enumerate(G.edges(keys=True, data=True)):
        scores = np.array([
            calculate_vegetation_score(G, u, v, key, edge_data, pois),
            calculate_accessibility_score(G, u, v, key, edge_data),
            calculate_safety_score(G, u, v, key, edge_data),
            calculate_culture_score(G, u, v, key, edge_data, pois),
            calculate_slope_score(G, u, v, key, edge_data),
            calculate_bikeability_score(G, u, v, key, edge_data, pois)
        ])
        
        edge_data['score_vector'] = scores
        
        if verbose and (i + 1) % 1000 == 0:
            print(f"   Progression: {i+1}/{total_edges} edges traites "
                  f"({100*(i+1)/total_edges:.1f}%)")
    
    print(f"OK: Scores calcules pour {total_edges} edges")
    
    return G


def save_scored_graph(G: nx.MultiDiGraph, metadata: dict, filepath: str = None):
    """Sauvegarde le graphe avec les scores"""
    if filepath is None:
        filepath = PROJECT_ROOT / "data" / "processed" / "graph.pkl"
    else:
        filepath = Path(filepath)
    
    print(f"\nSauvegarde du graphe avec scores...")
    print(f"Destination: {filepath}")
    
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    with open(filepath, 'wb') as f:
        pickle.dump((G, metadata), f)
    
    print(f"OK: Graphe sauvegarde dans: {filepath}")


def analyze_scores(G: nx.MultiDiGraph):
    """Analyse statistique des scores calcules"""
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
    
    all_scores = []
    for u, v, key, edge_data in G.edges(keys=True, data=True):
        all_scores.append(edge_data['score_vector'])
    
    all_scores = np.array(all_scores)
    
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
    """Pipeline complet de calcul des scores"""
    print("Chargement du graphe...")
    G, metadata = load_graph()
    
    print("Chargement des POIs...")
    pois = load_pois()
    print(f"OK: {len(pois)} POIs charges")
    
    G = calculate_all_scores(G, pois, verbose=True)
    
    analyze_scores(G)
    
    save_scored_graph(G, metadata)
    
    print("\nCalcul des scores termine avec succes!")


if __name__ == "__main__":
    main()