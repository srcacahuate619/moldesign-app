"""Estructuras predichas: de dónde vienen y cuánta confianza tiene el sitio de unión.

Una estructura de AlphaFold, de Boltz o de Chai no es un cristal: cada residuo trae una confianza (pLDDT) y, donde
es baja, la posición de los átomos es una conjetura. Para un receptor propio MolDesign hace tres cosas:

* **detecta** si el archivo es una predicción por lo que el propio archivo declara (cabecera, método, métricas
  ModelCIF), nunca por el nombre;
* **lee el pLDDT por residuo con la convención verificada en un archivo real** de esa fuente y declara cuál es. Hoy
  sólo está verificada la de **AlphaFold DB** (``AF-P23975-F1-model_v6``, descargado el 2026-10-09 del EBI): el
  factor B del PDB y el ``B_iso_or_equiv`` del mmCIF son el pLDDT por residuo en escala 0–100, y coinciden con
  ``_ma_qa_metric_local``. De Boltz, Chai-1 y AlphaFold 3 no hay un archivo de salida real en sus repositorios
  oficiales: su documentación dice que Boltz guarda el pLDDT en [0, 1] y AlphaFold 3 por átomo en 0–100, pero no
  dónde queda en el CIF, así que **no se afirma** y el pLDDT sale «no disponible» con ese motivo;
* **mide el sitio**: de los residuos a ``MARGEN_SITIO_A`` o menos de la caja, cuántos tienen pLDDT < 70.

Lo que no se puede leer no se inventa: ``no_disponible`` lleva un código y Preparación lo explica.
"""

from __future__ import annotations

import math
from typing import Any

from services.targets.entrada_receptor import FORMATO_MMCIF, FORMATO_PDB

UMBRAL_REVISION = 70.0     # por debajo, AlphaFold DB llama «baja» a la confianza
UMBRAL_MUY_BAJO = 50.0
#: El mismo margen que usa la preparación para decir que algo está «junto al sitio»
#: (`services/docking/preparer.py::MARGEN_SITIO_A`; una prueba comprueba que coinciden).
MARGEN_SITIO_A = 6.0
MAX_RESIDUOS_LISTADOS = 12

REFERENCIA_AFDB = (
    "AF-P23975-F1-model_v6.pdb y .cif, descargados de alphafold.ebi.ac.uk el 2026-10-09: el factor B (PDB) y "
    "B_iso_or_equiv (mmCIF) son el pLDDT por residuo, escala 0–100, y coinciden con _ma_qa_metric_local"
)

#: Códigos de ``no_disponible``; Preparación los convierte en frases (ES/EN).
SIN_PLDDT_DECLARADO = "sin_plddt_declarado"
CONVENCION_SIN_VERIFICAR = "convencion_sin_verificar"
ESCALA_AMBIGUA = "escala_ambigua"
B_NO_COINCIDE = "factor_b_no_coincide"
FORMATO_SIN_FACTOR_B = "formato_sin_factor_b"
PDBQT_SIN_ORIGEN = "pdbqt_sin_origen"


# ── Lectura por formato ──────────────────────────────────────────────


def _clave(chain: str, numero: int | str, insercion: str = "") -> str:
    return f"{chain.strip() or 'A'}:{numero}{insercion.strip()}"


def _clave_de_linea(linea: str) -> str | None:
    try:
        numero = int(linea[22:26])
    except ValueError:
        return None
    return _clave(linea[21:22], numero, linea[26:27])


def _factor_b_por_residuo(texto_pdb: str) -> dict[str, float]:
    """Media del factor B de los átomos de cada residuo de proteína (en AlphaFold DB es el mismo en todos)."""
    acumulado: dict[str, list[float]] = {}
    for linea in texto_pdb.splitlines():
        if not linea.startswith("ATOM"):
            continue
        clave = _clave_de_linea(linea)
        if clave is None:
            continue
        try:
            acumulado.setdefault(clave, []).append(float(linea[60:66]))
        except ValueError:
            continue
    return {k: round(sum(v) / len(v), 2) for k, v in acumulado.items() if v}


def _metodo_y_titulo_pdb(texto: str) -> tuple[str | None, str]:
    metodo, titulo = None, []
    for linea in texto.splitlines():
        registro = linea[:6].strip()
        if registro == "EXPDTA":
            metodo = linea[10:].strip().upper() or metodo
        elif registro == "TITLE":
            titulo.append(linea[10:].strip().upper())
        elif registro in ("ATOM", "HETATM"):
            break
    return metodo, " ".join(titulo)


