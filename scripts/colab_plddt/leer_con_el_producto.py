"""Qué dice HOY el producto de cada estructura que generó el cuaderno de Colab: la línea base del cambio.

Pasa cada ``.cif`` y ``.pdb`` de los resultados por ``services.targets.prediccion.analizar``, el mismo código que lee
una subida de receptor propio, y escribe una fila por archivo: si lo cree una predicción, de qué fuente, dónde lee el
pLDDT y por qué no lo da si no lo da. No cambia nada; sólo mide.

    python-embed\\python.exe -I scripts\\colab_plddt\\leer_con_el_producto.py <carpeta de resultados> [--json salida.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "backend"))

from services.targets import prediccion as P  # noqa: E402
from services.targets.conversion_mmcif import mmcif_a_pdb  # noqa: E402
from services.targets.normalizar_pdb import normalizar_pdb  # noqa: E402

#: Lo que el cuaderno escribe y no son estructuras del modelo (alineamientos, plantillas…).
CARPETAS_IGNORADAS = {"msa", "msas", "processed", "entradas", "licencias"}


def leer(ruta: Path) -> dict:
    texto = ruta.read_text(encoding="utf-8", errors="replace")
    try:
        if ruta.suffix.lower() == ".cif":
            conversion = mmcif_a_pdb(texto, ruta.name)
            info, mapa = P.analizar("mmcif", texto, conversion.pdb,
                                    {c["original"]: c["pdb"] for c in conversion.informe["cadenas"]})
        else:
            info, mapa = P.analizar("pdb", texto, normalizar_pdb(texto)[0])
    except Exception as exc:  # que el producto no lea el archivo también es un resultado
        return {"error": f"{type(exc).__name__}: {str(exc)[:300]}"}
    convencion = info.get("convencion") or {}
    return {"es_predicha": info.get("es_predicha"), "fuente": info.get("fuente"),
            "no_disponible": info.get("no_disponible"), "evidencia": info.get("evidencia"),
            "metodo_declarado": info.get("metodo_declarado"), "plddt_en": convencion.get("plddt_en"),
            "escala": convencion.get("escala"), "verificada": convencion.get("verificada"),
            "residuos_con_plddt": len(mapa) if mapa else 0}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("carpeta", type=Path)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()
    archivos = sorted(p for p in list(args.carpeta.rglob("*.cif")) + list(args.carpeta.rglob("*.pdb"))
                      if not CARPETAS_IGNORADAS & {parte.lower() for parte in p.relative_to(args.carpeta).parts[:-1]}
                      and "__fallido_" not in str(p))
    if not archivos:
        print(f"No hay .cif ni .pdb en {args.carpeta}")
        return 1
    filas = []
    for ruta in archivos:
        fila = {"archivo": str(ruta.relative_to(args.carpeta)).replace("\\", "/"), **leer(ruta)}
        filas.append(fila)
        if "error" in fila:
            print(f"{fila['archivo']}: ERROR {fila['error']}")
        else:
            print(f"{fila['archivo']}: predicha={fila['es_predicha']} fuente={fila['fuente']} "
                  f"no_disponible={fila['no_disponible']} plddt_en={fila['plddt_en']} escala={fila['escala']} "
                  f"verificada={fila['verificada']} residuos={fila['residuos_con_plddt']}")
    if args.json:
        args.json.write_text(json.dumps(filas, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
