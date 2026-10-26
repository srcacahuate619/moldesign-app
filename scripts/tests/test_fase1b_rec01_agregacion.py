"""SCI-B-148: tres retornos reales fallan; el adaptador externo los agrega sin tocar productor."""
import os,sys
from pathlib import Path
import pytest
HERE=Path(__file__).resolve().parents[1]
SCRIPTS=HERE if (HERE/"analisis_fase1b_rec01_agregacion.py").exists() else HERE/"scripts"
sys.path.insert(0,str(SCRIPTS))
import analisis_fase1b_rec01_agregacion as a
ROOT=Path(os.environ.get("FASE1B_REPO_ROOT",str(SCRIPTS.parent)))
def test_tres_rutas_tempranas_reproducen_KeyError():
    probes=a.sondas(ROOT)
    assert len(probes)==3
    assert all(p["error_agregacion_original"]=="'es_excepcion'" for p in probes)
    assert all(p["con_adaptador"]["excepciones"]["n_targets_con_excepcion"]==1 for p in probes)
def test_lectura_historica_se_separa_del_defecto_del_instrumento():
    r=a.analizar(ROOT)["SCI-B-148"]
    assert r["n_filas_selladas"]==387
    assert r["sin_flag_original"]==0
    assert r["excepciones_coinciden"] is True
def test_control_negativo_flag_que_oculta_excepcion_se_rechaza():
    row={"estrato":"INDETERMINADO","excepciones":["E6_SIN_PDB"],"es_excepcion":False}
    with pytest.raises(ValueError):a.normalizar_filas([row])
def test_ausencia_de_excepciones_no_se_interpreta_como_cero():
    with pytest.raises(ValueError):a.normalizar_filas([{"estrato":"INDETERMINADO"}])

