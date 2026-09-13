"""Conecta M5-Zn a una corrida real: qué señales entran y qué se persiste.

`docs/75_DECISION_CIENTIFICA_M5_ZN_V1.md` §4, §5, §7 y §8.

═══════════════════════════════════════════════════════════════════════════
POR QUÉ EXISTE ESTE MÓDULO
═══════════════════════════════════════════════════════════════════════════

`zinc.py` implementa los tres perfiles y no lo llamaba nadie. El protocolo
estaba escrito, probado, con su manifiesto y sus AUC reproducidas a precisión
de máquina — y no se ejecutaba en ninguna corrida. Un dossier llegó a decir
«calculado con el perfil exacto» sobre un cálculo que no ocurría.

Aquí vive la traducción entre lo que una corrida tiene y lo que la fórmula
pide. Vive en UN sitio porque hay DOS ejecutores —`queue_handler` y el `runner`
configurable— y duplicar esta decisión es lo que el documento 74 quiere
deshacer.

═══════════════════════════════════════════════════════════════════════════
QUÉ SEÑAL ES CADA COSA
═══════════════════════════════════════════════════════════════════════════

    Vina_norm    la afinidad de Vina normalizada por el máximo CONGELADO del
                 perfil, no por el máximo de la cohorte cargada — eso hacía que
                 el score de una molécula dependiera de sus vecinas.

    XGBoost      `xgb_score`, la probabilidad del clasificador de binder.

    UMS_warhead  la variante SMARTS-only del §2. **No** es `ums_score`, que es
                 el UMS histórico —warheads + donantes + MolChamb— y sigue
                 existiendo porque hay artefactos que lo usaron. Se persisten
                 los dos por separado: mezclarlos es el error del §9.4.

    GNN-D        NO TIENE PRODUCTOR EN PRODUCCIÓN. `gnn_d_prob` sólo aparece en
                 los checkpoints de benchmark y en los scripts de análisis; los
                 pesos entrenados están en `rescoring/artifacts/backup_.../`
                 como modelos LOTO, uno por diana excluida.

                 Sólo CA2/3DC3 la pide, con peso 0.20. Mientras no exista ese
                 productor, CA2 devuelve `NOT_EVALUATED_MISSING_COMPONENT`
                 nombrando `gnn_d`. Es lo que ordena el §4.1: no se sustituye
                 por CL-GNN ni se redistribuyen sus pesos.

                 MMP9 y ACE no la usan y sí calculan un score con las señales
                 que la corrida tiene — pero desde el 2026-09-04 los dos están
                 en CUARENTENA: sus benchmarks no acoplaron en el sitio del
                 zinc catalítico, así que devuelven
                 `REVIEW_INVALID_BENCHMARK_SITE` con el número calculado al
                 lado. Ver `docs/77_CORRIGENDUM_SITIO_DEL_BENCHMARK_M5_ZN.md`.

                 Hoy NINGÚN perfil produce `VALIDATED`.

═══════════════════════════════════════════════════════════════════════════
EL ZINC SE CONFIRMA, NO SE SUPONE
═══════════════════════════════════════════════════════════════════════════

§8: un carboxilato, un tiol o una sulfonamida en el ligando son una feature,
no una condición suficiente. El caso sólo es metálico si el metal está en la
estructura o si el catálogo lo declara. Esa comprobación la hace
`base.detectar_contexto_metalico`, que además DECLARA las discrepancias entre
fuentes en vez de resolverlas por precedencia.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from services.pipeline.protocols.m5.zinc import (
    EstadoM5Zn,
    calcular,
    contar_warheads,
    perfil_para,
    ums_warhead_score,
)


@dataclass(frozen=True)
class SalidaM5Zn:
    """Lo que la corrida persiste. Todo puede ser `None`, y eso significa algo."""

    #: `None` cuando el PDB no es ninguno de los tres perfiles validados.
    protocol_id: str | None
    #: `None` en estados sin score; en REVIEW puede conservarse como evidencia.
    score: float | None
    #: El estado del ADR, siempre presente: dice por qué el score es lo que es.
    estado: str
    #: La señal SMARTS-only autorizada. Se calcula aunque no haya perfil,
    #: porque es una propiedad de la molécula y sirve de diagnóstico.
    ums_warhead: float | None
    #: Los componentes con peso distinto de cero que faltaron.
    componentes_ausentes: tuple[str, ...] = ()
    #: Discrepancias entre las fuentes del contexto metálico, sin resolver.
    avisos: tuple[str, ...] = field(default=())

    def as_columns(self) -> dict[str, Any]:
        """Las columnas de `evaluation_results`, tal cual."""
        return {
            "m5_protocol_id": self.protocol_id,
            "m5_score": self.score,
            "m5_scientific_status": self.estado,
            "m5_missing_components": list(self.componentes_ausentes),
            "ums_warhead": self.ums_warhead,
        }


def _estructura_original(pdb_id: str | None) -> str | None:
    """La estructura CRUDA de la diana, sembrada desde el bundle si hace falta.

    Se mira la original y no el receptor preparado por dos motivos:

      · `detect_metals_in_protein` lee la columna de elemento (77-78) de las
        líneas HETATM de un PDB. Un `.pdbqt` pone ahí el tipo de átomo de
        AutoDock, así que preguntarle a un receptor preparado devolvería cero
        metales — un «no hay zinc» que en realidad es «no se supo mirar».
      · la pregunta que M5 hace es si la DIANA es una metaloenzima de zinc, y
        eso es una propiedad de la estructura depositada, no de lo que la
        preparación conservó. Si la preparación perdió el metal,
        `detectar_contexto_metalico` lo declara como discrepancia entre fuentes
        en vez de resolverlo por precedencia.
    """
    if not pdb_id:
        return None
    try:
        from services.semilla_estructuras import sembrar_una

        ruta = sembrar_una(pdb_id)
    except Exception:
        return None
    return str(ruta) if ruta else None


def ums_autorizado(smiles: str | None) -> float | None:
    """El UMS SMARTS-only, o `None` si no hay SMILES legible.

    Cero warheads es una OBSERVACIÓN —la molécula no tiene ninguno, y el score
    correspondiente es 0.0—; no poder leer el SMILES no lo es. Por eso lo
    segundo devuelve `None` y lo primero un número.
    """
    if not smiles:
        return None
    try:
        return ums_warhead_score(contar_warheads(smiles))
    except Exception:
        return None


def ejecutar(
    *,
    smiles: str | None,
    target_pdb_id: str | None,
    target_family: str | None,
    vina_kcal_mol: float | None,
    xgb_prob: float | None,
    ruta_receptor: str | None = None,
    gnn_d_prob: float | None = None,
) -> SalidaM5Zn | None:
    """Ejecuta M5-Zn si el caso es metálico. `None` si el bloque no aplica.

    `None` significa «esta corrida no es un caso de metal», que es distinto de
    «es un caso de metal y no se pudo puntuar»: lo segundo devuelve una salida
    con su estado y su motivo.

    `gnn_d_prob` se acepta por parámetro y hoy llega siempre `None`: no hay
    productor. Está en la firma para que, el día que lo haya, conectarlo sea
    pasar un argumento y no reescribir esto.
    """
    from services.pipeline.protocols.m5.base import detectar_contexto_metalico

    contexto = detectar_contexto_metalico(
        ruta_pdb=ruta_receptor or _estructura_original(target_pdb_id),
        familia_estructural=target_family,
    )
    if not contexto.es_metalica:
        return None

    ums = ums_autorizado(smiles)
    hay_zinc = "ZN" in contexto.elementos

    perfil = perfil_para(target_pdb_id)
    if perfil is None:
        # §7.2: se ejecuta la auditoría, no se heredan pesos de otra diana.
        return SalidaM5Zn(
            protocol_id=None,
            score=None,
            estado="REVIEW_OUT_OF_VALIDATED_TARGET",
            ums_warhead=ums,
            avisos=contexto.avisos,
        )

    resultado = calcular(
        pdb_id=target_pdb_id,
        smiles=smiles or "",
        vina_kcal_mol=vina_kcal_mol,
        xgb_prob=xgb_prob,
        gnn_d_prob=gnn_d_prob,
        hay_zinc_confirmado=hay_zinc,
        familia_normalizada=target_family,
    )
    return SalidaM5Zn(
        protocol_id=resultado.protocol_id,
        score=resultado.m5_score,
        estado=_estado_persistible(resultado.estado, resultado.componentes_ausentes),
        ums_warhead=ums,
        componentes_ausentes=tuple(resultado.componentes_ausentes),
        avisos=contexto.avisos,
    )


#: Del enum interno al vocabulario del §5 y §7, que es el que viaja al dossier,
#: a la API y al PDF. Se traduce en un solo sitio para que los tres digan lo
#: mismo con las mismas palabras.
_ESTADOS = {
    EstadoM5Zn.VALIDADO: "VALIDATED",
    EstadoM5Zn.FALTA_COMPONENTE: "NOT_EVALUATED_MISSING_COMPONENT",
    EstadoM5Zn.FUERA_DE_ESTRUCTURA: "REVIEW_OUT_OF_VALIDATED_STRUCTURE",
    EstadoM5Zn.FUERA_DE_DIANA: "REVIEW_OUT_OF_VALIDATED_TARGET",
    EstadoM5Zn.SIN_PROTOCOLO: "BLOCKED_PROTOCOL_NOT_AVAILABLE",
    EstadoM5Zn.BENCHMARK_EN_REVISION: "REVIEW_INVALID_BENCHMARK_SITE",
    EstadoM5Zn.PROCEDENCIA_INCOMPLETA: "REVIEW_BENCHMARK_PROVENANCE_INCOMPLETE",
    EstadoM5Zn.TOP1_SIN_COORDINACION: "REVIEW_BENCHMARK_TOP1_NOT_METAL_COORDINATING",
}


def _estado_persistible(estado: Any, ausentes: tuple[str, ...]) -> str:
    """El estado normalizado. Un enum desconocido se declara, no se silencia."""
    if isinstance(estado, EstadoM5Zn):
        traducido = _ESTADOS.get(estado)
        if traducido:
            return traducido
    return f"UNKNOWN_STATE_{estado}"
