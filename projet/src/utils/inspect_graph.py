import pickle
import os
if os.path.exists('projet/data/processed/graph.pkl'):
    with open('projet/data/processed/graph.pkl', 'rb') as f:
        data = pickle.load(f)
    if isinstance(data, tuple):
        G, metadata = data
        print('Loaded as tuple: G and metadata')
        print('Metadata:', metadata)
    else:
        G = data
    print('Type of G:', type(G))
    print('Number of nodes:', G.number_of_nodes())
    print('Number of edges:', G.number_of_edges())
    print('Graph type:', G.graph.get('graph_type', 'unknown'))
    print('CRS:', G.graph.get('crs', 'unknown'))
    print('Score dimensions:', G.graph.get('score_dimensions', 'unknown'))
    print('First 5 nodes:')
    for i, (node, data) in enumerate(G.nodes(data=True)):
        if i >= 5: break
        print(f'  {node}: x={data.get("x")}, y={data.get("y")}, street_count={data.get("street_count")}')
    print('First 5 edges:')
    for i, (u, v, data) in enumerate(G.edges(data=True)):
        if i >= 5: break
        print(f'  ({u}, {v}): length={data.get("length")}, score_vector={data.get("score_vector")}')
else:
    print('File not found')