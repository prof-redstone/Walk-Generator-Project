import osmnx as ox
import os
from datetime import datetime

def download_network(
    city: str = "Clermont-Ferrand, France", #Pour l'instant
    network_type: str = "walk",
    save_dir: str = "projet/data/raw"):

    """
    Télécharge le réseau routier d'une ville depuis OSM
    
    Args:
        city: Nom de la ville à télécharger
        network_type: Type de réseau ('walk', 'drive', 'bike', 'all')
        save_dir: Dossier où sauvegarder les données
        
    Returns:
        G: Graphe NetworkX du réseau routier
    """

    #print(f"Téléchargement du réseau de {city}...")
    #print(f"   Type: {network_type}")
    
    
    os.makedirs(save_dir, exist_ok=True)# Créer le dossier si nécessaire
    
    try:
        G = ox.graph_from_place(city, network_type=network_type)
        
        print(f"Réseau téléchargé:")
        print(f"   - Noeuds: {G.number_of_nodes()}")
        print(f"   - Arêtes: {G.number_of_edges()}")
        
        # Sauvegarder en GraphML (format qui préserve tous les attributs)
        filepath = os.path.join(save_dir, "clermont_network.graphml")
        ox.save_graphml(G, filepath)
        print(f" Sauvegardé dans: {filepath}")
        
        # Sauvegarder aussi des métadonnées
        metadata = {
            "city": city,
            "network_type": network_type,
            "download_date": datetime.now().isoformat(),
            "nodes_count": G.number_of_nodes(),
            "edges_count": G.number_of_edges()
        }
                
        return G, metadata
        
    except Exception as e:
        print(f"❌ Erreur lors du téléchargement: {e}")
        raise


# !!!!!! Option 2 fait par Claude, pas utile mais pas bete donc je garde dans le doute, ça peut être pratique :
def download_network_from_bbox(
    north: float,
    south: float,
    east: float,
    west: float,
    network_type: str = "walk",
    save_dir: str = "data/raw"
):
    """
    Alternative: télécharger par bounding box (plus précis)
    
    Args:
        north, south, east, west: Coordonnées de la bbox
        network_type: Type de réseau
        save_dir: Dossier de sauvegarde
        
    Returns:
        G: Graphe NetworkX
    """
    print(f"Téléchargement du réseau dans la bbox:")
    print(f"   N:{north}, S:{south}, E:{east}, W:{west}")
    
    os.makedirs(save_dir, exist_ok=True)
    
    try:
        G = ox.graph_from_bbox(north, south, east, west, network_type=network_type)
        
        print(f"✅ Réseau téléchargé:")
        print(f"   - Nœuds: {G.number_of_nodes()}")
        print(f"   - Arêtes: {G.number_of_edges()}")
        
        filepath = os.path.join(save_dir, "clermont_network.graphml")
        ox.save_graphml(G, filepath)
        print(f"💾 Sauvegardé dans: {filepath}")
        
        metadata = {
            "bbox": {"north": north, "south": south, "east": east, "west": west},
            "network_type": network_type,
            "download_date": datetime.now().isoformat(),
            "nodes_count": G.number_of_nodes(),
            "edges_count": G.number_of_edges()
        }
        
        return G, metadata
        
    except Exception as e:
        print(f"❌ Erreur lors du téléchargement: {e}")
        raise


if __name__ == "__main__":
    
    G, metadata = download_network("Clermont-Ferrand, France")
    
    # !!!!!! Option 2 fait par Claude, pas utile mais pas bete donc je garde dans le doute, ça peut être pratique :

    # Option 2: Par bounding box (pour zone plus précise)
    # Clermont-Ferrand centre approximatif
    # G, metadata = download_network_from_bbox(
    #     north=45.7950, #Coordonnée par Claude donc probablement fausse. Ok non j'ai vérif et c'est ça, c'est fou quand même les IA ça retient plein de truc ! (estomaqué)
    #     south=45.7650,
    #     east=3.1050,
    #     west=3.0700
    # )