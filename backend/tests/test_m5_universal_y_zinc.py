"""Qué de M5 es universal y qué es de zinc, y la detección que lo sostiene.

`docs/74_ARQUITECTURA_DISPATCHER_DE_PROTOCOLOS.md` §6 define M5 como una familia
con un adaptador por metal. La pregunta previa era cuál de las piezas actuales
sirve para cualquier metal.

Revisado `scoring/ums.py` entero: **del scoring no hay casi nada universal.**
Los siete warheads son grupos de unión a ZINC, validados sobre CA2, MMP9 y ACE
—tres enzimas de zinc—, y los pesos salen de ese mismo ajuste. Lo universal es
la infraestructura: detectar el ion, conservarlo, registrar su procedencia,
saber si hay adaptador y abstenerse si no.

═══════════════════════════════════════════════════════════════════════════
EL DEFECTO QUE HABÍA QUE ARREGLAR ANTES DE APOYARSE EN LA DETECCIÓN
═══════════════════════════════════════════════════════════════════════════

`detect_metals_in_protein` decidía así:

    if element in metal_symbols or atom_name.upper() in metal_symbols:

y `CA` es a la vez el calcio y el nombre del carbono alfa de todos los
aminoácidos. Medido antes de corregirlo:

    1gkc_chainA (MMP9, metaloenzima real)   198 «metales»: 191 con elemento C,
                                            5 CA, y sólo 2 ZN de verdad
    3pp0_chainB (CDK2, sin metales)         380 «metales», todos elemento C

Una quinasa sin un solo ion devolvía 380. La función no la llamaba el pipeline
de acoplamiento —sólo el router de protein_surgery— así que el defecto no se
notaba; pero el documento 74 §6.1 la quiere como fuente de activación de M5, y
sobre esto no se puede construir un enrutado.

Corregida con dos reglas leídas de las líneas reales del PDB:

    HETATM 2515 CA    CA A1444   ...  1.00 25.39          CA   <- ion de calcio
    ATOM      2  CA  PHE A 110   ...  1.00 76.45           C   <- carbono alfa

1. sólo registros HETATM;
2. sólo la columna de elemento (77-78), nunca el nombre del átomo.
"""

from __future__ import annotations

from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]

# Estas dos estructuras eran derivados por cadena que sólo existían en el disco
# del mantenedor: el repositorio distribuye `1gkc.pdb.gz` y `3PP0.pdb.gz`
# completos, no los recortes. En un clon limpio los archivos no existían, el
# detector de metales no veía ningún Zn y cuatro pruebas fallaban afirmando que
# una metaloenzima no tenía metales -que es exactamente el error que vigilan-.
#
# No sirve usar el `.gz` completo: 1GKC tiene 4 Zn repartidos en dos cadenas y
# la prueba espera los 2 de la cadena A. Se recorta la cadena, que reproduce el
# archivo local byte a byte en lo que importa.


def _cadena_desde_gz(gz: Path, cadena: str, destino: Path) -> Path:
    """Extrae una cadena del PDB comprimido que SÍ viaja en el repositorio."""
    import gzip

    with gzip.open(gz, "rt", encoding="utf-8", errors="replace") as entrada:
        lineas = [
            linea for linea in entrada.read().splitlines()
            if not linea.startswith(("ATOM", "HETATM")) or linea[21:22] == cadena
        ]
    destino.write_text(chr(10).join(lineas) + chr(10), encoding="utf-8")
    return destino


def _estructura(nombre_local: str, gz: str, cadena: str) -> Path:
    local = RAIZ / "data" / "targets" / nombre_local
    if local.is_file():
        return local
    comprimido = RAIZ / "data" / "targets" / gz
    if not comprimido.is_file():
        pytest.skip(f"ni {nombre_local} ni {gz} disponibles")
    import tempfile

    temporal = Path(tempfile.mkdtemp(prefix="m5zn_")) / nombre_local
    return _cadena_desde_gz(comprimido, cadena, temporal)


MMP9 = _estructura("1gkc_chainA.pdb", "1gkc.pdb.gz", "A")
CDK2 = _estructura("3pp0_chainB.pdb", "3PP0.pdb.gz", "B")


# ── La detección, que es la base de todo lo demás ────────────────────────

