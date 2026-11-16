"""Estructuras predichas: de dónde vienen y cuánta confianza tiene el sitio de unión.

Una estructura de AlphaFold, de Boltz o de Chai no es un cristal: cada residuo trae una confianza (pLDDT) y, donde
es baja, la posición de los átomos es una conjetura. Para un receptor propio MolDesign hace tres cosas:

* **detecta** si el archivo es una predicción por lo que el propio archivo declara (cabecera, método, métricas
  ModelCIF), nunca por el nombre;
* **lee el pLDDT por residuo** y declara de dónde lo sacó y si la convención de esa fuente está verificada con un
  archivo real:

  - **AlphaFold DB, verificada** (``AF-P23975-F1-model_v6``, descargado el 2026-10-09 del EBI): el factor B del PDB
    y el ``B_iso_or_equiv`` del mmCIF son el pLDDT por residuo en escala 0–100, y coinciden con
    ``_ma_qa_metric_local``;
  - **cualquier otro ModelCIF** que declare el pLDDT: se lee ``_ma_qa_metric_local``, con la fuente «modelcif» y la
    convención «sin verificar», porque el archivo no siempre dice quién lo generó. Si todos los valores son ≤ 1, la
    escala es ambigua y no se lee;
  - **un archivo que se declara modelo** (método THEORETICAL) pero no es de AlphaFold DB ni trae el pLDDT en
    ModelCIF: su factor B podría ser otra cosa, así que **no se afirma** y el pLDDT sale «no disponible» con ese
    motivo;
  - **un archivo que no dice de dónde viene** (ni método ni marca de predicción, como el PDB de Boltz, que no trae
    ninguna cabecera): manda lo que declaró quien lo subió (``fuente_declarada``). La interfaz se lo pregunta al
    elegir el archivo (``hay_que_preguntar_la_fuente``). Si declara Boltz-2, el factor B se lee como pLDDT sólo si
    el archivo es como los que escribe Boltz 2.2.1; si declara otra herramienta, se registra y no se lee; si no lo
    sabe, o la subida no lo dice, no consta si es una predicción;
* **mide el sitio**: de los residuos a ``MARGEN_SITIO_A`` o menos de la caja, cuántos tienen pLDDT < 70.

Lo que no se puede leer no se inventa: ``no_disponible`` lleva un código y Preparación lo explica.

Lo que escriben Boltz-2 y Chai-1 se comprobó con archivos reales el 2026-11-14/15 (acta en
``docs/auditorias/convencion-plddt-boltz-chai-2026-11-15/``; recortes en ``tests/data/receptores_propios/``):

* **Boltz 2.2.1.** En mmCIF, ``_ma_qa_metric_local`` y el factor B son el pLDDT del modelo ×100, uno por residuo (el
  [0, 1] de su documentación es el del ``.npz``). Aquí se lee bien, como ModelCIF sin verificar, porque el archivo no
  dice que es de Boltz. Su PDB no trae ninguna cabecera: el factor B es el mismo pLDDT, con 2 decimales, y sólo se lee
  si quien lo sube declara que es de Boltz-2.
* **Chai-1 0.6.1.** El factor B va por átomo, y el pLDDT por residuo del modelo es su media. ``_ma_qa_metric_local``,
  que es lo que se lee aquí, guarda el valor del Cα, que se aparta hasta 19 puntos. Con él, la regla del 70 ve menos
  residuos bajos que el modelo (9 frente a 21 en CDK2 sin ligando). Su mmCIF firma ``_struct.title`` con
  ``FIRMA_CHAI1``: con esa firma, Preparación nombra Chai-1 como «declarado por el archivo», y dice que el valor es el
  del Cα sólo si en ese mismo archivo coincide con el factor B del Cα de cada residuo. La regla lee el Cα: decisión del propietario del 2026-11-15 (D-01 de la investigación de 1.0.4), porque las dos
  lecturas dieron el mismo aviso en los casos medidos y el Cα es el campo que declara ModelCIF.
* De AlphaFold 3 no se ha generado ningún archivo.
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

REFERENCIA_BOLTZ = (
    "Boltz 2.2.1, ejecutado en Colab el 2026-11-14 (acta docs/auditorias/convencion-plddt-boltz-chai-2026-11-15): en "
    "el PDB, el factor B es el pLDDT del modelo ×100, el mismo en todos los átomos de cada residuo, con 2 decimales"
)

#: La firma que escribe el exportador de chai_lab 0.6.1 en ``_struct.title`` (``chai_lab/data/io/cif_utils.py``,
#: v0.6.1, L215–235). Es lo que el archivo dice de sí mismo: cualquiera puede escribirla y no dice la versión, así que
#: nombra la herramienta como «declarada por el archivo» y la convención sigue sin verificar (D-01 de la investigación
#: de 1.0.4, ``docs/auditorias/investigacion-1.0.4/D01.md``).
FIRMA_CHAI1 = "Chai-1 predicted structure"
FUENTE_ARCHIVO_CHAI1 = "chai1"
REFERENCIA_CHAI1 = (
    "chai_lab 0.6.1, ejecutado en Colab el 2026-11-14 (acta docs/auditorias/convencion-plddt-boltz-chai-2026-11-15): "
    "_ma_qa_metric_local guarda el pLDDT del Cα de cada residuo, no la media por residuo que da el modelo"
)

#: Lo que declara quien sube un archivo que no dice de dónde viene. Sólo cuenta cuando el archivo calla: si declara
#: su método o trae marcas de predicción, manda el archivo y la declaración queda registrada como no usada.
FUENTE_EXPERIMENTAL = "experimental"
FUENTE_BOLTZ = "boltz"
FUENTE_OTRA = "otra"
FUENTE_NO_SE = "no_se"
FUENTES_DECLARABLES = (FUENTE_EXPERIMENTAL, FUENTE_BOLTZ, FUENTE_OTRA, FUENTE_NO_SE)
MAX_HERRAMIENTA = 80

#: Códigos de ``no_disponible``; Preparación los convierte en frases (ES/EN).
SIN_PLDDT_DECLARADO = "sin_plddt_declarado"
CONVENCION_SIN_VERIFICAR = "convencion_sin_verificar"
ESCALA_AMBIGUA = "escala_ambigua"
B_NO_COINCIDE = "factor_b_no_coincide"
FORMATO_SIN_FACTOR_B = "formato_sin_factor_b"
PDBQT_SIN_ORIGEN = "pdbqt_sin_origen"
FUENTE_SIN_DECLARAR = "fuente_sin_declarar"
HERRAMIENTA_SIN_VERIFICAR = "herramienta_sin_verificar"
DECLARACION_NO_COINCIDE = "declaracion_no_coincide"


# ── Lectura por formato ──────────────────────────────────────────────


def _clave(chain: str, numero: int | str, insercion: str = "") -> str:
    return f"{chain.strip() or 'A'}:{numero}{insercion.strip()}"


def _clave_de_linea(linea: str) -> str | None:
    try:
        numero = int(linea[22:26])
    except ValueError:
        return None
    return _clave(linea[21:22], numero, linea[26:27])


def _factor_b_por_atomo(texto_pdb: str) -> dict[str, list[float]]:
    """El factor B de cada átomo de proteína (``ATOM``), agrupado por residuo."""
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
    return {k: v for k, v in acumulado.items() if v}


def _factor_b_por_residuo(texto_pdb: str) -> dict[str, float]:
    """Media del factor B de los átomos de cada residuo de proteína (en AlphaFold DB es el mismo en todos)."""
    return {k: round(sum(v) / len(v), 2) for k, v in _factor_b_por_atomo(texto_pdb).items()}


def _es_como_un_pdb_de_boltz(por_atomo: dict[str, list[float]]) -> bool:
    """Lo que escribe Boltz 2.2.1 en PDB: el mismo pLDDT en todos los átomos de cada residuo, entre 0 y 100.

    Un archivo que no lo cumple no es lo que se comprobó, aunque quien lo sube diga que es de Boltz: con valores
    distintos dentro de un residuo no se sabría cuál usar, y con todos ≤ 1 la escala sería otra.
    """
    if not por_atomo:
        return False
    valores = [b for v in por_atomo.values() for b in v]
    return (all(max(v) - min(v) <= 0.01 for v in por_atomo.values())
            and min(valores) >= 0.0 and max(valores) <= 100.0 and max(valores) > 1.0)


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

    resultado: dict[str, Any] = {"metodo": None, "entry_id": None, "titulo": None, "modelcif": False, "plddt": None,
                                 "factor_b_coincide": None, "local_es_el_calfa": None}
    try:
        bloque = gemmi.cif.read_string(texto)[0]
    except (RuntimeError, ValueError, IndexError):
        return resultado
    resultado["metodo"] = (gemmi.cif.as_string(bloque.find_value("_exptl.method")).upper()
                           if bloque.find_value("_exptl.method") else None)
    entry = bloque.find_value("_entry.id")
    resultado["entry_id"] = gemmi.cif.as_string(entry) if entry else None
    titulo = bloque.find_value("_struct.title")
    resultado["titulo"] = gemmi.cif.as_string(titulo).strip() if titulo else None
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
    iguales = total = calfa = 0
    for cadena in estructura[0]:
        letra = (cadenas_pdb or {}).get(cadena.name, cadena.name)
        for residuo in cadena:
            valor = local.get((residuo.subchain, residuo.label_seq)) if residuo.label_seq is not None else None
            if valor is None:
                continue
            mapa[_clave(letra, residuo.seqid.num, residuo.seqid.icode if residuo.seqid.icode != " " else "")] = valor
            total += 1
            iguales += all(abs(a.b_iso - valor) <= 0.01 for a in residuo)
            ca = residuo.find_atom("CA", "*")
            calfa += ca is not None and abs(ca.b_iso - valor) <= 0.01
    resultado["plddt"] = mapa or None
    resultado["factor_b_coincide"] = (iguales == total) if total else None
    #: Si el valor local de cada residuo es el factor B de su Cα en este mismo archivo: lo que hace falta para decir
    #: que el archivo guarda el Cα, y no sólo que se parece a lo que escribió Chai-1 0.6.1.
    resultado["local_es_el_calfa"] = (calfa == total) if total else None
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


def normalizar_declaracion(fuente: str | None, herramienta: str | None = None) -> dict[str, Any] | None:
    """La declaración de quien sube el archivo, validada: ``None`` si no declaró nada.

    El nombre de la herramienta sólo se guarda con ``otra``, sin caracteres de control y con ``MAX_HERRAMIENTA``
    caracteres como mucho. Una fuente desconocida es un ``ValueError``: la API la rechaza antes de llegar aquí.
    """
    if fuente is None or not str(fuente).strip():
        return None
    fuente = str(fuente).strip().lower()
    if fuente not in FUENTES_DECLARABLES:
        raise ValueError(f"fuente declarada desconocida: {fuente!r}")
    nombre = None
    if fuente == FUENTE_OTRA and herramienta:
        nombre = " ".join("".join(c if c.isprintable() else " " for c in str(herramienta)).split())
        nombre = nombre[:MAX_HERRAMIENTA].strip() or None
    return {"fuente": fuente, "herramienta": nombre}


def hay_que_preguntar_la_fuente(formato: str, texto_original: str) -> bool:
    """``True`` si el archivo no dice si es experimental o predicho: ni declara su método ni trae marcas de predicción.

    Es exactamente el caso en que ``analizar`` usa la declaración de quien lo sube. Un PQR o un PDBQT ya perdieron el
    factor B, así que preguntar no serviría de nada.
    """
    if formato == FORMATO_PDB:
        metodo, titulo = _metodo_y_titulo_pdb(texto_original)
        return metodo is None and "ALPHAFOLD MONOMER" not in titulo
    if formato == FORMATO_MMCIF:
        lectura = _plddt_modelcif(texto_original, None)
        es_afdb = bool(lectura["entry_id"] and lectura["entry_id"].upper().startswith("AF-") and lectura["plddt"])
        return lectura["metodo"] is None and not lectura["modelcif"] and not es_afdb
    return False


def _segun_lo_declarado(formato: str, texto_pdb: str,
                        declaracion: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, float] | None]:
    """El archivo no dice de dónde viene: manda lo que declaró quien lo subió, y queda registrado como declaración."""
    fuente = (declaracion or {}).get("fuente")
    registro = {"declaracion": {**declaracion, "usada": True}} if declaracion else {}
    if fuente == FUENTE_EXPERIMENTAL:
        return {"es_predicha": False, "fuente": None, "evidencia": [], "metodo_declarado": None, "convencion": None,
                "plddt": None, "no_disponible": None, **registro}, None
    if fuente in (None, FUENTE_NO_SE):
        return _no_disponible(None, FUENTE_SIN_DECLARAR, **registro), None
    if fuente == FUENTE_OTRA:
        return _no_disponible(True, HERRAMIENTA_SIN_VERIFICAR, fuente="declarada", **registro), None
    # Boltz-2: sólo se comprobó su PDB (sus mmCIF son ModelCIF y no llegan aquí).
    por_atomo = _factor_b_por_atomo(texto_pdb) if formato == FORMATO_PDB else {}
    if not _es_como_un_pdb_de_boltz(por_atomo):
        return _no_disponible(True, DECLARACION_NO_COINCIDE, fuente=FUENTE_BOLTZ, **registro), None
    mapa = _factor_b_por_residuo(texto_pdb)
    return {
        "es_predicha": True, "fuente": FUENTE_BOLTZ,
        "evidencia": ["fuente declarada por quien subió el archivo: Boltz-2",
                      "factor B igual en todos los átomos de cada residuo, entre 0 y 100"],
        "metodo_declarado": None,
        "convencion": {"plddt_en": "factor_b", "escala": "0-100", "verificada": True, "referencia": REFERENCIA_BOLTZ,
                       "fuente_declarada": True},
        "plddt": _resumen(mapa), "no_disponible": None, **registro,
    }, mapa


def analizar(formato: str, texto_original: str, texto_pdb: str,
             cadenas_pdb: dict[str, str] | None = None, *, fuente_declarada: str | None = None,
             herramienta_declarada: str | None = None) -> tuple[dict[str, Any], dict[str, float] | None]:
    """El resumen de lo que el archivo dice de sí mismo y el pLDDT por residuo (``"A:176"`` → valor), si se pudo leer.

    ``texto_original`` es el archivo tal como llegó (PDB o mmCIF) y ``texto_pdb`` su PDB clásico ya convertido, que
    es sobre el que se prepara; ``cadenas_pdb`` traduce las cadenas del mmCIF a las letras del PDB.
    ``fuente_declarada`` (una de ``FUENTES_DECLARABLES``) y ``herramienta_declarada`` son lo que dijo quien lo subió;
    sólo cuentan si el archivo no dice de dónde viene.
    """
    declaracion = normalizar_declaracion(fuente_declarada, herramienta_declarada)
    if formato not in (FORMATO_PDB, FORMATO_MMCIF):
        # Un PQR (o cualquier otro) ya perdió el factor B y el método al escribirse.
        return _no_disponible(None, FORMATO_SIN_FACTOR_B, formato=formato,
                              **({"declaracion": {**declaracion, "usada": False}} if declaracion else {})), None

    evidencia: list[str] = []
    metodo: str | None
    es_afdb = False
    plddt: dict[str, float] | None = None
    donde: str | None = None
    modelcif = False
    b_coincide: bool | None = None
    es_chai = False

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
            es_chai = lectura["titulo"] == FIRMA_CHAI1
            if es_chai:
                evidencia.append(f"_struct.title: «{FIRMA_CHAI1}»")
        if modelcif and not es_afdb:
            evidencia.append("ModelCIF (_ma_model_list o _ma_qa_metric)")
        if metodo is not None and "THEORETICAL" in metodo:
            evidencia.append(f"_exptl.method: {metodo}")
        plddt, donde = lectura["plddt"], "ma_qa_metric_local"
        predicha = es_afdb or modelcif or (metodo is not None and "THEORETICAL" in metodo)

    if not predicha and metodo is None:
        # Ni método ni marcas de predicción (el PDB de Boltz no trae cabecera): el archivo no dice de dónde viene.
        return _segun_lo_declarado(formato, texto_pdb, declaracion)

    base = {"es_predicha": predicha, "fuente": None, "evidencia": evidencia,
            "metodo_declarado": None if predicha else metodo, "convencion": None, "plddt": None,
            "no_disponible": None, **({"declaracion": {**declaracion, "usada": False}} if declaracion else {})}
    if not predicha:
        return base, None

    if es_afdb:
        base["fuente"] = "alphafold_db"
        if formato == FORMATO_MMCIF and b_coincide is False:
            # El archivo dice dos cosas distintas: no se elige una a ojo.
            return {**base, "no_disponible": B_NO_COINCIDE}, None
        base["convencion"] = {"plddt_en": donde, "escala": "0-100", "verificada": True, "referencia": REFERENCIA_AFDB}
    elif plddt:
        # ModelCIF de otra fuente: el archivo declara el pLDDT, pero no siempre dice quién lo generó, así que no se sabe
        # si su convención está verificada. Si trae la firma de Chai-1, se nombra como declarada por el archivo y se
        # dice que el valor es el del Cα (lo comprobado con Chai-1 0.6.1); la firma no da la versión, así que la
        # convención sigue sin verificar y la regla del 70 lee lo mismo que antes.
        # «Es el Cα» se dice sólo si este archivo lo cumple: la firma es un autorreporte y cualquiera puede escribirla
        # (contraejemplo del seguimiento de la réplica, 2026-11-15: un valor local cambiado a mano seguía rotulado Cα).
        # Y sólo si el factor B varía dentro del residuo (se conserva la condición: no cambia ningún estado). El texto ya
        # no afirma que el Cα «no es la media»: que el B varíe no lo prueba, porque valores por encima y por debajo
        # pueden compensarse (revisión final, D-01, 2026-11-15). Dice sólo lo que se comprobó: el valor local coincide
        # con el B de cada Cα.
        es_calfa = es_chai and lectura["local_es_el_calfa"] is True and lectura["factor_b_coincide"] is False
        base["fuente"] = FUENTE_ARCHIVO_CHAI1 if es_chai else "modelcif"
        base["convencion"] = {"plddt_en": donde, "escala": "0-100" if max(plddt.values()) > 1.0 else None,
                              "verificada": False, "referencia": REFERENCIA_CHAI1 if es_calfa else None,
                              **({"lectura": "calfa"} if es_calfa else {})}
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
