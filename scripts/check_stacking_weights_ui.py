#!/usr/bin/env python3
"""Los pesos que la interfaz muestra son los que el backend aplica.

═══════════════════════════════════════════════════════════════════════════
POR QUÉ EXISTE
═══════════════════════════════════════════════════════════════════════════

Auditoría del 2026-09-04. `frontend/lib/pipelineDefinitions.ts` declaraba una
calibración por familia y el backend aplicaba otra. Las SIETE familias
divergían — 16 diferencias:

    familia            componente   interfaz   backend
    ─────────────────  ───────────  ────────   ───────
    default            vina           0.30      0.20
    default            xgb            0.50      0.60
    gpcr               gnn            0.00      0.40
    gpcr               clgnn          0.40      0.00
    protease           vina           0.10      0.20
    protease           xgb            0.30      0.60
    protease           clgnn          0.60      0.20
    kinase             xgb            0.70      0.60
    kinase             clgnn          0.10      0.20
    nuclear_receptor   xgb            0.80      0.60
    nuclear_receptor   clgnn          0.00      0.20
    soluble_enzyme     vina           0.30      0.20
    soluble_enzyme     xgb            0.50      0.60
    metaloenzyme       vina           0.00      0.20
    metaloenzyme       xgb            0.00      0.60
    metaloenzyme       clgnn          1.00      0.20

La causa es estructural, no un descuido: hay TRES sitios que dicen cuánto pesa
cada modelo.

    1. `STACKING_WEIGHTS` en `backend/scoring/engine.py`
       — fallback, sólo se usa si el JSON no se puede leer.
    2. `rescoring/artifacts/stacking_weights.json`
       — LO QUE SE EJECUTA. Declara únicamente `default` y `gpcr`; todo lo
         demás cae a `default`.
    3. `frontend/lib/pipelineDefinitions.ts`
       — lo que se le enseña a quien usa el producto.

Es la misma forma que el §9.1 del ADR 75 describe para las metaloenzimas
—cuatro artefactos contando cuatro políticas distintas—, repetida para M4.

Este gate no unifica las tres fuentes: comprueba que la tercera coincida con la
segunda, que es la que decide el ranking. La primera sólo actúa si el artefacto
desaparece, y entonces la interfaz ya no describe la corrida por otro motivo.

Uso:

    python scripts/check_stacking_weights_ui.py --check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "backend"))

TABLA = RAIZ / "frontend" / "lib" / "pipelineDefinitions.ts"
REGISTRY = RAIZ / "backend" / "artifacts" / "sci_config_registry.json"
ESPEJO = RAIZ / "rescoring" / "artifacts" / "stacking_weights.json"
MANIFEST = RAIZ / "rescoring" / "artifacts" / "model-manifest.json"
MODELO_CLGNN = RAIZ / "rescoring" / "artifacts" / "gnn_v2_cl_best.pt"

#: Los cuatro componentes que el engine combina. `quantum`, `ums`, `molchamb` y
#: `mmgbsa` no entran en el stacking —son post-hoc o informativos— y su peso en
#: la interfaz debe ser 0.
COMPONENTES = ("vina", "xgb", "gnn", "clgnn")

#: Etapas que la interfaz muestra pero no participan en el ranking. Se exige
#: peso 0: un peso distinto de cero aquí afirmaría una contribución que el
#: engine no hace. El caso que lo motiva es UMS, que llegó a mostrarse con peso
#: 1.00 después de que el ADR 75 retirase su empujón aditivo de 0.06.
FUERA_DEL_STACKING = ("quantum", "ums", "molchamb", "mmgbsa")

_FAMILIA = re.compile(r"^  ([a-z_0-9]+): \{")
_ETAPA = re.compile(r'\{ id: "([a-z_0-9-]+)".*?weight: ([0-9.]+)')


def pesos_de_la_interfaz() -> dict[str, dict[str, float]]:
    texto = TABLA.read_text(encoding="utf-8")
    bloque = texto.split("export const PIPELINES_BY_FAMILY", 1)[1]
    bloque = bloque.split("export const FAMILY_LABELS", 1)[0]

    familias: dict[str, dict[str, float]] = {}
    actual: str | None = None
    for linea in bloque.splitlines():
        cabecera = _FAMILIA.match(linea)
        if cabecera:
            actual = cabecera.group(1)
            familias[actual] = {}
            continue
        etapa = _ETAPA.search(linea)
        if etapa and actual:
            familias[actual][etapa.group(1)] = float(etapa.group(2))
    return familias


def pesos_del_backend(familia: str) -> dict[str, float]:
    """La resolución EFECTIVA: la misma llamada que hace `evaluate()`."""
    from scoring.engine import _get_stacking_weights, _resolve_stacking_weights

    return _resolve_stacking_weights(_get_stacking_weights(familia))


def validar_contrato_canonico(familias: set[str]) -> list[str]:
    """Valida procedencia y las cuatro representaciones del contrato de release."""
    from scoring.sci_config_registry import ParameterCategory, SciConfigRegistry

    problemas: list[str] = []
    try:
        registry = SciConfigRegistry.load(REGISTRY)
        espejo = json.loads(ESPEJO.read_text(encoding="utf-8"))
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"contrato cientifico ilegible o invalido: {exc}"]

    models = manifest.get("models", {})
    candidates = models.values() if isinstance(models, dict) else models
    entry = next((x for x in candidates if isinstance(x, dict) and x.get("file") == MODELO_CLGNN.name), None)
    if entry is None:
        return ["model-manifest.json no declara gnn_v2_cl_best.pt"]

    sha_real = hashlib.sha256(MODELO_CLGNN.read_bytes()).hexdigest() if MODELO_CLGNN.is_file() else None
    registry_contract = json.loads(REGISTRY.read_text(encoding="utf-8")).get("contract", {})
    for origen, sha in (
        ("model-manifest", entry.get("sha256")),
        ("stacking_weights._contract", espejo.get("_contract", {}).get("clgnn_sha256")),
        ("SciConfigRegistry.contract", registry_contract.get("clgnn_sha256")),
    ):
        if sha != sha_real:
            problemas.append(f"{origen}: SHA CL-GNN {sha!r} != bytes distribuidos {sha_real!r}")

    exact_validated = entry.get("metrics", {}).get("external_metrics_for_exact_sha256") is not None
    if not exact_validated and "PENDING" not in str(entry.get("scientific_status")):
        problemas.append("CL-GNN no tiene validacion exacta y el manifiesto no lo marca PENDING")

    for family in sorted(familias | {"phosphodiesterase", "unknown"}):
        parameter = registry.get(f"stacking_{family}") or registry.get("stacking_default")
        if parameter is None or parameter.category != ParameterCategory.SCORING_WEIGHTS:
            problemas.append(f"stacking_{family}: parametro ausente o categoria incorrecta")
            continue
        value = parameter.current_value
        mirror = espejo.get(family, espejo.get("default"))
        if value != mirror:
            problemas.append(f"{family}: registry {value} != espejo {mirror}")
        if not exact_validated and float(value.get("clgnn", 0.0)) != 0.0:
            problemas.append(f"{family}: CL-GNN pesa >0 sin validacion del SHA exacto")
        if float(value.get("gnn", 0.0)) != 0.0:
            problemas.append(f"{family}: la GNN legacy deprecada pesa >0")
    return problemas


def comparar() -> list[str]:
    problemas: list[str] = []
    interfaz = pesos_de_la_interfaz()
    if not interfaz:
        return ["no se pudo leer ninguna familia de pipelineDefinitions.ts"]

    problemas.extend(validar_contrato_canonico(set(interfaz)))

    for familia, etapas in sorted(interfaz.items()):
        # `default` es la clave de la interfaz para «target no curado»; en el
        # backend esa consulta se hace con familia vacía.
        efectivos = pesos_del_backend("" if familia == "default" else familia)
        for componente in COMPONENTES:
            mostrado = etapas.get(componente)
            if mostrado is None:
                problemas.append(
                    f"{familia}: la interfaz no muestra la etapa «{componente}», "
                    "que sí participa en el stacking"
                )
                continue
            aplicado = round(efectivos[componente], 4)
            if abs(mostrado - aplicado) > 1e-6:
                problemas.append(
                    f"{familia} · {componente}: la interfaz muestra {mostrado:.2f} "
                    f"y el backend aplica {aplicado:.2f}"
                )
        for componente in FUERA_DEL_STACKING:
            mostrado = etapas.get(componente)
            if mostrado is not None and mostrado != 0.0:
                problemas.append(
                    f"{familia} · {componente}: peso {mostrado:.2f} en la interfaz. "
                    "Esta etapa no entra en el stacking del engine, así que "
                    "mostrarle un peso afirma una contribución al ranking que no "
                    "existe."
                )
    return problemas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.parse_args()

    problemas = comparar()
    if problemas:
        print(
            "ERROR: la interfaz declara pesos de stacking que el backend no "
            "aplica:\n  - " + "\n  - ".join(problemas)
            + "\n\nLa fuente canonica es "
            "`backend/artifacts/sci_config_registry.json`; el JSON de "
            "rescoring es un espejo. Actualiza registro e interfaz solo "
            "con evidencia sellada."
        )
        return 1

    familias = sorted(pesos_de_la_interfaz())
    print(
        f"Pesos del stacking verificados: {len(familias)} familias de la interfaz "
        f"coinciden con la resolución efectiva del backend ({', '.join(familias)})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
