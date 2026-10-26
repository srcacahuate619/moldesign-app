#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""posebusters_veredicto.py — validez fisica que exige la bateria entera (SCI-B-016).

POR QUE EXISTE, Y POR QUE NO SE CORRIGIO `posebusters_metrica.py`
-----------------------------------------------------------------
`posebusters_metrica.evaluar_pose` emite `pb_valid_fisica = len(fallan) == 0` sobre los
checks **booleanos** que haya. Tres respuestas de PoseBusters salian aprobadas sin que
nadie midiera nada (auditoria cientifica, SCI-B-016):

  * un check en NaN -PoseBusters lo devuelve cuando no puede evaluar: sin conformero,
    UFF sin parametros, receptor que no carga- se descartaba en silencio;
  * un `*_loaded` en False no contaba;
  * una fila sin ningun check fisico daba True.

Aquel modulo es **codigo productor sellado**: nueve manifiestos de
`scripts/artifacts_science/` (MF-33-PB, MF-33-H-COR, MF-33-MIN, MF-33-TOP1 y sus
prerregistros) guardan su SHA-256, y `validar_sellos.py --check` falla si cambia un byte.
Corregirlo en sitio rompia la procedencia de lo ya medido, igual que reescribir
`redock_pdbbind.py`. Por eso se conserva intacto y la regla nueva vive aqui.

**Un experimento nuevo usa `evaluar_pose` de este modulo, no el de aquel.** Lo comprueba
`scripts/tests/test_posebusters_metrica_cobertura.py`: un script que importe
`posebusters_metrica` tiene que ser un productor ya sellado.

La regla
--------
| Fila de PoseBusters                    | `pb_valid_fisica`                            |
|----------------------------------------|----------------------------------------------|
| algun `*_loaded` no es True            | None, motivo `carga_fallida:...`             |
| ningun check fisico                    | None, motivo `sin_checks_fisicos`            |
| algun check fisico en False            | False (un fallo medido es un fallo)          |
| algun check fisico sin evaluar (NaN)   | None, motivo `bateria_incompleta`            |
| todos evaluados y en True              | True                                         |

El check de RMSD sigue aparte (`pb_rmsd_ok`), por la misma razon que en el modulo viejo.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import posebusters_metrica as _pm

NO_SON_CHECKS = _pm.NO_SON_CHECKS
CHECK_RMSD_PREFIJO = _pm.CHECK_RMSD_PREFIJO


def _booleano(valor: Any) -> Optional[bool]:
    """True/False si es un booleano de verdad (Python o numpy); None en otro caso (NaN...)."""
    if isinstance(valor, bool):
        return valor
    tipo = type(valor)
    if tipo.__module__ == "numpy" and tipo.__name__ in ("bool_", "bool"):
        return bool(valor)
    return None


def veredicto_de_la_fila(fila: Dict[str, Any]) -> Dict[str, Any]:
    """`pb_valid_fisica` de una fila de PoseBusters, con la regla del docstring."""
    carga_fallida = sorted(str(k) for k, v in fila.items()
                           if str(k) in NO_SON_CHECKS and _booleano(v) is not True)
    checks: Dict[str, bool] = {}
    sin_evaluar: List[str] = []
    for k, v in fila.items():
        clave = str(k)
        if clave in NO_SON_CHECKS:
            continue
        b = _booleano(v)
        if b is None:
            sin_evaluar.append(clave)
        else:
            checks[clave] = b

    rmsd_keys = [k for k in checks if k.startswith(CHECK_RMSD_PREFIJO)]
    fisicos = {k: v for k, v in checks.items() if k not in rmsd_keys}
    fis_sin_evaluar = sorted(k for k in sin_evaluar if not k.startswith(CHECK_RMSD_PREFIJO))
    fallan_fis = sorted(k for k, v in fisicos.items() if not v)
    pb_rmsd_ok = (all(checks[k] for k in rmsd_keys) if rmsd_keys else None)
    base = {"pb_rmsd_ok": pb_rmsd_ok,
            "n_checks_fisicos": len(fisicos),
            "n_fallan": len(fallan_fis),
            "checks_que_fallan": fallan_fis,
            "checks_sin_evaluar": fis_sin_evaluar,
            "checks": checks}

    if carga_fallida:
        return {**base, "pb_valid_fisica": None, "motivo": "carga_fallida:" + ",".join(carga_fallida)}
    if not fisicos and not fis_sin_evaluar:
        return {**base, "pb_valid_fisica": None, "motivo": "sin_checks_fisicos"}
    if fallan_fis:
        return {**base, "pb_valid_fisica": False}
    if fis_sin_evaluar:
        return {**base, "pb_valid_fisica": None, "motivo": "bateria_incompleta"}
    return {**base, "pb_valid_fisica": True}


def evaluar_pose(pose_mol, crystal_mh, proteina: Path,
                 config: str = "redock") -> Dict[str, Any]:
    """Corre PoseBusters sobre una pose con la regla de cobertura de este modulo.

    `pb_valid_fisica` es None -y NO False- si algo impidio evaluar, igual que antes; lo que
    cambia es que una bateria incompleta tambien es «algo impidio evaluar».
    """
    if not _pm.disponible():
        return {"pb_valid_fisica": None, "motivo": "posebusters_no_instalado"}
    try:
        df = _pm._buster(config).bust([pose_mol], crystal_mh, Path(proteina))
    except Exception as ex:                                    # noqa: BLE001
        return {"pb_valid_fisica": None, "motivo": f"{type(ex).__name__}:{str(ex)[-120:]}"}
    if df is None or len(df) == 0:
        return {"pb_valid_fisica": None, "motivo": "sin_resultado"}
    return veredicto_de_la_fila(df.iloc[0].to_dict())
