import json
with open("D:/moldesign-build/data/gnn_fixed/benchmark_checkpoint_5ht1a.json") as f:
    ckpt = json.load(f)
print("Top-level keys:", list(ckpt.keys()))
for k, v in ckpt.items():
    if isinstance(v, dict):
        print(f"  {k}: dict with {len(v)} keys: {list(v.keys())[:6]}")
        if "pdbqt_block" in v:
            print(f"    has pdbqt_block: {len(v['pdbqt_block'])} chars")
    elif isinstance(v, list):
        print(f"  {k}: list[{len(v)}]")
        if v and isinstance(v[0], dict):
            print(f"    first item keys: {list(v[0].keys())}")
            if "pdbqt_block" in v[0]:
                size = len(v[0].get("pdbqt_block", ""))
                print(f"    pdbqt_block size: {size} chars")
            if "pdbqt_path" in v[0]:
                print(f"    pdbqt_path: {v[0]['pdbqt_path']}")
    else:
        print(f"  {k}: {str(v)[:80]}")
