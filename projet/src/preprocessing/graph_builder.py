import osmnx as ox
import networkx as nx
import pickle
import os
from datetime import datetime
import numpy as np


def load_raw_graph(filepath: str):
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
    - Projette le graphe en mètres (UTM) pour des calculs précis
    - Fusionne les intersections proches
    - Tente de simplifier si le graphe est encore brut
    """
    print(f"\n🔧 Simplification du graphe...")
    
    # 1. PROJECTION (Indispensable pour corriger les warnings et avoir des mètres)
    print("   🌐 Projection du graphe (Lat/Lon -> Mètres)...")
    if G.graph.get('crs', 'epsg:4326') == 'epsg:4326':
        G = ox.project_graph(G)
    
    print(f"   Avant: {G.number_of_nodes()} nœuds, {G.number_of_edges()} arêtes")
    
    # 2. CONSOLIDATION DES INTERSECTIONS
    distance_tolerance = 5
    print(f"   🔨 Consolidation des intersections ({distance_tolerance}m)...")
    G = ox.consolidate_intersections(
        G, 
        tolerance=distance_tolerance, 
        rebuild_graph=True, 
        dead_ends=False, 
        reconnect_edges=True
    )
    
    # 3. SIMPLIFICATION (Sécurisée)
    # On essaie de simplifier, mais on ignore l'erreur si c'est déjà fait
    try:
        G = ox.simplification.simplify_graph(G)
    except Exception as e:
        # On attrape l'erreur spécifique d'OSMnx ou générique
        if "already been simplified" in str(e):
            print("   ℹ️  Le graphe est déjà simplifié (étape ignorée).")
        else:
            raise e
            
    print(f"   Après: {G.number_of_nodes()} nœuds, {G.number_of_edges()} arêtes")
    
    return G


def convert_to_simple_graph(G: nx.MultiDiGraph):
    """
    Convertit le pseudographe en graphe simple via la méthode du "Dummy Node Proximal".
    
    Stratégie pour les arêtes multiples / boucles :
    - On crée un nœud fictif (dummy) TRÈS PROCHE du nœud de départ 'u'.
    - Segment 1 (u -> dummy) : Longueur quasi-nulle (ex: 10cm), pas de géométrie complexe.
    - Segment 2 (dummy -> v) : Longueur réelle, conserve TOUTE la géométrie et les infos.
    """
    print(f"\n🔄 Conversion en graphe simple")
    
    G_undirected = G.to_undirected()
    G_simple = nx.Graph()
    
    # 1. Copier les nœuds
    for node, data in G_undirected.nodes(data=True):
        G_simple.add_node(node, **data)
    
    midpoint_counter = 0
    processed_pairs = set()
    
    for u, v in G_undirected.edges():
        pair = tuple(sorted([u, v]))
        if pair in processed_pairs:
            continue
        processed_pairs.add(pair)
        
        edges_dict = G_undirected[u][v]
        num_edges = len(edges_dict)
        
        # CAS 1 : Arête simple (on garde tel quel)
        if num_edges == 1 and u != v:
            key = list(edges_dict.keys())[0]
            G_simple.add_edge(u, v, **edges_dict[key])
            
        # CAS 2 : Arêtes multiples ou Boucles
        else:
            # Pour CHAQUE arête parallèle, on crée un chemin via un dummy node
            for key, edge_data in edges_dict.items():
                dummy_id = f"dummy_{midpoint_counter}"
                midpoint_counter += 1
                
                # --- A. Positionnement du Dummy Node ---
                # On le place très près de 'u' (le nœud de départ arbitraire)
                node_u = G_simple.nodes[u]
                                
                dummy_x = node_u['x'] 
                dummy_y = node_u['y'] + 0.00001 #décalage de 1m vers le nord
                
                G_simple.add_node(dummy_id, x=dummy_x, y=dummy_y, fictif=True)
                
                # --- B. Création des 2 segments ---
                
                # Segment Court (u <-> dummy)
                # Distance arbitraire très faible (ex: 1 mètre) pour éviter division par zéro
                short_len = 1.0 
                G_simple.add_edge(u, dummy_id, length=short_len, type="connector")
                
                # Segment Long (dummy <-> v)
                # Il récupère TOUTES les données réelles (longueur - 1m, géométrie, score, etc.)
                real_len = max(edge_data.get('length', 10.0) - short_len, 0.1)
                
                long_attrs = edge_data.copy()
                long_attrs['length'] = real_len
                
                # Si c'est une boucle (u==v), le segment long revient vers u
                target = v
                
                G_simple.add_edge(dummy_id, target, **long_attrs)

    print(f"   ✅ Terminé : {midpoint_counter} arêtes complexes éclatées.")
    return G_simple


def add_edge_attributes(G: nx.Graph):
    """
    Ajoute les attributs nécessaires aux edges pour les algorithmes:
    - score_vector (initialisé à zéro, sera calculé plus tard)
    - penalty (pour historique utilisateur)
    - gratification (pour POIs proches)
    
    Args:
        G: Graph simple
        
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
    fictif_nodes = 0
    
    for node, data in G.nodes(data=True):
        # Compter les nœuds fictifs
        if data.get('fictif', False):
            fictif_nodes += 1
        
        # Vérifier que les coordonnées existent
        if 'x' not in data or 'y' not in data:
            nodes_without_coords += 1
    
    if nodes_without_coords > 0:
        print(f"   ⚠️  {nodes_without_coords} nœuds sans coordonnées")
    else:
        print(f"   ✅ Tous les nœuds ont des coordonnées")
    
    if fictif_nodes > 0:
        print(f"   📌 {fictif_nodes} nœuds fictifs (pour rues parallèles/boucles)")
    
    return G


