#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""posebusters_metrica.py — validez fisica de la pose como metrica secundaria.

Modulo reutilizable, **100% CPU**, sin dependencia de GPU. Pensado para que cualquier
experimento futuro del programa reporte, junto al `rmsd_pose_pocket`, si la pose es
**fisicamente valida**.

Por que
-------
El programa mide una sola cosa: `rmsd_pose_pocket <= 2.0 A`. PoseBusters
(Buttenschoen, Morris & Deane, *Chem. Sci.* 15, 3130, 2024) demostro sobre 308 complejos
que el RMSD por si solo **deja pasar poses fisicamente imposibles** —enlaces estirados,
estereoquimica rota, anillos no planos, solapamiento con el receptor—, y que ese es el modo
de fallo dominante de los metodos de aprendizaje profundo. Un acierto de RMSD sobre una pose
invalida no es un acierto.

La misma referencia da el contexto que justifica la restriccion de producto de MolDesign:
con validez fisica exigida, **AutoDock Vina 58% y Gold 55% contra DiffDock 12%**. Los
metodos clasicos de CPU no son el plan B.

Que se usa, y por que el paquete y no una reimplementacion
-----------------------------------------------------------
Se usa el paquete `posebusters` tal cual. **PB-valid es un termino definido y citable**; una
reimplementacion propia daria «checks parecidos a PB», que es mas debil y puede divergir en
detalles. El paquete es RDKit puro: no anade dependencia de GPU.

Los 22 checks se agrupan en tres familias, segun la referencia:

  * **quimica**: sanitizacion, InChI, conectividad, radicales, formula, enlaces,
    estereoquimica de dobles enlaces y quiralidad tetraedrica;
  * **intramolecular**: longitudes y angulos de enlace, choque esterico interno, planaridad
    de anillos aromaticos y de dobles enlaces, no-planaridad de los no aromaticos, y
    **energia interna** por UFF;
  * **intermolecular**: distancia maxima al receptor, distancia minima y solapamiento de
    volumen contra proteina, cofactores organicos, cofactores inorganicos **y aguas**.

Esa ultima familia es de interes directo para `REC-09` y `REC-11`: PoseBusters **ya trata
las aguas como parte del receptor** y penaliza el solapamiento con ellas.

El puente con el formato del programa
-------------------------------------
Las poses del programa son PDBQT y PoseBusters quiere moleculas RDKit. No se convierte de
formato: se **reusa el mapeo de indices sellado** de `molflex`.

    mh = Chem.AddHs(crystal, addCoords=True)   # la molecula que Meeko preparo
    pose = copia de mh con las coordenadas del PDBQT puestas por indice

`Chem.AddHs` **anade los hidrogenos DESPUES** de los atomos originales, asi que los indices
de los pesados coinciden entre `crystal` y `mh`. Es la misma invariante de la que ya depende
`molflex.rmsd_pose_pocket`, que filtra por pesados de `crystal` y busca en el mapa.

Decisiones declaradas
---------------------
1. **`mol_cond` es `<pid>_protein.pdb`, la estructura original**, no `rec.pdbqt`. La pregunta
   de validez fisica es contra la estructura real, no contra el receptor preparado. Como el
   original **conserva las aguas**, los checks de agua se aplican de verdad.
2. **`pb_valid_fisica` = todos los checks booleanos en True**, excluyendo los `*_loaded`
   -estado de carga, no propiedades de la pose- y excluyendo el check de RMSD.
3. Si la molecula no se puede cargar o el mapeo falla, se devuelve `pb_valid_fisica = None`
   y el motivo. **`None` no es `False`**: no se cuenta como pose invalida.
4. **La validez fisica se separa del RMSD.** El config `redock` incluye un check de RMSD
   entre sus booleanos; se reporta aparte como `pb_rmsd_ok` y NO entra en
   `pb_valid_fisica`, porque el programa ya mide su propio RMSD con `rmsd_pose_pocket` y
   mezclarlos convertiria la metrica secundaria en una copia ruidosa de la primaria.

AVISO DE INTEGRACION, importante para experimentos futuros
-----------------------------------------------------------
Los runners actuales del programa **borran las poses** tras calcular el RMSD
(`salida.unlink()` en `run_mf29emp_optimo_global.py`, `run_mf33ext_cobertura_flexible.py`,
`run_rec11_aguas_denovo.py` y otros). Sin la pose no hay validez fisica que medir.

