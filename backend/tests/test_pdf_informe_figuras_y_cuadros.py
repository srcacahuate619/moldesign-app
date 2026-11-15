"""Grupo 1 de los arreglos de PDF (2026-11-11): identidad legible, sin cuadros y una sola definición de LE.

Salió de medir 58 PDF de 15 corridas en una cápsula real de la app (`.tmp/pdf-capsula-2026-11-12/MAPA-2.md`). Las tres cosas se
repetían en 14 de 14 corridas y ninguna prueba las veía, porque las pruebas de figuras sólo comprobaban que la función devolvía
una `Image`. Estas GENERAN el informe con la molécula real de la muestra y miran el PDF:

* F1 — la imagen 2D de la molécula, opaca, tapaba el hash y el SMILES (la tabla anidada medía 490 pt en una columna de 350) y se
  salía del margen de la hoja.
* B1 — un aviso heredado empieza con «⚠️» y la fuente del PDF no tiene ese glifo: salía como cuadros negros.
* B2 — el informe imprimía la LE con signo (−0,348) y el dossier, la magnitud (0,348): dos definiciones de la misma cifra.
"""
from __future__ import annotations

import importlib.util
import re
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("reportlab") is None or importlib.util.find_spec("pypdf") is None,
    reason="reportlab o pypdf no disponibles en este entorno",
)

IMATINIB = "Cc1ccc(NC(=O)c2ccc(CN3CCN(C)CC3)cc2)cc1Nc1nccc(-c2cccnc2)n1"
HASH = "b00b6dcc21c3bf4d9320aacc80832dcff54f2ebe6c71df7ce5a1d3c0d8e9f012"
AVISO_HEREDADO = (
    "⚠️ Molécula con 37 átomos pesados y 7 enlaces rotables — el docking puede tardar más de lo habitual. "
    "Si necesitas reducir el tiempo, revisa la caja y la exhaustividad de Vina; una búsqueda menor puede cambiar las poses."
)
MARGEN_PT = 42.5  # 1,5 cm: el margen que declara SimpleDocTemplate en pdf_generator


def _informe(smiles: str = IMATINIB, smiles_hash: str = HASH, afinidad: float = -12.875, pesados: int = 37,
             avisos: list | None = None, nombre: str | None = "Imatinib", pose_sdf: str | None = None,
             receptor_pdb: str | None = None, shap: dict | None = None, extra: dict | None = None,
             pdb_id: str = "1M17", nombre_receptor: str = "EGFR Kinase Domain",
             target_extra: dict | None = None) -> bytes:
    from core.models import EvaluationResultORM, MoleculeORM, TargetORM
    from services.blockchain import pdf_generator

    target = TargetORM(
        pdb_id=pdb_id, name=nombre_receptor, chain="A", grid_center_x=22.0, grid_center_y=0.3, grid_center_z=52.8,
        description="Receptor tirosina quinasa.", requires_cns=False, is_private=False, spearman_rho=0.0,
    )
    for clave, valor in (target_extra or {}).items():
        setattr(target, clave, valor)
    mol = MoleculeORM(smiles=smiles, name=nombre, smiles_hash=smiles_hash)
    mol.target = target
    resultado = EvaluationResultORM(
        molecule_id=uuid.uuid4(), affinity_kcal=afinidad, affinity_score=62.1, total_score=71.2, adme_score=68.0,
        druglikeness_score=70.0, gnn_score=0.5,
        docking_poses=[{"rank": 1, "affinity": afinidad, "rmsd_lb": 0.0, "rmsd_ub": 0.0},
                       {"rank": 2, "affinity": afinidad + 1.5, "rmsd_lb": 3.8, "rmsd_ub": 12.1}],
        parsing_source="sdf", vina_version="1.2.7", vina_random_seed=42,
        scientific_warnings=avisos if avisos is not None else [AVISO_HEREDADO], hotspots_hit=["ASP116"],
        molecular_weight=493.6, log_p=3.0, tpsa=86.3, hbd=2, hba=7, rotatable_bonds=7, heavy_atom_count=pesados, ring_count=5,
        lipinski_pass=True, veber_pass=True, qed=0.41, sa_score=2.4,
    )
    for clave, valor in (extra or {}).items():
        setattr(resultado, clave, valor)
    if shap is not None:
        resultado.shap_values = shap
        resultado.shap_output = "delta_pKi"
        resultado.shap_model_id = "ab" * 32
    buf = pdf_generator.generate_certificate_pdf(
        mol, resultado, target.name, pose_sdf_content=pose_sdf, receptor_pdb_content=receptor_pdb)
    return buf.getvalue()


