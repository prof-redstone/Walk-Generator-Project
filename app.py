import osmnx as ox
import folium

#recupere les infos du graphe avec toutes les rues et genere un fichier html avec toutes les rues.

def show_graph_interactive(graph_path="clermont_graph.graphml", output_map="map.html"):
    # Recharge le graphe
    G = ox.load_graphml(graph_path)

    # Convertit en GeoDataFrames (nœuds et arêtes)
    nodes, edges = ox.graph_to_gdfs(G)

    # Centre de la carte = centroid du graphe
    center = nodes.geometry.unary_union.centroid
    m = folium.Map(location=[center.y, center.x], zoom_start=14)

    # Ajoute les routes
    for _, row in edges.iterrows():
        points = [(y, x) for x, y in row["geometry"].coords]
        folium.PolyLine(points, color="blue", weight=2, opacity=0.8).add_to(m)

    # Sauvegarde et ouvre la carte
    m.save(output_map)
    print(f"Carte générée : {output_map}")

if __name__ == "__main__":
    show_graph_interactive()

