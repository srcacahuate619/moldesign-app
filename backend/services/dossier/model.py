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
from services.targets.seccion_catalogo import catalogo_de_la_corrida
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
    #: Sección del catálogo del receptor y si su sello describe ESTA corrida
    #: (`services/targets/seccion_catalogo.py::catalogo_de_la_corrida`). Datos
    #: crudos: Preparación los lee por clave, nunca por la etiqueta de un campo.
    catalogo: dict[str, Any] = field(default_factory=dict)

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
                "catalogo": self.catalogo,
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
    if estado.respaldo is not None:
        r = estado.respaldo
        return (f"{estado.resumen} — ρ = {r['rho']:.2f}, IC 95 % [{r['ic95'][0]:.2f}; "
                f"{r['ic95'][1]:.2f}], n = {r['n']}")
    return f"{estado.resumen} — {estado.motivo}"


#: Condiciones declaradas de un sello de verificación, en frases completas: el
#: sello no se lee sin ellas. Un código desconocido se imprime, nunca se omite.
_CONDICIONES_DEL_SELLO = {
    "RECEPTOR_SIN_IONES": (
        "El receptor se acopló sin los iones del depósito (la preparación los retira); Vina no "
        "tiene término electrostático y la calibración se midió en esas condiciones."
    ),
    "SERIE_CONGENERICA": (
        "El panel es casi entero una serie de análogos: la ρ describe cómo ordena compuestos de "
        "esa serie, no ligandos de estructura diversa."
    ),
    "CONDICIONES_DEL_ENSAYO_NO_DOCUMENTADAS": (
        "Ensayo de desplazamiento de [3H]nisoxetina; el pH, la temperatura y la concentración "
        "del radioligando no constan en las fuentes consultadas, y la correlación es dentro de "
        "un único ensayo."
    ),
}

#: Avisos medidos del catálogo (`backend/data/avisos_catalogo.json`).
AVISOS_DEL_CATALOGO = {
    "SITIO_FUERA_DE_LA_UNIDAD_BIOLOGICA": (
        "Las cadenas del sitio anotado no están todas en la unidad biológica del depósito: el "
        "sitio podría ser un contacto del cristal. Pendiente de reanotar."
    ),
}

ETIQUETA_SECCION_DEL_CATALOGO = "Sección del catálogo"


def texto_del_aviso_del_catalogo(codigo: str) -> str:
    return AVISOS_DEL_CATALOGO.get(codigo) or f"Aviso del catálogo: {codigo}."


def campo_de_la_seccion(catalogo: dict[str, Any] | None) -> Campo:
    """La sección del catálogo de la corrida como campo: dossier y Preparación.

    Demostración pide revisión y no bloquea: el producto sugiere, no impide. Un
    sello verificado sólo se registra como tal si describe ESTA corrida (mismo
    receptor y mismos parámetros); si no, se dice en qué difiere y qué no
    declaró la corrida, sin confundir una cosa con la otra.
    """
    etiqueta = ETIQUETA_SECCION_DEL_CATALOGO
    if not catalogo or not catalogo.get("pdb_id"):
        return Campo(etiqueta, None, Estado.NO_EVALUADO, "La corrida no resolvió el receptor.")
    seccion = catalogo.get("seccion")
    if seccion is None:
        return Campo(
            etiqueta,
            "Receptor del usuario: fuera del catálogo incluido; MolDesign no lo ha verificado ni calibrado.",
            Estado.REGISTRADO,
        )
    if seccion == "demostracion":
        return Campo(
            etiqueta, "Demostración", Estado.REVISAR,
            "Receptor preparado automáticamente desde el PDB, sin verificación de pose ni "
            "calibración. Sirve para explorar la aplicación, no para decidir qué sintetizar.",
            valor_es_clasificacion=True,
        )
    ver = catalogo.get("verificacion") or {}
    cal, pose, prot = ver.get("calibracion") or {}, ver.get("pose") or {}, ver.get("protocolo") or {}
    parametros = (f"Medido con exhaustividad {prot.get('exhaustiveness')}, {prot.get('num_poses')} "
                  f"poses y semilla {prot.get('semilla')}.")
    if not catalogo.get("aplica_a_esta_corrida"):
        difiere = ", ".join(catalogo.get("difiere_en") or [])
        sin_declarar = ", ".join(catalogo.get("sin_declarar") or [])
        medido = (f"El sello se midió con exhaustividad {prot.get('exhaustiveness')}, "
                  f"{prot.get('num_poses')} poses y semilla {prot.get('semilla')} sobre el receptor "
                  f"{str(ver.get('receptor_sha256') or '')[:12]}")
        if difiere and sin_declarar:
            razon = (f"{medido}; esta corrida difiere en {difiere} y no declara {sin_declarar}: "
                     "la calibración no la describe.")
        elif sin_declarar:
            razon = (f"{medido}; esta corrida no declara {sin_declarar}: no se puede comprobar "
                     "que la calibración la describa.")
        else:
            razon = f"{medido}; esta corrida difiere en {difiere}: la calibración no la describe."
        return Campo(etiqueta, "Verificado; el sello no describe esta corrida", Estado.REVISAR, razon,
                     valor_es_clasificacion=True)
    ic = cal.get("ic95") or [None, None]
    frases = [
        f"Verificado · ρ = {cal.get('rho'):.2f} (IC 95 %: {ic[0]:.2f}–{ic[1]:.2f}; n = {cal.get('n')}; "
        f"{cal.get('endpoint')}, {cal.get('panel')}).",
        f"Pose del cristal reproducida en {pose.get('semillas_rmsd_ok')} de {pose.get('semillas')} "
        "semillas (RMSD ≤ 2 Å).",
        parametros,
    ]
    frases += [_CONDICIONES_DEL_SELLO.get(c) or f"Condición declarada: {c}."
               for c in ver.get("condiciones") or []]
    return Campo(etiqueta, " ".join(frases), Estado.REGISTRADO)


