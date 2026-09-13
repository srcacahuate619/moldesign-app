"""
Dossier de cohorte: la lectura humana y su contraparte verificable.

# Un solo protocolo de empaquetado

El ZIP se arma con `services/dossier/package.py::empaquetar`, el MISMO núcleo
que usa el dossier de caso desde Sprint 4. No hay un segundo protocolo de
checksums, y por eso `scripts/verify_dossier_package.py` —el mismo verificador—
valida los dos sin saber cuál está mirando.

Lo que cambia es QUÉ va dentro. Lo que no cambia es cómo se declara, se hashea
y se sella.

# Lo que el manifiesto promete

Todos los artefactos aparecen, incluidos los que NO están: un artefacto ausente
se declara con `NO_DISPONIBLE` y su razón. Omitirlo dejaría al lector sin saber
si el archivo no se generó o si alguien lo quitó del ZIP.

# Lo que el PDF NO dice

No hay ranking de candidatos, ni puntuación agregada, ni «mejores fármacos».
Hay cobertura, excepciones, afinidad Vina observada y, si son evaluables,
métricas etiquetadas con su límite de interpretación al lado.
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from services.dossier.package import (
    ArchivoPaquete,
    _json_canonico,
    empaquetar,
    sanitizar,
)
from services.dossier.pdf import _Chrome, _escapar, _estilos, _romper_largo
from services.dossier.taxonomy import Estado

#: Contrato del dossier de cohorte.
COHORT_DOSSIER_CONTRACT = "cohort_dossier/v1"

#: Filas que se imprimen en la tabla del PDF. Un PDF de 500 filas no se lee; el
#: ZIP lleva `rows.csv` con TODAS, y el PDF lo dice explícitamente.
MAX_PDF_ROWS = 60


def raiz_paquete_cohorte(cohort_name: str, run_id: uuid.UUID) -> str:
    corta = sanitizar(str(run_id), maximo=12)
    return f"moldesign_cohort_{sanitizar(cohort_name, maximo=40)}_run_{corta}"


# ── PDF ──────────────────────────────────────────────────────────────


def _tabla(datos: list[list[Any]], est, anchos: list[float]) -> Table:
    tabla = Table(datos, colWidths=anchos, repeatRows=1, hAlign="LEFT")
    tabla.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c9ced6")),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return tabla


def render_cohort_dossier_pdf(evidencia: dict[str, Any]) -> io.BytesIO:
    """
    Dossier de cohorte en PDF. Determinista salvo por lo que ya trae la corrida.

    El orden de las secciones es el orden en que hay que leerlas: primero qué se
    preguntó y sobre qué, después qué entró y qué quedó fuera, y sólo al final
    los números — nunca al revés, porque una tabla de afinidades al principio se
    lee como un ranking de candidatos.
    """
    est = _estilos()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=2.0 * cm,
        bottomMargin=2.0 * cm,
        title=f"Dossier de cohorte · {evidencia['cohort_name']}",
        author="MolDesign",
        subject="Evidencia computacional de una cohorte",
    )

    cobertura = evidencia["coverage"]
    config = evidencia["effective_config"]
    receptor = evidencia["receptor"]
    metricas = evidencia["labeled_metrics"]
    historia: list[Any] = []

    def parrafo(texto: str, estilo: str = "cuerpo") -> Paragraph:
        return Paragraph(_escapar(texto), est[estilo])

    def seccion(titulo: str) -> None:
        historia.append(Spacer(1, 0.45 * cm))
        historia.append(Paragraph(_escapar(titulo), est["seccion"]))

    # ── 1. Identidad y pregunta computacional ────────────────────────
    historia.append(Paragraph(_escapar(f"Dossier de cohorte · {evidencia['cohort_name']}"), est["titulo"]))
    historia.append(parrafo(
        "Este documento responde una pregunta computacional y sólo una: qué entró en "
        "esta cohorte, qué se pudo acoplar bajo una configuración común, y qué quedó "
        "sin evaluar. NO responde si alguna de estas moléculas es un fármaco."
    ))
    historia.append(Spacer(1, 0.3 * cm))
    historia.append(_tabla(
        [
            ["Campo", "Valor"],
            ["Cohorte", evidencia["cohort_name"]],
            ["Estado de la corrida", evidencia["run_status"]],
            ["Huella de cohorte", _romper_largo(evidencia["cohort_fingerprint"])],
            ["Huella de corrida", _romper_largo(evidencia["run_fingerprint"])],
            ["Contrato", COHORT_DOSSIER_CONTRACT],
        ],
        est, [4.5 * cm, 12.0 * cm],
    ))

    # ── 2. Cohorte y receptor ────────────────────────────────────────
    seccion("2 · Receptor")
    historia.append(_tabla(
        [
            ["Campo", "Valor"],
            ["PDB ID", receptor.get("pdb_id", "NO DECLARADO")],
            ["Cadena", receptor.get("chain") or "NO DECLARADA"],
            ["SHA-256 del preparado", _romper_largo(str(receptor.get("prepared_sha256", "NO DISPONIBLE")))],
            ["Tamaño (bytes)", str(receptor.get("prepared_size_bytes", "—"))],
            ["Objeto", receptor.get("prepared_object", "—")],
        ],
        est, [4.5 * cm, 12.0 * cm],
    ))
    historia.append(parrafo(
        "El receptor preparado se congeló por su contenido. Dos corridas con el mismo "
        "SHA-256 usaron el mismo receptor; con hashes distintos, no, por mucho que la "
        "ruta coincida."
    ))

    # ── 3. Configuración efectiva ────────────────────────────────────
    seccion("3 · Configuración efectiva")
    historia.append(parrafo("La misma para todas las filas. Se resolvió una vez, al abrir la corrida."))
    historia.append(Spacer(1, 0.2 * cm))
    historia.append(_tabla(
        [
            ["Parámetro", "Valor"],
            ["Caja (centro)", str(config.get("grid_center"))],
            ["Caja (tamaño)", str(config.get("grid_size"))],
            ["Origen de la caja", str(config.get("grid_origin"))],
            ["Motor", str(config.get("docking_engine"))],
            ["Versión del motor", str(config.get("engine_version") or "NO DISPONIBLE")],
            ["Exhaustividad", str(config.get("exhaustiveness"))],
            ["Poses", str(config.get("num_poses"))],
            ["Semilla", str(config.get("seed") if config.get("seed") is not None else "NO DECLARADA")],
        ],
        est, [4.5 * cm, 12.0 * cm],
    ))

    # ── 4. Cobertura y excepciones ───────────────────────────────────
    seccion("4 · Cobertura y excepciones")
    historia.append(_tabla(
        [
            ["Recuento", "Valor"],
            ["Filas en el archivo", str(cobertura["source_rows"])],
            ["Filas elegibles", str(cobertura["eligible_rows"])],
            ["Filas NO elegibles", str(cobertura["not_eligible_rows"])],
            ["Moléculas únicas acopladas", str(cobertura["unique_molecules_executed"])],
            ["Completadas", str(cobertura["completed_rows"])],
            ["Duplicados reutilizados", str(cobertura["duplicate_reused_rows"])],
            ["Fallidas", str(cobertura["failed_rows"])],
            ["No evaluadas", str(cobertura["not_evaluated_rows"])],
            ["Interrumpidas", str(cobertura["interrupted_rows"])],
            ["Canceladas", str(cobertura["cancelled_rows"])],
        ],
        est, [7.0 * cm, 9.5 * cm],
    ))
    historia.append(parrafo(
        "Las filas NO elegibles nunca entraron: el preflight las declaró inválidas antes "
        "de ejecutar. No desaparecen del recuento porque el denominador tiene que seguir "
        "siendo el del archivo que se subió."
    ))
    historia.append(parrafo(
        "«Fallida» y «no evaluada» describen lo que le pasó al MOTOR, no a la molécula. "
        "Ninguna de las dos es evidencia negativa."
    ))

    # ── Embudo estructural: cada escalón con SU denominador ──────────
    embudo = cobertura.get("structural_funnel")
    if embudo:
        historia.append(Spacer(1, 0.3 * cm))
        historia.append(parrafo("<b>Embudo estructural</b>"))
        veredictos = embudo["physical_verdicts"]
        selector = embudo["selector_states"]
        total = embudo["input_rows"]

        def _sobre_total(valor: int) -> str:
            """Cada escalón contra el archivo COMPLETO, no contra el anterior."""
            return f"{valor} de {total}" if total else str(valor)

        historia.append(_tabla(
            [
                ["Escalón", "Recuento (sobre el archivo)"],
                ["Entradas totales", str(total)],
                ["Válidas (elegibles)", _sobre_total(embudo["eligible_rows"])],
                ["Ejecutadas", _sobre_total(embudo["executed_rows"])],
                ["Con poses", _sobre_total(embudo["rows_with_poses"])],
                ["Seleccionables (≥2 poses)", _sobre_total(embudo["selectable_rows"])],
                ["Físicamente evaluadas", _sobre_total(embudo["physically_evaluated_rows"])],
                ["  · controles superados", str(veredictos["passed"])],
                ["  · controles fallidos", str(veredictos["failed"])],
                ["  · requieren revisión", str(veredictos["review"])],
                ["  · no evaluadas", str(veredictos["not_evaluated"])],
                ["Selector: recomendó", str(selector["selected"])],
                ["Selector: se abstuvo", str(selector["abstained"])],
                ["Selector: no disponible", str(selector["unavailable"])],
                ["Selector: falló", str(selector["error"])],
            ],
            est, [7.0 * cm, 9.5 * cm],
        ))
        historia.append(parrafo(_escapar(embudo["note"])))
        historia.append(parrafo(
            "«Requiere revisión» significa que la batería no corrió entera: NO es una pose "
            "aprobada. Sólo «controles superados» autoriza llamar válida a una pose."
        ))

    # ── Exclusiones: ninguna fila desaparece del recuento ────────────
    exclusiones = cobertura.get("exclusions")
    if exclusiones and exclusiones.get("by_cause"):
        historia.append(Spacer(1, 0.3 * cm))
        historia.append(parrafo("<b>Exclusiones y sus causas</b>"))
        filas_ex = [["Causa", "Filas"]]
        for causa, cuenta in exclusiones["by_cause"].items():
            filas_ex.append([_escapar(str(causa)), str(cuenta)])
        filas_ex.append(["TOTAL EXCLUIDAS", str(exclusiones["total"])])
        historia.append(_tabla(filas_ex, est, [11.0 * cm, 5.5 * cm]))
        historia.append(parrafo(
            "Se declaran una a una. Una molécula que no llegó al final no desaparece del "
            "informe: un recuento que sólo hablara de lo que salió bien no sería una cobertura."
        ))

    # ── 5. Tabla de evidencia ────────────────────────────────────────
    seccion("5 · Evidencia por molécula")
    moleculas = evidencia["molecules"]
    historia.append(parrafo(
        f"{len(moleculas)} fila(s) de trabajo. La columna es la afinidad Vina observada: "
        "una señal de ranking dentro de este protocolo, no una medida de energía libre "
        "ni una probabilidad de actividad."
    ))
    if len(moleculas) > MAX_PDF_ROWS:
        historia.append(parrafo(
            f"Se imprimen las primeras {MAX_PDF_ROWS}. El paquete ZIP lleva `rows.csv` "
            "con todas."
        ))
    historia.append(Spacer(1, 0.2 * cm))
    filas_pdf = [["#", "Nombre", "Estado", "Afinidad Vina obs. (kcal/mol)", "Etiq.", "Control"]]
    for entrada in moleculas[:MAX_PDF_ROWS]:
        afinidad = entrada["observed_vina_affinity_kcal_mol"]
        filas_pdf.append([
            str(entrada["source_row_index"]),
            _escapar(entrada["source_name"] or "—"),
            entrada["status"],
            f"{afinidad:.2f}" if afinidad is not None else "NO DISPONIBLE",
            {True: "activa", False: "inactiva", None: "—"}[entrada["active_label"]],
            entrada["control_role"],
        ])
    historia.append(_tabla(filas_pdf, est, [1.2 * cm, 5.0 * cm, 3.2 * cm, 3.6 * cm, 1.7 * cm, 1.8 * cm]))

    # ── 6. Controles ─────────────────────────────────────────────────
    seccion("6 · Controles declarados")
    controles = metricas.get("controls") or []
    if controles:
        filas_c = [["#", "Nombre", "Papel", "Etiqueta", "Afinidad Vina obs."]]
        for c in controles:
            afinidad = c["observed_vina_affinity_kcal_mol"]
            filas_c.append([
                str(c["source_row_index"]),
                _escapar(c["source_name"] or "—"),
                c["control_role"],
                {True: "activa", False: "inactiva", None: "—"}[c["active_label"]],
                f"{afinidad:.2f}" if afinidad is not None else "NO DISPONIBLE",
            ])
        historia.append(_tabla(filas_c, est, [1.2 * cm, 5.5 * cm, 3.0 * cm, 2.5 * cm, 4.3 * cm]))
        historia.append(parrafo(
            "Los controles se reportan aparte y NO entran en la población de las métricas: "
            "un control positivo dentro de la población sube el enriquecimiento sin decir "
            "nada sobre la cohorte."
        ))
    else:
        historia.append(parrafo(
            "NINGÚN control declarado. No se ha inferido ninguno a partir de nombres, "
            "etiquetas ni posiciones. Sin control, el resultado de esta cohorte no tiene "
            "contra qué contrastarse."
        ))

    # ── 7. Métricas ──────────────────────────────────────────────────
    seccion("7 · Métricas etiquetadas")
    if metricas["status"] == "evaluated":
        filas_m = [["Métrica", "Valor", "n"]]
        filas_m.append(["ROC-AUC", f"{metricas['roc_auc']:.4f}", str(metricas["n_total"])])
        for ef in metricas["enrichment_factors"]:
            valor = ef["value"]
            filas_m.append([
                f"EF@{int(ef['fraction'] * 100)}%",
                f"{valor:.3f}" if valor is not None else "NO DISPONIBLE",
                f"{ef['n_actives_selected']}/{ef['n_selected']}",
            ])
        historia.append(_tabla(filas_m, est, [5.0 * cm, 6.0 * cm, 5.5 * cm]))
        historia.append(parrafo(
            f"Población: {metricas['n_total']} moléculas canónicas etiquetadas "
            f"({metricas['n_positive']} activas, {metricas['n_negative']} inactivas), "
            f"cobertura {metricas['coverage']}."
        ))
        historia.append(parrafo(metricas["interpretation_limit"]))
    else:
        historia.append(parrafo(
            f"NO EVALUADAS · {metricas['reason_code']}: {metricas['reason']}"
        ))
        historia.append(parrafo(
            "Una métrica calculada sin cumplir sus condiciones no es una métrica "
            "aproximada: es un número que parece un resultado."
        ))

    # ── 8. Incertidumbres y límites ──────────────────────────────────
    seccion("8 · Qué puede y qué NO puede concluirse")
    historia.append(parrafo("PUEDE concluirse:"))
    for texto in [
        "Que estas moléculas se acoplaron contra este receptor con esta configuración.",
        "Qué proporción de la cohorte llegó a producir un resultado, y qué quedó fuera.",
        "Que dos corridas con la misma huella describen el mismo cálculo.",
    ]:
        historia.append(parrafo(f"· {texto}"))
    historia.append(Spacer(1, 0.2 * cm))
    historia.append(parrafo("NO puede concluirse:"))
    for texto in evidencia["limits"]:
        historia.append(parrafo(f"· {texto}"))

    # ── 9. Próximos pasos ────────────────────────────────────────────
    seccion("9 · Próximos pasos justificables")
    for texto in [
        "Revisar geométricamente las poses de las moléculas con mejor afinidad observada "
        "antes de atribuirles cualquier significado.",
        "Ejecutar un control de re-acoplamiento del ligando cristalográfico si el receptor "
        "lo tiene, para saber si el protocolo recupera una pose conocida.",
        "Repetir la cohorte con otra semilla y comparar el orden: si cambia, el orden no "
        "era estable.",
        "Ampliar los controles declarados. Una cohorte sin referencia no se puede "
        "interpretar aunque sus números sean buenos.",
    ]:
        historia.append(parrafo(f"· {texto}"))
    historia.append(parrafo(
        "Ninguno de estos pasos recomienda un fármaco, un candidato clínico ni un "
        "compuesto seguro. Describen qué trabajo computacional queda justificado."
    ))

    # ── 10. Procedencia ──────────────────────────────────────────────
    seccion("10 · Procedencia")
    procedencia = evidencia["provenance"]
    cohorte_prov = procedencia.get("cohort") or {}
    historia.append(_tabla(
        [
            ["Campo", "Valor"],
            ["Contrato de preflight", str(cohorte_prov.get("preflight_contract_version", "—"))],
            ["Contrato de fingerprint", str(cohorte_prov.get("fingerprint_contract", "—"))],
            ["Contrato de ejecución", str(procedencia.get("execution_contract", "—"))],
            ["Contrato de evidencia", str(procedencia.get("evidence_contract", "—"))],
            ["Versión de MolDesign", str(cohorte_prov.get("moldesign_version") or "NO DISPONIBLE")],
            ["Versión de RDKit", str(cohorte_prov.get("rdkit_version") or "NO DISPONIBLE")],
            ["Etapas ejecutadas", ", ".join(procedencia.get("stages") or [])],
        ],
        est, [5.5 * cm, 11.0 * cm],
    ))

    doc.build(historia, canvasmaker=_Chrome)
    buffer.seek(0)
    return buffer


# ── ZIP ──────────────────────────────────────────────────────────────


def _rows_csv(moleculas: list[dict[str, Any]]) -> bytes:
    salida = io.StringIO(newline="")
    campos = [
        "source_row_index", "source_name", "canonical_smiles", "status",
        "observed_vina_affinity_kcal_mol", "molecule_id", "result_id",
        "active_label", "control_role", "duplicate_of_row", "reused_from_row",
        "error_code",
    ]
    escritor = csv.DictWriter(salida, fieldnames=campos, extrasaction="ignore", lineterminator="\n")
    escritor.writeheader()
    for entrada in moleculas:
        escritor.writerow({campo: entrada.get(campo) for campo in campos})
    return salida.getvalue().encode("utf-8")


def _readme_cohorte(evidencia: dict[str, Any], raiz: str) -> bytes:
    cobertura = evidencia["coverage"]
    metricas = evidencia["labeled_metrics"]
    estado_metricas = (
        "evaluadas"
        if metricas["status"] == "evaluated"
        else f"NO EVALUADAS ({metricas['reason_code']})"
    )
    return f"""# Paquete reproducible de cohorte · {evidencia['cohort_name']}

