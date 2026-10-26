"""El lanzador de las FOTOS. Python normal (con Pillow), fuera de Blender.

    python correr_foto.py preparar --pdb 4FK3 --guion sitio_activo --sujeto pose_evaluada \\
        --formato social_vertical --sufijo abc --carpeta <salida> --blender <blender.exe> \\
        --dispositivo cpu

    python correr_foto.py tomar --escena <salida>/escena_fotos_abc.json --fotograma 253 \\
        --ancho 1080 --alto 1920 --muestras 128 --dispositivo gpu --nombre foto_1 \\
        --carpeta <salida> --blender <blender.exe>

`preparar` construye la escena UNA vez (`maestro.py --fotos`: el `.blend` y el acta
con los momentos sugeridos) y rinde una miniatura de cada momento, para elegir
viendo. `tomar` abre ese `.blend` y rinde un fotograma a la resolución pedida;
sirve igual para la foto final que para previsualizar un momento libre a tamaño
pequeño. Las dos componen escena y rótulos como el vídeo (`salida/foto_final.py`)
y dejan un acta JSON junto a cada PNG, con su SHA-256.

Como `correr_caso.ps1`, recibe las rutas del motor y de los casos por entorno
(`MOLCY_SCENES_DIR`, `MOLCY_OUTPUT_DIR`...). Lo que imprime es para el registro;
lo que vale es el acta. Códigos de salida: 0 = OK, 1 = FALLO (motivo en la
última línea, `FALLO <motivo>`).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
if str(AQUI) not in sys.path:
    sys.path.insert(0, str(AQUI))

from PIL import Image                                           # noqa: E402

from salida.foto_final import componer, ocupacion_esquinas      # noqa: E402

ADDON_MN = "bl_ext.blender_org.molecularnodes"
#: Lado largo de las miniaturas de los momentos sugeridos, y sus muestras.
MINIATURA, MUESTRAS_MINIATURA = 480, 16
#: Sin ventana de consola por cada Blender en Windows.
SIN_VENTANA = 0x08000000 if os.name == "nt" else 0


class Fallo(Exception):
    pass


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def blender(exe: str, args: list[str], marca: str) -> list[str]:
    """Lanza Blender, copia su salida al registro y exige `marca` y código 0."""
    if not exe or not Path(exe).is_file():
        raise Fallo(f"SIN_BLENDER({exe})")
    hecho = subprocess.run([exe, "-b", *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, encoding="utf-8", errors="replace", check=False,
                           creationflags=SIN_VENTANA)
    sys.stdout.write(hecho.stdout)
    sys.stdout.flush()
    lineas = hecho.stdout.splitlines()
    if any("QC_ABORTADO" in l for l in lineas):
        raise Fallo("QC_ABORTADO")
    if any("Traceback" in l for l in lineas):
        raise Fallo("TRACEBACK")
    propio = next((l.strip() for l in lineas
                   if l.startswith(("SIN_GPU_CYCLES", "ASPECTO_DISTINTO", "BLEND_EQUIVOCADO",
                                    "RESOLUCION_FUERA_DE_LIMITES", "FOTO_SIN_PNG", "ESPACIO_INSUFICIENTE")))
                  , None)
    if propio:
        raise Fallo(propio.split(":")[0])
    if hecho.returncode != 0:
        raise Fallo(f"BLENDER_EXIT_{hecho.returncode}")
    if not any(l.startswith(marca) for l in lineas):
        raise Fallo(f"SIN_{marca}")
    return lineas


def _json_de(lineas: list[str], marca: str) -> list[dict]:
    return [json.loads(l[len(marca):].strip()) for l in lineas if l.startswith(marca + " ")]


def leer_escena(ruta: Path) -> tuple[dict, Path]:
    """El acta de la escena y su .blend, comprobado por SHA-256: un .blend que no es el
    de la escena daría fotos de otra cosa."""
    escena = json.loads(ruta.read_text(encoding="utf-8"))
    if escena.get("schema") != "molcy.fotos.escena/1":
        raise Fallo("ESCENA_DESCONOCIDA")
    blend = ruta.parent / "blender" / escena["blend"]["nombre"]
    if not blend.is_file() or sha256(blend) != escena["blend"]["sha256"]:
        raise Fallo("BLEND_NO_COINCIDE")
    return escena, blend


def rendir(exe: str, blend: Path, escena_json: Path, fotogramas: list[int], ancho: int,
           alto: int, muestras: int, dispositivo: str, tmp: Path) -> tuple[dict, list[dict]]:
    lineas = blender(exe, [str(blend), "--factory-startup", "--addons", ADDON_MN,
                           "--python", str(AQUI / "foto.py"), "--",
                           "--escena", str(escena_json),
                           "--fotogramas", ",".join(str(f) for f in fotogramas),
                           "--ancho", str(ancho), "--alto", str(alto),
                           "--muestras", str(muestras), "--dispositivo", dispositivo,
                           "--salida", str(tmp)], "FOTO_LISTA")
    ajustes = _json_de(lineas, "FOTO_AJUSTES")
    hechos = _json_de(lineas, "FOTO_FOTOGRAMA")
    if len(ajustes) != 1 or sorted(h["fotograma"] for h in hechos) != sorted(fotogramas):
        raise Fallo("FOTOGRAMAS_INCOMPLETOS")
    return ajustes[0], hechos


def montar(tmp: Path, hecho: dict, escena: dict, destino: Path) -> dict:
    """Compone un fotograma rendido y lo guarda en `destino` (PNG, 300 ppp)."""
    with Image.open(tmp / hecho["escena"]) as im:
        im.load()
        base = im.copy()
    capa = None
    if hecho.get("capa"):
        with Image.open(tmp / hecho["capa"]) as im:
            im.load()
            capa = im.copy()
    foto, reforzada = componer(base, capa, escena.get("etiquetas_lectura") or [], hecho["fotograma"])
    destino.unlink(missing_ok=True)
    foto.save(destino, format="PNG", dpi=(300, 300), compress_level=6)
    return {"archivo": destino.name, "sha256": sha256(destino), "bytes": destino.stat().st_size,
            "ancho": foto.width, "alto": foto.height,
            "esquinas": ocupacion_esquinas(reforzada, foto.size)}


def tamano_miniatura(formato: dict, lado: int = MINIATURA) -> tuple[int, int]:
    fw, fh = formato["ancho"], formato["alto"]
    if fw >= fh:
        return lado, max(1, round(lado * fh / fw))
    return max(1, round(lado * fw / fh)), lado


def preparar(a) -> dict:
    carpeta = Path(a.carpeta).resolve()
    sufijo = f"_{a.sufijo}" if a.sufijo else ""
    t0 = time.time()
    blender(a.blender, ["--factory-startup", "--addons", ADDON_MN,
                        "--python", str(AQUI / "maestro.py"), "--", a.pdb,
                        "--guion", a.guion, "--sujeto", a.sujeto, "--formato", a.formato,
                        "--sufijo", a.sufijo, "--experimental-look", "--fotos"]
                        + (["--ajustes", a.ajustes] if getattr(a, "ajustes", "") else []),
            "FOTOS_ESCENA_OK")
    construccion = round(time.time() - t0, 1)
    escena_json = carpeta / f"escena_fotos{sufijo}.json"
    escena, blend = leer_escena(escena_json)
    momentos = escena["momentos"]
    if not momentos:
        raise Fallo("SIN_MOMENTOS")
    ancho, alto = tamano_miniatura(escena["formato"], a.miniatura)
    tomas = carpeta / f"tomas{sufijo}"
    tmp = carpeta / f"_tomas{sufijo}"
    shutil.rmtree(tmp, ignore_errors=True)
    tomas.mkdir(exist_ok=True)
    t1 = time.time()
    try:
        ajustes, hechos = rendir(a.blender, blend, escena_json, [m["fotograma"] for m in momentos],
                                 ancho, alto, a.muestras, a.dispositivo, tmp)
        por_fotograma = {h["fotograma"]: h for h in hechos}
        salida = []
        for m in momentos:
            hecho = por_fotograma[m["fotograma"]]
            png = montar(tmp, hecho, escena, tomas / f"toma_{m['fotograma']:04d}.png")
            salida.append({**m, **png, "segundos": round(hecho["segundos_escena"] + hecho["segundos_capa"], 2)})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    acta = {"schema": "molcy.fotos.tomas/1", "escena": escena_json.name,
            "escena_sha256": sha256(escena_json), "carpeta": tomas.name,
            "fotogramas_fuente": escena["fotogramas_fuente"], "beats": escena["beats"],
            "momentos": salida, "render_ajustes": ajustes,
            "segundos": {"construccion": construccion, "miniaturas": round(time.time() - t1, 1)}}
    (carpeta / f"tomas{sufijo}.json").write_text(json.dumps(acta, ensure_ascii=False, indent=2),
                                                 encoding="utf-8")
    return {"tomas": f"tomas{sufijo}.json", "momentos": len(salida), **acta["segundos"]}


def tomar(a) -> dict:
    carpeta = Path(a.carpeta).resolve()
    escena_json = Path(a.escena).resolve()
    if escena_json.parent != carpeta:
        raise Fallo("ESCENA_FUERA_DE_LA_CARPETA")
    escena, blend = leer_escena(escena_json)
    if not a.nombre or Path(a.nombre).name != a.nombre or a.nombre.startswith("."):
        raise Fallo("NOMBRE_INVALIDO")
    tmp = carpeta / f"_{a.nombre}"
    shutil.rmtree(tmp, ignore_errors=True)
    t0 = time.time()
    try:
        ajustes, (hecho,) = rendir(a.blender, blend, escena_json, [a.fotograma], a.ancho, a.alto,
                                   a.muestras, a.dispositivo, tmp)
        png = montar(tmp, hecho, escena, carpeta / f"{a.nombre}.png")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    momento = next((m for m in escena["momentos"] if m["fotograma"] == a.fotograma), None)
    beat = next((b for b, (i, j) in escena["beats"].items() if i <= a.fotograma <= j), None)
    acta = {"schema": "molcy.foto/1", "pdb_id": escena["pdb_id"], "guion": escena["guion"],
            "formato": escena["formato"]["nombre"], "sujeto": escena["sujeto"],
            "fotograma": a.fotograma, "fotogramas_fuente": escena["fotogramas_fuente"],
            "beat": beat, "momento": momento["id"] if momento else None,
            "tipo": momento["tipo"] if momento else "libre",
            "dispositivo": a.dispositivo, "render_ajustes": ajustes,
            "png": png, "escena": {"archivo": escena_json.name, "sha256": sha256(escena_json)},
            "blend_sha256": escena["blend"]["sha256"],
            "presentacion": escena.get("presentacion"),
            "procedencia_paquete": escena.get("procedencia_paquete"),
            "segundos": {"escena": hecho["segundos_escena"], "capa": hecho["segundos_capa"],
                         "total": round(time.time() - t0, 1)}}
    (carpeta / f"{a.nombre}.json").write_text(json.dumps(acta, ensure_ascii=False, indent=2),
                                              encoding="utf-8")
    return {"foto": png["archivo"], "acta": f"{a.nombre}.json", "segundos": acta["segundos"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="correr_foto")
    sub = ap.add_subparsers(dest="orden", required=True)
    p = sub.add_parser("preparar")
    p.add_argument("--pdb", required=True)
    p.add_argument("--guion", default="sitio_activo")
    p.add_argument("--sujeto", default="ligando_cocristal")
    p.add_argument("--formato", required=True)
    p.add_argument("--sufijo", default="")
    p.add_argument("--ajustes", default="")
    p.add_argument("--miniatura", type=int, default=MINIATURA)
    p.add_argument("--muestras", type=int, default=MUESTRAS_MINIATURA)
    t = sub.add_parser("tomar")
    t.add_argument("--escena", required=True)
    t.add_argument("--fotograma", type=int, required=True)
    t.add_argument("--ancho", type=int, required=True)
    t.add_argument("--alto", type=int, required=True)
    t.add_argument("--muestras", type=int, required=True)
    t.add_argument("--nombre", required=True)
    for q in (p, t):
        q.add_argument("--carpeta", required=True)
        q.add_argument("--blender", default=os.environ.get("MOLCY_BLENDER", ""))
        q.add_argument("--dispositivo", choices=("cpu", "gpu"), required=True)
    a = ap.parse_args(argv)
    if a.orden == "preparar" and Path(os.environ.get("MOLCY_OUTPUT_DIR") or a.carpeta).resolve() != Path(a.carpeta).resolve():
        # maestro.py escribe en MOLCY_OUTPUT_DIR: si apunta a otro sitio, el acta no estaría donde se busca.
        print("FALLO SALIDA_DISTINTA", flush=True)
        return 1
    os.environ["MOLCY_OUTPUT_DIR"] = str(Path(a.carpeta).resolve())
    try:
        resultado = preparar(a) if a.orden == "preparar" else tomar(a)
    except Fallo as exc:
        print(f"FALLO {exc}", flush=True)
        return 1
    marca = "TOMAS_OK" if a.orden == "preparar" else "FOTO_OK"
    print(f"{marca} " + json.dumps(resultado, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
