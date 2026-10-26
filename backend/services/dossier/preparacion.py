"""
Auditoría de preparación de UNA corrida: lo que enseña la pestaña Preparación.

# Qué responde

¿Qué le falta a esta corrida para que su sistema estructural se pueda entregar
a un cálculo posterior —FEP+, OpenFE u otro— sin que el receptor tenga que
adivinar las decisiones que la definen? Cinco bloques, los mismos de la
interfaz: receptor, ligando, pose, entorno del sitio y procedencia.

# Qué NO afirma

Que el sistema esté listo para FEP. `AGENTS.md` lo dice sin rodeos: hasta
superar `FEP-05` y `FEP-06` la formulación correcta es «auditor de readiness
para FEP en desarrollo». Por eso el estado global tiene techo en REVISIÓN
aunque todos los requisitos tengan dato: TRANSFERIBLE con alcance FEP sólo
puede emitirse con `TRANSFERENCIA_FEP_DEMOSTRADA`, y esa constante sólo puede
valer `True` con un `FEP-06` sellado GO. Lo vigila
`tests/test_preparacion_no_afirma_transferencia_fep.py`, al estilo de ENG-001.

# De dónde sale cada dato

De lo que la corrida SERIALIZÓ: `execution_provenance`, `receptor_prep`,
`ligand_state` y la evidencia de poses que ya interpretó el dossier. Nada se
reconstruye: un receptor preparado antes de registrar el diff de heteroátomos
sale NO_EVALUADO, no con el diff de la receta de hoy. Los requisitos se
seleccionan por clave estable y por datos crudos, nunca por la etiqueta en
castellano de un campo del dossier.

# Cómo se agrega

    imprescindible sin dato o en ABSTENCIÓN     → BLOQUEADO
    cualquier otro requisito no afirmativo      → REVISIÓN
    NO_APLICA                                   → no cuenta

Un requisito imprescindible en REVISAR —el tautómero con varios estados, una
pose con la batería incompleta— es una decisión científica abierta, no
evidencia que falte: pide revisión, no bloquea. Es la misma distinción que la
leyenda de la interfaz («Falta evidencia imprescindible» frente a «Hay una
decisión científica abierta»).

La comprobación previa no guarda los controles que pasan
(`frontend/lib/cases/schema.ts`), así que su ausencia de códigos se registra
como tal y nunca como PASA.

# Decisiones del investigador

Una decisión registrada sobre un requisito que pide revisión lo resuelve: el
investigador vio la incertidumbre, la asumió y dejó escrito por qué. Viaja en
`projection.decisions` con el código `preparacion:<clave>` y la huella
`tarea:<task_id>`: decide sobre ESTA corrida, y no se aplica a otra del mismo
caso. Sin justificación no resuelve nada.

Sobre un requisito que BLOQUEA se registra igual, pero no lo levanta: un zinc
retirado a 2 Å del ligando o un hueco en el sitio no se arreglan declarándolos,
hay que cambiar el sistema. El dato del requisito nunca cambia; la decisión va
al lado.

# Revisión rutinaria y revisión del caso

Una revisión es RUTINARIA cuando la pide toda corrida que pasa por esta ruta,
con el mismo motivo, sin que la dispare nada medido en el caso: la protonación
por plantilla, el bolsillo recortado de un receptor multicadena, el catálogo de
demostración, el commit que el instalador no declara. Medido en el panel del
2026-10-10, esas revisiones salían en las 11 corridas y el veredicto global no
distinguía una aspirina sin nada que decidir de una warfarina con el tautómero
y la estereoquímica abiertos.

La rutinaria sigue abierta, cuenta en `en_revision` y se puede decidir; sólo se
nombra aparte (`en_revision_rutinaria`, `solo_rutinaria`). Lo que la convierte en
revisión del caso es un dato medido: una histidina que toca al ligando, un agua
que lo puentea con la proteína. Ante la duda —la corrida no se pudo medir— es del
caso: llamar rutina a algo que podría ser del caso sería esconderlo.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Literal

from services.dossier.model import (
    Campo,
    CaseDossier,
    _campo_dato,
    _campo_de_estado_quimico,
    _v,
    campo_de_la_seccion,
    campos_del_estado_del_ligando,
    relacion_comprobada,
)
from services.dossier.contexto_estructural import (
    UMBRAL_AGUA_A,
    UMBRAL_ESPECIE_A,
    UMBRAL_PUENTE_H_A,
    UMBRAL_RESIDUO_A,
    UMBRAL_SOLAPAMIENTO_A,
    UMBRAL_TM,
    VENTANA_TM,
    ContextoEstructural,
)
from services.dossier.preparacion_confianza import campo_de_confianza
from services.dossier.preparacion_entrada import SEPARADOR, partes_de_entrada
from services.dossier.schemas import CaseProjection
from services.dossier.taxonomy import Estado

PREPARACION_SCHEMA = "preparacion/v1"

#: Sólo puede valer `True` con `FEP-06` sellado GO: un tercero reconstruye el paquete y ejecuta el
#: cálculo. Las pre-pruebas `FEP-06-PRE*` no cuentan. Hasta entonces ninguna auditoría emite
#: TRANSFERIBLE con alcance FEP.
TRANSFERENCIA_FEP_DEMOSTRADA = False

ALCANCE = "Auditor de readiness para FEP en desarrollo"

BLOQUES = ("receptor", "ligando", "pose", "entorno", "procedencia")

EstadoGlobal = Literal["BLOQUEADO", "REVISION", "TRANSFERIBLE"]
EstadoBloque = Literal["BLOQUEADO", "REVISION", "REGISTRADO"]

#: Especies del diff cuya retirada junto al sitio deja un receptor que no es
#: el de la estructura: bloquea hasta que alguien decida sobre ellas.
_CATEGORIAS_QUE_BLOQUEAN = ("metal", "organic_cofactor")

#: Cofactores que un ligando no desplaza: se une a su lado. Si la corrida declaró
#: uno de ellos como ligando del cristal, la preparación lo retiró como si fuera el
#: ligando y el sitio acoplado quedó sin él (3SRW: NADP; COX-1/2 y CYP2D6: hemo).
#: Bloquea igual que cualquier otro cofactor retirado. El resto de los cofactores
#: que el producto conserva (ATP, ADP, SAM, NAD) los desplaza un inhibidor
#: competitivo, así que retirarlos pide revisión y no bloquea. Es un subconjunto de
#: `preparer.ORGANIC_COFACTORS_KEPT`; lo vigila una prueba.
_COFACTORES_NO_DESPLAZABLES = frozenset({"HEM", "HEC", "FAD", "FMN", "NAP", "SF4", "FES", "F3S"})

#: Los hashes de UNA corrida de Vina. En ensamble cada conformación lleva los suyos
#: en `execution_provenance.por_conformacion` y el receptor es común a todas.
_HASHES_POR_CONFORMACION = ("ligand_input_sha256", "ligand_pdbqt_sha256", "poses_sha256", "log_sha256")

# ── Motivos de la revisión rutinaria ─────────────────────────────────
# Frases enteras, sin cifras sueltas: cada una tiene su traducción exacta (o su
# plantilla, si lleva el umbral).

RUTINA_PROTONACION_USUARIO = (
    "La pide toda corrida con un receptor que ya trae su protonación: la decisión es de quien lo preparó.")
RUTINA_RECORTE = (
    "La pide toda corrida con un receptor de varias cadenas: Vina recibe siempre un bolsillo recortado.")
RUTINA_DEMOSTRACION = "La pide toda corrida contra un receptor del catálogo de demostración."
RUTINA_COMMIT = (
    "La pide toda corrida del instalador o de un árbol con cambios sin commitear, que no declaran commit. "
    "La versión de la aplicación queda en «Versiones de la corrida».")
RUTINA_PREVIAS_ADVERTENCIAS = (
    "Son advertencias de la ruta o que esta auditoría vuelve a medir junto al ligando: receptor sin "
    "calibrar, especies retiradas de la estructura y protonación del receptor.")
RUTINA_PREVIAS_SIN_EVALUAR = (
    "La comprobación previa deja estos controles sin evaluar en toda corrida, como deuda declarada, o "
    "antes de preparar el receptor por primera vez.")
HIS_PLANTILLA_SIN_MIRAR = (
    "La plantilla eligió su estado sin mirar el sitio: HID, HIE o HIP cambian los puentes de hidrógeno "
    "que forma con el ligando.")
HIS_METAL_CON_H = "His que coordinan un metal conservado con el hidrógeno en el nitrógeno que lo coordina: {lista}."
HIS_METAL_NO_EXISTE = (
    "Ese estado no existe: el nitrógeno unido al metal no lleva hidrógeno, y la plantilla que corresponde lo "
    "pone en el otro nitrógeno del anillo.")
ACCION_HIS_METAL = (
    "Antes de un cálculo posterior, protona esa His con el hidrógeno en el otro nitrógeno del anillo (HID si "
    "coordina por NE2, HIE si coordina por ND1) y súbela como receptor ya preparado, o retira el metal si no "
    "forma parte de la hipótesis.")
CRISTAL_INCOMPLETO = (
    "El depósito declara que al ligando del cristal {ligando} le faltan átomos (REMARK 610): la comparación de la pose "
    "con él y las distancias medidas desde él son parciales.")
CYS_METAL_CON_H ="Cys que coordinan un metal conservado como tiol neutro, con el HG en el azufre que lo coordina: {lista}."
CYS_METAL_TIOLATO = (
    "Una cisteína que coordina un metal es un tiolato: la plantilla le puso el hidrógeno sin mirar el metal.")
ACCION_CYS_METAL = (
    "Antes de un cálculo posterior, desprotona esa Cys (tiolato, CYM) y parametriza su enlace con el metal, y "
    "súbela como receptor ya preparado, o retira el metal si no forma parte de la hipótesis.")
HIDROGENOS_DEPOSITADOS_RETIRADOS = (
    "El depósito traía hidrógenos que contradecían su propia estructura y se retiraron antes de Meeko: "
    "{his} His sin hidrógeno en ND1 ni NE2 (la plantilla eligió su estado como en un depósito sin hidrógenos) "
    "y {cys} HG de cisteínas con puente disulfuro.")
RAZON_SOLO_RUTINARIA = (
    "Nada propio de este caso pide revisión: sólo quedan las revisiones que esta ruta pide en toda corrida. "
    "Aun resueltas, la transferencia a un cálculo FEP no está demostrada: FEP-06 sigue sin sellar.")

#: Advertencias previas que no dicen nada del caso: el receptor sin calibrar (todos en
#: 1.0.2), la retirada de especies de TODA la estructura (las del sitio las mide
#: Entorno desde el ligando) y la protonación por plantilla (la mide Receptor). Un
#: metal retirado, un volumen de caja o una advertencia química del ligando sí lo son.
_ADVERTENCIAS_PREVIAS_DE_LA_RUTA = frozenset({
    "CALIBRACION_RECEPTOR", "ESPECIES_DEL_SITIO_RETIRADAS", "RECEPTOR_PROTONACION_DECLARADA",
})
#: Controles previos que quedan sin evaluar sin que dependa del caso: las tres deudas
#: declaradas (`preflight._declared_debts`, lo vigila una prueba) y los dos que no
#: pueden leerse antes de que exista el receptor preparado de la primera corrida.
_SIN_EVALUAR_PREVIOS_DE_LA_RUTA = frozenset({
    "LIGANDO_PROTONACION_TAUTOMERO", "ASSEMBLY_BIOLOGICA", "HUECOS_CERCA_DEL_SITIO",
    "RECEPTOR_PREPARADO_DISPONIBLE", "RECEPTOR_PROTONACION_DECLARADA",
})


@dataclass(frozen=True)
class Requisito:
    """Un requisito con clave estable, su dato, de dónde sale y si es imprescindible."""

    clave: str
    campo: Campo
    fuente: str
    imprescindible: bool
    ubicacion: list[dict[str, Any]] | None = None
    accion_recomendada: str | None = None
    #: La acción, en datos: con qué volver a evaluar (`{"tautomero", "smiles"}`). La interfaz la ofrece como botón que
    #: abre el caso en Evaluación con eso elegido; el texto de `accion_recomendada` sigue siendo el que se lee.
    reevaluar: list[dict[str, str]] | None = None
    #: Decisión del investigador sobre este requisito en esta corrida: `{"justificacion", "registrada"}`.
    decision: dict[str, Any] | None = None
    #: Si la revisión que pide es rutinaria, por qué: la pide toda corrida de esta ruta.
    rutinaria: str | None = None
    #: Lo que el contexto de ensayo declarado dice de este requisito (`moldesign.contexto_ensayo/1`). No va en
    #: `ubicacion`: esa lista describe huecos del esqueleto y el validador de la interfaz exige esa forma a cada
    #: entrada, así que un caso con ensayo declarado dejaba de abrir Preparación.
    ensayo: dict[str, Any] | None = None

    @property
    def bloquea(self) -> bool:
        estado = self.campo.estado
        if estado == Estado.NO_APLICA:
            return False
        return self.imprescindible and (estado.es_ausencia or estado == Estado.ABSTENCION)

    @property
    def pide_revision(self) -> bool:
        estado = self.campo.estado
        return not (estado.es_afirmativo or estado == Estado.NO_APLICA or self.bloquea or self.decidido)

    @property
    def decidido(self) -> bool:
        """Pedía revisión y alguien decidió con su justificación. Lo que bloquea no se decide."""
        estado = self.campo.estado
        return (self.decision is not None and not self.bloquea
                and not (estado.es_afirmativo or estado == Estado.NO_APLICA))

    def as_dict(self) -> dict[str, Any]:
        return {
            "clave": self.clave,
            **self.campo.as_dict(),
            "fuente": self.fuente,
            "imprescindible": self.imprescindible,
            **({"ubicacion": self.ubicacion} if self.ubicacion is not None else {}),
            **({"accion_recomendada": self.accion_recomendada} if self.accion_recomendada else {}),
            **({"reevaluar": self.reevaluar} if self.reevaluar else {}),
            **({"decision": {**self.decision, "resuelve": self.decidido}} if self.decision else {}),
            **({"rutinaria": {"motivo": self.rutinaria}} if self.rutinaria else {}),
            **({"ensayo": self.ensayo} if self.ensayo is not None else {}),
        }


# ── Utilidades ───────────────────────────────────────────────────────


def _no_evaluado(etiqueta: str, razon: str) -> Campo:
    return Campo(etiqueta, None, Estado.NO_EVALUADO, razon)


def _fila(fila: dict[str, Any], originales: dict[tuple[str, str, str], str] | None = None) -> str:
    nombre = fila.get("name")
    # Un código CCD largo se escribió con un sustituto de tres caracteres para entrar en el PDB clásico:
    # el original va al lado, para que nadie tenga que buscar qué era «Z00».
    original = (originales or {}).get((str(fila.get("chain")), str(fila.get("residue_number")), str(nombre)))
    if original:
        nombre = f"{nombre} [{original}]"
    return (
        f"{nombre} {fila.get('chain')}:{fila.get('residue_number')}"
        f"{fila.get('insertion_code') or ''} ({fila.get('distance_to_box_A')} Å)"
    )


def _originales(prep: Any) -> dict[tuple[str, str, str], str]:
    """(cadena del PDB, número, código sustituto) → código CCD original, de la conversión del mmCIF."""
    salida: dict[tuple[str, str, str], str] = {}
    for fuente in (_v(prep, "entrada"), _v(prep, "origen")):
        conversion = fuente.get("conversion") if isinstance(fuente, dict) else None
        for fila in (conversion or {}).get("residuos_renombrados") or []:
            salida[(str(fila["cadena_pdb"]), str(fila["numero"]), str(fila["pdb"]))] = str(fila["original"])
    return salida


def _tupla(valor: Any) -> str | None:
    if not isinstance(valor, (list, tuple)) or len(valor) != 3:
        return None
    return "(" + ", ".join(f"{float(v):g}" for v in valor) + ")"


def _especie(fila: dict[str, Any], originales: dict[tuple[str, str, str], str], distancia: float | None) -> str:
    """Como `_fila`, con la distancia al ligando en vez de a la caja."""
    nombre = fila.get("name")
    original = originales.get((str(fila.get("chain")), str(fila.get("residue_number")), str(nombre)))
    if original:
        nombre = f"{nombre} [{original}]"
    return (f"{nombre} {fila.get('chain')}:{fila.get('residue_number')}{fila.get('insertion_code') or ''}"
            + (f" ({distancia:g} Å)" if distancia is not None else ""))


def _medidor(contexto: ContextoEstructural | None):
    """Distancia al ligando de una fila de `near_site`, o None si la corrida no se pudo medir."""
    if contexto is None or not contexto.medido:
        return None

    def _d(fila: dict[str, Any]) -> float | None:
        return contexto.especies.get((str(fila.get("chain")), str(fila.get("residue_number")),
                                      str(fila.get("insertion_code") or ""), str(fila.get("name"))))
    return _d


def _medidor_del_sitio(contexto: ContextoEstructural | None):
    """Como `_medidor`, pero desde el ligando del cristal cuando lo hay: metales y cofactores se juzgan con el sitio
    del depósito, no con una pose que cambia con la semilla. Sin cristal, la pose."""
    base = _medidor(contexto)
    if base is None:
        return None

    def _d(fila: dict[str, Any]) -> float | None:
        clave = (str(fila.get("chain")), str(fila.get("residue_number")),
                 str(fila.get("insertion_code") or ""), str(fila.get("name")))
        return contexto.especies_al_cristal.get(clave, base(fila))
    return _d


def _coordinacion_de(contexto: ContextoEstructural | None, fila: dict[str, Any]) -> str | None:
    if contexto is None or not contexto.coordinadas:
        return None
    return contexto.coordinadas.get((str(fila.get("chain")), str(fila.get("residue_number")),
                                     str(fila.get("insertion_code") or ""), str(fila.get("name"))))


def _conformaciones(prov: Any) -> list[dict[str, Any]]:
    """Las conformaciones de una corrida en ensamble; vacío para una corrida de una sola."""
    filas = _v(prov, "por_conformacion")
    return [f for f in filas if isinstance(f, dict)] if isinstance(filas, list) else []


# ── 01 · Receptor y sitio ────────────────────────────────────────────


def _hueco_al_ligando(h: dict[str, Any], contexto: ContextoEstructural | None) -> float | None:
    if contexto is None or not contexto.medido:
        return None
    return contexto.huecos.get((str(h.get("chain")), str(h.get("after")), str(h.get("before"))))


def _hueco_critico(h: dict[str, Any], contexto: ContextoEstructural | None) -> bool:
    """Junto al ligando (≤ UMBRAL_RESIDUO_A) si se midió; si no, el criterio de la caja."""
    distancia = _hueco_al_ligando(h, contexto)
    return bool(h.get("site_critical")) if distancia is None else distancia <= UMBRAL_RESIDUO_A


def _huecos_y_poses(huecos: list[dict[str, Any]], contexto: ContextoEstructural) -> str:
    """Lo que la pose 1 no dice: si otras poses tocan un corte, o si la caja lo alcanza y ninguna llegó.

    La pose 1 y el ligando del cristal deciden si el corte es del sitio. Pero la caja de 5TBO
    alcanza su corte VAL343→GLU356 (a 1,6 Å) aunque esté a 20 Å del inhibidor: Vina busca junto
    a él, y una pose de otro rango que caiga ahí acopla contra el bucle ausente.
    """
    if not contexto.poses_medidas:
        return ""
    rangos = sorted({r for k in contexto.huecos_poses.values() for r in k if r != 1})
    if rangos:
        return (f" {len(rangos)} de las {contexto.poses_medidas} poses guardadas quedan a "
                f"{UMBRAL_RESIDUO_A:g} Å o menos de un corte del esqueleto (rangos {','.join(map(str, rangos))}): "
                "acoplan contra el bucle ausente y no son comparables con las demás.")
    from services.docking.preparer import MARGEN_SITIO_A

    en_la_caja = sum(1 for h in huecos if h.get("site_critical"))
    if en_la_caja:
        return (f" {en_la_caja} corte(s) a {MARGEN_SITIO_A:g} Å o menos de la caja: Vina busca junto a ellos, y "
                f"ninguna de las {contexto.poses_medidas} poses guardadas quedó a {UMBRAL_RESIDUO_A:g} Å o menos.")
    return ""


def _campo_de_huecos(huecos: Any, razon: str | None = None,
                     contexto: ContextoEstructural | None = None) -> Campo:
    """Cortes del esqueleto que midió la preparación (C–N > 2 Å entre consecutivos)."""
    if huecos is None:
        return _no_evaluado(
            "Huecos del esqueleto",
            razon or "La corrida no midió los huecos del esqueleto: su receptor se preparó antes "
            "de registrarlos o se congeló antes. No se reconstruye con la receta de hoy.",
        )
    if not huecos:
        return Campo(
            "Huecos del esqueleto",
            "Ninguno: el esqueleto de las cadenas del receptor es continuo (C–N ≤ 2 Å "
            "entre residuos consecutivos).",
            Estado.REGISTRADO,
        )

    def _hueco(h: dict[str, Any]) -> str:
        declarados = h.get("missing_declared")
        sin_declaracion = "REMARK 465 no declara los residuos ausentes"
        distancia = _hueco_al_ligando(h, contexto)
        return (f"{h.get('chain')}: {h.get('after')} → {h.get('before')} "
                f"(C–N {h.get('c_n_distance_A')} Å"
                + (f"; {declarados} ausente(s) en REMARK 465" if declarados is not None else "; " + sin_declaracion)
                + (f"; {h.get('distance_to_box_A')} Å de la caja)" if distancia is None
                   else f"; {distancia:g} Å del ligando)"))

    if contexto is not None and contexto.medido:
        en_sitio = [h for h in huecos if _hueco_critico(h, contexto)]
        return Campo(
            "Huecos del esqueleto",
            f"{len(huecos)} corte(s) del esqueleto"
            + (f"; {len(en_sitio)} a {UMBRAL_RESIDUO_A:g} Å o menos del ligando: "
               + ", ".join(_hueco(h) for h in en_sitio)
               if en_sitio else
               f"; todos a más de {UMBRAL_RESIDUO_A:g} Å del ligando: " + ", ".join(_hueco(h) for h in huecos)),
            Estado.ABSTENCION if en_sitio else Estado.REVISAR,
            ('Un corte del esqueleto junto al sitio deja una cavidad incompleta o incompatible con el receptor. Un cálculo posterior heredaría el bucle ausente o inventado; reparar o cambiar la estructura es imprescindible.'
             if en_sitio else
             "Lejos del sitio no cambian la cavidad, pero un cálculo con disolvente explícito "
             "necesita esos extremos capados o modelados." + _huecos_y_poses(huecos, contexto)),
            valor_es_clasificacion=True,
        )
    en_sitio = [h for h in huecos if h.get("site_critical")]
    return Campo(
        "Huecos del esqueleto",
        f"{len(huecos)} corte(s) del esqueleto"
        + (f"; {len(en_sitio)} junto al sitio: " + ", ".join(_hueco(h) for h in en_sitio)
           if en_sitio else "; todos lejos del sitio: " + ", ".join(_hueco(h) for h in huecos)),
        Estado.ABSTENCION if en_sitio else Estado.REVISAR,
        ('Un corte del esqueleto junto al sitio deja una cavidad incompleta o incompatible con el receptor. Un cálculo posterior heredaría el bucle ausente o inventado; reparar o cambiar la estructura es imprescindible.'
         if en_sitio else
         "Lejos del sitio no cambian la cavidad, pero un cálculo con disolvente explícito "
         "necesita esos extremos capados o modelados."),
        valor_es_clasificacion=True,
    )


def _requisito_de_entrada(prep: Any) -> list[Requisito]:
    """Cómo llegó el receptor propio: formato, modo, hash y cada conversión. Vacío para el catálogo."""
    partes = partes_de_entrada(prep)
    if not partes:
        return []
    return [Requisito(
        "receptor.entrada",
        Campo("Archivo del receptor", SEPARADOR.join(partes), Estado.REGISTRADO),
        "receptor_prep.entrada · receptor_prep.modo_de_preparacion",
        False,
    )]


def _requisito_de_confianza(prep: Any) -> list[Requisito]:
    """pLDDT de una estructura predicha junto al sitio. Vacío para el catálogo (todo experimental, sin perfil)."""
    prediccion = _v(prep, "prediccion")
    if not isinstance(prediccion, dict):
        return []
    campo, accion = campo_de_confianza(prediccion)
    return [Requisito(
        "receptor.confianza_estructural", campo, "receptor_prep.prediccion", False, accion_recomendada=accion,
    )]


def _cadenas_por_simetria(prep: Any) -> str:
    """« · generada(s) por simetría…: C←A (BIOMT 3)» para las cadenas del receptor que no están en el depósito.

    Sólo las que el receptor acoplado conserva: las demás copias se descartan al recortar al sitio. FEP-06-PRE (P09, 6SXC):
    el paquete decía «sitio entre A+C» sin decir que la C es la A transformada por el operador 3 del REMARK 350.
    """
    ensamblaje = _v(prep, "biological_assembly")
    if not isinstance(ensamblaje, dict):
        return ""
    en_el_receptor = set(_v(prep, "prepared_chains") or []) | set(_v(prep, "site_chains") or [])
    generadas = [g for g in ensamblaje.get("generated_chains") or []
                 if isinstance(g, dict) and (not en_el_receptor or g.get("chain") in en_el_receptor)]
    if not generadas:
        return ""
    return (" · generada(s) por simetría desde el depósito (REMARK 350, BIOMOLECULE 1): "
            + ", ".join(f"{g.get('chain')}←{g.get('from_chain')} (BIOMT {g.get('biomt_operator')})" for g in generadas))


def _bloque_receptor(prov: Any, prep: Any, contexto: ContextoEstructural | None = None) -> list[Requisito]:
    receptor_sha = _v(prov, "receptor_sha256")
    receta = _v(prep, "recipe_hash")
    cadena = _v(prep, "chain")
    sitio = _v(prep, "site_chains") or []
    centro, tamano = _tupla(_v(prov, "box_center")), _tupla(_v(prov, "box_size"))

    # Un receptor propio que no se pudo auditar explica POR QUÉ falta cada dato
    # (`no_disponible`); el catálogo no lo trae y conserva los textos de siempre.
    sin_dato = _v(prep, "no_disponible")
    sin_dato = sin_dato if isinstance(sin_dato, dict) else {}

    retirados = _v(prep, "removed_residues")
    fuera = _v(prep, "cofactors_outside_site") or []
    if retirados is None:
        residuos = _no_evaluado(
            "Residuos retirados por la preparación",
            sin_dato.get("removed_residues")
            or "La corrida no registró qué residuos retiró la preparación del receptor.",
        )
    elif not retirados and not fuera:
        residuos = Campo(
            "Residuos retirados por la preparación",
            "Meeko no retiró residuos y no hubo cofactores sin plantilla fuera del sitio.",
            Estado.REGISTRADO,
        )
    else:
        # Un residuo con la cadena lateral incompleta se trunca antes de Meeko, así que la fila de
        # retirados lleva el nombre truncado (ALA261) y no el del depósito (LYS261). Se encadena la
        # identidad original: FEP-06-PRE (P04) lo vio como un residuo que no estaba en el origen.
        truncado_desde = {
            (str(t.get("chain")), str(t.get("residue_number")), str(t.get("insertion_code") or "")):
            str(t.get("name"))
            for t in (_v(prep, "truncated_sidechains") or []) if isinstance(t, dict)
        }

        def _identidad(r: dict[str, Any]) -> str:
            original = truncado_desde.get(
                (str(r.get("chain")), str(r.get("residue_number")), str(r.get("insertion_code") or "")))
            return f"{original}→{r.get('name')}" if original and original != r.get("name") else str(r.get("name"))

        partes = [f"{r.get('chain')}:{r.get('residue_number')} {_identidad(r)} "
                  f"({r.get('distance_to_box_A')} Å)" for r in retirados]
        partes += [f"{_fila(f, _originales(prep))} {f.get('action')}" for f in fuera]
        encadenados = any("→" in _identidad(r) for r in retirados)
        residuos = Campo(
            "Residuos retirados por la preparación",
            f"{len(partes)} fuera del margen del sitio: " + ", ".join(partes),
            Estado.REVISAR,
            ("Fuera del margen no impiden la corrida, pero el receptor que se entregaría no los contiene. Declarar si "
             "importan para el cálculo siguiente. «X→ALA» o «X→GLY»: el depósito no resolvía la cadena lateral de X, se "
             "truncó y después Meeko retiró el residuo.") if encadenados else
            ("Fuera del margen no impiden la corrida, pero el receptor que se entregaría "
             "no los contiene. Declarar si importan para el cálculo siguiente."),
            valor_es_clasificacion=True,
        )

    # Receta v7: las cadenas laterales que el cristal no resolvía se truncan a ALA
    # o GLY conservando sólo átomos observados (PDBFixer no es reproducible). En
    # el sitio, la cavidad acoplada no es la de la proteína: se declara.
    truncadas = _v(prep, "truncated_sidechains")
    if truncadas is None:
        cadenas_truncadas = _no_evaluado(
            "Cadenas laterales truncadas",
            sin_dato.get("truncated_sidechains")
            or "La corrida no registró qué cadenas laterales incompletas del cristal se "
            "truncaron: su receta es anterior a la v7 o el receptor se congeló antes.",
        )
    elif not truncadas:
        cadenas_truncadas = Campo(
            "Cadenas laterales truncadas",
            "Ninguna: el cristal resolvía todas las cadenas laterales del receptor.",
            Estado.REGISTRADO,
        )
    else:
        medido = contexto is not None and contexto.medido

        def _al_ligando(t: dict[str, Any]) -> float | None:
            if not medido:
                return None
            return contexto.truncadas.get((str(t.get("chain")), str(t.get("residue_number")),
                                           str(t.get("insertion_code") or "")))

        def _en_sitio(t: dict[str, Any]) -> bool:
            distancia = _al_ligando(t)
            return bool(t.get("site_critical")) if distancia is None else distancia <= UMBRAL_RESIDUO_A

        en_sitio = [t for t in truncadas if _en_sitio(t)]

        def _truncada(t: dict[str, Any]) -> str:
            destino = str(t.get("action") or "").split()[-1:] or ["?"]
            distancia = _al_ligando(t)
            cifra = t.get("distance_to_box_A") if distancia is None else f"{distancia:g}"
            return (f"{t.get('chain')}:{t.get('residue_number')}{t.get('insertion_code') or ''} "
                    f"{t.get('name')}→{destino[0]} ({cifra} Å)")

        if medido:
            detalle = (f"; {len(en_sitio)} a {UMBRAL_RESIDUO_A:g} Å o menos del ligando: "
                       + ", ".join(_truncada(t) for t in en_sitio)
                       if en_sitio else f"; todas a más de {UMBRAL_RESIDUO_A:g} Å del ligando")
        else:
            detalle = (f"; {len(en_sitio)} en el sitio: " + ", ".join(_truncada(t) for t in en_sitio)
                       if en_sitio else "; todas fuera del sitio")
        # Las de lejos también, con su identificador: el receptor que se entregaría no las contiene, y P04 de
        # FEP-06-PRE sólo decía «2 truncada(s)» sin decir cuáles (HIS A:4 y LYS A:261 de 1BN1).
        lejos = [t for t in truncadas if t not in en_sitio]
        if lejos:
            detalle += "; resto: " + ", ".join(_truncada(t) for t in lejos)
        cadenas_truncadas = Campo(
            "Cadenas laterales truncadas",
            f"{len(truncadas)} truncada(s)" + detalle,
            Estado.REVISAR,
            "El cristal no resolvía esas cadenas laterales y se truncaron a ALA o GLY, "
            "conservando sólo átomos observados. "
            + ("En el sitio, la cavidad pierde esos grupos: un cálculo posterior tendría "
               "que reconstruirlos, y declararlo, o partir de otra estructura."
               if en_sitio else
               "Fuera del sitio no cambian la cavidad, pero el receptor que se entregaría "
               "no los contiene."),
            valor_es_clasificacion=True,
        )

    diff = _v(prep, "species_diff")
    cerca = _v(diff, "near_site") if isinstance(diff, dict) else None
    excluidas = _v(cerca, "protein_residues_removed") if isinstance(cerca, dict) else None
    if contexto is not None and contexto.medido and contexto.excluidas is not None:
        vecinas = Campo(
            "Cadenas excluidas junto al sitio",
            f"Residuos de proteína fuera del receptor a {UMBRAL_ESPECIE_A:g} Å o menos del ligando, por cadena: "
            + ", ".join(f"{c} {n}" for c, n in contexto.excluidas.items()),
            Estado.REVISAR,
            "Puede ser un sitio entre cadenas o una caja que invade la cadena vecina: el "
            "ligando podría acoplarse contra el hueco que deja.",
            valor_es_clasificacion=True,
        ) if contexto.excluidas else Campo(
            "Cadenas excluidas junto al sitio",
            f"Ninguna: no hay proteína fuera del receptor a {UMBRAL_ESPECIE_A:g} Å o menos del ligando.",
            Estado.REGISTRADO,
        )
    elif not isinstance(excluidas, dict):
        vecinas = _no_evaluado(
            "Cadenas excluidas junto al sitio",
            sin_dato.get("species_diff")
            or "La corrida no registró qué proteína quedó fuera del receptor junto a la caja.",
        )
    elif not isinstance(cerca.get("margin_A"), (int, float)):
        # Sin margen no hay «a X Å o menos de la caja»: antes el formato reventaba con None.
        vecinas = _no_evaluado("Cadenas excluidas junto al sitio", "El diff registrado no declara el margen del sitio.")
    elif not excluidas:
        vecinas = Campo(
            "Cadenas excluidas junto al sitio",
            f"Ninguna: toda la proteína a {cerca.get('margin_A'):g} Å o menos de la caja "
            "está en el receptor.",
            Estado.REGISTRADO,
        )
    else:
        vecinas = Campo(
            "Cadenas excluidas junto al sitio",
            f"A {cerca.get('margin_A'):g} Å o menos de la caja y fuera del receptor: "
            + "; ".join(f"cadena {c}, {n} residuo(s)" for c, n in excluidas.items()),
            Estado.REVISAR,
            "Puede ser un sitio entre cadenas o una caja que invade la cadena vecina: el "
            "ligando podría acoplarse contra el hueco que deja.",
            valor_es_clasificacion=True,
        )

    metodo = _v(prep, "protonation_method")
    declarada = _v(prep, "protonacion_declarada")
    if isinstance(declarada, dict):
        # Receptor ya preparado por quien lo subió: se dice de quién es la decisión.
        comprobada = declarada.get("plantillas_coinciden") is True
        protonacion = Campo(
            "Protonación del receptor",
            "Declarada por el usuario (origen: usuario)",
            Estado.REVISAR,
            ("MolDesign conservó la protonación del archivo y comprobó, residuo a residuo, que Meeko aplicó "
             "las plantillas declaradas. No fija un pH ni decide si es la adecuada para el sitio: la "
             "responsabilidad de esa decisión es de quien preparó el receptor."
             if comprobada else
             "MolDesign usó la protonación del archivo tal como venía y no la modificó. No fija un "
             "pH ni comprueba el estado de histidinas, ácidos y bases del sitio: la responsabilidad "
             "de esa decisión es de quien preparó el receptor."),
            valor_es_clasificacion=True,
        )
    else:
        protonacion = (
            Campo(
                "Protonación del receptor", metodo, Estado.REVISAR,
                "Asignación por plantilla, sin pH experimental: el estado de histidinas, "
                "ácidos y bases del sitio no está validado.",
                valor_es_clasificacion=True,
            ) if metodo else _no_evaluado(
                "Protonación del receptor",
                "La corrida no registró cómo se protonó el receptor.",
            )
        )
        # Hidrógenos del depósito que Meeko no habría podido usar (3KK6, 6S1Z): se dice que se retiraron.
        retirados = [f for f in _v(prep, "deposited_h_removed") or [] if isinstance(f, dict)]
        if retirados and protonacion.razon:
            protonacion = replace(protonacion, razon=protonacion.razon + " " + HIDROGENOS_DEPOSITADOS_RETIRADOS.format(
                his=sum(1 for f in retirados if f.get("name") == "HIS"),
                cys=sum(1 for f in retirados if f.get("name") == "CYS")))

    # Qué plantilla aplicó Meeko a las His del sitio, y estados no estándar: el dato
    # existía en el informe de la preparación y la auditoría no lo enseñaba.
    if contexto is not None and contexto.medido and contexto.plantillas and protonacion.razon:
        his = [f"{r} {plantilla} ({d:g} Å)" for r, entrada, plantilla, d in contexto.plantillas
               if entrada.startswith("HI")]
        otros = [f"{r} {plantilla} ({d:g} Å)" for r, entrada, plantilla, d in contexto.plantillas
                 if not entrada.startswith("HI")]
        protonacion = Campo(
            protonacion.etiqueta, protonacion.valor, protonacion.estado,
            protonacion.razon
            + (f" His a {UMBRAL_RESIDUO_A:g} Å o menos del ligando: {', '.join(his)}." if his else "")
            + (f" Estados no estándar a {UMBRAL_RESIDUO_A:g} Å o menos del ligando: {', '.join(otros)}."
               if otros else ""),
            valor_es_clasificacion=protonacion.valor_es_clasificacion,
        )

    # La protonación por plantilla se revisa en toda corrida. Pasa a ser del caso cuando
    # un nitrógeno de una His toca al ligando: ahí HID, HIE o HIP deciden qué puentes de
    # hidrógeno forma. Sin el informe de plantillas no se sabe, y entonces es del caso.
    rutina_protonacion = None
    if isinstance(declarada, dict):
        rutina_protonacion = RUTINA_PROTONACION_USUARIO
    elif metodo and contexto is not None and contexto.medido and contexto.plantillas is not None:
        en_contacto = [f"{r} {plantilla} ({contexto.anillos_his[r]:g} Å)"
                       for r, _entrada, plantilla, _ in contexto.plantillas
                       if contexto.anillos_his.get(r, UMBRAL_RESIDUO_A) <= UMBRAL_PUENTE_H_A]
        if en_contacto:
            protonacion = replace(protonacion, razon=(
                (protonacion.razon or "")
                + f" Histidina(s) con un nitrógeno del anillo a {UMBRAL_PUENTE_H_A:g} Å o menos del ligando: "
                + ", ".join(en_contacto) + ". " + HIS_PLANTILLA_SIN_MIRAR))
        else:
            rutina_protonacion = ("La pide toda corrida protonada por plantilla, y ninguna histidina tiene un "
                                  f"nitrógeno del anillo a {UMBRAL_PUENTE_H_A:g} Å o menos del ligando.")

    # Un estado de protonación imposible en el receptor que se entrega, esté donde esté: la His
    # que coordina un metal con el H en el nitrógeno coordinante (la His388 de las COX con hemo).
    accion_protonacion = None
    imposibles = [f for f in (contexto.his_al_metal or []) if f[4]] if contexto is not None else []
    if imposibles and protonacion.razon:
        protonacion = replace(protonacion, razon=(
            protonacion.razon + " " + HIS_METAL_CON_H.format(
                lista=", ".join(f"{r} {n}–{m} ({d:g} Å)" for r, n, m, d, _ in imposibles))
            + " " + HIS_METAL_NO_EXISTE))
        rutina_protonacion = None
        accion_protonacion = ACCION_HIS_METAL
    # Lo mismo con la Cys axial de un hemo tiolato (los P450): Meeko le deja el HG del tiol.
    tioles = [f for f in (contexto.cys_al_metal or []) if f[4]] if contexto is not None else []
    if tioles and protonacion.razon:
        protonacion = replace(protonacion, razon=(
            protonacion.razon + " " + CYS_METAL_CON_H.format(
                lista=", ".join(f"{r} {n}–{m} ({d:g} Å)" for r, n, m, d, _ in tioles))
            + " " + CYS_METAL_TIOLATO))
        rutina_protonacion = None
        accion_protonacion = (accion_protonacion + " " + ACCION_CYS_METAL) if accion_protonacion else ACCION_CYS_METAL

    huecos = _v(prep, "backbone_gaps") or []
    criticos = [h for h in huecos if _hueco_critico(h, contexto)]
    return [
        Requisito(
            "receptor.identidad",
            _campo_dato(
                "Receptor preparado",
                f"SHA-256 {receptor_sha}" + (f" · receta {receta}" if receta else "")
                if receptor_sha else None,
                "La corrida no registró el hash del receptor preparado.",
            ),
            "execution_provenance.receptor_sha256 · receptor_prep.recipe_hash",
            True,
        ),
        Requisito(
            "receptor.cadenas",
            _campo_dato(
                "Cadenas del receptor",
                (f"cadena {cadena}" + (f" · sitio entre {'+'.join(sitio)}" if len(sitio) > 1 else "")
                 + _cadenas_por_simetria(prep))
                if cadena else None,
                "La corrida no registró qué cadenas forman el receptor.",
            ),
            "receptor_prep.chain · receptor_prep.site_chains",
            True,
        ),
        Requisito(
            "receptor.caja",
            _campo_dato(
                "Caja de búsqueda",
                f"centro {centro} · tamaño {tamano} Å" if centro and tamano else None,
                "La corrida no persistió la caja de búsqueda efectiva.",
            ),
            "execution_provenance.box_center · box_size",
            True,
        ),
        Requisito("receptor.cadenas_excluidas", vecinas,
                  "receptor_prep.species_diff.near_site.protein_residues_removed", False),
        Requisito("receptor.residuos_retirados", residuos,
                  "receptor_prep.removed_residues · cofactors_outside_site", False),
        Requisito("receptor.cadenas_truncadas", cadenas_truncadas,
                  "receptor_prep.truncated_sidechains", False),
        Requisito("receptor.huecos",
                  _campo_de_huecos(_v(prep, "backbone_gaps"), sin_dato.get("backbone_gaps"), contexto),
                  "receptor_prep.backbone_gaps",
                  bool(criticos),
                  ubicacion=[{**h, "site_critical": True,
                              **({"distance_to_ligand_A": _hueco_al_ligando(h, contexto)}
                                 if _hueco_al_ligando(h, contexto) is not None else {})}
                             for h in criticos] or None,
                  accion_recomendada='Modela o repara el esqueleto en el sitio, o usa otra estructura del mismo receptor. Después vuelve a preparar y evaluar. Revisa también las cadenas laterales ausentes.' if criticos else None),
        Requisito("receptor.protonacion", protonacion, "receptor_prep.protonation_method", False,
                  rutinaria=rutina_protonacion, accion_recomendada=accion_protonacion),
        *_requisitos_del_contexto(contexto),
        _requisito_campo_del_receptor(contexto),
        *_requisito_de_entrada(prep),
        *_requisito_de_confianza(prep),
    ]


def _requisitos_del_contexto(contexto: ContextoEstructural | None) -> list[Requisito]:
    """Recorte, puentes disulfuro y conformaciones alternativas: sólo si la corrida se pudo medir."""
    if contexto is None or not contexto.medido:
        return []
    salida: list[Requisito] = []
    if contexto.recorte:
        r = contexto.recorte
        salida.append(Requisito(
            "receptor.recorte",
            Campo("Recorte del receptor",
                  f"Bolsillo de {r['radio_A']:g} Å alrededor del centro de la caja: {r['residuos_receptor']} de "
                  f"{r['residuos_cadenas']} residuos de las cadenas {'+'.join(r['cadenas'])}; "
                  f"{r['cortes']} corte(s) del esqueleto creados por el recorte",
                  Estado.REVISAR,
                  "El recorte sirve para Vina, pero el receptor que se entregaría no es la proteína: un cálculo "
                  "con disolvente explícito tiene que partir de las cadenas enteras de la estructura de origen.",
                  valor_es_clasificacion=True),
            "receptor PDBQT de la corrida · services/docking/preparer_multichain.radio_para_caja", False,
            rutinaria=RUTINA_RECORTE,
        ))
    if contexto.disulfuros_totales is not None:
        rotos, total = contexto.disulfuros_rotos or [], contexto.disulfuros_totales
        sin_evaluar = contexto.disulfuros_sin_evaluar or []
        if rotos:
            campo = Campo(
                "Puentes disulfuro",
                f"{len(rotos)} de {total} puente(s) disulfuro quedan como tiol libre en el receptor: "
                + ", ".join(rotos),
                Estado.REVISAR,
                "Meeko aplicó la plantilla de tiol libre (CYS) a una cisteína del puente porque su pareja quedó "
                "fuera del receptor: el receptor tiene un SH donde la estructura tiene un enlace S–S.",
                valor_es_clasificacion=True)
        elif sin_evaluar:
            # SCI-C-001: sin plantilla de las dos cisteínas no se sabe si el receptor conserva el
            # enlace. La proximidad S–S es un dato; su estado químico, no.
            campo = Campo(
                "Puentes disulfuro",
                f"{len(sin_evaluar)} de {total} puente(s) disulfuro de la estructura sin estado químico "
                "registrado en el receptor: " + ", ".join(sin_evaluar),
                Estado.NO_EVALUADO,
                "La preparación no registró la plantilla de una o de las dos cisteínas del puente, así que no "
                "se puede saber si el receptor conserva el enlace S–S o tiene un tiol libre.",
                valor_es_clasificacion=True)
        elif total:
            campo = Campo("Puentes disulfuro", f"{total} puente(s) disulfuro en la estructura; ninguno queda como tiol libre en el receptor",
                          Estado.REGISTRADO)
        else:
            campo = Campo("Puentes disulfuro", "Ninguno en las cadenas del receptor", Estado.REGISTRADO)
        salida.append(Requisito("receptor.disulfuros", campo,
                                "estructura de origen · informe de la preparación (protonation_templates)", False))
    if contexto.altlocs:
        campo = Campo(
            "Conformaciones alternativas",
            f"{len(contexto.altlocs)} residuo(s) con conformaciones alternativas a {UMBRAL_RESIDUO_A:g} Å o menos "
            "del ligando: " + ", ".join(f"{r} {reparto} ({d:g} Å)" for r, reparto, d in contexto.altlocs),
            Estado.REVISAR,
            "La preparación usó en cada residuo la conformación de mayor ocupación sumada y, si empatan, la "
            "primera por letra (A antes que B), sin mirar el ligando; la otra puede cambiar el contacto con "
            "el ligando.",
            valor_es_clasificacion=True)
    else:
        campo = Campo("Conformaciones alternativas", f"Ninguna a {UMBRAL_RESIDUO_A:g} Å o menos del ligando",
                      Estado.REGISTRADO)
    salida.append(Requisito("receptor.altlocs", campo, "estructura de origen (altloc y ocupación)", False))
    salida += _requisitos_de_las_cabeceras(contexto)
    return salida


def _distancia_texto(d: float | None) -> str:
    return f"{d:g} Å" if d is not None else "— Å"


def _requisitos_de_las_cabeceras(contexto: ContextoEstructural) -> list[Requisito]:
    """Constructo cristalizado y ocupación cero, como los declara el propio depósito (FEP-06-PRE, 2026-10-24).

    En 3G0E (P08) el depósito dice que los residuos 694-753 se borraron y se sustituyeron por TS, y en 1M17 (P01) que 37
    átomos tienen ocupación cero; el PDBQT les pone 1,00. El paquete traía el origen con esas cabeceras, pero Preparación
    no las leía. Piden revisión sólo junto al ligando: lejos, se declaran.
    """
    salida: list[Requisito] = []
    if contexto.secuencia_modificada is not None:
        mods = contexto.secuencia_modificada
        cerca = [m for m in mods if m[2] is not None and m[2] <= UMBRAL_RESIDUO_A]
        lista = ", ".join(f"{r} {c} ({_distancia_texto(d)})" for r, c, d in mods)
        nota = f" Según el REMARK 999: {contexto.remark_999}" if contexto.remark_999 else ""
        if cerca:
            campo = Campo("Constructo cristalizado",
                          f"{len(mods)} diferencia(s) con la secuencia de referencia (SEQADV): {lista}.{nota}",
                          Estado.REVISAR,
                          f"Hay diferencias con la secuencia natural a {UMBRAL_RESIDUO_A:g} Å o menos del ligando: el "
                          "sitio cristalizado no es el de la proteína natural, y un cálculo posterior hereda esa "
                          "diferencia.",
                          valor_es_clasificacion=True)
        elif mods or nota:
            campo = Campo("Constructo cristalizado",
                          (f"{len(mods)} diferencia(s) con la secuencia de referencia (SEQADV), ninguna a "
                           f"{UMBRAL_RESIDUO_A:g} Å o menos del ligando: {lista}." if mods else
                           "Sin diferencias SEQADV fuera de etiquetas de expresión.") + nota,
                          Estado.REGISTRADO)
        else:
            campo = Campo("Constructo cristalizado",
                          "Sin diferencias declaradas con la secuencia de referencia, aparte de etiquetas de expresión",
                          Estado.REGISTRADO)
        salida.append(Requisito("receptor.constructo", campo, "estructura de origen (SEQADV · REMARK 999)", False))
    if contexto.ocupacion_cero is not None:
        filas = contexto.ocupacion_cero
        cerca = [f for f in filas if f[2] is not None and f[2] <= UMBRAL_RESIDUO_A]
        lista = ", ".join(f"{r}{': ' + a if a else ''} ({_distancia_texto(d)})" for r, a, d in filas)
        if cerca:
            campo = Campo("Ocupación cero en el depósito",
                          f"{len(filas)} residuo(s) con átomos de ocupación cero (REMARK 475/480): {lista}",
                          Estado.REVISAR,
                          f"El cristal no los sostiene y están a {UMBRAL_RESIDUO_A:g} Å o menos del ligando: el receptor "
                          "preparado los conserva con ocupación 1,00, así que su posición es un modelo, no una medida.",
                          valor_es_clasificacion=True)
        elif filas:
            campo = Campo("Ocupación cero en el depósito",
                          f"{len(filas)} residuo(s) con átomos de ocupación cero (REMARK 475/480), ninguno a "
                          f"{UMBRAL_RESIDUO_A:g} Å o menos del ligando: {lista}. El receptor preparado los conserva con "
                          "ocupación 1,00.",
                          Estado.REGISTRADO)
        else:
            campo = Campo("Ocupación cero en el depósito", "Ninguna en las cadenas del receptor", Estado.REGISTRADO)
        salida.append(Requisito("receptor.ocupacion_cero", campo, "estructura de origen (REMARK 475 · REMARK 480)",
                                False))
    return salida


# ── 02 · Estado químico del ligando ──────────────────────────────────


def _sin_estereo(smiles: str) -> str | None:
    from rdkit import Chem, RDLogger

    RDLogger.DisableLog("rdApp.*")
    mol = Chem.MolFromSmiles(smiles)
    return Chem.MolToSmiles(mol, isomericSmiles=False) if mol is not None else None


def _tautomero_cambiado(estado: Any) -> tuple[str, str] | None:
    """(entrada, canónico) si el modo canónico acopló otro tautómero que el escrito; si no, None.

    Se compara sin estereoquímica: la declaración enumera con los valores por
    defecto de RDKit, que borran la E/Z del sistema tautomérico, y la entacapona o la
    rilpivirina saldrían «cambiadas» sin que cambie ningún hidrógeno.
    """
    tautomeria = _v(estado, "tautomeria")
    entrada = _v(tautomeria, "declaracion_entrada") if isinstance(tautomeria, dict) else None
    if not (isinstance(entrada, dict) and tautomeria.get("aplicada")
            and entrada.get("tautomero_acoplado") == "canonico_rdkit"):
        return None
    escrito, canonico = entrada.get("smiles_entrada"), entrada.get("smiles_canonico")
    if not (isinstance(escrito, str) and isinstance(canonico, str)):
        return None
    try:
        if _sin_estereo(escrito) == _sin_estereo(canonico):
            return None
    except Exception:  # noqa: BLE001 — sin RDKit no se afirma un cambio
        return None
    return escrito, canonico


def _plausibles(declaracion: Any) -> tuple[str | None, dict[str, list[str]]]:
    """(SMILES acoplado o escrito, {candidato: reglas de forma minoritaria}) de una declaración."""
    if not isinstance(declaracion, dict):
        return None, {}
    candidatos = [c for c in declaracion.get("candidatos") or [] if isinstance(c, dict) and c.get("smiles")]
    if not candidatos:
        return None, {}
    from chem.tautomeros_minoritarios import clasificar

    propio = next((c["smiles"] for c in candidatos if c.get("es_entrada")), None)
    return propio, clasificar([c["smiles"] for c in candidatos])


def _con_el_escrito(smiles: str) -> dict[str, str]:
    """Volver a evaluar este SMILES conservando su tautómero. Nunca se propone el canónico de RDKit."""
    return {"tautomero": "entrada", "smiles": smiles}


def _forma_minoritaria(estado: Any, tautomero: Campo, cambio: tuple[str, str] | None
                       ) -> tuple[Campo, str | None, list[dict[str, str]] | None] | None:
    """El requisito de tautómero según las reglas de forma minoritaria, o None si no cambia nada.

    Lo acoplado en una forma sin población (iminol, enol simple, hidroxiazina,
    imina exocíclica, nitroso, o un candidato desaromatizado) BLOQUEA, venga del
    usuario o del canónico de RDKit, y se recomienda la forma mayoritaria que dan
    las reglas, nunca el canónico. Si las reglas dejan un solo candidato plausible
    y es el acoplado, el «multiestado» del enumerador era ruido: queda registrado.
    """
    from chem.tautomeros_minoritarios import DESCRIPCION

    tautomeria = _v(estado, "tautomeria")
    acoplado, clasificacion = _plausibles(_v(tautomeria, "declaracion"))
    if not acoplado or acoplado not in clasificacion:
        return None
    reglas = clasificacion[acoplado]
    # Quién eligió el tautómero sigue diciéndose: las mismas frases que el dossier.
    eleccion = {
        "entrada": "Se acopló el tautómero del usuario; la protonación sigue el pH declarado. ",
        "canonico": "Se acopló el tautómero canónico de RDKit; la protonación sigue el pH declarado. ",
    }.get(tautomeria.get("modo") if isinstance(tautomeria, dict) else None, "")
    if reglas:
        escrito, de_la_entrada = _plausibles(_v(tautomeria, "declaracion_entrada"))
        plausibles = [s for s, r in de_la_entrada.items() if not r]
        if cambio and escrito in plausibles:
            accion = ("Vuelve a evaluar con «Tautómero del ligando: Por defecto (conservar el tautómero que "
                      "escribí)»: el tautómero que escribiste es la forma mayoritaria.")
            opciones = [_con_el_escrito(cambio[0])]
        elif len(plausibles) == 1:
            accion = f"Vuelve a evaluar con la forma mayoritaria: {plausibles[0]}"
            opciones = [_con_el_escrito(plausibles[0])]
        elif plausibles:
            accion = ("Vuelve a evaluar con una de estas formas, que ninguna regla descarta: "
                      + ", ".join(plausibles[:3]))
            opciones = [_con_el_escrito(s) for s in plausibles[:3]]
        else:
            accion, opciones = None, None
        return Campo(
            "Tautómero del ligando",
            f"Forma minoritaria acoplada: {acoplado} ({', '.join(DESCRIPCION[r] for r in reglas)})",
            Estado.ABSTENCION,
            eleccion + "El tautómero acoplado tiene una población despreciable en agua: un cálculo de "
            "energía libre partiría de una especie que casi no existe.",
            valor_es_clasificacion=True,
        ), accion, opciones
    plausibles = [s for s, r in clasificacion.items() if not r]
    if cambio or tautomero.estado != Estado.REVISAR or plausibles != [acoplado]:
        return None
    descartadas = sorted({DESCRIPCION[r] for s, rs in clasificacion.items() if s != acoplado for r in rs})
    return Campo(
        "Tautómero del ligando",
        acoplado,
        Estado.REGISTRADO,
        eleccion + f"Los demás candidatos de RDKit ({len(clasificacion) - 1}) son formas minoritarias "
        "conocidas: " + ", ".join(descartadas) + ".",
    ), None, None


#: A esta distancia del pH, la forma minoritaria de un grupo supera el 3 %: unos
#: 2 kcal/mol, la ventana con la que una preparación para FEP enumera estados.
UMBRAL_PKA = 1.5


def _pka_cerca_del_ph(estado: Any) -> tuple[float, list[str]] | None:
    """(pH, [«grupo (pKa ≈ x; y % en la otra forma)»]) de los grupos con pKa cerca del pH acoplado."""
    protonacion = _v(estado, "protonacion")
    ph = protonacion.get("ph") if isinstance(protonacion, dict) else None
    smiles = _v(estado, "smiles_entrada")
    if not isinstance(ph, (int, float)) or not isinstance(smiles, str):
        return None
    from chem.ionizacion import analizar_ionizacion

    try:
        centros = analizar_ionizacion(smiles, None).centros
    except Exception:  # noqa: BLE001 — sin tabla no se afirma nada: queda la especie como estaba
        return None
    cerca = []
    for nombre, pka, _caracter in centros:
        delta = abs(float(pka) - float(ph))
        if delta <= UMBRAL_PKA:
            minoritaria = 100.0 / (1.0 + 10.0 ** delta)
            cerca.append(f"{nombre} (pKa ≈ {float(pka):g}; {minoritaria:.0f} % en la otra forma)")
    return (float(ph), cerca) if cerca else None


def _bloque_ligando(eval_result: Any, prov: Any, contexto: ContextoEstructural | None = None) -> list[Requisito]:
    estado = _v(eval_result, "ligand_state") or {}
    smiles = _v(estado, "smiles_acoplado")
    sdf = _v(prov, "ligand_input_sha256")
    por_clave = dict(campos_del_estado_del_ligando(estado))

    # Un grupo con pKa cerca del pH tiene las dos formas pobladas: la tabla elige una,
    # pero no la resuelve. Sólo se añade a lo que estaba registrado; lo que ya pedía
    # revisión (piperazinas, ácidos enólicos) lo sigue pidiendo con su motivo.
    especie = por_clave.get("especie")
    mixta = _pka_cerca_del_ph(estado) if especie is not None and especie.estado == Estado.REGISTRADO else None
    if mixta:
        ph, grupos = mixta
        por_clave["especie"] = Campo(
            "Especie acoplada", especie.valor, Estado.REVISAR,
            f"Grupos con pKa a {UMBRAL_PKA:g} unidades o menos del pH {ph:g}: {', '.join(grupos)}. "
            + "La tabla de pKa por clases elige una forma, pero las dos están pobladas: un cálculo de energía "
            "libre tiene que considerar las dos o fijar una con evidencia.",
            valor_es_clasificacion=True,
        )

    # El modo por defecto acopla el canónico de RDKit, que no predice el tautómero
    # dominante: a vorinostat y belinostat los pasa a iminol, a aciclovir a N3-H. Sin
    # esto, el cambio se confundía con el aviso genérico de «varios candidatos».
    tautomero = por_clave.get("tautomero") or _no_evaluado(
        "Tautómero del ligando",
        "La corrida es anterior a la declaración de tautómeros y no se reconstruye.",
    )
    accion_tautomero = None
    reevaluar_tautomero = None
    cambio = _tautomero_cambiado(estado)
    if cambio and tautomero.estado in (Estado.REGISTRADO, Estado.REVISAR):
        declaracion = _v(_v(estado, "tautomeria"), "declaracion")
        from chem.declaracion_tautomeros import resumen_para_humanos

        resumen = resumen_para_humanos(declaracion) if isinstance(declaracion, dict) else None
        tautomero = Campo(
            "Tautómero del ligando",
            f"Entrada {cambio[0]} → tautómero canónico {cambio[1]}",
            Estado.REVISAR,
            "Se acopló el tautómero canónico de RDKit, que no es el de la entrada. El canónico es una "
            "representación reproducible, no una predicción del tautómero dominante."
            + (f" {resumen}" if resumen else ""),
            valor_es_clasificacion=True,
        )
        accion_tautomero = (
            "Si el tautómero que escribiste es el correcto, vuelve a evaluar con «Tautómero del ligando: "
            "Por defecto (conservar el tautómero que escribí)» en las opciones avanzadas.")
        reevaluar_tautomero = [_con_el_escrito(cambio[0])]
    if tautomero.estado in (Estado.REGISTRADO, Estado.REVISAR):
        por_reglas = _forma_minoritaria(estado, tautomero, cambio)
        if por_reglas is not None:
            tautomero, accion_tautomero, reevaluar_tautomero = por_reglas
    return [
        Requisito(
            "ligando.identidad",
            _campo_dato(
                "Ligando acoplado",
                (f"{smiles}" + (f" · SHA-256 del SDF {sdf}" if sdf else "")) if smiles else None,
                "La corrida no registró la forma del ligando que se acopló.",
            ),
            "ligand_state.smiles_acoplado · execution_provenance.ligand_input_sha256",
            True,
        ),
        Requisito(
            "ligando.ph",
            por_clave.get("ph") or _no_evaluado(
                "pH de protonación del ligando",
                "La corrida no registró la protonación del ligando.",
            ),
            "ligand_state.protonacion",
            False,
        ),
        Requisito(
            "ligando.especie",
            por_clave.get("especie") or _no_evaluado(
                "Especie acoplada",
                "La corrida no registró con qué criterio se eligió el microestado.",
            ),
            "ligand_state.protonacion.seleccion",
            True,
        ),
        Requisito(
            "ligando.tautomero",
            tautomero,
            "ligand_state.tautomeria.declaracion · declaracion_entrada" if accion_tautomero
            else "ligand_state.tautomeria.declaracion",
            True,
            accion_recomendada=accion_tautomero,
            reevaluar=reevaluar_tautomero,
        ),
        Requisito("ligando.estereoquimica", _campo_de_estado_quimico(eval_result),
                  "ligand_state.estereoquimica", True),
        _requisito_covalente(smiles, contexto),
        _requisito_campo_del_ligando(smiles),
    ]


# ── 03 · Pose y correspondencia ──────────────────────────────────────


def _bloque_pose(dossier: CaseDossier, eval_result: Any, prov: Any) -> list[Requisito]:
    sha = _v(prov, "poses_sha256")
    top1 = next((p for p in dossier.evidencia_poses if p.es_vina_top1), None)
    sugerida = next((p for p in dossier.evidencia_poses if p.es_sugerida), None)

    if top1 is not None:
        fallan = ", ".join(top1.checks_que_fallan)
        validez = Campo(
            "Validez física de la pose principal",
            f"#{top1.rango}: {top1.estado_fisico_codigo}"
            + (f" · fallan {fallan}" if fallan else ""),
            top1.estado_fisico,
            top1.detalle or "La etapa de validación no dejó detalle.",
            valor_es_clasificacion=True,
        )
    else:
        control = next((c for c in dossier.controles if c.codigo == "VALIDEZ_FISICA_POSES"), None)
        validez = Campo(
            "Validez física de la pose principal", None,
            control.estado if control else Estado.NO_EVALUADO,
            control.observacion if control else "No hay evidencia física de la pose principal.",
        )

    if top1 is None:
        regla = _no_evaluado(
            "Regla de selección de la pose",
            "La corrida no permitió identificar la pose principal (top-1 de Vina).",
        )
    elif sugerida is not None and sugerida.rango != top1.rango:
        regla = Campo(
            "Regla de selección de la pose",
            f"Pose principal: top-1 de Vina (#{top1.rango}); el selector sugiere #{sugerida.rango}",
            Estado.REVISAR,
            "Hay dos candidatas a pose de partida. Elegir una es una decisión que el "
            "cálculo siguiente hereda.",
            valor_es_clasificacion=True,
        )
    else:
        regla = Campo(
            "Regla de selección de la pose",
            f"Pose principal: top-1 de Vina (#{top1.rango})"
            + (" · el selector coincide" if sugerida is not None else " · sin recomendación del selector"),
            Estado.REGISTRADO,
        )

    # Ensamble: no hay un SDF de la piscina; cada conformación conserva el suyo con
    # su hash. Leer sólo el nivel superior bloqueaba toda corrida en ensamble.
    conformaciones = _conformaciones(prov)
    if conformaciones:
        sin_poses = [c for c in conformaciones if not (c.get("poses_sha256") and c.get("poses_file_path"))]
        origen = _campo_dato(
            "Poses de la corrida",
            None if sin_poses else (
                f"{len(conformaciones)} SDF de poses, uno por conformación: "
                + ", ".join(f"#{c.get('indice')} SHA-256 {c['poses_sha256']}" for c in conformaciones)
            ),
            "Falta el archivo de poses o su hash en la(s) conformación(es) "
            + ", ".join(f"#{c.get('indice')}" for c in sin_poses) + ".",
        )
        fuente_origen = "execution_provenance.por_conformacion[].poses_file_path · poses_sha256"
    else:
        origen = _campo_dato(
            "Poses de la corrida",
            f"SDF SHA-256 {sha}" if sha and _v(eval_result, "poses_file_path") else None,
            "La corrida no conservó el archivo de poses con su hash.",
        )
        fuente_origen = "eval_result.poses_file_path · execution_provenance.poses_sha256"

    return [
        Requisito("pose.origen", origen, fuente_origen, True),
        Requisito(
            "pose.validez_fisica", validez,
            "structural_evidence (PoseBusters con hidrógenos reconstruidos desde el SMILES; "
            "condición MF-33-H-COR)",
            True,
        ),
        Requisito("pose.regla_de_seleccion", regla, "pose_selection", False),
        Requisito(
            "pose.correspondencia_serie",
            Campo("Correspondencia atómica de la serie", None, Estado.NO_APLICA,
                  "Requiere una serie de ligandos; esta auditoría cubre una corrida."),
            "no aplica a una corrida",
            False,
        ),
    ]


# ── 04 · Entorno del sitio ───────────────────────────────────────────


def _bloque_entorno(prep: Any, projection: CaseProjection,
                    contexto: ContextoEstructural | None = None) -> list[Requisito]:
    diff = _v(prep, "species_diff")
    originales = _originales(prep)
    politica = Requisito(
        "entorno.politica",
        _campo_dato(
            "Política de heteroátomos",
            projection.preflight.execution_route if projection.preflight else None,
            "La corrida no declaró la ruta de preparación aplicada.",
        ),
        "preflight.execution_route",
        False,
    )
    referencia = []
    if contexto is not None:
        umbrales = (f"Metales, cofactores y otras especies cuentan a {UMBRAL_ESPECIE_A:g} Å o menos del ligando; "
                    f"aguas, a {UMBRAL_AGUA_A:g} Å; huecos y residuos, a {UMBRAL_RESIDUO_A:g} Å.")
        referencia = [Requisito(
            "entorno.referencia",
            # Un ligando del cristal al que le faltan átomos (REMARK 610) no es una referencia completa: la pose se
            # compara y las distancias se miden contra un fragmento (3G0E, P08 de FEP-06-PRE: 22 de 29 átomos pesados).
            Campo("Referencia de las distancias", contexto.referencia, Estado.REVISAR,
                  umbrales + " " + CRISTAL_INCOMPLETO.format(ligando=contexto.cristal_incompleto),
                  valor_es_clasificacion=True)
            if contexto.medido and contexto.cristal_incompleto else
            Campo("Referencia de las distancias", contexto.referencia, Estado.REGISTRADO, umbrales)
            if contexto.medido else
            Campo("Referencia de las distancias", None, Estado.NO_EVALUADO, contexto.razon),
            "pose top-1 · estructura de origen comprobada por la receta del receptor", False,
        )]
    cerca = _v(diff, "near_site") if isinstance(diff, dict) else None
    # Un diff evaluado que no declara el margen del sitio no dice qué quedó junto a él: sin margen no hay «a X Å o menos».
    sin_margen = (isinstance(diff, dict) and diff.get("state") == "evaluado" and isinstance(cerca, dict)
                  and not isinstance(cerca.get("margin_A"), (int, float)))
    if sin_margen or not isinstance(diff, dict) or diff.get("state") != "evaluado" or not isinstance(cerca, dict):
        sin_dato = _v(prep, "no_disponible")
        sin_origen = sin_dato.get("species_diff") if isinstance(sin_dato, dict) else None
        razon = "El diff registrado no declara el margen del sitio." if sin_margen else sin_origen or (
            "La corrida usó un receptor congelado y su informe de preparación no viaja con ella."
            if _v(prep, "source") == "durable_receptor_snapshot" else
            "La corrida no serializó qué retiró la preparación: su receptor se preparó antes "
            "de registrarlo. No se reconstruye con la receta de hoy."
        )
        return [
            Requisito("entorno.metales_cofactores",
                      _no_evaluado("Metales y cofactores junto al sitio", razon),
                      "receptor_prep.species_diff", True,
                      accion_recomendada=(
                          "Sube la estructura de origen del PDBQT (PDB o mmCIF) junto con el PDBQT y "
                          "vuelve a evaluar: con ella Preparación calcula qué especies se retiraron."
                          if sin_origen else None)),
            Requisito("entorno.aguas", _no_evaluado("Aguas junto al sitio", razon),
                      "receptor_prep.species_diff", False),
            Requisito("entorno.otras_especies",
                      _no_evaluado("Otras especies junto al sitio", razon),
                      "receptor_prep.species_diff", False),
            politica,
            *referencia,
            _requisito_de_membrana(contexto),
        ]

    margen = cerca.get("margin_A")
    retiradas = list(cerca.get("removed") or [])
    conservadas = list(cerca.get("preserved") or [])

    def _de(filas: list[dict[str, Any]], *categorias: str) -> list[dict[str, Any]]:
        return [f for f in filas if f.get("category") in categorias]

    bloqueantes = _de(retiradas, *_CATEGORIAS_QUE_BLOQUEAN)
    conservados = _de(conservadas, *_CATEGORIAS_QUE_BLOQUEAN)
    # El ligando del cristal se retira a propósito y no se informa, salvo que sea un
    # cofactor: entonces el sitio acoplado perdió algo que el producto conserva en
    # cualquier otro caso, y antes eso salía como «ninguno retirado».
    from services.docking.preparer import ORGANIC_COFACTORS_KEPT

    cofactor_cristal = [f for f in _de(retiradas, "site_ligand")
                        if str(f.get("name") or "").upper() in ORGANIC_COFACTORS_KEPT]
    no_desplazables = [f for f in cofactor_cristal
                       if str(f.get("name") or "").upper() in _COFACTORES_NO_DESPLAZABLES]
    distancia = _medidor_del_sitio(contexto)
    partes = []
    if distancia is not None:
        # Junto al ligando, o sin distancia (no se encontró en el origen: se cuenta, por prudencia).
        lejanos = [f for f in bloqueantes if distancia(f) is not None and distancia(f) > UMBRAL_ESPECIE_A]
        bloqueantes = [f for f in bloqueantes if f not in lejanos]
        lista = ", ".join(_especie(f, originales, distancia(f)) for f in bloqueantes)
        mas_lejos = ", ".join(_especie(f, originales, distancia(f)) for f in lejanos)
        guardados = ", ".join(_especie(f, originales, distancia(f)) for f in conservados)
        if bloqueantes:
            partes.append(f"Retirados a {UMBRAL_ESPECIE_A:g} Å o menos del ligando: {lista}"
                          + (f"; más lejos: {mas_lejos}" if mas_lejos else ""))
        elif not cofactor_cristal:
            partes.append(f"Ninguno retirado a {UMBRAL_ESPECIE_A:g} Å o menos del ligando"
                          + (f"; más lejos: {mas_lejos}" if mas_lejos else "")
                          + (f"; conservados: {guardados}" if guardados else ""))
    elif bloqueantes:
        partes.append(f"Retirados a {margen:g} Å o menos: " + ", ".join(_fila(f, originales) for f in bloqueantes))
    elif not cofactor_cristal:
        partes.append(
            f"Ninguno retirado a {margen:g} Å o menos"
            + (f"; conservados: {', '.join(_fila(f, originales) for f in conservados)}" if conservados else ""))
    if cofactor_cristal:
        partes.append("Cofactor retirado como ligando del cristal: "
                      + ", ".join(_fila(f, originales) for f in cofactor_cristal) + ".")
    # Dos niveles (2026-10-22): un metal o cofactor retirado en contacto con el ligando del cristal (metal coordinado, o cofactor
    # sin metal a ≤ 4 Å) sigue absteniendo; uno sólo cercano pide revisión. Sin ligando del cristal (coordinadas None) no se sabe y se abstiene, como antes.
    coordinados = ([f for f in bloqueantes if _coordinacion_de(contexto, f)]
                   if contexto is not None and contexto.coordinadas is not None else list(bloqueantes))
    solo_cerca = [f for f in bloqueantes if f not in coordinados]
    if distancia is not None and bloqueantes:
        if contexto.coordinadas is None:
            partes.append("Sin ligando del cristal no se puede ver si el ligando los toca.")
        elif coordinados:
            partes.append("En contacto con el ligando del cristal: " + ", ".join(
                f"{_especie(f, originales, None)} ({_coordinacion_de(contexto, f)})" for f in coordinados) + ".")
        else:
            partes.append("El ligando del cristal no toca ninguno (ni un N, O o S a 2,8 Å de un metal ni un átomo a 4 Å de un cofactor).")
    # Metales conservados que el ligando del cristal coordina (el Fe del hemo de 4NY4): el receptor los lleva, pero Vina no
    # tiene término de coordinación y un cálculo posterior necesita parámetros para el enlace.
    conservados_coordinados = [f for f in conservados if _coordinacion_de(contexto, f)]
    if conservados_coordinados:
        partes.append("Conservados y coordinados por el ligando del cristal: "
                      + ", ".join(f"{_especie(f, originales, None)} ({_coordinacion_de(contexto, f)})"
                                  for f in conservados_coordinados) + ".")
    valor_metales = (partes[0] + "." if len(partes) > 1 else partes[0]) + "".join(f" {p}" for p in partes[1:])
    accion_metales = None
    if coordinados or no_desplazables:
        metales = Campo(
            "Metales y cofactores junto al sitio",
            valor_metales,
            Estado.ABSTENCION,
            # Dos literales enteros, no uno con un añadido: así cada uno tiene su traducción exacta.
            ("El receptor que se entregaría no contiene especies que estaban en el sitio. "
             "Hay que decidir sobre ellas antes de cualquier cálculo posterior. "
             "El ligando se une junto a ese cofactor y no lo desplaza: el sitio acoplado quedó sin él.")
            if no_desplazables else
            ("El receptor que se entregaría no contiene especies que estaban en el sitio. "
             "Hay que decidir sobre ellas antes de cualquier cálculo posterior."),
            valor_es_clasificacion=True,
        )
        if no_desplazables:
            accion_metales = (
                "Usa otra estructura del mismo receptor en la que el cofactor no sea el ligando del cristal, "
                "o súbela como receptor propio ya preparado, con el cofactor dentro. Después vuelve a evaluar.")
    elif solo_cerca:
        metales = Campo(
            "Metales y cofactores junto al sitio",
            valor_metales,
            Estado.REVISAR,
            "El receptor no contiene especies que estaban cerca del sitio, pero el ligando del cristal no las toca. "
            "Si sólo ocupan la segunda esfera, retirarlas puede ser aceptable; decide y justifícalo antes de un cálculo "
            "posterior.",
            valor_es_clasificacion=True,
        )
        accion_metales = ("Si la especie es estructural o catalítica para este ligando, vuelve a evaluar con ella en la "
                          "lista de cofactores del receptor; si no, registra por qué se retira.")
    elif cofactor_cristal or conservados_coordinados:
        metales = Campo(
            "Metales y cofactores junto al sitio",
            valor_metales,
            Estado.REVISAR,
            ("Retirarlo es correcto si el ligando compite con él por el sitio, como un inhibidor competitivo "
             "con ATP, SAM o NAD. Si el ligando se une a su lado, el sitio acoplado quedó incompleto.")
            if cofactor_cristal else
            ("El ligando del cristal coordina un metal que el receptor conserva. Vina no tiene término de coordinación: "
             "la pose no la reproduce y un cálculo posterior necesita parámetros para ese enlace."),
            valor_es_clasificacion=True,
        )
    else:
        metales = Campo("Metales y cofactores junto al sitio", valor_metales, Estado.REGISTRADO)

    aguas_fuera, aguas_dentro = _de(retiradas, "water"), _de(conservadas, "water")

    def _por_distancia(filas: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(filas, key=lambda f: (f.get("distance_to_box_A") is None,
                                            f.get("distance_to_box_A") or 0.0))

    # TODAS, una por una y de la más cercana a la más lejana: decidir cuáles son
    # estructurales exige saber cuáles eran. Un recuento no deja decidir nada.
    # Con distancias al ligando se nombran las que pueden puentearlo (≤ UMBRAL_AGUA_A)
    # y el resto se cuenta: 347 aguas a 6 Å de la caja no dejaban ver las 10 que importan.
    razon_aguas = (
        "El receptor conserva las aguas que traía el archivo; las retiradas eran de otras cadenas o "
        "estaban lejos de la unidad que se acopla. La decisión sobre cuáles son estructurales y cuáles "
        "desplazables es de quien preparó el receptor."
        if _v(prep, "modo_de_preparacion") == "respetar" else
        "La ruta de docking retira todas las aguas. No se ha decidido cuáles son "
        "estructurales y cuáles desplazables.")
    rutina_aguas = None
    if distancia is not None:
        puente = sorted((f for f in aguas_fuera if distancia(f) is not None and distancia(f) <= UMBRAL_AGUA_A),
                        key=lambda f: distancia(f))
        resto = len(aguas_fuera) - len(puente)
        # Un agua a distancia de puente de hidrógeno de un N u O del ligando y de uno de la
        # proteína puede puentearlos: conservarla o no es una decisión de ESTE sitio. Más cerca
        # de cualquier átomo del ligando, la pose la desplaza; junto a un carbono, no lo puentea.
        a_la_proteina = contexto.aguas_a_la_proteina if contexto is not None else {}
        al_polar = contexto.aguas_al_ligando_polar if contexto is not None else {}

        def _clave(f: dict[str, Any]) -> tuple[str, str, str, str]:
            return (str(f.get("chain")), str(f.get("residue_number")), str(f.get("insertion_code") or ""),
                    str(f.get("name")))

        puentes = [f for f in puente
                   if distancia(f) >= UMBRAL_SOLAPAMIENTO_A
                   and al_polar.get(_clave(f), UMBRAL_AGUA_A) <= UMBRAL_PUENTE_H_A
                   and a_la_proteina.get(_clave(f), UMBRAL_AGUA_A) <= UMBRAL_PUENTE_H_A]
        if puente and puentes:
            razon_aguas += (f" Aguas que pueden puentear el ligando con la proteína (a {UMBRAL_PUENTE_H_A:g} Å "
                            "o menos de un N u O de cada uno): "
                            + ", ".join(_especie(f, originales, distancia(f)) for f in puentes) + ".")
        elif puente:
            rutina_aguas = ("Ninguna de las aguas retiradas puentea el ligando con la proteína (a "
                            f"{UMBRAL_PUENTE_H_A:g} Å o menos de un N u O de cada uno): decidir cuáles conservar es la misma "
                            "decisión en toda corrida contra un cristal.")
        aguas = Campo(
            "Aguas junto al sitio",
            f"{len(puente)} retirada(s) a {UMBRAL_AGUA_A:g} Å o menos del ligando: "
            + ", ".join(_especie(f, originales, distancia(f)) for f in puente)
            + f"; {resto} más retirada(s) a {margen:g} Å o menos de la caja; {len(aguas_dentro)} conservada(s)",
            Estado.REVISAR, razon_aguas, valor_es_clasificacion=True,
        ) if puente else Campo(
            "Aguas junto al sitio",
            f"Ninguna retirada a {UMBRAL_AGUA_A:g} Å o menos del ligando; {resto} retirada(s) a {margen:g} Å o "
            f"menos de la caja; "
            f"{len(aguas_dentro)} conservada(s)",
            Estado.REGISTRADO,
        )
    else:
        aguas = None
    aguas = aguas or (
        Campo(
            "Aguas junto al sitio",
            f"{len(aguas_fuera)} retirada(s) a {margen:g} Å o menos: "
            + ", ".join(_fila(f, originales) for f in _por_distancia(aguas_fuera))
            + (f"; {len(aguas_dentro)} conservada(s): "
               + ", ".join(_fila(f, originales) for f in _por_distancia(aguas_dentro))
               if aguas_dentro else "; ninguna conservada"),
            Estado.REVISAR,
            ("El receptor conserva las aguas que traía el archivo; las retiradas eran de otras cadenas o "
             "estaban lejos de la unidad que se acopla. La decisión sobre cuáles son estructurales y cuáles "
             "desplazables es de quien preparó el receptor."
             if _v(prep, "modo_de_preparacion") == "respetar" else
             "La ruta de docking retira todas las aguas. No se ha decidido cuáles son "
             "estructurales y cuáles desplazables."),
            valor_es_clasificacion=True,
        ) if aguas_fuera else Campo(
            "Aguas junto al sitio",
            f"Ninguna retirada a {margen:g} Å o menos; {len(aguas_dentro)} conservada(s)",
            Estado.REGISTRADO,
        )
    )

    otras_fuera = _de(retiradas, "other_heteroatom")
    if distancia is not None and otras_fuera:
        junto = [f for f in otras_fuera if distancia(f) is None or distancia(f) <= UMBRAL_ESPECIE_A]
        lejos = [f for f in otras_fuera if f not in junto]
        mas_lejos = ", ".join(_especie(f, originales, distancia(f)) for f in lejos)
        # Otra copia del ligando del cristal junto al sitio (6SXC: OHT A:307 a 3,3 Å de A:305) no es un aditivo: puede ser
        # una segunda molécula unida, y quien prepare el cálculo tiene que decidir si la conserva. Su distancia es al
        # cristal, como la de metales y cofactores (`especies_al_cristal`).
        copias_junto = [f for f in junto if f.get("site_ligand_copy")]
        otras_medidas = Campo(
            "Otras especies junto al sitio",
            f"Retiradas a {UMBRAL_ESPECIE_A:g} Å o menos del ligando: "
            + ", ".join(_especie(f, originales, distancia(f)) for f in junto)
            + (f"; más lejos: {mas_lejos}" if mas_lejos else ""),
            Estado.REVISAR,
            ("Incluye otra(s) copia(s) del ligando del cristal: "
             + ", ".join(_especie(f, originales, None) for f in copias_junto)
             + ". Puede ser una segunda molécula unida al sitio; la preparación la retira y un cálculo posterior "
               "tiene que decidir si la conserva.")
            if copias_junto else
            "Pueden ser aditivos de cristalización o parte de la cavidad; la preparación "
            "no lo distingue.",
            valor_es_clasificacion=True,
        ) if junto else Campo(
            "Otras especies junto al sitio",
            f"Ninguna retirada a {UMBRAL_ESPECIE_A:g} Å o menos del ligando; más lejos: {mas_lejos}",
            Estado.REGISTRADO,
        )
    else:
        otras_medidas = None
    otras = otras_medidas or (
        Campo(
            "Otras especies junto al sitio",
            "Retiradas: " + ", ".join(_fila(f, originales) for f in otras_fuera),
            Estado.REVISAR,
            "Pueden ser aditivos de cristalización o parte de la cavidad; la preparación "
            "no lo distingue.",
            valor_es_clasificacion=True,
        ) if otras_fuera else Campo(
            "Otras especies junto al sitio", "Ninguna retirada aparte del ligando del cristal",
            Estado.REGISTRADO,
        )
    )
    return [
        Requisito("entorno.metales_cofactores", metales, "receptor_prep.species_diff.near_site", True,
                  accion_recomendada=accion_metales),
        Requisito("entorno.aguas", aguas, "receptor_prep.species_diff.near_site", False, rutinaria=rutina_aguas),
        Requisito("entorno.otras_especies", otras, "receptor_prep.species_diff.near_site", False),
        politica,
        *referencia,
        _requisito_de_membrana(contexto),
    ]


#: Lo que el dossier (el PDF y el `dossier.json` del paquete) toma del entorno de la auditoría, en este orden.
_CLAVES_DEL_ENTORNO_EN_EL_DOSSIER = (
    "entorno.metales_cofactores", "entorno.aguas", "entorno.otras_especies", "entorno.referencia",
)


def campos_del_entorno_para_el_dossier(prep: Any, projection: CaseProjection,
                                       contexto: ContextoEstructural | None = None) -> list[Campo]:
    """Los campos de especies del sitio que el dossier copia de la auditoría, sin recalcularlos.

    Hasta el 2026-10-22 el PDF calculaba esto por su cuenta (`model._campo_de_especies`, a distancia de la caja y con un solo
    estado, REVISAR) y el ZIP llevaba un PDF que decía «REVISAR» y un `audit.json` que decía «ABSTENCIÓN» del mismo zinc; dejaba
    además REGISTRADO un hemo retirado como ligando del cristal. Una sola función decide, y las dos salidas la llaman.
    """
    por_clave = {r.clave: r.campo for r in _bloque_entorno(prep, projection, contexto)}
    return [por_clave[c] for c in _CLAVES_DEL_ENTORNO_EN_EL_DOSSIER if c in por_clave]


# ── 05 · Procedencia y entrega ───────────────────────────────────────

_HASHES = ("receptor_sha256", "ligand_input_sha256", "ligand_pdbqt_sha256", "poses_sha256", "log_sha256")


def _bloque_procedencia(eval_result: Any, prov: Any, projection: CaseProjection) -> list[Requisito]:
    conformaciones = _conformaciones(prov)
    if conformaciones:
        # El receptor es común; los cuatro de Vina, de cada conformación.
        faltan = [h for h in _HASHES if h not in _HASHES_POR_CONFORMACION and not _v(prov, h)]
        faltan += [f"{h} (#{c.get('indice')})" for c in conformaciones
                   for h in _HASHES_POR_CONFORMACION if not c.get(h)]
        registrados = (f"{len(_HASHES)}/{len(_HASHES)} registrados en cada una de las "
                       f"{len(conformaciones)} conformaciones")
    else:
        faltan = [h for h in _HASHES if not _v(prov, h)]
        registrados = f"{len(_HASHES)}/{len(_HASHES)} registrados"
    hashes = (
        Campo("Hashes de entrada y salida", registrados, Estado.REGISTRADO)
        if prov and not faltan else
        Campo("Hashes de entrada y salida", None, Estado.NO_DISPONIBLE,
              "Faltan: " + ", ".join(faltan) if prov else
              "La corrida no registró su procedencia de ejecución.")
    )

    herramientas = _v(prov, "toolchain")
    version = _v(prov, "app_version")
    versiones = _campo_dato(
        "Versiones de la corrida",
        (f"MolDesign {version} · " if version else "")
        + " · ".join(f"{k} {v}" for k, v in sorted(herramientas.items()))
        if isinstance(herramientas, dict) and herramientas else None,
        "La corrida no registró la cadena de herramientas.",
    )

    protocolo = _v(eval_result, "docking_protocol") or {}
    semilla = _v(protocolo, "seed")
    if semilla is None:
        semilla = _v(eval_result, "vina_random_seed")
    exhaustividad = _v(protocolo, "exhaustiveness")
    parametros = _campo_dato(
        "Semilla y parámetros",
        f"semilla {semilla}" + (f" · exhaustiveness {exhaustividad}" if exhaustividad else "")
        if semilla is not None else None,
        "La corrida no registró la semilla.",
    )

    relacion, _ = relacion_comprobada(projection)
    relacion_campo = {
        "corresponde": Campo("Relación con los inputs del caso",
                             "La corrida se ejecutó con los inputs actuales del caso.",
                             Estado.REGISTRADO),
        "corrida_anterior": Campo(
            "Relación con los inputs del caso", None, Estado.REVISAR,
            "Los inputs del caso cambiaron después de esta corrida: la auditoría describe la "
            "corrida, no la hipótesis actual.",
        ),
        "desconocida": _no_evaluado(
            "Relación con los inputs del caso",
            "La corrida no registró la huella de sus inputs.",
        ),
    }[relacion]

    preflight = projection.preflight
    if preflight is None or relacion != "corresponde":
        razon = (
            "La corrida no quedó atada a una comprobación previa." if preflight is None else
            "La comprobación previa del caso no corresponde a los inputs de esta corrida."
        )
        previa = [
            Requisito("procedencia.previa_bloqueantes",
                      _no_evaluado("Bloqueantes de la comprobación previa", razon),
                      "preflight.blockers", False),
            Requisito("procedencia.previa_advertencias",
                      _no_evaluado("Advertencias de la comprobación previa", razon),
                      "preflight.warnings", False),
            Requisito("procedencia.previa_sin_evaluar",
                      _no_evaluado("Controles previos sin evaluar", razon),
                      "preflight.not_evaluated", False),
        ]
    else:
        previa = [
            Requisito(
                "procedencia.previa_bloqueantes",
                Campo("Bloqueantes de la comprobación previa", ", ".join(preflight.blockers),
                      Estado.ABSTENCION, "La comprobación previa registró bloqueantes técnicos.",
                      valor_es_clasificacion=True)
                if preflight.blockers else
                Campo("Bloqueantes de la comprobación previa", "Ninguno registrado",
                      Estado.REGISTRADO),
                "preflight.blockers", True,
            ),
            Requisito(
                "procedencia.previa_advertencias",
                Campo("Advertencias de la comprobación previa", ", ".join(preflight.warnings),
                      Estado.REVISAR, "Advertencias registradas antes de ejecutar.",
                      valor_es_clasificacion=True)
                if preflight.warnings else
                Campo("Advertencias de la comprobación previa", "Ninguna registrada",
                      Estado.REGISTRADO),
                "preflight.warnings", False,
                rutinaria=RUTINA_PREVIAS_ADVERTENCIAS
                if preflight.warnings and set(preflight.warnings) <= _ADVERTENCIAS_PREVIAS_DE_LA_RUTA else None,
            ),
            Requisito(
                "procedencia.previa_sin_evaluar",
                Campo("Controles previos sin evaluar", ", ".join(preflight.not_evaluated),
                      Estado.NO_EVALUADO,
                      "No se evaluaron: eso no equivale a que los pasaran.",
                      valor_es_clasificacion=True)
                if preflight.not_evaluated else
                Campo("Controles previos sin evaluar", "Ninguno registrado", Estado.REGISTRADO),
                "preflight.not_evaluated", False,
                rutinaria=RUTINA_PREVIAS_SIN_EVALUAR
                if preflight.not_evaluated and set(preflight.not_evaluated) <= _SIN_EVALUAR_PREVIOS_DE_LA_RUTA
                else None,
            ),
        ]

    return [
        Requisito("procedencia.hashes", hashes, "execution_provenance", True),
        Requisito("procedencia.versiones", versiones,
                  "execution_provenance.app_version · toolchain", True),
        Requisito("procedencia.semilla", parametros, "docking_protocol.seed", True),
        Requisito(
            "procedencia.commit",
            _campo_dato("Commit de código", _v(prov, "git_commit"),
                        "La corrida no declaró un commit verificable (bundle o árbol modificado)."),
            "execution_provenance.git_commit",
            False,
            # El instalador nunca declara su commit (`vina_service._source_commit`): pasa en toda corrida.
            rutinaria=None if _v(prov, "git_commit") else RUTINA_COMMIT,
        ),
        Requisito("procedencia.relacion", relacion_campo, "huellas de la corrida y del preflight", False),
        *previa,
    ]


# ── Covalentes, membrana y campo de fuerzas ──────────────────────────

#: Segmentos transmembrana a partir de los cuales la hidropatía no se explica con hélices
#: enterradas de una proteína soluble. Medido en el catálogo (2026-10-10): las solubles dan
#: de 0 a 2 (CYP, polimerasas, topoisomerasas) y los fragmentos de membrana, de 5 a 20.
UMBRAL_SEGMENTOS_TM = 3

_POR_CLASE = {
    "metal": "metal: necesita parámetros de ion o un modelo enlazado",
    "cofactor": "cofactor: necesita parámetros propios",
    "fosforresiduo": "fosforresiduo: necesita parámetros adicionales",
    "otro": "residuo no estándar: necesita parámetros propios",
}


def _requisito_covalente(smiles: Any, contexto: ContextoEstructural | None) -> Requisito:
    from chem.ojivas_covalentes import OJIVAS, ojivas

    grupos = ojivas(smiles) if isinstance(smiles, str) and smiles else None
    if grupos is None:
        return Requisito("ligando.covalente", _no_evaluado(
            "Unión covalente", "La corrida no registró la forma del ligando que se acopló."),
            "ligand_state.smiles_acoplado", False)
    enlaces = contexto.enlaces_covalentes if contexto is not None and contexto.medido else None
    partes = []
    if grupos:
        partes.append(f"Ojiva: {', '.join(grupos)}.")
    if enlaces:
        partes.append(f"Ligando del cristal unido a la proteína: {', '.join(enlaces[:3])}.")
    fuente = "ligand_state.smiles_acoplado · LINK del depósito"
    if partes:
        return Requisito("ligando.covalente", Campo(
            "Unión covalente", " ".join(partes), Estado.REVISAR,
            "Vina acopla el complejo no covalente. Un cálculo de energía libre del inhibidor unido "
            "necesita el aducto, con parámetros para el enlace, o un protocolo covalente; el del "
            "complejo no covalente describe sólo el paso reversible.",
            valor_es_clasificacion=True,
        ), fuente, False,
            accion_recomendada="Declara qué estado describe el cálculo: el complejo no covalente previo o el aducto.")
    razon = f"Se buscaron {len({d for d, _ in OJIVAS})} tipos de ojiva; la lista no es exhaustiva."
    if enlaces is not None:
        razon += " El depósito no une el ligando del cristal a la proteína."
    else:
        razon += " No se consultaron los enlaces del depósito."
    return Requisito("ligando.covalente", Campo(
        "Unión covalente", "Ninguna ojiva covalente conocida", Estado.REGISTRADO, razon,
    ), fuente, False)


def _requisito_campo_del_ligando(smiles: Any) -> Requisito:
    from services.dossier.campo_de_fuerzas import ELEMENTOS_CUBIERTOS, elementos_del_ligando

    datos = elementos_del_ligando(smiles) if isinstance(smiles, str) and smiles else None
    fuente = "ligand_state.smiles_acoplado"
    if datos is None:
        return Requisito("ligando.campo_de_fuerzas", _no_evaluado(
            "Cobertura del campo de fuerzas del ligando",
            "La corrida no registró la forma del ligando que se acopló."), fuente, False)
    presentes, fuera, radical = datos
    if fuera or radical:
        razones = []
        if fuera:
            razones.append(f"Elementos sin parámetros en OpenFF 2 (Sage) ni en GAFF2: {', '.join(fuera)}.")
        if radical:
            razones.append("El ligando es un radical: los campos de fuerzas de uso común no tienen tipos "
                           "de átomo para electrones desapareados.")
        return Requisito("ligando.campo_de_fuerzas", Campo(
            "Cobertura del campo de fuerzas del ligando", ", ".join(presentes), Estado.REVISAR,
            " ".join(razones), valor_es_clasificacion=True,
        ), fuente, False,
            accion_recomendada="Declara qué campo de fuerzas cubre estos elementos o con qué parámetros propios se "
                               "describen.")
    return Requisito("ligando.campo_de_fuerzas", Campo(
        "Cobertura del campo de fuerzas del ligando", ", ".join(presentes), Estado.REGISTRADO,
        f"Todos sus elementos están en OpenFF 2 (Sage) y en GAFF2 ({', '.join(ELEMENTOS_CUBIERTOS)}). "
        + "Es cobertura por elemento: tipos de átomo y cargas se asignan al parametrizar.",
    ), fuente, False)


def _requisito_campo_del_receptor(contexto: ContextoEstructural | None) -> Requisito:
    from services.dossier.campo_de_fuerzas import clase_del_residuo

    fuente = "PDBQT del receptor (por su SHA-256)"
    no_estandar = contexto.no_estandar if contexto is not None else None
    if no_estandar is None:
        return Requisito("receptor.campo_de_fuerzas", _no_evaluado(
            "Cobertura del campo de fuerzas del receptor",
            "El receptor de la corrida no se pudo leer por su SHA-256."), fuente, False)
    if not no_estandar:
        return Requisito("receptor.campo_de_fuerzas", Campo(
            "Cobertura del campo de fuerzas del receptor", "Sólo aminoácidos estándar", Estado.REGISTRADO,
            "Los 20 aminoácidos y sus estados de protonación están en los campos de proteína de uso común "
            "(AMBER ff14SB y ff19SB, CHARMM36m, OPLS).",
        ), fuente, False)
    filas = [f"{nombre} ×{n} ({_POR_CLASE[clase_del_residuo(nombre)]})" for nombre, n in no_estandar.items()]
    return Requisito("receptor.campo_de_fuerzas", Campo(
        "Cobertura del campo de fuerzas del receptor", f"No estándar: {', '.join(filas)}.", Estado.REVISAR,
        "Un campo de proteína estándar no los cubre: el cálculo siguiente tiene que parametrizarlos aparte "
        "y declararlo.",
        valor_es_clasificacion=True,
    ), fuente, False,
        accion_recomendada="Declara con qué parámetros se describe cada uno, o retíralo si no forma parte de "
                           "la hipótesis.")


def _requisito_de_membrana(contexto: ContextoEstructural | None) -> Requisito:
    fuente = "secuencia del receptor · HEADER del depósito"
    if contexto is None or not contexto.medido or contexto.segmentos_tm is None:
        return Requisito("entorno.membrana", _no_evaluado(
            "Proteína de membrana",
            "Sin el archivo depositado, comprobado por la receta del receptor, no se mide su secuencia."), fuente, False)
    cadena, segmentos = max(contexto.segmentos_tm.items(), key=lambda par: par[1], default=("", 0))
    clasificada = "MEMBRANE PROTEIN" in (contexto.clasificacion or "").upper()
    if segmentos >= UMBRAL_SEGMENTOS_TM or clasificada:
        indicios = []
        if segmentos >= UMBRAL_SEGMENTOS_TM:
            indicios.append(f"{segmentos} segmentos transmembrana probables en la cadena {cadena}.")
        if clasificada:
            indicios.append("El depósito la clasifica como «MEMBRANE PROTEIN».")
        if contexto.lipidos:
            indicios.append(f"Lípidos o detergentes en el cristal: {', '.join(contexto.lipidos)}.")
        return Requisito("entorno.membrana", Campo(
            "Proteína de membrana", " ".join(indicios), Estado.REVISAR,
            "El receptor que se entrega no lleva bicapa: un cálculo con disolvente explícito tiene que "
            "insertarlo en una membrana y declarar su composición y orientación.",
            valor_es_clasificacion=True,
        ), fuente, False,
            accion_recomendada="Declara la membrana del sistema (composición y orientación) o por qué el "
                               "cálculo no la necesita.")
    return Requisito("entorno.membrana", Campo(
        "Proteína de membrana", "Sin indicios de proteína de membrana multipaso", Estado.REGISTRADO,
        f"Hidropatía de Kyte-Doolittle (ventanas de {VENTANA_TM}, media ≥ {UMBRAL_TM:g}): {segmentos} "
        f"segmento(s) en la cadena {cadena}; uno o dos aparecen también en proteínas solubles. "
        + "No detecta barriles β ni proteínas monotópicas o de un solo paso.",
    ), fuente, False)


# ── Agregación ───────────────────────────────────────────────────────


def _estado_del_bloque(requisitos: list[Requisito]) -> EstadoBloque:
    if any(r.bloquea for r in requisitos):
        return "BLOQUEADO"
    if any(r.pide_revision for r in requisitos):
        return "REVISION"
    return "REGISTRADO"


def estado_global(requisitos: list[Requisito]) -> tuple[EstadoGlobal, str]:
    """El estado de la auditoría entera. TRANSFERIBLE exige la constante del guardián."""
    if any(r.clave == "receptor.huecos" and r.bloquea for r in requisitos):
        return "BLOQUEADO", 'Hueco del esqueleto junto al sitio: el sistema está bloqueado hasta reparar o cambiar la estructura.'
    if any(r.bloquea for r in requisitos):
        return "BLOQUEADO", "Falta evidencia imprescindible o hay una abstención declarada."
    if any(r.pide_revision for r in requisitos):
        if all(r.rutinaria for r in requisitos if r.pide_revision):
            return "REVISION", RAZON_SOLO_RUTINARIA
        return "REVISION", "Hay decisiones científicas abiertas que el cálculo siguiente heredaría."
    if TRANSFERENCIA_FEP_DEMOSTRADA:
        return "TRANSFERIBLE", "Controles superados para el alcance declarado."
    if any(r.decidido for r in requisitos):
        return "REVISION", (
            "Todos los requisitos tienen dato registrado o una decisión justificada, pero la transferencia "
            "a un cálculo FEP no está demostrada: FEP-06 sigue sin sellar."
        )
    return "REVISION", (
        "Todos los requisitos tienen dato registrado, pero la transferencia a un cálculo "
        "FEP no está demostrada: FEP-06 sigue sin sellar."
    )


#: Código y huella con los que viaja una decisión de Preparación en `projection.decisions`.
PREFIJO_DECISION = "preparacion:"


def huella_de_decision(task_id: Any) -> str:
    return f"tarea:{task_id}"


def _decisiones(projection: CaseProjection, task_id: Any) -> tuple[dict[str, dict[str, Any]], int]:
    """(clave → decisión de esta corrida, cuántas hay sobre otras corridas del caso)."""
    huella = huella_de_decision(task_id)
    propias: dict[str, dict[str, Any]] = {}
    ajenas = 0
    for d in projection.decisions:
        if not d.control_code.startswith(PREFIJO_DECISION):
            continue
        if d.fingerprint != huella:
            ajenas += 1
            continue
        nota = (d.note or "").strip()
        if len(nota) < 3:
            continue
        propias[d.control_code[len(PREFIJO_DECISION):]] = {"justificacion": nota, "registrada": d.at}
    return propias, ajenas


# ── Contexto de ensayo (C-GAP-02) ────────────────────────────────────

def _formato_del_ensayo(campo: str, valor: Any) -> str:
    """El valor tal como se imprime: pH con su número; listas unidas; ∅ si vacía."""
    if campo == "ph":
        return f"pH {float(valor):g}"
    return ", ".join(valor) if valor else "∅"


_RAZON_DISCREPANCIA = {
    "ph": "El ensayo declara pH {e} y el ligando se protonó a pH {c}: la especie acoplada puede no ser la del ensayo.",
    "cadenas": "El constructo del ensayo declara las cadenas {e} y el receptor acoplado contiene {c}.",
    "cofactores": "El ensayo declara {e} y la corrida conservó {c}.",
}
_ACCION_DISCREPANCIA = {
    "ph": "Vuelve a evaluar con el pH del ensayo, o registra una decisión que diga por qué la especie "
          "acoplada sirve igual.",
    "cadenas": "Prepara el receptor con las cadenas del constructo, o registra una decisión que diga por "
               "qué las del receptor representan el ensayo.",
    "cofactores": "Declara en el receptor los cofactores del ensayo y vuelve a evaluar, o registra una "
                  "decisión que diga por qué su ausencia o su presencia no cambia la lectura.",
}
_RAZON_SIN_CORRIDA = {
    "ph": "La corrida no registró a qué pH se protonó el ligando: la comparación con el ensayo no se pudo hacer.",
    "cadenas": "La corrida no registró las cadenas del receptor acoplado: la comparación con el ensayo no se pudo hacer.",
    "cofactores": "La corrida no registró qué cofactores conservó: la comparación con el ensayo no se pudo hacer.",
}


def _requisitos_del_ensayo(projection: CaseProjection, eval_result: Any) -> list[Requisito]:
    """Lo que el ensayo declarado y la corrida dicen del pH, las cadenas y los cofactores.

    Sin contexto de ensayo declarado no hay ningún requisito: lo omitido es
    desconocido y no se convierte en alerta (C-GAP-02). Un campo que el caso no
    declaró tampoco produce requisito. Una discrepancia pide revisión y se resuelve
    con una decisión registrada (`preparacion:entorno.ensayo.<campo>`), como el
    resto de esta auditoría.
    """
    from services.dossier.contexto_ensayo import (
        CAMPOS_CONTRASTABLES, CONTRATO, TOLERANCIA_PH, comparar, declarados_sin_contraparte,
    )

    assay = projection.context.assay
    if assay is None:
        return []
    comparaciones = comparar(assay, eval_result)
    declaradas = [c for c in comparaciones if c.ensayo is not None]
    sin_contraparte = declarados_sin_contraparte(assay)
    salida = [Requisito(
        "entorno.ensayo",
        Campo("Contexto de ensayo",
              f"Contrato {CONTRATO}: {len(declaradas)} campo(s) contrastable(s) declarado(s) y "
              f"{len(sin_contraparte)} sin contraparte en la corrida",
              Estado.REGISTRADO,
              "Temperatura, magnitud medida, constructo y fuente se transmiten tal como los declaró el "
              "caso; la corrida no tiene con qué compararlos."),
        "case.context.assay", False,
        ensayo={"contrato": CONTRATO, "declarados_sin_contraparte": sin_contraparte},
    )]
    for c in declaradas:
        etiqueta = CAMPOS_CONTRASTABLES[c.campo][0]
        clave = f"entorno.ensayo.{c.campo}"
        fuente = f"{c.fuente_ensayo} · {c.fuente_corrida}"
        if c.estado == "desconocido":
            campo = Campo(etiqueta, None, Estado.NO_DISPONIBLE, _RAZON_SIN_CORRIDA[c.campo])
            salida.append(Requisito(clave, campo, fuente, False, ensayo=c.as_dict()))
            continue
        valor = (f"Ensayo {_formato_del_ensayo(c.campo, c.ensayo)} · "
                 f"corrida {_formato_del_ensayo(c.campo, c.corrida)}")
        if c.estado == "coincide":
            razon = (f"Coinciden dentro de ±{TOLERANCIA_PH:g} unidades de pH." if c.campo == "ph"
                     else "Coinciden.")
            campo = Campo(etiqueta, valor, Estado.REGISTRADO, razon)
            salida.append(Requisito(clave, campo, fuente, False, ensayo=c.as_dict()))
        else:
            razon = _RAZON_DISCREPANCIA[c.campo].format(
                e=_formato_del_ensayo(c.campo, c.ensayo).removeprefix("pH "),
                c=_formato_del_ensayo(c.campo, c.corrida).removeprefix("pH "))
            campo = Campo(etiqueta, valor, Estado.REVISAR, razon, valor_es_clasificacion=True)
            salida.append(Requisito(clave, campo, fuente, False, ensayo=c.as_dict(),
                                    accion_recomendada=_ACCION_DISCREPANCIA[c.campo]))
    return salida


def build_preparacion(
    dossier: CaseDossier, eval_result: Any, projection: CaseProjection,
    contexto: ContextoEstructural | None = None,
) -> dict[str, Any]:
    """La auditoría de preparación de la corrida que describe ``dossier``."""
    protocolo = _v(eval_result, "docking_protocol") or {}
    prov = _v(protocolo, "execution_provenance") or {}
    prep = _v(prov, "receptor_prep") or {}

    seccion = campo_de_la_seccion(dossier.catalogo)
    fuente_seccion = "catálogo · services/targets/seccion_catalogo.py"
    bloques = {
        # Demostración pide revisión y no bloquea: la decisión es del investigador. Es la
        # misma para los 381 receptores del catálogo, así que es rutinaria; un sello
        # verificado que no describe esta corrida, no.
        "receptor": _bloque_receptor(prov, prep, contexto) + [Requisito(
            "receptor.seccion_catalogo", seccion, fuente_seccion, False,
            rutinaria=RUTINA_DEMOSTRACION if (dossier.catalogo or {}).get("seccion") == "demostracion"
            and seccion.estado == Estado.REVISAR else None,
        )],
        "ligando": _bloque_ligando(eval_result, prov, contexto),
        "pose": _bloque_pose(dossier, eval_result, prov),
        "entorno": _bloque_entorno(prep, projection, contexto)
        + _requisitos_del_ensayo(projection, eval_result),
        "procedencia": _bloque_procedencia(eval_result, prov, projection),
    }
    decisiones, ajenas = _decisiones(projection, dossier.task_id)
    bloques = {nombre: [replace(r, decision=decisiones[r.clave]) if r.clave in decisiones else r
                        for r in requisitos]
               for nombre, requisitos in bloques.items()}
    todos = [r for requisitos in bloques.values() for r in requisitos]
    estado, razon = estado_global(todos)
    en_revision = [r.clave for r in todos if r.pide_revision]
    rutinarias = [r.clave for r in todos if r.pide_revision and r.rutinaria]

    return {
        "schema": PREPARACION_SCHEMA,
        "alcance": ALCANCE,
        "transferencia_fep_demostrada": TRANSFERENCIA_FEP_DEMOSTRADA,
        "estado": estado,
        "razon": razon,
        "bloqueantes": [r.clave for r in todos if r.bloquea],
        # Todo lo que pide revisión, rutinario o no: la rutinaria sigue abierta.
        "en_revision": en_revision,
        "en_revision_rutinaria": rutinarias,
        # Sin bloqueos, lo único abierto es lo que pide toda corrida de esta ruta.
        "solo_rutinaria": estado == "REVISION" and bool(en_revision) and len(rutinarias) == len(en_revision),
        "decididos": [r.clave for r in todos if r.decidido],
        # Con esta huella se registra una decisión sobre esta corrida.
        "huella_de_decision": huella_de_decision(dossier.task_id),
        "decisiones_de_otras_corridas": ajenas,
        "bloques": [
            {
                "id": nombre,
                "estado": _estado_del_bloque(bloques[nombre]),
                "solo_rutinaria": _estado_del_bloque(bloques[nombre]) == "REVISION"
                and all(r.rutinaria for r in bloques[nombre] if r.pide_revision),
                "requisitos": [r.as_dict() for r in bloques[nombre]],
            }
            for nombre in BLOQUES
        ],
        "corrida": {
            "case_id": dossier.case_id,
            "molecule_id": dossier.molecule_id,
            "task_id": dossier.task_id,
            "target": dossier.target_label,
            "pdb_id": (dossier.catalogo or {}).get("pdb_id"),
        },
        # Sin hash del dossier: incluye la hora de generación y no coincidiría con
        # el del paquete que se descargue después. La corrida la anclan sus
        # hashes de receptor y poses, que van en los requisitos.
        "generated_at": dossier.generated_at,
        "paquete": {
            "rotulo": "Paquete de la corrida",
            "aviso": "Es el paquete reproducible del dossier de esta corrida. No es un paquete FEP.",
        },
    }
