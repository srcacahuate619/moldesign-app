"""Exporta una escena desde los bytes persistidos, sin rehacer docking."""
from __future__ import annotations

import hashlib
import io
import json
import math
from pathlib import Path
from typing import Any

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pdbqt_a_pdb(data: bytes) -> tuple[bytes, list[dict[str, Any]], list[str], list[str]]:
    """Genera sólo una vista PDB de los mismos átomos y detecta cortes Cα.

    El elemento sale del **tipo AutoDock**, con el mismo decodificador que el resto
    del producto (`preparer_propio.elemento_de_tipo`), y distingue mayúsculas:
    ``NA`` es un nitrógeno aceptor y ``Na`` es sodio. SCI-A-028: antes había un
    mapa propio sin metales, y un tipo que no conocía caía a la primera letra del
    nombre del átomo, así que un ``Fe`` conservado se dibujaba como flúor. Un tipo
    que el decodificador no conoce no se inventa: la columna queda vacía y el tipo
    se devuelve para declararlo.
    """
    from services.docking.preparer_propio import elemento_de_tipo
    from services.targets.pdbqt_propio import _tipo

    lineas: list[str] = []
    ca: dict[str, list[tuple[int, tuple[float, float, float]]]] = {}
    cadenas: set[str] = set()
    sin_elemento: set[str] = set()
    for cruda in data.decode("utf-8").splitlines():
        if not cruda.startswith(("ATOM  ", "HETATM")):
            continue
        if len(cruda) < 54:
            raise ValueError("PDBQT truncado: faltan coordenadas")
        try:
            punto = tuple(float(cruda[i:i + 8]) for i in (30, 38, 46))
        except ValueError as exc:
            raise ValueError("PDBQT contiene coordenadas inválidas") from exc
        if not all(math.isfinite(v) for v in punto):
            raise ValueError("PDBQT contiene coordenadas no finitas")
        cadena = cruda[21:22] or " "
        cadenas.add(cadena)
        tipo = _tipo(cruda)
        elemento = elemento_de_tipo(tipo)
        if elemento is None:
            sin_elemento.add(tipo or "?")
            elemento = ""
        lineas.append(f"{cruda[:66]:<66}          {elemento:>2}  ")
        if cruda.startswith("ATOM  ") and cruda[12:16] == " CA ":
            try:
                ca.setdefault(cadena, []).append((int(cruda[22:26]), punto))
            except ValueError as exc:
                raise ValueError("PDBQT contiene numeración de residuo inválida") from exc
    if not lineas or not ca:
        raise ValueError("El receptor no conserva un esqueleto proteico dibujable")
    huecos = []
    for cadena, residuos in ca.items():
        for (a, p), (b, q) in zip(residuos, residuos[1:]):
            d = math.dist(p, q)
            if d > 4.5:
                huecos.append({"cadena": cadena, "entre_residuos": [a, b],
                               "distancia_ca_ca_a": round(d, 2),
                               "residuos_ausentes": max(0, b - a - 1)})
    return ("\n".join(lineas) + "\nEND\n").encode("utf-8"), huecos, sorted(cadenas), sorted(sin_elemento)


def primera_pose(sdf: bytes) -> tuple[bytes, bytes, int]:
    """Aísla la Vina top-1; la colección íntegra viaja con su hash."""
    from rdkit import Chem

    mol = next(iter(Chem.ForwardSDMolSupplier(io.BytesIO(sdf), removeHs=False)), None)
    if mol is None or mol.GetNumConformers() == 0:
        raise ValueError("El SDF no conserva una primera pose 3D válida")
    return ((Chem.MolToMolBlock(mol) + "\n$$$$\n").encode("utf-8"),
            Chem.MolToPDBBlock(mol).encode("utf-8"), mol.GetNumAtoms())


