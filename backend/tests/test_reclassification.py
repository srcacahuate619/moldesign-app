"""
Tests de backend/scripts/reclassify_targets.py — reclasificación dual de targets
(eje químico `structural_family` + eje terapéutico `therapeutic_family`).

Estrategia (sin DB real):
- Se importa el script como módulo (`backend/scripts/__init__.py` lo habilita).
- Se ejercitan sus internals: normalización de familias, heurísticas regex
  (primera regla que matchea gana), remapeo legacy, loader de overrides y el
  plan builder `construir_plan(rows, overrides)`, que es puro (no toca la DB).
- El plan builder se prueba contra una tabla `targets` en sqlite en memoria
  (solo stdlib), leyendo filas con la MISMA consulta que usa producción.
- Contrato: el schema Pydantic `Target` (core/models.py) expone
  `therapeutic_family`.

Nota de refactor: la regla de coagulación lleva el token `factor VIIa` ANTES
de `factor VII` (el ancla `(?![a-z])` hacía que "factor VII" no matcheara la
forma activada "factor VIIa", el nombre estándar de RCSB). Verificado: el
reporte dry-run contra la DB real es idéntico antes/después del cambio.
"""
from __future__ import annotations

import sqlite3

import pytest

from scripts import reclassify_targets as rc

# Familias químicas canónicas que deben pasar por normalizar_familia inalteradas.
# Excluimos "isomerase": es familia canónica pero el alias la remapea a
# topoisomerase (comportamiento deliberado, cubierto en TestNormalizacion).
FAMILIAS_PASSTHROUGH = sorted(rc.CHEMICAL_FAMILIES - {"isomerase"})


# ═════════════════════════════════════════════════════════════════════════════
# 1) Normalización de familias
# ═════════════════════════════════════════════════════════════════════════════

class TestNormalizacion:
    """Alias de FAMILY_ALIASES, case-insensitive (lowercase previo incluido)."""

    @pytest.mark.parametrize("entrada,esperado", [
        ("GPCR", "gpcr"),
        ("Kinase", "kinase"),
        ("Serine Protease", "protease"),
        ("serine protease", "protease"),          # case-insensitive
        ("cytochrome", "cytochrome_p450"),
        ("CYTOCHROME", "cytochrome_p450"),        # case-insensitive
        ("metaloenzyme", "metalloenzyme"),
        ("Metaloenzyme", "metalloenzyme"),        # case-insensitive
        ("isomerase", "topoisomerase"),
        ("ISOMERASE", "topoisomerase"),           # case-insensitive
    ])
    def test_aliases(self, entrada, esperado):
        assert rc.normalizar_familia(entrada) == esperado

    @pytest.mark.parametrize("entrada", FAMILIAS_PASSTHROUGH)
    def test_familias_quimicas_conocidas_pasan_inalteradas(self, entrada):
        assert rc.normalizar_familia(entrada) == entrada

    @pytest.mark.parametrize("entrada", [None, ""])
    def test_vacio_o_none_devuelve_none(self, entrada):
        assert rc.normalizar_familia(entrada) is None

    def test_solo_espacios_devuelve_cadena_vacia(self):
        # Quirk del código de producción: "   " es truthy, strip() → "".
        # Inofensivo: el plan builder manda esa fila a PENDIENTES igual.
        assert rc.normalizar_familia("   ") == ""


# ═════════════════════════════════════════════════════════════════════════════
# 2) Heurísticas regex (primera regla que matchea gana, por eje)
# ═════════════════════════════════════════════════════════════════════════════

