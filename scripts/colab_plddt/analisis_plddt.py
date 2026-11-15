"""Dónde guarda Boltz o Chai-1 el pLDDT en su archivo, comparado con lo que devuelve el propio modelo.

Por qué existe: ``backend/services/targets/prediccion.py`` sólo lee el pLDDT de una fuente cuya convención se haya
verificado con un archivo real. Hoy sólo AlphaFold DB lo está; Boltz y Chai-1 salen «no disponible» porque nadie tenía
un archivo suyo. El cuaderno ``convencion_plddt_boltz_chai.ipynb`` genera esos archivos en Colab y este módulo los
compara, campo a campo, con la salida numérica del modelo (Boltz: ``plddt_*.npz``; Chai-1: el tensor ``plddt`` que
devuelve ``run_inference``).

Criterio, fijado antes de ejecutar nada. Una convención queda **verificada** para un grupo (herramienta, formato) si:

* el grupo tiene al menos ``MINIMO_DE_ESTRUCTURAS`` estructuras terminadas, y
* en **todas** ellas un mismo campo del archivo reproduce el pLDDT del modelo, residuo a residuo (o átomo a átomo),
  con **una única escala** (×1, ×100 o ×0,01) y una diferencia máxima no mayor que el redondeo con que el archivo
  escribe el número (medio dígito del último decimal escrito).

Una sola estructura que no cumpla deja el grupo sin verificar. Lo que no termina (memoria, bf16) se registra y no
cuenta ni a favor ni en contra. La correlación con AlphaFold DB es un control de sentido, no parte del criterio.

Sólo usa la biblioteca estándar, numpy y gemmi: corre igual en Colab y en el ``python-embed`` del producto.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable

import numpy as np

MINIMO_DE_ESTRUCTURAS = 2
ESCALAS = (1.0, 100.0, 0.01)
#: Categorías del mmCIF que dicen de dónde viene el archivo (la detección del producto se apoya en ellas).
CATEGORIAS_DE_PROCEDENCIA = (
    "_entry.", "_exptl.", "_struct.", "_software.", "_audit_conform.", "_audit_author.", "_ma_model_list.",
    "_ma_qa_metric.", "_ma_qa_metric_global.", "_ma_data.", "_ma_protocol_step.", "_ma_software_group.",
    "_ma_target_entity.", "_entity.", "_struct_asym.", "_pdbx_database_status.",
)
MAX_FILAS_POR_CATEGORIA = 25
MAX_LINEAS_DE_CABECERA_PDB = 60


# ── Utilidades ───────────────────────────────────────────────────────


def sha256(ruta: Path | str) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _decimales(texto: str) -> int:
    texto = texto.strip()
    if "e" in texto.lower() or "." not in texto:
        return 0
    return len(texto.split(".", 1)[1])


def _flotante(texto: str) -> float | None:
    try:
        valor = float(texto)
    except (TypeError, ValueError):
        return None
    return valor if math.isfinite(valor) else None


def _rangos(valores: np.ndarray) -> np.ndarray:
    """Rangos con empates promediados (para la ρ de Spearman sin depender de scipy)."""
    orden = np.argsort(valores, kind="mergesort")
    rangos = np.empty(len(valores), dtype=float)
    ordenados = valores[orden]
    i = 0
    while i < len(valores):
        j = i
        while j + 1 < len(valores) and ordenados[j + 1] == ordenados[i]:
            j += 1
        rangos[orden[i:j + 1]] = (i + j) / 2.0
        i = j + 1
    return rangos


def spearman(a: Iterable[float], b: Iterable[float]) -> float | None:
    # Redondeo antes de ordenar: la media de átomos idénticos puede diferir en un ulp y romper un empate.
    x, y = np.round(np.asarray(list(a), dtype=float), 6), np.round(np.asarray(list(b), dtype=float), 6)
    if len(x) != len(y) or len(x) < 3:
        return None
    rx, ry = _rangos(x), _rangos(y)
    if rx.std() == 0 or ry.std() == 0:
        return None
    return float(np.corrcoef(rx, ry)[0, 1])


# ── Lectura del archivo ──────────────────────────────────────────────


def _es_hidrogeno(elemento: str, nombre: str) -> bool:
    elemento = (elemento or "").strip().upper()
    if elemento:
        return elemento in ("H", "D")
    return nombre.strip().upper().startswith("H")


def _agrupar_residuos(atomos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Residuos en el orden del archivo, con los factores B de sus átomos pesados."""
    residuos: list[dict[str, Any]] = []
    indice: dict[tuple, int] = {}
    for atomo in atomos:
        clave = atomo["residuo"]
        if clave not in indice:
            indice[clave] = len(residuos)
            residuos.append({"clave": clave, "nombre": atomo["comp"], "proteina": atomo["proteina"],
                             "cadena": atomo["cadena"], "label_seq": atomo.get("label_seq"),
                             "numero": atomo["numero"], "b": [], "b_ca": None})
        residuo = residuos[indice[clave]]
        residuo["b"].append(atomo["b"])
        if atomo["nombre"] == "CA" and residuo["b_ca"] is None:
            residuo["b_ca"] = atomo["b"]
    for residuo in residuos:
        residuo["b_media"] = float(np.mean(residuo["b"]))
        residuo["b_dispersion"] = float(max(residuo["b"]) - min(residuo["b"]))
    return residuos


