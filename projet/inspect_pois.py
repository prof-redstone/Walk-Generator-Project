import pickle
import os
if os.path.exists('data/processed/pois.pkl'):
    with open('data/processed/pois.pkl', 'rb') as f:
        pois = pickle.load(f)
    print('Type:', type(pois))
    print('Shape:', pois.shape)
    print('Columns:', pois.columns.tolist())
    print('CRS:', pois.crs)
    print('First 3 rows:')
    for idx, row in pois.head(3).iterrows():
        print(f'  {idx}: name={repr(row["name"])}, categories={row["categories"]}, nearest_edge={row["nearest_edge"]}, geometry={str(row["geometry"])[:50]}...')
else:
    print('File not found')