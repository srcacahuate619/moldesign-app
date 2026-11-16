"""B-11 (revisión final de 1.0.4): el comprobador del pipeline protege las dieciséis puertas, no nueve.

La sonda de la revisión quitó una puerta cada vez, en memoria, y el comprobador seguía pasando sin siete de ellas
(`check:runtime-arbol`, `check:openbabel-fuente`, `check:molcy-motor`, `check:openbabel`, `check:evaluation-runtime`,
`check:exported-api-url`, `check:no-remote-assets`). Que pase no prueba que el build haya corrido: prueba que
la configuración no perdió ninguna puerta ni su orden.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("check_release_pipeline", RAIZ / "scripts" / "check_release_pipeline.py")
cp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cp)


def _comandos_reales() -> list[str]:
    tauri = json.loads((RAIZ / "frontend" / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
    return [c.strip() for c in tauri["build"]["beforeBuildCommand"].split("&&")]


def test_las_requeridas_son_exactamente_las_dieciseis_de_la_configuracion_y_en_su_orden():
    assert len(cp.REQUERIDAS) == 16
    assert cp.REQUERIDAS == _comandos_reales()


@pytest.mark.parametrize("i", range(16))
def test_quitar_cualquier_puerta_hace_fallar_al_comprobador(i):
    sin = cp.REQUERIDAS[:i] + cp.REQUERIDAS[i + 1:]
    with pytest.raises(RuntimeError, match="no ejecuta"):
        cp.verificar_comandos(sin)


def test_el_orden_importa_el_artefacto_se_mira_despues_del_staging():
    comandos = list(cp.REQUERIDAS)
    a, b = comandos.index("npm run stage:desktop"), comandos.index("npm run check:openbabel")
    comandos[a], comandos[b] = comandos[b], comandos[a]
    with pytest.raises(RuntimeError, match="desordenado"):
        cp.verificar_comandos(comandos)


def test_la_configuracion_actual_pasa():
    cp.verificar_comandos(_comandos_reales())


def test_el_autotest_del_propio_comprobador_corre():
    cp.autotest()