Paquete: `{raiz}`
Corrida: `{evidencia['run_id']}`  ·  estado: `{evidencia['run_status']}`
Huella de cohorte: `{evidencia['cohort_fingerprint']}`
Huella de corrida: `{evidencia['run_fingerprint']}`

## Qué es esto

La contraparte verificable de `dossier.pdf`. Permite comprobar que la lectura
del PDF se hizo sobre estos archivos y no sobre otros.

## Cómo verificarlo

```
python scripts/verify_dossier_package.py <este-archivo>.zip
```

Es el MISMO verificador que valida los paquetes de caso: un solo protocolo de
manifiesto y checksums para todo el producto.

Si el resultado no es `VÁLIDO`, no uses el contenido: el paquete no describe lo
que dice describir.

## Los tres ciclos de hash

- el ZIP no se contiene a sí mismo;
- `checksums.sha256` no se hashea a sí mismo;
- `manifest.json` no se declara a sí mismo dentro de `files` — su integridad la
  cubre `checksums.sha256`, que se calcula después.

## Qué hay dentro

- `dossier.pdf` — la lectura humana.
- `cohort.json` — la cohorte congelada (definición normalizada y procedencia).
- `preflight.json` — el veredicto de comprobación previa, con TODAS las filas.
- `run.json` — la corrida: configuración efectiva, receptor, estado, contadores.
- `evidence.json` — este resumen científico completo.
- `rows.csv` — una línea por fila de trabajo.
- `inputs/` — el archivo original tal como se subió, y el receptor preparado.
- `manifest.json` · `checksums.sha256`

