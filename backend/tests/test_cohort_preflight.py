"""
Comprobación previa de cohortes: lo que se conserva, lo que bloquea y lo que identifica.

Estas pruebas fijan el NÚCLEO del contrato, sin HTTP. Lo que protegen, en orden
de gravedad:

1. **El denominador es el del archivo.** Ninguna fila desaparece: ni un SMILES
   vacío, ni uno ilegible, ni un duplicado. Si desaparecieran, la cobertura
   mediría sobre una población recortada y una cohorte del 60 % se presentaría
   como una del 100 %.

2. **Ningún control se infiere.** Un nombre que empiece por «ref», una etiqueta
   `active=1` o la primera fila del archivo NO convierten nada en control. El
   día que se calcule enriquecimiento, un control inventado decide el veredicto.

3. **La identidad es reproducible y no depende del reloj.** Dos comprobaciones
   de la misma cohorte dan el mismo fingerprint; cambiar receptor, configuración
   o una molécula lo cambia.

4. **No se ejecuta nada.** Sin docking, sin ML, sin tareas de fondo, sin score.
"""

from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone

import pytest

from services.cohort.fingerprint import FingerprintRow, canonical_cohort_document
from services.cohort.parser import read_cohort_file
from services.cohort.preflight import build_cohort_preflight
from services.cohort.schemas import CohortStudy
from services.cohort import taxonomy as tx
from tests.conftest import rdkit_available

# ── Moléculas que el validador del producto SÍ evalúa ────────────────
# El validador exige un mínimo de átomos pesados, así que las moléculas de
# juguete tipo «CCO» no sirven para probar el camino elegible: saldrían
# `SMILES_NO_ADMISIBLE` y estaríamos probando la política química, no la ingesta.
ASPIRINA = "CC(=O)Oc1ccccc1C(=O)O"
IBUPROFENO = "CC(C)Cc1ccc(cc1)C(C)C(=O)O"
PARACETAMOL = "CC(=O)Nc1ccc(O)cc1"
CAFEINA = "Cn1cnc2c1c(=O)n(C)c(=O)n2C"

#: Escrita al revés: la misma molécula, otro texto. Es el duplicado canónico
#: que un `==` sobre cadenas no detectaría.
ASPIRINA_REESCRITA = "OC(=O)c1ccccc1OC(C)=O"

#: Legible por RDKit, rechazada por la política química del producto (3 átomos
#: pesados). Separa «no te entiendo» de «te entiendo y no te evalúo».
ETANOL = "CCO"

ILEGIBLE = "CCX"


def estudio(**overrides) -> CohortStudy:
    """Cohorte mínima y completamente declarada."""
    base = {
        "schema_version": 1,
        "name": "Serie de anilinas",
        "receptor": {"pdb_id": "7E2Y", "chain": "A"},
        "config": {
            "docking_engine": "vina",
            "exhaustiveness": 8,
            "num_poses": 5,
            "grid_center": [10.0, 11.0, 12.0],
            "grid_size": [22.0, 22.0, 22.0],
            "seed": 42,
        },
    }
    for clave, valor in overrides.items():
        if clave == "config":
            base["config"] = {**base["config"], **valor}  # type: ignore[dict-item]
        elif clave == "receptor":
            base["receptor"] = {**base["receptor"], **valor}  # type: ignore[dict-item]
        else:
            base[clave] = valor
    return CohortStudy.model_validate(base)


def csv_bytes(*lineas: str) -> bytes:
    return "\n".join(lineas).encode("utf-8")


def preflight(contenido: bytes, nombre: str = "cohorte.csv", **kwargs):
    return build_cohort_preflight(
        study=kwargs.pop("study", estudio()),
        filename=nombre,
        content=contenido,
        **kwargs,
    )


# ── 1. CSV válido ────────────────────────────────────────────────────


@rdkit_available
def test_csv_valido_produce_una_cohorte_lista():
    resultado = preflight(
        csv_bytes(
            "name,smiles",
            f"aspirina,{ASPIRINA}",
            f"ibuprofeno,{IBUPROFENO}",
            f"paracetamol,{PARACETAMOL}",
        )
    )

    assert resultado.decision == tx.READY
    assert resultado.blockers == []
    assert resultado.summary.total_rows == 3
    assert resultado.summary.eligible_rows == 3
    assert resultado.summary.invalid_rows == 0
    assert resultado.summary.unique_canonical_ligands == 3
    assert [fila.source_name for fila in resultado.rows] == [
        "aspirina",
        "ibuprofeno",
        "paracetamol",
    ]
    assert all(fila.eligibility == tx.ELIGIBLE for fila in resultado.rows)
    # El canónico se devuelve para que el lector sepa qué se va a acoplar.
    assert all(fila.canonical_smiles for fila in resultado.rows)