def build_processed_graph(
    raw_graph_path: str = "projet/data/raw/clermont_network.graphml",
    save_path: str = "projet/data/processed/graph.pkl"
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
    print("CONSTRUCTION DU GRAPHE OPTIMISÉ")
    print("=" * 70)
    
    # 1. Charger le graphe brut
    G = load_raw_graph(raw_graph_path)
    
    # 2. Simplifier
    G = simplify_graph(G)
    
    # 3. Convertir en graphe simple avec nœuds intermédiaires
    G = convert_to_simple_graph(G)
    
    # 4. Ajouter les attributs pour les edges
    G = add_edge_attributes(G)
    
    # 5. Vérifier les attributs des nœuds
    G = add_node_attributes(G)
    
    # 6. Métadonnées
    metadata = {
        "creation_date": datetime.now().isoformat(),
        "nodes_count": G.number_of_nodes(),
        "edges_count": G.number_of_edges(),
        "graph_type": "undirected_simple_with_midpoints",
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


def load_processed_graph(filepath: str = "projet/data/processed/graph.pkl"):
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
    
    test_de_rechargement = True
    
    if test_de_rechargement:
        # Test de rechargement
        print("\n" + "=" * 70)
        print("🧪 TEST DE RECHARGEMENT")
        print("=" * 70)
        G_loaded, metadata_loaded = load_processed_graph()
        
        # Vérifier qu'un edge a bien tous les attributs
        sample_edges = list(G_loaded.edges(data=True))
        if sample_edges:
            u, v, edge_data = sample_edges[0]
            print(f"\n🔍 Exemple d'edge ({u} -> {v}):")
            print(f"   - length: {edge_data.get('length', 'N/A')}")
            print(f"   - score_vector shape: {edge_data['score_vector'].shape}")
            print(f"   - penalty: {edge_data['penalty']}")
            print(f"   - gratification: {edge_data['gratification']}")
            
            # Afficher info sur les nœuds
            node_u = G_loaded.nodes[u]
            node_v = G_loaded.nodes[v]
            if node_u.get('fictif', False) or node_v.get('fictif', False):
                print(f"   ℹ️  Cet edge contient un nœud fictif")
        