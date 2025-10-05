import osmnx as ox

def clean_graphml(input_path="clermont_graph.graphml", output_path="clermont_clean.graphml"):
    # Charge le graphe
    G = ox.load_graphml(input_path)

    # Attributs utiles
    keep_node_attrs = {"x", "y", "street_count", "highway"}
    keep_edge_attrs = {"length", "geometry", "highway", "oneway", "name"}

    # Nettoyage des nœuds
    for node, data in G.nodes(data=True):
        keys_to_remove = set(data.keys()) - keep_node_attrs
        for key in keys_to_remove:
            del data[key]

    # Nettoyage des arêtes
    for u, v, k, data in G.edges(keys=True, data=True):
        keys_to_remove = set(data.keys()) - keep_edge_attrs
        for key in keys_to_remove:
            del data[key]

    # Sauvegarde du graphe nettoyé
    ox.save_graphml(G, output_path)
    print(f"Graphe nettoyé sauvegardé dans {output_path}")

if __name__ == "__main__":
    clean_graphml()