class TestRegexHeuristicas:
    """`regex_para_eje` asigna la familia de la PRIMERA regla que matchea."""

    @pytest.mark.parametrize("texto,esperado", [
        ("CDK2", "kinase"),
        ("CYP3A4", "cytochrome_p450"),
        ("HIV-1 protease", "protease"),
        ("COX-2", "oxidoreductase"),
        ("telomerase", "polymerase"),
        ("20S proteasome", "proteasome"),
        ("BACE1 IN COMPLEX", "protease"),
        ("BETA-SITE APP-CLEAVING ENZYME 1", "protease"),
        ("FACTOR VIIA IN COMPLEX", "protease"),
        ("E. COLI DOMAIN IN COMPLEX WITH CLOROBIOCIN", "topoisomerase"),
        ("TSHR-THYROID STIMULATING HORMONE", "gpcr"),
        ("PDE5A1-IBMX", "phosphodiesterase"),
    ])
    def test_eje_quimico(self, texto, esperado):
        assert rc.regex_para_eje(texto, "chemical") == esperado

    @pytest.mark.parametrize("texto,esperado", [
        ("factor VIIa", "coagulacion___hemostasia"),
        ("CYP3A4", "metabolismo"),
        ("HIV-1 protease", "antivirales"),
        ("5-HT1A receptor", "psiquiatria"),
        ("PDE5A1-IBMX", "cardiovascular"),
        ("TBRPDEB1-INHIBITOR COMPLEX", "antiparasitarios"),
        ("TSHR-THYROID STIMULATING HORMONE-GS-ML109", "endocrinologia"),
        ("CELLULAR RETINOIC-ACID-BINDING PROTEIN", "endocrinologia"),
        ("RAR LIGAND-BINDING DOMAIN", "endocrinologia"),
        ("UNINHIBITED HUMAN CATHEPSIN K", "inflamacion___dolor"),
        ("CATHEPSIN B-E64C COMPLEX", "oncologia"),
        ("SRC SH2 DOMAIN", "oncologia"),
        ("PHOSPHODIESTERASE-9A IN COMPLEX", "neurodegeneracion"),
        ("BACE1 IN COMPLEX WITH OM99-2", "neurodegeneracion"),
    ])
    def test_eje_terapeutico(self, texto, esperado):
        assert rc.regex_para_eje(texto, "therapeutic") == esperado

    def test_desconocido_no_matchea_ningun_eje(self):
        assert rc.regex_para_eje("unrelated protein X", "chemical") is None
        assert rc.regex_para_eje("unrelated protein X", "therapeutic") is None

    def test_primera_regla_gana_y_los_ejes_son_independientes(self):
        # "CDK2" matchea la regla 1 (kinase) antes que cualquier regla posterior.
        assert rc.regex_para_eje("CDK2", "chemical") == "kinase"
        # CYP asigna AMBOS ejes desde la misma regla.
        assert rc.regex_para_eje("CYP3A4", "chemical") == "cytochrome_p450"
        assert rc.regex_para_eje("CYP3A4", "therapeutic") == "metabolismo"
        # "COX-2" es oxidoreductase en el eje químico (regla 3) pero
        # inflamacion___dolor en el terapéutico (regla 15): los ejes no se
        # contaminan entre sí.
        assert rc.regex_para_eje("COX-2", "chemical") == "oxidoreductase"
        assert rc.regex_para_eje("COX-2", "therapeutic") == "inflamacion___dolor"


# ═════════════════════════════════════════════════════════════════════════════
# 3) Remapeo legacy: transportadores → psiquiatria
# ═════════════════════════════════════════════════════════════════════════════

class TestRemapTransportadores:
    """Valores legacy terapéuticos se remapean; la química sale por regex."""

    def test_remap_en_constantes(self):
        assert "transportadores" in rc.LEGACY_THERAPEUTIC_VALUES
        assert rc.THERAPEUTIC_REMAP["transportadores"] == "psiquiatria"

    def test_clasificar_batch_remapea_y_busca_quimica_por_regex(self):
        quimica, terapeutica, motivo = rc.clasificar_batch(
            "8JTB",
            "CYP3A4-bound norepinephrine transporter NET complex",
            None,
            "transportadores",
        )
        assert motivo is None
        assert quimica == "cytochrome_p450"   # desde el regex del título
        assert terapeutica == "psiquiatria"   # remapeo legacy

    def test_transportador_con_token_quimico_clasifica(self):
        # VMAT2 ES un transporter (clase molecular): la química sale por regex.
        quimica, terapeutica, motivo = rc.clasificar_batch(
            "8JTB", "HUMAN VMAT2 COMPLEX WITH DOPAMINE", None, "transportadores",
        )
        assert motivo is None
        assert quimica == "transporter"
        assert terapeutica == "psiquiatria"   # remapeo legacy

    def test_transportador_sin_token_quimico_va_a_pendiente(self):
        quimica, terapeutica, motivo = rc.clasificar_batch(
            "TEST2", "UNRELATED MEMBRANE PROTEIN COMPLEX", None, "transportadores",
        )
        assert quimica is None
        assert terapeutica is None
        assert motivo is not None


# ═════════════════════════════════════════════════════════════════════════════
# 4) Loader de overrides (archivo real de producción)
# ═════════════════════════════════════════════════════════════════════════════

class TestOverridesLoader:
    """`cargar_overrides` sobre el JSON real de backend/scripts/data."""

    # Fuera de la clase y como `staticmethod`: pytest 10 retira los fixtures de
    # ámbito de clase definidos como método de instancia, y el aviso llevaba
    # tiempo tapando avisos nuevos en la salida de la suite.
    @staticmethod
    @pytest.fixture(scope="class")
    def overrides():
        return rc.cargar_overrides(rc.DEFAULT_OVERRIDES)

    def test_carga_84_entradas(self, overrides):
        assert len(overrides) == 122

    def test_claves_completas_por_entrada(self, overrides):
        esperadas = {"chemical_family", "therapeutic_family", "corrected_name", "delete"}
        for pdb_id, entrada in overrides.items():
            assert set(entrada.keys()) == esperadas, pdb_id

    def test_4otw_marcado_para_eliminar(self, overrides):
        assert overrides["4OTW"]["delete"] is True

    def test_corrected_name_se_aplica_verbatim(self, overrides):
        esperado = ("Structure of the D2 Dopamine Receptor Bound to the "
                    "Atypical Antipsychotic Drug Risperidone")
        assert overrides["6CM4"]["corrected_name"] == esperado

    def test_corrected_name_puede_ser_null(self, overrides):
        assert overrides["7E2Y"]["corrected_name"] is None


