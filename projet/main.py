import sys
import os
import webbrowser

# Ajouter le dossier src au path si nécessaire
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.visualization.show_path import (
    show_full_graph
)


def main():
    """
    Programme principal de test de visualisation
    """
    
    # Chemin vers le graphe traité
    graph_path = "projet/data/processed/graph.pkl"
    
    # Vérifier que le fichier existe
    if not os.path.exists(graph_path):
        print(f"❌ Erreur: Le graphe traité n'existe pas à {graph_path}")
        print("   Veuillez d'abord exécuter graph_builder.py")
        return
    
    try:            
        print("\n🎨 Génération de la carte interactive...")
        
        output_path = "projet/data/results/clermont_graph.html"
        
        show_full_graph(
            save_path=output_path,
            graph_path=graph_path,
            edge_color="blue",
            edge_weight=2,
            show_fictif=True,
            zoom_start=13
        )
        
        # Ouvrir automatiquement dans le navigateur
        abs_path = os.path.abspath(output_path)
        print(f"\n🌐 Ouverture dans le navigateur...")
        webbrowser.open('file://' + abs_path)        
            
        
    except FileNotFoundError as e:
        print(f"\n❌ Erreur: {e}")
        print("   Vérifiez que le graphe a bien été généré avec graph_builder.py")
        
    except Exception as e:
        print(f"\n❌ Erreur inattendue: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()