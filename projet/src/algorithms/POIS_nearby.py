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

def filter_nearby_pois(
    center_lat: float,
    center_lon: float,
    radius_meters: float,
    pois_path: str = "projet/data/processed/pois.pkl"
):
    """
    Filtre les POIs dans un rayon autour d'un point central.

    Args:
        center_lat: Latitude du centre (degrés)
        center_lon: Longitude du centre (degrés)
        radius_meters: Rayon en mètres
        pois_path: Chemin vers le fichier pois.pkl

    Returns:
        nearby_pois: Liste de tuples (poi, distance)
    """
    print("🗺️ Chargement des POIs pour filtrage...")

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

    # Convertir le centre en UTM
    center_x, center_y = latlon_to_utm(center_lat, center_lon, transformer)

    # Filtrer les POIs dans le rayon radius_meters
    nearby_pois = []
    for idx, poi in pois_gdf.iterrows():
        poi_lat = poi.geometry.y
        poi_lon = poi.geometry.x
        poi_x, poi_y = latlon_to_utm(poi_lat, poi_lon, transformer)
        distance = np.sqrt((poi_x - center_x)**2 + (poi_y - center_y)**2)
        if distance <= radius_meters:
            nearby_pois.append((poi, distance))

    print(f"📍 {len(nearby_pois)} POIs trouvés dans un rayon de {radius_meters}m")
    return nearby_pois

def show_nearby_pois_map(
    filtered_pois,
    center_lat: float,
    center_lon: float,
    save_path: str,
    zoom_start: int = 15
):
    """
    Affiche les POIs filtrés sur une carte.

    Args:
        filtered_pois: Liste de tuples (poi, distance) retournée par filter_nearby_pois
        center_lat: Latitude du centre (degrés)
        center_lon: Longitude du centre (degrés)
        save_path: Chemin où sauvegarder la carte HTML
        zoom_start: Niveau de zoom initial
    """
    print("🗺️ Génération de la carte...")

    # Créer la carte centrée sur le point
    m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_start, tiles='OpenStreetMap', max_zoom=25)

    # Ajouter le marqueur spécial au centre 
    folium.Marker(
        location=[center_lat, center_lon],
        popup="Point du centre",
        icon=folium.Icon(color='red')
    ).add_to(m)

    # Ajouter les POIs filtrés
    for poi, distance in filtered_pois:
        poi_lat = poi.geometry.y
        poi_lon = poi.geometry.x
        name = poi.get('name', 'Sans nom')
        categories = ', '.join(poi.get('categories', []))

        # Créer un popup avec les infos
        popup_text = f"<b>{name}</b><br>Distance: {distance:.0f}m<br>Catégories: {categories}"

        folium.Marker(
            location=[poi_lat, poi_lon],
            popup=popup_text,
            icon=folium.Icon(color='blue', icon='info-sign')
        ).add_to(m)

    # Sauvegarder la carte
    m.save(save_path)
    print(f"✅ Carte sauvegardée : {save_path}")
    return m

def show_nearby_pois(
    center_lat: float,
    center_lon: float,
    radius_meters: float,
    save_path: str,
    pois_path: str = "projet/data/processed/pois.pkl",
    zoom_start: int = 15
):
    """
    Fonction combinée pour filtrer et afficher les POIs (pour compatibilité).
    """
    filtered = filter_nearby_pois(center_lat, center_lon, radius_meters, pois_path)
    return show_nearby_pois_map(filtered, center_lat, center_lon, save_path, zoom_start)

if __name__ == "__main__":
    # Exemple d'utilisation
    center_lat = 45.7760  # Exemple: centre de Clermont-Ferrand (plein milieu de la place Jaude)
    center_lon = 3.0824
    radius = 500  # 500 mètres
    
    # Filtrer les POIs
    filtered_pois = filter_nearby_pois(center_lat, center_lon, radius)
    
    # Afficher sur la carte
    show_nearby_pois_map(filtered_pois, center_lat, center_lon, "projet/data/results/nearby_pois.html")