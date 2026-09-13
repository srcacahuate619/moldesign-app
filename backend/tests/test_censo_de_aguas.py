"""
El sitio se acopla seco. Cuánto se le quitó, medido.

# Lo que había

El dossier declaraba «preparación en condición desolvatada» en abstracto: la
misma frase para un sitio que no tenía ninguna agua y para uno con treinta y
ocho bien coordinadas. `preparer.py` sigue eliminándolas todas —es lo estándar
en acoplamiento generalista y no se cambia—; lo que faltaba era el número.

# Lo que la medición desaconseja

Una auditoría externa propuso conservar como estructurales las aguas con más de
tres puentes al receptor. Aplicado a las 307 estructuras empaquetadas, contando
sólo aguas dentro de la caja:

    receptores con estructura y caja      254
      con al menos una de >=3 puentes     237   (93 %)
    aguas de >=3 puentes  mediana 8   máximo 38

Un criterio que dispara en el 93 % de los receptores y selecciona ocho aguas de
mediana no identifica aguas estructurales: identifica aguas. Estas pruebas
fijan el censo —que es lo que se integró— y no una política de conservación,
que necesita otro criterio y una medición previa.
"""

from pathlib import Path

import pytest

from services.chemistry.censo_de_aguas import (
    CORTE_PUENTE_A,
    PUENTES_BIEN_COORDINADA,
    censar_aguas,
    describir_censo,
)

RAIZ = Path(__file__).resolve().parents[2]


def _atomo(serial: int, nombre: str, residuo: str, x: float, y: float, z: float, elemento: str) -> str:
    registro = "HETATM" if residuo in ("HOH", "WAT", "DOD") else "ATOM  "
    return (
        f"{registro}{serial:>5} {nombre:<4}{residuo:>4} A{1:>4}    "
        f"{x:>8.3f}{y:>8.3f}{z:>8.3f}  1.00 20.00          {elemento:>2}"
    )


def test_cuenta_solo_las_aguas_de_la_caja():
    pdb = "\n".join([
        _atomo(1, "O", "HOH", 0.0, 0.0, 0.0, "O"),      # dentro
        _atomo(2, "O", "HOH", 30.0, 0.0, 0.0, "O"),     # fuera
        _atomo(3, "O", "HOH", 1.0, 1.0, 1.0, "O"),      # dentro
    ])
    censo = censar_aguas(pdb, (0.0, 0.0, 0.0), (10.0, 10.0, 10.0))
    assert censo.en_la_estructura == 3
    assert censo.en_la_caja == 2


def test_cuenta_los_puentes_con_el_corte_declarado():
    """Un agua rodeada de tres nitrógenos a 3.0 Å está bien coordinada."""
    pdb = "\n".join([
        _atomo(1, "O", "HOH", 0.0, 0.0, 0.0, "O"),
        _atomo(2, "ND1", "HIS", 3.0, 0.0, 0.0, "N"),
        _atomo(3, "OD1", "ASP", 0.0, 3.0, 0.0, "O"),
        _atomo(4, "NE2", "GLN", 0.0, 0.0, 3.0, "N"),
    ])
    censo = censar_aguas(pdb, (0.0, 0.0, 0.0), (10.0, 10.0, 10.0))
    assert censo.bien_coordinadas == 1
    assert censo.max_puentes == 3


def test_un_carbono_no_cuenta_como_puente():
    """Sólo N y O. Un carbono cerca no es un puente de hidrógeno."""
    pdb = "\n".join([
        _atomo(1, "O", "HOH", 0.0, 0.0, 0.0, "O"),
        _atomo(2, "CA", "ALA", 3.0, 0.0, 0.0, "C"),
        _atomo(3, "CB", "ALA", 0.0, 3.0, 0.0, "C"),
        _atomo(4, "CG", "ALA", 0.0, 0.0, 3.0, "C"),
    ])
    assert censar_aguas(pdb, (0.0, 0.0, 0.0), (10.0, 10.0, 10.0)).max_puentes == 0


