import osmnx as ox
import networkx as nx
import pickle
import os
from datetime import datetime
import numpy as np


def load_raw_graph(filepath: str):
    """Charge le graphe brut depuis le fichier GraphML"""
    print(f"Chargement du graphe depuis {filepath}...")
    
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Fichier non trouve: {filepath}")
    
    G = ox.load_graphml(filepath)
    print(f"Graphe charge: {G.number_of_nodes()} noeuds, {G.number_of_edges()} aretes")
    
    return G


def simplify_graph(G: nx.MultiDiGraph):
    """Simplifie le graphe: projection, consolidation, simplification"""
    print(f"\nSimplification du graphe...")
    
    # Projection en metres
    print("   Projection du graphe (Lat/Lon -> Metres)...")
    if G.graph.get('crs', 'epsg:4326') == 'epsg:4326':
        G = ox.project_graph(G)
    
    print(f"   Avant: {G.number_of_nodes()} noeuds, {G.number_of_edges()} aretes")
    
    # Consolidation des intersections
    distance_tolerance = 5
    print(f"   Consolidation des intersections ({distance_tolerance}m)...")
    G = ox.consolidate_intersections(
        G, 
        tolerance=distance_tolerance, 
        rebuild_graph=True, 
        dead_ends=False, 
        reconnect_edges=True
    )
    
    # Simplification
    try:
        G = ox.simplification.simplify_graph(G)
    except Exception as e:
        if "already been simplified" in str(e):
            print("   Le graphe est deja simplifie.")
        else:
            raise e
            
    print(f"   Apres: {G.number_of_nodes()} noeuds, {G.number_of_edges()} aretes")
    
    return G


def add_edge_attributes(G: nx.MultiDiGraph):
    """Ajoute les attributs aux edges: score_vector, penalty, gratification"""
    print(f"\nAjout des attributs aux edges...")
    
    SCORE_DIMENSIONS = 6
    edge_count = 0
    
    for u, v, key, data in G.edges(keys=True, data=True):
        data['score_vector'] = np.zeros(SCORE_DIMENSIONS)
        data['penalty'] = 0.0
        data['gratification'] = 0.0
        
        if 'length' not in data:
            node_u = G.nodes[u]
            node_v = G.nodes[v]
            
            if 'x' in node_u and 'y' in node_u and 'x' in node_v and 'y' in node_v:
                dx = node_v['x'] - node_u['x']
                dy = node_v['y'] - node_u['y']
                data['length'] = np.sqrt(dx**2 + dy**2)
            else:
                data['length'] = 100.0
        
        edge_count += 1
    
    print(f"   {edge_count} edges mis a jour")
    
    return G


def add_node_attributes(G: nx.MultiDiGraph):
    """Verifie les attributs des noeuds"""
    print(f"\nVerification des attributs des noeuds...")
    
    nodes_without_coords = 0
    
    for node, data in G.nodes(data=True):
        if 'x' not in data or 'y' not in data:
            nodes_without_coords += 1
    
    if nodes_without_coords > 0:
        print(f"   WARN: {nodes_without_coords} noeuds sans coordonnees")
    else:
        print(f"   Tous les noeuds ont des coordonnees")
    
    return G


def build_processed_graph(
    raw_graph_path: str = "../../data/raw/clermont_network.graphml",
    save_path: str = "../../data/processed/graph.pkl"
):
    """Pipeline complet de construction du graphe optimise"""
    print("=" * 70)
    print("CONSTRUCTION DU GRAPHE OPTIMISE")
    print("=" * 70)
    
    G = load_raw_graph(raw_graph_path)
    G = simplify_graph(G)
    G = add_edge_attributes(G)
    G = add_node_attributes(G)
    
    metadata = {
        "creation_date": datetime.now().isoformat(),
        "nodes_count": G.number_of_nodes(),
        "edges_count": G.number_of_edges(),
        "graph_type": "MultiDiGraph",
        "score_dimensions": 6,
        "score_labels": [
            "vegetalisation",
            "accessibilite", 
            "securite",
            "culture",
            "denivele",
            "cyclabilite"
        ]
    }
    
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    
    print(f"\nSauvegarde du graphe...")
    with open(save_path, 'wb') as f:
        pickle.dump((G, metadata), f)
    
    print(f"Graphe sauvegarde dans: {save_path}")
    
    print("\n" + "=" * 70)
    print("RESUME DU GRAPHE TRAITE")
    print("=" * 70)
    print(f"   Noeuds: {metadata['nodes_count']}")
    print(f"   Aretes: {metadata['edges_count']}")
    print(f"   Type: {metadata['graph_type']}")
    print(f"   Dimensions du score: {metadata['score_dimensions']}")
    print("=" * 70)
    
    return G, metadata


def load_processed_graph(filepath: str = "../../data/processed/graph.pkl"):
    """Charge le graphe traite depuis le pickle"""
    print(f"Chargement du graphe traite depuis {filepath}...")
    
    if not os.path.exists(filepath):
        raise FileNotFoundError(
            f"Graphe traite non trouve. Executez d'abord build_processed_graph()"
        )
    
    with open(filepath, 'rb') as f:
        G, metadata = pickle.load(f)
    
    print(f"Graphe charge: {G.number_of_nodes()} noeuds, {G.number_of_edges()} aretes")
    print(f"   Type: {type(G).__name__}")
    
    return G, metadata


if __name__ == "__main__":
    G, metadata = build_processed_graph()
    
    print("\n" + "=" * 70)
    print("TEST DE RECHARGEMENT")
    print("=" * 70)
    G_loaded, metadata_loaded = load_processed_graph()
    
    sample_edges = list(G_loaded.edges(keys=True, data=True))
    if sample_edges:
        u, v, key, edge_data = sample_edges[0]
        print(f"\nExemple d'edge ({u} -> {v}, key={key}):")
        print(f"   - length: {edge_data.get('length', 'N/A')}")
        print(f"   - score_vector shape: {edge_data['score_vector'].shape}")
        print(f"   - penalty: {edge_data['penalty']}")
        print(f"   - gratification: {edge_data['gratification']}")