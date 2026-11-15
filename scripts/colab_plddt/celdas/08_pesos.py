# ── Huella de los pesos que se usaron (SHA-256 de cada archivo de 1 MB o más) ──
def huella_de_directorio(raiz, minimo=1 << 20):
    grandes, pequenos, total = {}, 0, 0
    for p in sorted(Path(raiz).rglob("*")):
        if not p.is_file():
            continue
        tam = p.stat().st_size
        total += tam
        if tam < minimo:
            pequenos += 1
            continue
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for bloque in iter(lambda: f.read(1 << 24), b""):
                h.update(bloque)
        grandes[str(p.relative_to(raiz))] = {"bytes": tam, "sha256": h.hexdigest()}
    return {"archivos_grandes": grandes, "archivos_pequenos_sin_hash": pequenos, "bytes_totales": total}


directorios = {"boltz": CACHE / "boltz", "chai": CACHE / "chai",
               "huggingface": Path.home() / ".cache" / "huggingface", "torch_hub": Path.home() / ".cache" / "torch"}
previa = cargar_procedencia()
pesos = dict(previa.get("pesos", {}))  # lo que esta ejecución no descargó conserva la huella de la que sí lo hizo
historial_pesos = list(previa.get("pesos_anteriores", []))
medidos_ahora = set()
for n, d in directorios.items():
    if not (d.exists() and any(p.is_file() for p in d.rglob("*"))):
        continue
    if n in pesos:
        historial_pesos.append({"directorio": n, "apartada": ahora(), **pesos[n]})
    pesos[n] = {**huella_de_directorio(d), "medido": ahora()}
    medidos_ahora.add(n)
for n, v in pesos.items():
    print(n, len(v["archivos_grandes"]), "archivos grandes,", round(v["bytes_totales"] / 1e9, 2), "GB",
          "(medido en esta ejecución)" if n in medidos_ahora else "(de una ejecución anterior)")
guardar_procedencia(pesos=pesos, pesos_anteriores=historial_pesos)
respaldar()
