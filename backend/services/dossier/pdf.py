"""
Render del dossier a PDF. Determinista y derivado del modelo canónico.

# Qué NO hace, y por qué importa

- **No consulta la red.** Ni PubChem, ni Ollama, ni proveedores. Un documento de
  evidencia no puede depender de que un tercero conteste, ni filtrar el SMILES
  del usuario a un servicio externo al imprimirlo.
- **No calcula nada científico.** Recibe `CaseDossier` ya interpretado. Si el
  renderizador pudiera decidir qué es «pasa», habría dos interpretaciones de la
  misma corrida y el paquete verificable dejaría de coincidir con el PDF.
- **No pone un score en la jerarquía principal.** Los índices 0-100 aparecen una
  sola vez, en el apéndice heredado, con su advertencia. No hay portada con
  nota, ni resumen con nota, ni «GLOBAL SCORE».

# Composición

Se usa `platypus` con un `SimpleDocTemplate`: el flujo decide los saltos de
página, que es lo que evita el defecto clásico de los PDF dibujados a mano —
texto que se sale del margen inferior cuando el contexto del usuario es largo.
Los encabezados van con `KeepTogether` junto a su primer bloque para que no
queden huérfanos al final de una página.
"""

from __future__ import annotations

import io
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from services.dossier.model import CaseDossier, Campo, Control
from services.dossier.taxonomy import ETIQUETA, GLOSARIO, Estado

# ── Tokens de presentación ───────────────────────────────────────────
INK = colors.HexColor("#0f172a")
SLATE = colors.HexColor("#475569")
SLATE_LT = colors.HexColor("#94a3b8")
LINE = colors.HexColor("#e2e8f0")
HEAD_BG = colors.HexColor("#f1f5f9")
BRAND = colors.HexColor("#1e40af")

#: Color por estado. Deliberadamente sobrio: `PASA` no es verde brillante
#: porque el documento no celebra resultados, los declara.
COLOR_ESTADO: dict[Estado, colors.Color] = {
    Estado.PASA: colors.HexColor("#15803d"),
    Estado.REGISTRADO: colors.HexColor("#334155"),
    Estado.REVISAR: colors.HexColor("#b45309"),
    Estado.ABSTENCION: colors.HexColor("#b91c1c"),
    Estado.NO_EVALUADO: colors.HexColor("#64748b"),
    Estado.NO_DISPONIBLE: colors.HexColor("#64748b"),
    Estado.NO_DEFINIDO: colors.HexColor("#94a3b8"),
    Estado.NO_APLICA: colors.HexColor("#94a3b8"),
}

_ANCHO_UTIL = A4[0] - 3.6 * cm  # márgenes de 1.8 cm a cada lado


