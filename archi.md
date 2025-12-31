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
│   │   └── metadata.json             # Infos sur la zone, date de DL, etc. Utile dans le futur
│   │
│   ├── results/                      #Dossier contenant tous les fichiers de résultat d'execution de visualization ou autre (.html de folium -> carte interactive).
│   │
│   └── user_data/                    # Données utilisateur
│       └── user_123_history.pkl      # Historique des chemins parcourus
│
└── src/
    ├── data_acquisition/
    │   ├── download_network.py       # Téléchargement réseau routier
    │   └── download_pois.py          # Téléchargement des pois
    │
    ├── preprocessing/
    │   ├── graph_builder.py          # Construit le graphe NetworkX
    │   ├── score_calculator.py       # Calcule tous les SSV
    │   └── poi_processor.py          # Traite les POIs et trouve nearest_edge
    │
    ├── algorithms/
    │   ├── algo1.py                  # Sélection des points de préselection
    │   ├── algo2.py                  # Génération du chemin
    │   ├── astar.py                  # A* adapté avec scores (redondance avec algo2_path_generation ? Pas forcement utile)
    │   └── atomic_operations.py      # ShortCut, Parallel, etc. (à voir si on met pas directement dans algo2_path_generation)
    │
    ├── utils/
    │   └── scoring.py                # Produits scalaires SSV·UPV (pas forcement utile, très simple peut rester dans un autre fichier qui l'utilise)
    │
    └── visualization/
        ├── show_path.py              # pour afficher le chemin résultant, avec les points selectionné passant par le chemin.
        └── interactive_map.py        # Affichage interactif (à la fin si il nous reste du temps, objectif second du projet).