def _valor_de_categoria(bloque, categoria: str) -> dict[str, list[str]]:
    import gemmi

    crudo = bloque.get_mmcif_category(categoria, raw=True)
    return {tag: [gemmi.cif.as_string(v) if v is not None else "?" for v in valores[:MAX_FILAS_POR_CATEGORIA]]
            for tag, valores in crudo.items()}


def leer_mmcif(ruta: Path | str) -> dict[str, Any]:
    """Lo que declara un mmCIF (procedencia, métricas ModelCIF) y el factor B de cada átomo, en el orden del archivo."""
    import gemmi

    bloque = gemmi.cif.read(str(ruta)).sole_block()
    categorias = sorted(bloque.get_mmcif_category_names())
    procedencia = {c: _valor_de_categoria(bloque, c) for c in CATEGORIAS_DE_PROCEDENCIA if c in categorias}

    # Qué cadenas son polímero, según el propio archivo (si lo declara).
    tipo_de_entidad = {gemmi.cif.as_string(f[0]): gemmi.cif.as_string(f[1]).lower()
                       for f in bloque.find("_entity.", ["id", "type"])}
    asym_polimero = {gemmi.cif.as_string(f[0]) for f in bloque.find("_struct_asym.", ["id", "entity_id"])
                     if tipo_de_entidad.get(gemmi.cif.as_string(f[1])) == "polymer"}
    criterio_polimero = "_entity.type" if asym_polimero else "group_PDB"

    tabla = bloque.find("_atom_site.", ["group_PDB", "label_atom_id", "label_comp_id", "label_asym_id",
                                         "?label_seq_id", "?auth_seq_id", "?auth_asym_id", "?type_symbol",
                                         "B_iso_or_equiv", "?pdbx_PDB_model_num", "?pdbx_PDB_ins_code"])
    atomos: list[dict[str, Any]] = []
    decimales_b = 0
    hidrogenos = 0
    primer_modelo = None
    for fila in tabla:
        texto = [gemmi.cif.as_string(fila[i]) if fila.has(i) else "" for i in range(len(fila))]
        modelo = texto[9] or "1"
        primer_modelo = primer_modelo or modelo
        if modelo != primer_modelo:
            continue
        if _es_hidrogeno(texto[7], texto[1]):
            hidrogenos += 1
            continue
        b = _flotante(texto[8])
        if b is None:
            continue
        decimales_b = max(decimales_b, _decimales(fila.str(8)))
        asym = texto[3]
        proteina = (asym in asym_polimero) if asym_polimero else texto[0].upper() == "ATOM"
        label_seq = int(texto[4]) if texto[4] not in ("", ".", "?") and texto[4].lstrip("-").isdigit() else None
        numero = texto[5] or texto[4]
        atomos.append({"nombre": texto[1], "comp": texto[2], "cadena": texto[6] or asym, "asym": asym,
                       "label_seq": label_seq, "numero": numero, "b": b, "proteina": proteina,
                       "residuo": (asym, label_seq if label_seq is not None else numero, texto[2], texto[10])})

    # Métricas ModelCIF: nombres y valores locales por métrica.
    metricas = [{"id": gemmi.cif.as_string(f[0]), "nombre": gemmi.cif.as_string(f[1]),
                 "tipo": gemmi.cif.as_string(f[2]) if f.has(2) else None,
                 "modo": gemmi.cif.as_string(f[3]) if f.has(3) else None}
                for f in bloque.find("_ma_qa_metric.", ["id", "name", "?type", "?mode"])]
    locales: dict[str, dict[tuple[str, int], float]] = {}
    decimales_local: dict[str, int] = {}
    for f in bloque.find("_ma_qa_metric_local.", ["label_asym_id", "label_seq_id", "metric_id", "metric_value"]):
        metrica = gemmi.cif.as_string(f[2])
        valor = _flotante(gemmi.cif.as_string(f[3]))
        seq = gemmi.cif.as_string(f[1])
        if valor is None or not seq.lstrip("-").isdigit():
            continue
        locales.setdefault(metrica, {})[(gemmi.cif.as_string(f[0]), int(seq))] = valor
        decimales_local[metrica] = max(decimales_local.get(metrica, 0), _decimales(f.str(3)))
    globales = [{"metrica": gemmi.cif.as_string(f[0]), "valor": gemmi.cif.as_string(f[1])}
                for f in bloque.find("_ma_qa_metric_global.", ["metric_id", "metric_value"])]

    return {"formato": "mmcif", "categorias": categorias, "procedencia": procedencia,
            "criterio_polimero": criterio_polimero, "atomos": atomos, "residuos": _agrupar_residuos(atomos),
            "decimales_b": decimales_b, "hidrogenos_omitidos": hidrogenos, "metricas": metricas,
            "locales": locales, "decimales_local": decimales_local, "globales": globales}


