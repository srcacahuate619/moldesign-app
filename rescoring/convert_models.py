
import json
from pathlib import Path

import joblib


def convert(name):
    joblib_path = Path(f"/app/artifacts/{name}.joblib")
    if not joblib_path.exists():
        print(f"File {joblib_path} not found")
        return

    print(f"Converting {name}...")
    data = joblib.load(joblib_path)
    
    # Save XGBoost JSON model
    booster = data["booster"]
    booster.save_model(f"/app/artifacts/{name}.json")
    
    # Save metadata
    metadata = {
        "feature_names": data["feature_names"],
        "metrics": data.get("metrics", {}),
        "train_samples": data.get("train_samples", 0),
        "train_timestamp": data.get("train_timestamp", "")
    }
    with open(f"/app/artifacts/{name}.metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    
    print(f"Done {name}")

if __name__ == "__main__":
    convert("model_a")
    convert("model_null")
