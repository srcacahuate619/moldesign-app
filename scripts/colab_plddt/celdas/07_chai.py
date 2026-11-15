# ── Chai-1: una corrida por caso, con ejecutar_chai.py dentro de su propio entorno ──
PENDIENTES_CHAI = pendientes()["chai"]
if not PENDIENTES_CHAI:
    print("Chai-1: todas las corridas están hechas; no se repite ninguna.")
elif CHAI_LISTO is False:
    print("Chai-1 no se lanza: pandas no puede escribir parquet en su entorno. "
          "Los intentos están en procedencia.json → instalacion → chai → parquet.")
else:
    CHAI_PY = str(VENVS / "chai" / "bin" / "python")
    ENTORNO_CHAI = {**ENTORNO_LIMPIO, "CHAI_DOWNLOADS_DIR": str(CACHE / "chai")}
    (RES / "chai").mkdir(exist_ok=True)
    corridas = cargar_procedencia().get("corridas_chai", {})
    anteriores = cargar_procedencia().get("corridas_chai_anteriores", [])
    for caso in CASOS:
        clave = f"{caso['id']}__mmcif"
        if clave not in PENDIENTES_CHAI:
            print("ya hecha:", clave)
            continue
        destino = RES / "chai" / clave
        log = RES / "chai" / f"{clave}.log"  # fuera de destino: Chai-1 exige un directorio vacío
        if destino.exists() or log.exists():
            if destino.exists():
                apartada = apartar(destino)
            else:
                apartada = destino.with_name(f"{clave}__fallido_{sello()}")
                apartada.mkdir()
            if log.exists():
                log.rename(apartada / "chai.log")  # el registro de la corrida fallida viaja con ella
            anteriores.append({"clave": clave, "apartada_como": apartada.name, **corridas.get(clave, {})})
        orden = [CHAI_PY, str(RAIZ / "ejecutar_chai.py"), "--fasta", str(ENT / f"{caso['id']}.fasta"),
                 "--salida", str(destino), "--semilla", str(SEMILLA), "--msa-servidor", "1" if USAR_SERVIDOR_MSA else "0",
                 "--muestras", str(MUESTRAS_CHAI)]
        r, s = sh(orden, log=log, env=ENTORNO_CHAI)
        corridas[clave] = {"orden": orden, "codigo": r.returncode, "segundos": s, "fin": ahora()}
        print(f"{clave}: código {r.returncode} en {s} s")
        if r.returncode != 0:
            print("".join(open(log, encoding="utf-8", errors="replace").readlines()[-25:]))
        guardar_procedencia(corridas_chai=corridas, corridas_chai_anteriores=anteriores)
        respaldar()