def leer_pdb(ruta: Path | str) -> dict[str, Any]:
    """La cabecera de un PDB clásico y el factor B de cada átomo pesado del primer modelo."""
    cabecera: list[str] = []
    atomos: list[dict[str, Any]] = []
    decimales_b = 0
    hidrogenos = 0
    en_atomos = False
    for linea in Path(ruta).read_text(encoding="utf-8", errors="replace").splitlines():
        registro = linea[:6].strip()
        if registro == "ENDMDL":
            break
        if registro not in ("ATOM", "HETATM"):
            if not en_atomos and len(cabecera) < MAX_LINEAS_DE_CABECERA_PDB:
                cabecera.append(linea.rstrip())
            continue
        en_atomos = True
        nombre, elemento = linea[12:16].strip(), linea[76:78].strip()
        if _es_hidrogeno(elemento, nombre):
            hidrogenos += 1
            continue
        crudo = linea[60:66]
        b = _flotante(crudo)
        if b is None:
            continue
        decimales_b = max(decimales_b, _decimales(crudo))
        cadena, numero, insercion, comp = linea[21:22].strip(), linea[22:26].strip(), linea[26:27].strip(), linea[17:20].strip()
        atomos.append({"nombre": nombre, "comp": comp, "cadena": cadena, "asym": cadena, "label_seq": None,
                       "numero": numero, "b": b, "proteina": registro == "ATOM",
                       "residuo": (cadena, numero, comp, insercion)})
    return {"formato": "pdb", "cabecera": cabecera, "criterio_polimero": "registro ATOM", "atomos": atomos,
            "residuos": _agrupar_residuos(atomos), "decimales_b": decimales_b, "hidrogenos_omitidos": hidrogenos,
            "metricas": [], "locales": {}, "decimales_local": {}, "globales": []}


def leer_estructura(ruta: Path | str) -> dict[str, Any]:
    return leer_pdb(ruta) if str(ruta).lower().endswith((".pdb", ".ent")) else leer_mmcif(ruta)


# ── Series que se comparan ───────────────────────────────────────────


