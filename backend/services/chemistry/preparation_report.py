"""Diff `fuente -> preparado`, por ruta de ejecucion.

Implementa la capacidad P0 de `docs/53_MAPA_ALINEACION_PRODUCTO.md` §6.2: responder
que atomos, residuos, aguas, metales y heteroatomos se perdieron o se transformaron al
convertir una estructura depositada en el receptor que realmente se ejecuta.

Por que existe, medido y no supuesto. `REC-12-R1` establecio que la fuente limpiada de
PDBBind ocultaba la pregunta, y la auditoria del 2026-08-22 encontro **tres politicas de
heteroatomos distintas y ninguna declarada**:

  - dataset experimental (`data/molflex_train_v2/*/rec.pdbqt`): conserva todo;
  - producto, docking (`services/docking/preparer.py`): elimina todas las aguas y, en la
    practica, todos los metales, porque su puerta de conservacion depende de un
    `cofactors_whitelist` vacio en los 380 targets del catalogo;
  - producto, MM-GBSA (`services/chemistry/molchamb_v2.py:52`): elimina todo.

Este modulo NO decide ni corrige nada. Observa, clasifica y emite alertas. La resolucion
de una ambiguedad es una decision humana registrada, y el §2.1 del `docs/53` declara que
eso es permanente: no hay experimento pendiente que vaya a automatizarlo.

El vocabulario de especies vive en `backend/data/site_species_vocabulary.json` como DATO
VERSIONADO. Su `vocabulary_version` viaja en el reporte porque un cambio de listas
reclasifica corridas ya emitidas.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict, field
from functools import lru_cache
from math import sqrt
from pathlib import Path
from typing import Any, Iterable, Literal

_VOCAB_PATH = Path(__file__).resolve().parents[2] / "data" / "site_species_vocabulary.json"

Route = Literal["docking", "mmgbsa", "dataset_experimental", "desconocida"]

# Categorias de especie. LIGANDO_O_DESCONOCIDO es deliberadamente ancha: una especie que
# no esta en ninguna lista NO se promueve a cofactor, se marca para revision.
CATEGORIAS = (
    "AGUA", "METAL", "COFACTOR_CONOCIDO", "ADITIVO",
    "RESIDUO_ESTANDAR", "RESIDUO_MODIFICADO", "LIGANDO_O_DESCONOCIDO",
)

# Disposiciones. PARCIAL es la mas informativa: la especie sobrevivio en unas copias y en
# otras no, que suele significar que la preparacion se quedo con una sola cadena.
DISPOSICIONES = ("CONSERVADA", "ELIMINADA", "PARCIAL")

RADIO_SITIO_A = 8.0
# Solapamiento con el ligando: por debajo de esto, el HETATM ES el ligando. Mismo valor
# que el `TOL` del modulo sellado de REC-12.
TOL_LIGANDO_A = 0.5


@lru_cache(maxsize=1)
def cargar_vocabulario(path: str | None = None) -> dict[str, Any]:
    p = Path(path) if path else _VOCAB_PATH
    return json.loads(p.read_text(encoding="utf-8"))


def _sets(vocab: dict[str, Any]) -> dict[str, set[str]]:
    return {
        k: {s.strip().upper() for s in vocab.get(k, [])}
        for k in ("waters", "metals", "known_cofactors", "modified_residues",
                  "additives", "standard_residues")
    }


def clasificar(resname: str, vocab: dict[str, Any] | None = None) -> str:
    """Categoria de una especie por nombre de residuo.

    El orden importa y es deliberado: agua, metal y residuo estandar antes que nada,
    porque son inequivocos; cofactor conocido antes que aditivo, porque un cofactor mal
    clasificado como aditivo se pierde en silencio y ese es el fallo caro; y lo que no
    encaja en ninguna lista cae en LIGANDO_O_DESCONOCIDO, que exige revision humana.
    """
    v = _sets(vocab or cargar_vocabulario())
    r = resname.strip().upper()
    if r in v["waters"]:
        return "AGUA"
    if r in v["metals"]:
        return "METAL"
    if r in v["standard_residues"]:
        return "RESIDUO_ESTANDAR"
    if r in v["modified_residues"]:
        return "RESIDUO_MODIFICADO"
    if r in v["known_cofactors"]:
        return "COFACTOR_CONOCIDO"
    if r in v["additives"]:
        return "ADITIVO"
    return "LIGANDO_O_DESCONOCIDO"


# ── Lectura de estructuras ────────────────────────────────────────────────────

@dataclass(frozen=True)
class Atomo:
    record: str
    nombre: str
    resname: str
    cadena: str
    resseq: str
    x: float
    y: float
    z: float

    @property
    def clave_residuo(self) -> tuple[str, str, str]:
        return (self.resname, self.cadena, self.resseq)

    @property
    def es_hidrogeno(self) -> bool:
        """Heuristica por nombre de atomo, valida en PDB y PDBQT.

        Existe porque el conteo bruto de atomos NO es interpretable entre formatos:
        `1gwv` pasa de 4820 a 2976 atomos al prepararse, lo que parece una perdida
        enorme, y son 2475 pesados en los dos lados. Los 1844 que 'faltan' son
        hidrogenos no polares que el PDBQT no lleva. Reportar esa cifra como perdida
        seria dar una alarma falsa en cada complejo.
        """
        n = self.nombre
        return bool(n) and (n[0] == "H" or (len(n) > 1 and n[0].isdigit() and n[1] == "H"))


def leer_atomos(texto: str) -> list[Atomo]:
    """Parsea ATOM/HETATM de un PDB o PDBQT por columnas fijas.

    Sirve para los dos formatos porque las columnas 1-54 son identicas; lo que cambia en
    PDBQT son las columnas finales (carga y tipo AutoDock), que aqui no se usan. Esa es
    justamente la trampa que hay que evitar: el tipo AutoDock de las columnas 77-78 NO es
    el simbolo quimico -`NA` alli es un nitrogeno aceptor, no sodio-, asi que este modulo
    clasifica SOLO por nombre de residuo.
    """
    fuera: list[Atomo] = []
    for l in texto.splitlines():
        if not l.startswith(("ATOM", "HETATM")) or len(l) < 54:
            continue
        try:
            fuera.append(Atomo(
                record=l[:6].strip(),
                nombre=l[12:16].strip(),
                resname=l[17:20].strip().upper(),
                cadena=l[21:22].strip() or "_",
                resseq=l[22:27].strip(),
                x=float(l[30:38]), y=float(l[38:46]), z=float(l[46:54]),
            ))
        except ValueError:
            continue
    return fuera


def _sha256(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8", "replace")).hexdigest()


def _cerca(a: Atomo, puntos: list[tuple[float, float, float]], radio: float) -> bool:
    r2 = radio * radio
    for px, py, pz in puntos:
        if (a.x - px) ** 2 + (a.y - py) ** 2 + (a.z - pz) ** 2 <= r2:
            return True
    return False


# ── Reporte ───────────────────────────────────────────────────────────────────

@dataclass
class Especie:
    resname: str
    categoria: str
    copias_fuente: int
    copias_preparado: int
    atomos_fuente: int
    atomos_preparado: int
    disposicion: str
    en_sitio: bool
    copias_en_sitio: int = 0

    def dict(self) -> dict[str, Any]:
        return asdict(self)


def _inventario(atomos: Iterable[Atomo], vocab: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Inventario por especie contando SOLO atomos pesados (ver `Atomo.es_hidrogeno`)."""
    inv: dict[str, dict[str, Any]] = {}
    for a in atomos:
        if a.es_hidrogeno:
            continue
        e = inv.setdefault(a.resname, {"atomos": 0, "copias": set(),
                                       "categoria": clasificar(a.resname, vocab)})
        e["atomos"] += 1
        e["copias"].add(a.clave_residuo)
    return inv


