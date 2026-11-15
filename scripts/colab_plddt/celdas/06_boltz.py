# ── Boltz: una corrida por caso y formato. Las terminadas no se repiten; las fallidas se apartan, no se borran ──
PENDIENTES_BOLTZ = pendientes()["boltz"]
if not PENDIENTES_BOLTZ:
    print("Boltz: todas las corridas están hechas; no se repite ninguna.")
else:
    BOLTZ = str(VENVS / "boltz" / "bin" / "boltz")
    AYUDA_BOLTZ = sh([BOLTZ, "predict", "--help"], check=True)[0].stdout
    (RES / "boltz").mkdir(exist_ok=True)
    corridas = cargar_procedencia().get("corridas_boltz", {})
    anteriores = cargar_procedencia().get("corridas_boltz_anteriores", [])
    for caso in CASOS:
        for formato in FORMATOS_BOLTZ[caso["id"]]:
            clave = f"{caso['id']}__{formato}"
            if clave not in PENDIENTES_BOLTZ:
                print("ya hecha:", clave)
                continue
            destino = RES / "boltz" / clave
            if destino.exists():  # su boltz.log va dentro y se aparta con ella
                apartada = apartar(destino)
                anteriores.append({"clave": clave, "apartada_como": apartada.name, **corridas.get(clave, {})})
            orden = [BOLTZ, "predict", str(ENT / f"{caso['id']}.yaml"), "--out_dir", str(destino),
                     "--cache", str(CACHE / "boltz"), "--output_format", formato, "--diffusion_samples", "1",
                     "--recycling_steps", "3", "--sampling_steps", "200", "--accelerator", "gpu", "--devices", "1"]
            pedidas = [("--seed", str(SEMILLA)), ("--write_full_pae", None), ("--override", None)]
            if USAR_SERVIDOR_MSA:
                pedidas.append(("--use_msa_server", None))
            if CAPACIDAD < 8.0:
                pedidas.append(("--no_kernels", None))
            no_aceptadas = []
            for bandera, valor in pedidas:
                if bandera in AYUDA_BOLTZ:
                    orden += [bandera] + ([valor] if valor is not None else [])
                else:
                    no_aceptadas.append(bandera)
            if USAR_SERVIDOR_MSA and "--use_msa_server" in no_aceptadas:
                raise RuntimeError("Esta versión de Boltz no acepta --use_msa_server: no se corre sin decirlo.")
            destino.mkdir(parents=True)
            r, s = sh(orden, log=destino / "boltz.log")
            corridas[clave] = {"orden": orden, "banderas_no_aceptadas": no_aceptadas, "codigo": r.returncode,
                               "segundos": s, "fin": ahora()}
            print(f"{clave}: código {r.returncode} en {s} s" + (f" (sin {no_aceptadas})" if no_aceptadas else ""))
            if r.returncode != 0:
                print("".join(open(destino / "boltz.log", encoding="utf-8", errors="replace").readlines()[-25:]))
            guardar_procedencia(corridas_boltz=corridas, corridas_boltz_anteriores=anteriores)
            respaldar()