Los artefactos que NO estaban disponibles aparecen en el manifiesto con estado
`{Estado.NO_DISPONIBLE.value}` y su razón. No se omiten y no se fabrican.

## Cobertura

- Filas en el archivo: {cobertura['source_rows']}
- Elegibles: {cobertura['eligible_rows']}
- Moléculas únicas acopladas: {cobertura['unique_molecules_executed']}
- Completadas: {cobertura['completed_rows']} · fallidas: {cobertura['failed_rows']} ·
  no evaluadas: {cobertura['not_evaluated_rows']} · duplicados reutilizados:
  {cobertura['duplicate_reused_rows']}
- Métricas etiquetadas: {estado_metricas}

## Qué NO garantiza

- No garantiza validez científica. Completar un acoplamiento no demuestra
  actividad.
- No contiene ranking de candidatos ni puntuación agregada.
- No garantiza reproducibilidad bit a bit: eso depende de la versión del motor y
  del hardware.
""".encode("utf-8")


def construir_paquete_cohorte(
    *,
    evidencia: dict[str, Any],
    pdf_bytes: bytes,
    cohort: Any,
    run: Any,
    artefactos: list[ArchivoPaquete] | None = None,
) -> tuple[bytes, list[Any], str]:
    """
    Arma el ZIP de la cohorte sobre el núcleo compartido.

    Decide QUÉ va dentro; el CÓMO —manifiesto, checksums, escritura
    determinista— lo pone `empaquetar`, el mismo que usa el dossier de caso.
    """
    raiz = raiz_paquete_cohorte(cohort.name, run.id)

    archivos: list[ArchivoPaquete] = [
        ArchivoPaquete("dossier.pdf", pdf_bytes, "lectura_humana",
                       "application/pdf", "services.cohort.dossier"),
        ArchivoPaquete("cohort.json", _json_canonico({
            "id": str(cohort.id),
            "name": cohort.name,
            "status": cohort.status,
            "schema_version": cohort.schema_version,
            "cohort_fingerprint": cohort.cohort_fingerprint,
            "normalized_study": cohort.normalized_study_json,
            "provenance": cohort.provenance_json,
            "source": {
                "filename": cohort.source_filename,
                "content_type": cohort.source_content_type,
                "sha256": cohort.source_sha256,
                "size_bytes": cohort.source_size_bytes,
            },
        }), "cohorte", "application/json", "core.models.CohortORM"),
        ArchivoPaquete("preflight.json", _json_canonico(cohort.preflight_snapshot_json),
                       "comprobacion_previa", "application/json",
                       "cohorts.preflight_snapshot_json"),
        ArchivoPaquete("run.json", _json_canonico({
            "id": str(run.id),
            "status": run.status,
            "cohort_fingerprint": run.cohort_fingerprint,
            "run_fingerprint": run.run_fingerprint,
            "effective_config": run.effective_config_json,
            "receptor_provenance": run.receptor_provenance_json,
            "total_rows": run.total_rows,
            "eligible_rows": run.eligible_rows,
            "completed_rows": run.completed_rows,
            "failed_rows": run.failed_rows,
            "not_evaluated_rows": run.not_evaluated_rows,
            "created_at": str(run.created_at) if run.created_at else None,
            "started_at": str(run.started_at) if run.started_at else None,
            "finished_at": str(run.finished_at) if run.finished_at else None,
            "last_error": run.last_error,
        }), "corrida", "application/json", "core.models.CohortRunORM"),
        ArchivoPaquete("evidence.json", _json_canonico(evidencia),
                       "evidencia", "application/json", "services.cohort.evidence"),
        ArchivoPaquete("rows.csv", _rows_csv(evidencia["molecules"]),
                       "evidencia", "text/csv", "services.cohort.evidence"),
    ]

    # ── El archivo original, tal como se subió ───────────────────────
    fuente = bytes(cohort.source_bytes) if cohort.source_bytes else None
    archivos.append(ArchivoPaquete(
        path=f"inputs/{sanitizar(cohort.source_filename, maximo=80)}",
        datos=fuente,
        rol="inputs",
        media_type=cohort.source_content_type or "application/octet-stream",
        fuente="cohorts.source_bytes",
        estado=Estado.REGISTRADO.value if fuente else Estado.NO_DISPONIBLE.value,
        razon=None if fuente else "La cohorte no conserva el archivo original.",
    ))

    # ── El receptor preparado CONGELADO ─────────────────────────────
    # Los bytes vienen de la corrida, no del disco: el `.pdbqt` del catálogo es
    # mutable y podría haberse repreparado desde entonces. El SHA-256 del
    # manifiesto tiene que coincidir con el que la corrida congeló.
    receptor_bytes = bytes(run.receptor_prepared_bytes) if run.receptor_prepared_bytes else None
    archivos.append(ArchivoPaquete(
        path="inputs/receptor_prepared.pdbqt",
        datos=receptor_bytes,
        rol="inputs",
        media_type="chemical/x-pdbqt",
        fuente="cohort_runs.receptor_prepared_bytes",
        estado=Estado.REGISTRADO.value if receptor_bytes else Estado.NO_DISPONIBLE.value,
        razon=None if receptor_bytes else (
            "Esta corrida es anterior al congelado del receptor y no conserva sus bytes. "
            "No se sustituye por el archivo del catálogo: podría haberse repreparado."
        ),
    ))

    archivos.extend(artefactos or [])
    archivos.append(ArchivoPaquete(
        "README.md", _readme_cohorte(evidencia, raiz), "lectura_humana",
        "text/markdown", "services.cohort.dossier",
    ))

    return empaquetar(
        raiz=raiz,
        archivos=archivos,
        manifiesto_extra={
            "cohort_dossier_contract": COHORT_DOSSIER_CONTRACT,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "cohort_id": str(cohort.id),
            "run_id": str(run.id),
            "cohort_fingerprint": run.cohort_fingerprint,
            "run_fingerprint": run.run_fingerprint,
        },
    )