def test_el_corte_es_estricto():
    pdb_dentro = "\n".join([
        _atomo(1, "O", "HOH", 0.0, 0.0, 0.0, "O"),
        _atomo(2, "N", "LYS", CORTE_PUENTE_A - 0.1, 0.0, 0.0, "N"),
    ])
    pdb_fuera = "\n".join([
        _atomo(1, "O", "HOH", 0.0, 0.0, 0.0, "O"),
        _atomo(2, "N", "LYS", CORTE_PUENTE_A + 0.1, 0.0, 0.0, "N"),
    ])
    caja = ((0.0, 0.0, 0.0), (10.0, 10.0, 10.0))
    assert censar_aguas(pdb_dentro, *caja).max_puentes == 1
    assert censar_aguas(pdb_fuera, *caja).max_puentes == 0


def test_un_receptor_sin_aguas_se_declara_igual():
    """«No había» y «no se midió» no pueden parecer lo mismo."""
    pdb = _atomo(1, "CA", "ALA", 0.0, 0.0, 0.0, "C")
    censo = censar_aguas(pdb, (0.0, 0.0, 0.0), (10.0, 10.0, 10.0))
    assert censo.en_la_caja == 0
    assert not censo.hay_algo_que_declarar
    assert "no tenía aguas" in describir_censo(censo)


def test_un_pdb_ya_preparado_da_censo_cero_sin_reventar():
    assert censar_aguas("", (0.0, 0.0, 0.0), (20.0, 20.0, 20.0)).en_la_caja == 0
    assert censar_aguas("basura\nno es un pdb\n", (0.0,) * 3, (20.0,) * 3).en_la_caja == 0


def test_la_frase_lleva_los_numeros_y_no_promete_nada():
    pdb = "\n".join(
        [_atomo(1, "O", "HOH", 0.0, 0.0, 0.0, "O")]
        + [_atomo(i + 2, "N", "LYS", 3.0, float(i), 0.0, "N") for i in range(3)]
    )
    frase = describir_censo(censar_aguas(pdb, (0.0, 0.0, 0.0), (10.0, 10.0, 10.0)))
    assert "1 aguas" in frase or "1 agua" in frase
    assert str(PUENTES_BIEN_COORDINADA) in frase
    # Declara la condición; no afirma que el resultado esté mal.
    assert "no la incluyen" in frase
    for prohibida in ("inválido", "incorrecto", "error"):
        assert prohibida not in frase.lower()


# ── Sobre una estructura real del producto ─────────────────────────────────

@pytest.mark.skipif(
    not (RAIZ / "data" / "target_library").exists(),
    reason="la biblioteca de estructuras no está en este árbol",
)
def test_la_proteasa_del_vih_declara_sus_aguas():
    """1HSG es el caso de libro: el sitio tiene aguas, y una es la catalítica."""
    import json

    catalogo = json.loads((RAIZ / "curated_targets.json").read_text(encoding="utf-8"))
    filas = catalogo if isinstance(catalogo, list) else catalogo.get("targets", catalogo)
    fila = next((f for f in filas if isinstance(f, dict) and f.get("pdb_id") == "1HSG"), None)
    if fila is None or fila.get("grid_center_x") is None:
        pytest.skip("1HSG no está en el catálogo de este árbol")

    ruta = next(
        (p for p in (RAIZ / "data" / "target_library").rglob("*.pdb")
         if p.stem.upper().startswith("1HSG")),
        None,
    )
    if ruta is None:
        pytest.skip("1HSG no está sembrada en este árbol")

    censo = censar_aguas(
        ruta.read_text(encoding="utf-8", errors="ignore"),
        (fila["grid_center_x"], fila["grid_center_y"], fila["grid_center_z"]),
        (fila.get("grid_size_x") or 20, fila.get("grid_size_y") or 20, fila.get("grid_size_z") or 20),
    )
    assert censo.en_la_caja > 0, "la proteasa del VIH tiene aguas en el sitio"
    assert censo.bien_coordinadas > 0
    assert "se retiraron" in describir_censo(censo)


