import geopandas as gpd
import folium
import pickle
import numpy as np
from pyproj import Transformer
import os

# --- CONFIGURATION DE LA PROJECTION ---
# EPSG:32631 = UTM Zone 31N (Standard pour cette partie de la France en UTM)
# EPSG:2154  = Lambert 93 (Standard national français)
# EPSG:4326  = WGS84 (GPS / Folium / Google Maps)
SOURCE_CRS = "EPSG:32631"  # <--- Si ça ne marche pas, "EPSG:2154"
TARGET_CRS = "EPSG:4326"

def get_transformer():
    """Initialise le convertisseur de coordonnées."""
    # always_xy=True assure qu'on passe (lon, lat) ou (x, y) dans le bon ordre
    return Transformer.from_crs(TARGET_CRS, SOURCE_CRS, always_xy=True)

def latlon_to_utm(lat, lon, transformer):
    """Convertit lat, lon (degrés) en x, y (mètres)."""
    x, y = transformer.transform(lon, lat)
    return x, y

def utm_to_latlon(x, y, transformer):
    """Convertit x, y (mètres) en lat, lon (degrés)."""
    lon, lat = transformer.transform(x, y)
    return lat, lon

def filter_pois_in_path_range(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    max_distance_meters: float,
    pois_path: str = "projet/data/processed/pois.pkl"
):
    """
    Filtre les POIs p tels que distance(A->p) + distance(p->B) <= max_distance_meters.

    Args:
        start_lat: Latitude du point A (degrés)
        start_lon: Longitude du point A (degrés)
        end_lat: Latitude du point B (degrés)
        end_lon: Longitude du point B (degrés)
        max_distance_meters: Distance maximale A->p + p->B en mètres
        pois_path: Chemin vers le fichier pois.pkl

    Returns:
        valid_pois: Liste de tuples (poi, dist_a_to_p, dist_p_to_b, total_dist)
    """
    print("🗺️ Chargement des POIs pour filtrage de l'algo 1...")

    # Vérifier que le fichier existe
    if not os.path.exists(pois_path):
        print(f"❌ Erreur: Le fichier POIs n'existe pas à {pois_path}")
        return []

    # Charger les POIs
    with open(pois_path, 'rb') as f:
        pois_gdf = pickle.load(f)

    print(f"✅ POIs chargés: {len(pois_gdf)} POIs")

    # Initialiser le convertisseur de projection
    transformer = get_transformer()

    # Convertir A et B en UTM
    start_x, start_y = latlon_to_utm(start_lat, start_lon, transformer)
    end_x, end_y = latlon_to_utm(end_lat, end_lon, transformer)

    # Filtrer les POIs où dist(A,p) + dist(p,B) <= max_distance_meters
    valid_pois = []
    for idx, poi in pois_gdf.iterrows():
        poi_lat = poi.geometry.y
        poi_lon = poi.geometry.x
        poi_x, poi_y = latlon_to_utm(poi_lat, poi_lon, transformer)

        dist_a_to_p = np.sqrt((poi_x - start_x)**2 + (poi_y - start_y)**2)
        dist_p_to_b = np.sqrt((end_x - poi_x)**2 + (end_y - poi_y)**2)
        total_dist = dist_a_to_p + dist_p_to_b

        if total_dist <= max_distance_meters:
            valid_pois.append((poi, dist_a_to_p, dist_p_to_b, total_dist))

    print(f"📍 {len(valid_pois)} POIs valides pour A->p->B <= {max_distance_meters}m")
    return valid_pois

def show_pois_in_path_range_map(
    filtered_pois,
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    save_path: str,
    zoom_start: int = 13
):
    """
    Affiche les POIs filtrés sur une carte avec les points A et B.

    Args:
        filtered_pois: Liste de tuples (poi, dist_a, dist_b, total) retournée par filter_pois_in_path_range
        start_lat: Latitude du point A (degrés)
        start_lon: Longitude du point A (degrés)
        end_lat: Latitude du point B (degrés)
        end_lon: Longitude du point B (degrés)
        save_path: Chemin où sauvegarder la carte HTML
        zoom_start: Niveau de zoom initial
    """
    print("🗺️ Génération de la carte...")

    # Initialiser le convertisseur pour la distance directe
    transformer = get_transformer()
    start_x, start_y = latlon_to_utm(start_lat, start_lon, transformer)
    end_x, end_y = latlon_to_utm(end_lat, end_lon, transformer)

    # Centrer la carte sur le milieu entre A et B
    center_lat = (start_lat + end_lat) / 2
    center_lon = (start_lon + end_lon) / 2

    m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_start, tiles='OpenStreetMap', max_zoom=25)

    # Ajouter le point A (départ)
    folium.Marker(
        location=[start_lat, start_lon],
        popup="Point de départ (A)",
        icon=folium.Icon(color='green', icon='play')
    ).add_to(m)

    # Ajouter le point B (arrivée)
    folium.Marker(
        location=[end_lat, end_lon],
        popup="Point d'arrivée (B)",
        icon=folium.Icon(color='red', icon='stop')
    ).add_to(m)

    # Ajouter une ligne entre A et B
    folium.PolyLine(
        locations=[[start_lat, start_lon], [end_lat, end_lon]],
        color='black',
        weight=3,
        opacity=0.7,
        popup=f"Distance directe: {np.sqrt((end_x - start_x)**2 + (end_y - start_y)**2):.0f}m"
    ).add_to(m)

    # Ajouter les POIs valides
    for poi, dist_a, dist_b, total in filtered_pois:
        poi_lat = poi.geometry.y
        poi_lon = poi.geometry.x
        name = poi.get('name', 'Sans nom')
        categories = ', '.join(poi.get('categories', []))

        # Créer un popup avec les infos
        popup_text = f"<b>{name}</b><br>A->POI: {dist_a:.0f}m<br>POI->B: {dist_b:.0f}m<br>Total: {total:.0f}m<br>Catégories: {categories}"

        folium.Marker(
            location=[poi_lat, poi_lon],
            popup=popup_text,
            icon=folium.Icon(color='blue', icon='info-sign')
        ).add_to(m)

    # Sauvegarder la carte
    m.save(save_path)
    print(f"✅ Carte sauvegardée : {save_path}")
    return m

def show_pois_in_path_range(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    max_distance_meters: float,
    save_path: str,
    pois_path: str = "projet/data/processed/pois.pkl",
    zoom_start: int = 13
):
    """
    Fonction combinée pour filtrer et afficher les POIs (pour compatibilité).
    """
    filtered = filter_pois_in_path_range(start_lat, start_lon, end_lat, end_lon, max_distance_meters, pois_path)
    return show_pois_in_path_range_map(filtered, start_lat, start_lon, end_lat, end_lon, save_path, zoom_start)

if __name__ == "__main__":
    # Exemple d'utilisation
    start_lat = 45.7640  # Point A
    start_lon = 3.0824
    end_lat = 45.7800    # Point B
    end_lon = 3.0924
    max_dist = 2200  # en metre
    
    # Filtrer les POIs
    filtered_pois = filter_pois_in_path_range(start_lat, start_lon, end_lat, end_lon, max_dist)
    
    # Afficher sur la carte
    show_pois_in_path_range_map(filtered_pois, start_lat, start_lon, end_lat, end_lon, "projet/data/results/algo1_pois.html")