Para que esta metrica entre en un experimento nuevo hay dos vias:

  * **conservar** el PDBQT de salida, y llamar a `evaluar_pose` en el mismo bucle; o
  * llamar a `evaluar_pose` **antes** de borrar, que es de coste despreciable frente al
    docking y no cambia el artefacto de salida.

El material historico **si esta en disco**: `data/molflex_train_v2/<pid>/<pid>/conf*.out.pdbqt`
conserva las poses del protocolo congelado, asi que la linea base se puede medir sin recomputo.

DONDE ESTA INSTALADO HOY
------------------------
`posebusters` esta instalado **en la maquina local** (0.6.5), no en la imagen
`moldesign-lab` del servidor. `disponible()` permite degradar sin romper: un experimento que
corra en el contenedor devolvera `pb_valid_fisica = None` con motivo
`posebusters_no_instalado`, y **None no es False**.

Anadirlo a `docker/Dockerfile.lab` exige reconstruir la imagen, y eso **no debe hacerse con
experimentos corriendo sobre ella**. Mientras tanto la via valida es evaluar en local sobre
las poses descargadas, que es lo que este modulo hace sin coste apreciable.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Los `*_loaded` son estado de carga, no propiedades de la pose.
NO_SON_CHECKS = {"mol_pred_loaded", "mol_true_loaded", "mol_cond_loaded"}

# El config `redock` de PoseBusters incluye un check de RMSD <= 2 A entre sus booleanos.
# Se SEPARA de la validez fisica a proposito: el programa ya mide su propio RMSD con
# `rmsd_pose_pocket` -sin alineamiento, en el marco del pocket- y mezclarlos convertiria la
# metrica secundaria en una copia ruidosa de la primaria. `pb_valid_fisica` excluye este
# check; `pb_rmsd_ok` lo reporta aparte, sin usarlo para nada.
CHECK_RMSD_PREFIJO = "rmsd_"

_BUSTER = None


def _buster(config: str = "redock"):
    """PoseBusters se instancia una vez por proceso: cargarlo es lo caro."""
    global _BUSTER
    if _BUSTER is None:
        from posebusters import PoseBusters
        _BUSTER = PoseBusters(config=config)
    return _BUSTER


def disponible() -> bool:
    """True si el paquete esta instalado. Permite degradar sin romper."""
    try:
        import posebusters  # noqa: F401
        return True
    except ImportError:
        return False


def mol_con_hidrogenos(crystal):
    """La molecula que Meeko preparo: el cristal con hidrogenos y sus coordenadas."""
    from rdkit import Chem
    return Chem.AddHs(crystal, addCoords=True)


def pose_a_mol(mh, coords_por_mol: Dict[int, Tuple[float, float, float]]):
    """Copia de `mh` con las coordenadas de la pose puestas por indice de atomo.

    `coords_por_mol` es la salida de `molflex.coords_pose_a_por_mol`, cuyos indices se
    refieren a esta misma molecula con hidrogenos.
    """
    from rdkit import Chem
    pose = Chem.Mol(mh)
    conf = pose.GetConformer()
    for idx, (x, y, z) in coords_por_mol.items():
        if idx < pose.GetNumAtoms():
            conf.SetAtomPosition(int(idx), (float(x), float(y), float(z)))
    return pose


