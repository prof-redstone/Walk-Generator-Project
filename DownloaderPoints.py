import osmnx as ox
import geopandas as gpd



def get_bars(city="Clermont-Ferrand, France", save_path="clermont_bars.geojson"):
    # Définir les tags pour les bars et établissements similaires
    tags = {
        'amenity': ['bar', 'cafe'],
    }
    
    # Télécharge les POIs correspondant aux tags
    gdf = ox.features_from_place(city, tags=tags)
    
    # Sauvegarde en GeoJSON pour réutiliser plus tard
    gdf.to_file(save_path, driver='GeoJSON')
    print(f"POIs sauvegardés dans {save_path}")
    print(f"Nombre de bars/pubs trouvés : {len(gdf)}")
    
    return gdf

if __name__ == "__main__":
    
    bars = get_bars()
    
    
    print("\nColonnes disponibles :", bars.columns.tolist())
    print("\nPremiers bars :")
    print(bars[['name', 'amenity']].head() if 'name' in bars.columns else bars['amenity'].head())