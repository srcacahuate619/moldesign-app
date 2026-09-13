import pandas as pd

try:
    df = pd.read_parquet('/app/data/pdbbind/dataset_v4.parquet')
    cols = ['logp', 'vina_best_score', 'tpsa', 'hbd', 'hba']
    available_cols = [c for c in cols if c in df.columns]
    if available_cols:
        print(df[available_cols].describe())
    else:
        print("None of the columns exist in the parquet file!")
except Exception as e:
    print(f"Error: {e}")
