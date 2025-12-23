import networkx as nx
import folium
import pickle
import numpy as np
from pyproj import Transformer
from shapely.geometry import LineString

# --- CONFIGURATION DE LA PROJECTION ---
# EPSG:32631 = UTM Zone 31N (Standard pour cette partie de la France en UTM)
# EPSG:2154  = Lambert 93 (Standard national français)
# EPSG:4326  = WGS84 (GPS / Folium / Google Maps)
SOURCE_CRS = "EPSG:32631"  # <--- Si ça ne marche pas, "EPSG:2154"
TARGET_CRS = "EPSG:4326"

def get_transformer():
    """Initialise le convertisseur de coordonnées."""
    # always_xy=True assure qu'on passe (lon, lat) ou (x, y) dans le bon ordre
    return Transformer.from_crs(SOURCE_CRS, TARGET_CRS, always_xy=True)

def project_coords(x, y, transformer):
    """Convertit x, y (mètres) en lon, lat (degrés)."""
    lon, lat = transformer.transform(x, y)
    # Folium attend [lat, lon], pyproj renvoie (lon, lat)
    return lat, lon

def show_full_graph(
    graph_path: str = "projet/data/processed/graph.pkl",
    save_path: str = "projet/data/processed/clermont_graph.html",
    show_fictif: bool = True,
    edge_color: str = "blue",
    edge_weight: float = 2,
    zoom_start: int = 13
):
    print("🗺️  Chargement du graphe pour visualisation...")
    
    with open(graph_path, 'rb') as f:
        G, metadata = pickle.load(f)
    
    print(f"✅ Graphe chargé: {G.number_of_nodes()} nœuds")
    
    # Initialiser le convertisseur de projection
    transformer = get_transformer()
    #print(f"🌍 Conversion des coordonnées de {SOURCE_CRS} vers WGS84...")

    node_coords = {} # Stocke {node_id: (lat, lon)}
    lats = []
    lons = []
    fictif_nodes = []

    # 1. Convertir tous les nœuds
    for node, data in G.nodes(data=True):
        if 'x' in data and 'y' in data:
            lat, lon = project_coords(data['x'], data['y'], transformer)
            node_coords[node] = (lat, lon)
            lats.append(lat)
            lons.append(lon)
            
            if data.get('fictif', False):
                fictif_nodes.append(node)

    # Centrer la carte sur la moyenne des points réels
    if lats and lons:
        center_lat = np.mean(lats)
        center_lon = np.mean(lons)
    else:
        print("Impossible de centrer la carte !")

    #print(f"📍 Centre calculé: ({center_lat:.4f}, {center_lon:.4f})")
    
    m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_start, tiles='OpenStreetMap', max_zoom=25)

    # 2. Ajouter les arêtes (avec géométrie précise si dispo)
    #print("🎨 Ajout des arêtes...")
    edge_count = 0
    
    for u, v, data in G.edges(data=True):
        if u in node_coords and v in node_coords:
            points = []
            
            # Cas 1: L'arête possède une géométrie détaillée (courbure des rues)
            if 'geometry' in data:
                try:
                    # Si c'est un objet Shapely
                    if isinstance(data['geometry'], LineString):
                        coords = list(data['geometry'].coords)
                    # Si c'est déjà une liste
                    else:
                        coords = data['geometry']
                        
                    # On doit projeter CHAQUE point de la ligne
                    for x, y in coords:
                        lat, lon = project_coords(x, y, transformer)
                        points.append([lat, lon])
                except Exception as e:
                    # Fallback ligne droite en cas d'erreur
                    points = [node_coords[u], node_coords[v]]            
            # Cas 2: Pas de géométrie, ligne droite entre nœuds
            else:
                points = [node_coords[u], node_coords[v]]
            
            if points:
                folium.PolyLine(
                    points,
                    color=edge_color,
                    weight=edge_weight,
                    opacity=0.6,
                    popup=f"Len: {data.get('length', 0):.0f}m"
                ).add_to(m)
                edge_count += 1

    # 3. Ajouter les nœuds fictifs
    if show_fictif and fictif_nodes:
        print(f"🎨 Ajout des {len(fictif_nodes)} nœuds fictifs...")
        for node in fictif_nodes:
            if node in node_coords:
                folium.CircleMarker(
                    location=node_coords[node],
                    radius=4,
                    color='red',
                    fill=True,
                    fillColor='red',
                    popup=f"Nœud fictif: {node}"
                ).add_to(m)

    m.save(save_path)
    print(f"✅ Carte sauvegardée : {save_path}")
    return m


if __name__ == "__main__":
    show_full_graph()