def _escribir_ensamble(destino: Path, ensamble: dict, archivos: dict[str, str],
                       escena: dict, fuente: dict, centro, tamano) -> None:
    """Escribe `ensamble.json` y los archivos que cita, verificando que lo citado es lo escrito.

    Un hash en el contrato que no es el de los bytes del archivo haría que el motor
    se abstuviera tarde y sin explicación: aquí se falla pronto y diciendo cuál.
    """
    contrato, adjuntos = ensamble["contrato"], ensamble["archivos"]
    if contrato.get("schema") != "moldesign.ensamble/1":
        raise ValueError("El contrato del ensamble no declara su esquema")
    if (list(contrato["caja"]["centro"]) != list(centro)
            or list(contrato["caja"]["tamano"]) != list(tamano)):
        raise ValueError("La caja del ensamble no es la de la escena")
    raiz = destino.resolve()
    for ruta, datos in adjuntos.items():
        objetivo = (destino / ruta).resolve()
        try:
            objetivo.relative_to(raiz)
        except ValueError as exc:
            raise ValueError(f"El ensamble cita un archivo fuera del paquete: {ruta}") from exc
        objetivo.parent.mkdir(parents=True, exist_ok=True)
        objetivo.write_bytes(datos)
        archivos[ruta] = sha256(datos)
    for item in [*contrato["conformeros"], *contrato["poses"]]:
        for ruta, huella in ((item["archivo"], item["sha256"]), (item["sdf"], item["sdf_sha256"])):
            if archivos.get(ruta) != huella:
                raise ValueError(f"El SHA-256 de {ruta} no es el que cita el contrato del ensamble")
    contrato = {**contrato, "origen": fuente}
    (destino / "ensamble.json").write_text(
        json.dumps(contrato, ensure_ascii=False, indent=2), encoding="utf-8")
    archivos["ensamble.json"] = sha256((destino / "ensamble.json").read_bytes())
    escena["declarar_si_se_dibuja"].append(
        "Ensamble: conformaciones discretas alineadas sólo para compararlas, poses de la piscina de "
        "K corridas de Vina reordenada por afinidad y controles físicos posteriores al acoplamiento.")