def preparation_report(
    fuente_pdb: str,
    preparado: str,
    ruta: Route = "desconocida",
    ligando_coords: list[tuple[float, float, float]] | None = None,
    radio_sitio: float = RADIO_SITIO_A,
    vocab_path: str | None = None,
) -> dict[str, Any]:
    """Compara la estructura depositada con la que realmente se ejecuta.

    Args:
        fuente_pdb: contenido de la estructura de origen (PDB).
        preparado: contenido del receptor ejecutado (PDB o PDBQT).
        ruta: que camino del producto produjo `preparado`.
        ligando_coords: atomos pesados del ligando, para delimitar el sitio. Si es None,
            el reporte se emite igual pero sin la dimension `en_sitio`, y se declara.
        radio_sitio: radio del sitio en A. 8.0 es el de `REC-12` y `REC-08-EXT`.

    Returns:
        Diccionario serializable con inventario por especie, diff, alertas y hashes.
        No decide nada: `ESPECIE_DEL_SITIO_ELIMINADA` es una alerta, no una correccion.
    """
    vocab = cargar_vocabulario(vocab_path)
    a_fuente = leer_atomos(fuente_pdb)
    a_prep = leer_atomos(preparado)

    inv_f = _inventario(a_fuente, vocab)
    inv_p = _inventario(a_prep, vocab)
    pesados_f = sum(1 for a in a_fuente if not a.es_hidrogeno)
    pesados_p = sum(1 for a in a_prep if not a.es_hidrogeno)

    sitio_conocido = bool(ligando_coords)
    puntos = list(ligando_coords or [])
    en_sitio_por_especie: dict[str, int] = {}
    if sitio_conocido:
        for a in a_fuente:
            if a.record != "HETATM":
                continue
            if not _cerca(a, puntos, radio_sitio):
                continue
            # El propio ligando cristalografico figura como HETATM junto al sitio -es el
            # sitio-, y sacarlo del receptor es lo CORRECTO, no una perdida. Se descarta
            # por solapamiento exacto, igual que hace el modulo sellado de REC-12. Sin
            # esto el conteo daba 110 de 116 complejos "perdiendo una especie del sitio"
            # en las TRES rutas, que es una alarma sin contenido.
            if _cerca(a, puntos, TOL_LIGANDO_A):
                continue
            en_sitio_por_especie[a.resname] = en_sitio_por_especie.get(a.resname, 0) + 1

    especies: list[Especie] = []
    for resname in sorted(set(inv_f) | set(inv_p)):
        f = inv_f.get(resname, {"atomos": 0, "copias": set(),
                                "categoria": clasificar(resname, vocab)})
        p = inv_p.get(resname, {"atomos": 0, "copias": set()})
        cf, cp = len(f["copias"]), len(p.get("copias", set()))
        if cp == 0 and cf > 0:
            disp = "ELIMINADA"
        elif cp < cf:
            disp = "PARCIAL"
        else:
            disp = "CONSERVADA"
        especies.append(Especie(
            resname=resname, categoria=f["categoria"],
            copias_fuente=cf, copias_preparado=cp,
            atomos_fuente=f["atomos"], atomos_preparado=p.get("atomos", 0),
            disposicion=disp,
            en_sitio=resname in en_sitio_por_especie,
            copias_en_sitio=en_sitio_por_especie.get(resname, 0),
        ))

    def _cuenta(cat: str, disp: str | None = None, solo_sitio: bool = False) -> list[str]:
        return sorted(e.resname for e in especies
                      if e.categoria == cat
                      and (disp is None or e.disposicion == disp)
                      and (not solo_sitio or e.en_sitio))

    perdidas_sitio = sorted(
        e.resname for e in especies
        if e.en_sitio and e.disposicion in ("ELIMINADA", "PARCIAL")
        and e.categoria in ("COFACTOR_CONOCIDO", "METAL", "LIGANDO_O_DESCONOCIDO")
    )
    por_revisar = sorted(
        e.resname for e in especies
        if e.categoria == "LIGANDO_O_DESCONOCIDO" and (e.en_sitio or not sitio_conocido)
    )

    cadenas_f = {a.cadena for a in a_fuente}
    cadenas_p = {a.cadena for a in a_prep}

    alertas: list[dict[str, Any]] = []

    def _alerta(codigo: str, detalle: Any) -> None:
        alertas.append({"codigo": codigo, "detalle": detalle})

    aguas_f = [e for e in especies if e.categoria == "AGUA"]
    # Firma de fuente limpiada, y es literalmente el G1 que fallo en REC-12: la fraccion
    # de estructuras con algun HETATM que no sea agua ni metal. PDBBind entrega su
    # `_protein.pdb` con aguas y metales y SIN el resto, asi que un cero aqui teniendo
    # aguas es la marca de que la fuente ya paso por una limpieza que borro la evidencia.
    het_no_agua_no_metal = sum(
        e.copias_fuente for e in especies
        if e.categoria in ("COFACTOR_CONOCIDO", "ADITIVO", "LIGANDO_O_DESCONOCIDO")
    )
    if het_no_agua_no_metal == 0:
        _alerta("FUENTE_LIMPIADA_O_INCOMPLETA",
                {"hetatm_no_agua_no_metal_en_fuente": 0,
                 "aguas_en_fuente": sum(e.copias_fuente for e in aguas_f),
                 "nota": "la fuente no contiene un solo heteroatomo que no sea agua o "
                         "metal. Es la firma del _protein.pdb de PDBBind, cuyo G1 en "
                         "REC-12 dio 0.0208 y por eso aquel inventario NO SE LEYO. "
                         "Con la entrada de RCSB, REC-12-R1 midio 0.9914"})
    if perdidas_sitio:
        _alerta("ESPECIE_DEL_SITIO_ELIMINADA", perdidas_sitio)
    if por_revisar:
        _alerta("COFACTOR_O_HETEROATOMO_POR_REVISAR", por_revisar)
    if cadenas_f - cadenas_p:
        _alerta("CADENA_O_HUECO_CERCA_DEL_SITIO",
                {"cadenas_perdidas": sorted(cadenas_f - cadenas_p)})
    if ruta == "desconocida":
        _alerta("AGUAS_SIN_POLITICA_DECLARADA",
                "la ruta de ejecucion no se declaro, asi que la politica de aguas "
                "aplicada no es conocida")
    if not sitio_conocido:
        _alerta("SITIO_NO_DELIMITADO",
                "sin coordenadas de ligando no se puede decir que especies eran del "
                "sitio; el inventario es global")
    _alerta("ASSEMBLY_NO_DECLARADA",
            "la unidad asimetrica depositada no es necesariamente la assembly biologica; "
            "REC-08 gobierna esa cuestion y este reporte no la resuelve")

    return {
        "reporte": "preparation_report",
        "version": "1.0.0",
        "vocabulary_version": cargar_vocabulario(vocab_path)["vocabulary_version"],
        "ruta": ruta,
        "radio_sitio_A": radio_sitio if sitio_conocido else None,
        "hashes": {"fuente_sha256": _sha256(fuente_pdb),
                   "preparado_sha256": _sha256(preparado)},
        "totales": {
            # La cifra que importa es la de PESADOS. El bruto incluye hidrogenos, que el
            # PDBQT no lleva completos, y compararlo entre formatos da falsas alarmas.
            "atomos_pesados_fuente": pesados_f,
            "atomos_pesados_preparado": pesados_p,
            "atomos_pesados_perdidos": pesados_f - pesados_p,
            "atomos_brutos_fuente": len(a_fuente),
            "atomos_brutos_preparado": len(a_prep),
            "nota_hidrogenos": ("la diferencia en bruto suele ser hidrogenos no polares "
                                "que el PDBQT no conserva; no es perdida de informacion"),
            "cadenas_fuente": sorted(cadenas_f), "cadenas_preparado": sorted(cadenas_p),
        },
        "politica_observada": {
            "aguas": ("elimina_todas"
                      if all(e.disposicion == "ELIMINADA" for e in aguas_f) and aguas_f
                      else "conserva" if aguas_f else "no_habia"),
            "metales_eliminados": _cuenta("METAL", "ELIMINADA"),
            "metales_conservados": _cuenta("METAL", "CONSERVADA"),
            "cofactores_eliminados": _cuenta("COFACTOR_CONOCIDO", "ELIMINADA"),
            "cofactores_conservados": _cuenta("COFACTOR_CONOCIDO", "CONSERVADA"),
        },
        "especies": [e.dict() for e in especies],
        "resumen_sitio": {
            "delimitado": sitio_conocido,
            "especies_del_sitio_perdidas": perdidas_sitio,
            "por_revisar": por_revisar,
        },
        "alertas": alertas,
        "declaracion": (
            "Este reporte OBSERVA; no corrige receptores ni afirma relevancia funcional. "
            "Que una especie sea COFACTOR_CONOCIDO no implica que el sitio la necesite "
            "(prohibicion de REC-12-R1-PRE). La resolucion de LIGANDO_O_DESCONOCIDO es "
            "una decision humana registrada y permanente: no hay experimento pendiente "
            "que la automatice (docs/53 §2.1)."
        ),
    }