def _campo_unidad_acoplada(receptor: Any, procedencia_ejecucion: Any) -> Campo:
    """La unidad de receptor que la corrida acopló, distinta de la que se declaró.

    AMP-11. «Receptor declarado» dice lo que el caso pidió (en 3F75, la cadena
    A). La corrida mide sobre los bytes del PDBQT cuáles cadenas contiene
    realmente (A+P). Quien recibe el PDF sin conocer la sesión necesita las dos,
    porque la declarada no demuestra que se acoplara sólo contra ella. En las
    corridas anteriores a la medida se declara la ausencia: no se reconstruye la
    unidad a partir de la petición.
    """
    preparacion = _v(procedencia_ejecucion, "receptor_prep")
    cadenas = _v(preparacion, "prepared_chains")
    if not isinstance(cadenas, (list, tuple)) or not cadenas:
        return Campo(
            etiqueta="Receptor acoplado (unidad preparada)",
            estado=Estado.NO_DISPONIBLE,
            razon=(
                "La corrida no registró las cadenas del receptor preparado; la cadena "
                "declarada por el caso no prueba contra cuáles se acopló."
            ),
        )
    acopladas = "+".join(str(c) for c in cadenas)
    declarada = (getattr(receptor, "chain", None) or "").strip() if receptor else ""
    pdb = getattr(receptor, "pdb_id", None) if receptor else None
    valor = f"{pdb + ' · ' if pdb else ''}cadenas {acopladas}"
    if declarada and {declarada} != {str(c) for c in cadenas}:
        valor += (
            f" — el caso declaró la cadena {declarada}; el PDBQT acoplado contiene "
            f"{acopladas}"
        )
    return Campo(
        etiqueta="Receptor acoplado (unidad preparada)",
        valor=valor + " (medido sobre los bytes del PDBQT hasheado)",
        estado=Estado.REGISTRADO,
    )


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
    # SCI-A-059: la dimensión física ya no aplana `failed` en `review`, así que
    # este mapa recibe `failed` por primera vez. El vocabulario de `Estado` no
    # tiene un miembro para «se midió y falló» —lo más cercano es REVISAR—, y
    # ampliarlo cambiaría el contrato del dossier, su PDF y su JSON. Se mapea
    # explícito para no depender del `.get` por defecto; la observación del
    # control sí nombra el fallo. Un `Estado` propio queda pendiente.
    "failed": Estado.REVISAR,
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
    if es_peptidico:
        # Decisión del propietario (2026-10-04): la vía de péptidos se marca EXPERIMENTAL en pantalla y en
        # el dossier. Está probado que ESMFold carga y sirve poses; no que las poses sean buenas.
        campos.append(Campo(
            "Validación del método peptídico",
            "EXPERIMENTAL: la estructura la predice ESMFold y su calidad no está validada en MolDesign",
            Estado.REVISAR,
            "MolDesign ha comprobado que ESMFold carga y sirve estructuras, no que sean buenas. El acoplamiento "
            "lo hace después Vina sobre esa estructura predicha: su afinidad no hereda validez de la predicción.",
            valor_es_clasificacion=True,
        ))
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
    identidad = ligand_state.get("identidad_entrada") if isinstance(ligand_state, dict) else None
    if isinstance(identidad, dict):
        campos.append(_campo_dato(
            "RDKit de canonicalización", identidad.get("rdkit_version"),
            "La corrida no registró la versión de RDKit usada para la identidad.",
        ))
        campos.append(_campo_dato(
            "SHA-256 de identidad v2", identidad.get("sha256"),
            "La corrida no registró un hash de identidad con versión de RDKit.",
        ))

    campos.extend(campo for _, campo in campos_del_estado_del_ligando(ligand_state))

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


def _motivos_de_revision_de_especie(ligand_state: Any) -> list[Any]:
    """Motivos por los que la especie acoplada no puede declararse resuelta.

    Importación perezosa: RDKit no entra en el arranque por construir un expediente.
    """
    smiles = ligand_state.get("smiles_acoplado") if isinstance(ligand_state, dict) else None
    if not smiles:
        return []
    from chem.especie_en_revision import motivos_de_revision

    return motivos_de_revision(smiles)


