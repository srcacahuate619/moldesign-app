"""Inspect RCSB API response structure for one PDB."""
import json, requests

pdb = "1HSG"
r = requests.get(f"https://data.rcsb.org/rest/v1/core/entry/{pdb}", timeout=10)
data = r.json()

print("Top-level keys:", sorted(data.keys()))
print()

# struct
if "struct" in data:
    print("struct title:", data["struct"].get("title"))

# rcsb_entry_info
if "rcsb_entry_info" in data:
    info = data["rcsb_entry_info"]
    for k in sorted(info.keys()):
        if "class" in k.lower() or "keyword" in k.lower() or "name" in k.lower():
            print(f"  {k}: {json.dumps(info[k], indent=2)[:200]}")

# polymer_entities
if "polymer_entities" in data:
    pe_list = data["polymer_entities"]
    print(f"polymer_entities count: {len(pe_list)}")
    if pe_list:
        pe0 = pe_list[0]
        print(f"Entity[0] keys: {sorted(pe0.keys())}")
        if "rcsb_uniprot_annotation" in pe0:
            ua = pe0["rcsb_uniprot_annotation"]
            print(f"rcsb_uniprot_annotation count: {len(ua)}")
            if ua:
                u0 = ua[0]
                print(f"  name: {u0.get('name')}")
                print(f"  ec: {u0.get('ec')}")
                print(f"  lineage: {json.dumps(u0.get('lineage', [])[:5], indent=2)[:500]}")
                keywords = u0.get("keywords", [])
                print(f"  keywords count: {len(keywords)}")
                if keywords:
                    print(f"  first keyword: {keywords[0]}")
                go_func = u0.get("goFunction", [])
                print(f"  goFunction: {json.dumps(go_func[:3], indent=2)[:300]}")
        if "rcsb_entity_source_organism" in pe0:
            src = pe0["rcsb_entity_source_organism"]
            print(f"source_organism: {json.dumps(src[:2], indent=2)[:300]}")
