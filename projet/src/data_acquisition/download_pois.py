import osmnx as ox
import geopandas as gpd
import os
from datetime import datetime

# Définition des catégories de POIs pertinentes pour Baladéo
#Categories générer par Claude : vérifier l'existance et la pertinance !!!!!!!
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


def download_pois(
    city: str = "Clermont-Ferrand, France",
    categories: list = None,
    save_dir: str = "projet/data/raw"
):
    """
    Télécharge les POIs d'une ville depuis OSM
    
    Args:
        city: Nom de la ville
        categories: Liste des catégories à télécharger (None = toutes)
        save_dir: Dossier de sauvegarde
        
    Returns:
        gdf: GeoDataFrame contenant tous les POIs
        metadata: Dictionnaire avec les statistiques
    """
    print(f"Téléchargement des POIs de {city}...")
    
    os.makedirs(save_dir, exist_ok=True)
    
    # Si aucune catégorie spécifiée, prendre toutes
    if categories is None:
        categories = list(POI_CATEGORIES.keys())
    
    all_pois = []
    stats = {}
    
    # Télécharger chaque catégorie
    for category in categories:
        if category not in POI_CATEGORIES:
            print(f"!  Catégorie inconnue: {category}")
            continue
            
        print(f"\n Catégorie: {category}")
        tags = POI_CATEGORIES[category]
        
        try:
            gdf = ox.features_from_place(city, tags=tags)
            
            if len(gdf) > 0:
                # Ajouter la catégorie comme colonne
                gdf['category'] = category
                all_pois.append(gdf)
                stats[category] = len(gdf)
                print(f"{len(gdf)} POIs trouvés")
            else:
                print(f"Aucun POI trouvé")
                stats[category] = 0
                
        except Exception as e:
            print(f"❌ Erreur: {e}")
            stats[category] = 0
    
    # Combiner tous les POIs
    if all_pois:
        combined_gdf = gpd.GeoDataFrame(
            pd.concat(all_pois, ignore_index=True),
            crs=all_pois[0].crs
        )
        
        # Ne garder que les colonnes utiles
        useful_columns = [
            'osmid', 'name', 'geometry', 'category',
            'amenity', 'tourism', 'historic', 'leisure', 'natural',
            'building', 'sport'
        ]
        
        # Garder seulement les colonnes qui existent
        columns_to_keep = [col for col in useful_columns if col in combined_gdf.columns]
        combined_gdf = combined_gdf[columns_to_keep]


        
        # Ne garder que les Points et Polygones (convertir polygones en centroides)
        print(f"\n📊 Traitement des géométries...")
        original_count = len(combined_gdf)
        
        #projection en metre pour calcul plus précis, pas forcement utile mais sinon warning dans la console donc relou.
        # 1. On projette en mètres pour un calcul précis
        combined_gdf = combined_gdf.to_crs(epsg=3857) 
        
        # 2. Calcul du centroïde
        mask_polygon = combined_gdf.geometry.type.isin(['Polygon', 'MultiPolygon'])
        combined_gdf.loc[mask_polygon, 'geometry'] = combined_gdf.loc[mask_polygon, 'geometry'].centroid
        
        # 3. On repasse en degrés (WGS84) pour le format GeoJSON
        combined_gdf = combined_gdf.to_crs(epsg=4326)

        # Supprimer les lignes (pas pertinent pour nous)
        combined_gdf = combined_gdf[combined_gdf.geometry.type == 'Point']
        
        print(f"   {original_count} POIs -> {len(combined_gdf)} points, très peu de perte = très bien, càd données propre de base.")
        


        # Sauvegarder
        filepath = os.path.join(save_dir, "clermont_pois.geojson")
        combined_gdf.to_file(filepath, driver='GeoJSON')
        print(f"\n💾 Sauvegardé dans: {filepath}")
        
        # Métadonnées
        metadata = {
            "city": city,
            "download_date": datetime.now().isoformat(),
            "total_pois": len(combined_gdf),
            "categories": stats
        }
        
        # Afficher le résumé
        print(f"\n✅ Total: {len(combined_gdf)} POIs")
        print(f"   Répartition par catégorie:")
        for cat, count in stats.items():
            if count > 0:
                print(f"   - {cat}: {count}")
        
        return combined_gdf, metadata
    
    else:
        print("❌ Aucun POI téléchargé")
        return None, None




if __name__ == "__main__":
    import pandas as pd
    
    #Télécharger toutes les catégories
    gdf, metadata = download_pois("Clermont-Ferrand, France")
    
    if gdf is not None:
        print(f"\n📋 Colonnes disponibles: {gdf.columns.tolist()}")
        print(f"\n🔝 Premiers POIs:")
        print(gdf[['name', 'category', 'amenity']].head(10))
    