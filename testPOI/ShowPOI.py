import geopandas as gpd
import folium

def show_pois_interactive(geojson_path="clermont_bars.geojson", output_map="pois_map.html"):
    gdf = gpd.read_file(geojson_path)
    
    # Centre de la carte = centroid des POIs
    center = gdf.geometry.unary_union.centroid
    m = folium.Map(location=[center.y, center.x], zoom_start=14)
    
    # Ajoute les POIs comme marqueurs
    for _, row in gdf.iterrows():
        # Récupère les coordonnées du point
        if row.geometry.geom_type == 'Point':
            coords = [row.geometry.y, row.geometry.x]
        else:
            # Si c'est un polygone, prend le centroid
            coords = [row.geometry.centroid.y, row.geometry.centroid.x]
        
        # Récupère le nom et le type
        name = row.get('name', 'Sans nom')
        amenity = row.get('amenity', 'Inconnu')
        
        # Crée un popup avec les infos
        popup_text = f"<b>{name}</b><br>Type: {amenity}"
        
        # Ajoute le marqueur
        folium.Marker(
            location=coords,
            popup=folium.Popup(popup_text, max_width=200),
            icon=folium.Icon(color='red', icon='info-sign')
        ).add_to(m)
    
    # Sauvegarde la carte
    m.save(output_map)
    print(f"Carte générée : {output_map}")
    print(f"Nombre de POIs affichés : {len(gdf)}")

if __name__ == "__main__":
    show_pois_interactive()