import networkx as nx
import numpy as np
import random
import pickle
import os
import folium
from pyproj import Transformer
from typing import List, Tuple
from pathlib import Path

# HYPERPARAMÈTRES CONFIGURABLES
"""Notes :
CHANGEMENTS A FAIRE : 
1. encore pas mal de modifications à faire, l'utilisation de la zone générée par l'algo 1 pour limiter la zone de recherche, 
2. plutôt que de fixer soit meme la distance from center
IMPLIQUE DONC de changer l'algo 1, pour avoir une sortie qui est utilisable dans l'algo 2 (et non juste un html)
3. Simplifier la gestion des hyperaparamètres, mais on verra quand on utilisera l'output de l'algo1.
4.Optimiser le choix du squelette initial, que ce soit au niveau de la proximité des points d'intérêt, ou de comment on fait notre premier squelette.
5. et on optimise pour un path pour l'instant entre A et B, mais on ne fait pas de boucle entre A et A, même si c'est réalisable plus tard, n'oublions pas l'objectif final.

PRINCIPE :
- Part d'un squelette initial passant par les top_k nœuds les plus intéressants
- Optimise itérativement avec 2 opérations : Shortcut (raccourcit) et Parallel (explore rues adjacentes)
- Utilise une pression croissante : au début favorise l'intérêt, à la fin favorise la distance courte

ENTRÉE : 
- graph.pkl (Simple Graph avec dummy nodes)
- start_node, end_node
- Préférences utilisateur (à voir plus tard)

SORTIE :
- Edge path : liste de tuples (u, v) représentant les rues à emprunter
- Carte HTML interactive dans /results/

STRUCTURE DES DONNÉES :
- Node path : [node1, node2, node3] → Intersections
- Edge path : [(node1, node2), (node2, node3)] → Rues réelles (utilisé partout dans ce code)

"""

class Config:
    """Configuration centralisée de tous les hyperparamètres"""
    
    # --- Préférences utilisateur ---
    # [végétalisation, accessibilité, sécurité, culture, dénivelé, cyclabilité]
    USER_PREFS = [1.0, 0.0, 0.5, 0.2, 0.0, 0.0]
    
    # --- Contrainte de distance ---
    MAX_WALK_DISTANCE = 3000  # Distance maximale souhaitée en mètres 
    DISTANCE_PENALTY_FACTOR = 100.0  # Pénalité si dépassement
    
    # --- Génération du squelette initial ---
    SKELETON_TOP_K = 20                    # Nombre de points d'intérêt à cibler 
    SKELETON_MIN_NODE_SCORE = 0.01         # Score minimum pour qu'un nœud soit considéré
    
    # --- Optimisation (run) ---
    ITERATIONS = 80                     # Nombre d'itérations d'optimisation
    INITIAL_PRESSURE = 0.0001              # Pression initiale (favorise l'intérêt)
    FINAL_PRESSURE = 0.5                   # Pression finale (favorise la distance courte)
    
    # --- Opérations ---
    SHORTCUT_MIN_PATH_LENGTH = 5           # Longueur min du chemin pour shortcut
    SHORTCUT_POISSON_LAMBDA = 20           # Paramètre λ de la loi de Poisson pour le saut
    PARALLEL_SCAN_SAMPLE_SIZE = 40         # Nombre de nœuds à scanner pour parallèle
    PARALLEL_MIN_SCORE = 0.0               # Score minimum pour considérer une arête parallèle
    
    # --- Heuristique A* ---
    ASTAR_SCORE_WEIGHT = 5.0               # Poids du score dans le coût A*
    DEFAULT_EDGE_LENGTH = 10.0             # Longueur par défaut si absente
    
    # --- Probabilités dynamiques ---
    SHORTCUT_BASE_PROB = 0.4               # Probabilité de base pour shortcut
    SHORTCUT_FINAL_PROB = 0.9              # Probabilité finale (= base + augmentation)
    
    # --- Sélection des nœuds start/end ---
    MIN_DISTANCE_START_END = 500           # Distance minimale entre départ et arrivée (m)
    MAX_DISTANCE_START_END = 2000          # Distance maximale entre départ et arrivée (m)