def _plddt_modelcif(texto: str, cadenas_pdb: dict[str, str] | None) -> dict[str, Any]:
    """Lo que el mmCIF declara: método, identidad, y el pLDDT local por residuo si lo trae (diccionario ModelCIF)."""
    import gemmi

    resultado: dict[str, Any] = {"metodo": None, "entry_id": None, "modelcif": False, "plddt": None, "factor_b_coincide": None}
    try:
        bloque = gemmi.cif.read_string(texto)[0]
    except (RuntimeError, ValueError, IndexError):
        return resultado
    resultado["metodo"] = (gemmi.cif.as_string(bloque.find_value("_exptl.method")).upper()
                           if bloque.find_value("_exptl.method") else None)
    entry = bloque.find_value("_entry.id")
    resultado["entry_id"] = gemmi.cif.as_string(entry) if entry else None
    resultado["modelcif"] = bool(bloque.find_values("_ma_model_list.model_id")) or bool(
        bloque.find_values("_ma_qa_metric.id"))
    nombres = {gemmi.cif.as_string(fila[0]): gemmi.cif.as_string(fila[1]).lower()
               for fila in bloque.find("_ma_qa_metric.", ["id", "name"])}
    ids_plddt = {i for i, n in nombres.items() if n == "plddt"}
    filas = bloque.find("_ma_qa_metric_local.", ["label_asym_id", "label_seq_id", "metric_id", "metric_value"])
    local: dict[tuple[str, int], float] = {}
    for fila in filas:
        if gemmi.cif.as_string(fila[2]) not in ids_plddt:
            continue
        try:
            local[(gemmi.cif.as_string(fila[0]), int(gemmi.cif.as_string(fila[1])))] = float(gemmi.cif.as_string(fila[3]))
        except ValueError:
            continue
    if not local:
        return resultado
    estructura = gemmi.make_structure_from_block(bloque)
    mapa: dict[str, float] = {}
    iguales = total = 0
    for cadena in estructura[0]:
        letra = (cadenas_pdb or {}).get(cadena.name, cadena.name)
        for residuo in cadena:
            valor = local.get((residuo.subchain, residuo.label_seq)) if residuo.label_seq is not None else None
            if valor is None:
                continue
            mapa[_clave(letra, residuo.seqid.num, residuo.seqid.icode if residuo.seqid.icode != " " else "")] = valor
            total += 1
            iguales += all(abs(a.b_iso - valor) <= 0.01 for a in residuo)
    resultado["plddt"] = mapa or None
    resultado["factor_b_coincide"] = (iguales == total) if total else None
    return resultado


# ── Análisis de la subida ────────────────────────────────────────────


def _resumen(mapa: dict[str, float]) -> dict[str, Any]:
    valores = list(mapa.values())
    return {
        "residuos": len(valores),
        "media": round(sum(valores) / len(valores), 2),
        "minimo": min(valores), "maximo": max(valores),
        "bajo_70": sum(1 for v in valores if v < UMBRAL_REVISION),
        "bajo_50": sum(1 for v in valores if v < UMBRAL_MUY_BAJO),
    }


def _no_disponible(es_predicha: bool | None, codigo: str, **extra: Any) -> dict[str, Any]:
    return {"es_predicha": es_predicha, "fuente": None, "evidencia": [], "metodo_declarado": None,
            "convencion": None, "plddt": None, "no_disponible": codigo, **extra}


def sin_estructura_de_origen() -> dict[str, Any]:
    """Un PDBQT no conserva el factor B ni el método: no se puede saber si el receptor es una predicción."""
    return _no_disponible(None, PDBQT_SIN_ORIGEN)


