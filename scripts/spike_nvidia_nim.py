#!/usr/bin/env python
"""Spike de la Fase 0 del motor externo (docs/97): ¿cómo responde DE VERDAD la API alojada de NVIDIA?

NO es producto ni ciencia sellada. Sirve para confirmar, con una clave temporal, lo que la documentación
pública no deja leer: rutas alojadas, autenticación, esquema real de entrada y salida, latencia, sondeo
asíncrono, límites de la clave gratuita. Todo lo que figura aquí como ruta o esquema es una SUPOSICIÓN que
la propia ejecución confirma o desmiente: ante un 4xx el script imprime el cuerpo del error, que dice qué
campo falla.

Qué envía: sólo datos PÚBLICOS (secuencia de la proteasa del VIH-1, indinavir y, para DiffDock, el PDB 1HSG
de RCSB). Nada del usuario ni de ningún caso.

La clave: variable de entorno NVIDIA_API_KEY o un archivo FUERA del repositorio (--key-file; por defecto
D:\\moldesign-dev-data\\secretos\\nvidia.key). Nunca se imprime ni se guarda, y todo lo que se escribe a disco
pasa por `redactar`. Un archivo de clave dentro del repositorio se rechaza.

    python scripts/spike_nvidia_nim.py --dry-run                 # sin red ni clave: sólo comprueba las cargas
    python scripts/spike_nvidia_nim.py --motor boltz2            # una llamada real
    python scripts/spike_nvidia_nim.py --motor ambos --timeout 600
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CLAVE_POR_DEFECTO = Path(r"D:\moldesign-dev-data\secretos\nvidia.key")
SALIDA = Path(r"D:\moldesign-dev-data\spike-nvidia")

# SUPOSICIONES a confirmar con la clave (la documentación pública sólo describe el contenedor propio).
BASE_URL = "https://health.api.nvidia.com/v1"
RUTAS = {"boltz2": "biology/mit/boltz2/predict", "diffdock": "biology/mit/diffdock"}
ESTADO_NVCF = "https://api.nvcf.nvidia.com/v2/nvcf/pexec/status/{id}"
RCSB_1HSG = "https://files.rcsb.org/download/1HSG.pdb"

PATRON_CLAVE = re.compile(r"nvapi-[A-Za-z0-9_\-]{8,}")

# Entradas públicas. La secuencia es la de referencia de la proteasa del VIH-1 con las mutaciones
# estabilizadoras habituales: este spike mide plomería, no se compara contra el cristal.
PROTEASA = (
    "PQITLWKRPLVTIKIGGQLKEALLDTGADDTVLEEMNLPGRWKPKMIGGIGGFIKVRQYDQIIIEIAGHKAIGTVLVGPTPVNIIGRNLLTQIGATLNF"
)
INDINAVIR = (
    "CC(C)(C)NC(=O)[C@@H]1CN(CCN1C[C@H](C[C@@H](CC2=CC=CC=C2)C(=O)N[C@H]3[C@@H](CC4=CC=CC=C34)O)O)"
    "CC5=CN=CC=C5"
)


def redactar(valor: object, clave: str | None = None) -> str:
    """Texto sin ninguna clave: la dada y cualquier cosa con forma de `nvapi-…`."""
    texto = valor if isinstance(valor, str) else json.dumps(valor, ensure_ascii=False)
    if clave:
        texto = texto.replace(clave, "nvapi-***")
    return PATRON_CLAVE.sub("nvapi-***", texto)


def leer_clave(ruta: Path) -> str:
    clave = os.environ.get("NVIDIA_API_KEY", "").strip()
    if not clave and ruta.is_file():
        if RAIZ in ruta.resolve().parents:
            raise SystemExit("La clave no puede estar dentro del repositorio: muévela fuera y vuelve a intentar.")
        clave = ruta.read_text(encoding="utf-8").strip()
    if not clave:
        raise SystemExit(
            "Falta la clave: define NVIDIA_API_KEY o escribe el archivo " + str(ruta) + " (fuera del repositorio)."
        )
    if not clave.startswith("nvapi-"):
        print("Aviso: la clave no empieza por «nvapi-»; se usa igual.")
    return clave


# Fragmento de KRAS (47 aa), el de la prueba mínima del propietario: sin ligando ni afinidad, es la
# sonda más barata para saber si la URL y la clave funcionan antes de gastar tiempo en la carga completa.
SECUENCIA_MINIMA = "MTEYKLVVVGACGVGKSALTIQLIQNHFVDEYDPTIEDSYRKQVVID"


def carga_boltz2(minima: bool = False) -> dict:
    if minima:
        return {"polymers": [{"id": "A", "molecule_type": "protein", "sequence": SECUENCIA_MINIMA}]}
    return {
        "polymers": [{"id": "A", "molecule_type": "protein", "sequence": PROTEASA}],
        "ligands": [{"id": "L", "smiles": INDINAVIR, "predict_affinity": True}],
        "recycling_steps": 3,
        "sampling_steps": 50,
        "diffusion_samples": 1,
        "output_format": "mmcif",
    }


def carga_diffdock(pdb: str, smiles: str = INDINAVIR) -> dict:
    return {
        "ligand": smiles,
        "ligand_file_type": "txt",
        "protein": pdb,
        "num_poses": 5,
        "time_divisions": 20,
        "steps": 18,
        "save_trajectory": False,
        "is_staged": False,
    }


def huella(valor: object) -> str:
    crudo = json.dumps(valor, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(crudo).hexdigest()


def observaciones(motor: str, url: str, carga: dict, resp, transcurrido: float, sondeos: int, clave: str) -> dict:
    """Lo que se aprende de una llamada, sin la clave ni el cuerpo entero."""
    interesantes = ("ratelimit", "nvcf", "retry-after", "content-type", "x-request", "server")
    cabeceras = {k: v for k, v in resp.headers.items() if any(p in k.lower() for p in interesantes)}
    try:
        cuerpo = resp.json()
        claves = sorted(cuerpo.keys()) if isinstance(cuerpo, dict) else f"lista de {len(cuerpo)}"
    except ValueError:
        cuerpo, claves = None, None
    obs = {
        "motor": motor,
        "url": url,
        "estado_http": resp.status_code,
        "segundos": round(transcurrido, 2),
        "sondeos_202": sondeos,
        "cabeceras": cabeceras,
        "bytes_respuesta": len(resp.content),
        "huella_peticion": huella(carga),
        "huella_respuesta": hashlib.sha256(resp.content).hexdigest(),
        "claves_de_primer_nivel": claves,
    }
    if resp.status_code >= 400:
        # El cuerpo de un 4xx dice qué campo no encaja: es la mitad del valor del spike.
        obs["error"] = redactar(resp.text[:800], clave)
    return obs


def llamar(cliente, motor: str, carga: dict, clave: str, base_url: str, timeout: float) -> tuple[dict, str]:
    url = f"{base_url.rstrip('/')}/{RUTAS[motor]}"
    cabeceras = {
        "Authorization": f"Bearer {clave}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "NVCF-POLL-SECONDS": "30",
    }
    t0 = time.monotonic()
    resp = cliente.post(url, json=carga, headers=cabeceras, timeout=timeout)
    sondeos = 0
    # NVCF contesta 202 con un id cuando la tarea tarda: se sondea hasta el plazo.
    while resp.status_code == 202 and time.monotonic() - t0 < timeout:
        id_peticion = resp.headers.get("NVCF-REQID")
        if not id_peticion:
            break
        sondeos += 1
        resp = cliente.get(
            ESTADO_NVCF.format(id=id_peticion),
            headers={"Authorization": f"Bearer {clave}", "Accept": "application/json"},
            timeout=timeout,
        )
    return observaciones(motor, url, carga, resp, time.monotonic() - t0, sondeos, clave), resp.text


def guardar(sello: str, motor: str, obs: dict, cuerpo: str, clave: str) -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    (SALIDA / f"{sello}_{motor}_observaciones.json").write_text(
        redactar(obs, clave), encoding="utf-8")
    (SALIDA / f"{sello}_{motor}_respuesta.txt").write_text(redactar(cuerpo, clave), encoding="utf-8")


def resumen(obs: dict) -> str:
    base = f"{obs['motor']:9s} HTTP {obs['estado_http']}  {obs['segundos']:>7.1f} s  {obs['bytes_respuesta']:>9d} B"
    if "error" in obs:
        return base + "\n    error: " + obs["error"].replace("\n", " ")[:300]
    return base + f"  claves: {obs['claves_de_primer_nivel']}"


def descargar_1hsg() -> str:
    import httpx

    print(f"Descargando {RCSB_1HSG} (PDB público de RCSB, unos 200 KB).")
    r = httpx.get(RCSB_1HSG, timeout=60, follow_redirects=True)
    r.raise_for_status()
    return r.text


def comprobar_cargas() -> int:
    """--dry-run: valida las cargas sin red ni clave."""
    boltz = carga_boltz2()
    print(f"boltz2   polímeros={len(boltz['polymers'])} ligandos={len(boltz['ligands'])} "
          f"secuencia={len(PROTEASA)} aa")
    try:
        from rdkit import Chem

        molecula = Chem.MolFromSmiles(INDINAVIR)
        print("SMILES de indinavir:", "válido, %d átomos pesados" % molecula.GetNumHeavyAtoms()
              if molecula is not None else "NO PARSEA")
        if molecula is None:
            return 1
    except ImportError:
        print("RDKit no disponible: no se valida el SMILES.")
    difusion = carga_diffdock("<PDB 1HSG>")
    print("diffdock campos:", sorted(difusion))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--motor", choices=["boltz2", "diffdock", "ambos"], default="ambos")
    ap.add_argument("--carga", choices=["minima", "completa"], default="completa",
                    help="Boltz-2: «minima» = un polímero y nada más; «completa» = con ligando y afinidad")
    ap.add_argument("--base-url", default=BASE_URL)
    ap.add_argument("--key-file", type=Path, default=CLAVE_POR_DEFECTO)
    ap.add_argument("--receptor-pdb", type=Path, help="PDB para DiffDock; por defecto se baja 1HSG de RCSB")
    ap.add_argument("--smiles", default=INDINAVIR,
                    help="ligando de DiffDock; debe corresponder al receptor (por defecto indinavir, de 1HSG)")
    ap.add_argument("--timeout", type=float, default=300.0)
    ap.add_argument("--dry-run", action="store_true", help="valida las cargas; sin clave ni red")
    args = ap.parse_args(argv)
    # La consola de Windows usa cp1252 y rompería los acentos de los mensajes.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if args.dry_run:
        return comprobar_cargas()

    import httpx

    clave = leer_clave(args.key_file)
    motores = ["boltz2", "diffdock"] if args.motor == "ambos" else [args.motor]
    sello = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    cargas: dict[str, dict] = {}
    if "boltz2" in motores:
        cargas["boltz2"] = carga_boltz2(minima=args.carga == "minima")
    if "diffdock" in motores:
        pdb = args.receptor_pdb.read_text(encoding="utf-8") if args.receptor_pdb else descargar_1hsg()
        cargas["diffdock"] = carga_diffdock(pdb, args.smiles)

    with httpx.Client() as cliente:
        for motor, carga in cargas.items():
            try:
                obs, cuerpo = llamar(cliente, motor, carga, clave, args.base_url, args.timeout)
            except httpx.HTTPError as exc:
                obs = {"motor": motor, "estado_http": 0, "segundos": 0.0, "bytes_respuesta": 0,
                       "error": redactar(f"{type(exc).__name__}: {exc}", clave)}
                cuerpo = ""
            guardar(sello, motor, obs, cuerpo, clave)
            print(resumen(obs))
    print(f"Resultados en {SALIDA} (sin la clave).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
