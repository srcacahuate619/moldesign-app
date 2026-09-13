"""El runtime que se empaqueta, y el verificador que tiene que verlo fallar.

Auditoría de backend del 2026-09-04, §1. Dos defectos encadenados que juntos
dejaban salir un instalador en el que `torch` no carga.

═══════════════════════════════════════════════════════════════════════════
1. El redist de Visual C++ se elegía ordenando una RUTA
═══════════════════════════════════════════════════════════════════════════

`bundle_helper` hacía `sorted(raiz_vs.glob(...), reverse=True)` suponiendo que
la carpeta más nueva quedaría primero. El nombre del directorio de Visual
Studio no es un número de versión, y como texto:

    "Microsoft Visual Studio/2019/..."  >  "Microsoft Visual Studio/18/..."

porque '2' > '1' en el primer carácter. Medido en la máquina de construcción:

    ganaba      2019/.../MSVC/14.29.30133/x64/Microsoft.VC142.CRT   msvcp140 14.29.30157
    disponible    18/.../MSVC/14.50.35710/x64/Microsoft.VC145.CRT   msvcp140 14.50.35719

Y `ProgramFiles(x86)` se recorría antes que `ProgramFiles`, así que un VS de 32
bits ganaba a uno de 64 aunque el orden interno hubiera sido correcto.

Resultado: `msvcp140.dll` 14.29 al lado de binarios compilados contra 14.38+.
`torch` no carga —`WinError 1114`— y ADMET devuelve None en todo. Invisible en
esta máquina, donde System32 tiene un runtime nuevo: en una instalación limpia
manda la DLL del directorio del binario.

═══════════════════════════════════════════════════════════════════════════
2. El verificador importaba en un orden que el producto no usa
═══════════════════════════════════════════════════════════════════════════

La sonda hacía `...,sklearn,xgboost,torch,...` y sólo después `from api.main
import app`. En producción el orden es el contrario: se arranca por `api.main`
y se llega a torch a través de ADMET. Importar xgboost primero deja cargado un
runtime de Visual C++ que torch luego acepta, así que la sonda pasaba haciendo
algo que el producto no hace.

Un verificador que reordena para que le salga bien no verifica nada.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
VERIFY = RAIZ / "scripts" / "verify_desktop_bundle.py"

_SPEC = importlib.util.spec_from_file_location(
    "moldesign_bundle_helper_runtime", RAIZ / "scripts" / "bundle_helper.py"
)
assert _SPEC and _SPEC.loader
_BH = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BH)


def _sonda() -> str:
    """El código Python que `validate_runtime` ejecuta dentro del bundle."""
    fuente = VERIFY.read_text(encoding="utf-8")
    bloque = re.search(r"import_probe = \((.*?)\n    \)", fuente, re.S)
    assert bloque, "no se encontró `import_probe` en verify_desktop_bundle.py"
    return "".join(re.findall(r'"([^"]*)"', bloque.group(1)))


# ── El redist ────────────────────────────────────────────────────────────

def test_la_version_del_redist_se_parsea_del_nombre_de_carpeta():
    version = _BH.__dict__.get("_version_msvc")
    if version is None:  # vive dentro de stage_resources
        fuente = (RAIZ / "scripts" / "bundle_helper.py").read_text(encoding="utf-8")
        assert "def _version_msvc" in fuente, (
            "desapareció el parseo de versión del redist: se habría vuelto a "
            "ordenar por la ruta, que es lo que elegía el 14.29 sobre el 14.50"
        )


def test_no_se_ordenan_las_carpetas_del_redist_por_su_ruta():
    """La regresión concreta: `sorted(glob(...), reverse=True)` sobre rutas."""
    fuente = (RAIZ / "scripts" / "bundle_helper.py").read_text(encoding="utf-8")
    assert "sorted(raiz_vs.glob(" not in fuente, (
        "el redist volvió a elegirse ordenando la ruta como texto. "
        '"2019" > "18" en ese orden, así que gana el Visual Studio más viejo.'
    )
    assert "key=_version_msvc" in fuente, (
        "las carpetas del redist ya no se ordenan por versión de MSVC"
    )


def test_las_dos_bases_de_program_files_se_ordenan_juntas():
    """Ordenar cada base por separado deja que la de 32 bits siga ganando."""
    fuente = (RAIZ / "scripts" / "bundle_helper.py").read_text(encoding="utf-8")
    indice_recogida = fuente.index("candidatas.append(carpeta)")
    indice_orden = fuente.index("candidatas.sort(key=_version_msvc")
    assert indice_orden > indice_recogida, (
        "se ordena antes de haber recogido las dos bases: ProgramFiles(x86) "
        "volvería a tener preferencia sobre ProgramFiles"
    )


# ── El verificador ───────────────────────────────────────────────────────

def test_la_sonda_importa_en_el_orden_de_produccion():
    sonda = _sonda()
    assert "from api.main import app" in sonda, "la sonda dejó de arrancar por api.main"

    pos_main = sonda.index("from api.main import app")
    pos_torch = sonda.index("import torch")
    pos_xgb = sonda.index("xgboost")

    assert pos_main < pos_torch, (
        "la sonda importa torch antes que api.main: no es el orden con el que "
        "arranca el backend"
    )
    assert pos_torch < pos_xgb, (
        "la sonda volvió a importar xgboost antes que torch. Ese orden deja "
        "cargado un runtime de Visual C++ que torch luego acepta, y esconde "
        "exactamente el fallo que este gate existe para encontrar."
    )


def test_la_sonda_no_se_conforma_con_que_admet_importe():
    """El síntoma de la DLL mala no es una excepción: es un None en todo."""
    sonda = _sonda()
    assert "predict_admet_ai(" in sonda, (
        "la sonda ya no ejerce una predicción de ADMET. Con el runtime "
        "incompatible el import funciona y la predicción devuelve None: "
        "comprobar sólo el import no distingue los dos casos."
    )
    assert "_vivos" in sonda and "assert _vivos" in sonda, (
        "la sonda llama a ADMET pero no comprueba que haya devuelto algo"
    )


def test_la_sonda_es_python_valido():
    """Se ejecuta con `python -c` dentro del bundle: un error de sintaxis
    ahí no se ve hasta que alguien corre el gate entero."""
    import ast

    ast.parse(_sonda())
