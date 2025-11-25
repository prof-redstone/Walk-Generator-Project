import osmnx as ox

def get_pedestrian_graph(city="Clermont-Ferrand, France", save_path="clermont_graph.graphml"):
    # Télécharge le graphe pour les piétons
    G = ox.graph_from_place(city, network_type="walk")
    
    # Sauvegarde en .graphml pour réutiliser plus tard
    ox.save_graphml(G, save_path)
    print(f"Graphe sauvegardé dans {save_path}")
    return G

if __name__ == "__main__":
    G = get_pedestrian_graph()