# ── 2. Otro formato ya soportado por Batch ───────────────────────────


@rdkit_available
def test_formato_smiles_txt_se_ingiere_igual():
    contenido = "\n".join(
        [
            "# cohorte de prueba",
            f"{ASPIRINA} aspirina 1 reference",
            f"{IBUPROFENO} ibuprofeno 0 none",
            "",
        ]
    ).encode("utf-8")

    resultado = preflight(contenido, "cohorte.smi")

    assert resultado.summary.total_rows == 2
    assert resultado.summary.eligible_rows == 2
    assert resultado.rows[0].control_role == "reference"
    assert resultado.rows[0].active_label is True
    assert resultado.rows[1].active_label is False
    # Comentarios y líneas en blanco son separadores del formato, no moléculas
    # que alguien haya declarado y se hayan perdido.
    assert resultado.summary.input_coverage_denominator == 2


@rdkit_available
def test_formato_sdf_conserva_registros_ilegibles():
    from rdkit import Chem

    bloque = Chem.MolToMolBlock(Chem.MolFromSmiles(ASPIRINA))
    sdf = f"{bloque}$$$$\nbasura que no es un molblock\n$$$$\n".encode("utf-8")

    resultado = preflight(sdf, "cohorte.sdf")

    assert resultado.summary.total_rows == 2
    assert resultado.summary.eligible_rows == 1
    assert resultado.rows[1].eligibility == tx.INVALID_INPUT
    assert tx.REGISTRO_ILEGIBLE in resultado.rows[1].reasons


@rdkit_available
def test_formato_excel_conserva_la_fila_vacia_intercalada_y_no_la_del_relleno():
    openpyxl = pytest.importorskip("openpyxl")

    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.append(["name", "smiles"])
    hoja.append(["aspirina", ASPIRINA])
    hoja.append([None, None])
    hoja.append(["ibuprofeno", IBUPROFENO])
    # Relleno del final: openpyxl lo fabrica a partir de la dimensión declarada
    # de la hoja y no son moléculas que nadie haya escrito.
    hoja.append([None, None])
    hoja.append([None, None])
    buffer = io.BytesIO()
    libro.save(buffer)

    resultado = preflight(buffer.getvalue(), "cohorte.xlsx")

    # Tres filas: dos moléculas y el hueco que alguien dejó entre ellas.
    assert resultado.summary.total_rows == 3
    assert resultado.summary.eligible_rows == 2
    assert resultado.rows[1].reasons == [tx.SMILES_AUSENTE]


def test_formato_desconocido_bloquea():
    resultado = preflight(b"lo que sea", "cohorte.docx")

    assert resultado.decision == tx.BLOCKED
    assert tx.FORMATO_NO_SOPORTADO in resultado.blockers


def test_archivo_ilegible_bloquea():
    # Bytes que no son UTF-8. NO se sustituyen por U+FFFD: eso convertiría un
    # archivo corrupto en un archivo lleno de moléculas «ilegibles» y culparía
    # a la química de un problema del archivo.
    resultado = preflight(b"smiles\n\xff\xfe\x00\x01", "cohorte.csv")

    assert resultado.decision == tx.BLOCKED
    assert tx.ARCHIVO_ILEGIBLE in resultado.blockers


def test_sin_columna_de_estructura_bloquea_pero_conserva_las_filas():
    resultado = preflight(csv_bytes("name,active", "aspirina,1", "ibuprofeno,0"))

    assert resultado.decision == tx.BLOCKED
    assert tx.COLUMNA_SMILES_AUSENTE in resultado.blockers
    # Las filas siguen ahí: el archivo tenía dos, y el recuento lo dice.
    assert resultado.summary.total_rows == 2
    assert all(tx.SMILES_AUSENTE in fila.reasons for fila in resultado.rows)


# ── 3. SMILES inválido conservado ────────────────────────────────────


@rdkit_available
def test_smiles_ilegible_se_conserva_como_invalid_input():
    resultado = preflight(
        csv_bytes("name,smiles", f"buena,{ASPIRINA}", f"rota,{ILEGIBLE}")
    )

    assert resultado.summary.total_rows == 2
    assert resultado.summary.eligible_rows == 1
    rota = resultado.rows[1]
    assert rota.eligibility == tx.INVALID_INPUT
    assert rota.reasons == [tx.SMILES_ILEGIBLE]
    # Se conserva lo que la persona escribió, para que pueda corregirlo.
    assert rota.input_smiles == ILEGIBLE
    assert rota.canonical_smiles is None
    assert tx.FILAS_INVALIDAS in resultado.warnings