def test_una_quinasa_sin_metales_no_reporta_ninguno():
    """El caso que delató el defecto: CDK2 devolvía 380."""
    from services.chemistry.protein_surgery import detect_metals_in_protein

    metales = detect_metals_in_protein(str(CDK2))
    assert metales == [], (
        f"CDK2 no tiene iones metálicos y se detectaron {len(metales)}. "
        "Comprueba que no se vuelve a mirar el nombre del átomo: `CA` es el "
        "carbono alfa de todos los residuos."
    )


def test_una_metaloenzima_reporta_sus_iones_reales():
    """MMP9: zinc catalítico y estructural, más calcios estructurales."""
    from services.chemistry.protein_surgery import detect_metals_in_protein

    metales = detect_metals_in_protein(str(MMP9))
    elementos = sorted(m["element"] for m in metales)
    assert elementos.count("ZN") == 2, f"se esperaban 2 Zn y salieron {elementos}"
    assert "CA" in elementos, "MMP9 tiene calcios estructurales"
    assert all(e in {"ZN", "CA"} for e in elementos), (
        f"aparecieron elementos que no son iones: {sorted(set(elementos))}"
    )


def test_no_se_mira_el_nombre_del_atomo():
    """La regresión concreta, sobre el código."""
    fuente = (
        RAIZ / "backend" / "services" / "chemistry" / "protein_surgery.py"
    ).read_text(encoding="utf-8")
    bloque = fuente[
        fuente.index("def detect_metals_in_protein") : fuente.index("# Layer 6")
    ]
    # Fuera el docstring: cita el código viejo a propósito, y buscarlo ahí
    # encontraría siempre la explicación en vez del código.
    partes = bloque.split('"""')
    cuerpo = partes[2] if len(partes) > 2 else bloque
    codigo = [l for l in cuerpo.splitlines() if not l.strip().startswith("#")]
    assert not [l for l in codigo if "atom_name" in l and "metal" in l.lower()], (
        "vuelve a compararse el nombre del átomo contra los símbolos de metal"
    )
    assert any("startswith(\"HETATM\")" in l for l in codigo), (
        "se dejó de exigir HETATM: un registro ATOM es un átomo del polímero"
    )


def test_cada_metal_trae_su_procedencia():
    """§6.2 pide identidad, coordenadas y procedencia, no sólo que lo hay."""
    from services.chemistry.protein_surgery import detect_metals_in_protein

    metales = detect_metals_in_protein(str(MMP9))
    assert metales
    for m in metales:
        for clave in ("element", "position", "residue_name", "chain", "source_line"):
            assert clave in m, f"falta {clave} en el registro del metal"
        assert m["source_line"] > 0


# ── El contexto metálico y sus tres fuentes ──────────────────────────────

def test_las_fuentes_del_contexto_se_registran_por_separado():
    from services.pipeline.protocols.m5.base import (
        FuenteDelContexto,
        detectar_contexto_metalico,
    )

    ctx = detectar_contexto_metalico(
        ruta_pdb=str(MMP9), familia_estructural="metalloenzyme"
    )
    assert ctx.es_metalica
    assert FuenteDelContexto.FAMILIA_CURADA in ctx.fuentes
    assert FuenteDelContexto.OBSERVADO_EN_ESTRUCTURA in ctx.fuentes
    assert ctx.elementos == {"ZN", "CA"}


def test_una_discrepancia_entre_fuentes_se_declara_no_se_resuelve():
    """Metal observado sin etiqueta curada: puede ser estructural."""
    from services.pipeline.protocols.m5.base import detectar_contexto_metalico

    ctx = detectar_contexto_metalico(ruta_pdb=str(MMP9), familia_estructural="kinase")
    assert ctx.es_metalica
    assert ctx.avisos, (
        "se observó metal y el catálogo dice otra cosa: eso tiene que salir "
        "como aviso, no resolverse por precedencia"
    )
    assert "estructural" in " ".join(ctx.avisos)


def test_familia_metalica_sin_metal_en_la_estructura_avisa():
    """O se perdió en la preparación, o la etiqueta no corresponde."""
    from services.pipeline.protocols.m5.base import detectar_contexto_metalico

    ctx = detectar_contexto_metalico(
        ruta_pdb=str(CDK2), familia_estructural="metalloenzyme"
    )
    assert ctx.avisos
    assert "cofactors_whitelist" in " ".join(ctx.avisos), (
        "el aviso tiene que apuntar a las dos causas posibles, y una es que el "
        "metal se perdiera en la preparación del receptor"
    )


def test_una_diana_sin_metal_no_activa_m5():
    from services.pipeline.protocols.m5.base import (
        adaptador_para,
        detectar_contexto_metalico,
    )

    ctx = detectar_contexto_metalico(ruta_pdb=str(CDK2), familia_estructural="kinase")
    assert ctx.es_metalica is False
    assert adaptador_para(ctx) is None


