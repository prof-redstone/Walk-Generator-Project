import osmnx as ox
import geopandas as gpd
import pandas as pd
import os
import pickle

# Définition des catégories de POIs pertinentes pour Baladéo
POI_CATEGORIES = {
    'monuments': {
        'historic': ['monument', 'memorial', 'castle', 'ruins', 'archaeological_site'],
        'tourism': ['attraction', 'viewpoint', 'artwork']
    },
    'culture': {
        'amenity': ['theatre', 'cinema', 'arts_centre', 'library'],
        'tourism': ['museum', 'gallery']
    },
    'nature': {
        'leisure': ['park', 'garden', 'nature_reserve', 'beach'],
        'natural': ['tree', 'wood', 'water']
    },
    'food_drink': {
        'amenity': ['restaurant', 'cafe', 'bar', 'pub', 'fast_food', 'ice_cream']
    },
    'religious': {
        'amenity': ['place_of_worship'],
        'building': ['church', 'cathedral', 'chapel', 'basilica', 'mosque', 'synagogue']
    },
    'shopping': {
        'shop': ['bakery', 'supermarket', 'mall', 'gift', 'books', 'clothes']
    },
    'leisure': {
        'leisure': ['playground', 'sports_centre', 'stadium', 'pitch'],
        'sport': True  # Tous les sports
    }
}


def get_poi_categories(row):
    """
    Détermine toutes les catégories auxquelles un POI appartient
    """
    categories = []
    for cat_name, cat_tags in POI_CATEGORIES.items():
        matches = False
        for tag_key, tag_values in cat_tags.items():
            if tag_values is True:  # Cas spécial pour 'sport': True
                if row.get(tag_key) is not None:
                    matches = True
                    break
            elif isinstance(tag_values, list):
                if row.get(tag_key) in tag_values:
                    matches = True
                    break
        if matches:
            categories.append(cat_name)
    return categories


def process_pois(
    raw_pois_path: str = "projet/data/raw/clermont_pois.geojson",
    graph_path: str = "projet/data/raw/clermont_network.graphml",
    processed_dir: str = "projet/data/processed"
):
    """
    Traite les POIs bruts : détermine les catégories, trouve les arêtes les plus proches
    
    Args:
        raw_pois_path: Chemin vers le fichier GeoJSON des POIs bruts
        graph_path: Chemin vers le fichier GraphML du réseau
        processed_dir: Dossier où sauvegarder les données traitées
        
    Returns:
        pois_processed: GeoDataFrame des POIs traités
    """
    print("Traitement des POIs...")
    
    # Créer le dossier processed s'il n'existe pas
    os.makedirs(processed_dir, exist_ok=True)
    
    # Charger le graphe
    print(f"Chargement du graphe depuis {graph_path}...")
    G = ox.load_graphml(graph_path)
    print(f"Graphe chargé: {G.number_of_nodes()} noeuds, {G.number_of_edges()} arêtes")
    
    # Charger les POIs bruts
    print(f"Chargement des POIs depuis {raw_pois_path}...")
    pois_gdf = gpd.read_file(raw_pois_path)
    pois_gdf.reset_index(inplace=True)
    print(f"{len(pois_gdf)} POIs chargés")
    
    # Déterminer les catégories pour chaque POI
    print("Détermination des catégories...")
    pois_gdf['categories'] = pois_gdf.apply(get_poi_categories, axis=1)
    
    # Trouver l'arête la plus proche pour chaque POI
    print("Recherche des arêtes les plus proches...")
    # Les coordonnées sont en EPSG:4326 (degrés)
    # nearest_edges attend les coordonnées dans le même CRS que le graphe
    nearest_edges = ox.nearest_edges(G, pois_gdf.geometry.x, pois_gdf.geometry.y)
    pois_gdf['nearest_edge'] = nearest_edges
    
    # Garder seulement les colonnes utiles
    columns_to_keep = ['name', 'geometry', 'categories', 'nearest_edge']
    pois_processed = pois_gdf[columns_to_keep].copy()
    
    # Sauvegarder en pickle
    pois_pickle_path = os.path.join(processed_dir, "pois.pkl")
    with open(pois_pickle_path, 'wb') as f:
        pickle.dump(pois_processed, f)
    print(f"POIs traités sauvegardés dans {pois_pickle_path}")
    
    # Afficher un résumé
    print(f"\n✅ {len(pois_processed)} POIs traités")
    print("Colonnes finales:", pois_processed.columns.tolist())
    print("\nExemples:")
    for idx, row in pois_processed.head(5).iterrows():
        print(f"- {row['name'] or 'Sans nom'}: {row['categories']} (arête: {row['nearest_edge']})")
    
    return pois_processed


if __name__ == "__main__":
    # Traiter les POIs
    pois_processed = process_pois()