def series_del_archivo(lectura: dict[str, Any]) -> dict[str, tuple[list[float], int]]:
    """Cada candidato a «el pLDDT del archivo», con los decimales con que está escrito."""
    proteina = [r for r in lectura["residuos"] if r["proteina"]]
    otros = [r for r in lectura["residuos"] if not r["proteina"]]
    d = lectura["decimales_b"]
    series: dict[str, tuple[list[float], int]] = {
        "b_media_por_residuo_proteina": ([r["b_media"] for r in proteina], d),
        "b_ca_por_residuo_proteina": ([r["b_ca"] if r["b_ca"] is not None else r["b"][0] for r in proteina], d),
        "b_por_atomo_proteina": ([a["b"] for a in lectura["atomos"] if a["proteina"]], d),
        "b_por_atomo_todo": ([a["b"] for a in lectura["atomos"]], d),
        # Un residuo de proteína = un token; cada átomo pesado de un ligando = un token (como tokeniza Boltz).
        "b_por_token": ([r["b_media"] for r in proteina] + [b for r in otros for b in r["b"]], d),
    }
    for metrica, valores in lectura["locales"].items():
        nombre = next((m["nombre"] for m in lectura["metricas"] if m["id"] == metrica), metrica)
        serie = [valores.get((r["clave"][0], r["label_seq"])) for r in proteina]
        if serie and all(v is not None for v in serie):
            series[f"ma_qa_metric_local[{nombre}]_proteina"] = (serie, lectura["decimales_local"].get(metrica, 0))
    return {k: v for k, v in series.items() if v[0]}


def series_del_modelo(valores: np.ndarray, lectura: dict[str, Any]) -> dict[str, list[float]]:
    plano = np.asarray(valores, dtype=float).reshape(-1)
    n_res = sum(1 for r in lectura["residuos"] if r["proteina"])
    n_atomos_proteina = sum(1 for a in lectura["atomos"] if a["proteina"])
    series = {"modelo": plano.tolist()}
    if len(plano) > n_res > 0:
        series["modelo_primeros_n_residuos"] = plano[:n_res].tolist()
    if len(plano) > n_atomos_proteina > 0:
        series["modelo_primeros_n_atomos_proteina"] = plano[:n_atomos_proteina].tolist()
    return series


def comparar(archivo: list[float], modelo: list[float], decimales: int) -> dict[str, Any]:
    """¿Reproduce el archivo la salida del modelo con una sola escala, hasta el redondeo con que escribe?"""
    if len(archivo) != len(modelo):
        return {"coincide": False, "motivo": "longitud", "n_archivo": len(archivo), "n_modelo": len(modelo)}
    a, m = np.asarray(archivo, dtype=float), np.asarray(modelo, dtype=float)
    tolerancia = 0.5 * 10.0 ** (-decimales) + 1e-5
    mejor: dict[str, Any] | None = None
    for escala in ESCALAS:
        dif = float(np.max(np.abs(a - m * escala)))
        if mejor is None or dif < mejor["max_dif"]:
            mejor = {"escala": escala, "max_dif": dif}
    pearson = float(np.corrcoef(a, m)[0, 1]) if len(a) > 2 and a.std() > 0 and m.std() > 0 else None
    return {"coincide": mejor["max_dif"] <= tolerancia, "escala": mejor["escala"], "max_dif": mejor["max_dif"],
            "tolerancia": tolerancia, "decimales": decimales, "n": len(a), "pearson": pearson}


def comparar_estructura(lectura: dict[str, Any], valores_modelo: np.ndarray | None) -> list[dict[str, Any]]:
    if valores_modelo is None:
        return []
    salida = []
    archivo = series_del_archivo(lectura)
    modelo = series_del_modelo(valores_modelo, lectura)
    for nombre_a, (serie_a, decimales) in archivo.items():
        for nombre_m, serie_m in modelo.items():
            if len(serie_a) != len(serie_m):
                continue
            salida.append({"serie_archivo": nombre_a, "serie_modelo": nombre_m,
                           **comparar(serie_a, serie_m, decimales)})
    return salida


def dispersion_dentro_del_residuo(lectura: dict[str, Any]) -> dict[str, Any]:
    """Si el factor B cambia de un átomo a otro del mismo residuo (pLDDT por átomo) o es uno por residuo."""
    proteina = [r for r in lectura["residuos"] if r["proteina"]]
    if not proteina:
        return {"residuos": 0}
    maxima = max(r["b_dispersion"] for r in proteina)
    tolerancia = 0.5 * 10.0 ** (-lectura["decimales_b"]) * 2 + 1e-5
    return {"residuos": len(proteina), "max_dispersion": maxima,
            "uno_por_residuo": maxima <= tolerancia,
            "residuos_con_dispersion": sum(1 for r in proteina if r["b_dispersion"] > tolerancia)}