# ── El registro de adaptadores ───────────────────────────────────────────

def test_solo_el_zinc_tiene_adaptador_disponible():
    from services.pipeline.protocols.m5.base import ADAPTADORES

    disponibles = [a.metal for a in ADAPTADORES.values() if a.disponible]
    assert disponibles == ["ZN"], (
        f"hay adaptadores marcados disponibles sin validación: {disponibles}. "
        "El §12 del documento 74 fija los ocho gates para pasar de registrado "
        "a disponible."
    )


def test_los_metales_sin_adaptador_estan_registrados_y_bloqueados():
    """§8: que existan en el registro impide que M4 los absorba sin aviso."""
    from services.pipeline.protocols.m5.base import ADAPTADORES

    for metal in ("FE", "MG", "CA", "MN"):
        adaptador = ADAPTADORES[metal]
        assert adaptador.disponible is False
        assert adaptador.estado_cientifico == "BLOCKED_UNTIL_VALIDATED"
        assert adaptador.motivo.strip(), (
            f"{metal} está bloqueado sin decir por qué: un bloqueo sin motivo "
            "no se puede revisar"
        )


def test_el_adaptador_de_zinc_declara_donde_se_midio():
    from scoring.ums import DOMINIO_MEDIDO_ZN
    from services.pipeline.protocols.m5.base import ADAPTADORES

    assert set(DOMINIO_MEDIDO_ZN) == {"CA2", "MMP9", "ACE"}
    assert ADAPTADORES["ZN"].estado_cientifico == "REVIEW", (
        "el adaptador de zinc no puede declararse SUPPORTED: se evaluó "
        "retrospectivamente sobre tres dianas"
    )
    assert len(ADAPTADORES["ZN"].dominio_medido) == 3


def test_un_metal_desconocido_bloquea_en_vez_de_caer_a_m4(tmp_path):
    """§6.1: no se degrada en silencio a M4."""
    from services.pipeline.protocols.m5.base import (
        adaptador_para,
        detectar_contexto_metalico,
    )

    # Un PDB mínimo con un solo ion de wolframio, que no tiene adaptador.
    pdb = tmp_path / "w.pdb"
    pdb.write_text(
        "HETATM    1  W    W  A 900      10.000  10.000  10.000  1.00 20.00           W \n"
        "END\n",
        encoding="utf-8",
    )
    ctx = detectar_contexto_metalico(ruta_pdb=str(pdb), familia_estructural="metalloenzyme")
    adaptador = adaptador_para(ctx)
    assert adaptador is not None
    assert adaptador.disponible is False, (
        "un metal sin adaptador tiene que bloquear, no ejecutarse como si "
        "fuera zinc"
    )


# ── La separación universal / zinc, escrita donde toca ───────────────────

def test_ums_se_declara_como_adaptador_de_zinc():
    fuente = (RAIZ / "backend" / "scoring" / "ums.py").read_text(encoding="utf-8")
    assert "adaptador de ZINC" in fuente or "adaptador de zinc" in fuente, (
        "`ums.py` volvió a presentarse como universal. Sus siete warheads son "
        "grupos de unión a zinc y sus pesos salen de dianas de zinc."
    )


def test_la_base_universal_no_conoce_warheads():
    """Si la base supiera de sulfonamidas, no sería universal."""
    fuente = (
        RAIZ / "backend" / "services" / "pipeline" / "protocols" / "m5" / "base.py"
    ).read_text(encoding="utf-8")
    codigo = [l for l in fuente.splitlines() if not l.strip().startswith("#")]
    cuerpo = "\n".join(codigo)
    for termino in ("sulfonamide", "hydroxamic", "WARHEAD_SMARTS", "detect_warheads"):
        assert termino not in cuerpo, (
            f"la base universal de M5 usa «{termino}», que es química de zinc. "
            "Eso pertenece al adaptador."
        )


@pytest.mark.parametrize(
    "estado", ["sin_metal", "metal_preserved", "metal_geometry_evaluated", "metal_aware_scoring"]
)
def test_la_maquina_de_estados_del_metal_existe(estado: str):
    """§6.2: conservar el ion, medir su geometría y puntuar con él son
    tres cosas distintas, y viajaban indistinguibles."""
    from services.pipeline.protocols.m5.base import EstadoMetal

    assert estado in {e.value for e in EstadoMetal}