def _texto(datos: bytes) -> str:
    import io

    import pypdf

    return "\n".join((p.extract_text() or "") for p in pypdf.PdfReader(io.BytesIO(datos)).pages)


# ── F1: la figura 2D no puede tapar el texto ni salirse de la hoja ───────────────────────────────


def test_ninguna_figura_tapa_texto_del_informe():
    from tests.pdf_geometria import paginas

    taparon = []
    for numero, pagina in enumerate(paginas(_informe()), start=1):
        for figura in pagina.figuras():
            if figura.con_alfa:
                continue  # sólo una imagen opaca tapa lo que tiene debajo
            for t in pagina.textos:
                if figura.caja.solapa(t.caja):
                    taparon.append((numero, t.texto.strip()[:50]))
    assert not taparon, f"una imagen opaca cubre texto: {taparon[:4]}"


def test_ninguna_figura_se_sale_del_margen_del_informe():
    from tests.pdf_geometria import paginas

    fuera = []
    for numero, pagina in enumerate(paginas(_informe()), start=1):
        for figura in pagina.figuras():
            c = figura.caja
            if c.x0 < MARGEN_PT - 0.5 or c.x1 > pagina.ancho - MARGEN_PT + 0.5:
                fuera.append((numero, round(c.x0), round(c.x1)))
    assert not fuera, f"figuras fuera del margen de {MARGEN_PT} pt (hoja de 595): {fuera}"


def test_el_smiles_y_el_hash_salen_enteros_en_el_informe():
    texto = re.sub(r"\s+", "", _texto(_informe()))
    assert IMATINIB in texto
    assert HASH in texto


def test_un_smiles_largo_tampoco_tapa_ni_sale():
    """Una molécula de 62 pesados: el SMILES ocupa varias líneas y el hash sigue visible."""
    from tests.pdf_geometria import paginas

    largo = "CC(C)C[C@H](NC(=O)[C@@H](Cc1ccccc1)NC(=O)c1cnccn1)C(=O)N[C@@H](Cc1ccccc1)C(=O)N[C@H](CC(C)C)C(=O)O"
    datos = _informe(smiles=largo, pesados=40)
    for numero, pagina in enumerate(paginas(datos), start=1):
        for figura in pagina.figuras():
            if figura.con_alfa:
                continue
            assert not [t for t in pagina.textos if figura.caja.solapa(t.caja)], f"p. {numero}: imagen sobre texto"
            assert figura.caja.x1 <= pagina.ancho - MARGEN_PT + 0.5
    assert re.sub(r"\s+", "", largo) in re.sub(r"\s+", "", _texto(datos))


# ── B1: el aviso heredado no deja cuadros ────────────────────────────────────────────────────────

CUADROS = ("■", "□", "▪", "\x00", "\x7f", "�", "⚠", "️")


def test_el_aviso_heredado_con_emoji_no_deja_cuadros_en_el_informe():
    texto = _texto(_informe())
    assert "Molécula con 37 átomos pesados" in texto, "el aviso tiene que seguir en el documento"
    sobrantes = [c for c in CUADROS if c in texto]
    assert not sobrantes, f"glifos que la fuente no tiene: {[hex(ord(c)) for c in sobrantes]}"
    assert not re.search(r"\bII\s+Molécula", texto), "los cuadros se extraen como «II»"


def test_el_aviso_heredado_con_emoji_no_deja_cuadros_en_el_dossier():
    from services.dossier.model import build_case_dossier
    from services.dossier.pdf import render_dossier_pdf
    from tests.fixtures_dossier import caso_completo

    caso = caso_completo()
    caso["eval_result"].scientific_warnings = [AVISO_HEREDADO]
    texto = _texto(render_dossier_pdf(build_case_dossier(**caso)).getvalue())
    assert "Molécula con 37 átomos pesados" in texto
    sobrantes = [c for c in CUADROS if c in texto]
    assert not sobrantes, f"glifos que la fuente no tiene: {[hex(ord(c)) for c in sobrantes]}"