def resumen_de_la_estructura(lectura: dict[str, Any]) -> dict[str, Any]:
    proteina = [r for r in lectura["residuos"] if r["proteina"]]
    otros = [r for r in lectura["residuos"] if not r["proteina"]]
    b = [a["b"] for a in lectura["atomos"]]
    return {
        "formato": lectura["formato"],
        "criterio_polimero": lectura["criterio_polimero"],
        "residuos_proteina": len(proteina),
        "residuos_no_proteina": [{"nombre": r["nombre"], "cadena": r["cadena"], "numero": r["numero"],
                                  "atomos": len(r["b"]), "b_min": min(r["b"]), "b_max": max(r["b"])} for r in otros],
        "atomos_pesados": len(b),
        "hidrogenos_omitidos": lectura["hidrogenos_omitidos"],
        "b_min": min(b) if b else None, "b_max": max(b) if b else None,
        "decimales_b": lectura["decimales_b"],
        "dentro_del_residuo": dispersion_dentro_del_residuo(lectura),
        "metricas_modelcif": lectura["metricas"],
        "metricas_globales": lectura["globales"],
        "categorias": lectura.get("categorias"),
        "procedencia": lectura.get("procedencia"),
        "cabecera_pdb": lectura.get("cabecera"),
    }


# ── Veredicto ────────────────────────────────────────────────────────


def escala_del_archivo(escala_sobre_modelo: float, max_modelo: float) -> str:
    modelo_0_1 = max_modelo <= 1.0 + 1e-6
    valor = (1.0 if modelo_0_1 else 100.0) * escala_sobre_modelo
    return "0-1" if abs(valor - 1.0) < 1e-9 else "0-100" if abs(valor - 100.0) < 1e-9 else f"×{valor:g}"


def veredicto(estructuras: list[dict[str, Any]]) -> dict[str, Any]:
    """``estructuras``: [{herramienta, formato, archivo, max_modelo, comparaciones: [...]}, ...] de UN grupo."""
    terminadas = [e for e in estructuras if e.get("comparaciones") is not None]
    candidatos = sorted({c["serie_archivo"] for e in terminadas for c in e["comparaciones"]})
    por_serie: dict[str, Any] = {}
    for serie in candidatos:
        escalas, difs, cubiertas = set(), [], 0
        for e in terminadas:
            buenas = [c for c in e["comparaciones"] if c["serie_archivo"] == serie and c["coincide"]]
            if buenas:
                cubiertas += 1
                mejor = min(buenas, key=lambda c: c["max_dif"])
                escalas.add(escala_del_archivo(mejor["escala"], e["max_modelo"]))
                difs.append(mejor["max_dif"])
        verificada = (len(terminadas) >= MINIMO_DE_ESTRUCTURAS and cubiertas == len(terminadas)
                      and len(escalas) == 1)
        por_serie[serie] = {"verificada": verificada, "estructuras_que_coinciden": cubiertas,
                            "estructuras": len(terminadas), "escala_en_el_archivo": sorted(escalas),
                            "max_dif": max(difs) if difs else None}
    verificadas = [s for s, v in por_serie.items() if v["verificada"]]
    if len(terminadas) < MINIMO_DE_ESTRUCTURAS:
        motivo = f"sólo {len(terminadas)} estructura(s) terminada(s); el criterio pide {MINIMO_DE_ESTRUCTURAS}"
    elif not verificadas:
        motivo = "ningún campo del archivo reproduce el pLDDT del modelo en todas las estructuras"
    else:
        motivo = None
    return {"estructuras": len(terminadas), "series_verificadas": verificadas, "motivo_si_no": motivo,
            "por_serie": por_serie}


# ── Recorrido de los resultados del cuaderno ─────────────────────────


def _modelo_boltz(cif: Path) -> tuple[np.ndarray | None, dict[str, Any] | None]:
    m = re.match(r"(.+)_model_(\d+)\.(cif|pdb)$", cif.name)
    if not m:
        return None, None
    nombre, k = m.group(1), m.group(2)
    npz = cif.parent / f"plddt_{nombre}_model_{k}.npz"
    conf = cif.parent / f"confidence_{nombre}_model_{k}.json"
    valores = None
    if npz.exists():
        with np.load(npz) as datos:
            clave = "plddt" if "plddt" in datos.files else datos.files[0]
            valores = np.asarray(datos[clave], dtype=float)
    confianza = json.loads(conf.read_text(encoding="utf-8")) if conf.exists() else None
    return valores, confianza