def _escapar(texto: Any) -> str:
    """
    Escapa para `Paragraph`, que interpreta un subconjunto de XML.

    Sin esto, un SMILES con `<` o un nombre con `&` rompe el render o, peor,
    desaparece del documento sin avisar.
    """
    if texto is None:
        return ""
    return (
        str(texto)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _romper_largo(texto: str) -> str:
    """
    Deja que reportlab parta las cadenas largas por su cuenta.

    La versión anterior insertaba U+200B (espacio de ancho cero) cada 60
    caracteres para partir hashes y SMILES. Helvetica no tiene glifo para ese
    carácter, así que el PDF lo pintaba como un **cuadrado negro** en mitad del
    SHA-256 — visible en el QA de la página 1. Un carácter invisible en el
    editor y sólido en el papel es la peor clase de defecto tipográfico.

    `Paragraph` ya parte palabras que no caben (`splitLongWords`, activo por
    defecto). No hace falta ayudarle, y ayudarle rompía el documento.
    """
    return texto or ""


class _Chrome(pdfcanvas.Canvas):
    """Encabezado, pie y numeración «página N de M»."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._paginas: list[dict[str, Any]] = []
        self.encabezado = ""

    def showPage(self) -> None:  # noqa: N802 (API de reportlab)
        self._paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total = len(self._paginas)
        for estado in self._paginas:
            self.__dict__.update(estado)
            self._dibujar_chrome(total)
            super().showPage()
        super().save()

    def _dibujar_chrome(self, total: int) -> None:
        self.saveState()
        self.setFillColor(BRAND)
        self.rect(0, A4[1] - 0.18 * cm, A4[0], 0.18 * cm, stroke=0, fill=1)

        self.setFont("Helvetica", 7)
        self.setFillColor(SLATE_LT)
        self.drawString(1.8 * cm, A4[1] - 0.85 * cm, self.encabezado)
        self.drawRightString(
            A4[0] - 1.8 * cm, 1.0 * cm, f"Página {self._pageNumber} de {total}"
        )
        self.drawString(
            1.8 * cm, 1.0 * cm,
            "MolDesign · dossier de evidencia computacional · no es una recomendación clínica",
        )
        self.restoreState()


def _estilos() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle(
            "DossierTitulo", parent=base["Heading1"], fontSize=17, leading=21,
            textColor=BRAND, spaceAfter=2, alignment=TA_LEFT,
        ),
        "subtitulo": ParagraphStyle(
            "DossierSubtitulo", parent=base["Normal"], fontSize=10, leading=13,
            textColor=SLATE, spaceAfter=10,
        ),
        "seccion": ParagraphStyle(
            "DossierSeccion", parent=base["Heading2"], fontSize=11.5, leading=14,
            textColor=BRAND, spaceBefore=12, spaceAfter=5,
        ),
        "cuerpo": ParagraphStyle(
            "DossierCuerpo", parent=base["Normal"], fontSize=8.6, leading=11.6,
            textColor=INK, spaceAfter=3,
        ),
        "nota": ParagraphStyle(
            "DossierNota", parent=base["Normal"], fontSize=7.6, leading=10,
            textColor=SLATE, spaceAfter=2,
        ),
        "celda": ParagraphStyle(
            "DossierCelda", parent=base["Normal"], fontSize=8.2, leading=10.6, textColor=INK,
        ),
        "celda_nota": ParagraphStyle(
            "DossierCeldaNota", parent=base["Normal"], fontSize=7.4, leading=9.6, textColor=SLATE,
        ),
        "mono": ParagraphStyle(
            "DossierMono", parent=base["Normal"], fontName="Courier", fontSize=7.4,
            leading=9.4, textColor=INK,
        ),
    }


def _tabla_campos(campos: list[Campo], est: dict[str, ParagraphStyle]) -> Table:
    """
    Tabla etiqueta / valor / estado.

    Celdas con `Paragraph` para que una fila larga se parta entre páginas sin
    recortar texto, y `repeatRows=1` para que la cabecera viaje con ella. Los
    anchos son fijos: dejarlos automáticos hacía que una etiqueta larga
    empujara el valor fuera del margen.
    """
    filas = [[
        Paragraph("<b>Campo</b>", est["celda"]),
        Paragraph("<b>Contenido</b>", est["celda"]),
        Paragraph("<b>Estado</b>", est["celda"]),
    ]]
    estilos_fila = []
    for indice, campo in enumerate(campos, start=1):
        cuerpo = _escapar(_romper_largo(campo.texto))
        # La razón sólo se añade si DICE algo distinto del valor. Repetir la
        # misma frase dos veces seguidas es ruido, y aparecía en la fila de
        # «relación de la corrida con los inputs».
        if campo.razon and campo.razon.strip() != (campo.valor or "").strip():
            cuerpo += f"<br/><font size='7' color='#64748b'>{_escapar(campo.razon)}</font>"
        filas.append([
            Paragraph(_escapar(campo.etiqueta), est["celda"]),
            Paragraph(cuerpo, est["celda"]),
            Paragraph(ETIQUETA[campo.estado], est["celda_nota"]),
        ])
        estilos_fila.append(("TEXTCOLOR", (2, indice), (2, indice), COLOR_ESTADO[campo.estado]))

    # `repeatRows=1`: si la tabla se parte entre páginas, la cabecera se repite.
    # Sin esto, la segunda mitad quedaba sin decir qué era cada columna.
    tabla = Table(filas, colWidths=[_ANCHO_UTIL * 0.28, _ANCHO_UTIL * 0.55, _ANCHO_UTIL * 0.17],
                  repeatRows=1)
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEAD_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), INK),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        *estilos_fila,
    ]))
    return tabla


def _tabla_controles(controles: list[Control], est: dict[str, ParagraphStyle]) -> Table:
    filas = [[
        Paragraph("<b>Control</b>", est["celda"]),
        Paragraph("<b>Observación y protocolo</b>", est["celda"]),
        Paragraph("<b>Estado</b>", est["celda"]),
    ]]
    estilos_fila = []
    for indice, control in enumerate(controles, start=1):
        cuerpo = _escapar(control.observacion)
        if control.protocolo:
            cuerpo += f"<br/><font size='7' color='#64748b'>Protocolo: {_escapar(control.protocolo)}</font>"
        if control.procedencia:
            cuerpo += f"<br/><font size='7' color='#94a3b8'>Procedencia: {_escapar(control.procedencia)}</font>"
        filas.append([
            Paragraph(f"{_escapar(control.titulo)}<br/><font size='6.6' color='#94a3b8'>{_escapar(control.codigo)}</font>", est["celda"]),
            Paragraph(cuerpo, est["celda"]),
            Paragraph(ETIQUETA[control.estado], est["celda_nota"]),
        ])
        estilos_fila.append(("TEXTCOLOR", (2, indice), (2, indice), COLOR_ESTADO[control.estado]))

    tabla = Table(filas, colWidths=[_ANCHO_UTIL * 0.26, _ANCHO_UTIL * 0.57, _ANCHO_UTIL * 0.17],
                  repeatRows=1)
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEAD_BG),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        *estilos_fila,
    ]))
    return tabla


def _tabla_poses_evidencia(evidencia: list[Any], est: dict[str, ParagraphStyle]) -> Table:
    """
    Una fila por pose: afinidad, veredicto físico, selector y papel.

    Los papeles se imprimen JUNTOS y no se colapsan en una etiqueta: la top-1 de
    Vina puede ser además una alternativa válida, y la pose sugerida puede ser
    la que falla. Colapsarlos escondería justo la combinación que hay que ver.
    """
    filas = [[
        Paragraph("<b>Pose</b>", est["celda"]),
        Paragraph("<b>Afinidad Vina (kcal/mol)</b>", est["celda"]),
        Paragraph("<b>Controles físicos</b>", est["celda"]),
        Paragraph("<b>Selector</b>", est["celda"]),
        Paragraph("<b>Papel</b>", est["celda"]),
        Paragraph("<b>Controles que fallan</b>", est["celda"]),
    ]]
    for pose in evidencia:
        papeles = []
        if pose.es_vina_top1:
            papeles.append("Vina top-1")
        if pose.es_sugerida:
            papeles.append("Sugerida")
        if pose.es_alternativa:
            papeles.append("Alternativa válida")
        filas.append([
            Paragraph(f"#{pose.rango}" if pose.rango is not None else "—", est["celda"]),
            Paragraph(f"{pose.afinidad_kcal_mol:.2f}" if pose.afinidad_kcal_mol is not None
                      else ETIQUETA[Estado.NO_DISPONIBLE], est["celda"]),
            Paragraph(ETIQUETA[pose.estado_fisico], est["celda"]),
            Paragraph(f"{pose.puntuacion_selector:.4f}" if pose.puntuacion_selector is not None
                      else "—", est["celda"]),
            Paragraph(_escapar(" · ".join(papeles)) if papeles else "—", est["celda"]),
            Paragraph(_romper_largo(_escapar(", ".join(pose.checks_que_fallan)))
                      if pose.checks_que_fallan else "—", est["celda"]),
        ])
    tabla = Table(filas, colWidths=[_ANCHO_UTIL * 0.08, _ANCHO_UTIL * 0.17,
                                    _ANCHO_UTIL * 0.19, _ANCHO_UTIL * 0.11,
                                    _ANCHO_UTIL * 0.20, _ANCHO_UTIL * 0.25],
                  repeatRows=1)
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEAD_BG),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return tabla


def _seccion(titulo: str, est: dict[str, ParagraphStyle], *cuerpo: Any) -> list[Any]:
    """
    Encabezado unido a su primer bloque.

    Sin `KeepTogether`, un título podía quedarse solo al pie de una página con
    su tabla en la siguiente: el defecto de «encabezado huérfano» que el QA
    visual busca.
    """
    partes: list[Any] = [KeepTogether([Paragraph(titulo, est["seccion"]), *list(cuerpo)[:1]])]
    partes.extend(list(cuerpo)[1:])
    return partes


def render_dossier_pdf(dossier: CaseDossier) -> io.BytesIO:
    """Convierte el modelo canónico en PDF. Sin red, sin cálculo, sin estado."""
    est = _estilos()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.8 * cm, rightMargin=1.8 * cm,
        topMargin=1.5 * cm, bottomMargin=1.6 * cm,
        title=f"Dossier · {dossier.case_name}",
        author="MolDesign",
        subject="Dossier de evidencia computacional",
        # DETERMINISMO. Sin `invariant`, reportlab escribe `/CreationDate` con la
        # hora real y un `/ID` aleatorio en el tráiler, así que dos PDF del mismo
        # caso difieren byte a byte. Eso propagaba la diferencia al hash del
        # manifiesto y hacía que el paquete NO fuera reproducible — el
        # verificador no podría distinguir un cambio real de dos exportaciones.
        # La fecha del documento vive en el modelo (`generated_at`), no en los
        # metadatos del PDF.
        invariant=1,
    )
    flujo: list[Any] = []

    # ── 1. Portada ───────────────────────────────────────────────────
    flujo.append(Paragraph("DOSSIER DE EVIDENCIA COMPUTACIONAL", est["titulo"]))
    flujo.append(Paragraph(
        "Este documento describe qué evidencia produjo una corrida, qué partes son "
        "reproducibles y qué quedó sin evaluar. No califica la molécula ni afirma que sea "
        "un fármaco, un candidato clínico ni un compuesto seguro.",
        est["subtitulo"],
    ))
    flujo.append(_tabla_campos(dossier.portada, est))

    if dossier.avisos_integridad:
        flujo.append(Spacer(1, 6))
        for aviso in dossier.avisos_integridad:
            flujo.append(Paragraph(
                f"<b>Aviso de integridad:</b> {_escapar(aviso)}", est["cuerpo"]))

    # ── 2. Pregunta y propósito ──────────────────────────────────────
    flujo.extend(_seccion("1. Pregunta y propósito del caso", est,
                          _tabla_campos(dossier.proposito, est)))

    # ── 3. Resumen de lo ejecutado ───────────────────────────────────
    flujo.extend(_seccion(
        "2. Resumen de lo ejecutado", est,
        _tabla_campos(
            [dossier.ejecucion["tecnico"], dossier.ejecucion["cientifico"], dossier.ejecucion["humano"]],
            est,
        ),
        Paragraph(
            "El estado técnico, la disposición científica y la revisión humana son tres cosas "
            "distintas. Que un proceso termine no valida su resultado, y que no haya alertas no "
            "significa que alguien lo haya revisado.",
            est["nota"],
        ),
    ))

    # ── 4. Entradas y procedencia ────────────────────────────────────
    flujo.extend(_seccion("3. Entradas y procedencia", est,
                          _tabla_campos(dossier.entradas, est)))

    hashes = [
        Campo("Hash del ligando (SMILES)", dossier.procedencia.get("ligando_smiles_sha256"),
              Estado.REGISTRADO if dossier.procedencia.get("ligando_smiles_sha256") else Estado.NO_DISPONIBLE,
              None if dossier.procedencia.get("ligando_smiles_sha256") else "La corrida no selló el ligando."),
        Campo("Referencia del receptor", dossier.procedencia.get("receptor_referencia"),
              Estado.REGISTRADO if dossier.procedencia.get("receptor_referencia") else Estado.NO_DISPONIBLE,
              None if dossier.procedencia.get("receptor_referencia") else "Sin referencia de receptor."),
        Campo("Hash de la configuración", dossier.procedencia.get("configuracion_sha256"),
              Estado.REGISTRADO if dossier.procedencia.get("configuracion_sha256") else Estado.NO_DISPONIBLE,
              None if dossier.procedencia.get("configuracion_sha256") else "Sin configuración sellada."),
        Campo("Hash de las poses", dossier.procedencia.get("poses_sha256"),
              Estado.REGISTRADO if dossier.procedencia.get("poses_sha256") else Estado.NO_DISPONIBLE,
              None if dossier.procedencia.get("poses_sha256") else
              "La corrida no serializó bloques de pose que sellar."),
    ]
    # La tabla de hashes es corta: se mantiene entera. Sin esto, su cabecera
    # quedaba sola al pie de la página 1 y las filas empezaban en la 2.
    flujo.append(KeepTogether([Spacer(1, 6), _tabla_campos(hashes, est)]))

    # ── 5. Preparación y supuestos ───────────────────────────────────
    flujo.extend(_seccion("4. Preparación del sistema y supuestos", est,
                          _tabla_campos(dossier.preparacion, est)))

    if dossier.decisiones:
        filas = [[
            Paragraph("<b>Control</b>", est["celda"]),
            Paragraph("<b>Decisión</b>", est["celda"]),
            Paragraph("<b>Aplica a los inputs actuales</b>", est["celda"]),
        ]]
        for decision in dossier.decisiones:
            nota = f"<br/><font size='7' color='#64748b'>{_escapar(decision.get('nota'))}</font>" if decision.get("nota") else ""
            filas.append([
                Paragraph(_escapar(decision["control"]), est["celda"]),
                Paragraph(f"{_escapar(decision['decision'])} · {_escapar(decision.get('fecha'))}{nota}", est["celda"]),
                Paragraph("Sí" if decision.get("aplica_a_los_inputs_actuales") else "No", est["celda_nota"]),
            ])
        tabla_dec = Table(filas, colWidths=[_ANCHO_UTIL * 0.3, _ANCHO_UTIL * 0.5, _ANCHO_UTIL * 0.2],
                          repeatRows=1)
        tabla_dec.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HEAD_BG),
            ("GRID", (0, 0), (-1, -1), 0.4, LINE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        flujo.append(Spacer(1, 6))
        flujo.append(Paragraph("Decisiones humanas registradas", est["cuerpo"]))
        flujo.append(tabla_dec)
    else:
        flujo.append(Spacer(1, 4))
        flujo.append(Paragraph(
            "<b>Decisiones humanas:</b> NO EVALUADO — nadie ha revisado ni reconocido controles "
            "de esta corrida.", est["cuerpo"]))

    # ── 6. Protocolo y entorno ───────────────────────────────────────
    flujo.extend(_seccion("5. Protocolo y entorno de ejecución", est,
                          _tabla_campos(dossier.protocolo, est)))

    # ── 7. Evidencia estructural ─────────────────────────────────────
    if dossier.poses:
        filas = [[
            Paragraph("<b>Rango</b>", est["celda"]),
            Paragraph("<b>Afinidad (kcal/mol)</b>", est["celda"]),
            Paragraph("<b>RMSD l.b.</b>", est["celda"]),
            Paragraph("<b>RMSD u.b.</b>", est["celda"]),
        ]]
        for pose in dossier.poses:
            filas.append([
                Paragraph(str(pose.rango), est["celda"]),
                Paragraph(f"{pose.afinidad_kcal_mol:.2f}" if pose.afinidad_kcal_mol is not None
                          else ETIQUETA[Estado.NO_DISPONIBLE], est["celda"]),
                Paragraph(f"{pose.rmsd_lb:.2f}" if isinstance(pose.rmsd_lb, (int, float)) else "—", est["celda"]),
                Paragraph(f"{pose.rmsd_ub:.2f}" if isinstance(pose.rmsd_ub, (int, float)) else "—", est["celda"]),
            ])
        tabla_poses = Table(filas, colWidths=[_ANCHO_UTIL * 0.14, _ANCHO_UTIL * 0.34,
                                              _ANCHO_UTIL * 0.26, _ANCHO_UTIL * 0.26],
                            repeatRows=1)
        tabla_poses.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HEAD_BG),
            ("GRID", (0, 0), (-1, -1), 0.4, LINE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        cuerpo_poses: list[Any] = [tabla_poses, Paragraph(
            "Las afinidades son señales de ranking dentro de este protocolo, no mediciones de "
            "energía libre. La pose de mejor energía no es, por serlo, la pose correcta: sin un "
            "control geométrico superado no hay evidencia estructural.",
            est["nota"],
        )]
    else:
        cuerpo_poses = [Paragraph(
            f"<b>{ETIQUETA[dossier.poses_estado]}</b> — {_escapar(dossier.poses_razon)}",
            est["cuerpo"])]
    flujo.extend(_seccion("6. Evidencia estructural y acoplamiento", est, *cuerpo_poses))

    # ── 7. Generación de poses ───────────────────────────────────────
    flujo.extend(_seccion(
        "7. Generación de poses", est,
        _tabla_campos(dossier.generacion, est),
        Paragraph(
            "Los parámetros que la corrida no persistió aparecen como NO EVALUADO con su razón. "
            "No se sustituyen por los de la configuración del caso: describirían un ajuste que "
            "nadie guardó con este resultado.",
            est["nota"]),
    ))

    # ── 8. Selección de pose ─────────────────────────────────────────
    flujo.extend(_seccion(
        "8. Selección de pose", est,
        _tabla_campos(dossier.seleccion, est),
        Paragraph(
            "El selector RECOMIENDA; no sustituye. La pose principal del producto sigue siendo "
            "la top-1 de Vina, que se conserva y se declara siempre. Cuando el selector se "
            "abstiene, falta o falla, la referencia es Vina top-1 en calidad de FALLBACK — no "
            "como un acierto del selector. El margen de confianza es la distancia entre la "
            "primera y la segunda pose según el modelo: no es una probabilidad ni una nota.",
            est["nota"]),
    ))

    # ── 9. Validación geométrica y física ────────────────────────────
    cuerpo_val: list[Any] = [_tabla_campos(dossier.validacion, est)]
    if dossier.evidencia_poses:
        cuerpo_val.append(Spacer(1, 0.25 * cm))
        cuerpo_val.append(Paragraph("<b>Veredicto por pose</b>", est["cuerpo"]))
        cuerpo_val.append(_tabla_poses_evidencia(dossier.evidencia_poses, est))
    else:
        cuerpo_val.append(Paragraph(
            f"<b>{ETIQUETA[Estado.NO_EVALUADO]}</b> — Esta corrida no registró veredicto físico "
            f"por pose.", est["cuerpo"]))
    cuerpo_val.append(Paragraph(
        "Sólo un CONTROL SUPERADO explícito autoriza llamar válida a una pose. REVISIÓN "
        "describe una batería que no corrió entera, y NO EVALUADO un validador que no corrió: "
        "las dos describen lo que le pasó a la comprobación, nunca a la molécula, y ninguna de "
        "las dos es evidencia negativa sobre el compuesto.",
        est["nota"]))
    flujo.extend(_seccion("9. Validación geométrica y física", est, *cuerpo_val))

    # ── 8. Controles físicos ─────────────────────────────────────────
    flujo.extend(_seccion("10. Controles físicos y geométricos", est,
                          _tabla_controles(dossier.controles, est),
                          Paragraph(
                              "La ausencia de alertas no equivale a validez: un control que no se "
                              "ejecutó aparece como NO EVALUADO y no autoriza ninguna conclusión.",
                              est["nota"])))

    # ── 9. Evidencia por dimensión ───────────────────────────────────
    # Deja que Platypus use el espacio restante. El salto forzado producía una
    # página casi vacía cuando los controles físicos eran breves.
    flujo.extend(_seccion("11. Evidencia por dimensión", est,
                          _tabla_controles(dossier.dimensiones, est)))

    # ── 10. Supuestos e incertidumbres ───────────────────────────────
    cuerpo_sup: list[Any] = []
    for texto in dossier.supuestos:
        cuerpo_sup.append(Paragraph(f"• {_escapar(texto)}", est["cuerpo"]))
    if not cuerpo_sup:
        cuerpo_sup.append(Paragraph(ETIQUETA[Estado.NO_DEFINIDO], est["cuerpo"]))
    flujo.extend(_seccion("12. Supuestos declarados", est, *cuerpo_sup))

    cuerpo_inc: list[Any] = []
    for texto in dossier.incertidumbres:
        cuerpo_inc.append(Paragraph(f"• {_escapar(texto)}", est["cuerpo"]))
    if not cuerpo_inc:
        cuerpo_inc.append(Paragraph(
            "No se registraron incertidumbres adicionales. Esto no significa que no existan.",
            est["cuerpo"]))
    flujo.extend(_seccion("13. Incertidumbres y limitaciones", est, *cuerpo_inc))

    # ── 11. Siguiente acción ─────────────────────────────────────────
    accion = dossier.siguiente_accion
    flujo.extend(_seccion(
        "14. Interpretación justificable y próximos pasos", est,
        Paragraph(f"<b>{_escapar(accion.texto)}</b>", est["cuerpo"]),
        Paragraph(_escapar(accion.razon or ""), est["cuerpo"]),
        Paragraph(
            "Ninguna acción de esta lista afirma que el compuesto sea un fármaco, un candidato "
            "clínico ni un compuesto seguro. Describen qué trabajo computacional queda "
            "justificado por la evidencia de esta corrida.",
            est["nota"]),
    ))

    # ── 12. Procedencia y manifiesto ─────────────────────────────────
    faltantes = dossier.procedencia.get("campos_ausentes") or []
    flujo.extend(_seccion(
        "15. Procedencia e instrucciones de verificación", est,
        Paragraph(
            "El paquete reproducible que acompaña a este dossier lleva un `manifest.json` con "
            "rol, tamaño y SHA-256 de cada archivo, y un `checksums.sha256` ordenado que permite "
            "detectar archivos ausentes, modificados o añadidos.",
            est["cuerpo"]),
        Paragraph(
            f"Campos de procedencia sin sellar en esta corrida: "
            f"{_escapar(', '.join(faltantes)) if faltantes else 'ninguno'}.",
            est["cuerpo"]),
        Paragraph(
            "<b>Cómo verificar el paquete, sin ejecutar nada:</b> (1) abrir el ZIP y leer "
            "`manifest.json`, que declara rol, tamaño y SHA-256 de cada archivo, incluidos los "
            "ausentes con su razón; (2) recalcular el SHA-256 de cada archivo y compararlo con "
            "`checksums.sha256`; (3) comprobar que no sobra ni falta ningún archivo respecto al "
            "manifiesto. El propio ZIP, `checksums.sha256` y la entrada de `manifest.json` "
            "dentro de `files` quedan fuera por construcción —un archivo no puede contener su "
            "propio hash—, y el README del paquete lo declara.",
            est["cuerpo"]),
        Paragraph(
            "Un checksum correcto demuestra INTEGRIDAD: que los bytes no cambiaron desde que se "
            "generó el paquete. No demuestra que el método sea adecuado, que la preparación "
            "fuera correcta ni que la conclusión sea cierta. Integridad no es validez "
            "científica, y este dossier no las presenta como lo mismo.",
            est["nota"]),
        Paragraph(_escapar(dossier.procedencia.get("nota", "")), est["nota"]),
    ))

    # ── 13. Glosario de estados ──────────────────────────────────────
    filas_glos = [[Paragraph("<b>Estado</b>", est["celda"]), Paragraph("<b>Significado</b>", est["celda"])]]
    for estado in Estado:
        filas_glos.append([
            Paragraph(ETIQUETA[estado], est["celda"]),
            Paragraph(_escapar(GLOSARIO[estado]), est["celda"]),
        ])
    tabla_glos = Table(filas_glos, colWidths=[_ANCHO_UTIL * 0.25, _ANCHO_UTIL * 0.75],
                       repeatRows=1)
    tabla_glos.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEAD_BG),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    flujo.extend(_seccion("16. Glosario de estados", est, tabla_glos))

    # ── 14. Apéndice heredado ────────────────────────────────────────
    cuerpo_ap: list[Any] = [Paragraph(
        "Los índices siguientes los calcula el pipeline por compatibilidad con lecturas "
        "anteriores. <b>No son decisionales.</b> No son probabilidad, ni confianza, ni calidad, "
        "y no deben usarse para comparar moléculas ni para priorizar trabajo experimental.",
        est["cuerpo"])]
    if dossier.apendice_heredado:
        cuerpo_ap.append(_tabla_campos(dossier.apendice_heredado, est))
    else:
        cuerpo_ap.append(Paragraph(
            "Esta corrida no serializó ningún índice heredado.", est["cuerpo"]))
    flujo.extend(_seccion("Apéndice A. Outputs heredados (no decisionales)", est, *cuerpo_ap))

    # El encabezado se compone al revés de lo intuitivo: el identificador de
    # corrida es lo ÚLTIMO que puede perderse, porque es la identidad del
    # documento. Antes se concatenaba caso + receptor + corrida y se recortaba
    # a 110 caracteres, lo que cortaba justo el identificador («corrida task-c»).
    # Ahora se recorta el nombre del caso y el receptor se cede entero.
    corrida = dossier.task_id or "sin identificador"
    espacio = 108 - len(corrida) - len(" · corrida ")
    caso = dossier.case_name
    if len(caso) > espacio:
        caso = caso[: max(0, espacio - 1)].rstrip() + "…"
    encabezado = f"{caso} · corrida {corrida}"

    def _con_chrome(*args: Any, **kwargs: Any) -> _Chrome:
        lienzo = _Chrome(*args, **kwargs)
        lienzo.encabezado = encabezado
        return lienzo

    doc.build(flujo, canvasmaker=_con_chrome)
    buf.seek(0)
    return buf
