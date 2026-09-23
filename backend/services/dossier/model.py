"""
Modelo canónico del dossier.

# Por qué existe este archivo

El PDF, el `manifest.json` y el `README.md` describen la misma corrida. Si cada
uno la interpretara por su cuenta —leyendo el ORM, decidiendo qué es «pasa»,
formateando su propia frase— acabarían discrepando, y una discrepancia entre el
documento legible y el paquete verificable destruye el valor de los dos: el
lector no sabría cuál creer.

Aquí se interpreta la corrida **una vez**. Los tres formatos son proyecciones de
este objeto y no vuelven a mirar el ORM.

# Cuatro cosas que se mantienen separadas

    estado de ejecución    ¿terminó el proceso?          técnico
    disposición científica ¿la evidencia sostiene algo?   del método
    revisión humana        ¿alguien lo miró?             de la persona
    procedencia            ¿sobre qué se calculó?        de los artefactos

Mezclarlas es la forma más común de fabricar autoridad: un `SUCCESS` técnico
presentado como validez científica, o la ausencia de alertas presentada como
revisión. `docs/53 §6.7` lo pide explícitamente y el modelo lo hace imposible
por tipos: son cuatro campos distintos y ninguna función los combina.

# La regla que gobierna el archivo

Ningún `None` se convierte en afirmación. Cuando falta un dato, el campo lleva
un `Estado` de la taxonomía y una razón. No hay valores por defecto optimistas.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from services.blockchain.evidence_summary import build_evidence_summary
from services.dossier.schemas import CaseProjection
from services.targets.calibracion import estado_de_calibracion
from services.dossier.taxonomy import ETIQUETA, GLOSARIO, Estado, estado_de_texto, estado_de_valor

#: Versión del modelo canónico. Viaja al PDF, al manifiesto y al README.
DOSSIER_SCHEMA_VERSION = 1


# ── Piezas ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Campo:
    """
    Un dato con su estado. Es la unidad de todo el dossier.

    `valor` sólo se imprime cuando el estado es afirmativo; en cualquier otro
    caso se imprime la etiqueta y la `razon`. Así un hueco nunca puede pasar por
    contenido, ni siquiera por accidente de formato.
    """

    etiqueta: str
    valor: str | None = None
    estado: Estado = Estado.REGISTRADO
    razon: str | None = None
    #: El valor ES la clasificación, no un dato sujeto a ella.
    #:
    #: Existe por un caso concreto: la siguiente acción justificable. Su valor
    #: («ABSTENCIÓN: COMPLETAR LA CORRIDA») ya expresa el estado, y ocultarlo
    #: por no ser afirmativo dejaba el dossier imprimiendo sólo «REVISAR» —
    #: perdiendo justo la frase que dice qué hacer. Se marca campo a campo y
    #: nunca por defecto: para un DATO, ocultarlo sigue siendo lo correcto.
    valor_es_clasificacion: bool = False

    @property
    def texto(self) -> str:
        """Lo que se imprime. Un solo sitio decide esto para los tres formatos."""
        if self.valor and (self.estado.es_afirmativo or self.valor_es_clasificacion):
            return self.valor
        return ETIQUETA[self.estado]

    def as_dict(self) -> dict[str, Any]:
        visible = self.estado.es_afirmativo or self.valor_es_clasificacion
        return {
            "etiqueta": self.etiqueta,
            "valor": self.valor if visible else None,
            "estado": self.estado.value,
            "razon": self.razon,
            # Sin esta marca, quien lee el JSON no puede distinguir un valor
            # que ES la clasificación —«ABSTENCIÓN: COMPLETAR LA CORRIDA»— de
            # una fuga: un dato que se imprimió pese a estar su campo en un
            # estado de ausencia. Las dos cosas se ven igual desde fuera, y
            # sólo una es correcta.
            "valor_es_clasificacion": self.valor_es_clasificacion,
        }


@dataclass(frozen=True)
class Control:
    """Un control con su protocolo, su estado y por qué está en ese estado."""

    codigo: str
    titulo: str
    estado: Estado
    observacion: str
    protocolo: str | None = None
    procedencia: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "codigo": self.codigo,
            "titulo": self.titulo,
            "estado": self.estado.value,
            "observacion": self.observacion,
            "protocolo": self.protocolo,
            "procedencia": self.procedencia,
        }


@dataclass(frozen=True)
class Pose:
    """Una pose serializada. Sin interpretación: rango, energía y RMSD."""

    rango: int
    afinidad_kcal_mol: float | None
    rmsd_lb: float | None
    rmsd_ub: float | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PoseEvidencia:
    """
    Una pose con su veredicto físico y su papel. Sin combinar nada.

    `fisicamente_valida` es SÓLO `passed`. `review` describe una batería que no
    corrió entera y `not_evaluated` un validador que no corrió: ninguna de las
    dos autoriza la palabra «válida», y el dossier no puede prestarla.

    Los papeles CONVIVEN: la top-1 de Vina puede ser además una alternativa
    físicamente válida, y una pose sugerida puede fallar los controles. Son tres
    booleanos, no una etiqueta única, justamente para que no se colapsen.
    """

    rango: int | None
    afinidad_kcal_mol: float | None
    estado_fisico: Estado
    estado_fisico_codigo: str
    fisicamente_valida: bool
    motor: str | None
    checks_que_fallan: list[str]
    checks_totales: int
    puntuacion_selector: float | None
    es_vina_top1: bool
    es_sugerida: bool
    es_alternativa: bool
    detalle: str | None
    razon: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "rango": self.rango,
            "afinidad_kcal_mol": self.afinidad_kcal_mol,
            "estado_fisico": self.estado_fisico.value,
            "estado_fisico_codigo": self.estado_fisico_codigo,
            "fisicamente_valida": self.fisicamente_valida,
            "motor": self.motor,
            "checks_que_fallan": list(self.checks_que_fallan),
            "checks_totales": self.checks_totales,
            "puntuacion_selector": self.puntuacion_selector,
            "papeles": {
                "vina_top1": self.es_vina_top1,
                "sugerida_por_selector": self.es_sugerida,
                "alternativa_fisicamente_valida": self.es_alternativa,
            },
            "detalle": self.detalle,
            "razon": self.razon,
        }


@dataclass(frozen=True)
class Artefacto:
    """
    Un archivo que el paquete puede llevar. Declarado exista o no.

    Un artefacto ausente se registra igual, con `NO_DISPONIBLE` y su razón: el
    lector tiene que poder distinguir «no se generó» de «se me olvidó incluirlo».
    """

    rol: str
    nombre: str
    media_type: str
    fuente: str
    estado: Estado
    contenido: bytes | None = None
    razon: str | None = None


# ── El dossier ───────────────────────────────────────────────────────


@dataclass
class CaseDossier:
    """Interpretación única de la corrida. Serializable y sin efectos."""

    schema_version: int
    generated_at: str
    case_id: str
    case_name: str
    case_schema_version: int | None
    molecule_id: str
    task_id: str | None
    target_label: str

    portada: list[Campo]
    proposito: list[Campo]
    ejecucion: dict[str, Campo]
    entradas: list[Campo]
    preparacion: list[Campo]
    protocolo: list[Campo]
    generacion: list[Campo]
    seleccion: list[Campo]
    validacion: list[Campo]
    evidencia_poses: list[PoseEvidencia]
    poses: list[Pose]
    poses_estado: Estado
    poses_razon: str | None
    controles: list[Control]
    dimensiones: list[Control]
    supuestos: list[str]
    incertidumbres: list[str]
    decisiones: list[dict[str, Any]]
    siguiente_accion: Campo
    procedencia: dict[str, Any]
    apendice_heredado: list[Campo]
    avisos_integridad: list[str]

    def as_dict(self) -> dict[str, Any]:
        """Forma canónica. Es lo que viaja a `case_snapshot.json` y al README."""
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "case": {
                "case_id": self.case_id,
                "name": self.case_name,
                "case_schema_version": self.case_schema_version,
            },
            "run": {
                "molecule_id": self.molecule_id,
                "task_id": self.task_id,
                "target": self.target_label,
            },
            "portada": [c.as_dict() for c in self.portada],
            "proposito": [c.as_dict() for c in self.proposito],
            "ejecucion": {k: v.as_dict() for k, v in self.ejecucion.items()},
            "entradas": [c.as_dict() for c in self.entradas],
            "preparacion": [c.as_dict() for c in self.preparacion],
            "protocolo": [c.as_dict() for c in self.protocolo],
            "generacion": [c.as_dict() for c in self.generacion],
            "seleccion": [c.as_dict() for c in self.seleccion],
            "validacion_fisica": {
                "campos": [c.as_dict() for c in self.validacion],
                "por_pose": [p.as_dict() for p in self.evidencia_poses],
            },
            "poses": {
                "estado": self.poses_estado.value,
                "razon": self.poses_razon,
                "items": [p.as_dict() for p in self.poses],
            },
            "controles": [c.as_dict() for c in self.controles],
            "dimensiones": [d.as_dict() for d in self.dimensiones],
            "supuestos": self.supuestos,
            "incertidumbres": self.incertidumbres,
            "decisiones": self.decisiones,
            "siguiente_accion": self.siguiente_accion.as_dict(),
            "procedencia": self.procedencia,
            "apendice_heredado": [c.as_dict() for c in self.apendice_heredado],
            "avisos_integridad": self.avisos_integridad,
            "glosario": {e.value: GLOSARIO[e] for e in Estado},
        }

    def json_canonico(self) -> str:
        """JSON estable: claves ordenadas y sin espacios variables."""
        return json.dumps(self.as_dict(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"


# ── Construcción ─────────────────────────────────────────────────────


def _v(obj: Any, campo: str, defecto: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(campo, defecto)
    return getattr(obj, campo, defecto)


def _texto(valor: Any) -> str | None:
    if valor is None:
        return None
    if isinstance(valor, float):
        return f"{valor:.4g}"
    return str(valor)


def _campo_contexto(etiqueta: str, valor: str | None) -> Campo:
    estado = estado_de_texto(valor)
    return Campo(
        etiqueta=etiqueta,
        valor=valor.strip() if valor and valor.strip() else None,
        estado=estado,
        razon=None if estado.es_afirmativo else "El caso no lo declaró.",
    )


def _respaldo_del_receptor(target: Any) -> str:
    """Una línea que un revisor pueda leer sin ambigüedad (SC-9)."""
    estado = estado_de_calibracion(target)
    if estado.spearman_rho is not None:
        return f"{estado.resumen} — ρ = {estado.spearman_rho}"
    return f"{estado.resumen} — {estado.motivo}"


def _campo_dato(etiqueta: str, valor: Any, razon_ausencia: str) -> Campo:
    estado = estado_de_valor(valor)
    return Campo(
        etiqueta=etiqueta,
        valor=_texto(valor) if estado.es_afirmativo else None,
        estado=estado,
        razon=None if estado.es_afirmativo else razon_ausencia,
    )


#: Estado de la etapa de selección -> taxonomía del dossier.
_ESTADO_SELECCION = {
    "selected": Estado.REGISTRADO,
    "abstained": Estado.ABSTENCION,
    "unavailable": Estado.NO_EVALUADO,
    "error": Estado.NO_DISPONIBLE,
}

#: Veredicto físico de una pose -> taxonomía. `review` NO es `PASA`: describe
#: una batería incompleta, y llamarla superada sería el error que la etapa de
#: validación existe para impedir.
_ESTADO_FISICO_POSE = {
    "passed": Estado.PASA,
    "review": Estado.REVISAR,
    "failed": Estado.ABSTENCION,
    "not_evaluated": Estado.NO_EVALUADO,
}

_ESTADO_EVIDENCIA = {
    "available": Estado.REGISTRADO,
    "ready": Estado.REGISTRADO,
    "review": Estado.REVISAR,
    "missing": Estado.NO_DISPONIBLE,
    "not_evaluated": Estado.NO_EVALUADO,
    "incomplete": Estado.NO_DISPONIBLE,
}


def _campos_por_protocolo(eval_result, resumen, target) -> list:
    """Los bloques de M4 y M5-Zn. Ver `services/dossier/bloques_protocolo.py`.

    `Campo`, `_campo_dato` y `_v` se pasan por parametro para que el modulo de
    bloques no tenga que importar de aqui: seria circular.

    `target` viaja porque el PDB de la estructura no esta en el resultado de la
    evaluacion sino en el objetivo, y M5-Zn resuelve su perfil por PDB exacto.
    """
    from services.dossier.bloques_protocolo import campos_de_m4, campos_de_m5_zn

    return [
        *campos_de_m4(Campo, _campo_dato, _v, eval_result, resumen),
        *campos_de_m5_zn(Campo, _campo_dato, _v, eval_result, resumen, target),
    ]


def _campos_de_protocolo_y_abstencion(eval_result, resumen) -> list:
    """Qué se pidió, qué se ejecutó, y de qué se abstuvo la corrida.

    `docs/74_ARQUITECTURA_DISPATCHER_DE_PROTOCOLOS.md` §10 y
    `docs/76_DECISION_TRANSFERENCIA_ESMFOLD_A_LIGANDO_V1.md` §8: el dossier
    tiene que separar observaciones crudas, score derivado, dominio de
    aplicabilidad, componentes ausentes, abstención con su motivo, y el motor
    solicitado frente al ejecutado.

    El caso que obliga a que esto exista con nombre propio es el peptídico.
    Ejecutado ESMFold de verdad el 2026-09-04, la corrida llega a una
    estructura plegada y NO llega a una afinidad: el PDB de ESMFold no trae
    OXT, así que no casa con el grafo del SMILES y el ligando no se puede
    preparar para Vina. Eso no es un fallo que ocultar: es un resultado
    científico válido, y el dossier tiene que poder decirlo sin llamarlo
    «docking peptídico completado».
    """
    protocolo = _v(eval_result, "docking_protocol") or {}
    if not isinstance(protocolo, dict):
        protocolo = {}

    solicitado = protocolo.get("engine_requested") or protocolo.get("requested_engine")
    ejecutado = (
        protocolo.get("engine_executed")
        or protocolo.get("executed_engine")
        or protocolo.get("engine")
    )

    campos = []

    # ── Motor solicitado frente a ejecutado ──────────────────────────
    if solicitado and ejecutado and str(solicitado) != str(ejecutado):
        campos.append(Campo(
            "Motor solicitado frente a ejecutado",
            f"{solicitado} -> {ejecutado}",
            Estado.REVISAR,
            "El motor que corrió no es el que se pidió. La pose no es "
            "comparable con la que habría producido el motor solicitado.",
            # El valor ES la clasificación: sin esto el dossier imprimiría
            # sólo «REVISAR» y perdería QUÉ se sustituyó por qué, que es toda
            # la información del campo.
            valor_es_clasificacion=True,
        ))
    elif ejecutado:
        campos.append(_campo_dato(
            "Motor ejecutado", str(ejecutado),
            "La corrida no registró qué motor se ejecutó.",
        ))

    # ── Abstención en la frontera estructura -> ligando ──────────────
    #
    # Se detecta por lo que de verdad hay: hubo estructura y no hubo afinidad.
    # No se lee de una bandera que alguien tenga que acordarse de poner.
    afinidad = resumen.get("top_pose_affinity")
    es_peptidico = bool(
        ejecutado and any(m in str(ejecutado).lower() for m in ("esmfold", "colabfold"))
    )
    if es_peptidico and afinidad is None:
        campos.append(Campo(
            "Estado del acoplamiento",
            "Estructura peptídica generada; docking no evaluado",
            Estado.NO_EVALUADO,
            "El modelo de plegamiento produjo una estructura, y la conversión de "
            "esa estructura a un ligando acoplable no se completó, así que Vina "
            "no llegó a ejecutarse y NO hay afinidad. No se sustituye por un "
            "valor derivado de la confianza del plegado: la confianza describe "
            "la estructura, no la unión. Ver "
            "docs/76_DECISION_TRANSFERENCIA_ESMFOLD_A_LIGANDO_V1.md.",
            # La frase ES el estado. Ocultarla dejaría «NO EVALUADO» a secas,
            # que no distingue «no se pudo acoplar» de «no se intentó».
            valor_es_clasificacion=True,
        ))
    elif afinidad is None:
        campos.append(_campo_dato(
            "Estado del acoplamiento", None,
            "La corrida no produjo afinidad y no declara el motivo.",
        ))

    # La transferencia ESMFold→ligando se presenta sólo si fue persistida;
    # nunca se reconstruye desde el PDB ni desde la etiqueta del motor.
    ligand_state = _v(eval_result, "ligand_state") or {}

    # ── A qué pH se protonó, y qué especie salió de ahí ────────────────────
    #
    # `ligand_state` se persistía entero y el dossier sólo leía de él la
    # transferencia de péptidos. Mientras el pH estuvo escrito a mano en 7.4
    # eso era una omisión tolerable: siempre era el mismo. Desde que el usuario
    # puede elegirlo en las opciones avanzadas deja de serlo — dos corridas de
    # la misma molécula pueden haber acoplado especies distintas, y sin esto el
    # expediente no permite distinguirlas.
    protonacion = ligand_state.get("protonacion") if isinstance(ligand_state, dict) else None
    if isinstance(protonacion, dict) and protonacion.get("aplicada"):
        ph_usado = protonacion.get("ph")
        ph_pedido = protonacion.get("ph_solicitado")
        aviso_ph = protonacion.get("aviso_de_ph")

        # Lo que se EJECUTÓ, y —si no coincide— lo que se pidió. Un expediente
        # que dijera el pH solicitado cuando corrió otro sería peor que uno que
        # no lo dijera: parecería verificado.
        texto_ph = None if ph_usado is None else f"{ph_usado:g}"
        if texto_ph is not None and aviso_ph and ph_pedido is not None:
            texto_ph = f"{ph_usado:g} (se pidió {ph_pedido:g}; fuera del rango admitido)"
        campos.append(_campo_dato(
            "pH de protonación del ligando",
            texto_ph,
            "La corrida no registró a qué pH se protonó el ligando.",
        ))

        seleccion = protonacion.get("seleccion")
        if isinstance(seleccion, dict):
            empatados = seleccion.get("empatados")
            alternativas = protonacion.get("alternativas")
            descripcion = None
            if ph_usado is not None:
                descripcion = (
                    f"Microestado más próximo al predicho a pH {ph_usado:g}"
                    + (f", de {alternativas} enumerados" if isinstance(alternativas, int) else "")
                    # Un empate lo rompe el orden alfabético del SMILES, no la
                    # química. Se dice, porque cambia cuánto vale la elección.
                    + (
                        f"; {empatados} empataron y el desempate fue alfabético"
                        if isinstance(empatados, int) and empatados > 1 else ""
                    )
                )
            campos.append(_campo_dato(
                "Especie acoplada",
                descripcion,
                "La corrida no registró con qué criterio se eligió el microestado.",
            ))

    # ── Qué tautómero se acopló, y cuántos quedaron sin descartar ──────────
    #
    # FEP-ready, paso 1. Hasta 2026-09-23 sólo se contaban las alternativas y
    # el expediente no decía nada. Tres estados (`chem/declaracion_tautomeros.py`):
    # uno solo, varios sin descartar (el acoplado es el canónico de RDKit, que
    # no predice poblaciones) o no resuelto. Las corridas anteriores no traen la
    # declaración y no enseñan este campo: no se reconstruye a posteriori.
    tautomeria = ligand_state.get("tautomeria") if isinstance(ligand_state, dict) else None
    declaracion = tautomeria.get("declaracion") if isinstance(tautomeria, dict) else None
    if isinstance(declaracion, dict) and declaracion.get("estado"):
        from chem.declaracion_tautomeros import MULTIESTADO_REQUERIDO, RESUELTO_UNICO, resumen_para_humanos

        texto = resumen_para_humanos(declaracion)
        if declaracion["estado"] == RESUELTO_UNICO:
            campos.append(Campo("Tautómero del ligando", texto, Estado.REGISTRADO, None))
        elif declaracion["estado"] == MULTIESTADO_REQUERIDO:
            campos.append(Campo("Tautómero del ligando", None, Estado.REVISAR, texto))
        else:
            campos.append(Campo("Tautómero del ligando", None, Estado.ABSTENCION, texto))

    transfer = ligand_state.get("peptide_transfer") if isinstance(ligand_state, dict) else None
    if isinstance(transfer, dict):
        transfer_status = transfer.get("status")
        if transfer_status == "completed":
            campos.extend([
                _campo_dato("Transferencia química ESMFold → ligando", "COMPLETADA", "La conectividad procede del SMILES y las coordenadas proceden de ESMFold."),
                _campo_dato("Átomos transferidos / completados", f"{transfer.get('coordinates_transferred', 0)} / {transfer.get('coordinates_completed', 0)}", "El manifiesto no registró el recuento de coordenadas."),
                _campo_dato("Método de completado geométrico", transfer.get("completion_method"), "La transferencia no registró cómo completó los átomos ausentes."),
                _campo_dato("Versión del mapeo", transfer.get("mapping_version"), "La transferencia no registró su versión de mapeo."),
            ])
        else:
            campos.append(Campo(
                "Transferencia química ESMFold → ligando",
                f"ABSTENCIÓN · {transfer.get('failure_code') or 'motivo no registrado'}",
                Estado.NO_EVALUADO,
                transfer.get("failure_message") or "La transferencia no se completó; no se generó un ligando acoplable.",
                valor_es_clasificacion=True,
            ))

    return campos


def _campo_de_estado_quimico(eval_result: Any) -> Campo:
    """Preparación: qué parte de la química del ligando quedó registrada.

    Hasta 2026-09-23 decía siempre que el pipeline no registraba ni la forma
    protonada ni el tautómero. Era cierto para las corridas viejas y dejó de
    serlo para las nuevas: una corrida que trae la declaración de tautómeros
    (y con ella el microestado) dice lo que falta de verdad, la estereoquímica.
    """
    ligand_state = _v(eval_result, "ligand_state") or {}
    tautomeria = ligand_state.get("tautomeria") if isinstance(ligand_state, dict) else None
    if isinstance(tautomeria, dict) and isinstance(tautomeria.get("declaracion"), dict):
        return Campo(
            "Estereoquímica del ligando",
            None,
            Estado.NO_EVALUADO,
            "La corrida registra el pH, el microestado y el tautómero (ver el protocolo); "
            "la estereoquímica no se evalúa todavía.",
        )
    return Campo(
        "Protonación, tautomería y estereoquímica",
        None,
        Estado.NO_EVALUADO,
        "El pipeline no registra la forma protonada ni el tautómero elegidos.",
    )


def _campos_de_eficiencia(eval_result, resumen) -> list:
    """Eficiencia por átomo, con la fórmula y la referencia dentro del campo.

    Un número como «FQ 0.82» en un dossier no dice en qué unidades está, contra
    qué se normalizó, ni que la afinidad de partida es un proxy. Aquí van los
    tres, porque el dossier tiene que poder leerse sin el código al lado.

    Se calculan sobre `affinity_kcal`, que desde el 2026-09-04 es el score de
    Vina sin transformar —antes lo pisaba la regresión de XGBoost, ver
    `db/repository.py`—. Ninguna de estas métricas entra en `total_score`.
    """
    from scoring.eficiencia import calcular

    afinidad = resumen.get("top_pose_affinity")
    atomos = _v(eval_result, "heavy_atom_count")
    metricas = calcular(afinidad, atomos or 0) if afinidad is not None else None

    if metricas is None:
        return [
            _campo_dato(
                "Eficiencia por átomo pesado",
                None,
                "Sin afinidad o sin recuento de átomos: no se calcula.",
            )
        ]

    sujetado = ""
    if metricas.escala_sujetada:
        sujetado = (
            f" La escala se sujetó a HA={metricas.ha_para_la_escala}: el ajuste "
            "de Reynolds cubre 15-50 átomos pesados y esta molécula queda "
            "fuera, así que el valor es un límite, no una interpolación."
        )

    return [
        _campo_dato(
            "Eficiencia de ligando (LE)",
            f"{metricas.ligand_efficiency_vina:.3f} kcal/mol por átomo pesado "
            f"({metricas.heavy_atoms} átomos). Hopkins et al. 2004. Depende del "
            "tamaño por construcción: medido sobre la cohorte de este proyecto "
            "(17 431 moléculas), su correlación con el número de átomos es tan "
            "fuerte como la del score crudo, con el signo cambiado.",
            "No calculable.",
        ),
        _campo_dato(
            "SILE",
            f"{metricas.sile_vina:.3f} = |afinidad| / HA^0.3. Nissink, J. Chem. "
            "Inf. Model. 49 (2009) 1617. El artículo no publica un umbral, así "
            "que aquí no hay ninguno.",
            "No calculable.",
        ),
        _campo_dato(
            "Fit Quality (proxy sobre Vina)",
            f"{metricas.fq_vina_proxy:.3f} = LE / LE_scale(HA), con "
            "LE_scale = 0.0715 + 7.5328/HA + 25.7079/HA² − 361.4722/HA³ "
            "(Reynolds, Tounge, Bembenek, J. Med. Chem. 51 (2008) 2432, ec. 1-2). "
            f"LE_scale usada: {metricas.le_scale_pki:.4f} en unidades de pKi. "
            "PROXY: la escala está ajustada contra Ki experimental, no contra "
            f"scores de acoplamiento; la conversión usa {1.37} kcal/mol por "
            "unidad logarítmica. FQ ≈ 1 significa proximidad a la envolvente "
            "eficiente del conjunto de Reynolds para ese tamaño — no es "
            f"probabilidad de unión ni calidad de pose.{sujetado}",
            "No calculable.",
        ),
    ]


def _campo_conformaciones(eval_result: Any) -> Campo:
    """
    El protocolo de generación 3D que la corrida ejecutó de verdad.

    Antes esto decía siempre «no evaluado» porque el resultado no persistía el
    parámetro. Ahora se sella con la corrida, así que el dossier puede declarar
    QUÉ generador produjo las conformaciones que se acoplaron.

    Se dicen las dos cifras: pedidas y conseguidas. Un ensemble de 30 que sólo
    embebió 22 tiene menos cobertura de la solicitada, y contar sólo lo
    conseguido escondería esa diferencia — que es justo la que dice si el
    ensemble hizo lo que se le pidió.
    """
    protocolo = _v(eval_result, "docking_protocol")
    if not isinstance(protocolo, dict) or not protocolo:
        return Campo(
            "Generación conformacional",
            None,
            Estado.NO_EVALUADO,
            "Esta corrida es anterior al sellado del protocolo de generación 3D. No se "
            "sustituye por la configuración del caso: sería atribuirle un ajuste que "
            "nadie guardó con ella.",
        )

    pedidas = protocolo.get("conformers_requested")
    conseguidas = protocolo.get("conformers_generated")
    if not isinstance(pedidas, int) or not isinstance(conseguidas, int):
        return Campo(
            "Generación conformacional", None, Estado.NO_EVALUADO,
            "El protocolo sellado no declara el número de conformaciones.",
        )

    if pedidas <= 1:
        return Campo(
            "Generación conformacional",
            "Confórmero único (ETKDG + MMFF94)",
            Estado.REGISTRADO,
            None,
        )

    completo = conseguidas >= pedidas

    # ── DE CUÁNTAS CANDIDATAS SALIÓ LA AFINIDAD ────────────────────────────
    #
    # El ensemble acopla cada conformación por separado y junta las
    # `conformaciones × num_poses` poses en UNA piscina ordenada por afinidad.
    # La que se entrega es, por tanto, la mejor de esa piscina.
    #
    # Sin decir el tamaño de la piscina, dos dossiers de la misma molécula —uno
    # con confórmero único y otro con ensemble— presentan su afinidad igual,
    # aunque una sea la mejor de 9 candidatas y la otra la mejor de 144. Eso no
    # es una advertencia sobre el método: es el denominador, y quien compare dos
    # expedientes lo necesita para saber que está comparando.
    num_poses = protocolo.get("num_poses")
    piscina = (
        f" · pose elegida entre {conseguidas * num_poses} candidatas"
        if isinstance(num_poses, int) and num_poses > 0 and conseguidas > 0
        else ""
    )

    return Campo(
        "Generación conformacional",
        f"Ensemble · {conseguidas} de {pedidas} conformaciones{piscina}",
        Estado.REGISTRADO if completo else Estado.REVISAR,
        None if completo else (
            f"Se pidieron {pedidas} conformaciones y se generaron {conseguidas}: la "
            f"cobertura geométrica es menor que la solicitada. El ensemble amplía "
            f"cobertura; no mejora, por sí solo, la elección de la pose top-1."
        ),
        # El valor ES el hecho, no un dato sujeto a clasificación. Sin esto, un
        # ensemble incompleto imprimía «REVISAR» y perdía «22 de 30» — que es
        # justo la cifra por la que hay que revisar.
        valor_es_clasificacion=True,
    )


def build_case_dossier(
    *,
    projection: CaseProjection,
    molecule: Any,
    eval_result: Any,
    target: Any,
    artefactos: list[Artefacto] | None = None,
    generated_at: datetime | None = None,
) -> CaseDossier:
    """
    Interpreta la corrida UNA vez.

    `generated_at` es inyectable para que el paquete pueda ser determinista bajo
    reloj congelado; sin eso, dos ZIP de la misma corrida diferirían sólo por la
    hora y el verificador no serviría para comparar.
    """
    ahora = (generated_at or datetime.now(timezone.utc)).replace(microsecond=0)
    generado = ahora.isoformat()

    resumen = build_evidence_summary(eval_result, target, molecule)
    ctx = projection.context
    inputs = projection.inputs
    avisos: list[str] = []

    calibracion = estado_de_calibracion(target)

    # ── Identidad ────────────────────────────────────────────────────
    molecule_id = str(_v(molecule, "id", "") or "")
    target_label = " · ".join(
        p for p in (_texto(_v(target, "pdb_id")), _texto(_v(target, "name"))) if p
    ) or "Receptor no informado"
    task_declarado = projection.run.task_id if projection.run else None
    task_registrado = _v(eval_result, "celery_task_id") or _v(eval_result, "task_id")

    portada = [
        Campo("Caso", projection.name),
        _campo_dato("Molécula", molecule_id, "El backend no resolvió la molécula."),
        Campo("Receptor", target_label),
        # SC-9: el dossier es el documento que sale del producto y el que un
        # revisor lee. Si no dice qué respaldo tenía el receptor, invita
        # exactamente a la lectura que el catálogo no puede sostener.
        Campo("Respaldo del receptor", _respaldo_del_receptor(target)),
        _campo_dato("Corrida", task_declarado, "El caso no registró identificador de corrida."),
        _campo_dato(
            "Fecha de la corrida",
            _texto(_v(eval_result, "evaluated_at")),
            "La corrida no serializó su fecha.",
        ),
        Campo("Esquema del dossier", f"v{DOSSIER_SCHEMA_VERSION}"),
    ]

    # ── Propósito ────────────────────────────────────────────────────
    proposito = [
        _campo_contexto("Tipo de estudio", ctx.study_kind),
        _campo_contexto("¿Qué intenta responder este caso?", ctx.question),
        _campo_contexto("¿Qué decisión se pretende tomar?", ctx.decision),
        _campo_contexto("¿Qué justifica la elección del sistema?", ctx.system_rationale),
        _campo_contexto("¿Qué controles o referencias existen?", ctx.controls),
    ]

    # ── Ejecución: tres estados que NO se mezclan ────────────────────
    estado_tecnico = projection.run.execution_state if projection.run else None
    disposicion = _ESTADO_EVIDENCIA.get(resumen["status"], Estado.REVISAR)
    final_disposition = projection.disposition
    revision_humana = (
        Estado.REGISTRADO if final_disposition or projection.decisions else Estado.NO_EVALUADO
    )
    final_label = {
        "accept": "Aceptar evidencia",
        "limit": "Aceptar con límites",
        "abstain": "Abstenerse",
    }
    ejecucion = {
        "tecnico": _campo_dato(
            "Estado de ejecución (técnico)",
            estado_tecnico,
            "El caso no registró el estado de la corrida.",
        ),
        "cientifico": Campo(
            "Disposición científica de la evidencia",
            resumen["label"],
            disposicion,
            resumen["summary"],
        ),
        "humano": Campo(
            "Revisión humana",
            (
                f"{final_label[final_disposition.kind]} · {final_disposition.rationale}"
                if final_disposition
                else f"{len(projection.decisions)} control(es) reconocido(s)"
                if projection.decisions
                else None
            ),
            revision_humana,
            None if final_disposition or projection.decisions else "Nadie ha revisado ni reconocido controles de esta corrida.",
        ),
        "disposicion_final": Campo(
            "Disposición final del caso",
            (
                f"{final_label[final_disposition.kind]} · {final_disposition.rationale}"
                if final_disposition else None
            ),
            Estado.REGISTRADO if final_disposition else Estado.NO_EVALUADO,
            None if final_disposition else "El caso aún no tiene una disposición científica final.",
        ),
    }

    # ── Entradas y procedencia ───────────────────────────────────────
    receptor = inputs.receptor
    ligando = inputs.ligand
    config = inputs.config
    preflight = projection.preflight

    entradas = [
        _campo_dato(
            "Receptor declarado",
            f"{receptor.pdb_id}" + (f" · cadena {receptor.chain}" if receptor and receptor.chain else "")
            if receptor else None,
            "El caso no declaró receptor.",
        ),
        _campo_dato(
            "Origen del receptor",
            receptor.origin if receptor else None,
            "El caso no declaró el origen del receptor.",
        ),
        _campo_dato(
            "Ligando introducido",
            ligando.input_smiles if ligando else None,
            "El caso no declaró ligando.",
        ),
        _campo_dato(
            "Ligando canónico (el que se acopla)",
            (ligando.canonical_smiles if ligando else None) or _v(molecule, "smiles"),
            "No se registró la forma canónica del ligando.",
        ),
        _campo_dato(
            "Caja efectiva",
            (f"centro {tuple(config.grid_center)} · tamaño {tuple(config.grid_size)} Å"
             if config and config.grid_center and config.grid_size else None),
            "La configuración efectiva no quedó registrada en el caso.",
        ),
        _campo_dato(
            "Residuos de referencia",
            ", ".join(config.custom_hotspots) if config and config.custom_hotspots else None,
            "No se seleccionaron residuos de referencia.",
        ),
        _campo_dato(
            "Huella de los inputs (preflight)",
            preflight.fingerprint if preflight else None,
            "La corrida no quedó atada a una comprobación previa.",
        ),
    ]

    # ── Correspondencia corrida ↔ inputs, comprobada aquí ────────────
    relacion = projection.run_inputs_relation
    huella_corrida = projection.run.input_fingerprint if projection.run else None
    huella_preflight = preflight.fingerprint if preflight else None
    if final_disposition:
        expected_fingerprint = huella_corrida or huella_preflight
        if not expected_fingerprint or final_disposition.fingerprint != expected_fingerprint:
            avisos.append(
                "La disposición final no está vinculada a la huella de la corrida documentada. "
                "Se conserva como declaración, pero no se considera aplicable a esta evidencia."
            )
            ejecucion["disposicion_final"] = Campo(
                "Disposición final del caso",
                f"{final_label[final_disposition.kind]} · {final_disposition.rationale}",
                Estado.REVISAR,
                "La huella de la disposición no coincide con la huella de la corrida.",
            )
    if huella_corrida and huella_preflight:
        comprobada = "corresponde" if huella_corrida == huella_preflight else "corrida_anterior"
        if comprobada != relacion:
            avisos.append(
                "El cliente declaró la relación corrida/inputs como "
                f"«{relacion}», pero las huellas dicen «{comprobada}». Manda lo comprobable."
            )
        relacion = comprobada

    relacion_estado = {
        "corresponde": Estado.REGISTRADO,
        "corrida_anterior": Estado.REVISAR,
        "desconocida": Estado.NO_EVALUADO,
    }[relacion]
    relacion_texto = {
        "corresponde": "La corrida se ejecutó con los inputs que este dossier describe.",
        "corrida_anterior": (
            "Los inputs del caso CAMBIARON después de esta corrida. El dossier describe la "
            "corrida, no la hipótesis actual."
        ),
        "desconocida": (
            "La corrida no registró la huella de sus inputs; no se puede afirmar a qué "
            "hipótesis corresponde."
        ),
    }[relacion]
    entradas.append(
        Campo("Relación de la corrida con los inputs actuales",
              relacion_texto if relacion_estado.es_afirmativo else None,
              relacion_estado, relacion_texto)
    )

    # ── Discordancia de task_id ──────────────────────────────────────
    if task_declarado and task_registrado and str(task_registrado) != str(task_declarado):
        avisos.append(
            f"El caso pide la corrida «{task_declarado}» y el resultado almacenado pertenece a "
            f"«{task_registrado}». El paquete no puede afirmar que describan lo mismo."
        )

    # ── Preparación: sólo lo REGISTRADO ──────────────────────────────
    preparacion = [
        _campo_dato(
            "Política de heteroátomos declarada",
            preflight.execution_route if preflight else None,
            "La corrida no declaró la ruta de preparación aplicada.",
        ),
        Campo(
            "Aguas, metales y cofactores",
            None,
            Estado.NO_EVALUADO,
            "Esta corrida no serializó un diff fuente→preparado. La comprobación previa lo "
            "calcula, pero no queda archivado con el resultado.",
        ),
        _campo_de_estado_quimico(eval_result),
    ]
    if preflight and preflight.blockers:
        preparacion.append(
            Campo("Bloqueantes declarados en la comprobación previa",
                  ", ".join(preflight.blockers), Estado.ABSTENCION,
                  "La comprobación previa registró bloqueantes técnicos.")
        )
    if preflight and preflight.warnings:
        preparacion.append(
            Campo("Advertencias de la comprobación previa",
                  ", ".join(preflight.warnings), Estado.REVISAR,
                  "Advertencias científicas registradas antes de ejecutar.")
        )
    # DOC 71, DEFECTO A8. El caso guarda TRES listas del preflight —bloqueantes,
    # advertencias y controles no evaluados— y el dossier sólo pintaba las dos
    # primeras. El resultado es el que describió el informe de la VM: la interfaz
    # mostraba «dos advertencias y tres controles sin evaluar» y el documento
    # hablaba únicamente de las advertencias.
    #
    # Un control que NO SE EVALUÓ no es un control que pasó, y omitirlo lo
    # convierte en lo segundo por defecto. Es la misma distinción que este
    # producto sostiene en la validez física de poses: `not_evaluated` nunca se
    # mezcla con `passed`.
    if preflight and preflight.not_evaluated:
        preparacion.append(
            Campo("Controles sin evaluar en la comprobación previa",
                  ", ".join(preflight.not_evaluated), Estado.ABSTENCION,
                  "El preflight no pudo ejecutar estos controles. No se evaluaron: "
                  "eso no equivale a que los pasaran.")
        )

    # ── Protocolo y entorno ──────────────────────────────────────────
    repro = resumen["reproducibility"]
    modelo = resumen["model_context"]
    protocolo = [
        _campo_dato("Motor de acoplamiento", modelo.get("engine"), "La corrida no registró el motor."),
        _campo_dato("Versión del motor", repro.get("vina_version"), "La corrida no registró la versión."),
        _campo_dato("Semilla aleatoria", repro.get("random_seed"), "La corrida no registró la semilla."),
        _campo_dato("Origen del parseo", repro.get("parsing_source"), "La corrida no registró el parser."),
        _campo_dato("Modelo de rescoring", modelo.get("model"), "La corrida no registró el modelo."),
        _campo_dato(
            "Configuración PRO declarada",
            json.dumps(config.pipeline_config, ensure_ascii=False, sort_keys=True) if config and config.pipeline_config else None,
            "La corrida no registró opciones PRO avanzadas.",
        ),
        _campo_dato(
            "Exhaustiveness",
            config.exhaustiveness if config else None,
            "La corrida no registró la exhaustividad utilizada.",
        ),
        _campo_dato(
            "Poses solicitadas",
            config.num_poses if config else None,
            "La corrida no registró el número de poses solicitado.",
        ),
        _campo_dato(
            "Motivo de fallback",
            modelo.get("fallback_reason"),
            "No se registró ningún fallback.",
        ),
        _campo_dato(
            "Error declarado",
            _v(eval_result, "error_message"),
            "La corrida no registró errores.",
        ),
    ]

    # ── Poses ────────────────────────────────────────────────────────
    poses_crudas = _v(eval_result, "docking_poses") or []
    poses: list[Pose] = []
    for indice, p in enumerate(poses_crudas, start=1):
        afinidad = _v(p, "affinity")
        poses.append(
            Pose(
                rango=int(_v(p, "rank", indice) or indice),
                afinidad_kcal_mol=float(afinidad) if isinstance(afinidad, (int, float)) else None,
                rmsd_lb=_v(p, "rmsd_lb"),
                rmsd_ub=_v(p, "rmsd_ub"),
            )
        )
    poses.sort(key=lambda x: (x.afinidad_kcal_mol if x.afinidad_kcal_mol is not None else 0.0, x.rango))
    if poses:
        poses_estado, poses_razon = Estado.REGISTRADO, None
    else:
        poses_estado = Estado.NO_DISPONIBLE
        poses_razon = "La corrida no serializó poses; no hay evidencia estructural que revisar."

    # ── Generación de poses ──────────────────────────────────────────
    # Protocolo, semilla y cobertura de lo que la corrida REALMENTE produjo.
    # Conformeros y restarts NO se persisten con el resultado: se declaran
    # ausentes en vez de tomarlos de la configuración del caso, que pertenece a
    # otro objeto y podría no ser la que se ejecutó.
    validez = resumen["physical_validity"]
    seleccion_res = resumen["pose_selection"]
    generacion = [
        _campo_dato("Poses producidas", len(poses) or None,
                    "La corrida no serializó poses."),
        _campo_dato("Poses solicitadas al motor",
                    config.num_poses if config else None,
                    "La corrida no registró el número de poses solicitado."),
        _campo_dato("Exhaustividad", config.exhaustiveness if config else None,
                    "La corrida no registró la exhaustividad utilizada."),
        _campo_dato("Semilla aleatoria", repro.get("random_seed"),
                    "La corrida no registró la semilla: no es repetible bit a bit."),
        _campo_dato("Motor y versión",
                    " · ".join(x for x in (modelo.get("engine"), repro.get("vina_version")) if x) or None,
                    "La corrida no registró el motor ni su versión."),
        _campo_conformaciones(eval_result),
        _campo_dato(
            "Mejor afinidad Vina observada",
            (f"{resumen['top_pose_affinity']:.2f} kcal/mol"
             if resumen.get("top_pose_affinity") is not None else None),
            "La corrida no serializó afinidad.",
        ),
        _campo_dato(
            "Cobertura de validación física",
            (f"{validez['poses_evaluated']}/{validez['poses_produced']} poses con veredicto"
             if validez.get("poses_produced") else None),
            "Ninguna pose recibió veredicto físico.",
        ),
        # Los bloques por PROTOCOLO viven en `bloques_protocolo.py`: es la
        # dimension que el dispatcher va a hacer crecer (M5-Fe, macrociclos,
        # covalentes), y mezclarla aqui repetiria lo que el doc 74 deshace.
        *_campos_por_protocolo(eval_result, resumen, target),
        *_campos_de_protocolo_y_abstencion(eval_result, resumen),
        *_campos_de_eficiencia(eval_result, resumen),
    ]

    # ── Selección de pose ────────────────────────────────────────────
    # Vina top-1 se declara SIEMPRE. La recomendación viaja al lado con su
    # margen, su modelo y su SHA-256; cuando no hay recomendación, la referencia
    # se etiqueta FALLBACK, no como un acierto del selector.
    seleccion = [
        Campo(
            "Estado de la etapa de selección",
            seleccion_res["label"],
            _ESTADO_SELECCION[seleccion_res["status"]],
            {
                "selected": "El selector emitió una recomendación.",
                "abstained": "El margen no llegó al umbral: el selector NO recomienda.",
                "unavailable": "El selector no se ejecutó en esta corrida.",
                "error": "El selector falló; no hay recomendación que leer.",
            }[seleccion_res["status"]],
            valor_es_clasificacion=True,
        ),
        _campo_dato("Pose principal del producto (Vina top-1)",
                    (f"#{seleccion_res['vina_top1_rank']}"
                     if seleccion_res["vina_top1_rank"] is not None else None),
                    "La corrida no permitió identificar la top-1 de Vina."),
        _campo_dato("Pose recomendada por el selector",
                    (f"#{seleccion_res['suggested_pose_rank']}"
                     if seleccion_res["suggested_pose_rank"] is not None else None),
                    "El selector no recomendó ninguna pose."),
        _campo_dato("Pose que habría recomendado (abstención)",
                    (f"#{seleccion_res['would_have_suggested_rank']}"
                     if seleccion_res["would_have_suggested_rank"] is not None else None),
                    "No aplica: la etapa no se abstuvo con una candidata medida."),
        _campo_dato(
            "Margen de confianza y umbral",
            (f"{seleccion_res['confidence']:.6f} (umbral {seleccion_res['abstention_threshold']})"
             if seleccion_res["confidence"] is not None else None),
            "El selector no dejó margen medido.",
        ),
        Campo(
            "Referencia declarada",
            ("Vina top-1 como FALLBACK: no es un acierto del selector"
             if seleccion_res["is_fallback"]
             else "Recomendación del selector, junto a Vina top-1"),
            Estado.REVISAR if seleccion_res["is_fallback"] else Estado.REGISTRADO,
            "Cuando no hay recomendación, la referencia es Vina top-1 por defecto.",
            valor_es_clasificacion=True,
        ),
        _campo_dato("Razón de abstención", seleccion_res["abstention_reason"],
                    "La etapa no registró razón de abstención."),
        _campo_dato("Modelo del selector",
                    seleccion_res["model_name"] or seleccion_res["model_version"],
                    "No se registró el modelo del selector."),
        _campo_dato("SHA-256 del modelo", seleccion_res["model_sha256"],
                    "No se selló el modelo del selector."),
        _campo_dato("SHA-256 de la metadata del modelo", seleccion_res["meta_sha256"],
                    "No se selló la metadata del selector."),
    ]
    if seleccion_res["diverges_from_vina_top1"]:
        seleccion.append(Campo(
            "Discordancia entre la sugerida y Vina top-1",
            (f"La sugerida (#{seleccion_res['suggested_pose_rank']}) NO es la top-1 de Vina "
             f"(#{seleccion_res['vina_top1_rank']})"),
            Estado.REVISAR,
            "Ambas se conservan y ambas se declaran. La pose principal del producto sigue "
            "siendo la de Vina; la del selector es una recomendación.",
            valor_es_clasificacion=True,
        ))
    if seleccion_res["physically_valid_alternatives"]:
        seleccion.append(Campo(
            "Alternativas físicamente válidas",
            ", ".join(f"#{r}" for r in seleccion_res["physically_valid_alternatives"]),
            Estado.REGISTRADO,
            "Se listan para comparar. NINGUNA se selecciona automáticamente.",
        ))

    # ── Validación geométrica/física ─────────────────────────────────
    validacion = [
        Campo(
            "Veredicto de la etapa",
            validez["label"],
            _ESTADO_FISICO_POSE.get(validez["status"], Estado.NO_EVALUADO),
            validez["detail"],
            valor_es_clasificacion=True,
        ),
        _campo_dato("Motor de validación", validez.get("engine"),
                    "La etapa no declaró motor de validación."),
        _campo_dato(
            "Cobertura",
            (f"{validez['poses_evaluated']} de {validez['poses_produced']} poses"
             if validez.get("poses_produced") else None),
            "Ninguna pose recibió veredicto.",
        ),
        _campo_dato("Código de razón", validez.get("reason_code"),
                    "La etapa no registró código de razón."),
        _campo_dato(
            "Estado físico de la pose recomendada",
            seleccion_res["suggested_pose_physical_status"],
            "No hay pose recomendada, o su estado físico no se midió.",
        ),
        # Doc 71, C2. Cuando el selector se abstiene el contrato SÍ trae un
        # estado físico, pero es el de la candidata que descartó. Decirlo con su
        # nombre conserva el dato sin atribuírselo a una recomendación que no
        # existe; callarlo perdería información útil —que la descartada pasaba
        # los controles— y llamarlo «de la pose recomendada» era la contradicción.
        _campo_dato(
            "Estado físico de la pose que habría recomendado",
            seleccion_res.get("would_have_suggested_physical_status"),
            "No aplica: el selector no se abstuvo con una candidata medida.",
        ),
    ]
    if seleccion_res["suggested_pose_rank"] is not None and (
        seleccion_res["suggested_pose_physical_status"] != "passed"
    ):
        validacion.append(Campo(
            "Sustitución automática",
            "NO SE SUSTITUYE. Se declara revisión",
            Estado.REVISAR,
            "La pose recomendada no está confirmada como físicamente válida. No se elige otra "
            "en su lugar: escoger la siguiente que pase sería una decisión que nadie tomó y "
            "para la que el modelo no fue entrenado.",
            valor_es_clasificacion=True,
        ))

    evidencia_poses = [
        PoseEvidencia(
            rango=item["rank"],
            afinidad_kcal_mol=item["observed_vina_affinity_kcal_mol"],
            estado_fisico=_ESTADO_FISICO_POSE.get(item["physical_status"], Estado.NO_EVALUADO),
            estado_fisico_codigo=item["physical_status"],
            fisicamente_valida=item["physically_valid"],
            motor=item["engine"],
            checks_que_fallan=item["failing_checks"],
            checks_totales=item["checks_total"],
            puntuacion_selector=item["selector_score"],
            es_vina_top1=item["is_vina_top1"],
            es_sugerida=item["is_suggested"],
            es_alternativa=item["is_alternative"],
            detalle=item["detail"],
            razon=item["reason_code"],
        )
        for item in resumen["pose_evidence"]
    ]

    # ── Controles físicos ────────────────────────────────────────────
    estado_fisico = _ESTADO_FISICO_POSE.get(validez["status"], Estado.NO_EVALUADO)
    controles = [
        Control(
            codigo="VALIDEZ_FISICA_POSES",
            titulo="Validez física y geométrica de las poses",
            estado=estado_fisico,
            observacion=validez["detail"],
            protocolo=(
                "Reconstrucción de la pose desde PDBQT con plantilla del SMILES y validación "
                "geométrica. La representación con la que se valida NO es la del cristal: los "
                "hidrógenos se añaden en la reconstrucción."
            ),
            procedencia="eval_result.structural_evidence",
        ),
        Control(
            codigo="SEPARACION_ENTRE_POSES",
            titulo="Separación energética entre poses",
            estado=_ESTADO_EVIDENCIA.get(
                next((d["status"] for d in resumen["dimensions"] if d["id"] == "sampling"), "missing"),
                Estado.REVISAR,
            ),
            observacion=next(
                (d["detail"] for d in resumen["dimensions"] if d["id"] == "sampling"),
                "No se pudo describir la separación entre poses.",
            ),
            protocolo="Diferencia de afinidad entre la pose 1 y la 2, y recuento a ≤1 kcal/mol.",
            procedencia="eval_result.docking_poses",
        ),
        Control(
            codigo="TRAZA_REPRODUCIBILIDAD",
            titulo="Traza de reproducibilidad técnica",
            estado=Estado.REGISTRADO if repro["available_count"] == 3 else (
                Estado.REVISAR if repro["available_count"] else Estado.NO_DISPONIBLE
            ),
            observacion=f"{repro['available_count']}/3 trazas: versión del motor, semilla y parser.",
            protocolo="Presencia de los tres campos que permiten repetir la corrida.",
            procedencia="eval_result",
        ),
    ]

    # ── Dimensiones ──────────────────────────────────────────────────
    dimensiones = [
        Control(
            codigo=d["id"].upper(),
            titulo=d["label"],
            estado=_ESTADO_EVIDENCIA.get(d["status"], Estado.REVISAR),
            observacion=d["detail"],
            protocolo=None,
            procedencia="build_evidence_summary",
        )
        for d in resumen["dimensions"]
    ]

    # ── Decisiones humanas ───────────────────────────────────────────
    decisiones = [
        {
            "control": d.control_code,
            "decision": d.decision,
            "fingerprint": d.fingerprint,
            "fecha": d.at,
            "nota": d.note,
            "aplica_a_los_inputs_actuales": bool(
                huella_preflight and d.fingerprint == huella_preflight
            ),
        }
        for d in projection.decisions
    ]

    # ── Siguiente acción ─────────────────────────────────────────────
    accion = resumen["next_action"]
    estado_accion = {
        "abstain": Estado.ABSTENCION,
        "review": Estado.REVISAR,
        "proceed": Estado.REGISTRADO,
    }.get(accion["status"], Estado.REVISAR)
    if relacion == "corrida_anterior":
        siguiente = Campo(
            "Siguiente acción justificable",
            "ABSTENCIÓN: LA HIPÓTESIS CAMBIÓ",
            Estado.ABSTENCION,
            "Los inputs del caso cambiaron después de esta corrida: antes de decidir nada hay "
            "que volver a comprobar la preparación y ejecutar con la hipótesis actual.",
            valor_es_clasificacion=True,
        )
    else:
        siguiente = Campo(
            "Siguiente acción justificable",
            accion["label"],
            estado_accion,
            accion["detail"],
            valor_es_clasificacion=True,
        )

    # ── Apéndice heredado ────────────────────────────────────────────
    apendice = _apendice_heredado(eval_result)

    # ── Supuestos e incertidumbres ───────────────────────────────────
    supuestos = list(resumen["assumptions"])
    if ctx.assumptions and ctx.assumptions.strip():
        supuestos.append(f"Declarado por el caso: {ctx.assumptions.strip()}")
    incertidumbres = list(resumen["uncertainties"])
    # SC-9: la falta de calibración del receptor es una incertidumbre
    # científica declarada, no un aviso de integridad. Va aquí para que el
    # revisor la lea junto al resto de lo que el caso no puede sostener.
    if calibracion.requiere_advertencia:
        incertidumbres.insert(0, calibracion.advertencia)
    if ctx.uncertainties and ctx.uncertainties.strip():
        incertidumbres.append(f"Declarado por el caso: {ctx.uncertainties.strip()}")
    if relacion != "corresponde":
        incertidumbres.append(relacion_texto)

    return CaseDossier(
        schema_version=DOSSIER_SCHEMA_VERSION,
        generated_at=generado,
        case_id=projection.case_id,
        case_name=projection.name,
        case_schema_version=projection.case_schema_version,
        molecule_id=molecule_id,
        task_id=task_declarado,
        target_label=target_label,
        portada=portada,
        proposito=proposito,
        ejecucion=ejecucion,
        entradas=entradas,
        preparacion=preparacion,
        protocolo=protocolo,
        generacion=generacion,
        seleccion=seleccion,
        validacion=validacion,
        evidencia_poses=evidencia_poses,
        poses=poses,
        poses_estado=poses_estado,
        poses_razon=poses_razon,
        controles=controles,
        dimensiones=dimensiones,
        supuestos=supuestos,
        incertidumbres=incertidumbres,
        decisiones=decisiones,
        siguiente_accion=siguiente,
        procedencia=resumen["provenance"],
        apendice_heredado=apendice,
        avisos_integridad=avisos,
    )


def _apendice_heredado(eval_result: Any) -> list[Campo]:
    """
    Índices 0-100 que el pipeline sigue calculando.

    Viven AQUÍ y en ningún otro sitio del dossier. No son probabilidad, no son
    confianza y no son calidad: son combinaciones lineales cuyo peso vive en el
    código y cuya fórmula no está versionada. Sin fórmula ni versión, un número
    entre 0 y 100 sólo puede leerse como una nota, y no lo es.

    Se conservan por compatibilidad con lecturas anteriores; se etiquetan como
    no decisionales, que es lo que `docs/53 §6.7` exige.
    """
    campos: list[Campo] = []
    for etiqueta, atributo in (
        ("Índice compuesto heredado (total_score)", "total_score"),
        ("Índice de afinidad heredado", "affinity_score"),
        ("Índice ADME heredado", "adme_score"),
        ("Índice de similitud a fármaco heredado", "druglikeness_score"),
    ):
        valor = _v(eval_result, atributo)
        if valor is None:
            continue
        campos.append(
            Campo(
                etiqueta,
                f"{float(valor):.1f}",
                # REVISAR, no REGISTRADO: el número existe, pero no autoriza
                # ninguna conclusión. `valor_es_clasificacion` mantiene la
                # cifra visible — sin ella el apéndice imprimía «REVISAR» en
                # lugar del valor y no decía nada, que es peor que decirlo con
                # su advertencia al lado.
                Estado.REVISAR,
                "Sin fórmula ni versión publicadas: no es interpretable como probabilidad, "
                "confianza ni calidad. No decisional.",
                valor_es_clasificacion=True,
            )
        )
    return campos


def hash_canonico(dossier: CaseDossier) -> str:
    """SHA-256 del modelo canónico. Ancla el PDF y el manifiesto al mismo objeto."""
    return hashlib.sha256(dossier.json_canonico().encode("utf-8")).hexdigest()
