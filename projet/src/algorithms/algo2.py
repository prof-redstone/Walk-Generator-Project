import networkx as nx
import numpy as np
import random
import pickle
import os
import folium
from pyproj import Transformer
from typing import List, Tuple
from pathlib import Path


class Config:
    """Configuration des hyperparametres"""
    
    USER_PREFS = [1.0, 0.0, 0.5, 0.2, 0.0, 0.0]
    
    MAX_WALK_DISTANCE = 3000
    DISTANCE_PENALTY_FACTOR = 100.0
    
    SKELETON_TOP_K = 20
    SKELETON_MIN_NODE_SCORE = 0.01
    
    ITERATIONS = 1000
    INITIAL_PRESSURE = 0.0001
    FINAL_PRESSURE = 0.5
    
    SHORTCUT_MIN_PATH_LENGTH = 5
    SHORTCUT_POISSON_LAMBDA = 20
    SHORTCUT_MAX_DISTANCE = 300  # Distance maximale pour un shortcut (en mètres)
    
    PARALLEL_SCAN_SAMPLE_SIZE = 40
    PARALLEL_MIN_SCORE = 0.0
    
    ASTAR_SCORE_WEIGHT = 5.0
    DEFAULT_EDGE_LENGTH = 10.0
    
    SHORTCUT_BASE_PROB = 0.4
    SHORTCUT_FINAL_PROB = 0.9
    
    MIN_DISTANCE_START_END = 500
    MAX_DISTANCE_START_END = 2000


