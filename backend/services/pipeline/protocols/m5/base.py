"""M5: lo que es común a cualquier metal, separado de lo que es de zinc.

`docs/74_ARQUITECTURA_DISPATCHER_DE_PROTOCOLOS.md` §6 define M5 como una
familia con un adaptador por metal, no como un algoritmo universal. Este módulo
es la parte que NO depende del metal; `zinc.py` es el primer adaptador.

═══════════════════════════════════════════════════════════════════════════
QUÉ DEL M5 ACTUAL ES UNIVERSAL Y QUÉ ES DE ZINC
═══════════════════════════════════════════════════════════════════════════

Revisado `scoring/ums.py` entero, la respuesta es más asimétrica de lo que
parece: **del scoring no hay casi nada universal.**

Lo que hoy se llama «Universal Metal Score» son siete SMARTS —sulfonamida,
sulfonamida primaria, hidroxámico, tiol, carboxilato, fosfonato, N-hidroxi— y
esos siete son **grupos de unión a zinc** (ZBG). El paper que los valida lo hace
sobre CA2 (sulfonamida), MMP9 (hidroxámico) y ACE (carboxilato/tiol): las tres,
enzimas de zinc.

Algunos solapan con otros metales —el hidroxámico también quela Fe(III), el
carboxilato quela casi todo— pero el ORDEN de preferencia cambia por completo
con el metal: una sulfonamida primaria es un quelante de Zn de primer orden y
un pésimo ligando de Mg. Un score que las trata igual no es universal, es de
zinc aplicado a otra cosa.

Y los pesos tampoco: `0.60·warhead + 0.20·donor + 0.20·molchamb`, con el
componente de warhead en `0.85 + 0.10·min(n/3, 1)` y el divisor de donores en
30, salen del ajuste sobre dianas de zinc.

Lo que **sí** es universal es todo lo que rodea al score, y es lo que vive aquí:

    detectar que la diana TIENE un metal, y cuál          <- este módulo
    conservarlo en la preparación del receptor
    registrar identidad, coordenadas y procedencia        <- este módulo
    saber si existe un adaptador validado para ese metal  <- este módulo
    abstenerse cuando no existe                           <- este módulo
    la máquina de estados de §6.2                         <- este módulo

    los warheads, sus pesos y su dominio medido           <- zinc.py

Dicho de otro modo: la infraestructura es universal, la química no.

═══════════════════════════════════════════════════════════════════════════
CÓMO SE SABE HOY QUE UNA DIANA ES METÁLICA, Y POR QUÉ NO BASTA
═══════════════════════════════════════════════════════════════════════════

La puerta actual de M5 mira `target.structural_family == "metaloenzyme"`: una
etiqueta curada. El §6.1 del documento pide que el contexto metálico esté
sustentado por al menos una fuente registrable, y enumera tres — familia
curada, metal observado en la estructura, y declaración explícita del
investigador.

La segunda existía como función (`services/chemistry/protein_surgery.py::
detect_metals_in_protein`) pero **el pipeline de acoplamiento no la llamaba**, y
además estaba rota: comparaba el NOMBRE del átomo contra los símbolos de metal,
y `CA` es a la vez el calcio y el carbono alfa de todos los aminoácidos. Medido
antes de arreglarla, CDK2 —una quinasa sin un solo ion— devolvía 380 metales.
Corregida, devuelve 0, y MMP9 devuelve sus 2 Zn y 5 Ca reales.

Este módulo la usa ya corregida, y conserva de qué fuente vino cada afirmación.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class EstadoMetal(str, Enum):
    """Qué se hizo de verdad con el metal. §6.2 del documento 74.

    Los tres son cosas distintas y hasta ahora viajaban indistinguibles:
    conservar el ion en el receptor no es evaluar su geometría, y evaluar su
    geometría no es puntuar con un scoring que la tenga en cuenta.
    """

    #: No se detectó metal, o la diana no es metálica.
    SIN_METAL = "sin_metal"
    #: El ion está en el receptor preparado. Nada más.
    METAL_PRESERVADO = "metal_preserved"
    #: Además se midió la geometría metal-ligando sobre una pose.
    GEOMETRIA_EVALUADA = "metal_geometry_evaluated"
    #: Además el scoring usó esa información dentro de su dominio medido.
    SCORING_CON_METAL = "metal_aware_scoring"


class FuenteDelContexto(str, Enum):
    """De dónde sale la afirmación «esta diana es metálica»."""

    FAMILIA_CURADA = "familia_curada"
    OBSERVADO_EN_ESTRUCTURA = "observado_en_estructura"
    DECLARADO_POR_INVESTIGADOR = "declarado_por_investigador"


@dataclass(frozen=True)
class MetalObservado:
    """Un ion concreto, con de dónde salió."""

    elemento: str
    posicion: tuple[float, float, float]
    residuo: str
    cadena: str
    numero: str
    #: Línea del PDB de la que se leyó. La procedencia que pide §6.2.
    linea_origen: int


@dataclass(frozen=True)
class ContextoMetalico:
    """Lo que se sabe del metal de esta diana, y con qué respaldo."""

    es_metalica: bool
    fuentes: tuple[FuenteDelContexto, ...] = ()
    metales: tuple[MetalObservado, ...] = ()
    #: Elementos distintos observados, en mayúsculas.
    elementos: frozenset[str] = frozenset()
    #: Discrepancias entre fuentes, si las hay.
    avisos: tuple[str, ...] = ()
    #: Si se llegó a mirar una estructura. «No se observó metal» y «no se
    #: miró» son afirmaciones distintas y `adaptador_para` las trata distinto.
    estructura_consultada: bool = False


@dataclass(frozen=True)
class AdaptadorM5:
    """Un protocolo de metal, disponible o no."""

    metal: str
    id_protocolo: str
    disponible: bool
    estado_cientifico: str
    #: Dónde se midió. Vacío si no se midió en ninguna parte.
    dominio_medido: tuple[str, ...] = ()
    motivo: str = ""


#: El registro. Zn es el único con adaptador; los demás están DECLARADOS y
#: bloqueados a propósito: §8 del documento pide que existan en el registro
#: para que una diana de hierro no acabe absorbida por M4 sin aviso.
ADAPTADORES: dict[str, AdaptadorM5] = {
    "ZN": AdaptadorM5(
        metal="ZN",
        id_protocolo="M5_ZN",
        disponible=True,
        estado_cientifico="REVIEW",
        dominio_medido=("CA2 (anhidrasa carbónica II)", "MMP9", "ACE"),
        motivo=(
            "Evaluado retrospectivamente sobre tres dianas de zinc. Fuera de "
            "ellas el resultado se marca REVIEW: no hay medición que respalde "
            "la transferencia."
        ),
    ),
    "FE": AdaptadorM5(
        metal="FE", id_protocolo="M5_FE", disponible=False,
        estado_cientifico="BLOCKED_UNTIL_VALIDATED",
        motivo=(
            "El hierro tiene química de coordinación y estados de oxidación "
            "distintos del zinc. Los quelantes que lo caracterizan —catecoles, "
            "hidroxipiridinonas— no están entre los warheads medidos, y los "
            "que sí solapan (hidroxámico) tienen otro orden de preferencia."
        ),
    ),
    "MG": AdaptadorM5(
        metal="MG", id_protocolo="M5_MG", disponible=False,
        estado_cientifico="BLOCKED_UNTIL_VALIDATED",
        motivo=(
            "El magnesio es un ácido duro y prefiere donores de oxígeno; los "
            "fosfatos y dicetoácidos que lo caracterizan no están medidos. Una "
            "sulfonamida, que es el warhead de zinc por excelencia, es un mal "
            "ligando de Mg."
        ),
    ),
    "CA": AdaptadorM5(
        metal="CA", id_protocolo="M5_CA", disponible=False,
        estado_cientifico="BLOCKED_UNTIL_VALIDATED",
        motivo=(
            "El calcio suele ser estructural más que catalítico, y su presencia "
            "en el receptor no implica que el sitio de unión sea metálico. "
            "MMP9 tiene cinco Ca estructurales y un Zn catalítico: tratarlos "
            "igual sería un error de sitio, no sólo de metal."
        ),
    ),
    "MN": AdaptadorM5(
        metal="MN", id_protocolo="M5_MN", disponible=False,
        estado_cientifico="BLOCKED_UNTIL_VALIDATED",
        motivo="Sin conjunto de evaluación ni warheads medidos para manganeso.",
    ),
}


def detectar_contexto_metalico(
    ruta_pdb: str | None = None,
    familia_estructural: str | None = None,
    declarado_por_investigador: bool = False,
) -> ContextoMetalico:
    """Reúne las tres fuentes del §6.1 y dice cuáles respaldan la afirmación.

    No decide el protocolo: sólo establece los hechos. La elección de adaptador
    es de `adaptador_para`, que es donde vive la regla de abstención.
    """
    from scoring.ums import _is_metalloenzyme_family

    fuentes: list[FuenteDelContexto] = []
    avisos: list[str] = []

    por_familia = _is_metalloenzyme_family(familia_estructural)
    if por_familia:
        fuentes.append(FuenteDelContexto.FAMILIA_CURADA)
    if declarado_por_investigador:
        fuentes.append(FuenteDelContexto.DECLARADO_POR_INVESTIGADOR)

    metales: list[MetalObservado] = []
    if ruta_pdb:
        from services.chemistry.protein_surgery import detect_metals_in_protein

        for m in detect_metals_in_protein(ruta_pdb):
            metales.append(MetalObservado(
                elemento=m["element"],
                posicion=m["position"],
                residuo=m.get("residue_name", ""),
                cadena=m.get("chain", ""),
                numero=m.get("residue_seq", ""),
                linea_origen=int(m.get("source_line", 0)),
            ))
        if metales:
            fuentes.append(FuenteDelContexto.OBSERVADO_EN_ESTRUCTURA)

    # Las discrepancias se declaran, no se resuelven por precedencia.
    if por_familia and ruta_pdb and not metales:
        avisos.append(
            "El catálogo declara esta diana como metaloenzima y no se observó "
            "ningún ion metálico en la estructura preparada. O el metal se "
            "perdió en la preparación —no estaba en `cofactors_whitelist`— o la "
            "etiqueta del catálogo no corresponde a esta estructura."
        )
    if metales and not por_familia and not declarado_por_investigador:
        elementos = sorted({m.elemento for m in metales})
        avisos.append(
            f"Se observaron iones {elementos} en la estructura pero el catálogo "
            "no clasifica esta diana como metaloenzima. Un metal presente no "
            "implica un sitio de unión metálico: puede ser estructural."
        )

    return ContextoMetalico(
        es_metalica=bool(fuentes),
        fuentes=tuple(fuentes),
        metales=tuple(metales),
        elementos=frozenset(m.elemento for m in metales),
        avisos=tuple(avisos),
        estructura_consultada=bool(ruta_pdb),
    )


def adaptador_para(contexto: ContextoMetalico) -> AdaptadorM5 | None:
    """El adaptador que corresponde, o `None` si no hay contexto metálico.

    Un adaptador `disponible=False` NO es lo mismo que `None`: significa que la
    diana es metálica y este producto no tiene protocolo para ese metal, que es
    justamente el caso que §6.1 prohíbe degradar a M4 en silencio.

    Cuando hay varios metales se elige el que tenga adaptador disponible; si
    ninguno lo tiene, el primero por orden alfabético, para que la respuesta sea
    determinista y no dependa del orden del archivo PDB.
    """
    if not contexto.es_metalica:
        return None

    if not contexto.elementos:
        # ── Metálica por etiqueta, sin metal observado ────────────────────
        #
        # La primera versión devolvía aquí el adaptador de zinc, razonando que
        # es el único que existe. Eso es la misma degradación silenciosa que
        # §6.1 prohíbe, un nivel más arriba: en vez de caer a M4 sin avisar,
        # se caía a «zinc» sin saber si hay zinc.
        #
        # Hay dos casos y no son el mismo:
        if FuenteDelContexto.OBSERVADO_EN_ESTRUCTURA in contexto.fuentes:
            # No puede pasar (esa fuente implica elementos), pero se cubre.
            return ADAPTADORES["ZN"]

        if contexto.estructura_consultada:
            # Se miró la estructura y NO había metal. Que el catálogo diga
            # metaloenzima no pone un ion en el sitio: o se perdió en la
            # preparación o la etiqueta no corresponde a esta estructura.
            return AdaptadorM5(
                metal="?",
                id_protocolo="M5_SIN_METAL_OBSERVADO",
                disponible=False,
                estado_cientifico="BLOCKED",
                motivo=(
                    "La diana está declarada como metálica pero no se observó "
                    "ningún ion en la estructura preparada. Sin saber qué metal "
                    "es no se puede elegir adaptador, y asumir zinc sería "
                    "inventar la química del sitio."
                ),
            )

        # No se consultó ninguna estructura: no se puede confirmar ni negar.
        # Se conserva el comportamiento actual —el único adaptador que hay—
        # pero declarándolo, en vez de en silencio.
        return AdaptadorM5(
            metal="ZN",
            id_protocolo="M5_ZN",
            disponible=True,
            estado_cientifico="REVIEW",
            dominio_medido=ADAPTADORES["ZN"].dominio_medido,
            motivo=(
                "Metálica según el catálogo, sin estructura consultada para "
                "confirmar de qué metal se trata. Se usa el adaptador de zinc "
                "por ser el único disponible; el resultado queda en REVIEW."
            ),
        )

    con_adaptador = [
        ADAPTADORES[e] for e in sorted(contexto.elementos)
        if e in ADAPTADORES and ADAPTADORES[e].disponible
    ]
    if con_adaptador:
        return con_adaptador[0]

    conocidos = [ADAPTADORES[e] for e in sorted(contexto.elementos) if e in ADAPTADORES]
    if conocidos:
        return conocidos[0]

    elemento = sorted(contexto.elementos)[0]
    return AdaptadorM5(
        metal=elemento,
        id_protocolo=f"M5_{elemento}",
        disponible=False,
        estado_cientifico="BLOCKED",
        motivo=(
            f"Se observó {elemento} en el sitio y no existe adaptador para ese "
            "metal. No se degrada a M4 en silencio."
        ),
    )
