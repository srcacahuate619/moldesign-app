#!/usr/bin/env python3
r"""Subida de receptores propios por la API, como la aplicación: qué entra, qué se evalúa y qué audita Preparación.

Parte del arnés del encargo (`docs/encargos/receptores-propios-1-0-2/qa_subida_receptores.py`) y lo
extiende: para cada caso aceptado hace subida → comprobación previa → evaluación con Vina real →
auditoría de Preparación (por la ruta `/dossier/{id}/preparacion`, en castellano y en inglés), y
registra el estado y los motivos. Levanta un backend con datos desechables (el arnés de
`check:evaluation-runtime`, vía `scripts/calibracion_receptor.py::Backend`).

Uso (con el Python embebido):

    python scripts/qa_subida_receptores.py --raiz <worktree> --salida <carpeta> [--casos casos.json]

`--raiz` es obligatorio: el backend, `tools/vina` y los módulos se toman de ese árbol.
Sin `--casos` repite los cuatro casos medidos el 2026-10-09 (`informe_20261009.json`).

`casos.json` es una lista de objetos:

    {"nombre": "8hfi_crudo.pdb",                  # nombre con el que se sube (y del caso)
     "archivo": "ruta al archivo",
     "campos": {"is_curated": "false", "chain_id": "A", ...},   # campos del formulario
     "origen": "ruta opcional a la estructura de origen", "campo_origen": "source_file",
     "ligando": "SMILES opcional",               # por defecto, la desipramina
     "esperado": {"http": 201, "evaluacion": "SUCCESS",
                  "codigo": "CODIGO_DE_ERROR",   # para los rechazos: el código que debe devolver
                  "preparacion_estado": "BLOQUEADO",
                  "requisitos": {"receptor.confianza_estructural": "REVISAR"},   # estado esperado de cada requisito
                  "igual_a": "otro_caso"}}       # mismo receptor_sha256 que otro caso

Escribe `informe.json` y sale con código 1 si algún caso no cumple lo esperado.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path


def _raiz() -> Path:
    for i, arg in enumerate(sys.argv):
        if arg == "--raiz" and i + 1 < len(sys.argv):
            return Path(sys.argv[i + 1]).resolve()
        if arg.startswith("--raiz="):
            return Path(arg.split("=", 1)[1]).resolve()
    raise SystemExit("Falta --raiz: la raíz del worktree cuyo backend se prueba.")


RAIZ = _raiz()
if not (RAIZ / "scripts" / "calibracion_receptor.py").is_file():
    raise SystemExit(f"{RAIZ} no parece la raíz de un worktree de MolDesign.")
sys.path.insert(0, str(RAIZ / "scripts"))
import calibracion_receptor as cr  # noqa: E402

DESIPRAMINA = "CNCCCN1c2ccccc2CCc2ccccc21"
CENTRO_8HFI = ("100.281", "100.843", "101.442")
FUENTE = Path(r"D:\moldesign-audits\cal-8hfi-01\datos-01\targets\8HFI")


def _casos_por_defecto() -> list[dict]:
    caja = {"chain_id": "A", "grid_center_x": CENTRO_8HFI[0], "grid_center_y": CENTRO_8HFI[1],
            "grid_center_z": CENTRO_8HFI[2], "grid_size_x": "30", "grid_size_y": "30", "grid_size_z": "30"}
    pdbqt = str(next(FUENTE.glob("prepared-*.pdbqt")))
    ok = {"http": 201, "evaluacion": "SUCCESS"}
    return [
        {"archivo": pdbqt, "nombre": "8hfi_curado.pdbqt", "campos": {**caja, "is_curated": "true"}, "esperado": ok},
        {"archivo": str(FUENTE / "raw.pdb"), "nombre": "8hfi_crudo.pdb", "campos": {**caja, "is_curated": "false"},
         "esperado": ok},
        {"archivo": str(FUENTE / "raw.pdb"), "nombre": "8HFI_CRUDO.PDB", "campos": {**caja, "is_curated": "false"},
         "esperado": {**ok, "igual_a": "8hfi_crudo.pdb"}},
        {"archivo": r"D:\moldesign-audits\verificacion-8hfi-20261008\fuentes\8HFI.cif", "nombre": "8hfi.cif",
         "campos": {**caja, "is_curated": "false"}, "esperado": {**ok, "igual_a": "8hfi_crudo.pdb"}},
    ]


def _multipart(campos: dict[str, str], archivos: list[tuple[str, str, bytes]]) -> tuple[bytes, str]:
    limite = uuid.uuid4().hex
    partes = [f'--{limite}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
              for k, v in campos.items()]
    for campo, nombre, contenido in archivos:
        partes.append(f'--{limite}\r\nContent-Disposition: form-data; name="{campo}"; filename="{nombre}"\r\n'
                      "Content-Type: application/octet-stream\r\n\r\n".encode() + contenido + b"\r\n")
    partes.append(f"--{limite}--\r\n".encode())
    return b"".join(partes), f"multipart/form-data; boundary={limite}"


def _llamar(be: cr.Backend, metodo: str, ruta: str, *, cuerpo=None, idioma: str = "es", cabeceras=None):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(
        be.base + ruta, data=datos, method=metodo,
        headers={"Authorization": f"Bearer {be.token}", "Accept-Language": idioma,
                 **({"Content-Type": "application/json"} if datos else {}), **(cabeceras or {})})
    try:
        with urllib.request.urlopen(req, timeout=1800) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        texto = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(texto)
        except ValueError:
            return e.code, {"detail": texto[:800]}


def subir(be: cr.Backend, caso: dict) -> tuple[int, dict]:
    archivo = Path(caso["archivo"])
    nombre = caso.get("nombre") or archivo.name
    archivos = [("file", nombre, archivo.read_bytes())]
    if caso.get("origen"):
        origen = Path(caso["origen"])
        archivos.append((caso.get("campo_origen", "source_file"), origen.name, origen.read_bytes()))
    campos = {"name": f"prueba {nombre}", **caso.get("campos", {})}
    cuerpo, tipo = _multipart(campos, archivos)
    req = urllib.request.Request(be.base + "/targets/upload", data=cuerpo, method="POST",
                                 headers={"Authorization": f"Bearer {be.token}", "Content-Type": tipo,
                                          "Accept-Language": caso.get("idioma", "es")})
    try:
        with urllib.request.urlopen(req, timeout=1800) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        texto = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(texto)
        except ValueError:
            return e.code, {"detail": texto[:800]}


_MARCAS_ES = re.compile(r"[áéíóúñ¿¡ÁÉÍÓÚÑ]")
_FUNCION_ES = {"el", "la", "los", "las", "del", "que", "con", "sin", "una", "por", "para", "se", "es", "al",
               "este", "esta", "como"}


def _parece_espanol(texto: str) -> bool:
    if re.match(r"^\d+ corte\(s\) del esqueleto", texto):     # huecos: ruido de la base (ver RUIDO_PREEXISTENTE)
        return False
    limpio = re.sub(r"`[^`]*`|https?://\S+|\b[A-Za-z0-9_]{12,}\b", " ", texto)
    palabras = [w.lower() for w in re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]+", limpio)]
    return bool(_MARCAS_ES.search(limpio)) or sum(1 for w in palabras if w in _FUNCION_ES) >= 2


#: Español que la comprobación previa y el dossier YA dejaban en las respuestas en inglés en la base
#: (`codex/release-hygiene` e9b032ae), medido con el caso automático de 8HFI antes de tocar nada: títulos de los
#: controles (el cliente los traduce), la caja del catálogo y avisos con datos variables. No son de este encargo.
RUIDO_PREEXISTENTE = (
    "Caja de búsqueda", "Center (", "Forma química del ligando", "La especie acoplada no es la entrada",
    "Plantillas de histidina asignadas por Meeko", "Política de heteroátomos de esta ruta",
    "Preparación en condición desolvatada", "1 corte(s) del esqueleto", "Fuente del receptor",
    "Receptor preparado", "Cadena del receptor", "Protonación del receptor", "Especies retiradas",
    "Model A usó la pose", "La preparación retira ",
    # Avisos de `vina_service.py` (commits 12bd2110 y 20955f15, anteriores al encargo) que se emiten en español
    # también para el catálogo: `RESIDUOS_ELIMINADOS_FUERA_DEL_SITIO`, `CADENAS_LATERALES_TRUNCADAS` y la lista de
    # cofactores fuera del sitio. Un receptor propio en modo `respetar` con residuos sin plantilla los hace visibles.
    "Meeko eliminó residuos del receptor", "El cristal no resolvía ", "Cofactors or modified residues without",
    # Otros tres textos anteriores al encargo (be1c48d9 y cb83add0) que salen en español, o a medias, en la versión
    # inglesa de cualquier receptor del catálogo con ligandos quirales sin estereoquímica o con metales junto al sitio.
    "La entrada dejó ", "2 metal atoms are removed", "Preparation removes ",
)


def _cadenas(valor):
    if isinstance(valor, str):
        yield valor
    elif isinstance(valor, dict):
        for clave, v in valor.items():
            if clave in {"pdb_id", "provenance", "sha256", "input_document", "fingerprint", "title"}:
                continue
            yield from _cadenas(v)
    elif isinstance(valor, (list, tuple)):
        for v in valor:
            yield from _cadenas(v)


def _preflight(be: cr.Backend, smiles: str, pdb_id: str, chain: str, idioma: str = "es") -> dict:
    config = json.loads(json.dumps(cr.CONFIG_CASO))
    config["stage_params"]["docking"]["seed"] = 42
    codigo, cuerpo = _llamar(be, "POST", "/evaluation/preflight", idioma=idioma, cuerpo={
        "smiles": smiles, "target_pdb_id": pdb_id, "docking_engine": "vina", "exhaustiveness": 8,
        "num_poses": 9, "conformers": 1, "chain": chain, "pipeline_config": config})
    if codigo != 200:
        return {"http": codigo, "detalle": cuerpo.get("detail")}
    return {"http": 200, "_cuerpo": cuerpo, "bloqueantes": cuerpo.get("technical_blockers"), "advertencias": cuerpo.get("warnings"),
            "no_evaluados": cuerpo.get("not_evaluated"),
            "controles": {c["code"]: c["state"] for c in cuerpo.get("controls", [])
                          if c["code"].startswith(("RECEPTOR", "POLITICA", "ESPECIES", "COFACTOR", "METALES"))},
            "modo": (cuerpo.get("receptor") or {}).get("modo_de_preparacion")}


def _preparacion(be: cr.Backend, molecule_id: str, idioma: str) -> dict:
    codigo, cuerpo = _llamar(be, "POST", f"/evaluation/dossier/{molecule_id}/preparacion", idioma=idioma,
                             cuerpo={"case_id": "qa-subida", "name": "qa subida"})
    if codigo != 200:
        return {"http": codigo, "detalle": cuerpo.get("detail")}
    requisitos = {r["clave"]: {"estado": r["estado"], "razon": r.get("razon"), "valor": r.get("valor"),
                               "accion": r.get("accion_recomendada")}
                  for b in cuerpo["bloques"] for r in b["requisitos"]}
    return {"http": 200, "estado": cuerpo["estado"], "razon": cuerpo["razon"],
            "bloqueantes": cuerpo["bloqueantes"], "en_revision": cuerpo["en_revision"],
            "requisitos": requisitos}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    p.add_argument("--raiz", required=True, help="raíz del worktree cuyo backend se prueba")
    p.add_argument("--casos")
    p.add_argument("--salida", required=True)
    p.add_argument("--smiles", default=DESIPRAMINA)
    a = p.parse_args()
    salida = Path(a.salida)
    casos = json.loads(Path(a.casos).read_text(encoding="utf-8")) if a.casos else _casos_por_defecto()
    informe: list[dict] = []
    por_nombre: dict[str, dict] = {}
    fallan = 0
    with cr.Backend(salida / "datos") as be:
        for caso in casos:
            codigo, cuerpo = subir(be, caso)
            target = (cuerpo.get("target") or {}) if isinstance(cuerpo, dict) else {}
            nombre = caso.get("nombre") or Path(caso["archivo"]).name
            fila = {"caso": nombre, "campos": caso.get("campos"), "origen": caso.get("origen"), "http": codigo,
                    "codigo": cuerpo.get("codigo") if codigo >= 400 else None,
                    "detalle": cuerpo.get("detail") if codigo >= 400 else cuerpo.get("message"),
                    "pdb_id": target.get("pdb_id")}
            if codigo < 400 and fila["pdb_id"]:
                cadena = target.get("chain") or caso.get("campos", {}).get("chain_id", "A")
                smiles = caso.get("ligando") or a.smiles
                fila["preflight"] = _preflight(be, smiles, fila["pdb_id"], cadena)
                fila["preflight"].pop("_cuerpo", None)
                try:
                    r = be.evaluar(smiles, fila["pdb_id"], cadena, 42, f"subida-{nombre}")
                    res = r["resultado"]
                    prov = (res.get("docking_protocol") or {}).get("execution_provenance") or {}
                    prep = prov.get("receptor_prep") or {}
                    fila.update({
                        "evaluacion": "SUCCESS", "E_top1": res.get("affinity_kcal"), "segundos": r["segundos"],
                        "receptor_sha256": prov.get("receptor_sha256"),
                        "modo_de_preparacion": prep.get("modo_de_preparacion"),
                        "species_diff": bool(prep.get("species_diff")),
                        "protonation_method": prep.get("protonation_method"),
                        "entrada": (prep.get("entrada") or {}).get("formato"),
                    })
                    molecula = res.get("molecule_id")
                    if molecula:
                        fila["preparacion"] = {"es": _preparacion(be, molecula, "es"),
                                               "en": _preparacion(be, molecula, "en")}
                    en = _preflight(be, smiles, fila["pdb_id"], cadena, "en")
                    textos = [*_cadenas((en.get("_cuerpo") or {}).get("controls")),
                              *_cadenas((en.get("_cuerpo") or {}).get("preparation_diff")),
                              *_cadenas(fila["preparacion"]["en"] if molecula else {}),
                              *_cadenas(_llamar(be, "GET", f"/evaluation/status/{r['task_id']}", idioma="en")[1]
                                        .get("result", {}).get("scientific_warnings"))]
                    fila["espanol_en_ingles"] = sorted({t[:160] for t in textos
                                                 if _parece_espanol(t) and not t.startswith(RUIDO_PREEXISTENTE)})[:8]
                except Exception as exc:  # noqa: BLE001 - se registra
                    fila.update({"evaluacion": "FALLA", "error": str(exc)[:600]})
            esperado = caso.get("esperado") or {}
            cumple = not fila.get("espanol_en_ingles")
            if esperado.get("evaluacion") == "SUCCESS" and "espanol_en_ingles" not in fila:
                cumple = False
            for clave, valor in esperado.items():
                if clave == "igual_a":
                    otro = por_nombre.get(valor, {})
                    cumple &= bool(fila.get("receptor_sha256")) and fila.get("receptor_sha256") == otro.get("receptor_sha256")
                elif clave == "preparacion_estado":
                    cumple &= (fila.get("preparacion") or {}).get("es", {}).get("estado") == valor
                elif clave == "requisitos":
                    reqs = (fila.get("preparacion") or {}).get("es", {}).get("requisitos", {})
                    cumple &= all((reqs.get(k) or {}).get("estado") == v for k, v in valor.items())
                else:
                    cumple &= fila.get(clave) == valor
            fila["cumple"] = cumple
            fallan += not cumple
            informe.append(fila)
            por_nombre[nombre] = fila
            resumen = {k: fila.get(k) for k in ("caso", "http", "codigo", "evaluacion", "E_top1", "segundos",
                                                "receptor_sha256", "modo_de_preparacion", "cumple")}
            resumen["preparacion"] = (fila.get("preparacion") or {}).get("es", {}).get("estado")
            print(json.dumps(resumen, ensure_ascii=False), flush=True)
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "informe.json").write_text(json.dumps(informe, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(informe) - fallan}/{len(informe)} casos cumplen lo esperado")
    return 1 if fallan else 0


if __name__ == "__main__":
    raise SystemExit(main())
