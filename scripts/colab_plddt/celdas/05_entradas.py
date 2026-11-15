# ── Entradas: YAML de Boltz y FASTA de Chai-1 ──
ENT = RES / "entradas"
ENT.mkdir(exist_ok=True)
secuencias = cargar_procedencia()["secuencias"]
entradas = {}
for caso in CASOS:
    seq = secuencias[caso["uniprot"]]["secuencia"]
    proteina = {"id": "A", "sequence": seq}
    if not USAR_SERVIDOR_MSA:
        proteina["msa"] = "empty"  # una sola secuencia, sin alineamiento
    cadenas = [{"protein": proteina}]
    if caso["ligando"]:
        cadenas.append({"ligand": {"id": "B", "smiles": caso["ligando"]["smiles"]}})
    yaml_ruta = ENT / f"{caso['id']}.yaml"  # JSON es YAML válido: sin dependencias ni problemas de comillas
    yaml_ruta.write_text(json.dumps({"version": 1, "sequences": cadenas}, indent=2), encoding="utf-8")
    fasta = f">protein|name={caso['id']}_A\n{seq}\n"
    if caso["ligando"]:
        fasta += f">ligand|name={caso['id']}_B\n{caso['ligando']['smiles']}\n"
    fasta_ruta = ENT / f"{caso['id']}.fasta"
    fasta_ruta.write_text(fasta, encoding="utf-8")
    entradas[caso["id"]] = {
        "boltz": yaml_ruta.name, "sha256_boltz": hashlib.sha256(yaml_ruta.read_bytes()).hexdigest(),
        "chai": fasta_ruta.name, "sha256_chai": hashlib.sha256(fasta_ruta.read_bytes()).hexdigest(),
    }
guardar_procedencia(entradas=entradas)
respaldar()
print(json.dumps(entradas, indent=1))