def campos_del_estado_del_ligando(ligand_state: Any) -> list[tuple[str, Campo]]:
    """pH, especie y tautómero acoplados, con una clave estable por campo.

    Extraído sin cambios de `_campos_de_protocolo_y_abstencion`, que los sigue
    enseñando en el mismo orden. La auditoría de preparación los necesita por
    clave: seleccionarlos por su etiqueta en castellano se rompería al traducir.
    """
    campos: list[tuple[str, Campo]] = []
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
        campos.append(("ph", _campo_dato(
            "pH de protonación del ligando",
            texto_ph,
            "La corrida no registró a qué pH se protonó el ligando.",
        )))

        seleccion = protonacion.get("seleccion")
        if isinstance(seleccion, dict):
            empatados = seleccion.get("empatados")
            alternativas = protonacion.get("alternativas")
            descripcion = None
            criterio = str(seleccion.get("criterio") or "")
            if criterio.startswith("cargas_esperadas_ph_") and ph_usado is not None:
                descripcion = (
                    f"Microestado más próximo al predicho a pH {ph_usado:g}"
                    + (f", de {alternativas} enumerados" if isinstance(alternativas, int) else "")
                    + (
                        f"; {empatados} empataron y el desempate fue alfabético"
                        if isinstance(empatados, int) and empatados > 1 else ""
                    )
                )
            elif criterio == "primer_smiles_alfabetico_sin_centros":
                descripcion = (
                    "Primer SMILES canónico por orden alfabético: la tabla no "
                    "reconoció centros ionizables y no estimó poblaciones"
                    + (f"; {empatados} candidatos" if isinstance(empatados, int) else "")
                )
            elif criterio == "grupo_reconocido_sin_pka":
                clases = ", ".join(seleccion.get("clases_sin_pka") or [])
                descripcion = (
                    f"Menor carga formal entre alternativas y entrada; {clases} "
                    "carece de pKa verificado. Población química no determinada."
                )
            # `rstrip(".")`: la descripción de un grupo sin pKa ya acaba en punto y
            # el sufijo dejaba «no determinada.; el grupo…».
            if seleccion.get("revision_biguanida"):
                descripcion = (descripcion or "Selección de biguanida").rstrip(".") + (
                    "; monocatión como hipótesis en revisión por datos "
                    "experimentales discrepantes cerca de pH fisiológico"
                )
            elif seleccion.get("clases_sin_pka") and descripcion:
                descripcion = descripcion.rstrip(".") + "; el grupo sin pKa sigue en revisión"
            # Clases que la tabla de pKa por clases no resuelve aunque la selección
            # se declare resuelta (piperazinas, N-sulfonil-piperazinas, ácidos
            # enólicos): se DECLARAN en revisión; lo acoplado no cambia. Ver
            # `chem/especie_en_revision.py` y QA-002/QA-024/QA-S05.
            motivos = _motivos_de_revision_de_especie(ligand_state)
            if descripcion and (seleccion.get("quimica_resuelta") is False or motivos):
                # Frases completas y literales: así tienen su traducción exacta y
                # el auditor del catálogo inglés las ve vivas.
                razon = descripcion.rstrip(".") + ". " + (
                    "La selección es reproducible, pero la población del microestado no "
                    "quedó establecida por una constante química verificada."
                    if seleccion.get("quimica_resuelta") is False else
                    "La selección es reproducible, pero la población de esta clase no la "
                    "resuelve la tabla de pKa por clases."
                )
                if motivos:
                    # Una frase por motivo: cada una tiene su traducción exacta.
                    # Unidas con «; y por» no casaba ninguna plantilla y el
                    # dossier en inglés salía con el párrafo en castellano.
                    razon += (
                        "".join(f" {m.texto}" for m in motivos)
                        + " Revisa la especie antes de un cálculo de energía libre."
                    )
                campos.append(("especie", Campo("Especie acoplada", None, Estado.REVISAR, razon)))
            else:
                campos.append(("especie", _campo_dato(
                    "Especie acoplada",
                    descripcion,
                    "La corrida no registró con qué criterio se eligió el microestado.",
                )))

        # ── Con qué se enumeraron los microestados (CLAVE-09) ───────────────
        #
        # Para que un tercero repita la enumeración y compruebe que obtiene el
        # mismo conjunto, no sólo el mismo elegido (FEP-05/06). Las corridas
        # anteriores no lo registraron y no enseñan este campo.
        parametros = protonacion.get("parametros")
        if isinstance(parametros, dict) and protonacion.get("candidatos_sha256"):
            valor = (
                f"dimorphite-dl {protonacion.get('version_motor') or 'versión no registrada'} · "
                f"pH {parametros.get('ph_min'):g}–{parametros.get('ph_max'):g} · "
                f"precisión {parametros.get('precision'):g} · máximo {parametros.get('max_variants')} · "
                f"huella {str(protonacion['candidatos_sha256'])[:12]}"
            )
            if protonacion.get("recortado"):
                campos.append(("enumeracion", Campo(
                    "Enumeración de microestados", valor + " · recortada al máximo", Estado.REVISAR,
                    "dimorphite-dl devolvió su número máximo de microestados: el conjunto puede estar "
                    "incompleto y la especie acoplada se eligió entre los que devolvió.",
                    valor_es_clasificacion=True,
                )))
            else:
                campos.append(("enumeracion", Campo("Enumeración de microestados", valor)))

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
        mode = tautomeria.get("modo")
        if mode in ("entrada", "canonico"):
            choice = (
                "Se acopló el tautómero del usuario; la protonación sigue el pH declarado."
                if mode == "entrada" else
                "Se acopló el tautómero canónico de RDKit; la protonación sigue el pH declarado."
            )
            texto = f"{choice} {texto}"
        if declaracion["estado"] == RESUELTO_UNICO:
            campos.append(("tautomero", Campo("Tautómero del ligando", texto, Estado.REGISTRADO, None)))
        elif declaracion["estado"] == MULTIESTADO_REQUERIDO:
            campos.append(("tautomero", Campo("Tautómero del ligando", None, Estado.REVISAR, texto)))
        else:
            campos.append(("tautomero", Campo("Tautómero del ligando", None, Estado.ABSTENCION, texto)))
    return campos


