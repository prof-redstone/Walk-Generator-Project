import pickle
import os

if os.path.exists('projet/data/processed/pois.pkl'):
    with open('projet/data/processed/pois.pkl', 'rb') as f:
        pois = pickle.load(f)

    print('Type:', type(pois))
    print('Shape:', pois.shape)
    print('Columns:', pois.columns.tolist())
    print('CRS:', pois.crs)
    print('10 rows randomly selected:')

    # Tirage aléatoire de 10 lignes (ou moins si le DF est plus petit)
    sample_pois = pois.sample(n=min(10, len(pois)), random_state=None)

    for idx, row in sample_pois.iterrows():
        print(
            f'  {idx}: '
            f'name={repr(row["name"])}, '
            f'categories={row["categories"]}, '
            f'nearest_edge={row["nearest_edge"]}, '
            f'geometry={str(row["geometry"])[:50]}...'
        )
else:
    print('File not found')