def construir_paquete(
    destino: Path, *, receptor_pdbqt: bytes, receptor_sha256: str,
    pdb_id: str, nombre: str, cadena: str, centro: tuple[float, float, float],
    tamano: tuple[float, float, float], fuente: dict[str, Any],
    poses_sdf: bytes | None = None, poses_sha256: str | None = None,
    afinidad: float | None = None, version_vina: str | None = None,
    semilla: int | None = None,
    search_metadata: dict | None = None, search_files: dict[str, bytes] | None = None,
    ensamble: dict | None = None, seccion: str | None = None,
) -> dict[str, Any]:
    if sha256(receptor_pdbqt) != receptor_sha256:
        raise ValueError("El SHA-256 del receptor no coincide con la fuente")
    if not all(math.isfinite(v) for v in (*centro, *tamano)) or any(v <= 0 for v in tamano):
        raise ValueError("La caja no es válida")
    preparado, huecos, cadenas, sin_elemento = pdbqt_a_pdb(receptor_pdbqt)
    geometria = destino / "geometry"
    geometria.mkdir(parents=True, exist_ok=False)
    (geometria / "prepared.pdb").write_bytes(preparado)
    (geometria / "prepared.pdbqt").write_bytes(receptor_pdbqt)
    archivos = {"geometry/prepared.pdb": sha256(preparado),
                "geometry/prepared.pdbqt": receptor_sha256}
    escena = {
        "schema": "moldesign.scene/1",
        "receptor": {"pdb_id": pdb_id, "nombre": nombre, "cadena_principal": cadena,
                     "seccion": seccion,
                     "cadenas_del_sitio": cadenas, "sitio_multicadena": len(cadenas) > 1,
                     "familia_estructural": None, "resolucion_a": None},
        "encuadre": {"objetivo": list(centro), "caja": list(tamano),
                     "fuente": "corrida persistida" if fuente.get("origen") == "moldex" else "receptor registrado"},
        "resaltar": {"hotspots": [], "fuente": None},
        "geometria": {"deposited": None,
                       "prepared": {"ruta": "geometry/prepared.pdb", "sha256": sha256(preparado),
                                    "atomos": len(preparado.splitlines()) - 1,
                                    "cadenas_conservadas": cadenas,
                                    "que_es": "PDB visual derivado del PDBQT preparado exacto",
                                    "fuente_pdbqt_sha256": receptor_sha256},
                       "site_ligand": None},
        "declarado": {"huecos_de_cadena": huecos, "aguas": {},
                      "conversion_visual": "Coordenadas y numeración conservadas del PDBQT.",
                      # Tipos AutoDock sin elemento conocido: su columna queda vacía (SCI-A-028).
                      "tipos_sin_elemento": sin_elemento},
        "no_dibujar": [
            {"id": "trayectoria_de_union", "razon": "No se midió una trayectoria de unión.",
             "permitido_en_su_lugar": "Aparición por fundido de la pose."},
            {"id": "busqueda", "razon": "Vina del producto no conservó una traza interna."},
        ],
        "declarar_si_se_dibuja": [],
        "procedencia": {**fuente, "receptor_pdbqt_sha256": receptor_sha256},
    }
    if poses_sdf is not None:
        if not poses_sha256 or sha256(poses_sdf) != poses_sha256:
            raise ValueError("El SHA-256 de las poses no coincide con la corrida")
        pose, pose_pdb, n_atomos = primera_pose(poses_sdf)
        docking = destino / "docking"
        docking.mkdir()
        (docking / "pose_001.sdf").write_bytes(pose)
        (docking / "pose_001.pdb").write_bytes(pose_pdb)
        (docking / "poses.sdf").write_bytes(poses_sdf)
        archivos.update({"docking/pose_001.sdf": sha256(pose),
                         "docking/pose_001.pdb": sha256(pose_pdb),
                         "docking/poses.sdf": poses_sha256})
        contrato = {"schema": "moldesign.dock/1", "origen": fuente,
                    "caja": {"centro": list(centro), "tamano": list(tamano)},
                    "motor": "vina", "version": version_vina, "semilla": semilla,
                    "traza_interna": None,
                    "poses": [{"rank": 1, "archivo": "docking/pose_001.sdf",
                               "pdb_visual": "docking/pose_001.pdb",
                               "pdb_visual_sha256": sha256(pose_pdb),
                               "sha256": sha256(pose), "atomos": n_atomos,
                               "afinidad_kcal_mol": afinidad}],
                    "coleccion": {"archivo": "docking/poses.sdf", "sha256": poses_sha256}}
        if search_metadata is not None:
            from services.docking.search_trace import models, parse
            if not search_files or search_metadata["receptor_sha256"] != receptor_sha256:
                raise ValueError("La traza no pertenece al receptor de esta corrida")
            if search_metadata.get("poses_sdf_sha256") != poses_sha256:
                raise ValueError("La traza no pertenece a las poses de esta corrida")
            if search_metadata["box_center"] != list(centro) or search_metadata["box_size"] != list(tamano) or search_metadata["seed"] != semilla:
                raise ValueError("La traza no pertenece al protocolo de esta corrida")
            traza = parse(search_files, search_metadata["trace"]["replicas"])
            # The archive retains every sampled state. The short video selects
            # up to twelve uniformly, without claiming continuous motion.
            state_blocks = models(search_files["states.pdbqt"])
            last = len(state_blocks) - 1
            indices = sorted({round(i * last / max(1, min(12, len(state_blocks)) - 1))
                              for i in range(min(12, len(state_blocks)))})
            def visual(block):
                atoms = [line[:66].ljust(66) + "\n" for line in block.decode().splitlines()
                         if line.startswith(("ATOM  ", "HETATM"))]
                return ("".join(atoms) + "END\n").encode()
            def guardar(nombre_archivo, data):
                (destino / nombre_archivo).write_bytes(data)
                archivos[nombre_archivo] = sha256(data)
            samples = []
            for index in indices:
                item = dict(traza["instantaneas"][index])
                name = f"docking/state_{item['step']:07d}.pdb"
                data = visual(state_blocks[index]); guardar(name, data)
                samples.append({**item, "archivo": name, "sha256": sha256(data)})
            final_blocks = models(search_files["poses.pdbqt"])
            from rdkit import Chem
            sdf_mols = list(Chem.ForwardSDMolSupplier(io.BytesIO(poses_sdf), removeHs=False))
            if len(sdf_mols) != len(final_blocks) or any(m is None for m in sdf_mols):
                raise ValueError("Las poses persistidas y la traza tienen distinto número de modelos")
            poses_native = []
            for item, block in zip(traza["poses"], final_blocks):
                name = f"docking/native_pose_{item['rank']:03d}.pdb"
                data = visual(block); guardar(name, data)
                poses_native.append({**item, "archivo": name, "sha256": sha256(data)})
            guardar("docking/search.csv", search_files["replica_0.csv"])
            guardar("docking/search.pdbqt", search_files["states.pdbqt"])
            guardar("docking/native_poses.pdbqt", search_files["poses.pdbqt"])
            contrato["poses"] = poses_native
            contrato["motor"] = {"nombre": "AutoDock Vina", **search_metadata["instrumentation"]}
            contrato["traza_interna"] = {**traza, "instantaneas": samples,
                                         "csv_replica": "docking/search.csv",
                                         "csv_sha256": sha256(search_files["replica_0.csv"])}
            escena["no_dibujar"] = [x for x in escena["no_dibujar"] if x["id"] != "busqueda"]
            escena["declarar_si_se_dibuja"].append("Búsqueda: estados retenidos muestreados de la réplica 0, sin trayectoria interpolada.")
        (destino / "docking.json").write_text(json.dumps(contrato, ensure_ascii=False, indent=2), encoding="utf-8")
        archivos["docking.json"] = sha256((destino / "docking.json").read_bytes())
    if ensamble is not None:
        _escribir_ensamble(destino, ensamble, archivos, escena, fuente, centro, tamano)
    (destino / "scene.json").write_text(json.dumps(escena, ensure_ascii=False, indent=2), encoding="utf-8")
    archivos["scene.json"] = sha256((destino / "scene.json").read_bytes())
    (destino / "MANIFEST.sha256").write_text(
        "".join(f"{digest}  {nombre_archivo}\n" for nombre_archivo, digest in sorted(archivos.items())),
        encoding="utf-8")
    return escena