def test_el_censo_es_barato():
    """Corre en el camino caliente del acoplamiento: no puede costar segundos."""
    import time

    aguas = [_atomo(i, "O", "HOH", float(i % 20), float(i % 17), float(i % 13), "O") for i in range(150)]
    proteina = [
        _atomo(1000 + i, "N", "LYS", float(i % 25), float(i % 19), float(i % 11), "N")
        for i in range(4000)
    ]
    pdb = "\n".join(aguas + proteina)

    inicio = time.perf_counter()
    censar_aguas(pdb, (10.0, 10.0, 6.0), (30.0, 30.0, 30.0))
    assert time.perf_counter() - inicio < 1.0


# ── P3: la cita que respalda la decisión de multicadena ────────────────────
#
# El panel de anti-dianas acopla hERG (5VA1) y NaV1.5 (6MVW) sobre estructuras
# experimentales ensambladas, no sobre modelos de co-plegamiento. Esa decisión
# se tomó por medición del catálogo; el benchmark de canales iónicos es la
# evidencia de literatura que faltaba citar.

def test_la_decision_de_multicadena_cita_su_evidencia():
    fuente = (RAIZ / "backend" / "services" / "docking" / "anti_target_sitio.py").read_text(
        encoding="utf-8"
    )
    assert "frbis.2026.1937302" in fuente, "falta el DOI del benchmark de canales"
    # Y que se diga POR QUÉ importa aquí, no sólo que existe.
    for termino in ("5VA1", "6MVW", "poro"):
        assert termino in fuente


def test_el_panel_apunta_a_donde_vive_la_decision():
    fuente = (RAIZ / "backend" / "services" / "docking" / "selectivity.py").read_text(
        encoding="utf-8"
    )
    # El número de artículo, que es lo común a las dos citas; el DOI completo
    # vive donde está la decisión.
    assert "1937302" in fuente
    assert "anti_target_sitio.py" in fuente


# ── El criterio de conservación, medido antes de decidir ───────────────────
#
# La pendiente era «enterramiento + desplazabilidad, no conteo de puentes». Se
# implementó y se midió sobre las 322 estructuras del catálogo con aguas en la
# caja; el encabezado de `censo_de_aguas.py` trae la tabla. El resultado fue que
# el criterio propuesto NO sirve tal cual —la desplazabilidad por proximidad da
# «no desplazable» al 80 % de las aguas— y que lo único que llega a una escala
# creíble es encierro total con cinco o más contactos.
#
# Estas pruebas fijan esa conclusión para que no se pierda, y fijan también que
# nada del acoplamiento aplica el criterio.

from services.chemistry.censo_de_aguas import (  # noqa: E402
    ENTERRAMIENTO_ENCERRADA,
    PUENTES_ESTRUCTURAL,
    AguaMedida,
)


def _cascara(radio: float = 5.0) -> list[str]:
    """Un carbono en cada una de las 26 direcciones del cubo, a `radio` del origen.

    Es la cáscara mínima que tapa todas las direcciones: con ella el agua del
    centro sale con enterramiento 1.0, y quitando átomos se ve bajar la fracción.
    """
    lineas = []
    serial = 100
    for i in (-1, 0, 1):
        for j in (-1, 0, 1):
            for k in (-1, 0, 1):
                if (i, j, k) == (0, 0, 0):
                    continue
                norma = (i * i + j * j + k * k) ** 0.5
                serial += 1
                lineas.append(_atomo(serial, "C", "ALA", i * radio / norma,
                                     j * radio / norma, k * radio / norma, "C"))
    return lineas