def _campo_de_estado_quimico(eval_result: Any) -> Campo:
    """Identidad estereoquímica registrada o incertidumbre explícita."""
    ligand_state = _v(eval_result, "ligand_state") or {}
    estereo = ligand_state.get("estereoquimica") if isinstance(ligand_state, dict) else None
    if isinstance(estereo, dict):
        smiles_3d = estereo.get("smiles_3d_efectivo")
        centros = int(estereo.get("centros_sin_asignar") or 0)
        dobles = int(estereo.get("dobles_sin_asignar") or 0)
        sin_clasificar = int(estereo.get("dobles_sin_clasificar_3d") or 0)
        if not smiles_3d:
            return Campo(
                "Estereoquímica del ligando", None, Estado.ABSTENCION,
                "No se pudo asignar el isómero desde la geometría 3D guardada.",
            )
        perdida = estereo.get("perdida_en_la_especie_acoplada") or {}
        centros_perdidos = int(perdida.get("centros") or 0)
        dobles_perdidos = int(perdida.get("dobles") or 0)
        if centros_perdidos or dobles_perdidos:
            # QA-032: la entrada lo declaraba; la especie acoplada ya no.
            return Campo(
                "Estereoquímica del ligando", smiles_3d, Estado.REVISAR,
                f"La entrada declaraba {centros_perdidos} estereocentro(s) y "
                f"{dobles_perdidos} doble(s) E/Z que la especie acoplada no conserva "
                "(la normalización cambió esos átomos): lo acoplado no es el "
                "estereoisómero escrito.",
            )
        if centros or dobles:
            return Campo(
                "Estereoquímica del ligando", smiles_3d, Estado.REVISAR,
                f"La entrada dejó {centros} centro(s) y {dobles} doble(s) E/Z "
                f"sin especificar; el conformero representa un isómero. "
                f"{sin_clasificar} doble(s) siguen sin clasificar desde 3D. "
                "Los demás estereoisómeros no se evaluaron.",
            )
        return Campo(
            "Estereoquímica del ligando", smiles_3d, Estado.REGISTRADO,
            "SMILES isomérico derivado del conformero 3D guardado.",
        )
    tautomeria = ligand_state.get("tautomeria") if isinstance(ligand_state, dict) else None
    if isinstance(tautomeria, dict) and isinstance(tautomeria.get("declaracion"), dict):
        return Campo(
            "Estereoquímica del ligando", None, Estado.NO_EVALUADO,
            "La corrida registra el pH, el microestado y el tautómero (ver el protocolo); "
            "la estereoquímica no se evaluó en esa corrida.",
        )
    return Campo(
        "Protonación, tautomería y estereoquímica", None, Estado.NO_EVALUADO,
        "El pipeline no registra la forma protonada ni el tautómero elegidos.",
    )


def _campo_de_registros_retirados(preparacion: Any) -> Campo | None:
    """Cuántos registros HETATM retiró la preparación de TODA la estructura, sin juicio.

    Es el único dato del diff que la auditoría de Preparación no trae (ella mira lo retirado junto al sitio). Va aparte y sin
    estado de revisión: no clasifica nada, así que no puede decir otra cosa que la auditoría. Los recuentos son REGISTROS
    HETATM, no moléculas: un HEM son 43.
    """
    diff = _v(preparacion, "species_diff") if isinstance(preparacion, dict) else None
    if not isinstance(diff, dict) or diff.get("state") != "evaluado":
        return None
    retirado = diff.get("removed") or {}
    return Campo(
        "Registros HETATM retirados del ensamblaje",
        f"aguas {retirado.get('waters', 0)}, metales {retirado.get('metals', 0)}, cofactores orgánicos "
        f"{retirado.get('organic_cofactors', 0)}, otras especies {retirado.get('other_hetatm', 0)}",
        Estado.REGISTRADO,
    )


