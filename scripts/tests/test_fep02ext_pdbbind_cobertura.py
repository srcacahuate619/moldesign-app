"""SCI-B-042: los 1438 receptores SIN_PDB no cuentan como SIN_HUECOS."""
import analisis_fep02ext_pdbbind_cobertura as a


def test_un_padre_sin_pdb_no_es_sin_huecos():
    ext = [{"pid": "x", "clasificacion": "SIN_HUECOS"}, {"pid": "y", "clasificacion": "SIN_HUECOS"}]
    c = a.reclasificar(ext, {"x": {"error": "SIN_PDB"}, "y": {}})
    assert c == {"SIN_FUENTE_SIN_PDB": 1, "SIN_HUECOS": 1}


def test_los_datos_sellados():
    r = a.analizar()
    assert r["sellado"]["SIN_HUECOS"] == 3648 and "ERROR" not in r["sellado"]
    assert r["con_estado_del_padre"]["SIN_FUENTE_SIN_PDB"] == 1438
    assert r["con_estado_del_padre"]["SIN_HUECOS"] == 2210 and r["evaluables"] == 3887
