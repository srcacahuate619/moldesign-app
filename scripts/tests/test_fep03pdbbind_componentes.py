"""SCI-B-008: los ligandos conectados de FEP-03-PDBBIND se cuentan por componente conexo."""
import analisis_fep03pdbbind_componentes as a


def test_dos_parejas_sueltas_no_son_una_red():
    # control negativo: A-B y C-D dan 4 extremos pero un componente de 2
    f = a.por_diana([("A", "B"), ("C", "D")], {"A": 0, "C": 0})[0]
    assert f["extremos"] == 4 and f["mayor_componente"] == 2 and f["n_componentes"] == 2


def test_una_cadena_es_un_componente():
    f = a.por_diana([("A", "B"), ("B", "C"), ("C", "D")], {"A": 0, "B": 0, "C": 0})[0]
    assert f["extremos"] == f["mayor_componente"] == 4


def test_reproduce_lo_publicado_y_lo_corrige():
    r = a.analizar()
    assert (r["parejas_aptas"], r["dianas"]) == (3299, 313)
    assert (r["extremos_ge10"], r["extremos_ge20"]) == (28, 12)      # lo que se publicó
    assert (r["componente_ge10"], r["componente_ge20"]) == (11, 4)   # con camino entre ligandos
