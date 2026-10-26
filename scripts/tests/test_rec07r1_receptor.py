"""SCI-B-022: el receptor de REC-07 no tenía la cisteína catalítica; el de REC-07-R1 sí.

No acoplan nada: comparan el filtro sellado de REC-07 con el coherente de REC-07-R1 sobre el
mismo 5TUN, y prueban el aborto por ancla ausente.
"""
import run_rec07_grid_5tun as rec07
import run_rec07r1_grid_5tun as r1


def _cys25(pdb_text):
    return {l[12:16].strip(): l for l in pdb_text.splitlines()
            if l.startswith("ATOM") and l[17:20] == "CYS" and l[21] == "A" and l[22:26].strip() == "25"}


def test_el_filtro_de_rec07_deja_la_cys25_sin_cadena_lateral(tmp_path):
    destino = tmp_path / "rec07.pdb"
    stats = rec07.filtrar_pdb(r1.PDB_5TUN, destino)
    assert stats["altloc_cys25"] == " "
    assert sorted(_cys25(destino.read_text())) == ["C", "N", "O"]


def test_el_filtro_coherente_conserva_la_cys25_entera_en_altloc_a(tmp_path):
    destino = tmp_path / "r1.pdb"
    stats = r1.filtrar_pdb_coherente(r1.PDB_5TUN, destino)
    assert stats["altloc_cys25"] == "A"
    cys = _cys25(destino.read_text())
    assert sorted(cys) == ["C", "CA", "CB", "N", "O", "SG"]
    sg = cys["SG"]
    assert sg[16] == " "  # normalizado a altloc vacío para Meeko
    assert (float(sg[30:38]), float(sg[38:46]), float(sg[46:54])) == (16.591, 140.606, 16.594)


def test_ningun_residuo_pierde_atomos_comunes(tmp_path):
    """Con la regla coherente, un átomo sin altloc nunca se descarta."""
    destino = tmp_path / "r1.pdb"
    r1.filtrar_pdb_coherente(r1.PDB_5TUN, destino)
    salida = {(l[22:26], l[12:16]) for l in destino.read_text().splitlines() if l.startswith("ATOM")}
    comunes = {(l[22:26], l[12:16]) for l in r1.PDB_5TUN.read_text().splitlines()
               if l.startswith("ATOM") and l[21] == "A" and l[16] == " " and int(l[22:26]) > 0}
    assert comunes <= salida


def test_verificar_anclas_rechaza_un_receptor_sin_sg():
    referencia = rec07.leer_atomos(r1.PDB_5TUN)
    completo = {res: dict(atomos) for res, atomos in referencia.items()}
    assert r1.verificar_anclas(completo, referencia)["ok"] is True
    del completo["A:CYS25"]["SG"]
    veredicto = r1.verificar_anclas(completo, referencia)
    assert veredicto["ok"] is False
    assert veredicto["detalle"]["A:CYS25:SG"]["presente"] is False
    desplazado = {res: dict(atomos) for res, atomos in referencia.items()}
    x, y, z = desplazado["A:HIS162"]["NE2"]
    desplazado["A:HIS162"]["NE2"] = (x + 0.5, y, z)
    assert r1.verificar_anclas(desplazado, referencia)["ok"] is False