class WalkGenerator:
    """Generateur de promenades optimisees."""
    
    def __init__(self, graph_path: str, user_preferences: np.ndarray = None):
        # Charger le graphe (MultiDiGraph)
        with open(graph_path, 'rb') as f:
            data = pickle.load(f)
            self.G = data[0] if isinstance(data, tuple) else data
            self.metadata = data[1] if isinstance(data, tuple) and len(data) > 1 else None
        
        print(f"[INFO] Graphe chargé: type={type(self.G).__name__}")
        
        self.user_prefs = np.array(user_preferences) if user_preferences is not None else np.array(Config.USER_PREFS)
        self.prefiltered_poi_nodes = set()

    def load_prefiltered_pois(self, filtered_pois_path: str):
        """Charge les POIs prefiltres depuis l'algo 1."""
        print(f"[LOAD] Chargement POIs prefiltres: {filtered_pois_path}")
        
        with open(filtered_pois_path, 'rb') as f:
            data = pickle.load(f)
        
        print(f"[INFO] {data['count']} POIs prefiltres")
        
        transformer = Transformer.from_crs("EPSG:4326", "EPSG:32631", always_xy=True)
        
        for poi in data['pois']:
            poi_lat = poi.geometry.y
            poi_lon = poi.geometry.x
            poi_x, poi_y = transformer.transform(poi_lon, poi_lat)
            
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

    def get_edge_score(self, u, v, key=0) -> float:
        """Calcule l'interet d'une arete (gestion MultiDiGraph)."""
        if not self.G.has_edge(u, v):
            return 0.0
        
        # Prendre la meilleure arête si plusieurs existent
        best_score = 0.0
        
        if isinstance(self.G, nx.MultiDiGraph):
            for k in self.G[u][v]:
                data = self.G[u][v][k]
                score_vector = data.get('score_vector', np.zeros(6))
                base_interest = np.dot(score_vector, self.user_prefs)
                total_score = base_interest + data.get('gratification', 0.0)
                best_score = max(best_score, total_score)
        else:
            data = self.G[u][v]
            score_vector = data.get('score_vector', np.zeros(6))
            base_interest = np.dot(score_vector, self.user_prefs)
            best_score = base_interest + data.get('gratification', 0.0)
        
        return max(0.0, best_score)

    def get_edge_length(self, u, v, key=0) -> float:
        """Récupère la longueur d'une arête (gestion MultiDiGraph)."""
        if not self.G.has_edge(u, v):
            return Config.DEFAULT_EDGE_LENGTH
        
        # Prendre l'arête la plus courte si plusieurs existent
        if isinstance(self.G, nx.MultiDiGraph):
            min_length = float('inf')
            for k in self.G[u][v]:
                length = self.G[u][v][k].get('length', Config.DEFAULT_EDGE_LENGTH)
                min_length = min(min_length, length)
            return min_length
        else:
            return self.G[u][v].get('length', Config.DEFAULT_EDGE_LENGTH)

    def evaluate_path(self, edge_path: List[Tuple[str, str]], length_penalty_factor: float) -> Tuple[float, float, float]:
        """Fitness = Total_Score - (Pression * longueur totale) - Penalite si depassement"""
        total_score = 0.0
        total_length = 0.0
        
        for u, v in edge_path:
            if self.G.has_edge(u, v):
                total_length += self.get_edge_length(u, v)
                total_score += self.get_edge_score(u, v)

        distance_penalty = 0.0
        if total_length > Config.MAX_WALK_DISTANCE:
            overshoot = total_length - Config.MAX_WALK_DISTANCE
            distance_penalty = overshoot * Config.DISTANCE_PENALTY_FACTOR

        fitness = total_score - (length_penalty_factor * total_length) - distance_penalty
        return fitness, total_score, total_length

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
        
        # Calculer le score en cherchant la meilleure clé
        score = 0.0
        if isinstance(self.G, nx.MultiDiGraph):
            # 'd' contient les données d'UNE arête spécifique
            score_vector = d.get('score_vector', np.zeros(6))
            base_interest = np.dot(score_vector, self.user_prefs)
            score = base_interest + d.get('gratification', 0.0)
        else:
            score_vector = d.get('score_vector', np.zeros(6))
            base_interest = np.dot(score_vector, self.user_prefs)
            score = base_interest + d.get('gratification', 0.0)
        
        return length / (1.0 + max(0.0, score) * Config.ASTAR_SCORE_WEIGHT)

    def _dist_heuristic(self, u, v):
        """Distance a vol d'oiseau."""
        n1 = self.G.nodes[u]
        n2 = self.G.nodes[v]
        return np.sqrt((n1['x'] - n2['x'])**2 + (n1['y'] - n2['y'])**2)

    def _shortest_edge_path(self, start_node, end_node, weight='length'):
        """Trouve le plus court chemin en edges entre deux noeuds."""
        try:
            node_path = nx.shortest_path(self.G, start_node, end_node, weight=weight)
            
            edge_path = []
            for i in range(len(node_path) - 1):
                u, v = node_path[i], node_path[i + 1]
                
                if self.G.has_edge(u, v):
                    edge_path.append((u, v))
                else:
                    print(f"[WARN] Edge manquante {u}->{v}")
                    return []
            
            return edge_path
            
        except nx.NetworkXNoPath:
            return []

    def _astar_edge_path(self, start_node, end_node):
        """Version A* qui retourne un edge path."""
        try:
            node_path = nx.astar_path(
                self.G, 
                start_node, 
                end_node, 
                heuristic=self._dist_heuristic, 
                weight=self._weighted_cost
            )
            
            edge_path = []
            for i in range(len(node_path) - 1):
                u, v = node_path[i], node_path[i + 1]
                if self.G.has_edge(u, v):
                    edge_path.append((u, v))
                else:
                    print(f"[WARN] Edge manquante {u}->{v} dans A*")
                    return []
            
            return edge_path
            
        except nx.NetworkXNoPath:
            return []

    def _merge_edge_paths(self, path1: List[Tuple[str, str]], path2: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """Fusionne deux edge paths en gerant les connexions."""
        if not path1:
            return path2
        if not path2:
            return path1
        
        last_node_path1 = path1[-1][1]
        first_node_path2 = path2[0][0]
        
        if last_node_path1 == first_node_path2:
            return path1 + path2
        else:
            bridge = self._shortest_edge_path(last_node_path1, first_node_path2)
            if bridge:
                return path1 + bridge + path2
            else:
                print(f"[WARN] Impossible de connecter les chemins")
                return path1

    def diagnose_edge_path(self, edge_path: List[Tuple[str, str]]) -> bool:
        """Verifie la continuite d'un chemin d'edges."""
        if not edge_path:
            return False
        
        breaks = 0
        missing_edges = 0
        
        for i in range(len(edge_path)):
            u, v = edge_path[i]
            
            if not self.G.has_edge(u, v):
                missing_edges += 1
            
            if i < len(edge_path) - 1:
                next_edge = edge_path[i + 1]
                if v != next_edge[0]:
                    breaks += 1
        
        is_valid = (breaks == 0 and missing_edges == 0)
        
        if not is_valid:
            print(f"[WARN] Chemin invalide: {missing_edges} edges manquantes, {breaks} ruptures")
        
        return is_valid

    def _generate_high_interest_skeleton(self, start_node, end_node, top_k=None, min_node_score=None):
        """Genere un chemin initial passant par les top_k noeuds les plus interessants."""
        if top_k is None:
            top_k = Config.SKELETON_TOP_K
        if min_node_score is None:
            min_node_score = Config.SKELETON_MIN_NODE_SCORE
            
        print("[INIT] Construction du Squelette")
        
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
        
        if start_node not in top_nodes: 
            top_nodes.insert(0, start_node)
        if end_node not in top_nodes: 
            top_nodes.append(end_node)
        
        unique_nodes = []
        seen = set()
        for node in top_nodes:
            if node not in seen:
                unique_nodes.append(node)
                seen.add(node)
        top_nodes = unique_nodes

        print(f"   [TARGET] {len(top_nodes)} Points d'interet identifies")

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

        print(f"   [BUILD] Connexion des {len(ordered_path)} POIs...")
        
        full_edge_path = []
        
        for i in range(len(ordered_path) - 1):
            u = ordered_path[i]
            v = ordered_path[i + 1]
            
            if u == v:
                continue
            
            segment_edges = self._shortest_edge_path(u, v)
            
            if not segment_edges:
                print(f"   [WARN] Pas de chemin entre {u} et {v}")
                continue
            
            full_edge_path = self._merge_edge_paths(full_edge_path, segment_edges)
        
        print(f"   [OK] Squelette: {len(full_edge_path)} edges")
        
        return full_edge_path

    def op_shortcut(self, edge_path: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """Operation Shortcut : raccourcit le chemin (AVEC CONTRAINTE DE DISTANCE)."""
        if len(edge_path) < Config.SHORTCUT_MIN_PATH_LENGTH: 
            return edge_path
        
        idx_x = random.randint(0, len(edge_path) - 4)
        jump = np.random.poisson(lam=Config.SHORTCUT_POISSON_LAMBDA) 
        idx_y = min(idx_x + max(3, jump), len(edge_path) - 1)
        
        start_node = edge_path[idx_x][0]
        end_node = edge_path[idx_y][1]
        
        # CONTRAINTE : interdire les shortcuts trop longs
        dist = self._dist_heuristic(start_node, end_node)
        if dist > Config.SHORTCUT_MAX_DISTANCE:
            return edge_path
        
        new_segment_edges = self._astar_edge_path(start_node, end_node)
        
        if not new_segment_edges:
            return edge_path
        
        before = edge_path[:idx_x]
        after = edge_path[idx_y + 1:] if idx_y + 1 < len(edge_path) else []
        
        return before + new_segment_edges + after

    def op_parallel(self, edge_path: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """Operation Parallel : explore une rue parallele."""
        if not edge_path:
            return edge_path
        
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
                        candidates.append((score, node, neighbor, idx))
        
        if not candidates: 
            return edge_path
        
        candidates.sort(key=lambda x: x[0], reverse=True)
        _, n1, n2, idx_in_path = candidates[0]
        
        departure_edge_idx = max(0, idx_in_path - 1)
        arrival_node_idx = min(idx_in_path + 5, len(node_path) - 1)
        arrival_edge_idx = min(arrival_node_idx, len(edge_path) - 1)
        
        departure_node = edge_path[departure_edge_idx][0]
        arrival_node = edge_path[arrival_edge_idx][1]
        
        try:
            seg_to_n1 = self._shortest_edge_path(departure_node, n1)
            seg_n1_to_n2 = [(n1, n2)] if self.G.has_edge(n1, n2) else self._shortest_edge_path(n1, n2)
            seg_from_n2 = self._shortest_edge_path(n2, arrival_node)
            
            if seg_to_n1 and seg_n1_to_n2 and seg_from_n2:
                before = edge_path[:departure_edge_idx]
                detour = self._merge_edge_paths(seg_to_n1, seg_n1_to_n2)
                detour = self._merge_edge_paths(detour, seg_from_n2)
                after = edge_path[arrival_edge_idx + 1:]
                
                return before + detour + after
        
        except Exception as e:
            print(f"[WARN] Erreur dans op_parallel: {e}")
        
        return edge_path

    def run(self, start_node, end_node,iterations=None,initial_pressure=None,final_pressure=None,max_distance=None,skeleton_output_html=None):
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
            print("[ERROR] Echec squelette, fallback sur shortest path")
            try:
                current_path = self._shortest_edge_path(start_node, end_node)
            except:
                return []

        # Sauvegarder le squelette initial si demandé
        if skeleton_output_html:
            print(f"[SKELETON] Génération de la carte du squelette initial...")
            save_path_to_html(self.G, current_path, skeleton_output_html)

        current_pressure = initial_pressure
        _, c_score, c_len = self.evaluate_path(current_path, current_pressure)

        print(f"[START] Edges: {len(current_path)} | Len: {c_len:.0f}m | Score: {c_score:.1f}")

        step = (final_pressure - initial_pressure) / iterations
        prob_increase = (Config.SHORTCUT_FINAL_PROB - Config.SHORTCUT_BASE_PROB) / iterations

        for i in range(iterations):
            current_pressure += step
            prob_shortcut = Config.SHORTCUT_BASE_PROB + prob_increase * i


            cand_path = list(current_path)

            if c_len > Config.MAX_WALK_DISTANCE:
                # MODE COMPRESSION FORCÉE
                if random.random() < 0.8:
                    cand_path = self.op_shortcut(cand_path)
                    op = "ShortCut*"
                else:
                    cand_path = self.op_parallel(cand_path)
                    op = "Parallel*"
            else:
                # MODE EXPLORATION NORMALE
                if random.random() < prob_shortcut:
                    cand_path = self.op_shortcut(cand_path)
                    op = "ShortCut"
                else:
                    cand_path = self.op_parallel(cand_path)
                    op = "Parallel"

            cand_fitness, cand_score, cand_len = self.evaluate_path(cand_path, current_pressure)
            curr_fitness, _, _ = self.evaluate_path(current_path, current_pressure)

            accepted = False

            if c_len > Config.MAX_WALK_DISTANCE:
                # Tant qu'on est hors contrainte :
                # priorité ABSOLUE à la réduction de longueur
                if cand_len < c_len:
                    accepted = True
            else:
                # Une fois faisable :
                # optimisation classique
                if cand_fitness > curr_fitness:
                    accepted = True

            if accepted:
                diff_len = cand_len - c_len
                current_path = cand_path
                c_len = cand_len
                c_score = cand_score

                print(
                    f"   [OK] [{i:03d}] {op:10s} | "
                    f"Edges: {len(cand_path)} | "
                    f"Len: {cand_len:.0f}m ({diff_len:+.0f}) | "
                    f"Score: {cand_score:.1f}"
                )

        if not self.diagnose_edge_path(current_path):
            print("[WARN] Le chemin final contient des discontinuités")

        return current_path


def save_path_to_html(G, edge_path, filepath):
    """Genere une carte HTML avec la geometrie reelle des rues."""
    graph_crs = G.graph.get('crs', "EPSG:32631") 
    transformer = Transformer.from_crs(graph_crs, "EPSG:4326", always_xy=True)

    def get_latlon(node_id):
        node = G.nodes[node_id]
        lon, lat = transformer.transform(node['x'], node['y'])
        return lat, lon
    
    def get_edge_geometry(u, v):
        """Recupere la geometrie reelle d'une arete (MultiDiGraph compatible)."""
        if not G.has_edge(u, v):
            return [get_latlon(u), get_latlon(v)]
        
        # Gestion MultiDiGraph : prendre la première arête
        if isinstance(G, nx.MultiDiGraph):
            keys = list(G[u][v].keys())
            edge_data = G[u][v][keys[0]]
        else:
            edge_data = G[u][v]
        
        if 'geometry' in edge_data:
            coords = []
            geom = edge_data['geometry']
            for x, y in geom.coords:
                lon, lat = transformer.transform(x, y)
                coords.append((lat, lon))
            return coords
        else:
            return [get_latlon(u), get_latlon(v)]

    route_coords = []
    
    for i, (u, v) in enumerate(edge_path):
        edge_coords = get_edge_geometry(u, v)
        
        if not route_coords:
            route_coords.extend(edge_coords)
        else:
            if len(edge_coords) > 0:
                if len(route_coords) > 0 and route_coords[-1] == edge_coords[0]:
                    route_coords.extend(edge_coords[1:])
                else:
                    route_coords.extend(edge_coords)

    if not route_coords:
        print("[ERROR] Chemin vide")
        return

    start_lat, start_lon = route_coords[0]
    m = folium.Map(location=[start_lat, start_lon], zoom_start=14, tiles='OpenStreetMap')
    
    folium.PolyLine(route_coords, color="blue", weight=5, opacity=0.7, tooltip="Promenade").add_to(m)
    folium.Marker(route_coords[0], popup="Depart", icon=folium.Icon(color="green", icon="play")).add_to(m)
    folium.Marker(route_coords[-1], popup="Arrivee", icon=folium.Icon(color="red", icon="stop")).add_to(m)
    
    m.save(filepath)
    print(f"[OK] Carte sauvegardee: {filepath}")


if __name__ == "__main__":
    # Chemins des fichiers
    GRAPH_PATH = "../../data/processed/graph.pkl"
    FILTERED_POIS_PATH = "../../data/processed/filtered_pois_for_algo2.pkl"
    OUTPUT_HTML = "../../data/results/promenade_generee.html"
    SKELETON_HTML = "../../data/results/squelette_initial.html"
    
    # Paramètres de test
    MAX_WALK_VAL = 3000
    
    print("[INIT] Algo 2 - Walk Generator")
    
    try:
        generator = WalkGenerator(GRAPH_PATH)
        
        # Chargement optionnel des POIs préfiltrés
        if os.path.exists(FILTERED_POIS_PATH):
            generator.load_prefiltered_pois(FILTERED_POIS_PATH)
        else:
            print("[INFO] Pas de POIs prefiltres, mode classique")
        
        # --- SÉLECTION START / END NORMALE ---
        
        # 1. Récupérer tous les noeuds valides (avec coordonnées x, y)
        valid_nodes = [n for n, d in generator.G.nodes(data=True) if 'x' in d and 'y' in d]
        
        if not valid_nodes:
            raise ValueError("Le graphe ne contient aucun noeud avec des coordonnées 'x' et 'y'.")

        # 2. Choisir un point de départ au hasard
        start_node = random.choice(valid_nodes)
        s_data = generator.G.nodes[start_node]
        
        # 3. Choisir un point d'arrivée qui respecte une distance min/max (vol d'oiseau)
        possible_ends = []
        
        print(f"[SEARCH] Recherche d'une destination entre {Config.MIN_DISTANCE_START_END}m et {Config.MAX_DISTANCE_START_END}m...")

        for node in valid_nodes:
            if node == start_node:
                continue
                
            n_data = generator.G.nodes[node]
            # Distance euclidienne
            dist = np.sqrt((s_data['x'] - n_data['x'])**2 + (s_data['y'] - n_data['y'])**2)
            
            if Config.MIN_DISTANCE_START_END <= dist <= Config.MAX_DISTANCE_START_END:
                possible_ends.append((node, dist))
        
        if possible_ends:
            end_node, dist_vol_oiseau = random.choice(possible_ends)
            print(f"[INFO] Trajet généré aléatoirement.")
            print(f"       Départ : {start_node}")
            print(f"       Arrivée: {end_node}")
            print(f"       Dist. vol d'oiseau: {dist_vol_oiseau:.0f}m")
        else:
            # Fallback si le graphe est trop petit ou trop dense
            print("[WARN] Aucune destination trouvée dans les contraintes, choix purement aléatoire.")
            end_node = random.choice([n for n in valid_nodes if n != start_node])
            dist_vol_oiseau = generator._dist_heuristic(start_node, end_node)
            print(f"       Arrivée (fallback): {end_node} ({dist_vol_oiseau:.0f}m)")

        # --- Lancement de l'algo ---

        final_edge_path = generator.run(
            start_node, 
            end_node, 
            max_distance=MAX_WALK_VAL, 
            skeleton_output_html=SKELETON_HTML
        )
        
        if final_edge_path:
            save_path_to_html(generator.G, final_edge_path, OUTPUT_HTML)
        else:
            print("[FAIL] Aucun chemin généré")
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()