# ── B2: una sola definición de LE ────────────────────────────────────────────────────────────────


def test_la_le_del_informe_es_la_magnitud_y_coincide_con_la_del_dossier():
    from scoring.eficiencia import calcular

    texto = _texto(_informe(afinidad=-12.875, pesados=37))
    m = re.search(r"Eficiencia de Ligando \(LE\)\s*(-?\d+\.\d+)", texto)
    assert m, "el informe tiene que imprimir la LE"
    esperada = f"{calcular(-12.875, 37).ligand_efficiency_vina:.3f}"
    assert m.group(1) == esperada == "0.348", f"LE del informe {m.group(1)}; el dossier da {esperada}"


# ── El saneador ──────────────────────────────────────────────────────────────────────────────────


def test_el_saneador_quita_lo_que_no_se_dibuja_y_respeta_el_resto():
    from services.pdf_glifos import sin_glifos_ausentes as s

    assert s("⚠️ Molécula con 37 átomos") == "Molécula con 37 átomos"
    assert s("⚠ <b>Aviso</b>: ⚡ dos") == "<b>Aviso</b>: dos"
    assert s("x\x00y\x7fz") == "xyz"
    assert s("a​b") == "ab"
    # Control negativo: lo que las fuentes del producto sí dibujan no se toca.
    assert s("✓ Δ → · – « » ±  Å") == "✓ Δ → · – « » ±  Å"
    assert s("línea 1\n  línea 2\tcon tabulador") == "línea 1\n  línea 2\tcon tabulador"
    assert s("") == ""


# ── L2: el texto no baja del contraste que pide WCAG AA ─────────────────────────────────────────


def _textos_con_poco_contraste(datos: bytes, minimo: float = 4.5):
    from tests.pdf_geometria import paginas

    # El texto casi blanco va sobre una banda de color (cabeceras de tabla, barra de marca): no se mide contra el blanco.
    return sorted({
        (round(t.contraste, 1), t.texto.strip()[:40])
        for p in paginas(datos) for t in p.textos
        if min(t.color) <= 0.85 and t.contraste < minimo and t.texto.strip()
    })


def test_el_informe_no_tiene_texto_por_debajo_de_4_5_a_1_de_contraste():
    malos = _textos_con_poco_contraste(_informe())
    assert not malos, f"texto con poco contraste sobre blanco (contraste, texto): {malos[:6]}"


def test_el_dossier_no_tiene_texto_por_debajo_de_4_5_a_1_de_contraste():
    from services.dossier.model import build_case_dossier
    from services.dossier.pdf import render_dossier_pdf
    from tests.fixtures_dossier import caso_completo

    malos = _textos_con_poco_contraste(render_dossier_pdf(build_case_dossier(**caso_completo())).getvalue())
    assert not malos, f"texto con poco contraste sobre blanco (contraste, texto): {malos[:6]}"


def test_control_negativo_el_medidor_ve_el_gris_que_daba_2_6_a_1():
    from tests.pdf_geometria import Caja, Texto

    claro = Texto(Caja(0, 0, 1, 1), "x", 7, (0x94 / 255, 0xA3 / 255, 0xB8 / 255))
    medio = Texto(Caja(0, 0, 1, 1), "x", 7, (0x64 / 255, 0x74 / 255, 0x8B / 255))
    assert claro.contraste < 3 and medio.contraste > 4.5


# ── B4 / B5: ni títulos solos al pie ni huecos grandes en blanco ────────────────────────────────

LIBRE_MAXIMO = 0.35  # la cápsula midió 44–71 % de página libre en 13 de 14 dossiers
TAMANO_DE_CUERPO_MAXIMO = 10.5  # el cuerpo va a 9–10 pt; los títulos de sección, a 12 pt o más


def _pie_de_pagina(pagina) -> float:
    return 45.0  # el pie del documento está por debajo de esta altura