def _modelo_chai(cif: Path, corrida: Path) -> tuple[np.ndarray | None, dict[str, Any] | None]:
    resumen_ruta = corrida / "resumen_chai.json"
    npz = corrida / "salida_del_modelo.npz"
    if not (resumen_ruta.exists() and npz.exists()):
        return None, None
    resumen = json.loads(resumen_ruta.read_text(encoding="utf-8"))
    rutas = [Path(p).name for p in resumen.get("cif_paths") or []]
    if cif.name not in rutas:
        return None, None
    i = rutas.index(cif.name)
    with np.load(npz) as datos:
        if "plddt" not in datos.files:
            return None, None
        plddt = np.asarray(datos["plddt"], dtype=float)
    valores = plddt[i] if plddt.ndim >= 2 else plddt
    puntuaciones = corrida / cif.name.replace("pred.", "scores.").replace(".cif", ".npz")
    extra = None
    if puntuaciones.exists():
        with np.load(puntuaciones) as datos:
            extra = {k: _a_lista(datos[k]) for k in datos.files}
    return valores, extra


def _a_lista(valor) -> Any:
    """Un array del npz como lista JSON. Sólo se redondea lo que es número real: Chai-1 guarda también booleanos."""
    arreglo = np.asarray(valor)
    return arreglo.round(4).tolist() if np.issubdtype(arreglo.dtype, np.floating) else arreglo.tolist()


def analizar_resultados(raiz: Path | str) -> dict[str, Any]:
    """Recorre ``resultados/boltz/*`` y ``resultados/chai/*`` y aplica el criterio por grupo."""
    raiz = Path(raiz)
    estructuras: list[dict[str, Any]] = []
    for herramienta in ("boltz", "chai"):
        for corrida in sorted((raiz / herramienta).glob("*")) if (raiz / herramienta).exists() else []:
            if not corrida.is_dir() or "__fallido_" in corrida.name:
                continue
            caso, _, formato_pedido = corrida.name.partition("__")
            for ruta in sorted(list(corrida.rglob("*.cif")) + list(corrida.rglob("*.pdb"))):
                if herramienta == "boltz" and "_model_" not in ruta.name:
                    continue
                if herramienta == "chai" and not ruta.name.startswith("pred."):
                    continue
                lectura = leer_estructura(ruta)
                valores, confianza = (_modelo_boltz(ruta) if herramienta == "boltz" else _modelo_chai(ruta, corrida))
                estructuras.append({
                    "herramienta": herramienta, "caso": caso, "formato": lectura["formato"],
                    "archivo": str(ruta.relative_to(raiz)).replace("\\", "/"), "sha256": sha256(ruta),
                    "max_modelo": float(np.max(valores)) if valores is not None else None,
                    "media_modelo": float(np.mean(valores)) if valores is not None else None,
                    "n_modelo": int(np.asarray(valores).size) if valores is not None else None,
                    "confianza_declarada_por_el_modelo": confianza,
                    "resumen": resumen_de_la_estructura(lectura),
                    "comparaciones": comparar_estructura(lectura, valores) if valores is not None else None,
                    "_lectura": lectura,
                })
    grupos: dict[str, Any] = {}
    for clave in sorted({(e["herramienta"], e["formato"]) for e in estructuras}):
        grupo = [e for e in estructuras if (e["herramienta"], e["formato"]) == clave]
        grupos[f"{clave[0]}/{clave[1]}"] = veredicto(grupo)

    control = _control_alphafold_db(raiz, estructuras, grupos)
    for e in estructuras:
        e.pop("_lectura", None)
    return {"criterio": {"minimo_de_estructuras": MINIMO_DE_ESTRUCTURAS, "escalas": list(ESCALAS),
                         "tolerancia": "0,5 × 10^-decimales escritos (+1e-5)"},
            "grupos": grupos, "control_alphafold_db": control, "estructuras": estructuras}