def test_un_agua_rodeada_sale_encerrada_y_una_expuesta_no():
    """La medida es direccional: distingue cavidad cerrada de surco abierto."""
    dentro = "\n".join([_atomo(1, "O", "HOH", 0.0, 0.0, 0.0, "O")] + _cascara())
    censo = censar_aguas(dentro, (0.0, 0.0, 0.0), (6.0, 6.0, 6.0), medir_sitio=True)
    assert len(censo.aguas) == 1
    assert censo.aguas[0].enterramiento == 1.0

    # La misma agua con receptor sólo a un lado: la mayoría de direcciones libres.
    medio = "\n".join([
        _atomo(1, "O", "HOH", 0.0, 0.0, 0.0, "O"),
        _atomo(2, "C", "ALA", 0.0, 0.0, 3.0, "C"),
        _atomo(3, "C", "ALA", 1.0, 0.0, 3.5, "C"),
    ])
    censo2 = censar_aguas(medio, (0.0, 0.0, 0.0), (6.0, 6.0, 6.0), medir_sitio=True)
    assert censo2.aguas[0].enterramiento < 0.5
    assert not censo2.aguas[0].encerrada


def test_la_medicion_del_sitio_no_se_hace_si_no_se_pide():
    """El censo va en el camino caliente del acoplamiento; esto cuesta y no hace falta."""
    pdb = "\n".join([_atomo(1, "O", "HOH", 0.0, 0.0, 0.0, "O")] + _cascara())
    assert censar_aguas(pdb, (0.0, 0.0, 0.0), (6.0, 6.0, 6.0)).aguas == ()


def test_el_criterio_exige_las_dos_cosas():
    """Encerrada pero mal coordinada no basta, y bien coordinada pero abierta tampoco."""
    encerrada_floja = AguaMedida((0, 0, 0), puentes=2, enterramiento=1.0, hueco_a=2.8)
    abierta_fuerte = AguaMedida((0, 0, 0), puentes=6, enterramiento=0.4, hueco_a=2.8)
    ambas = AguaMedida((0, 0, 0), puentes=6, enterramiento=1.0, hueco_a=2.8)
    assert not encerrada_floja.candidata_a_conservar
    assert not abierta_fuerte.candidata_a_conservar
    assert ambas.candidata_a_conservar


def test_el_corte_es_el_que_la_medicion_dejo_en_pie():
    """Encierro total y cinco contactos. Los flojos disparaban en 8 de cada 10 sitios."""
    assert ENTERRAMIENTO_ENCERRADA == 1.00
    assert PUENTES_ESTRUCTURAL == 5


def test_la_desplazabilidad_por_proximidad_ya_no_existe():
    """Se midió y no separaba nada: el 80 % de las aguas caía del mismo lado.

    Se deja el `hueco_a` como número declarado —informa— pero no como criterio.
    """
    assert not hasattr(AguaMedida, "desplazable")
    assert "hueco_a" in AguaMedida.__dataclass_fields__


def test_el_acoplamiento_no_aplica_el_criterio():
    """Medir no es conservar. Conservar cambia toda afinidad ya guardada."""
    vina = (RAIZ / "backend" / "services" / "docking" / "vina_service.py").read_text(
        encoding="utf-8", errors="replace"
    )
    assert "candidata_a_conservar" not in vina
    assert "medir_sitio=True" not in vina
    preparer = (RAIZ / "backend" / "services" / "docking" / "preparer.py").read_text(
        encoding="utf-8", errors="replace"
    )
    assert "candidata_a_conservar" not in preparer


# ── La caché: el censo estaba en el camino caliente ────────────────────────
#
# `vina_service` censaba en CADA acoplamiento, y antes leía el PDB depositado
# entero para hacerlo. Medido sobre 25 receptores del catálogo:
#
#     leer el PDB        mediana   2.38 ms
#     censar             mediana  14.27 ms
#     acierto de caché   mediana   7.50 µs
#
# El resultado es determinista en (pdb_id, centro, tamaño), así que se guarda.
# Lo que la caché no puede saber es si el archivo cambió: por eso
# `invalidar_censo` existe y la ingesta la llama al reescribir una estructura.

from services.chemistry.censo_de_aguas import (  # noqa: E402
    censo_en_cache,
    guardar_censo,
    invalidar_censo,
)


@pytest.fixture(autouse=True)
def _cache_limpia():
    invalidar_censo()
    yield
    invalidar_censo()