def _campo_de_especies_convertidas(preparacion: Any) -> Campo | None:
    """Las especies junto al sitio que la preparación conservó con el nombre de otro residuo (MSE → MET), sin juicio.

    La auditoría de Preparación no las nombra (mira lo retirado), y el PDF antiguo las imprimía dentro de su fila única
    («conservado MSE A:2 … como MET»): sin esta fila, cambiar el cálculo habría borrado una sustitución química del receptor.
    La flecha va sin palabras para que no haga falta traducirla.
    """
    diff = _v(preparacion, "species_diff") if isinstance(preparacion, dict) else None
    cerca = diff.get("near_site") if isinstance(diff, dict) and diff.get("state") == "evaluado" else None
    if not isinstance(cerca, dict):
        return None
    filas = [f for lista in ("removed", "preserved") for f in cerca.get(lista) or [] if f.get("converted_to")]
    if not filas:
        return None
    return Campo(
        "Especies conservadas como otro residuo (Å a la caja)",
        ", ".join(f"{f.get('name')} {f.get('chain')}:{f.get('residue_number')}{f.get('insertion_code') or ''} "
                  f"({f.get('distance_to_box_A')} Å) → {f['converted_to']}" for f in filas),
        Estado.REGISTRADO,
    )


def _campos_de_especies(procedencia_ejecucion: Any, projection: CaseProjection, contexto: Any) -> list[Campo]:
    """Metales, cofactores, aguas y otras especies que la preparación retiró, según la corrida.

    Los campos con veredicto NO se calculan aquí: son los de la auditoría de Preparación
    (`preparacion.campos_del_entorno_para_el_dossier`), para que el PDF y `audit.json` del mismo paquete digan lo mismo. Antes
    esta función los recalculaba a distancia de la caja con un solo estado, REVISAR (2026-10-22: ver ese módulo).
    """
    # Import tardío: `preparacion` importa este módulo.
    from services.dossier.preparacion import campos_del_entorno_para_el_dossier

    preparacion = _v(procedencia_ejecucion, "receptor_prep") or {}
    registros = _campo_de_registros_retirados(preparacion)
    convertidas = _campo_de_especies_convertidas(preparacion)
    return [*campos_del_entorno_para_el_dossier(preparacion, projection, contexto),
            *(c for c in (registros, convertidas) if c)]


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


#: Cómo se escribe el campo de fuerza que registró el conformador (`chem/conformer.py`).
_CAMPO_DE_FUERZA = {"MMFF94": "MMFF94", "UFF": "UFF (MMFF94 no parametrizó la molécula)"}


def _metodo_conformacional(eval_result: Any) -> tuple[str, bool]:
    """(método, ¿optimizado con MMFF94 y convergido?) del confórmero de entrada.

    SCI-A-025: el dossier escribía siempre «ETKDG + MMFF94», aunque el conformador
    cae a UFF cuando MMFF no parametriza la molécula y a una geometría sin optimizar
    si UFF también falla, y lo deja dicho en `ligand_state.conformero`. Sin ese
    registro no se atribuye ningún método.
    """
    ligand_state = _v(eval_result, "ligand_state") or {}
    conformero = ligand_state.get("conformero") if isinstance(ligand_state, dict) else None
    if not isinstance(conformero, dict) or not conformero.get("campo_fuerza_final"):
        return "método no registrado por la corrida", False
    embebido = str(conformero.get("estrategia_embebido") or "ETKDG")
    campo = str(conformero["campo_fuerza_final"])
    if campo == "sin_optimizacion":
        return f"{embebido}, sin optimizar: MMFF94 y UFF fallaron", False
    texto = f"{embebido} + {_CAMPO_DE_FUERZA.get(campo, campo)}"
    convergida = conformero.get("optimizacion_convergida") is True
    if not convergida:
        texto += ", sin converger"
    return texto, campo == "MMFF94" and convergida