def analizar(formato: str, texto_original: str, texto_pdb: str,
             cadenas_pdb: dict[str, str] | None = None) -> tuple[dict[str, Any], dict[str, float] | None]:
    """El resumen de lo que el archivo dice de sí mismo y el pLDDT por residuo (``"A:176"`` → valor), si se pudo leer.

    ``texto_original`` es el archivo tal como llegó (PDB o mmCIF) y ``texto_pdb`` su PDB clásico ya convertido, que
    es sobre el que se prepara; ``cadenas_pdb`` traduce las cadenas del mmCIF a las letras del PDB.
    """
    if formato not in (FORMATO_PDB, FORMATO_MMCIF):
        # Un PQR (o cualquier otro) ya perdió el factor B y el método al escribirse.
        return _no_disponible(None, FORMATO_SIN_FACTOR_B, formato=formato), None

    evidencia: list[str] = []
    metodo: str | None
    es_afdb = False
    plddt: dict[str, float] | None = None
    donde: str | None = None
    modelcif = False
    b_coincide: bool | None = None

    if formato == FORMATO_PDB:
        metodo, titulo = _metodo_y_titulo_pdb(texto_original)
        if "ALPHAFOLD MONOMER" in titulo:
            es_afdb = True
            evidencia.append("TITLE: «ALPHAFOLD MONOMER …»")
            plddt, donde = _factor_b_por_residuo(texto_pdb), "factor_b"
        predicha = es_afdb or (metodo is not None and "THEORETICAL" in metodo)
        if metodo is not None and "THEORETICAL" in metodo:
            evidencia.append(f"EXPDTA: {metodo}")
    else:
        lectura = _plddt_modelcif(texto_original, cadenas_pdb)
        metodo, modelcif, b_coincide = lectura["metodo"], lectura["modelcif"], lectura["factor_b_coincide"]
        es_afdb = bool(lectura["entry_id"] and lectura["entry_id"].upper().startswith("AF-") and lectura["plddt"])
        if es_afdb:
            evidencia.append(f"_entry.id: {lectura['entry_id']} · pLDDT en _ma_qa_metric_local")
        elif lectura["plddt"]:
            evidencia.append("pLDDT en _ma_qa_metric_local (ModelCIF)")
        if modelcif and not es_afdb:
            evidencia.append("ModelCIF (_ma_model_list o _ma_qa_metric)")
        if metodo is not None and "THEORETICAL" in metodo:
            evidencia.append(f"_exptl.method: {metodo}")
        plddt, donde = lectura["plddt"], "ma_qa_metric_local"
        predicha = es_afdb or modelcif or (metodo is not None and "THEORETICAL" in metodo)

    base = {"es_predicha": predicha, "fuente": None, "evidencia": evidencia,
            "metodo_declarado": None if predicha else metodo, "convencion": None, "plddt": None,
            "no_disponible": None}
    if not predicha:
        return base, None

    if es_afdb:
        base["fuente"] = "alphafold_db"
        if formato == FORMATO_MMCIF and b_coincide is False:
            # El archivo dice dos cosas distintas: no se elige una a ojo.
            return {**base, "no_disponible": B_NO_COINCIDE}, None
        base["convencion"] = {"plddt_en": donde, "escala": "0-100", "verificada": True, "referencia": REFERENCIA_AFDB}
    elif plddt:
        # ModelCIF de otra fuente: el archivo declara el pLDDT, pero esa fuente no está verificada con un archivo real.
        base["fuente"] = "modelcif"
        base["convencion"] = {"plddt_en": donde, "escala": "0-100" if max(plddt.values()) > 1.0 else None,
                              "verificada": False, "referencia": None}
        if max(plddt.values()) <= 1.0:
            return {**base, "no_disponible": ESCALA_AMBIGUA}, None
    else:
        base["fuente"] = "desconocida"
        return {**base, "no_disponible": SIN_PLDDT_DECLARADO if modelcif else CONVENCION_SIN_VERIFICAR}, None

    if not plddt:
        return {**base, "no_disponible": SIN_PLDDT_DECLARADO}, None
    base["plddt"] = _resumen(plddt)
    return base, plddt


# ── El sitio ─────────────────────────────────────────────────────────


def _distancia_a_caja(pos: tuple[float, float, float], center: tuple[float, float, float],
                      size: tuple[float, float, float]) -> float:
    """Distancia euclídea de un punto a la caja; 0 si está dentro (la misma que mide la preparación)."""
    return math.dist(
        tuple(max(abs(pos[i] - float(center[i])) - float(size[i]) / 2, 0.0) for i in range(3)),
        (0.0, 0.0, 0.0),
    )


def confianza_del_sitio(mapa: dict[str, float], texto: str, center: tuple[float, float, float],
                        size: tuple[float, float, float], margen: float = MARGEN_SITIO_A) -> dict[str, Any]:
    """pLDDT de los residuos con algún átomo a ``margen`` Å o menos de la caja (acepta PDB y PDBQT)."""
    cerca: dict[str, tuple[float, str]] = {}
    for linea in texto.splitlines():
        if not linea.startswith("ATOM"):
            continue
        clave = _clave_de_linea(linea)
        if clave is None:
            continue
        try:
            pos = (float(linea[30:38]), float(linea[38:46]), float(linea[46:54]))
        except ValueError:
            continue
        distancia = _distancia_a_caja(pos, center, size)
        if distancia <= margen and (clave not in cerca or distancia < cerca[clave][0]):
            cerca[clave] = (distancia, linea[17:20].strip())
    con_dato = {k: v for k, v in cerca.items() if k in mapa}
    valores = [mapa[k] for k in con_dato]
    bajos = sorted(((mapa[k], k, nombre, distancia) for k, (distancia, nombre) in con_dato.items()
                    if mapa[k] < UMBRAL_REVISION))
    return {
        "margen_A": margen,
        "residuos": len(cerca),
        "con_plddt": len(con_dato),
        "sin_plddt": len(cerca) - len(con_dato),
        "minimo": min(valores) if valores else None,
        "media": round(sum(valores) / len(valores), 2) if valores else None,
        "n_bajo_70": len(bajos),
        "n_bajo_50": sum(1 for v, *_ in bajos if v < UMBRAL_MUY_BAJO),
        "bajo_70": [{"residuo": k, "nombre": nombre, "plddt": v, "distancia_A": round(d, 3)}
                    for v, k, nombre, d in bajos[:MAX_RESIDUOS_LISTADOS]],
    }
