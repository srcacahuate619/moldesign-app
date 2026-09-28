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
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from services.dossier.model import (
    Campo,
    CaseDossier,
    _campo_dato,
    _campo_de_estado_quimico,
    _v,
    campos_del_estado_del_ligando,
    relacion_comprobada,
)
from services.dossier.schemas import CaseProjection
from services.dossier.taxonomy import Estado

PREPARACION_SCHEMA = "preparacion/v1"

#: Sólo puede valer `True` con un `scripts/artifacts_science/FEP-06*` sellado
#: GO. Hasta entonces ninguna auditoría emite TRANSFERIBLE con alcance FEP.
TRANSFERENCIA_FEP_DEMOSTRADA = False

ALCANCE = "Auditor de readiness para FEP en desarrollo"

BLOQUES = ("receptor", "ligando", "pose", "entorno", "procedencia")

EstadoGlobal = Literal["BLOQUEADO", "REVISION", "TRANSFERIBLE"]
EstadoBloque = Literal["BLOQUEADO", "REVISION", "REGISTRADO"]

#: Especies del diff cuya retirada junto al sitio deja un receptor que no es
#: el de la estructura: bloquea hasta que alguien decida sobre ellas.
_CATEGORIAS_QUE_BLOQUEAN = ("metal", "organic_cofactor")


@dataclass(frozen=True)
class Requisito:
    """Un requisito con clave estable, su dato, de dónde sale y si es imprescindible."""

    clave: str
    campo: Campo
    fuente: str
    imprescindible: bool

    @property
    def bloquea(self) -> bool:
        estado = self.campo.estado
        if estado == Estado.NO_APLICA:
            return False
        return self.imprescindible and (estado.es_ausencia or estado == Estado.ABSTENCION)

    @property
    def pide_revision(self) -> bool:
        estado = self.campo.estado
        return not (estado.es_afirmativo or estado == Estado.NO_APLICA or self.bloquea)

    def as_dict(self) -> dict[str, Any]:
        return {
            "clave": self.clave,
            **self.campo.as_dict(),
            "fuente": self.fuente,
            "imprescindible": self.imprescindible,
        }


# ── Utilidades ───────────────────────────────────────────────────────


def _no_evaluado(etiqueta: str, razon: str) -> Campo:
    return Campo(etiqueta, None, Estado.NO_EVALUADO, razon)


def _fila(fila: dict[str, Any]) -> str:
    return (
        f"{fila.get('name')} {fila.get('chain')}:{fila.get('residue_number')}"
        f"{fila.get('insertion_code') or ''} ({fila.get('distance_to_box_A')} Å)"
    )


def _tupla(valor: Any) -> str | None:
    if not isinstance(valor, (list, tuple)) or len(valor) != 3:
        return None
    return "(" + ", ".join(f"{float(v):g}" for v in valor) + ")"


# ── 01 · Receptor y sitio ────────────────────────────────────────────


