import pandas as pd

df = pd.read_parquet('/app/data/pdbbind/dataset_v4.parquet')
print(df[['logp', 'vina_best_score', 'tpsa', 'hbd', 'hba']].describe())
