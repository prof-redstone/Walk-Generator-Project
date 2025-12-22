import osmnx as ox
import networkx as nx
import pickle
import os
from datetime import datetime
import numpy as np


def load_raw_graph(filepath: str = "data/raw/clermont_network.graphml"):
    """
    Charge le graphe brut depuis le fichier GraphML
    
    Args:
        filepath: Chemin vers le fichier GraphML
        
    Returns:
        G: Graphe NetworkX brut
    """
    print(f"📂 Chargement du graphe depuis {filepath}...")
    
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Fichier non trouvé: {filepath}")
    
    G = ox.load_graphml(filepath)
    print(f"✅ Graphe chargé: {G.number_of_nodes()} nœuds, {G.number_of_edges()} arêtes")
    
    return G


def simplify_graph(G: nx.MultiDiGraph):
    """
    Simplifie le graphe:
    - Fusionne les intersections proches
    - Simplifie les segments de rue sans intersection
    
    Args:
        G: Graphe MultiDiGraph d'OSMnx
        
    Returns:
        G_simplified: Graphe simplifié
    """
    print(f"\n🔧 Simplification du graphe...")
    print(f"   Avant: {G.number_of_nodes()} nœuds, {G.number_of_edges()} arêtes")
    
    # Consolider les intersections proches (rayon 15m)
    tolerance=10 #On considère que 2 intersection séparé de moins de tolerance metre, sont les mêmes intersections. Voir si ça pose pb si on a intersection tous les 9m par ex.
    G = ox.consolidate_intersections(G, tolerance, rebuild_graph=True, dead_ends=False, reconnect_edges=True)
    
    # Simplifier les segments (fusionner les nœuds intermédiaires)
    G = ox.simplification.simplify_graph(G)
    
    print(f"   Après: {G.number_of_nodes()} nœuds, {G.number_of_edges()} arêtes")
    
    return G


def convert_to_undirected(G: nx.MultiDiGraph):
    """
    Convertit le graphe dirigé en non-dirigé (marche = bidirectionnel)
    Supprime les multi-edges en gardant le plus court
    
    Args:
        G: MultiDiGraph
        
    Returns:
        G_simple: Graph simple non-dirigé
    """
    print(f"\n🔄 Conversion en graphe non-dirigé...")
    
    # Convertir en non-dirigé
    G_undirected = G.to_undirected()
    
    # Créer un graphe simple (sans multi-edges)
    G_simple = nx.Graph()
    
    # Copier les nœuds avec leurs attributs
    for node, data in G_undirected.nodes(data=True):
        G_simple.add_node(node, **data)
    
    # Pour chaque paire de nœuds, garder seulement l'edge le plus court
    edge_count = 0
    for u, v, key, data in G_undirected.edges(keys=True, data=True):
        if not G_simple.has_edge(u, v):
            G_simple.add_edge(u, v, **data)
            edge_count += 1
        else:
            # Comparer les longueurs et garder le plus court
            current_length = G_simple[u][v].get('length', float('inf'))
            new_length = data.get('length', float('inf'))
            
            if new_length < current_length:
                G_simple[u][v].update(data)
    
    print(f"   {G_undirected.number_of_edges()} multi-edges -> {G_simple.number_of_edges()} edges simples")
    
    return G_simple


def add_edge_attributes(G: nx.Graph):
    """
    Ajoute les attributs nécessaires aux edges pour les algorithmes:
    - score_vector (initialisé à zéro, sera calculé plus tard)
    - penalty (pour historique utilisateur)
    - gratification (pour POIs proches)
    
    Args:
        G: Graphe simple
        
    Returns:
        G: Graphe avec nouveaux attributs
    """
    print(f"\n Ajout des attributs aux edges...")
    
    # Nombre de dimensions du vecteur de score
    # [végétalisation, accessibilité, sécurité, culture, dénivelé, cyclabilité]
    SCORE_DIMENSIONS = 6
    
    edge_count = 0
    for u, v, data in G.edges(data=True):
        # Initialiser le vecteur de score (sera calculé dans score_calculator.py)
        data['score_vector'] = np.zeros(SCORE_DIMENSIONS)
        
        # Initialiser pénalisation (historique utilisateur)
        data['penalty'] = 0.0
        
        # Initialiser gratification (POIs proches)
        data['gratification'] = 0.0
        
        # Garder les attributs OSM utiles
        # length est déjà présent normalement
        if 'length' not in data:
            # Calculer la longueur euclidienne si pas présente
            node_u = G.nodes[u]
            node_v = G.nodes[v]
            
            # Approximation rapide (pas parfaite mais suffisante)
            if 'x' in node_u and 'y' in node_u:
                dx = node_v['x'] - node_u['x']
                dy = node_v['y'] - node_u['y']
                data['length'] = np.sqrt(dx**2 + dy**2)
            else:
                data['length'] = 100.0  # Valeur par défaut
        
        edge_count += 1
    
    print(f"   ✅ {edge_count} edges mis à jour")
    
    return G