def _campo_de_huecos(huecos: Any) -> Campo:
    """Cortes del esqueleto que midió la preparación (C–N > 2 Å entre consecutivos)."""
    if huecos is None:
        return _no_evaluado(
            "Huecos del esqueleto",
            "La corrida no midió los huecos del esqueleto: su receptor se preparó antes "
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
        return (f"{h.get('chain')}: {h.get('after')} → {h.get('before')} "
                f"(C–N {h.get('c_n_distance_A')} Å"
                + (f"; {declarados} ausente(s) en REMARK 465" if declarados else "")
                + f"; {h.get('distance_to_box_A')} Å de la caja)")

    en_sitio = [h for h in huecos if h.get("site_critical")]
    return Campo(
        "Huecos del esqueleto",
        f"{len(huecos)} corte(s) del esqueleto"
        + (f"; {len(en_sitio)} junto al sitio: " + ", ".join(_hueco(h) for h in en_sitio)
           if en_sitio else "; todos lejos del sitio: " + ", ".join(_hueco(h) for h in huecos)),
        Estado.REVISAR,
        ("El esqueleto está roto junto al sitio: faltan residuos que el cristal no "
         "observó. Un cálculo posterior tendría que modelarlos, y declararlo, o capar "
         "los extremos; y el bucle ausente puede formar parte de la cavidad."
         if en_sitio else
         "Lejos del sitio no cambian la cavidad, pero un cálculo con disolvente explícito "
         "necesita esos extremos capados o modelados."),
        valor_es_clasificacion=True,
    )


def _bloque_receptor(prov: Any, prep: Any) -> list[Requisito]:
    receptor_sha = _v(prov, "receptor_sha256")
    receta = _v(prep, "recipe_hash")
    cadena = _v(prep, "chain")
    sitio = _v(prep, "site_chains") or []
    centro, tamano = _tupla(_v(prov, "box_center")), _tupla(_v(prov, "box_size"))

    retirados = _v(prep, "removed_residues")
    fuera = _v(prep, "cofactors_outside_site") or []
    if retirados is None:
        residuos = _no_evaluado(
            "Residuos retirados por la preparación",
            "La corrida no registró qué residuos retiró la preparación del receptor.",
        )
    elif not retirados and not fuera:
        residuos = Campo(
            "Residuos retirados por la preparación",
            "Meeko no retiró residuos y no hubo cofactores sin plantilla fuera del sitio.",
            Estado.REGISTRADO,
        )
    else:
        partes = [f"{r.get('chain')}:{r.get('residue_number')} {r.get('name')} "
                  f"({r.get('distance_to_box_A')} Å)" for r in retirados]
        partes += [f"{_fila(f)} {f.get('action')}" for f in fuera]
        residuos = Campo(
            "Residuos retirados por la preparación",
            f"{len(partes)} fuera del margen del sitio: " + ", ".join(partes),
            Estado.REVISAR,
            "Fuera del margen no impiden la corrida, pero el receptor que se entregaría "
            "no los contiene. Declarar si importan para el cálculo siguiente.",
            valor_es_clasificacion=True,
        )

    # Receta v7: las cadenas laterales que el cristal no resolvía se truncan a ALA
    # o GLY conservando sólo átomos observados (PDBFixer no es reproducible). En
    # el sitio, la cavidad acoplada no es la de la proteína: se declara.
    truncadas = _v(prep, "truncated_sidechains")
    if truncadas is None:
        cadenas_truncadas = _no_evaluado(
            "Cadenas laterales truncadas",
            "La corrida no registró qué cadenas laterales incompletas del cristal se "
            "truncaron: su receta es anterior a la v7 o el receptor se congeló antes.",
        )
    elif not truncadas:
        cadenas_truncadas = Campo(
            "Cadenas laterales truncadas",
            "Ninguna: el cristal resolvía todas las cadenas laterales del receptor.",
            Estado.REGISTRADO,
        )
    else:
        en_sitio = [t for t in truncadas if t.get("site_critical")]

        def _truncada(t: dict[str, Any]) -> str:
            destino = str(t.get("action") or "").split()[-1:] or ["?"]
            return (f"{t.get('chain')}:{t.get('residue_number')}{t.get('insertion_code') or ''} "
                    f"{t.get('name')}→{destino[0]} ({t.get('distance_to_box_A')} Å)")

        cadenas_truncadas = Campo(
            "Cadenas laterales truncadas",
            f"{len(truncadas)} truncada(s)"
            + (f"; {len(en_sitio)} en el sitio: " + ", ".join(_truncada(t) for t in en_sitio)
               if en_sitio else "; todas fuera del sitio"),
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
    if not isinstance(excluidas, dict):
        vecinas = _no_evaluado(
            "Cadenas excluidas junto al sitio",
            "La corrida no registró qué proteína quedó fuera del receptor junto a la caja.",
        )
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
                (f"cadena {cadena}" + (f" · sitio entre {'+'.join(sitio)}" if len(sitio) > 1 else ""))
                if cadena else None,
                "La corrida no registró qué cadenas forman el receptor.",
            ),
            "receptor_prep.chain · receptor_prep.site_chains",
            True,
        ),
        Requisito(
            "receptor.caja",
            _campo_dato(
                "Caja de trabajo",
                f"centro {centro} · tamaño {tamano} Å" if centro and tamano else None,
                "La corrida no persistió la caja efectiva.",
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
        Requisito("receptor.huecos", _campo_de_huecos(_v(prep, "backbone_gaps")),
                  "receptor_prep.backbone_gaps", False),
        Requisito("receptor.protonacion", protonacion, "receptor_prep.protonation_method", False),
    ]


# ── 02 · Estado químico del ligando ──────────────────────────────────


def _bloque_ligando(eval_result: Any, prov: Any) -> list[Requisito]:
    estado = _v(eval_result, "ligand_state") or {}
    smiles = _v(estado, "smiles_acoplado")
    sdf = _v(prov, "ligand_input_sha256")
    por_clave = dict(campos_del_estado_del_ligando(estado))
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
            por_clave.get("tautomero") or _no_evaluado(
                "Tautómero del ligando",
                "La corrida es anterior a la declaración de tautómeros y no se reconstruye.",
            ),
            "ligand_state.tautomeria.declaracion",
            True,
        ),
        Requisito("ligando.estereoquimica", _campo_de_estado_quimico(eval_result),
                  "ligand_state.estereoquimica", True),
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

    return [
        Requisito(
            "pose.origen",
            _campo_dato(
                "Poses de la corrida",
                f"SDF SHA-256 {sha}" if sha and _v(eval_result, "poses_file_path") else None,
                "La corrida no conservó el archivo de poses con su hash.",
            ),
            "eval_result.poses_file_path · execution_provenance.poses_sha256",
            True,
        ),
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


def _bloque_entorno(prep: Any, projection: CaseProjection) -> list[Requisito]:
    diff = _v(prep, "species_diff")
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
    cerca = _v(diff, "near_site") if isinstance(diff, dict) else None
    if not isinstance(diff, dict) or diff.get("state") != "evaluado" or not isinstance(cerca, dict):
        razon = (
            "La corrida usó un receptor congelado y su informe de preparación no viaja con ella."
            if _v(prep, "source") == "durable_receptor_snapshot" else
            "La corrida no serializó qué retiró la preparación: su receptor se preparó antes "
            "de registrarlo. No se reconstruye con la receta de hoy."
        )
        return [
            Requisito("entorno.metales_cofactores",
                      _no_evaluado("Metales y cofactores junto al sitio", razon),
                      "receptor_prep.species_diff", True),
            Requisito("entorno.aguas", _no_evaluado("Aguas junto al sitio", razon),
                      "receptor_prep.species_diff", False),
            Requisito("entorno.otras_especies",
                      _no_evaluado("Otras especies junto al sitio", razon),
                      "receptor_prep.species_diff", False),
            politica,
        ]

    margen = cerca.get("margin_A")
    retiradas = list(cerca.get("removed") or [])
    conservadas = list(cerca.get("preserved") or [])

    def _de(filas: list[dict[str, Any]], *categorias: str) -> list[dict[str, Any]]:
        return [f for f in filas if f.get("category") in categorias]

    bloqueantes = _de(retiradas, *_CATEGORIAS_QUE_BLOQUEAN)
    conservados = _de(conservadas, *_CATEGORIAS_QUE_BLOQUEAN)
    if bloqueantes:
        metales = Campo(
            "Metales y cofactores junto al sitio",
            f"Retirados a {margen:g} Å o menos: " + ", ".join(_fila(f) for f in bloqueantes),
            Estado.ABSTENCION,
            "El receptor que se entregaría no contiene especies que estaban en el sitio. "
            "Hay que decidir sobre ellas antes de cualquier cálculo posterior.",
            valor_es_clasificacion=True,
        )
    else:
        metales = Campo(
            "Metales y cofactores junto al sitio",
            f"Ninguno retirado a {margen:g} Å o menos"
            + (f"; conservados: {', '.join(_fila(f) for f in conservados)}" if conservados else ""),
            Estado.REGISTRADO,
        )

    aguas_fuera, aguas_dentro = _de(retiradas, "water"), _de(conservadas, "water")

    def _por_distancia(filas: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(filas, key=lambda f: (f.get("distance_to_box_A") is None,
                                            f.get("distance_to_box_A") or 0.0))

    # TODAS, una por una y de la más cercana a la más lejana: decidir cuáles son
    # estructurales exige saber cuáles eran. Un recuento no deja decidir nada.
    aguas = (
        Campo(
            "Aguas junto al sitio",
            f"{len(aguas_fuera)} retirada(s) a {margen:g} Å o menos: "
            + ", ".join(_fila(f) for f in _por_distancia(aguas_fuera))
            + (f"; {len(aguas_dentro)} conservada(s): "
               + ", ".join(_fila(f) for f in _por_distancia(aguas_dentro))
               if aguas_dentro else "; ninguna conservada"),
            Estado.REVISAR,
            "La ruta de docking retira todas las aguas. No se ha decidido cuáles son "
            "estructurales y cuáles desplazables.",
            valor_es_clasificacion=True,
        ) if aguas_fuera else Campo(
            "Aguas junto al sitio",
            f"Ninguna retirada a {margen:g} Å o menos; {len(aguas_dentro)} conservada(s)",
            Estado.REGISTRADO,
        )
    )

    otras_fuera = _de(retiradas, "other_heteroatom")
    otras = (
        Campo(
            "Otras especies junto al sitio",
            "Retiradas: " + ", ".join(_fila(f) for f in otras_fuera),
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
        Requisito("entorno.metales_cofactores", metales, "receptor_prep.species_diff.near_site", True),
        Requisito("entorno.aguas", aguas, "receptor_prep.species_diff.near_site", False),
        Requisito("entorno.otras_especies", otras, "receptor_prep.species_diff.near_site", False),
        politica,
    ]


# ── 05 · Procedencia y entrega ───────────────────────────────────────

_HASHES = ("receptor_sha256", "ligand_input_sha256", "ligand_pdbqt_sha256", "poses_sha256", "log_sha256")


def _bloque_procedencia(eval_result: Any, prov: Any, projection: CaseProjection) -> list[Requisito]:
    faltan = [h for h in _HASHES if not _v(prov, h)]
    hashes = (
        Campo("Hashes de entrada y salida", f"{len(_HASHES)}/{len(_HASHES)} registrados",
              Estado.REGISTRADO)
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
        ),
        Requisito("procedencia.relacion", relacion_campo, "huellas de la corrida y del preflight", False),
        *previa,
    ]


# ── Agregación ───────────────────────────────────────────────────────


def _estado_del_bloque(requisitos: list[Requisito]) -> EstadoBloque:
    if any(r.bloquea for r in requisitos):
        return "BLOQUEADO"
    if any(r.pide_revision for r in requisitos):
        return "REVISION"
    return "REGISTRADO"


def estado_global(requisitos: list[Requisito]) -> tuple[EstadoGlobal, str]:
    """El estado de la auditoría entera. TRANSFERIBLE exige la constante del guardián."""
    if any(r.bloquea for r in requisitos):
        return "BLOQUEADO", "Falta evidencia imprescindible o hay una abstención declarada."
    if any(r.pide_revision for r in requisitos):
        return "REVISION", "Hay decisiones científicas abiertas que el cálculo siguiente heredaría."
    if TRANSFERENCIA_FEP_DEMOSTRADA:
        return "TRANSFERIBLE", "Controles superados para el alcance declarado."
    return "REVISION", (
        "Todos los requisitos tienen dato registrado, pero la transferencia a un cálculo "
        "FEP no está demostrada: FEP-06 sigue sin sellar."
    )


def build_preparacion(
    dossier: CaseDossier, eval_result: Any, projection: CaseProjection,
) -> dict[str, Any]:
    """La auditoría de preparación de la corrida que describe ``dossier``."""
    protocolo = _v(eval_result, "docking_protocol") or {}
    prov = _v(protocolo, "execution_provenance") or {}
    prep = _v(prov, "receptor_prep") or {}

    bloques = {
        "receptor": _bloque_receptor(prov, prep),
        "ligando": _bloque_ligando(eval_result, prov),
        "pose": _bloque_pose(dossier, eval_result, prov),
        "entorno": _bloque_entorno(prep, projection),
        "procedencia": _bloque_procedencia(eval_result, prov, projection),
    }
    todos = [r for requisitos in bloques.values() for r in requisitos]
    estado, razon = estado_global(todos)

    return {
        "schema": PREPARACION_SCHEMA,
        "alcance": ALCANCE,
        "transferencia_fep_demostrada": TRANSFERENCIA_FEP_DEMOSTRADA,
        "estado": estado,
        "razon": razon,
        "bloqueantes": [r.clave for r in todos if r.bloquea],
        "en_revision": [r.clave for r in todos if r.pide_revision],
        "bloques": [
            {
                "id": nombre,
                "estado": _estado_del_bloque(bloques[nombre]),
                "requisitos": [r.as_dict() for r in bloques[nombre]],
            }
            for nombre in BLOQUES
        ],
        "corrida": {
            "case_id": dossier.case_id,
            "molecule_id": dossier.molecule_id,
            "task_id": dossier.task_id,
            "target": dossier.target_label,
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