def _control_alphafold_db(raiz: Path, estructuras: list[dict[str, Any]], grupos: dict[str, Any]) -> list[dict]:
    """ρ de Spearman entre el pLDDT de cada predicción de NET y el de AlphaFold DB, residuo a residuo."""
    af = next(iter(sorted((raiz / "referencias").glob("AF-*.cif"))), None) if (raiz / "referencias").exists() else None
    if af is None:
        return []
    lectura_af = leer_mmcif(af)
    plddt_af = next((v for m, v in lectura_af["locales"].items()
                     if any(x["id"] == m and x["nombre"].lower() == "plddt" for x in lectura_af["metricas"])), None)
    if not plddt_af:
        return []
    por_numero = {seq: v for (_, seq), v in plddt_af.items()}
    salida = []
    for e in estructuras:
        if e["caso"] != "net_apo":
            continue
        lectura = e["_lectura"]
        proteina = [r for r in lectura["residuos"] if r["proteina"]]
        numeros = [r["label_seq"] if r["label_seq"] is not None else int(r["numero"]) for r in proteina]
        comunes = [(r["b_media"], por_numero[n]) for r, n in zip(proteina, numeros) if n in por_numero]
        salida.append({"archivo": e["archivo"], "residuos_comunes": len(comunes),
                       "spearman_b_media_vs_afdb": spearman([c[0] for c in comunes], [c[1] for c in comunes]),
                       "referencia": af.name, "referencia_sha256": sha256(af)})
    return salida


def informe_markdown(analisis: dict[str, Any], procedencia: dict[str, Any] | None = None) -> str:
    lineas = ["# Convención del pLDDT de Boltz y Chai-1 — resultado", ""]
    if procedencia:
        lineas += [f"- GPU: {procedencia.get('gpu', {}).get('nombre')}",
                   f"- Boltz: {procedencia.get('versiones', {}).get('boltz')} · Chai-1: "
                   f"{procedencia.get('versiones', {}).get('chai_lab')}", ""]
    lineas += ["| Grupo | Estructuras | Campo verificado | Escala en el archivo | Motivo si no |",
               "|---|---:|---|---|---|"]
    for grupo, v in analisis["grupos"].items():
        series = v["series_verificadas"]
        escalas = sorted({e for s in series for e in v["por_serie"][s]["escala_en_el_archivo"]})
        lineas.append(f"| {grupo} | {v['estructuras']} | {', '.join(series) or '—'} | {', '.join(escalas) or '—'} | "
                      f"{v['motivo_si_no'] or ''} |")
    lineas += ["", "## Lo que declara cada archivo", ""]
    for e in analisis["estructuras"]:
        r = e["resumen"]
        lineas.append(f"### {e['archivo']}")
        lineas.append(f"- átomos pesados {r['atomos_pesados']}, residuos de proteína {r['residuos_proteina']}, "
                      f"B {r['b_min']}–{r['b_max']} con {r['decimales_b']} decimales; "
                      f"uno por residuo: {r['dentro_del_residuo'].get('uno_por_residuo')}")
        if r.get("metricas_modelcif"):
            lineas.append(f"- métricas ModelCIF: {', '.join(m['nombre'] for m in r['metricas_modelcif'])}")
        if r.get("procedencia"):
            for categoria in ("_exptl.", "_struct.", "_software.", "_audit_conform.", "_entry."):
                if categoria in r["procedencia"]:
                    lineas.append(f"- `{categoria}` {json.dumps(r['procedencia'][categoria], ensure_ascii=False)[:300]}")
        if r.get("cabecera_pdb") is not None:
            lineas.append(f"- cabecera PDB: {json.dumps(r['cabecera_pdb'][:8], ensure_ascii=False)[:400]}")
        lineas.append("")
    if analisis.get("control_alphafold_db"):
        lineas += ["## Control de sentido contra AlphaFold DB (NET)", ""]
        for c in analisis["control_alphafold_db"]:
            rho = c["spearman_b_media_vs_afdb"]
            lineas.append(f"- {c['archivo']}: ρ = {rho:.3f} sobre {c['residuos_comunes']} residuos" if rho is not None
                          else f"- {c['archivo']}: sin ρ")
    return "\n".join(lineas) + "\n"