def _campo_de_la_corrida(declarado: Any, registrado: Any) -> Campo:
    """La identidad de la corrida, comprobada contra el resultado almacenado (SCI-A-022).

    Se imprimía el `task_id` que declara el caso con `REGISTRADO` aunque el resultado
    almacenado no guardara ninguno: la falta de un identificador guardado no demuestra
    que coincidan. La discordancia la rechaza antes el router (409) y la avisa el
    dossier; aquí se distingue «comprobada» de «sólo declarada».
    """
    declarado = str(declarado) if declarado else None
    registrado = str(registrado) if registrado else None
    if declarado and registrado and declarado == registrado:
        return Campo("Corrida", declarado, Estado.REGISTRADO)
    if declarado and not registrado:
        return Campo(
            "Corrida", f"{declarado} (declarada por el caso)", Estado.REVISAR,
            "El resultado almacenado no guarda identificador de corrida: la correspondencia con la "
            "corrida que declara el caso no se pudo comprobar.",
            valor_es_clasificacion=True,
        )
    if registrado and not declarado:
        return Campo("Corrida", registrado, Estado.REGISTRADO,
                     "El caso no la declaró; es la del resultado almacenado.")
    if declarado and registrado:
        return Campo(
            "Corrida", f"{declarado} (declarada por el caso)", Estado.REVISAR,
            f"El resultado almacenado pertenece a la corrida «{registrado}».",
            valor_es_clasificacion=True,
        )
    return _campo_dato("Corrida", None, "El caso no registró identificador de corrida.")


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

    metodo, metodo_completo = _metodo_conformacional(eval_result)

    if pedidas <= 1:
        return Campo(
            "Generación conformacional",
            f"Confórmero único ({metodo})",
            Estado.REGISTRADO if metodo_completo else Estado.REVISAR,
            None if metodo_completo else (
                "La geometría de entrada no se optimizó con MMFF94 hasta converger, o la corrida "
                "no registró cómo se optimizó: las poses de Vina parten de ella."
            ),
            valor_es_clasificacion=not metodo_completo,
        )

    if conseguidas <= 1:
        # SCI-A-038: el ensemble se pidió y cayó a un único confórmero.
        return Campo(
            "Generación conformacional",
            f"Confórmero único ({metodo}) · se pidieron {pedidas} conformaciones",
            Estado.REVISAR,
            f"Se pidieron {pedidas} conformaciones y la corrida siguió con una sola: el ensemble "
            "no se generó y su cobertura no está.",
            valor_es_clasificacion=True,
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
    #
    # SCI-A-024: el denominador es lo que el motor DEVOLVIÓ, no `conformaciones ×
    # num_poses`. Vina puede dar menos modos de los pedidos y una conformación
    # puede no acoplarse; multiplicar convertía el máximo solicitado en un hecho.
    # El recuento real está en `execution_provenance.por_conformacion`; sin él, se
    # dice que es un máximo.
    num_poses = protocolo.get("num_poses")
    por_conformacion = (protocolo.get("execution_provenance") or {}).get("por_conformacion")
    medidas = ([c.get("num_poses") for c in por_conformacion]
               if isinstance(por_conformacion, list) and por_conformacion else None)
    if medidas and all(isinstance(n, int) and not isinstance(n, bool) and n >= 0 for n in medidas):
        piscina = f" · pose elegida entre {sum(medidas)} candidatas"
    elif isinstance(num_poses, int) and num_poses > 0 and conseguidas > 0:
        piscina = f" · pose elegida entre hasta {conseguidas * num_poses} candidatas (recuento no registrado)"
    else:
        piscina = ""

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


#: Cuántos nombres de residuo se escriben en el dossier antes de abreviar con «… y N más».
_MAX_RESIDUOS_EN_DOSSIER = 12


def _campo_residuos_de_referencia(protocolo: Any) -> Campo:
    """Qué residuos de referencia usó la corrida (decisión del propietario, 2026-10-04).

    Se lee del protocolo sellado con la corrida, nunca del catálogo actual: los residuos del catálogo
    pueden no ser los que se usaron. Tres hechos distintos y una ausencia:

        catalog   se heredó el catálogo
        selected  la persona eligió un subconjunto
        none      la persona decidió NO usar residuos de referencia
        (sin dato) corrida anterior al sellado: se declara, no se sustituye
    """
    declarado = protocolo.get("reference_residues") if isinstance(protocolo, dict) else None
    if not isinstance(declarado, dict):
        return Campo(
            "Residuos de referencia",
            None,
            Estado.NO_EVALUADO,
            "Esta corrida es anterior al sellado de los residuos de referencia. No se sustituyen por los "
            "del catálogo: podrían no ser los que se usaron.",
        )

    origen = declarado.get("source")
    nombres = [str(n) for n in (declarado.get("residues") or [])]
    cuantos = len(nombres)
    total = declarado.get("catalog_count")

    if origen == "none" or cuantos == 0:
        return Campo(
            "Residuos de referencia",
            "Ninguno: la persona decidió no usar residuos de referencia",
            Estado.REGISTRADO,
            "Sin residuos de referencia la corrida no calcula qué residuos del sitio contactan las poses.",
            valor_es_clasificacion=True,
        )

    lista = ", ".join(nombres[:_MAX_RESIDUOS_EN_DOSSIER])
    if cuantos > _MAX_RESIDUOS_EN_DOSSIER:
        lista += f" … y {cuantos - _MAX_RESIDUOS_EN_DOSSIER} más"
    if origen == "selected":
        de_cuantos = f" de {total}" if isinstance(total, int) and total > 0 else ""
        valor = f"{cuantos} elegidos{de_cuantos} del catálogo: {lista}"
    else:
        valor = f"{cuantos} del catálogo: {lista}"
    return Campo(
        "Residuos de referencia", valor, Estado.REGISTRADO, None, valor_es_clasificacion=True,
    )


def relacion_comprobada(projection: CaseProjection) -> tuple[str, str | None]:
    """La relación corrida↔inputs que se puede comprobar, y el aviso si difiere.

    Con las dos huellas, manda la comparación y no lo que declaró el cliente.
    Sin ellas, se conserva la declaración. La usan el dossier y la auditoría
    de preparación, que no puede leerla de una etiqueta del dossier.
    """
    relacion = projection.run_inputs_relation
    huella_corrida = projection.run.input_fingerprint if projection.run else None
    huella_preflight = projection.preflight.fingerprint if projection.preflight else None
    if not (huella_corrida and huella_preflight):
        return relacion, None
    comprobada = "corresponde" if huella_corrida == huella_preflight else "corrida_anterior"
    if comprobada == relacion:
        return comprobada, None
    return comprobada, (
        "El cliente declaró la relación corrida/inputs como "
        f"«{relacion}», pero las huellas dicen «{comprobada}». Manda lo comprobable."
    )


def build_case_dossier(
    *,
    projection: CaseProjection,
    molecule: Any,
    eval_result: Any,
    target: Any,
    artefactos: list[Artefacto] | None = None,
    generated_at: datetime | None = None,
    contexto: Any | None = None,
) -> CaseDossier:
    """
    Interpreta la corrida UNA vez.

    `generated_at` es inyectable para que el paquete pueda ser determinista bajo
    reloj congelado; sin eso, dos ZIP de la misma corrida diferirían sólo por la
    hora y el verificador no serviría para comparar.

    `contexto` es el `ContextoEstructural` que mide las distancias al ligando (`contexto_estructural.medir`). Lo usa la
    sección de especies del sitio para decir lo mismo que la auditoría de Preparación; sin él, ambas miden desde la caja.
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
    catalogo = catalogo_de_la_corrida(target, _v(eval_result, "docking_protocol") or {})

    portada = [
        Campo("Caso", projection.name),
        _campo_dato("Molécula", molecule_id, "El backend no resolvió la molécula."),
        Campo("Receptor", target_label),
        # SC-9: el dossier es el documento que sale del producto y el que un
        # revisor lee. Si no dice qué respaldo tenía el receptor, invita
        # exactamente a la lectura que el catálogo no puede sostener.
        Campo("Respaldo del receptor", _respaldo_del_receptor(target)),
        # Un resultado de un receptor de demostración no puede salir del producto
        # pareciendo de uno verificado: lo dice la portada, no sólo la pantalla.
        campo_de_la_seccion(catalogo),
        _campo_de_la_corrida(task_declarado, task_registrado),
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
    # AMP-05. Las notas ya viajaban en `case_snapshot.json` del paquete pero no
    # en el documento que lee una persona: un canal que sólo ve quien abre el
    # ZIP. Si salen del equipo, se ven. Sólo se imprimen cuando existen —un
    # hueco en un campo opcional no es información— y la etiqueta dice lo que
    # son: contexto libre del investigador, que no entra en ningún cálculo.
    if ctx.notes and ctx.notes.strip():
        proposito.append(
            _campo_contexto("Notas del caso (contexto libre; no entra en ningún cálculo)", ctx.notes)
        )

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
    protocolo_corrida = _v(eval_result, "docking_protocol") or {}
    estado_ligando = _v(eval_result, "ligand_state") or {}
    procedencia_ejecucion = _v(protocolo_corrida, "execution_provenance") or {}
    centro_corrida = _v(procedencia_ejecucion, "box_center")
    tamano_corrida = _v(procedencia_ejecucion, "box_size")

    entradas = [
        _campo_dato(
            "Receptor declarado",
            f"{receptor.pdb_id}" + (f" · cadena {receptor.chain}" if receptor and receptor.chain else "")
            if receptor else None,
            "El caso no declaró receptor.",
        ),
        _campo_unidad_acoplada(receptor, procedencia_ejecucion),
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
            _v(estado_ligando, "smiles_acoplado"),
            "No se registró la forma canónica del ligando.",
        ),
        _campo_dato(
            "Caja de búsqueda efectiva",
            (f"centro {tuple(centro_corrida)} · tamaño {tuple(tamano_corrida)} Å"
             if centro_corrida and tamano_corrida else None),
            "La corrida no persistió la caja de búsqueda efectiva; la caja declarada por el caso no prueba la ejecutada.",
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
    relacion, aviso_relacion = relacion_comprobada(projection)
    if aviso_relacion:
        avisos.append(aviso_relacion)

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
        *_campos_de_especies(procedencia_ejecucion, projection, contexto),
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
        _campo_dato("Versión MolDesign", _v(procedencia_ejecucion, "app_version"),
                    "La corrida no registró la versión de la aplicación."),
        _campo_dato("Commit de código", _v(procedencia_ejecucion, "git_commit"),
                    "La corrida no declaró un commit verificable (bundle o árbol modificado)."),
        _campo_dato("CPU solicitadas a Vina", _v(procedencia_ejecucion, "cpu"),
                    "La corrida no registró el argumento CPU de Vina."),
        _campo_dato("SHA-256 receptor preparado", _v(procedencia_ejecucion, "receptor_sha256"),
                    "La corrida no registró el hash del receptor preparado."),
        _campo_dato("SHA-256 ligando SDF de entrada", _v(procedencia_ejecucion, "ligand_input_sha256"),
                    "La corrida no registró el hash del conformero de entrada."),
        _campo_dato("SHA-256 ligando PDBQT", _v(procedencia_ejecucion, "ligand_pdbqt_sha256"),
                    "La corrida no registró el hash del PDBQT acoplado."),
        _campo_dato("SHA-256 poses SDF", _v(procedencia_ejecucion, "poses_sha256"),
                    "La corrida no registró el hash del SDF de salida."),
        _campo_dato("SHA-256 log", _v(procedencia_ejecucion, "log_sha256"),
                    "La corrida no registró el hash del log."),
        _campo_dato("Receta de receptor", _v(_v(procedencia_ejecucion, "receptor_prep"), "recipe_hash"),
                    "La corrida no registró el hash de receta del receptor."),
        _campo_dato("Versiones de preparación",
                    json.dumps(_v(procedencia_ejecucion, "toolchain"), ensure_ascii=False, sort_keys=True)
                    if _v(procedencia_ejecucion, "toolchain") else None,
                    "La corrida no registró la cadena de herramientas."),
        _campo_dato("Semilla aleatoria", repro.get("random_seed"), "La corrida no registró la semilla."),
        _campo_dato("Origen del parseo", repro.get("parsing_source"), "La corrida no registró el parser."),
        _campo_dato("Modelo de rescoring", modelo.get("model"), "La corrida no registró el modelo."),
        _campo_dato(
            "Configuración PRO declarada",
            json.dumps(config.pipeline_config, ensure_ascii=False, sort_keys=True) if config and config.pipeline_config else None,
            "El caso no declaró opciones PRO avanzadas; este campo no acredita su ejecución.",
        ),
        _campo_dato(
            "Exhaustiveness",
            _v(protocolo_corrida, "exhaustiveness"),
            "La corrida no registró la exhaustividad utilizada.",
        ),
        _campo_dato(
            "Poses solicitadas",
            _v(protocolo_corrida, "num_poses"),
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

    if config:
        for etiqueta, declarado, ejecutado in (
            ("Exhaustividad declarada por el caso", config.exhaustiveness, _v(protocolo_corrida, "exhaustiveness")),
            ("Poses declaradas por el caso", config.num_poses, _v(protocolo_corrida, "num_poses")),
        ):
            if declarado is not None:
                difiere = ejecutado is not None and declarado != ejecutado
                protocolo.append(Campo(
                    etiqueta,
                    str(declarado),
                    Estado.REVISAR if difiere else Estado.REGISTRADO,
                    "El valor declarado por el caso difiere del protocolo ejecutado." if difiere
                    else "Valor declarado por el caso; la ejecución se documenta por separado.",
                ))
        if config.grid_center and config.grid_size:
            difiere = bool(
                centro_corrida and tamano_corrida
                and (list(config.grid_center) != list(centro_corrida)
                     or list(config.grid_size) != list(tamano_corrida))
            )
            entradas.append(Campo(
                "Caja declarada por el caso",
                f"centro {tuple(config.grid_center)} · tamaño {tuple(config.grid_size)} Å",
                Estado.REVISAR if difiere else Estado.REGISTRADO,
                "La caja declarada difiere de la ejecutada." if difiere
                else "Valor declarado por el caso; no sustituye la caja ejecutada.",
            ))

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
        # SCI-A-036: lo que se pidió AL MOTOR en esta corrida es lo que selló su
        # protocolo. Se tomaba del caso (`config.num_poses`), que es otro objeto y
        # puede haber cambiado después: el dossier atribuía a la corrida una cifra
        # que la corrida no registró. Lo declarado por el caso sigue aparte, en
        # «Poses declaradas por el caso», con REVISAR si difiere.
        _campo_dato("Poses solicitadas al motor",
                    _v(protocolo_corrida, "num_poses"),
                    "La corrida no registró el número de poses solicitado."),
        _campo_dato("Exhaustividad", _v(protocolo_corrida, "exhaustiveness"),
                    "La corrida no registró la exhaustividad utilizada."),
        _campo_dato("Semilla aleatoria", repro.get("random_seed"),
                    "La corrida no registró la semilla: no es repetible bit a bit."),
        _campo_residuos_de_referencia(protocolo_corrida),
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
    # Avisos medidos del catálogo (p. ej. un sitio fuera de la unidad biológica).
    incertidumbres += [texto_del_aviso_del_catalogo(c) for c in catalogo.get("avisos") or []]
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
        catalogo=catalogo,
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