class WalkGenerator:
    """Générateur de promenades optimisées."""
    
    def __init__(self, graph_path: str, user_preferences: np.ndarray = None):
        # Charger le graphe
        with open(graph_path, 'rb') as f:
            data = pickle.load(f)
            self.G = data[0] if isinstance(data, tuple) else data
            self.metadata = data[1] if isinstance(data, tuple) and len(data) > 1 else None
        
        self.user_prefs = np.array(user_preferences) if user_preferences is not None else np.array(Config.USER_PREFS)
        
        # POIs préfiltrés (chargés par algo1)
        self.prefiltered_poi_nodes = set()

    def load_prefiltered_pois(self, filtered_pois_path: str):
        """Charge les POIs préfiltrés depuis l'algo 1."""
        print(f"[LOAD] Chargement POIs prefiltres: {filtered_pois_path}")
        
        with open(filtered_pois_path, 'rb') as f:
            data = pickle.load(f)
        
        print(f"[INFO] {data['count']} POIs prefiltres")
        
        # Mapper POIs vers nodes du graphe
        transformer = Transformer.from_crs("EPSG:4326", "EPSG:32631", always_xy=True)
        
        for poi in data['pois']:
            poi_lat = poi.geometry.y
            poi_lon = poi.geometry.x
            poi_x, poi_y = transformer.transform(poi_lon, poi_lat)
            
            # Trouver le node le plus proche
            best_node = None
            min_dist = float('inf')
            
            for node, node_data in self.G.nodes(data=True):
                if 'x' not in node_data or 'y' not in node_data:
                    continue
                
                dist = np.sqrt((node_data['x'] - poi_x)**2 + (node_data['y'] - poi_y)**2)
                if dist < min_dist:
                    min_dist = dist
                    best_node = node
            
            if best_node and min_dist < 100:
                self.prefiltered_poi_nodes.add(best_node)
        
        print(f"[OK] {len(self.prefiltered_poi_nodes)} nodes associes")

    def get_edge_score(self, u, v) -> float:
        """Calcule l'intérêt d'une arête."""
        if not self.G.has_edge(u, v): 
            return 0.0
        
        data = self.G[u][v]
        score_vector = data.get('score_vector', np.zeros(6))
        base_interest = np.dot(score_vector, self.user_prefs)
        total_score = base_interest + data.get('gratification', 0.0)
        return max(0.0, total_score)

    def evaluate_path(self, edge_path: List[Tuple[str, str]], length_penalty_factor: float) -> Tuple[float, float, float]:
        """Fitness = Total_Score - (Pression * longueur totale) - Pénalité si dépassement"""
        total_score = 0.0
        total_length = 0.0
        
        for u, v in edge_path:
            if self.G.has_edge(u, v):
                data = self.G[u][v]
                l = data.get('length', 0)
                if isinstance(l, (int, float)):
                    total_length += l
                total_score += self.get_edge_score(u, v)

        # Pénalité si dépassement de la distance max
        distance_penalty = 0.0
        if total_length > Config.MAX_WALK_DISTANCE:
            overshoot = total_length - Config.MAX_WALK_DISTANCE
            distance_penalty = overshoot * Config.DISTANCE_PENALTY_FACTOR

        fitness = total_score - (length_penalty_factor * total_length) - distance_penalty
        return fitness, total_score, total_length

    def _node_path_to_edge_path(self, node_path: List[str]) -> List[Tuple[str, str]]:
        """Convertit un chemin de nodes en chemin d'edges."""
        edge_path = []
        for i in range(len(node_path) - 1):
            u = node_path[i]
            v = node_path[i + 1]
            if self.G.has_edge(u, v):
                edge_path.append((u, v))
        return edge_path

    def _edge_path_to_node_path(self, edge_path: List[Tuple[str, str]]) -> List[str]:
        """Convertit un chemin d'edges en chemin de nodes."""
        if not edge_path:
            return []
        node_path = [edge_path[0][0]]
        for u, v in edge_path:
            node_path.append(v)
        return node_path

    def _weighted_cost(self, u, v, d):
        """A* favorise les segments courts ET interessants."""
        length = d.get('length', Config.DEFAULT_EDGE_LENGTH)
        score = self.get_edge_score(u, v)
        return length / (1.0 + score * Config.ASTAR_SCORE_WEIGHT)

    def _dist_heuristic(self, u, v):
        """Distance a vol d'oiseau."""
        n1 = self.G.nodes[u]
        n2 = self.G.nodes[v]
        return np.sqrt((n1['x'] - n2['x'])**2 + (n1['y'] - n2['y'])**2)

    def _generate_high_interest_skeleton(self, start_node, end_node, top_k=None, min_node_score=None):
        """Génère un chemin initial passant par les top_k nœuds les plus intéressants."""
        if top_k is None:
            top_k = Config.SKELETON_TOP_K
        if min_node_score is None:
            min_node_score = Config.SKELETON_MIN_NODE_SCORE
            
        print("[INIT] Construction du Squelette")
        
        # Si POIs préfiltrés disponibles, les utiliser
        if self.prefiltered_poi_nodes:
            print(f"[MODE] Utilisation des POIs prefiltres")
            top_nodes = list(self.prefiltered_poi_nodes)[:top_k]
        else:
            print("[MODE] Mode classique - scan du graphe")
            s_data = self.G.nodes[start_node]
            e_data = self.G.nodes[end_node]
            center_x = (s_data['x'] + e_data['x']) / 2
            center_y = (s_data['y'] + e_data['y']) / 2
            max_dist = self._dist_heuristic(start_node, end_node) * 1.5
            
            candidates = []
            for n, data in self.G.nodes(data=True):
                if data.get('fictif', False):
                    continue
                if 'x' not in data or 'y' not in data: 
                    continue
                    
                dist = np.sqrt((data['x'] - center_x)**2 + (data['y'] - center_y)**2)
                
                if dist <= max_dist:
                    node_score = 0
                    for neighbor in self.G.neighbors(n):
                        s = self.get_edge_score(n, neighbor)
                        node_score = max(node_score, s)
                    
                    if node_score > min_node_score: 
                        candidates.append((n, node_score))
            
            candidates.sort(key=lambda x: x[1], reverse=True)
            top_nodes = [x[0] for x in candidates[:top_k]]
        
        # Ajouter start et end
        if start_node not in top_nodes: 
            top_nodes.insert(0, start_node)
        if end_node not in top_nodes: 
            top_nodes.append(end_node)
        
        # Dédupliquer
        unique_nodes = []
        seen = set()
        for node in top_nodes:
            if node not in seen:
                unique_nodes.append(node)
                seen.add(node)
        top_nodes = unique_nodes

        print(f"   [TARGET] {len(top_nodes)} Points d'interet identifies")

        # Ordonner (plus proche voisin)
        ordered_path = [start_node]
        unvisited = set(top_nodes)
        if start_node in unvisited: 
            unvisited.remove(start_node)
        if end_node in unvisited: 
            unvisited.remove(end_node)
        
        current_node = start_node
        
        while unvisited:
            best_next = None
            min_dist = float('inf')
            c_data = self.G.nodes[current_node]
            
            for cand in unvisited:
                d_data = self.G.nodes[cand]
                dist = (c_data['x'] - d_data['x'])**2 + (c_data['y'] - d_data['y'])**2
                if dist < min_dist:
                    min_dist = dist
                    best_next = cand
            
            if best_next:
                ordered_path.append(best_next)
                unvisited.remove(best_next)
                current_node = best_next
            else:
                break
        
        ordered_path.append(end_node)

        # Relier avec shortest_path
        full_node_path = []
        for i in range(len(ordered_path) - 1):
            u = ordered_path[i]
            v = ordered_path[i+1]
            try:
                if u == v: 
                    continue
                segment = nx.shortest_path(self.G, u, v, weight='length')
                if i > 0:
                    full_node_path.extend(segment[1:]) 
                else:
                    full_node_path.extend(segment)
            except nx.NetworkXNoPath:
                print(f"   [WARN] Pas de chemin entre {u} et {v}")
                continue

        return self._node_path_to_edge_path(full_node_path)

    def op_shortcut(self, edge_path: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """Opération Shortcut : raccourcit le chemin."""
        if len(edge_path) < Config.SHORTCUT_MIN_PATH_LENGTH: 
            return edge_path
        
        node_path = self._edge_path_to_node_path(edge_path)
        idx_x = random.randint(0, len(node_path) - 4)
        jump = np.random.poisson(lam=Config.SHORTCUT_POISSON_LAMBDA) 
        idx_y = min(idx_x + max(3, jump), len(node_path) - 1)
        
        try:
            new_segment_nodes = nx.astar_path(
                self.G, node_path[idx_x], node_path[idx_y], 
                heuristic=self._dist_heuristic, weight=self._weighted_cost
            )
            new_segment_edges = self._node_path_to_edge_path(new_segment_nodes)
            before = edge_path[:idx_x]
            after = edge_path[idx_y+1:] if idx_y+1 < len(edge_path) else []
            return before + new_segment_edges + after
        except nx.NetworkXNoPath:
            return edge_path

    def op_parallel(self, edge_path: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """Opération Parallel : explore une rue parallèle."""
        node_path = self._edge_path_to_node_path(edge_path)
        path_set = set(node_path)
        candidates = []
        scan_size = min(Config.PARALLEL_SCAN_SAMPLE_SIZE, len(node_path))
        scan_indices = random.sample(range(len(node_path)), scan_size)
        
        for idx in scan_indices:
            node = node_path[idx]
            for neighbor in self.G.neighbors(node):
                if neighbor not in path_set:
                    score = self.get_edge_score(node, neighbor)
                    if score > Config.PARALLEL_MIN_SCORE: 
                        candidates.append((score, node, neighbor))
        
        if not candidates: 
            return edge_path
            
        candidates.sort(key=lambda x: x[0], reverse=True)
        _, n1, n2 = candidates[0]
        
        def get_closest_idx(target_node):
            best_i, min_d = -1, float('inf')
            t_data = self.G.nodes[target_node]
            for i, p_node in enumerate(node_path):
                p_data = self.G.nodes[p_node]
                d = (t_data['x']-p_data['x'])**2 + (t_data['y']-p_data['y'])**2
                if d < min_d: 
                    min_d, best_i = d, i
            return best_i

        idx_n3 = get_closest_idx(n1)
        idx_n4 = get_closest_idx(n2)
        
        if idx_n3 >= idx_n4: 
            return edge_path
        
        try:
            seg_to_nodes = nx.shortest_path(self.G, node_path[idx_n3], n1, weight='length')
            seg_from_nodes = nx.shortest_path(self.G, n2, node_path[idx_n4], weight='length')
            seg_to_edges = self._node_path_to_edge_path(seg_to_nodes)
            seg_from_edges = self._node_path_to_edge_path(seg_from_nodes)
            parallel_edge = [(n1, n2)]
            return edge_path[:idx_n3] + seg_to_edges + parallel_edge + seg_from_edges + edge_path[idx_n4+1:]
        except nx.NetworkXNoPath:
            return edge_path

    def run(self, start_node, end_node, iterations=None, initial_pressure=None, final_pressure=None, max_distance=None):
        """Lance l'optimisation du parcours."""
        if iterations is None:
            iterations = Config.ITERATIONS
        if initial_pressure is None:
            initial_pressure = Config.INITIAL_PRESSURE
        if final_pressure is None:
            final_pressure = Config.FINAL_PRESSURE
        if max_distance is not None:
            Config.MAX_WALK_DISTANCE = max_distance
            
        current_path = self._generate_high_interest_skeleton(start_node, end_node)
        
        if not current_path or len(current_path) < 1:
            print("[ERROR] Echec squelette, shortest path")
            try:
                node_path = nx.shortest_path(self.G, start_node, end_node, weight='length')
                current_path = self._node_path_to_edge_path(node_path)
            except:
                return []

        current_pressure = initial_pressure
        _, c_score, c_len = self.evaluate_path(current_path, current_pressure)
        print(f"[START] Edges: {len(current_path)} | Len: {c_len:.0f}m | Score: {c_score:.1f}")

        step = (final_pressure - initial_pressure) / iterations
        prob_increase = (Config.SHORTCUT_FINAL_PROB - Config.SHORTCUT_BASE_PROB) / iterations

        for i in range(iterations):
            current_pressure += step
            prob_shortcut = Config.SHORTCUT_BASE_PROB + (prob_increase * i)
            
            cand_path = list(current_path)
            if random.random() < prob_shortcut:
                cand_path = self.op_shortcut(cand_path)
                op = "ShortCut"
            else:
                cand_path = self.op_parallel(cand_path)
                op = "Parallel"
            
            cand_fitness, cand_score, cand_len = self.evaluate_path(cand_path, current_pressure)
            updated_current_fitness, _, _ = self.evaluate_path(current_path, current_pressure)
            
            if cand_fitness > updated_current_fitness:
                diff_len = cand_len - c_len
                current_path = cand_path
                c_len = cand_len
                c_score = cand_score
                print(f"   [OK] [{i:03d}] {op:8s} | Edges: {len(cand_path)} | Len: {cand_len:.0f}m ({diff_len:+.0f}) | Score: {cand_score:.1f}")
        
        return current_path


def save_path_to_html(G, edge_path, filepath):
    """Génère une carte HTML du parcours."""
    print(f"[MAP] Generation carte HTML: {filepath}")
    
    graph_crs = G.graph.get('crs', "EPSG:32631") 
    transformer = Transformer.from_crs(graph_crs, "EPSG:4326", always_xy=True)

    def get_latlon(node_id):
        node = G.nodes[node_id]
        lon, lat = transformer.transform(node['x'], node['y'])
        return lat, lon

    route_coords = []
    for u, v in edge_path:
        if not route_coords:
            route_coords.append(get_latlon(u))
        route_coords.append(get_latlon(v))

    if not route_coords:
        print("[ERROR] Chemin vide")
        return

    start_lat, start_lon = route_coords[0]
    m = folium.Map(location=[start_lat, start_lon], zoom_start=14, tiles='OpenStreetMap')
    folium.PolyLine(route_coords, color="blue", weight=5, opacity=0.7, tooltip="Promenade").add_to(m)
    folium.Marker(route_coords[0], popup="Depart", icon=folium.Icon(color="green", icon="play")).add_to(m)
    folium.Marker(route_coords[-1], popup="Arrivee", icon=folium.Icon(color="red", icon="stop")).add_to(m)
    m.save(filepath)
    print(f"[OK] Carte sauvegardee")


if __name__ == "__main__":
    GRAPH_PATH = "../../data/processed/graph.pkl"
    FILTERED_POIS_PATH = "../../data/processed/filtered_pois_for_algo2.pkl"
    OUTPUT_HTML = "../../data/results/promenade_generee.html"
    
    MAX_DISTANCE = 3000  # Distance max souhaitée en mètres
    
    print(f"[INIT] Algo 3 - Walk Generator")
    
    try:
        generator = WalkGenerator(GRAPH_PATH)
        generator.load_prefiltered_pois(FILTERED_POIS_PATH)
        
        all_nodes = list(generator.G.nodes())
        start_node = random.choice(all_nodes)
        
        possible_ends = [n for n in all_nodes 
                        if Config.MIN_DISTANCE_START_END < generator._dist_heuristic(start_node, n) < Config.MAX_DISTANCE_START_END]
        end_node = random.choice(possible_ends) if possible_ends else random.choice(all_nodes)

        print(f"[INFO] Trajet: {start_node} -> {end_node}")

        final_edge_path = generator.run(start_node, end_node, max_distance=MAX_DISTANCE)
        
        if final_edge_path:
            save_path_to_html(generator.G, final_edge_path, OUTPUT_HTML)
        else:
            print("[FAIL] Aucun chemin genere")
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()