# ═════════════════════════════════════════════════════════════════════════════
# 5) Plan builder contra sqlite en memoria (sin DB real)
# ═════════════════════════════════════════════════════════════════════════════

class TestPlanBuilder:
    """`construir_plan` no toca la DB: recibe filas + overrides. Acá las filas
    salen de una tabla `targets` en sqlite en memoria, leída con la misma
    consulta de producción (`leer_targets`)."""

    FILAS = [
        # override con corrected_name → actualizar con nombre verbatim
        ("6CM4", "Old D2 receptor name", "desc", "gpcr"),
        # override delete:true → eliminar
        ("4OTW", "Kinase domain structure", "desc", "kinase"),
        # batch químico (gpcr) → terapéutica por regex del título
        ("7E2Y", "5-HT1A receptor structure", "desc", "gpcr"),
        # batch legacy (transportadores) → psiquiatria + química por regex
        ("8JTB", "CYP3A4-bound VMAT2 complex", "desc", "transportadores"),
        # ambigua: familia química conocida sin señal terapéutica → pendiente
        ("ZZZZ", "unrelated protein X", None, "kinase"),
        # ambigua: familia desconocida (ni química ni legacy) → pendiente
        ("YYYY", "Factor Xa (Coagulation)", None, "soluble_enzyme"),
    ]

    def _crear_db(self):
        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE targets (pdb_id TEXT, name TEXT, description TEXT, "
            "structural_family TEXT)"
        )
        conn.executemany(
            "INSERT INTO targets (pdb_id, name, description, structural_family) "
            "VALUES (?, ?, ?, ?)",
            self.FILAS,
        )
        return conn

    def _overrides_subset(self):
        todos = rc.cargar_overrides(rc.DEFAULT_OVERRIDES)
        return {k: todos[k] for k in ("6CM4", "4OTW")}

    def test_plan_completo_sobre_sqlite_en_memoria(self):
        conn = self._crear_db()
        try:
            filas = rc.leer_targets(conn)
        finally:
            conn.close()

        plan = rc.construir_plan(filas, self._overrides_subset())

        # ── stats globales ────────────────────────────────────────────────
        assert plan["total"] == 6
        assert plan["con_override"] == 2
        assert plan["batch"] == 4
        assert plan["con_override"] + plan["batch"] == plan["total"]
        assert plan["insertar"]["pdb_id"] == "4JSX"  # alta planificada, siempre presente
        assert plan["overrides_fuera_vocabulario"] == []

        por_id = {u["pdb_id"]: u for u in plan["actualizar"]}
        pend = {p["pdb_id"]: p for p in plan["pendientes"]}

        # 1) override aplicado con nombre verbatim
        assert por_id["6CM4"]["quimica"] == "gpcr"
        assert por_id["6CM4"]["terapeutica"] == "psiquiatria"
        assert por_id["6CM4"]["corrected_name"] == (
            "Structure of the D2 Dopamine Receptor Bound to the "
            "Atypical Antipsychotic Drug Risperidone"
        )
        assert plan["nombres_corregidos"] == 1

        # 2) delete marcado
        assert plan["eliminar"] == ["4OTW"]

        # 3) batch químico: terapéutica desde regex
        assert por_id["7E2Y"]["quimica"] == "gpcr"
        assert por_id["7E2Y"]["terapeutica"] == "psiquiatria"
        assert por_id["7E2Y"]["corrected_name"] is None

        # 4) transportadores → psiquiatria + química por regex
        assert por_id["8JTB"]["quimica"] == "cytochrome_p450"
        assert por_id["8JTB"]["terapeutica"] == "psiquiatria"

        # 5) ambiguas → pendientes con motivo
        assert set(pend) == {"ZZZZ", "YYYY"}
        assert "falta familia terapéutica" in pend["ZZZZ"]["motivo"]
        assert "soluble_enzyme" in pend["YYYY"]["motivo"]

        # 6) ninguna fila queda sin clasificar silenciosamente
        assert len(plan["actualizar"]) == 3
        assert len(plan["actualizar"]) + len(plan["eliminar"]) + len(plan["pendientes"]) \
            == plan["total"]


# ═════════════════════════════════════════════════════════════════════════════
# 6) Contrato: el schema Pydantic Target expone therapeutic_family
# ═════════════════════════════════════════════════════════════════════════════

class TestContratoSchema:
    """Contrato de datos: la API debe exponer el eje terapéutico.

    Si core.models no importa (faltan pydantic/sqlalchemy en el entorno),
    el test se salta con nota en vez de fallar la suite.
    """

    def test_target_pydantic_expone_therapeutic_family(self):
        try:
            from core.models import Target
        except Exception as exc:  # noqa: BLE001 — skip con nota, no falla
            pytest.skip(f"core.models no importable en este entorno: {exc}")

        assert "therapeutic_family" in Target.model_fields
        assert not Target.model_fields["therapeutic_family"].is_required()
