"""Inspect correct RCSB API fields for classification."""
import json, requests

pdb = "1HSG"
r = requests.get(f"https://data.rcsb.org/rest/v1/core/entry/{pdb}", timeout=10)
data = r.json()

print("struct_keywords:", json.dumps(data.get("struct_keywords", {}), indent=2))
print()

print("rcsb_entry_container_identifiers keys:", sorted(data.get("rcsb_entry_container_identifiers", {}).keys()))
print()
rcsb_id = data.get("rcsb_entry_container_identifiers", {})
if "uniprot_ids" in rcsb_id:
    print("uniprot_ids:", rcsb_id["uniprot_ids"])
print()

print("rcsb_entry_info relevant fields:")
info = data.get("rcsb_entry_info", {})
for k in sorted(info.keys()):
    if any(x in k.lower() for x in ["class", "keyword", "name", "entity"]):
        v = info[k]
        print(f"  {k}: {str(v)[:200]}")

# Now check rcsb_polymer_entity
# This is a DIFFERENT endpoint
print("\n--- Checking polymer entity endpoint ---")
r2 = requests.get(f"https://data.rcsb.org/rest/v1/core/polymer_entity/{pdb}/1", timeout=10)
if r2.status_code == 200:
    pe = r2.json()
    print("polymer_entity keys:", sorted(pe.keys()))
    for k in sorted(pe.keys()):
        if "classif" in k.lower() or "name" in k.lower() or "desc" in k.lower():
            print(f"  {k}: {str(pe[k])[:200]}")
else:
    print(f"polymer_entity returned {r2.status_code}")

# Try the annotation endpoint
print("\n--- Checking annotation endpoint ---")
r3 = requests.get(f"https://data.rcsb.org/rest/v1/core/entry/{pdb}/annotation", timeout=10)
if r3.status_code == 200:
    ann = r3.json()
    print(f"annotations count: {len(ann)}")
    if ann:
        a0 = ann[0]
        print(f"first annotation keys: {sorted(a0.keys())[:10]}")
        print(f"type: {a0.get('type')}")
        print(f"name: {a0.get('name')}")
else:
    print(f"annotation returned {r3.status_code}")

# Check for assembly endpoint
print("\n--- Checking UniProt endpoint ---")
uniprot_id = rcsb_id.get("uniprot_ids", [None])[0]
if uniprot_id:
    r4 = requests.get(f"https://rest.uniprot.org/uniprotkb/{uniprot_id}.json", timeout=10)
    if r4.status_code == 200:
        u_data = r4.json()
        print(f"UniProt ID: {uniprot_id}")
        print(f"proteinDescription: {u_data.get('proteinDescription', {}).get('recommendedName', {}).get('fullName', {}).get('value', 'N/A')}")
        genes = u_data.get("genes", [{}])
        if genes:
            print(f"gene: {genes[0].get('geneName', {}).get('value', 'N/A')}")
        keywords = [kw.get("name", "") for kw in u_data.get("keywords", [])]
        print(f"keywords ({len(keywords)}): {keywords[:15]}")
        # Check GO terms
        go_terms = []
        for ref in u_data.get("uniProtKBCrossReferences", []):
            if ref.get("database") == "GO":
                go_terms.append(ref.get("id"))
        print(f"GO terms ({len(go_terms)}): {go_terms[:10]}")
        # EC number
        ec = u_data.get("proteinDescription", {}).get("recommendedName", {}).get("ecNumbers", [])
        if ec:
            print(f"EC: {[e.get('value') for e in ec]}")
    else:
        print(f"UniProt returned {r4.status_code}")
