"""Validez fisica de la pose entregada, en produccion.

Cierra el hueco numero uno del dossier: hasta hoy la seccion de validez fisica decia
`NO EVALUADA`. El modulo se sigue justificando por eso -un dossier que no evalua la fisica
de lo que entrega tiene un hueco-, pero NO por la cifra con la que se escribio.

CORREGIDO EL 2026-08-23 POR `MF-33-H-COR`. La motivacion original de este modulo era que
`MF-33-TOP1` habia medido 10/116 = 8.62 % (un conformero) y 18/116 = 15.52 % (ensemble),
con `internal_energy` fallando 203 veces, y de ahi que «mas del 84 % de lo que se entrega
es fisicamente invalido». ESA MEDICION ESTABA CONTAMINADA por la capa de reconstruccion de
`scripts/posebusters_metrica.py`, que anadia los hidrogenos sobre la geometria
CRISTALOGRAFICA y solo reemplazaba despues las coordenadas presentes en el PDBQT -de Vina,
unicamente las polares-. Con reconstruccion canonica -todos los hidrogenos regenerados
desde la geometria dockeada y relajados con los pesados FIJOS- las tasas reales son
**91.38 % y 94.83 %**, y `internal_energy` cae de 8006 a 7 sobre el brazo flexible.

CONSECUENCIA PARA ESTE MODULO, y es la parte que importa: la explicacion causal que se
escribio aqui -«la pose hereda la tension del conformero de entrada sin relajarse nunca»-
ES FALSA y queda retirada. El fallo dominante no era tension del ligando. Lo que queda
como fallo real es GEOMETRICO y escaso: choques internos, distancia al receptor y
geometria de enlaces, en 43 de 8224 poses concentradas en siete complejos.

LAS DOS DEUDAS QUEDARON CERRADAS EL 2026-08-23 POR `PROD-PV-H-01`, 232 poses, y en
direcciones distintas.

  DEUDA 1, REPRESENTACION DE HIDROGENOS: SIN EFECTO DETECTABLE, Y EL DISENO NO TUVO PODER
  PARA DETECTARLO. La ruta mixta y la canonica dan el mismo veredicto en las 232 bajo el
  evaluador oficial, pero la razon no es que sean equivalentes: LAS 232 PASAN, asi que no
  hubo un solo caso discriminante. El `energy_ratio` oficial va de -20.3 a 19.1 contra un
  umbral de 100.0. Se puede decir que en esta cohorte la ruta actual no se equivoca; NO se
  puede decir que las dos representaciones sean equivalentes en general.

  DEUDA 2, PROXY ENERGETICO: DISCREPA, Y SIEMPRE HACIA EL FALSO RECHAZO. 33 de 232 -el
  14.2%-, todas en la misma direccion: el proxy FALLA donde el oficial PASA. Por eso el
  escalon 2 ya nunca emite `failed`; ver la razon completa en `evaluar_pose_fisica`.

LO QUE SIGUE ABIERTO, y conviene no perderlo de vista: este modulo mide el control
ENERGETICO y solo ese. La bateria completa -distancias al receptor, valencias, aromaticidad,
planaridad- solo corre en el escalon 1, con PoseBusters instalado y con receptor.

DIFERENCIA CRITICA CON `scripts/posebusters_metrica.py`, y es la razon de que este modulo
exista en vez de reusar aquel: el de `scripts/` corre PoseBusters en configuracion
**redock**, que necesita el ligando cristalografico como referencia. En produccion esa
referencia NO EXISTE -es justamente el caso de uso-, asi que aqui se usa la configuracion
**dock**: pose contra receptor, sin verdad de terreno. Cubre lo intramolecular y las
distancias al receptor.

Degrada en dos escalones y lo declara siempre:

  1. PoseBusters instalado -> bateria completa en config `dock`;
  2. solo RDKit           -> unicamente el proxy energetico NO CALIBRADO, declarado como
     tal y nunca como PoseBusters;
  3. ninguno              -> `NO EVALUADA`, igual que hoy, pero diciendo por que.

Nunca inventa un veredicto: un control que no se pudo ejecutar se reporta como no
evaluado, no como aprobado. La frase obligatoria del `docs/53` §6.3 se emite con el
resultado.

AVISO QUE NO SE PUEDE OMITIR AL COMPARAR CIFRAS. El 91.38 % / 94.83 % de `MF-33-H-COR` se
midio en configuracion **redock**, que incluye controles contra la verdad de terreno, y es
CONDICIONAL a una reconstruccion canonica de hidrogenos. Esta comprobacion corre en
**dock**, que tiene menos controles porque en produccion no hay cristal, y con la
representacion de hidrogenos descrita arriba. Una pose puede pasar `dock` y fallar
`redock`. **Las dos tasas no son comparables**, y presentar la de produccion como si
refutara la del registro seria repetir el error de escala que costo una retractacion en
`MF-29-EMP-COR`. La tasa de produccion es una cota superior de la validez, no una medida
equivalente.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, NamedTuple

log = logging.getLogger(__name__)

# Parametros del PROXY de tension propio. NO son los de PoseBusters, y la coincidencia del
# 100.0 es enganosa: el umbral de PoseBusters se aplica a OTRA cantidad. Ver la tabla del
# docstring de `proxy_tension_rdkit`. Estos numeros NO estan calibrados contra nada.
UMBRAL_PROXY_TENSION = 100.0
N_CONFORMEROS_PROXY = 16

# Los de PoseBusters 0.6.5 en configuracion `dock`, leidos de su propio `config/dock.yml`.
# Se declaran aqui para que la diferencia con el proxy sea visible sin abrir el paquete, y
# para que nadie vuelva a escribir que el proxy es "la reimplementacion" de este control.
PB_DOCK_UMBRAL_ENERGY_RATIO = 100.0
PB_DOCK_N_CONFORMEROS = 50

# El nombre del control del escalon 2. NO se llama `internal_energy` a proposito: ese nombre
# es de PoseBusters y decirlo aqui haria pasar por oficial una cantidad que no lo es.
NOMBRE_PROXY = "rdkit_energy_strain_proxy"
MOTOR_PROXY = "rdkit:energy_strain_proxy_no_calibrado"

FRASE_OBLIGATORIA = (
    "Ausencia de alertas no significa ausencia de choques, enlaces imposibles o "
    "artefactos de preparacion."
)


def _rdkit():
    try:
        from rdkit import Chem, RDLogger
        RDLogger.DisableLog("rdApp.*")
        return Chem
    except ImportError:
        return None


def _posebusters_disponible() -> bool:
    try:
        import posebusters  # noqa: F401
        return True
    except ImportError:
        return False


def _version_posebusters() -> str:
    """La version va en el `motor` porque los umbrales viven en el paquete, no aqui.

    `dock.yml` fija `threshold_energy_ratio` y `ensemble_number_conformations`. Si una
    actualizacion los cambia, el veredicto cambia sin que este modulo se toque; sin la
    version en el registro, ese cambio seria invisible en el dossier.
    """
    try:
        import posebusters
        return str(getattr(posebusters, "__version__", "desconocida"))
    except ImportError:
        return "no_instalado"


class LecturaPose(NamedTuple):
    """Resultado de leer una pose. `mol` es None si NO se pudo leer sin ambiguedad."""
    mol: Any
    ruta: str | None
    motivo: str | None
    diagnostico: dict[str, Any]


# Pseudo-atomos de PEGADO que Meeko inserta al abrir un macrociclo para hacerlo flexible.
# NO son atomos de la molecula: no tienen entrada en `index_map.json` porque no existen en
# ella. Se reconocen por su tipo AutoDock -no hay elemento `G`- y se descartan. Es una
# convencion documentada del formato, no una heuristica quimica.
TIPOS_PEGADO_MACROCICLO = frozenset(
    {"G", "CG"} | {f"G{i}" for i in range(10)} | {f"CG{i}" for i in range(10)})

_REMARK_H_PARENT = re.compile(r"^REMARK\s+H\s+PARENT\s*(.*)$", re.MULTILINE)


def _coords_de_pdbqt(texto: str) -> list[tuple[int, float, float, float, str]]:
    """(serial, x, y, z, tipo_autodock) por atomo, leidos por COLUMNAS FIJAS.

    Las columnas 77-78 se leen SOLO para saber si el atomo es un pseudo-atomo de pegado;
    nunca para deducir el elemento. Ahi vive el tipo AutoDock, no el simbolo quimico: `A` es
    carbono aromatico, `NA` nitrogeno aceptor, `HD` hidrogeno donador. Confundirlos con
    elementos es lo que hacia ilegible el 76.7% de la cohorte.
    """
    salida = []
    for l in texto.splitlines():
        if not l.startswith(("ATOM", "HETATM")):
            continue
        try:
            salida.append((int(l[6:11]), float(l[30:38]), float(l[38:46]), float(l[46:54]),
                           l[76:78].strip()))
        except (ValueError, IndexError):
            continue
    return salida


def leer_pose_pdbqt(pose_pdbqt: str, plantilla=None, index_map=None,
                    smiles: str | None = None) -> LecturaPose:
    """El PDBQT aporta SOLO coordenadas. El grafo, la carga y los ordenes de enlace, no.

    RUTA PRINCIPAL -`mapa_atomico`-: plantilla quimica + `index_map` serial->indice +
    coordenadas del PDBQT. Es el patron que usa el corrigendum `MF-33-H-COR`, y es fuerte
    porque NADA se infiere: la identidad quimica viene de la molecula que el pipeline
    preparo, y del archivo solo se leen numeros de las columnas 31-54.

    POR QUE NO SE TRUNCA A PDB. Truncar quita la confusion `A`->elemento, pero obliga a
    RDKit a inferir el grafo desde distancias y luego a parchearlo con
    `AssignBondOrdersFromTemplate`. Medido sobre 232 poses: el lector viejo leia 40, el
    truncado 156, y a cambio los fallos de valencia subian de 14 a 70. Inferir y despues
    corregir NO es una ruta principal aceptable.

    LA REPRESENTACION QUE DEVUELVE es la MIXTA, que es lo que hoy ve produccion: se
    conservan explicitos los atomos que traen coordenada en el PDBQT -pesados y polares- y
    se ELIMINAN los que no -los no polares, que pasan a implicitos-. No se les deja la
    coordenada de la plantilla: eso seria reproducir el defecto de `MF-33-H-COR`.

    SE ABSTIENE ANTES QUE ADIVINAR. Mapa no biyectivo, serial ausente o duplicado, o un
    atomo PESADO sin coordenada devuelven `None` con el motivo, nunca una reconstruccion
    heuristica silenciosa.

    `smiles` habilita la RUTA DE RESPALDO -`plantilla_heuristica`-, que es el lector viejo.
    Queda explicita y contada, no como fundamento.
    """
    Chem = _rdkit()
    if Chem is None:
        return LecturaPose(None, None, "rdkit_no_instalado", {})

    atomos = _coords_de_pdbqt(pose_pdbqt)
    diag: dict[str, Any] = {"n_atomos_en_pdbqt": len(atomos)}
    if not atomos:
        return LecturaPose(None, None, "pdbqt_sin_atomos", diag)

    if plantilla is not None and index_map:
        return _leer_por_mapa(Chem, atomos, plantilla, index_map, diag)
    if smiles:
        diag["aviso"] = ("sin mapa atomico: se usa la ruta de respaldo, que infiere el grafo "
                         "desde distancias y lo parchea con AssignBondOrdersFromTemplate")
        return _leer_por_plantilla_heuristica(Chem, pose_pdbqt, smiles, diag)
    return LecturaPose(None, None, "sin_mapa_ni_smiles", diag)


def _seriales_h_polares_declarados(pose_pdbqt: str) -> set[int]:
    """Seriales de H que Meeko declara en ``REMARK H PARENT``.

    No se deduce el elemento desde el tipo AutoDock. La declaración del
    preparador permite excluir esos H antes de reconstruirlos todos desde la
    geometría pesada, que es el protocolo corregido de MF-33-H-COR.
    """
    seriales: set[int] = set()
    for bloque in _REMARK_H_PARENT.findall(pose_pdbqt or ""):
        campos = bloque.split()
        for i in range(0, len(campos) - 1, 2):
            try:
                seriales.add(int(campos[i + 1]))
            except ValueError:
                continue
    return seriales


def leer_pose_pdbqt_canonica(
    pose_pdbqt: str,
    plantilla=None,
    index_map=None,
    smiles: str | None = None,
) -> LecturaPose:
    """Lee únicamente el esqueleto pesado que Vina posicionó.

    La ruta histórica ``leer_pose_pdbqt`` conserva los H polares de Vina y se
    mantiene para reproducir PROD-PV-H-01. Producción usa esta ruta: descarta
    sólo los H declarados por Meeko, remapea los índices pesados y deja que
    ``canonicalizar_hidrogenos`` regenere *todos* los H. Así un amonio con tres
    H equivalentes no obliga a escoger arbitrariamente cuál serial corresponde
    a cuál átomo explícito.
    """
    Chem = _rdkit()
    if Chem is None:
        return LecturaPose(None, None, "rdkit_no_instalado", {})

    if plantilla is None or not index_map:
        # PDBQT externo: conserva la degradación declarada existente. La
        # canonicalización posterior elimina cualquier H antes de regenerarlo.
        return leer_pose_pdbqt(
            pose_pdbqt, plantilla=plantilla, index_map=index_map, smiles=smiles
        )

    atomos = _coords_de_pdbqt(pose_pdbqt)
    diag: dict[str, Any] = {"n_atomos_en_pdbqt": len(atomos)}
    if not atomos:
        return LecturaPose(None, None, "pdbqt_sin_atomos", diag)

    try:
        original = Chem.Mol(plantilla)
        indices_pesados = [
            atom.GetIdx() for atom in original.GetAtoms() if atom.GetAtomicNum() > 1
        ]
        viejo_a_nuevo = {viejo: nuevo for nuevo, viejo in enumerate(indices_pesados)}
        mapa_pesado = [
            (int(serial), viejo_a_nuevo[int(indice)])
            for serial, indice in index_map
            if int(indice) in viejo_a_nuevo
        ]
        plantilla_pesada = Chem.RemoveAllHs(original)
    except Exception as exc:                                   # noqa: BLE001
        diag["error_mapa_pesado"] = type(exc).__name__
        return LecturaPose(None, "mapa_atomico_canonico", "index_map_ilegible", diag)

    h_polares = _seriales_h_polares_declarados(pose_pdbqt)
    atomos_pesados = [entrada for entrada in atomos if entrada[0] not in h_polares]
    diag["h_polares_declarados_descartados"] = len(h_polares)
    diag["n_h_heredados"] = 0

    lectura = _leer_por_mapa(
        Chem,
        atomos_pesados,
        plantilla_pesada,
        mapa_pesado,
        diag,
    )
    return LecturaPose(
        lectura.mol,
        "mapa_atomico_canonico",
        lectura.motivo,
        lectura.diagnostico,
    )


def _leer_por_mapa(Chem, atomos, plantilla, index_map, diag) -> LecturaPose:
    pegado = [s for s, *_r in atomos if _r[3] in TIPOS_PEGADO_MACROCICLO]
    if pegado:
        # Un macrociclo abierto por Meeko. Se descartan por tipo, y el control de «ningun
        # pesado sin coordenada» de mas abajo garantiza que no se cuela nada real.
        diag["pseudoatomos_de_pegado_descartados"] = len(pegado)
        atomos = [a for a in atomos if a[4] not in TIPOS_PEGADO_MACROCICLO]
        if not atomos:
            return LecturaPose(None, "mapa_atomico", "solo_pseudoatomos_de_pegado", diag)
    seriales = [s for s, *_ in atomos]
    if len(set(seriales)) != len(seriales):
        diag["seriales_duplicados"] = len(seriales) - len(set(seriales))
        return LecturaPose(None, "mapa_atomico", "seriales_duplicados_en_pdbqt", diag)

    try:
        pares = [(int(a), int(b)) for a, b in index_map]
    except (TypeError, ValueError):
        return LecturaPose(None, "mapa_atomico", "index_map_ilegible", diag)
    s2m = dict(pares)
    if len(s2m) != len(pares) or len({b for _, b in pares}) != len(pares):
        diag["mapa_biyectivo"] = False
        return LecturaPose(None, "mapa_atomico", "index_map_no_biyectivo", diag)
    diag["mapa_biyectivo"] = True

    mol = Chem.Mol(plantilla)
    n = mol.GetNumAtoms()
    sin_mapa = [s for s in seriales if s not in s2m]
    fuera = [s2m[s] for s in seriales if s in s2m and not 0 <= s2m[s] < n]
    if sin_mapa or fuera:
        diag.update(seriales_sin_entrada_en_el_mapa=sin_mapa[:10],
                    indices_fuera_de_rango=fuera[:10])
        return LecturaPose(None, "mapa_atomico", "serial_ausente_o_indice_fuera_de_rango", diag)

    coords = {s2m[s]: (x, y, z) for s, x, y, z, _tipo in atomos}
    pesados_sin_coord = [i for i, a in enumerate(mol.GetAtoms())
                         if a.GetAtomicNum() > 1 and i not in coords]
    if pesados_sin_coord:
        diag["atomos_pesados_sin_coordenada"] = pesados_sin_coord[:10]
        return LecturaPose(None, "mapa_atomico", "atomo_pesado_sin_coordenada", diag)

    conf = mol.GetConformer()
    for idx, (x, y, z) in coords.items():
        conf.SetAtomPosition(int(idx), (float(x), float(y), float(z)))

    # Los que no traen coordenada son hidrogenos: se ELIMINAN para que queden implicitos,
    # en vez de conservar la geometria de la plantilla. Esa es la diferencia entre la
    # representacion mixta real de produccion y el defecto que corrigio MF-33-H-COR.
    sobran = sorted((i for i in range(n) if i not in coords), reverse=True)
    diag["h_sin_coordenada_eliminados"] = len(sobran)
    if sobran:
        rw = Chem.RWMol(mol)
        for i in sobran:
            vecinos = [v.GetIdx() for v in rw.GetAtomWithIdx(i).GetNeighbors()]
            rw.RemoveAtom(i)
            for v in vecinos:
                a = rw.GetAtomWithIdx(v if v < i else v - 1)
                a.SetNoImplicit(False)
                a.SetNumExplicitHs(0)
        mol = rw.GetMol()
    try:
        Chem.SanitizeMol(mol)
    except Exception as exc:                                   # noqa: BLE001
        return LecturaPose(None, "mapa_atomico", f"no_sanitiza:{type(exc).__name__}", diag)

    diag.update(_invariantes_lectura(Chem, plantilla, mol, coords))
    if not diag["carga_formal_identica"] or not diag["n_enlaces_pesados_identico"]:
        return LecturaPose(None, "mapa_atomico", "la_lectura_altero_la_identidad_quimica", diag)
    return LecturaPose(mol, "mapa_atomico", None, diag)


def _invariantes_lectura(Chem, plantilla, mol, coords) -> dict[str, Any]:
    """Que la lectura no invente quimica: carga, enlaces, estereo y coordenadas pesadas."""
    def _sin_h(m):
        return Chem.RemoveAllHs(Chem.Mol(m))

    try:
        pl, le = _sin_h(plantilla), _sin_h(mol)
        Chem.AssignStereochemistry(pl, cleanIt=True, force=True)
        Chem.AssignStereochemistry(le, cleanIt=True, force=True)
        return {
            "carga_formal_identica": Chem.GetFormalCharge(plantilla) == Chem.GetFormalCharge(mol),
            "n_enlaces_pesados_identico": pl.GetNumBonds() == le.GetNumBonds(),
            "n_atomos_pesados_identico": pl.GetNumAtoms() == le.GetNumAtoms(),
            "smiles_isomerico_identico": (Chem.MolToSmiles(pl, isomericSmiles=True)
                                          == Chem.MolToSmiles(le, isomericSmiles=True)),
            "n_coordenadas_aplicadas": len(coords),
        }
    except Exception as exc:                                   # noqa: BLE001
        return {"carga_formal_identica": False, "n_enlaces_pesados_identico": False,
                "error_invariantes": type(exc).__name__}


def _leer_por_plantilla_heuristica(Chem, pose_pdbqt: str, smiles: str, diag) -> LecturaPose:
    """RUTA DE RESPALDO, para un PDBQT externo sin mapa. Se cuenta aparte a proposito.

    Infiere el grafo desde distancias y lo parchea con `AssignBondOrdersFromTemplate`. Es
    justo lo que NO debe fundamentar el lector, y por eso vive aqui abajo y se etiqueta.
    """
    bloque = "\n".join(l for l in pose_pdbqt.splitlines()
                       if l.startswith(("ATOM", "HETATM", "END", "CONECT")))
    mol = Chem.MolFromPDBBlock(bloque, removeHs=False, sanitize=False)
    if mol is None:
        return LecturaPose(None, "plantilla_heuristica", "pose_ilegible", diag)
    plantilla = Chem.MolFromSmiles(smiles)
    if plantilla is None:
        return LecturaPose(None, "plantilla_heuristica", "smiles_ilegible", diag)
    try:
        from rdkit.Chem import AllChem
        mol = AllChem.AssignBondOrdersFromTemplate(plantilla, mol)
    except Exception as exc:                                   # noqa: BLE001
        return LecturaPose(None, "plantilla_heuristica",
                           f"plantilla_no_encaja:{type(exc).__name__}", diag)
    return LecturaPose(mol, "plantilla_heuristica", None, diag)


def pose_pdbqt_a_mol(pose_pdbqt: str, smiles: str | None = None, plantilla=None,
                     index_map=None):
    """Envoltura estrecha de `leer_pose_pdbqt` con el contrato `(mol, motivo)` de siempre."""
    r = leer_pose_pdbqt(pose_pdbqt, plantilla=plantilla, index_map=index_map, smiles=smiles)
    return r.mol, r.motivo


# Controles de CARGA, no de quimica. Si uno de estos falla, lo que se rompio es la
# entrada -formato del archivo, permisos, ruta-, no la pose. Reportarlos como
# `CONTROLES FALLIDOS` le diria al usuario que su pose es invalida cuando lo unico
# invalido era el archivo que le pasamos al validador.
CHECKS_DE_CARGA = frozenset({
    "mol_pred_loaded", "mol_true_loaded", "mol_cond_loaded", "sanitization",
})


def clasificar_resultado_pb(valor: Any) -> str:
    """PASA / FALLA / NO_EVALUADO para una celda de la tabla de PoseBusters.

    EXISTE POR UN DEFECTO DE CONTRATO REAL, no por prudencia abstracta. PoseBusters no
    senala «no pude evaluar esto» con `None`: varios de sus modulos devuelven **NaN**. En
    `posebusters/modules/energy_ratio.py`, `_empty_results` pone `energy_ratio_passes` a
    `float("nan")` y se devuelve en CUATRO caminos distintos -sin conformero, molecula que no
    sanitiza, **UFF sin parametros para la molecula**, o InChI que no se puede construir-.
    Un ligando con un metal o con quimica exotica cae ahi con toda naturalidad.

    Y `nan` no es `None` ni es `False`: con la deteccion anterior -`v is None`- ese control
    no entraba ni en los fallidos ni en los no evaluados, asi que **una bateria a la que le
    falto el control de energia se reportaba como CONTROLES SUPERADOS**. Es exactamente el
    error que la frase obligatoria del `docs/53` §6.3 existe para impedir, cometido por el
    propio modulo que la emite.

    La regla, deliberadamente estricta: aprueba **solo** un `True` booleano. Cualquier otra
    cosa -`None`, `nan`, un numero, una cadena- es NO_EVALUADO, no aprobado. Los booleanos de
    numpy se aceptan porque son booleanos de verdad; se comprueban por valor y no por
    identidad, que es lo que `v is True` no hacia.
    """
    if isinstance(valor, bool):                    # bool de Python
        return "PASA" if valor else "FALLA"
    tipo = type(valor)
    if tipo.__module__ == "numpy" and tipo.__name__ in ("bool_", "bool"):
        return "PASA" if bool(valor) else "FALLA"
    return "NO_EVALUADO"


#: Tipo AutoDock -> simbolo quimico. Un PDBQT no lleva columna de elemento: la
#: lleva en su tipo, que ademas distingue cosas que el simbolo no -`NA` es un
#: nitrogeno ACEPTOR, no sodio; `A` es carbono aromatico.
_ELEMENTO_POR_TIPO_AD = {
    "A": "C", "C": "C", "N": "N", "NA": "N", "NS": "N",
    "O": "O", "OA": "O", "OS": "O", "S": "S", "SA": "S",
    "H": "H", "HD": "H", "HS": "H", "F": "F", "CL": "CL", "BR": "BR", "I": "I",
    "P": "P", "MG": "MG", "CA": "CA", "MN": "MN", "FE": "FE", "ZN": "ZN",
    "CU": "CU", "NI": "NI", "CO": "CO", "SE": "SE", "K": "K", "NB": "N",
}


def receptor_como_pdb(receptor_path: str | Path) -> Path | None:
    """PoseBusters no lee PDBQT. Devuelve un PDB temporal equivalente si hace falta.

    La conversion es un truncado de columnas: las 1-66 de un PDBQT son las de un PDB, y
    lo que sobra son la carga parcial y el tipo AutoDock. Se pierde el simbolo quimico de
    las columnas 77-78, que RDKit reinfiere del nombre de atomo; para un receptor es
    suficiente y evita arrastrar aqui la trampa de que `NA` en un PDBQT es un nitrogeno
    aceptor y no sodio.
    """
    import tempfile

    p = Path(receptor_path)
    if not p.exists():
        return None
    if p.suffix.lower() != ".pdbqt":
        return p
    lineas = []
    for linea in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if not linea.startswith(("ATOM", "HETATM")):
            continue
        # El TIPO AUTODOCK -ultimo campo del PDBQT- se traduce a simbolo quimico
        # y se escribe en las columnas 77-78.
        #
        # EL FALLO QUE ARREGLA. Antes se truncaba a 66 columnas y se dejaba sin
        # simbolo, confiando en que RDKit lo dedujera del nombre del atomo. Con
        # un receptor de OpenBabel cuela; con uno de MEEKO -el que produce el
        # pipeline- RDKit no puede cargarlo NI SIN SANEAR, y PoseBusters
        # contestaba `mol_cond_loaded = False`.
        #
        # La consecuencia no era un aviso: eran los NUEVE controles
        # intermoleculares -distancia minima al receptor, solapamiento de
        # volumen, distancia maxima proteina-ligando- devolviendo NaN. La
        # interfaz mostraba "12 pasan" sobre poses de las que NADIE habia
        # comprobado si chocan con la proteina, que es justo lo que PoseBusters
        # existe para decir. El veredicto era honesto al declarar los 9 sin
        # evaluar, pero la validez fisica no se estaba midiendo.
        campos = linea[66:].split()
        simbolo = _ELEMENTO_POR_TIPO_AD.get(campos[-1].upper()) if campos else None
        if simbolo is None:
            simbolo = linea[12:16].strip()[:1] or "C"
        lineas.append(f"{linea[:66]:<76}{simbolo.rjust(2)}")
    if not lineas:
        return None
    tmp = Path(tempfile.mkstemp(suffix=".pdb", prefix="rec_pb_")[1])
    tmp.write_text("\n".join(lineas) + "\nEND\n", encoding="utf-8")
    return tmp


def _energia(mol, conf_id: int = -1) -> float | None:
    """Energia MMFF de una conformacion; UFF si MMFF no parametriza la molecula."""
    from rdkit.Chem import AllChem
    try:
        props = AllChem.MMFFGetMoleculeProperties(mol)
        if props is not None:
            ff = AllChem.MMFFGetMoleculeForceField(mol, props, confId=conf_id)
            if ff is not None:
                return float(ff.CalcEnergy())
        ff = AllChem.UFFGetMoleculeForceField(mol, confId=conf_id)
        return float(ff.CalcEnergy()) if ff is not None else None
    except Exception:                                          # noqa: BLE001
        return None


def proxy_tension_rdkit(mol) -> dict[str, Any]:
    """PROXY ENERGETICO RDKit NO CALIBRADO. **No** es el `internal_energy` de PoseBusters.

    Se llamaba `control_energia_interna`, devolvia `check: internal_energy` y se describia
    como «la reimplementacion del `internal_energy` de PoseBusters». Las tres cosas eran
    falsas y se retiran. No comparte con aquel ni el campo de fuerza, ni el tamano del
    ensemble, ni la cantidad que compara, ni el significado del umbral:

    |                        | PoseBusters 0.6.5 `dock`            | este proxy                    |
    |------------------------|-------------------------------------|-------------------------------|
    | campo de fuerza        | UFF                                 | MMFF, con UFF de respaldo     |
    | conformeros referencia | 50                                  | 16                            |
    | cantidad               | `energia_pose / energia_media`      | `(pose - min) / (media - min)`|
    | umbral                 | 100.0 sobre ESA razon               | 100.0 sobre OTRA razon        |

    Que los dos umbrales valgan 100.0 es una coincidencia sin contenido: se aplican a
    cantidades distintas. **Nunca se debe presentar este numero como si fuera el control de
    PoseBusters**, y no puede llamarse equivalente mientras no exista una calibracion medida
    contra el modulo oficial. Es la deuda 2 del `docs/53`.

    TAMPOCO ES «EL CONTROL DOMINANTE». Esa etiqueta venia de que `MF-33-TOP1` habia contado
    203 fallos de `internal_energy`, y `MF-33-H-COR` mostro que esas 203 apariciones eran un
    artefacto de la reconstruccion de hidrogenos: con reconstruccion canonica el check cae de
    8006 a 7 sobre el brazo flexible. Se conserva porque en el escalon 2 -solo RDKit, sin
    PoseBusters- es el unico control intramolecular ejecutable, no porque sea donde esta el
    fallo.

    ALCANCE DECLARADO: no sustituye a PoseBusters. No mira distancias al receptor, ni
    valencias, ni aromaticidad, ni planaridad de dobles enlaces. Y opera sobre la
    representacion de hidrogenos que reciba -mixta, en la ruta actual: polares explicitos de
    Vina, no polares implicitos-, que es la deuda 1 del `docs/53`.
    """
    from rdkit.Chem import AllChem
    from rdkit import Chem

    e_pose = _energia(mol)
    if e_pose is None:
        return {"check": NOMBRE_PROXY, "estado": "NO_EVALUADO",
                "motivo": "no se pudo parametrizar la molecula"}

    ref = Chem.Mol(mol)
    ref.RemoveAllConformers()
    params = AllChem.ETKDGv3()
    params.randomSeed = 42
    if AllChem.EmbedMultipleConfs(ref, numConfs=N_CONFORMEROS_PROXY, params=params) == 0:
        return {"check": NOMBRE_PROXY, "estado": "NO_EVALUADO",
                "motivo": "no se generaron conformeros de referencia"}
    try:
        AllChem.MMFFOptimizeMoleculeConfs(ref, maxIters=400)
    except Exception:                                          # noqa: BLE001
        pass
    energias = [e for e in (_energia(ref, c.GetId()) for c in ref.GetConformers())
                if e is not None]
    if not energias:
        return {"check": NOMBRE_PROXY, "estado": "NO_EVALUADO",
                "motivo": "el ensemble de referencia no dio energias"}

    media = sum(energias) / len(energias)
    minimo = min(energias)
    # La razon se toma sobre el rango del ensemble para que no dependa del cero de energia
    # del campo de fuerza, que es arbitrario.
    escala = max(abs(media - minimo), 1e-6)
    razon = (e_pose - minimo) / escala
    pasa = razon <= UMBRAL_PROXY_TENSION
    return {
        "check": NOMBRE_PROXY,
        "estado": "PASA" if pasa else "FALLA",
        "energia_pose": round(e_pose, 3),
        "energia_ensemble_min": round(minimo, 3),
        "energia_ensemble_media": round(media, 3),
        "razon": round(razon, 3),
        "umbral": UMBRAL_PROXY_TENSION,
        "n_conformeros_referencia": len(energias),
    }


def canonicalizar_hidrogenos(mol) -> tuple[Any | None, dict[str, Any]]:
    """Regenera y relaja todos los H manteniendo fijos los átomos pesados.

    Es la traducción productiva del procedimiento sellado en MF-33-H-COR. La
    geometría pesada entra desde la pose dockeada; ningún H de una plantilla o
    del PDBQT sobrevive. Si MMFF no puede construir el sistema o una invariante
    cambia, se abstiene en vez de evaluar otra representación.
    """
    Chem = _rdkit()
    if Chem is None or mol is None:
        return None, {"motivo": "rdkit_no_instalado"}

    from rdkit.Chem import AllChem

    def coords_pesados(molecula) -> list[tuple[float, float, float]]:
        conf = molecula.GetConformer()
        return [
            (
                float(conf.GetAtomPosition(atom.GetIdx()).x),
                float(conf.GetAtomPosition(atom.GetIdx()).y),
                float(conf.GetAtomPosition(atom.GetIdx()).z),
            )
            for atom in molecula.GetAtoms()
            if atom.GetAtomicNum() > 1
        ]

    try:
        entrada = Chem.Mol(mol)
        pesados_antes = coords_pesados(entrada)
        desnuda = Chem.RemoveAllHs(entrada)
        canonica = Chem.AddHs(desnuda, addCoords=True)
        props = AllChem.MMFFGetMoleculeProperties(canonica)
        if props is None:
            return None, {"motivo": "MMFF_NO_PARAMETRIZA"}
        ff = AllChem.MMFFGetMoleculeForceField(canonica, props)
        if ff is None:
            return None, {"motivo": "FF_NO_CONSTRUIBLE"}
        for atom in canonica.GetAtoms():
            if atom.GetAtomicNum() > 1:
                ff.AddFixedPoint(atom.GetIdx())
        ff.Minimize(maxIts=500)
        pesados_despues = coords_pesados(canonica)
    except Exception as exc:                                   # noqa: BLE001
        return None, {"motivo": f"CANONICALIZACION_FALLO:{type(exc).__name__}"}

    if len(pesados_antes) != len(pesados_despues):
        desplazamiento = None
    else:
        desplazamiento = max(
            (
                sum((antes[i] - despues[i]) ** 2 for i in range(3)) ** 0.5
                for antes, despues in zip(pesados_antes, pesados_despues)
            ),
            default=0.0,
        )

    try:
        entrada_sin_h = Chem.RemoveAllHs(Chem.Mol(entrada))
        canonica_sin_h = Chem.RemoveAllHs(Chem.Mol(canonica))
        Chem.AssignStereochemistry(entrada_sin_h, cleanIt=True, force=True)
        Chem.AssignStereochemistry(canonica_sin_h, cleanIt=True, force=True)
        invariantes = {
            "desplazamiento_pesado_max_A": (
                round(float(desplazamiento), 9) if desplazamiento is not None else None
            ),
            "pesados_invariantes": (
                desplazamiento is not None and desplazamiento <= 1e-6
            ),
            "smiles_isomerico_identico": (
                Chem.MolToSmiles(entrada_sin_h, isomericSmiles=True)
                == Chem.MolToSmiles(canonica_sin_h, isomericSmiles=True)
            ),
            "carga_formal_identica": (
                Chem.GetFormalCharge(entrada) == Chem.GetFormalCharge(canonica)
            ),
            "n_enlaces_pesados_identico": (
                entrada_sin_h.GetNumBonds() == canonica_sin_h.GetNumBonds()
            ),
            "n_atomos_pesados_identico": (
                entrada_sin_h.GetNumAtoms() == canonica_sin_h.GetNumAtoms()
            ),
            "n_h_heredados": 0,
            "n_h_canonicos": sum(
                1 for atom in canonica.GetAtoms() if atom.GetAtomicNum() == 1
            ),
        }
    except Exception as exc:                                   # noqa: BLE001
        return None, {"motivo": f"INVARIANTES_FALLO:{type(exc).__name__}"}

    obligatorias = (
        "pesados_invariantes",
        "smiles_isomerico_identico",
        "carga_formal_identica",
        "n_enlaces_pesados_identico",
        "n_atomos_pesados_identico",
    )
    if not all(invariantes[nombre] is True for nombre in obligatorias):
        return None, {**invariantes, "motivo": "INVARIANTE_CANONICA_VIOLADA"}
    return canonica, invariantes


def evaluar_pose_fisica(
    pose_pdbqt: str,
    smiles: str | None = None,
    receptor_path: str | Path | None = None,
    plantilla=None,
    index_map=None,
) -> dict[str, Any]:
    """Veredicto de validez fisica de una pose, con el motor que haya disponible.

    PASAR `plantilla` E `index_map` SIEMPRE que la corrida sea de MolDesign. Es la ruta
    fuerte: el PDBQT aporta solo coordenadas y la quimica viene de la molecula que el propio
    pipeline preparo. Medido sobre 232 poses, la ruta del mapa cubre 232/232 y la de
    respaldo -sin mapa- cubria 40/232, con el fallo correlacionado con la aromaticidad.
    Para un PDBQT externo sin mapa queda `smiles`, y la lectura se marca como heuristica.

    Returns:
        Dict con la forma que `evidence_summary.build_evidence_summary` ya espera en
        `eval_result.pose_validation`: `status` en {passed, review, failed, not_evaluated},
        `label`, `detail`, mas `checks` y `motor` para el dossier.
    """
    lectura = leer_pose_pdbqt_canonica(
        pose_pdbqt, plantilla=plantilla, index_map=index_map, smiles=smiles
    )
    mol, motivo = lectura.mol, lectura.motivo
    if mol is None:
        return {
            "status": "not_evaluated", "label": "NO EVALUADA",
            "detail": f"No se pudo reconstruir la pose para validarla ({motivo}). "
                      f"{FRASE_OBLIGATORIA}",
            "motor": None, "checks": [], "motivo": motivo,
            "ruta_lector": lectura.ruta, "diagnostico_lector": lectura.diagnostico,
        }

    mol_canonica, invariantes_canonicas = canonicalizar_hidrogenos(mol)
    if mol_canonica is None:
        return {
            "status": "not_evaluated",
            "label": "NO EVALUADA",
            "detail": (
                "No se pudo reconstruir la representación canónica de hidrógenos "
                f"({invariantes_canonicas.get('motivo')}). {FRASE_OBLIGATORIA}"
            ),
            "motor": None,
            "checks": [],
            "motivo": invariantes_canonicas.get("motivo"),
            "ruta_lector": lectura.ruta,
            "diagnostico_lector": lectura.diagnostico,
            "canonicalization_invariants": invariantes_canonicas,
        }
    mol = mol_canonica

    # Por que no se corrio la bateria completa. Se nombra la causa REAL: decir "no
    # instalado" cuando lo que falta es el receptor seria el tipo de mensaje que hace que
    # nadie arregle nada.
    if not _posebusters_disponible():
        razon_degradacion = "PoseBusters no esta instalado en este entorno"
    elif not receptor_path:
        razon_degradacion = ("no se paso la ruta del receptor, y la configuracion `dock` "
                             "la necesita para los controles intermoleculares")
    else:
        razon_degradacion = None

    if razon_degradacion is None:
        try:
            from posebusters import PoseBusters
            rec_pdb = receptor_como_pdb(receptor_path)
            if rec_pdb is None:
                raise FileNotFoundError("receptor ilegible o vacio")
            try:
                df = PoseBusters(config="dock").bust(
                    mol_pred=[mol], mol_true=None, mol_cond=str(rec_pdb))
            finally:
                # ``receptor_como_pdb`` materializa un temporal cuando recibe
                # PDBQT. Antes quedaba huérfano por cada pose evaluada.
                try:
                    if Path(rec_pdb).resolve() != Path(receptor_path).resolve():
                        Path(rec_pdb).unlink(missing_ok=True)
                except OSError:
                    pass
            fila = df.iloc[0].to_dict()
            clasif = {k: clasificar_resultado_pb(v) for k, v in fila.items()}
            fallan_quimica = sorted(k for k, e in clasif.items()
                                    if e == "FALLA" and k not in CHECKS_DE_CARGA)
            fallan_carga = sorted(k for k, e in clasif.items()
                                  if e == "FALLA" and k in CHECKS_DE_CARGA)
            no_eval = sorted(k for k, e in clasif.items() if e == "NO_EVALUADO")

            if fallan_quimica:
                estado, etiqueta = "failed", "CONTROLES FALLIDOS"
            elif fallan_carga or no_eval:
                # Nada de quimica fallo, pero la bateria no corrio entera. Eso es
                # REVISION, no aprobado: declararlo `passed` seria afirmar lo que no se
                # midio, que es justo lo que la frase obligatoria previene.
                estado, etiqueta = "review", "REVISIÓN NECESARIA"
            else:
                estado, etiqueta = "passed", "CONTROLES SUPERADOS"

            detalle = (f"PoseBusters en configuracion `dock` -sin verdad de terreno, que "
                       f"en produccion no existe-. ")
            if fallan_quimica:
                detalle += (f"Fallan {len(fallan_quimica)} controles de quimica o "
                            f"geometria: {', '.join(fallan_quimica)}. ")
            else:
                detalle += "Ningun control de quimica o geometria falla. "
            if fallan_carga:
                detalle += (f"No se pudieron cargar entradas ({', '.join(fallan_carga)}), "
                            f"asi que los controles intermoleculares NO se evaluaron: eso "
                            f"es un problema de la entrada, no de la pose. ")
            if no_eval:
                # Se NOMBRAN. «2 controles no evaluables» no le dice a nadie si lo que
                # falto fue la energia interna o la distancia a las aguas.
                detalle += (f"{len(no_eval)} controles no devolvieron un booleano y NO se "
                            f"cuentan como superados: {', '.join(no_eval)}. ")
            return {
                "status": estado, "label": etiqueta,
                "detail": detalle + FRASE_OBLIGATORIA,
                "motor": f"posebusters:{_version_posebusters()}:dock",
                "checks": [{"check": k, "estado": clasif[k]} for k in fila],
                "checks_que_fallan": fallan_quimica,
                "checks_de_carga_fallidos": fallan_carga,
                "checks_no_evaluados": no_eval,
                "ruta_lector": lectura.ruta,
                "diagnostico_lector": lectura.diagnostico,
                "canonicalization_invariants": invariantes_canonicas,
            }
        except Exception as exc:                               # noqa: BLE001
            log.warning("PoseBusters fallo, se degrada al proxy RDKit: %s", exc)
            razon_degradacion = f"PoseBusters fallo al ejecutarse ({type(exc).__name__})"

    # Escalon 2: el proxy RDKit. NO es el control de PoseBusters y no se presenta como tal.
    ctrl = proxy_tension_rdkit(mol)
    if ctrl["estado"] == "NO_EVALUADO":
        return {
            "status": "not_evaluated", "label": "NO EVALUADA",
            "detail": f"El proxy energetico RDKit no pudo ejecutarse "
                      f"({ctrl.get('motivo')}). {FRASE_OBLIGATORIA}",
            "motor": MOTOR_PROXY, "checks": [ctrl],
            "ruta_lector": lectura.ruta,
            "diagnostico_lector": lectura.diagnostico,
            "canonicalization_invariants": invariantes_canonicas,
        }
    pasa = ctrl["estado"] == "PASA"
    return {
        # SIEMPRE `review`, PASE O FALLE EL PROXY, y no por prudencia: por medicion.
        #
        # Aprobado no puede ser, porque el resto de la bateria no se ejecuto; declararlo
        # `passed` seria el error que la frase obligatoria previene. Pero FALLIDO tampoco.
        # `PROD-PV-H-01` midio el proxy contra el evaluador oficial sobre 232 poses: discrepa
        # en 33 -el 14.2%- y las 33 van en la MISMA direccion, proxy FALLA donde el oficial
        # PASA. No es ruido: son FALSOS RECHAZOS. Decirle a un usuario que su pose falla la
        # fisica apoyandose en una cantidad que rechaza el 14% de las poses buenas seria
        # fabricar una alarma. La regla estaba preregistrada en el gate de ese artefacto.
        "status": "review",
        "label": "REVISIÓN NECESARIA",
        "detail": (
            f"Bateria completa no ejecutada: {razon_degradacion}. Solo se corrio un "
            f"PROXY ENERGETICO RDKit NO CALIBRADO, que **no** es el control "
            f"`internal_energy` de PoseBusters: usa MMFF en vez de UFF, "
            f"{N_CONFORMEROS_PROXY} conformeros en vez de {PB_DOCK_N_CONFORMEROS:.0f} y una "
            f"razon distinta, y su umbral no esta calibrado contra ninguna medicion. "
            f"Razon {ctrl['razon']} contra un umbral de {ctrl['umbral']}: "
            f"{'dentro' if pasa else 'FUERA'} de rango. "
            + ("" if pasa else
               "ESE VALOR FUERA DE RANGO NO ES UN VEREDICTO DE FALLA: `PROD-PV-H-01` midio "
               "que este proxy rechaza el 14.2% de las poses que el control oficial de "
               "PoseBusters aprueba, y siempre en esa direccion. Por eso se reporta como "
               "revision y no como control fallido. ")
            + f"No se evaluaron distancias al receptor, valencias, aromaticidad ni "
              f"planaridad. {FRASE_OBLIGATORIA}"),
        "motor": MOTOR_PROXY,
        "checks": [ctrl],
        # Vacio SIEMPRE: un proxy con 14.2% de falsos rechazos medidos no nombra controles
        # fallidos. Su valor va en `checks`, como diagnostico, no como acusacion.
        "checks_que_fallan": [],
        "proxy_fuera_de_rango": not pasa,
        "ruta_lector": lectura.ruta,
        "diagnostico_lector": lectura.diagnostico,
        "canonicalization_invariants": invariantes_canonicas,
    }