def add_node_attributes(G: nx.Graph):
    """
    S'assure que les nœuds ont les attributs nécessaires
    
    Args:
        G: Graphe
        
    Returns:
        G: Graphe avec attributs de nœuds vérifiés
    """
    print(f"\n🔍 Vérification des attributs des nœuds...")
    
    nodes_without_coords = 0
    
    for node, data in G.nodes(data=True):
        # Vérifier que les coordonnées existent
        if 'x' not in data or 'y' not in data:
            nodes_without_coords += 1
    
    if nodes_without_coords > 0:
        print(f"   ⚠️  {nodes_without_coords} nœuds sans coordonnées")
    else:
        print(f"   ✅ Tous les nœuds ont des coordonnées")
    
    return G


def build_processed_graph(
    raw_graph_path: str = "data/raw/clermont_network.graphml",
    save_path: str = "data/processed/graph.pkl"
):
    """
    Pipeline complet de construction du graphe optimisé
    
    Args:
        raw_graph_path: Chemin vers le graphe brut
        save_path: Chemin de sauvegarde du graphe traité
        
    Returns:
        G: Graphe traité et prêt pour les algorithmes
        metadata: Dictionnaire avec statistiques
    """
    print("=" * 70)
    print("  CONSTRUCTION DU GRAPHE OPTIMISÉ")
    print("=" * 70)
    
    # 1. Charger le graphe brut
    G = load_raw_graph(raw_graph_path)
    
    # 2. Simplifier
    G = simplify_graph(G)
    
    # 3. Convertir en non-dirigé simple
    G = convert_to_undirected(G)
    
    # 4. Ajouter les attributs pour les edges
    G = add_edge_attributes(G)
    
    # 5. Vérifier les attributs des nœuds
    G = add_node_attributes(G)
    
    # 6. Métadonnées
    metadata = {
        "creation_date": datetime.now().isoformat(),
        "nodes_count": G.number_of_nodes(),
        "edges_count": G.number_of_edges(),
        "graph_type": "undirected_simple",
        "score_dimensions": 6,
        "score_labels": [
            "végétalisation",
            "accessibilité", 
            "sécurité",
            "culture",
            "dénivelé",
            "cyclabilité"
        ]
    }
    
    # 7. Sauvegarder
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    
    print(f"\n💾 Sauvegarde du graphe...")
    with open(save_path, 'wb') as f:
        pickle.dump((G, metadata), f)
    
    print(f"✅ Graphe sauvegardé dans: {save_path}")
    
    # 8. Afficher le résumé
    print("\n" + "=" * 70)
    print("📊 RÉSUMÉ DU GRAPHE TRAITÉ")
    print("=" * 70)
    print(f"   Nœuds: {metadata['nodes_count']}")
    print(f"   Arêtes: {metadata['edges_count']}")
    print(f"   Type: {metadata['graph_type']}")
    print(f"   Dimensions du score: {metadata['score_dimensions']}")
    print(f"   Labels: {', '.join(metadata['score_labels'])}")
    print("=" * 70)
    
    return G, metadata


def load_processed_graph(filepath: str = "data/processed/graph.pkl"):
    """
    Charge le graphe traité depuis le pickle
    
    Args:
        filepath: Chemin vers le fichier pickle
        
    Returns:
        G: Graphe traité
        metadata: Métadonnées
    """
    print(f"📂 Chargement du graphe traité depuis {filepath}...")
    
    if not os.path.exists(filepath):
        raise FileNotFoundError(
            f"Graphe traité non trouvé. Exécutez d'abord build_processed_graph()"
        )
    
    with open(filepath, 'rb') as f:
        G, metadata = pickle.load(f)
    
    print(f"✅ Graphe chargé: {G.number_of_nodes()} nœuds, {G.number_of_edges()} arêtes")
    
    return G, metadata


if __name__ == "__main__":
    # Construction du graphe optimisé
    G, metadata = build_processed_graph()
    
    # Test de rechargement
    print("\n" + "=" * 70)
    print("🧪 TEST DE RECHARGEMENT")
    print("=" * 70)
    G_loaded, metadata_loaded = load_processed_graph()
    
    # Vérifier qu'un edge a bien tous les attributs
    u, v = list(G_loaded.edges())[0]
    edge_data = G_loaded[u][v]
    print(f"\n🔍 Exemple d'edge ({u} -> {v}):")
    print(f"   - length: {edge_data.get('length', 'N/A')}")
    print(f"   - score_vector shape: {edge_data['score_vector'].shape}")
    print(f"   - penalty: {edge_data['penalty']}")
    print(f"   - gratification: {edge_data['gratification']}")
    
    print("\n✅ Tous les tests passés !")