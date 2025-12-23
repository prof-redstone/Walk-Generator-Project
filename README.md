# Walk-Generator-Project

**Walk-Generator-Project** est un projet de génération intelligente de promenades urbaines, visant à proposer des itinéraires de marche **agréables, sûrs et personnalisés**, sous contrainte de **temps ou de distance**, plutôt que de simples chemins optimaux au sens géométrique.

📍 Le projet s’adresse aussi bien aux **touristes découvrant une ville** qu’aux **habitants souhaitant explorer autrement leur environnement**, en favorisant la nouveauté et la qualité de l’expérience.

---

## 👥 Équipe & Encadrement

- **Auteurs** : Vivien Fleuriot, Tom Demagny  
- **Encadrant** : Laurent Beaudou  

---

## 🎯 Objectifs du projet

Contrairement aux systèmes de navigation classiques, ce projet ne cherche **pas** le chemin le plus court, mais le **meilleur compromis** entre :

- plaisir de la balade,
- centres d’intérêt culturels et naturels,
- sécurité et accessibilité,
- respect strict d’une contrainte de temps ou de distance.

Les objectifs principaux sont :

- Générer des **chemins A → B** ou des **boucles** (A → A)
- Respecter une durée cible (ex. 30 min, 2h ± tolérance)
- Favoriser les rues agréables plutôt que les axes rapides
- Éviter la répétition des segments
- Encourager la **découverte** et la diversité des parcours

---

## 🧠 Philosophie algorithmique

### Hypothèses clés

1. **Optimalité locale**  
   Dans l’espace des chemins urbains, il existe une grande quantité de chemins **localement optimaux** très proches les uns des autres.  
   → Un chemin aléatoire bien raffiné est souvent quasi-optimal.

2. **La nouveauté est une valeur**  
   L’utilisateur ne cherche pas *le* meilleur chemin absolu, mais un chemin **différent** de ceux déjà parcourus.

3. **Cas d’usage principal**  
   Un utilisateur (souvent touriste) dispose d’un temps limité, connaît mal la ville, et souhaite voir les points importants tout en profitant d’une promenade agréable.

---

## 🗺️ Modélisation du problème

### Graphe urbain

- La ville est représentée comme un **graphe simple** (NetworkX) :
  - **Nœuds** : intersections
  - **Arêtes (segments)** : portions de rues

## 🧠 Architecture algorithmique

Le système repose sur **deux algorithmes principaux** :

### 🔹 Algorithme 1 — Sélection des points intéressants

Objectif : réduire l’espace de recherche pour permettre un calcul temps réel.

### 🔹 Algorithme 2 — Génération et optimisation du chemin

Approche :
- Génération d’un **chemin initial** passant par les segments importants
- Optimisation par **algorithme évolutif** avec opérations atomiques
- Contrainte de temps gérée dynamiquement via un poids adaptatif

## 🧭 Perspectives

- Intégration du feedback utilisateur
- Ajustement périodique des scores
- Interface interactive (carte + pop-ups culturels)
- Extension à d’autres villes

---

## 📝 Licence & statut

Projet académique / expérimental  
Statut : **en cours de développement**