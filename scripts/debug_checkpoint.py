import json
ckpt = json.load(open("D:/moldesign-build/data/gnn_fixed/benchmark_checkpoint_5ht1a.json"))
r = ckpt["results"][0]
pq = r.get("pose_pdbqt", "")
print(f"Keys: {list(r.keys())}")
print(f"pose_pdbqt type: {type(pq).__name__}")
print(f"pose_pdbqt length: {len(str(pq))}")
print(f"First 300 chars:")
print(str(pq)[:300])
print()
r2 = ckpt["results"][100]
pq2 = r2.get("pose_pdbqt", "")
print(f"Result[100] pose_pdbqt first 200:")
print(str(pq2)[:200])
print()
print(f"Result[0] prob: {r.get('prob')}")
print(f"Result[0] gnn_prob: {r.get('gnn_prob')}")
print(f"Result[0] vina_score: {r.get('vina_score')}")