@rdkit_available
def test_molecula_legible_pero_no_admisible_se_distingue_de_una_ilegible():
    resultado = preflight(csv_bytes("name,smiles", f"etanol,{ETANOL}"))

    fila = resultado.rows[0]
    assert fila.eligibility == tx.INVALID_INPUT
    assert fila.reasons == [tx.SMILES_NO_ADMISIBLE]
    # Se lee perfectamente: el canónico está ahí. Lo que pasa es que este
    # producto no la evalúa, y decir «SMILES ilegible» mandaría a la persona a
    # revisar una sintaxis que es correcta.
    assert fila.canonical_smiles == "CCO"
    assert resultado.decision == tx.BLOCKED
    assert tx.SIN_MOLECULAS_ELEGIBLES in resultado.blockers


# ── 4. Fila vacía conservada ─────────────────────────────────────────


@rdkit_available
def test_fila_vacia_se_conserva_y_se_cuenta():
    resultado = preflight(
        csv_bytes("name,smiles", f"aspirina,{ASPIRINA}", "", f"ibuprofeno,{IBUPROFENO}")
    )

    # Tres filas de datos, no dos: la vacía cuenta en el denominador.
    assert resultado.summary.total_rows == 3
    assert resultado.summary.eligible_rows == 2
    vacia = resultado.rows[1]
    assert vacia.row_index == 1
    assert vacia.input_smiles == ""
    assert vacia.reasons == [tx.SMILES_AUSENTE]
    assert resultado.summary.input_coverage == pytest.approx(2 / 3, abs=1e-6)


# ── 5. Duplicados canónicos ──────────────────────────────────────────


@rdkit_available
def test_duplicados_canonicos_se_declaran_y_apuntan_a_la_primera_fila():
    resultado = preflight(
        csv_bytes(
            "name,smiles",
            f"aspirina,{ASPIRINA}",
            f"ibuprofeno,{IBUPROFENO}",
            f"aspirina-otra-escritura,{ASPIRINA_REESCRITA}",
        )
    )

    duplicada = resultado.rows[2]
    assert duplicada.duplicate_of_row == 0
    assert tx.SMILES_DUPLICADO in duplicada.warnings
    # NO se excluye: sigue siendo elegible y sigue contando en el total.
    assert duplicada.eligibility == tx.ELIGIBLE
    assert resultado.summary.total_rows == 3
    assert resultado.summary.eligible_rows == 3
    assert resultado.summary.duplicate_rows == 1
    # Dos moléculas distintas, tres filas.
    assert resultado.summary.unique_canonical_ligands == 2
    assert tx.DUPLICADOS_CANONICOS in resultado.warnings


# ── 6. Etiquetas active opcionales ───────────────────────────────────


@rdkit_available
def test_sin_etiquetas_active_avisa_pero_no_bloquea():
    resultado = preflight(csv_bytes("name,smiles", f"aspirina,{ASPIRINA}"))

    assert resultado.decision == tx.READY
    assert tx.SIN_ETIQUETAS_ACTIVE in resultado.warnings
    assert resultado.rows[0].active_label is None


@rdkit_available
def test_etiqueta_active_ilegible_no_invalida_la_fila_ni_se_adivina():
    resultado = preflight(
        csv_bytes("name,smiles,active", f"aspirina,{ASPIRINA},quizás")
    )

    fila = resultado.rows[0]
    assert fila.eligibility == tx.ELIGIBLE
    assert fila.active_label is None
    assert tx.ETIQUETA_ACTIVE_INVALIDA in fila.warnings


# ── 7 y 8. Controles: explícitos o ninguno ───────────────────────────


@rdkit_available
def test_roles_de_control_explicitos_se_cuentan_por_rol():
    resultado = preflight(
        csv_bytes(
            "name,smiles,control_role",
            f"ref,{ASPIRINA},reference",
            f"pos,{IBUPROFENO},positive",
            f"neg,{PARACETAMOL},negative",
            f"otra,{CAFEINA},none",
        )
    )

    assert resultado.summary.explicit_reference_controls == 1
    assert resultado.summary.explicit_positive_controls == 1
    assert resultado.summary.explicit_negative_controls == 1
    assert tx.SIN_CONTROLES_DECLARADOS not in resultado.warnings


