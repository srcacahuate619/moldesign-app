#!/usr/bin/env python3
"""Emite el manifiesto de M5-Zn DESDE el módulo de perfiles.

Gates §10.1 y §10.2 de `docs/75_DECISION_CIENTIFICA_M5_ZN_V1.md`: los tres
perfiles tienen que vivir en un manifiesto legible por producción, y cada uno
contener fórmula, constantes y hashes.

# Por qué se genera y no se escribe a mano

Un manifiesto escrito a mano es una segunda fuente de verdad. En cuanto existen
dos, divergen — y este proyecto ya tiene el precedente: `model-manifest.json`,
`stacking_weights.json`, el manuscrito y `scoring/engine.py` describían cuatro
políticas distintas de metaloenzimas, que es el §9.1 del ADR.

Aquí la única fuente es `services/pipeline/protocols/m5/zinc.py`. El JSON es un
derivado determinista, y `--check` falla si el commiteado no coincide con lo que
el módulo produce hoy. Cambiar un peso sin regenerar rompe el gate; regenerar
deja el cambio visible en el diff.

# Qué se hashea, y por qué eso

Además de los checkpoints, se hashea la tabla de SMARTS de los warheads. El §2
del ADR dice que modificar patrones, normalización o escala crea una versión de
protocolo nueva: sin ese hash, alguien podría afinar un SMARTS y el manifiesto
seguiría diciendo lo mismo mientras el score cambia.

# Uso

    python scripts/generate_m5_manifest.py            # escribe
    python scripts/generate_m5_manifest.py --check    # falla si difiere
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "backend"))

from services.pipeline.protocols.m5.zinc import PERFILES  # noqa: E402
from scoring.ums import WARHEAD_KEYS, _WARHEAD_SMARTS  # noqa: E402

MANIFEST_VERSION = 1
DESTINO = RAIZ / "backend" / "services" / "pipeline" / "protocols" / "m5" / "m5_zn_manifest.json"

#: La fórmula del UMS autorizado, transcrita del §2 del ADR. Va en el
#: manifiesto como texto para que se pueda leer sin abrir el código.
FORMULA_UMS = "0.0 if n_warheads == 0 else 0.85 + 0.10 * min(n_warheads / 3, 1)"


def _sha256_archivo(ruta: Path) -> str | None:
    if not ruta.is_file():
        return None
    digest = hashlib.sha256()
    with ruta.open("rb") as handle:
        for bloque in iter(lambda: handle.read(65536), b""):
            digest.update(bloque)
    return digest.hexdigest()


def _sha256_smarts() -> str:
    """Hash de la tabla de warheads, en forma canónica y ordenada.

    Se serializa con `sort_keys` para que el hash no dependa del orden en que
    Python conserve el diccionario.
    """
    canonico = json.dumps(
        {clave: sorted(_WARHEAD_SMARTS[clave]) for clave in sorted(_WARHEAD_SMARTS)},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def construir() -> dict:
    """El manifiesto, derivado del módulo de perfiles y de nada más."""
    perfiles = {}
    for pdb, perfil in sorted(PERFILES.items()):
        ruta_checkpoint = RAIZ / perfil.checkpoint
        actual = _sha256_archivo(ruta_checkpoint)
        if actual is not None and actual != perfil.checkpoint_sha256:
            raise SystemExit(
                f"El checkpoint de {pdb} no es el declarado.\n"
                f"    declarado: {perfil.checkpoint_sha256}\n"
                f"    en disco : {actual}\n"
                f"    archivo  : {ruta_checkpoint}\n"
                "Alguien cambio el checkpoint sin actualizar el perfil. El "
                "manifiesto no se escribe: diria una cosa y el score seria otra."
            )
        perfiles[pdb] = {
            "protocol_id": perfil.protocol_id,
            "target": perfil.diana,
            "pdb_id": perfil.pdb_id,
            "formula": perfil.formula,
            "weights": {
                "vina_norm": perfil.peso_vina,
                "xgboost": perfil.peso_xgb,
                "gnn_d": perfil.peso_gnn_d,
                "ums_warhead": perfil.peso_ums,
            },
            # Los que tienen peso distinto de cero. Si falta uno,
            # `m5_score = null` y no se renormaliza (§5 del ADR).
            "required_components": list(perfil.componentes_requeridos),
            "normalizer": {
                "vina_reference_max": perfil.vina_reference_max,
                "formula": "min(abs(vina_kcal_mol) / vina_reference_max, 1.0)",
                "nota": (
                    "Congelada. Los benchmarks usaban el máximo de la cohorte "
                    "cargada, lo que hacía que el score de una molécula "
                    "dependiera de sus vecinas."
                ),
            },
            # Sólo la DECLARACIÓN. `sha256_actual` y `presente` describían el
            # disco de quien generaba el manifiesto —los checkpoints de
            # benchmark están en .gitignore—, así que el artefacto versionado
            # decía `presente: true` y ningún clon podía reproducirlo: la
            # prueba que lo compara fallaba en cualquier máquina que no fuera
            # la del mantenedor. La comprobación no se pierde: se hace ARRIBA,
            # al generar, donde el checkpoint sí está.
            "checkpoint": {
                "path": perfil.checkpoint,
                "sha256_declarado": perfil.checkpoint_sha256,
            },
            # La cuarentena viaja EN EL MANIFIESTO, que es lo que producción
            # lee para saber qué puede afirmar. Un perfil cuestionado que sólo
            # estuviera cuestionado en un documento seguiría presentándose como
            # bueno en el artefacto que la build comprueba.
            "quarantine": {
                "en_revision": perfil.en_cuarentena,
                "motivo": perfil.cuarentena,
                "corrigendum": (
                    "docs/77_CORRIGENDUM_SITIO_DEL_BENCHMARK_M5_ZN.md"
                    if perfil.en_cuarentena else None
                ),
            },
            "reference_auc": {
                "m4": perfil.auc_m4_referencia,
                "m5": perfil.auc_m5_referencia,
                "delta": round(perfil.auc_m5_referencia - perfil.auc_m4_referencia, 10),
                # La procedencia de las dos NO es la misma, y decir que ambas
                # salen del reporte DeLong seria falso desde V2.
                "fuente_m4": "data/molchamb_loto/delong_paired_report.json",
                "fuente_m5": (
                    "medida de nuevo sobre el mismo checkpoint con los patrones "
                    "de warhead V2; el reporte DeLong contiene la de V1"
                ),
                "nota": (
                    "Reproducible, NO validada: dos de los tres benchmarks siguen "
                    "en cuarentena por el sitio y estas AUC se miden sobre esos "
                    "mismos datos."
                ),
            },
        }

    return {
        "manifest_version": MANIFEST_VERSION,
        "adr": "docs/75_DECISION_CIENTIFICA_M5_ZN_V1.md",
        "protocol_family": "M5_ZN",
        "generado_por": "scripts/generate_m5_manifest.py",
        "fuente_unica": "backend/services/pipeline/protocols/m5/zinc.py",
        "ums": {
            "variant": "smarts_only",
            "formula": FORMULA_UMS,
            "warhead_keys": list(WARHEAD_KEYS),
            "warhead_smarts_sha256": _sha256_smarts(),
            "nota": (
                "NO es el UMS histórico con donantes y MolChamb. Cambiar un "
                "patrón cambia este hash y obliga a una versión de protocolo "
                "nueva (§2 del ADR)."
            ),
        },
        "benchmark_en_revision": {
            "estado": "REVIEW_INVALID_BENCHMARK_SITE",
            "corrigendum": "docs/77_CORRIGENDUM_SITIO_DEL_BENCHMARK_M5_ZN.md",
            "instrumento": "scripts/auditar_sitio_m5.py",
            "nota": (
                "MMP9/1GKC esta en revision por sitio de benchmark incorrecto; ACE/1O86 esta en revision porque la pose top-1 no coordina el zinc y la procedencia del benchmark esta incompleta. CA2/3DC3 queda no evaluado por ausencia de GNN-D. El score solo se muestra como evidencia auditable y hoy NINGUN perfil produce VALIDATED."
            ),
        },
        "fuera_de_perfil": {
            "otra_estructura": "REVIEW_OUT_OF_VALIDATED_STRUCTURE",
            "otra_diana_de_zinc": "REVIEW_OUT_OF_VALIDATED_TARGET",
            "otro_metal": "BLOCKED_PROTOCOL_NOT_AVAILABLE",
            "componente_ausente": "NOT_EVALUATED_MISSING_COMPONENT",
            "nota": "En los cuatro casos `m5_score = null`. No se heredan pesos.",
        },
        "profiles": perfiles,
    }


def serializar(manifiesto: dict) -> str:
    """Forma canónica: claves ordenadas y salto final.

    Determinista a propósito: `--check` compara bytes, así que cualquier
    variación de formato sería un falso positivo.
    """
    return json.dumps(manifiesto, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="No escribe: falla si el manifiesto commiteado difiere del generado.",
    )
    args = parser.parse_args()

    esperado = serializar(construir())

    if args.check:
        if not DESTINO.is_file():
            print(f"ERROR: falta {DESTINO.relative_to(RAIZ)}. Ejecuta el script sin --check.")
            return 1
        actual = DESTINO.read_text(encoding="utf-8")
        if actual != esperado:
            print(
                f"ERROR: {DESTINO.relative_to(RAIZ)} no coincide con lo que produce "
                "el módulo de perfiles. Alguien cambió un peso, una constante o un "
                "SMARTS sin regenerar. Ejecuta:\n"
                "    python scripts/generate_m5_manifest.py"
            )
            return 1
        print(f"Manifiesto M5-Zn verificado: {DESTINO.relative_to(RAIZ)}")
        return 0

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(esperado, encoding="utf-8")
    print(f"Manifiesto M5-Zn escrito: {DESTINO.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
