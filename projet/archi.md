Idée archi (donc pas forcement la plus pertinante et sujet à modif !)

projet/
│
├── main.py                           # Point d'entrée principal
│
├── data/
│   ├── raw/                          # Données brutes OSM (ne pas versionner)
│   │   ├── clermont_network.graphml
│   │   └── clermont_pois.geojson
│   │
│   ├── processed/                    # Données traitées (à générer)
│   │   ├── graph.pkl                 # Graphe NetworkX avec tous les attributs
│   │   ├── pois.pkl                  # Liste des POIs traités
│   │   └── metadata.json             # Infos sur la zone, date de DL, etc.
│   │
│   ├── results/                      #Dossier contenant tous les fichiers de résultat d'execution de visualization (.html de folium -> carte interactive).
│   │
│   └── user_data/                    # Données utilisateur
│       └── user_123_history.pkl      # Historique des chemins parcourus
│
└── src/
    ├── data_acquisition/
    │   ├── download_network.py       # Téléchargement réseau routier
    │   ├── download_pois.py          # Téléchargement des pois
    │   └── data_validator.py         # Vérifier intégrité des données (-voir l'utilité car directement dans les 2 autres fichiers) (graph connexe, pas noeuds deg = 0)
    │
    ├── preprocessing/
    │   ├── graph_builder.py          # Construit le graphe NetworkX
    │   ├── score_calculator.py       # Calcule tous les SSV
    │   └── poi_processor.py          # Traite les POIs et trouve nearest_edge
    │
    ├── algorithms/
    │   ├── algo1_point_selection.py  # Sélection des points de préselection
    │   ├── algo2_path_generation.py  # Génération du chemin
    │   ├── astar.py                  # A* adapté avec scores (redondance avec algo2_path_generation ? Pas forcement utile)
    │   └── atomic_operations.py      # ShortCut, Parallel, etc. (à voir si on met pas directement dans algo2_path_generation)
    │
    ├── utils/
    │   ├── geometry.py               # Fonctions géométriques
    │   ├── distance.py               # Calculs de distances (pas forcement utile, aprox distance avec norme L2 (pytghagore))
    │   └── scoring.py                # Produits scalaires SSV·UPV (pas forcement utile, très simple peut rester dans un autre fichier qui l'utilise)
    │
    └── visualization/
        ├── show_path.py              # pour afficher le chemin résultant, avec les points selectionné passant par le chemin.
        └── interactive_map.py        # Affichage interactif (à la fin si il nous reste du temps, objectif second du projet).
