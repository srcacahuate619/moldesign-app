"""ENG-001 — el menú avanzado no puede ofrecer motores que esta build no ejecuta.

Auditoría del 2026-09-01, antes de la primera build pública. El modal de opciones
avanzadas ofrece siete motores. Lo que hay realmente detrás:

* **AutoDock Vina 1.2.7** — real. Es el binario que el instalador empaqueta.
* **QuickVina 2** — `settings.qvina2_executable_path` vale `"qvina2"` y ese binario
  **no se distribuye** (`frontend/src-tauri/resources/tools/` trae vina, xtb y
  llama). `vina_service` cae a Vina con `exhaustiveness=4` escribiendo sólo un
  `log.warning`; el preflight del caso sí lo bloquea.
* **DiffDock** — `diffdock_api_url` es `None` por defecto: el servicio es un cliente
  HTTP a un servidor externo que nadie levanta.
* **ESMFold** — su servicio SÍ existía en el árbol (`<raíz>/esmfold/`), pero el
  instalador no lo copiaba, nadie lo encendía y cargaba el checkpoint por nombre
  contra HuggingFace en vez de leer los pesos descargados. Desde ENG-002 es un
  motor **descargable**: `services/motores` sabe si está, lo enciende y lo apaga.
  Ver `test_motores_descargables.py`.
* **ESMFold Pro / RFdiffusion** — sidecar en `localhost:8300`, que sigue sin
  existir en este árbol.
* **ColabFold** — `colabfold_api_url` es `None`.

El fallo no es que falten: es que **la interfaz no lo dice**, y la ruta peptídica
cae a Vina con `exhaustiveness=4` y una caja fija de (20, 30, 28) cuando el
servicio no responde. `GET /evaluation/engines` existe para que la interfaz
apague lo que no se puede ejecutar, con su motivo, en vez de ofrecerlo.
"""

from __future__ import annotations

import inspect
from pathlib import Path

from api.routers import evaluation as evaluation_router

ROOT = Path(__file__).resolve().parents[2]
MODAL = ROOT / "frontend" / "components" / "interfaces" / "pro" / "ProOptionsModal.tsx"

IDS_ESPERADOS = {
    "vina",
    "qvina2",
    "diffdock",
    "esmfold",
    "esmfold-pro",
    "esmfold-experimental",
    "colabfold",
}


def test_el_endpoint_declara_los_siete_motores_del_menu():
    inventario = evaluation_router.inventario_de_motores()
    ids = {m["id"] for m in inventario["docking"]} | {m["id"] for m in inventario["peptido"]}
    assert ids == IDS_ESPERADOS, (
        "el inventario y el menú tienen que hablar de los mismos motores; "
        f"sobran/faltan: {ids ^ IDS_ESPERADOS}"
    )


def test_cada_motor_no_disponible_explica_por_que():
    inventario = evaluation_router.inventario_de_motores()
    for motor in inventario["docking"] + inventario["peptido"]:
        if not motor["disponible"]:
            assert motor["motivo"], f"{motor['id']} no disponible y sin motivo declarado"
            assert len(motor["motivo"]) > 20, f"{motor['id']}: el motivo no explica nada"


def test_vina_es_el_unico_que_esta_disponible_de_fabrica():
    """Los demás exigen un binario o un servicio que este instalador no trae.

    Si algún día se empaqueta QuickVina o se levanta un sidecar, esta prueba
    fallará y habrá que actualizarla A PROPÓSITO. Es la señal de que la promesa
    del menú cambió.
    """
    inventario = evaluation_router.inventario_de_motores()
    disponibles = {
        m["id"] for m in inventario["docking"] + inventario["peptido"] if m["disponible"]
    }
    assert disponibles <= {"vina"}, (
        f"declara disponible algo que este árbol no distribuye: {disponibles - {'vina'}}"
    )


def test_los_motores_dicen_de_que_dependen():
    """Dos familias distintas, y la diferencia importa para el investigador.

    `descarga_bajo_demanda` es un motor que la aplicación sabe instalar y
    encender: ESMFold entra ahí desde que existe `services/motores`. Los demás
    siguen siendo `servicio_externo`, que significa «hay que levantarlo fuera»,
    y ninguna acción de la interfaz los va a resolver.
    """
    inventario = evaluation_router.inventario_de_motores()
    por_id = {m["id"]: m for m in inventario["docking"] + inventario["peptido"]}

    assert por_id["esmfold"]["requiere"] == "descarga_bajo_demanda"
    assert por_id["esmfold"]["modulo_launcher"], (
        "un motor descargable tiene que decir de qué módulo del launcher sale"
    )

    for engine_id in ("diffdock", "esmfold-pro", "esmfold-experimental", "colabfold"):
        motor = por_id[engine_id]
        assert motor["requiere"] == "servicio_externo", (
            f"{engine_id} depende de un servicio HTTP externo y el contrato debe decirlo"
        )


def test_todo_motor_declara_estado_y_accion():
    """`disponible: false` sin más manda a mirar al sitio equivocado."""
    inventario = evaluation_router.inventario_de_motores()
    for motor in inventario["docking"] + inventario["peptido"]:
        assert "estado" in motor, f"{motor['id']} no declara estado"
        assert "accion" in motor, f"{motor['id']} no declara acción"
        if not motor["disponible"]:
            assert motor["motivo"], f"{motor['id']} no disponible y sin motivo"


def test_el_modal_no_ofrece_un_motor_sin_consultar_el_inventario():
    """La interfaz tiene que apagar lo que el backend declara no disponible."""
    fuente = MODAL.read_text(encoding="utf-8")
    assert "/evaluation/engines" in fuente or "inventarioDeMotores" in fuente, (
        "el modal de opciones avanzadas sigue ofreciendo los siete motores sin "
        "preguntar cuáles existen"
    )


def test_la_ruta_peptidica_no_inventa_una_caja_de_docking():
    """El fallback usaba (20, 30, 28) y 30 Å cuando no le pasaban grid.

    Docking en una caja arbitraria no es un resultado degradado: es un resultado
    de otro sitio. Sin caja, la ruta tiene que fallar y decirlo.
    """
    fuente = inspect.getsource(
        __import__("services.docking.peptide_docking", fromlist=["run_peptide_docking_helper"])
    )
    assert "else 20.0" not in fuente and "else 30.0" not in fuente, (
        "el fallback peptídico sigue inventando el centro y el tamaño de la caja"
    )