def _huecos_y_titulos_al_pie(datos: bytes):
    """[(página, «libre» o «título al pie»)] para cada página menos la última."""
    from tests.pdf_geometria import paginas

    hallazgos = []
    todas = paginas(datos)
    for n, p in enumerate(todas[:-1], start=1):
        cuerpo = [t for t in p.textos if t.caja.y0 > _pie_de_pagina(p) and t.caja.y1 < p.alto - 30]
        figuras = [f for f in p.figuras() if f.caja.y0 > _pie_de_pagina(p)]
        if not cuerpo and not figuras:
            continue
        base = min([t.caja.y0 for t in cuerpo] + [f.caja.y0 for f in figuras])
        libre = (base - _pie_de_pagina(p)) / (p.alto - 75)
        if libre > LIBRE_MAXIMO:
            hallazgos.append((n, f"{libre:.0%} libre"))
        ultimo = min(cuerpo, key=lambda t: t.caja.y0) if cuerpo else None
        if ultimo is not None and ultimo.tamano > TAMANO_DE_CUERPO_MAXIMO and not [f for f in figuras if f.caja.y0 < ultimo.caja.y0]:
            hallazgos.append((n, f"título al pie: {ultimo.texto.strip()[:40]}"))
    return hallazgos


def test_el_dossier_no_deja_huecos_ni_titulos_al_pie():
    from services.dossier.model import build_case_dossier
    from services.dossier.pdf import render_dossier_pdf
    from tests.fixtures_dossier import caso_completo

    hallazgos = _huecos_y_titulos_al_pie(render_dossier_pdf(build_case_dossier(**caso_completo())).getvalue())
    assert not hallazgos, f"huecos o títulos huérfanos en el dossier: {hallazgos}"


@pytest.mark.parametrize("relleno", [0, 2, 4, 6, 8, 10, 12, 14, 16, 18])
def test_el_informe_no_deja_titulos_solos_al_pie_con_ningun_relleno(relleno):
    """Con más o menos texto antes, el salto de página cae en sitios distintos: ninguno deja un título huérfano."""
    from services.avisos import Severidad, aviso

    avisos = [aviso(f"RELLENO_{i}", Severidad.INFO, "Aviso de relleno que ocupa una línea del documento, número %d." % i)
              for i in range(relleno)]
    shap = {"log_p": 0.3, "tpsa": -0.1, "hbd": 0.05, "qed": 0.02}  # con la sección de explicabilidad, que también lleva título
    hallazgos = [h for h in _huecos_y_titulos_al_pie(_informe(avisos=avisos, shap=shap)) if h[1].startswith("título al pie")]
    assert not hallazgos, f"títulos huérfanos con {relleno} avisos de relleno: {hallazgos}"


# ── B6: ninguna fuente sin incrustar ────────────────────────────────────────────────────────────


def _hay_truetype_para_incrustar() -> bool:
    from services.dossier.pdf import fuente_de_texto_incrustada

    return fuente_de_texto_incrustada()


@pytest.mark.skipif(not _hay_truetype_para_incrustar(), reason="este equipo no tiene Arial, DejaVu ni Liberation para incrustar")
def test_el_informe_no_declara_fuentes_sin_incrustar():
    from tests.pdf_geometria import fuentes_sin_incrustar

    sueltas = fuentes_sin_incrustar(_informe())
    assert not sueltas, f"fuentes que el PDF declara sin llevarlas dentro: {sueltas}"


@pytest.mark.skipif(not _hay_truetype_para_incrustar(), reason="este equipo no tiene Arial, DejaVu ni Liberation para incrustar")
def test_el_dossier_no_declara_fuentes_sin_incrustar():
    from services.dossier.model import build_case_dossier
    from services.dossier.pdf import render_dossier_pdf
    from tests.fixtures_dossier import caso_completo
    from tests.pdf_geometria import fuentes_sin_incrustar

    sueltas = fuentes_sin_incrustar(render_dossier_pdf(build_case_dossier(**caso_completo())).getvalue())
    assert not sueltas, f"fuentes que el PDF declara sin llevarlas dentro: {sueltas}"


def test_control_negativo_el_medidor_ve_las_fuentes_estandar():
    """Un PDF hecho a propósito con Helvetica y Courier: el medidor tiene que nombrarlas."""
    import io as _io

    from reportlab.pdfgen import canvas

    from tests.pdf_geometria import fuentes_sin_incrustar

    buf = _io.BytesIO()
    c = canvas.Canvas(buf)
    c.setFont("Helvetica", 10)
    c.drawString(50, 700, "uno")
    c.setFont("Courier", 10)
    c.drawString(50, 680, "dos")
    c.save()
    assert {"Helvetica", "Courier"} <= set(fuentes_sin_incrustar(buf.getvalue()))
