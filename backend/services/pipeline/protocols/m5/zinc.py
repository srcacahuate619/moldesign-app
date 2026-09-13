"""M5-Zn V2: los tres perfiles autorizados, y la abstención fuera de ellos.

Implementa `docs/75_DECISION_CIENTIFICA_M5_ZN_V1.md`. Ese ADR es normativo: si
algo de aquí y algo de allí discrepan, manda el ADR y esto es el defecto.

═══════════════════════════════════════════════════════════════════════════
NO HAY UN PESO M5 UNIVERSAL
═══════════════════════════════════════════════════════════════════════════

V1 no define un peso familiar genérico. Define tres perfiles exactos, uno por
cada diana con comparación de pipeline disponible, y **se abstiene de calcular
un score compuesto fuera de ese dominio**.

    CA2  / 3DC3   0.20·Vina_norm + 0.20·XGB + 0.20·GNN-D + 0.40·UMS
    MMP9 / 1GKC                    0.75·XGB              + 0.25·UMS
    ACE  / 1O86   0.20·Vina_norm + 0.40·XGB              + 0.40·UMS

Sustituye dos comportamientos que no reproducen ningún experimento:

  - el ajuste de UMS en `scoring/engine.py`, con peso máximo 0.06 que además
    ENCOGE según la confianza del stack;
  - la entrada `clgnn=1.0` de `stacking_weights.json` para toda la familia.

Sobre la segunda: **CA2 usa GNN-D, no CL-GNN.** Por eso no bastaba con cambiar
0.06 por 0.40 — la entrada genérica no reproduce ninguno de los tres.

═══════════════════════════════════════════════════════════════════════════
POR QUÉ ESTO ES V2, Y QUÉ CAMBIÓ RESPECTO A V1
═══════════════════════════════════════════════════════════════════════════

V1 reproducía `data/molchamb_loto/delong_paired_report.json` a precisión de
máquina. **V2 ya no, y es lo correcto**: el §2 del ADR dice que cambiar un
patrón de warhead crea una versión de protocolo nueva, y aquí cambiaron dos
cosas del detector, las dos por defecto:

1. **`"N(O)"` casaba cualquier grupo nitro.** En SMARTS es «nitrógeno alifático
   unido por enlace simple a oxígeno alifático», y el enlace N–[O-] de un nitro
   es exactamente eso. El nitro no coordina zinc y es uno de los grupos más
   comunes de la química medicinal: el nitrobenceno puntuaba como un quelante.
2. **`n_warheads` contaba claves, no grupos.** Una sulfonamida primaria casa
   `sulfonamide` y `primary_sulfonamide`; un hidroxámico lleva un N–OH dentro.
   La fórmula `0.85 + 0.10·min(n/3, 1)` es monótona en n, así que un solo grupo
   funcional entraba valiendo el doble.

Rehechas las AUC sobre los MISMOS checkpoints, con los mismos pesos y la misma
normalización, sólo cambiando el detector:

    perfil    n     pos    AUC M4     V1        V2        delta
    CA2     1933     37    0.8042   0.9314    0.9507    +0.0193
    MMP9    1925     50    0.8473   0.9208    0.9289    +0.0081
    ACE     2003     46    0.4362   0.6708    0.7179    +0.0471

Ordena MEJOR en los tres. Eso dice que la corrección no degradó nada; **no dice
que los perfiles estén validados**, porque dos de los tres benchmarks siguen en
cuarentena por el sitio (ver la sección siguiente) y las AUC de arriba se miden
sobre esos mismos datos.

Las tres constantes de normalización no cambian y siguen saliendo exactas del
máximo de |Vina| de cada checkpoint: 10.450, 8.247 y 9.566.

`tests/test_m5_zn_perfiles.py` ancla las comprobaciones.

═══════════════════════════════════════════════════════════════════════════
DOS DE LOS TRES PERFILES ESTÁN EN CUARENTENA
═══════════════════════════════════════════════════════════════════════════

Las AUC de arriba son reproducibles. Lo que el 2026-09-04 dejó de estar claro
es QUÉ miden.

Reconstruyendo la caja real desde las poses guardadas en los propios
checkpoints, los benchmarks de MMP9 y ACE **no acoplaron en el sitio del zinc
catalítico**:

    MMP9 / 1GKC   18.74 Å del Zn · 4.96 Å de un ion de CALCIO ·
                  16.44 Å del inhibidor cristalográfico NFH
    ACE  / 1O86   centroide de las poses a 13.14 Å del Zn, con 75.8% fuera
                  del semilado de 12.5 Å declarado

Los dos pasan a `EstadoM5Zn.BENCHMARK_EN_REVISION`. El score se sigue
calculando —es reproducible y sirve para comparar corridas entre sí— pero no
puede presentarse como validado. Los checkpoints no se tocan: son la prueba.

`docs/77_CORRIGENDUM_SITIO_DEL_BENCHMARK_M5_ZN.md` y
`scripts/auditar_sitio_m5.py`.

═══════════════════════════════════════════════════════════════════════════
UMS AQUÍ ES SMARTS-ONLY
═══════════════════════════════════════════════════════════════════════════

La señal autorizada es la variante de warheads pura, no el UMS histórico que
mezcla warheads, número de donantes y MolChamb (`scoring/ums.py::
compute_universal_metal_score`). Ese histórico sigue existiendo porque hay
artefactos que lo usaron, pero NO es lo que entra en estos tres perfiles.

`ums_warhead_score` de este módulo es la única implementación de producción.
`scripts/bootstrap_ci.py::warhead_only_score` calcula lo mismo y lo dice en su
docstring; `scripts/compute_ace_m5.py` NO —usa el histórico— y por eso su
reporte no es comparable con el de DeLong. Ver §9.4 del ADR.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# ── La señal autorizada ──────────────────────────────────────────────────

def ums_warhead_score(n_warheads: int) -> float:
    """El UMS de los tres perfiles. SMARTS puro, sin donantes ni MolChamb.

    Transcrito del §2 del ADR:

        0.0 si no hay warhead; 0.85 + 0.10·min(n/3, 1) si lo hay.

    Cambiar patrones, normalización o escala crea una versión de protocolo
    nueva y obliga a regenerar la evidencia científica. No es un parámetro.
    """
    if n_warheads <= 0:
        return 0.0
    return 0.85 + 0.10 * min(n_warheads / 3.0, 1.0)


def contar_warheads(smiles: str) -> int:
    """Cuántos GRUPOS de unión a zinc distintos hay. Ver `scoring/ums.py`.

    Cuenta grupos químicos, no claves que casaron. Contaba claves, y varias de
    las siete describen el mismo grupo: una sulfonamida primaria casa también
    `sulfonamide`, y un ácido hidroxámico lleva un N–OH dentro. La acetazolamida
    entraba en la fórmula con n=2 por un único grupo funcional, y `0.85 +
    0.10·min(n/3, 1)` es monótona en n: el doble conteo subía el score.
    """
    from scoring.ums import contar_warheads_distintos, detect_warheads

    return contar_warheads_distintos(detect_warheads(smiles))


def ums_desde_smiles(smiles: str) -> float:
    return ums_warhead_score(contar_warheads(smiles))


def vina_normalizada(vina_kcal_mol: float, referencia_max: float) -> float:
    """|Vina| / referencia, acotado a 1.

    La referencia está CONGELADA por perfil. Los benchmarks usaban el máximo de
    la cohorte cargada, lo que hacía que el score de una molécula dependiera de
    sus vecinas: dos corridas del mismo caso con distinto lote daban números
    distintos. Ver §3 del ADR.
    """
    return min(abs(float(vina_kcal_mol)) / referencia_max, 1.0)


# ── Estados ──────────────────────────────────────────────────────────────

class EstadoM5Zn(str, Enum):
    """Qué se puede afirmar del resultado. §5 y §7 del ADR."""

    #: Perfil exacto, todos los componentes presentes. El único con score.
    VALIDADO = "VALIDATED_PROFILE"
    #: Falta un componente con peso distinto de cero. No se renormaliza.
    FALTA_COMPONENTE = "NOT_EVALUATED_MISSING_COMPONENT"
    #: Misma proteína, otra estructura. El nombre no hereda el perfil.
    FUERA_DE_ESTRUCTURA = "REVIEW_OUT_OF_VALIDATED_STRUCTURE"
    #: Otra metaloenzima de zinc. Se ejecuta la auditoría, no el score.
    FUERA_DE_DIANA = "REVIEW_OUT_OF_VALIDATED_TARGET"
    #: Otro metal sin adaptador.
    SIN_PROTOCOLO = "BLOCKED_PROTOCOL_NOT_AVAILABLE"
    #: El perfil existe y su score se calcula, pero se DEMOSTRÓ que el
    #: benchmark que lo validó no acopló en el sitio del zinc catalítico.
    #:
    #: NO es lo mismo que FUERA_DE_DIANA: allí el perfil no existe para ese PDB;
    #: aquí existe, se resuelve y produce un número —que sigue siendo
    #: reproducible— pero no se puede presentar como validado.
    BENCHMARK_EN_REVISION = "REVIEW_INVALID_BENCHMARK_SITE"
    #: No se demostró que el sitio sea incorrecto, pero tampoco se puede
    #: verificar la procedencia: falta el complejo cristalográfico, o el
    #: artefacto no registra la caja efectiva, o su integridad tiene huecos.
    #:
    #: La distinción con el estado anterior es la que separa «sabemos que está
    #: mal» de «no podemos comprobar que esté bien», y confundirlas fue
    #: exactamente el error del 2026-09-04: ACE se invalidó con un criterio
    #: geométrico equivocado. Ver §1.2 y §7 del corrigendum.
    PROCEDENCIA_INCOMPLETA = "REVIEW_BENCHMARK_PROVENANCE_INCOMPLETE"
    #: La caja SÍ contenía el metal, y aun así ninguna pose **top-1** de ningún
    #: activo coloca un átomo donante en su entorno. Esas top-1 son las que
    #: produjeron las features y sostienen el AUC.
    #:
    #: El nombre dice TOP1 y no «no probó el metal» a propósito: el checkpoint
    #: descartó las poses alternativas, así que **no se puede saber** si alguna
    #: de ellas coordinaba. Afirmar que la búsqueda nunca exploró la
    #: coordinación convertiría «oráculo ausente» en «muestreo fallido», que es
    #: una conclusión que el artefacto no sostiene.
    #:
    #: Es un estado distinto de los dos anteriores: no es que la caja estuviera
    #: mal, ni que no se pueda comprobar — es que lo que se puntuó no coordina.
    TOP1_SIN_COORDINACION = "REVIEW_BENCHMARK_TOP1_NOT_METAL_COORDINATING"


# ── Los tres perfiles ────────────────────────────────────────────────────

@dataclass(frozen=True)
class PerfilM5Zn:
    """Un perfil exacto: fórmula, constantes, checkpoint y referencia."""

    protocol_id: str
    diana: str
    pdb_id: str
    #: Pesos. Un componente con peso 0.0 NO entra: no se le da peso por estar
    #: disponible (§4.2 del ADR).
    peso_vina: float
    peso_xgb: float
    peso_gnn_d: float
    peso_ums: float
    #: Congelada. Ver `vina_normalizada`.
    vina_reference_max: float
    checkpoint: str
    checkpoint_sha256: str
    auc_m4_referencia: float
    auc_m5_referencia: float
    #: ── Cuarentena del benchmark (2026-09-04) ────────────────────────
    #:
    #: `None` = el benchmark que validó este perfil sigue en pie.
    #: Un texto = el motivo por el que NO, y entonces el perfil no puede
    #: producir `VALIDADO` aunque sus componentes estén todos presentes.
    #:
    #: Ver `docs/77_CORRIGENDUM_SITIO_DEL_BENCHMARK_M5_ZN.md`. El score se
    #: sigue CALCULANDO —es reproducible— pero no se presenta como validado.
    cuarentena: str | None = None
    #: Qué estado produce esa cuarentena. Son dos cosas distintas:
    #:
    #:   BENCHMARK_EN_REVISION      se demostró que el sitio es incorrecto
    #:   PROCEDENCIA_INCOMPLETA     no se pudo comprobar que sea correcto
    #:
    #: Tenerlas separadas no es un matiz: la primera versión del auditor
    #: comparaba distancias euclídeas contra el semilado de un CUBO —es decir,
    #: contra su esfera inscrita— y con eso ACE parecía tener el 75.8% de sus
    #: poses fuera. Con el criterio por eje, la nube entera cae dentro.
    estado_de_cuarentena: "EstadoM5Zn | None" = None

    @property
    def en_cuarentena(self) -> bool:
        return bool(self.cuarentena)

    @property
    def componentes_requeridos(self) -> tuple[str, ...]:
        requeridos = []
        if self.peso_vina:
            requeridos.append("vina")
        if self.peso_xgb:
            requeridos.append("xgb")
        if self.peso_gnn_d:
            requeridos.append("gnn_d")
        if self.peso_ums:
            requeridos.append("ums")
        return tuple(requeridos)

    @property
    def formula(self) -> str:
        partes = []
        for peso, nombre in (
            (self.peso_vina, "Vina_norm"),
            (self.peso_xgb, "XGBoost"),
            (self.peso_gnn_d, "GNN-D"),
            (self.peso_ums, "UMS_warhead"),
        ):
            if peso:
                partes.append(f"{peso:.2f}*{nombre}")
        return " + ".join(partes)


#: Los tres perfiles autorizados, indexados por PDB canónico en mayúsculas.
#:
#: CA2 pide GNN-D y NO CL-GNN. Si GNN-D falta, el score queda NOT_EVALUATED: no
#: se sustituye por CL-GNN ni se reparten sus pesos (§4.1 del ADR).
PERFILES: dict[str, PerfilM5Zn] = {
    "3DC3": PerfilM5Zn(
        protocol_id="M5_ZN_CA2_3DC3_V2",
        diana="CA2",
        pdb_id="3DC3",
        peso_vina=0.20,
        peso_xgb=0.20,
        peso_gnn_d=0.20,
        peso_ums=0.40,
        vina_reference_max=10.450,
        checkpoint="data/gnn_v31/checkpoints/benchmark_checkpoint_ca2.json",
        checkpoint_sha256="92f5c3dcc5d0bbe13159ea44ad2516a3596e217bebdc6903909236dbe1233e49",
        auc_m4_referencia=0.8042108564260463,
        auc_m5_referencia=0.9506927813889839,
    ),
    "1GKC": PerfilM5Zn(
        protocol_id="M5_ZN_MMP9_1GKC_V2",
        diana="MMP9",
        pdb_id="1GKC",
        peso_vina=0.0,
        peso_xgb=0.75,
        peso_gnn_d=0.0,
        peso_ums=0.25,
        vina_reference_max=8.247,
        cuarentena=(
            "NINGUN zinc cae dentro de la caja declarada por el criterio por eje: "
            "el catalitico ZN A1450 queda fuera por dz=-17.34 con semilado 12.5. "
            "El inhibidor cristalografico NFH A1448 tiene solo 4 de sus 22 atomos "
            "dentro, y el ion de CALCIO CA A1447 si esta dentro, a 4.7 A del "
            "centro. Medido atomo a atomo sobre los 50 activos, el donante mas "
            "cercano queda a 14.91 A del zinc (mediana 16.99). 0.75 del score "
            "depende de features de esa pose. Ver "
            "docs/77_CORRIGENDUM_SITIO_DEL_BENCHMARK_M5_ZN.md §1.1."
        ),
        estado_de_cuarentena=EstadoM5Zn.BENCHMARK_EN_REVISION,
        checkpoint="data/benchmark_checkpoint_mmp9.json",
        checkpoint_sha256="593b50762830bb475ea361bcb7e5f5e525811545f562339675304eeae94c4bf3",
        auc_m4_referencia=0.8472693333333332,
        auc_m5_referencia=0.9289066666666667,
    ),
    "1O86": PerfilM5Zn(
        protocol_id="M5_ZN_ACE_1O86_V2",
        diana="ACE",
        pdb_id="1O86",
        peso_vina=0.20,
        peso_xgb=0.40,
        peso_gnn_d=0.0,
        peso_ums=0.40,
        vina_reference_max=9.566,
        cuarentena=(
            "El sitio era CORRECTO —ZN A701 es el centro exacto de la caja y las "
            "poses caen dentro— y aun asi, de los 47 activos evaluables (de 50), "
            "NINGUNA pose top-1 coloca un atomo donante a <=4.0 A del metal: "
            "minima 6.13 A, mediana 11.04. Esas top-1 son las que produjeron las "
            "features y sostienen el AUC. Los inhibidores de ACE del tipo "
            "lisinopril quelan zinc, asi que lo que se puntuo no reproduce su "
            "modo de union. NO se sabe si alguna pose descartada si coordinaba: "
            "el checkpoint guardo solo la top-1. La procedencia ademas esta "
            "incompleta —falta el complejo cristalografico y ningun artefacto "
            "registra la caja efectiva— y el AUC de casos completos, 0.6708, "
            "baja a 0.5612 bajo imputacion adversa de los ausentes, lo que mide "
            "su fragilidad y no una correccion. Ver "
            "docs/77_CORRIGENDUM_SITIO_DEL_BENCHMARK_M5_ZN.md §1.2 y §8."
        ),
        estado_de_cuarentena=EstadoM5Zn.TOP1_SIN_COORDINACION,
        checkpoint="data/benchmark_checkpoint_ace.json",
        checkpoint_sha256="f646d7fb7b2e3946f638beaa213cf57d9dff9c6d37630fd1d8db593182973fb2",
        auc_m4_referencia=0.43623780853569133,
        auc_m5_referencia=0.7178800737597476,
    ),
}


def perfil_para(pdb_id: str | None) -> PerfilM5Zn | None:
    """El perfil de este PDB, o `None`.

    Se compara el PDB EXACTO, no el nombre de la proteína: §7.1 del ADR dice
    que otra estructura de la misma proteína puede cambiar cadena, bolsillo,
    metal, cofactores, aguas y caja, así que no hereda el perfil.
    """
    if not pdb_id:
        return None
    return PERFILES.get(pdb_id.strip().upper())


# ── El cálculo, con sus abstenciones ─────────────────────────────────────

@dataclass(frozen=True)
class ResultadoM5Zn:
    """El resultado, con el score o la razón de no haberlo."""

    estado: EstadoM5Zn
    #: `None` en estados sin score. En REVIEW el numero puede conservarse como evidencia auditable; un neutro fabricado no cuenta como evaluacion.

    m5_score: float | None
    protocol_id: str | None
    formula: str | None
    #: Las señales que sí existen, se usen o no en el score.
    señales: dict
    #: Qué faltó, si faltó algo.
    componentes_ausentes: tuple[str, ...]
    motivo: str


def calcular(
    *,
    pdb_id: str | None,
    smiles: str,
    vina_kcal_mol: float | None = None,
    xgb_prob: float | None = None,
    gnn_d_prob: float | None = None,
    hay_zinc_confirmado: bool = False,
    familia_normalizada: str | None = None,
) -> ResultadoM5Zn:
    """El score M5-Zn si el caso corresponde a un perfil exacto; si no, la razón.

    Las reglas de abstención son las del §5 y §7 del ADR, y ninguna se relaja:
    no se renormalizan pesos, no se sustituye un modelo por otro, y un valor
    neutral fabricado no cuenta como evaluación.
    """
    import math

    señales = {
        "vina_kcal_mol": vina_kcal_mol,
        "xgb_prob": xgb_prob,
        "gnn_d_prob": gnn_d_prob,
        "n_warheads": contar_warheads(smiles) if smiles else None,
    }
    if señales["n_warheads"] is not None:
        señales["ums_warhead"] = ums_warhead_score(señales["n_warheads"])

    perfil = perfil_para(pdb_id)
    if perfil is None:
        # §7.1 y §7.2: se ejecuta la auditoría común, no el score.
        return ResultadoM5Zn(
            estado=EstadoM5Zn.FUERA_DE_DIANA,
            m5_score=None,
            protocol_id=None,
            formula=None,
            señales=señales,
            componentes_ausentes=(),
            motivo=(
                f"El PDB «{pdb_id}» no es ninguno de los tres perfiles validados "
                f"({', '.join(sorted(PERFILES))}). M5-Zn prepara, conserva el Zn, "
                "ejecuta Vina y calcula señales diagnósticas, pero no hereda los "
                "pesos de otra diana: el score compuesto queda sin calcular."
            ),
        )

    if not hay_zinc_confirmado:
        # §8: un warhead del ligando es una feature, no una condición
        # suficiente. Sin centro metálico confirmado no hay caso metálico.
        return ResultadoM5Zn(
            estado=EstadoM5Zn.FUERA_DE_DIANA,
            m5_score=None,
            protocol_id=perfil.protocol_id,
            formula=perfil.formula,
            señales=señales,
            componentes_ausentes=("zinc_confirmado",),
            motivo=(
                "El PDB corresponde a un perfil validado pero no se confirmó el "
                "Zn en el snapshot estructural ni en el bolsillo. Un carboxilato, "
                "tiol o sulfonamida en el ligando no convierte el caso en "
                "metaloenzima."
            ),
        )

    disponibles = {
        "vina": vina_kcal_mol,
        "xgb": xgb_prob,
        "gnn_d": gnn_d_prob,
        "ums": señales.get("ums_warhead"),
    }
    ausentes = tuple(
        nombre for nombre in perfil.componentes_requeridos
        if disponibles.get(nombre) is None
        or (isinstance(disponibles.get(nombre), float)
            and not math.isfinite(disponibles[nombre]))
    )
    if ausentes:
        return ResultadoM5Zn(
            estado=EstadoM5Zn.FALTA_COMPONENTE,
            m5_score=None,
            protocol_id=perfil.protocol_id,
            formula=perfil.formula,
            señales=señales,
            componentes_ausentes=ausentes,
            motivo=(
                f"Faltan componentes con peso distinto de cero: {', '.join(ausentes)}. "
                "No se renormalizan pesos ni se sustituye un modelo por otro; las "
                "señales que sí existen se muestran por separado."
            ),
        )

    # Un componente con peso 0.0 NO se evalúa, ni siquiera para multiplicarlo
    # por cero: MMP9 no usa Vina, y `vina_normalizada(None, ...)` reventaba.
    # §4.2 del ADR: «pueden conservarse como observaciones, pero no entran en
    # este score. No se les asigna peso por estar disponibles.»
    score = 0.0
    if perfil.peso_vina:
        score += perfil.peso_vina * vina_normalizada(
            vina_kcal_mol, perfil.vina_reference_max
        )
    if perfil.peso_xgb:
        score += perfil.peso_xgb * float(xgb_prob)
    if perfil.peso_gnn_d:
        score += perfil.peso_gnn_d * float(gnn_d_prob)
    if perfil.peso_ums:
        score += perfil.peso_ums * float(señales["ums_warhead"])
    # ── El corte de la cuarentena ────────────────────────────────────
    #
    # El score SE CALCULA y se devuelve: sigue siendo reproducible y sirve para
    # comparar corridas entre sí. Lo que no se puede es llamarlo VALIDADO,
    # porque el benchmark que sostenía esa palabra acopló fuera del sitio del
    # zinc catalítico. Ver docs/77_CORRIGENDUM_SITIO_DEL_BENCHMARK_M5_ZN.md.
    #
    # Ocultar el número habría sido la otra tentación, y es peor: dejaría de
    # poder auditarse justo cuando hace falta auditarlo.
    if perfil.en_cuarentena:
        return ResultadoM5Zn(
            estado=perfil.estado_de_cuarentena or EstadoM5Zn.BENCHMARK_EN_REVISION,
            m5_score=round(score, 6),
            protocol_id=perfil.protocol_id,
            formula=perfil.formula,
            señales=señales,
            componentes_ausentes=(),
            motivo=(
                f"Perfil {perfil.protocol_id}: score calculado y REPRODUCIBLE, "
                f"pero su benchmark está en revisión. {perfil.cuarentena} "
                "No debe leerse como evidencia de acoplamiento metaloproteico."
            ),
        )

    return ResultadoM5Zn(
        estado=EstadoM5Zn.VALIDADO,
        m5_score=round(score, 6),
        protocol_id=perfil.protocol_id,
        formula=perfil.formula,
        señales=señales,
        componentes_ausentes=(),
        motivo=(
            f"Perfil {perfil.protocol_id}. Score de ranking derivado, no una "
            f"afinidad ni una medida experimental. Normalización de Vina "
            f"congelada en {perfil.vina_reference_max}."
        ),
    )