@rdkit_available
def test_ningun_control_se_infiere_del_nombre_de_la_etiqueta_ni_del_orden():
    resultado = preflight(
        csv_bytes(
            "name,smiles,active",
            # Nombres que invitan a inferir, etiquetas que invitan a inferir, y
            # la primera posición del archivo. Ninguna de las tres cosas es una
            # declaración de control.
            f"reference_compound,{ASPIRINA},1",
            f"control positivo,{IBUPROFENO},1",
            f"decoy,{PARACETAMOL},0",
        )
    )

    assert resultado.summary.explicit_reference_controls == 0
    assert resultado.summary.explicit_positive_controls == 0
    assert resultado.summary.explicit_negative_controls == 0
    assert all(fila.control_role == "none" for fila in resultado.rows)
    assert tx.SIN_CONTROLES_DECLARADOS in resultado.warnings


@rdkit_available
def test_un_rol_fuera_del_vocabulario_no_se_aproxima_al_mas_parecido():
    resultado = preflight(
        csv_bytes("name,smiles,control_role", f"ref,{ASPIRINA},reference_compound")
    )

    fila = resultado.rows[0]
    assert fila.control_role == "none"
    assert tx.ROL_CONTROL_INVALIDO in fila.warnings
    assert resultado.summary.explicit_reference_controls == 0


# ── 12. Cohorte sin filas elegibles ──────────────────────────────────


@rdkit_available
def test_cohorte_sin_moleculas_elegibles_bloquea():
    resultado = preflight(csv_bytes("name,smiles", f"a,{ILEGIBLE}", "b,"))

    assert resultado.decision == tx.BLOCKED
    assert tx.SIN_MOLECULAS_ELEGIBLES in resultado.blockers
    assert resultado.summary.eligible_rows == 0
    assert resultado.summary.input_coverage == 0.0
    assert resultado.summary.input_coverage_denominator == 2


def test_cohorte_sin_ninguna_fila_bloquea_y_la_cobertura_no_es_nan():
    resultado = preflight(csv_bytes("name,smiles"))

    assert resultado.decision == tx.BLOCKED
    assert tx.COHORTE_VACIA in resultado.blockers
    # Sin denominador no hay cobertura que medir. `0.0` afirmaría un 0 % medido
    # sobre nada; NaN o ±Infinity ni siquiera serían JSON válido.
    assert resultado.summary.input_coverage is None
    assert resultado.summary.input_coverage_denominator == 0
    serializado = resultado.model_dump_json()
    assert "NaN" not in serializado
    assert "Infinity" not in serializado


# ── 16. Cobertura y su denominador ───────────────────────────────────


@rdkit_available
def test_input_coverage_es_elegibles_sobre_total():
    resultado = preflight(
        csv_bytes(
            "name,smiles",
            f"a,{ASPIRINA}",
            f"b,{IBUPROFENO}",
            f"c,{ILEGIBLE}",
            "d,",
        )
    )

    assert resultado.summary.total_rows == 4
    assert resultado.summary.eligible_rows == 2
    assert resultado.summary.input_coverage == pytest.approx(0.5)
    assert resultado.summary.input_coverage_denominator == 4
    assert (
        resultado.summary.eligible_rows + resultado.summary.invalid_rows
        == resultado.summary.total_rows
    )


# ── 13, 14 y 15. Fingerprint ─────────────────────────────────────────


@rdkit_available
def test_fingerprint_identico_con_la_misma_entrada():
    contenido = csv_bytes("name,smiles", f"a,{ASPIRINA}", f"b,{IBUPROFENO}")

    primera = preflight(contenido)
    segunda = preflight(contenido)

    assert primera.cohort_fingerprint == segunda.cohort_fingerprint


@rdkit_available
def test_generated_at_no_altera_el_fingerprint():
    contenido = csv_bytes("name,smiles", f"a,{ASPIRINA}")
    ahora = datetime(2026, 8, 24, 10, 0, tzinfo=timezone.utc)

    primera = preflight(contenido, generated_at=ahora)
    segunda = preflight(contenido, generated_at=ahora + timedelta(days=400))

    assert primera.generated_at != segunda.generated_at
    assert primera.cohort_fingerprint == segunda.cohort_fingerprint


@rdkit_available
def test_el_nombre_del_estudio_y_el_del_archivo_no_entran_en_la_identidad():
    contenido = csv_bytes("name,smiles", f"a,{ASPIRINA}")

    original = preflight(contenido, "cohorte.csv")
    renombrada = preflight(
        contenido, "otro-archivo.csv", study=estudio(name="Otro título distinto")
    )

    # Renombrar un estudio o su archivo no cambia la ciencia que se va a hacer.
    assert original.cohort_fingerprint == renombrada.cohort_fingerprint