def _censo_de_prueba():
    pdb = "\n".join([_atomo(1, "O", "HOH", 0.0, 0.0, 0.0, "O")] + _cascara())
    return censar_aguas(pdb, (0.0, 0.0, 0.0), (6.0, 6.0, 6.0))


def test_sin_nada_guardado_la_cache_dice_que_no():
    """Devolver `None` es la señal de que hay que leer el archivo."""
    assert censo_en_cache("1ABC", (0.0, 0.0, 0.0), (6.0, 6.0, 6.0)) is None


def test_lo_guardado_se_recupera_con_la_misma_caja():
    censo = _censo_de_prueba()
    guardar_censo("1ABC", (0.0, 0.0, 0.0), (6.0, 6.0, 6.0), censo)
    assert censo_en_cache("1ABC", (0.0, 0.0, 0.0), (6.0, 6.0, 6.0)) is censo


def test_otra_caja_es_otro_censo():
    """La misma diana con otra caja tiene otras aguas dentro."""
    guardar_censo("1ABC", (0.0, 0.0, 0.0), (6.0, 6.0, 6.0), _censo_de_prueba())
    assert censo_en_cache("1ABC", (0.0, 0.0, 0.0), (30.0, 30.0, 30.0)) is None
    assert censo_en_cache("1ABC", (5.0, 0.0, 0.0), (6.0, 6.0, 6.0)) is None


def test_el_ruido_de_coma_flotante_no_falla_el_acierto():
    """Sin redondear, cada corrida sería una clave nueva y la caché no serviría."""
    censo = _censo_de_prueba()
    guardar_censo("1ABC", (10.0, -7.771, 34.741), (30.0, 30.0, 30.0), censo)
    assert censo_en_cache(
        "1ABC", (10.0 + 1e-9, -7.771, 34.741), (30.0, 30.0, 30.0)
    ) is censo


def test_invalidar_borra_solo_el_receptor_que_se_dice():
    guardar_censo("1ABC", (0.0, 0.0, 0.0), (6.0, 6.0, 6.0), _censo_de_prueba())
    guardar_censo("2XYZ", (0.0, 0.0, 0.0), (6.0, 6.0, 6.0), _censo_de_prueba())
    assert invalidar_censo("1ABC") == 1
    assert censo_en_cache("1ABC", (0.0, 0.0, 0.0), (6.0, 6.0, 6.0)) is None
    assert censo_en_cache("2XYZ", (0.0, 0.0, 0.0), (6.0, 6.0, 6.0)) is not None


def test_la_cache_esta_acotada():
    """Una sesión con cajas personalizadas no puede hacerla crecer sin límite."""
    from services.chemistry.censo_de_aguas import _CACHE, _CACHE_MAXIMO

    censo = _censo_de_prueba()
    for i in range(_CACHE_MAXIMO + 50):
        guardar_censo(f"P{i:04d}", (0.0, 0.0, 0.0), (6.0, 6.0, 6.0), censo)
    assert len(_CACHE) <= _CACHE_MAXIMO


def test_la_ingesta_invalida_al_reescribir_la_estructura():
    """La caché no puede enterarse sola de que el archivo cambió."""
    fuente = (RAIZ / "backend" / "services" / "targets" / "ingestion_manager.py").read_text(
        encoding="utf-8", errors="replace"
    )
    assert fuente.count("invalidar_censo(pdb_id)") >= 2, (
        "los dos caminos que escriben `raw.pdb` deben invalidar el censo"
    )


def test_vina_consulta_la_cache_antes_de_leer_el_archivo():
    """Si leyera primero, la caché no ahorraría la E/S, que es el punto."""
    fuente = (RAIZ / "backend" / "services" / "docking" / "vina_service.py").read_text(
        encoding="utf-8", errors="replace"
    )
    pos_cache = fuente.index("censo_en_cache(")
    pos_lectura = fuente.index("read_text(StoragePath.target_raw(target_pdb_id))")
    assert pos_cache < pos_lectura, "la caché se consulta después de leer el PDB"