def evaluar_pose(pose_mol, crystal_mh, proteina: Path,
                 config: str = "redock") -> Dict[str, Any]:
    """Corre PoseBusters sobre una pose. Devuelve los checks, `pb_valid_fisica` y `pb_rmsd_ok`.

    `pb_valid_fisica` es None -y NO False- si algo impidio evaluar.
    """
    if not disponible():
        return {"pb_valid_fisica": None, "motivo": "posebusters_no_instalado"}
    try:
        df = _buster(config).bust([pose_mol], crystal_mh, Path(proteina))
    except Exception as ex:
        return {"pb_valid_fisica": None, "motivo": f"{type(ex).__name__}:{str(ex)[-120:]}"}
    if df is None or len(df) == 0:
        return {"pb_valid_fisica": None, "motivo": "sin_resultado"}

    fila = df.iloc[0].to_dict()
    checks: Dict[str, bool] = {}
    for k, v in fila.items():
        clave = str(k)
        if clave in NO_SON_CHECKS:
            continue
        if isinstance(v, bool):
            checks[clave] = bool(v)
        else:
            try:
                import numpy as np
                if isinstance(v, np.bool_):
                    checks[clave] = bool(v)
            except Exception:
                pass
    if not checks:
        return {"pb_valid_fisica": None, "motivo": "sin_checks_booleanos"}

    # separar el check de RMSD del resto: ver CHECK_RMSD_PREFIJO
    rmsd_keys = [k for k in checks if k.startswith(CHECK_RMSD_PREFIJO)]
    fisicos = {k: v for k, v in checks.items() if k not in rmsd_keys}
    fallan_fis = sorted(k for k, v in fisicos.items() if not v)
    pb_rmsd_ok = (all(checks[k] for k in rmsd_keys) if rmsd_keys else None)

    return {"pb_valid_fisica": len(fallan_fis) == 0,
            "pb_rmsd_ok": pb_rmsd_ok,
            "n_checks_fisicos": len(fisicos),
            "n_fallan": len(fallan_fis),
            "checks_que_fallan": fallan_fis,
            "checks": checks}


def evaluar_pdbqt(pid: str, pdbqt_texto: str, ws: Path,
                  crystal=None, s2m: Optional[Dict[int, int]] = None,
                  solo_top1: bool = True) -> List[Dict[str, Any]]:
    """Evalua las poses de un PDBQT de salida de Vina, reusando el mapeo de molflex.

    Devuelve una lista de dicts, uno por modelo evaluado. Con `solo_top1`, solo el primero
    -que es el de mejor score dentro de esa corrida-.
    """
    import molflex as mf

    w = ws / "data" / "molflex_train_v2" / pid / pid
    if crystal is None:
        crystal = mf.leer_ligando(ws / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf")
    if crystal is None:
        return [{"pb_valid_fisica": None, "motivo": "SDF_ILEGIBLE"}]
    if s2m is None:
        ruta = w / "index_map.json"
        if not ruta.exists():
            return [{"pb_valid_fisica": None, "motivo": "SIN_INDEX_MAP"}]
        s2m = {int(s): int(m) for s, m in json.loads(ruta.read_text(encoding="utf-8"))}

    proteina = ws / "data" / "pdbbind" / pid / f"{pid}_protein.pdb"
    if not proteina.exists():
        return [{"pb_valid_fisica": None, "motivo": "SIN_PROTEINA_ORIGINAL"}]

    mh = mol_con_hidrogenos(crystal)
    salidas: List[Dict[str, Any]] = []
    modelos = mf.parsear_out_vina(pdbqt_texto)
    for i, (score, atomos) in enumerate(modelos):
        coords = mf.coords_pose_a_por_mol(atomos, s2m)
        if not coords:
            salidas.append({"modelo": i, "pb_valid_fisica": None, "motivo": "SIN_MAPEO"})
        else:
            r = evaluar_pose(pose_a_mol(mh, coords), mh, proteina)
            r["modelo"] = i
            r["score"] = score
            r["rmsd_pose_pocket"] = mf.rmsd_pose_pocket(crystal, coords)
            salidas.append(r)
        if solo_top1:
            break
    return salidas


def resumen(filas: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Agrega una lista de evaluaciones: tasa de PB-valid y que checks fallan mas."""
    from collections import Counter
    evaluadas = [f for f in filas if f.get("pb_valid_fisica") is not None]
    validas = [f for f in evaluadas if f["pb_valid_fisica"]]
    fallos = Counter()
    for f in evaluadas:
        for c in f.get("checks_que_fallan", []):
            fallos[c] += 1
    motivos = Counter(f.get("motivo") for f in filas if f.get("pb_valid_fisica") is None)
    return {"n_total": len(filas), "n_evaluadas": len(evaluadas),
            "n_no_evaluables": len(filas) - len(evaluadas),
            "motivos_no_evaluable": dict(motivos),
            "n_pb_valid_fisica": len(validas),
            "tasa_pb_valid_fisica": round(len(validas) / len(evaluadas), 4) if evaluadas else None,
            "checks_que_mas_fallan": dict(fallos.most_common())}
