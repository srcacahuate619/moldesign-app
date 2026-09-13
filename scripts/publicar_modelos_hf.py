#!/usr/bin/env python3
"""Publica en HuggingFace los módulos descargables declarados en el manifiesto.

Los pesos pesados no caben en el instalador y se descargan bajo demanda desde
`huggingface.co/srcacahuate/moldesign-models`. Este script es el que pone ahí lo
que el manifiesto promete, y —más importante— el que se niega a publicar algo que
no coincida con lo prometido.

Tres reglas, y las tres existen porque el fallo silencioso sería peor que no
publicar:

1. **El hash manda.** Antes de subir nada se recalcula el SHA-256 del archivo
   local y se compara con el del manifiesto. Publicar un peso que no coincide
   deja a cada usuario con una descarga que la aplicación rechaza al verificar,
   y sin forma de saber por qué.
2. **Nada se sube por accidente.** Sin `--subir` esto sólo informa. Publicar es
   irreversible en la práctica: la URL queda en manos de terceros en cuanto
   alguien la descarga.
3. **Lo que no está, se dice.** Un módulo cuyo archivo local no existe no se
   omite en silencio: se reporta, porque el manifiesto lo está prometiendo a los
   usuarios.

Uso
---
    set HF_TOKEN=hf_...              (token con permiso de escritura en el repo)
    python scripts/publicar_modelos_hf.py            # sólo informa
    python scripts/publicar_modelos_hf.py --subir    # publica de verdad

Se le puede indicar dónde están los archivos grandes si no viven en el árbol:

    python scripts/publicar_modelos_hf.py --raiz-archivos D:/moldesign-app
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MANIFIESTO = RAIZ / "launcher-manifest.json"
REPO = "srcacahuate/moldesign-models"
VERSION_EN_REPO = "v1.0.0"

#: Archivos pequeños que acompañan a un checkpoint. Viajan en el instalador,
#: pero publicarlos también hace que el módulo del repositorio sea completo por
#: sí mismo: quien clone el repo tiene todo lo que `from_pretrained` necesita.
COMPANEROS = {
    "esmfold-weights": (
        "esmfold/models/config.json",
        "esmfold/models/vocab.txt",
        "esmfold/models/tokenizer_config.json",
        "esmfold/models/special_tokens_map.json",
    ),
}


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloque)
    return h.hexdigest()


def ruta_local(modulo: dict, raices: list[Path]) -> Path | None:
    """Dónde está el archivo grande de este módulo, si está."""
    destino = (modulo.get("destination") or ".").strip("/")
    nombre = modulo.get("filename") or ""
    relativa = f"{destino}/{nombre}" if destino not in ("", ".") else nombre
    for raiz in raices:
        candidato = raiz / relativa
        if candidato.is_file():
            return candidato
    return None


def ruta_en_repo(modulo: dict) -> str:
    destino = (modulo.get("destination") or ".").strip("/")
    nombre = modulo.get("filename") or ""
    if destino in ("", "."):
        return f"{VERSION_EN_REPO}/{nombre}"
    return f"{VERSION_EN_REPO}/{destino}/{nombre}"


def main() -> int:
    # La consola de Windows viene en cp1252 y este informe lleva flechas y acentos.
    # Sin esto el script se cae imprimiendo, que es la peor forma de fallar: parece
    # un problema de la publicación y es de la terminal.
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subir", action="store_true",
                    help="publica de verdad; sin esto sólo informa")
    ap.add_argument("--raiz-archivos", action="append", default=[],
                    help="directorio extra donde buscar los archivos grandes")
    ap.add_argument("--repo", default=REPO)
    args = ap.parse_args()

    raices = [RAIZ] + [Path(r) for r in args.raiz_archivos]
    manifiesto = json.loads(MANIFIESTO.read_text(encoding="utf-8"))
    modulos = manifiesto.get("modules", [])

    try:
        from huggingface_hub import HfApi
    except ImportError:
        print("Falta huggingface_hub: pip install huggingface_hub", file=sys.stderr)
        return 2

    token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN")
    api = HfApi(token=token)

    try:
        existentes = {s.rfilename for s in api.model_info(args.repo, files_metadata=False).siblings}
    except Exception as exc:  # noqa: BLE001
        print(f"No se pudo leer {args.repo}: {exc}", file=sys.stderr)
        return 2

    por_subir: list[tuple[Path, str]] = []
    problemas: list[str] = []

    for modulo in modulos:
        mid = modulo.get("id", "?")

        # Sólo se publica lo que el manifiesto pide DESDE ESTE repositorio. El
        # GGUF de Qwen, por ejemplo, se descarga del repositorio oficial de Qwen:
        # copiarlo aquí duplicaría 1.1 GB, y una copia se queda atrás en cuanto
        # el original se corrige. Que un módulo venga de fuera no es un descuido,
        # es la procedencia correcta.
        urls = modulo.get("urls") or []
        if not any(f"/{args.repo}/" in u for u in urls):
            origen = urls[0].split("/resolve/")[0] if urls else "sin URL"
            print(f"[{mid}] se descarga de otro repositorio ({origen}); no se publica aquí")
            continue

        destino_repo = ruta_en_repo(modulo)
        local = ruta_local(modulo, raices)

        if local is None:
            estado = "YA ESTÁ EN EL REPO" if destino_repo in existentes else "FALTA EN TODAS PARTES"
            print(f"[{mid}] {estado} — no hay copia local en {[str(r) for r in raices]}")
            if destino_repo not in existentes:
                problemas.append(
                    f"{mid}: el manifiesto lo promete y no está ni en local ni en el repo"
                )
            continue

        esperado = (modulo.get("sha256") or "").lower()
        print(f"[{mid}] comprobando {local} ({local.stat().st_size:,} bytes)…")
        real = sha256(local)
        if esperado and real != esperado:
            problemas.append(
                f"{mid}: el SHA-256 local {real[:16]}… no coincide con el del "
                f"manifiesto {esperado[:16]}…"
            )
            continue

        if destino_repo in existentes:
            print(f"  ya publicado en {destino_repo}")
        else:
            por_subir.append((local, destino_repo))
            print(f"  pendiente de publicar → {destino_repo}")

        for companero in COMPANEROS.get(mid, ()):
            origen = None
            for raiz in raices:
                if (raiz / companero).is_file():
                    origen = raiz / companero
                    break
            destino_c = f"{VERSION_EN_REPO}/{companero}"
            if origen is None:
                problemas.append(f"{mid}: falta el archivo acompañante {companero}")
            elif destino_c in existentes:
                print(f"  acompañante ya publicado: {companero}")
            else:
                por_subir.append((origen, destino_c))
                print(f"  acompañante pendiente → {destino_c}")

    # El manifiesto se publica siempre que cambie: es la documentación de qué
    # ofrece cada versión. La aplicación NO lo lee de aquí —usa el empaquetado—,
    # así que esto no puede romper a un usuario instalado.
    por_subir.append((MANIFIESTO, "launcher-manifest.json"))
    por_subir.append((MANIFIESTO, f"{VERSION_EN_REPO}/launcher-manifest.json"))

    print("\n── Resumen ─────────────────────────────────────────")
    for origen, destino in por_subir:
        print(f"  subir  {origen.name:32s} → {destino}")
    for p in problemas:
        print(f"  PROBLEMA  {p}")

    if problemas:
        print("\nHay problemas declarados arriba. Se puede publicar igual, pero el "
              "manifiesto estaría prometiendo algo que no está.")

    if not args.subir:
        print("\nModo informe. Añade --subir para publicar.")
        return 0

    if not token:
        print("\nFalta HF_TOKEN con permiso de escritura. Sin token no se sube nada.",
              file=sys.stderr)
        return 2

    for origen, destino in por_subir:
        print(f"subiendo {origen.name} → {destino} …", flush=True)
        api.upload_file(
            path_or_fileobj=str(origen),
            path_in_repo=destino,
            repo_id=args.repo,
            commit_message=f"MolDesign: publicar {destino}",
        )
    print("Publicado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