@rdkit_available
@pytest.mark.parametrize(
    "cambio",
    [
        pytest.param({"receptor": {"pdb_id": "3PP0"}}, id="receptor"),
        pytest.param({"receptor": {"chain": "B"}}, id="cadena"),
        pytest.param({"config": {"exhaustiveness": 16}}, id="exhaustividad"),
        pytest.param({"config": {"num_poses": 9}}, id="poses"),
        pytest.param({"config": {"docking_engine": "qvina2"}}, id="motor"),
        pytest.param({"config": {"seed": 7}}, id="semilla"),
        pytest.param({"config": {"grid_center": [1.0, 2.0, 3.0]}}, id="centro"),
        pytest.param({"config": {"grid_size": [30.0, 30.0, 30.0]}}, id="caja"),
    ],
)
def test_fingerprint_cambia_al_cambiar_la_ciencia(cambio):
    contenido = csv_bytes("name,smiles", f"a,{ASPIRINA}")

    original = preflight(contenido)
    modificada = preflight(contenido, study=estudio(**cambio))

    assert original.cohort_fingerprint != modificada.cohort_fingerprint


@rdkit_available
def test_fingerprint_cambia_al_cambiar_una_molecula_una_etiqueta_o_un_rol():
    base = csv_bytes(
        "name,smiles,active,control_role",
        f"a,{ASPIRINA},1,reference",
        f"b,{IBUPROFENO},0,none",
    )
    huella = preflight(base).cohort_fingerprint

    otra_molecula = csv_bytes(
        "name,smiles,active,control_role",
        f"a,{ASPIRINA},1,reference",
        f"b,{PARACETAMOL},0,none",
    )
    otra_etiqueta = csv_bytes(
        "name,smiles,active,control_role",
        f"a,{ASPIRINA},0,reference",
        f"b,{IBUPROFENO},0,none",
    )
    otro_rol = csv_bytes(
        "name,smiles,active,control_role",
        f"a,{ASPIRINA},1,positive",
        f"b,{IBUPROFENO},0,none",
    )

    assert preflight(otra_molecula).cohort_fingerprint != huella
    assert preflight(otra_etiqueta).cohort_fingerprint != huella
    assert preflight(otro_rol).cohort_fingerprint != huella


@rdkit_available
def test_la_misma_molecula_escrita_de_otra_forma_no_cambia_la_identidad():
    # El fingerprint se toma sobre el CANÓNICO: «CCO» y «OCC» son la misma
    # cohorte, y decir lo contrario invalidaría un preflight por una reescritura.
    uno = preflight(csv_bytes("name,smiles", f"a,{ASPIRINA}"))
    otro = preflight(csv_bytes("name,smiles", f"a,{ASPIRINA_REESCRITA}"))

    assert uno.cohort_fingerprint == otro.cohort_fingerprint


def test_el_documento_canonico_no_contiene_nada_del_entorno():
    documento = canonical_cohort_document(
        estudio(name="Un nombre descriptivo"),
        [FingerprintRow(molecule=ASPIRINA, active_label=True, control_role="reference")],
    )

    for prohibido in ("generated_at", "workers", "Un nombre descriptivo", "cohorte.csv", "user"):
        assert prohibido not in documento
    assert '"contract":"cohort_preflight/v1"' in documento


# ── 17. No se ejecuta nada ───────────────────────────────────────────


@rdkit_available
def test_la_comprobacion_previa_no_ejecuta_docking_ni_produce_scores(monkeypatch):
    import asyncio

    import services.docking.vina_service as vina

    def _prohibido(*args, **kwargs):
        raise AssertionError("La comprobación previa NO puede ejecutar docking.")

    monkeypatch.setattr(vina, "run_vina_docking", _prohibido)
    monkeypatch.setattr(asyncio, "create_task", _prohibido)

    resultado = preflight(
        csv_bytes("name,smiles", f"a,{ASPIRINA}", f"b,{IBUPROFENO}")
    )

    assert resultado.decision == tx.READY
    # Y no aparece ningún número que pueda leerse como un veredicto.
    serializado = resultado.model_dump_json()
    for prohibido in ("total_score", "affinity", "score", "ef_", "roc", "auc"):
        assert prohibido not in serializado.lower()


# ── Lectura sin interpretación ───────────────────────────────────────


def test_la_ingesta_no_interpreta_las_etiquetas():
    # El lector devuelve texto crudo. Interpretar `active` es una decisión con
    # taxonomía y pertenece al preflight, no al que abre el archivo.
    lectura = read_cohort_file(
        "c.csv", csv_bytes("smiles,active,control_role", "CCO,quizás,reference_compound")
    )

    assert lectura.rows[0].active_raw == "quizás"
    assert lectura.rows[0].control_role_raw == "reference_compound"
