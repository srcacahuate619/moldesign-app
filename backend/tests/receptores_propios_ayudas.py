"""Ayudas compartidas por las pruebas de receptores propios (subida, formatos, modos).

No es un `conftest`: se importa explícitamente para que cada prueba diga qué usa.
"""

from __future__ import annotations

import math
from pathlib import Path

#: Átomos de un residuo de alanina en una hélice recta (suficiente para todo lo que se mide aquí).
_ALA = (("N", "N", -1.2, 0.8, 0.0), ("CA", "C", 0.0, 0.0, 0.0), ("C", "C", 1.2, 0.9, 0.0),
        ("O", "OA", 1.2, 2.1, 0.0), ("CB", "C", 0.0, -1.0, 1.2))


def linea_pdbqt(serial: int, nombre: str, residuo: str, cadena: str, numero: int,
                xyz: tuple[float, float, float], tipo: str, *, carga: float = 0.0,
                registro: str = "ATOM") -> str:
    x, y, z = xyz
    return (f"{registro:<6}{serial:>5} {nombre:^4}{' '}{residuo:>3} {cadena}{numero:>4}{' '}   "
            f"{x:8.3f}{y:8.3f}{z:8.3f}{1.0:6.2f}{0.0:6.2f}    {carga:6.3f} {tipo:<2}")


def linea_pdb(serial: int, nombre: str, residuo: str, cadena: str, numero: int,
              xyz: tuple[float, float, float], elemento: str, *, registro: str = "ATOM",
              altloc: str = " ", ocupacion: float = 1.0, bfactor: float = 20.0) -> str:
    x, y, z = xyz
    return (f"{registro:<6}{serial:>5} {nombre:^4}{altloc}{residuo:>3} {cadena}{numero:>4}{' '}   "
            f"{x:8.3f}{y:8.3f}{z:8.3f}{ocupacion:6.2f}{bfactor:6.2f}          {elemento:>2}")


def cadena_de_alaninas(cadena: str = "A", residuos: int = 30, *, origen=(0.0, 0.0, 0.0),
                       hetero: tuple[str, str, int, tuple[float, float, float]] | None = None):
    """Una cadena recta de ALA: devuelve (líneas PDB, líneas PDBQT) con las mismas coordenadas."""
    pdb, pdbqt, serial = [], [], 1
    for n in range(1, residuos + 1):
        for nombre, tipo, dx, dy, dz in _ALA:
            xyz = (origen[0] + 3.8 * n + dx, origen[1] + dy, origen[2] + dz)
            elemento = {"N": "N", "OA": "O"}.get(tipo, "C")
            pdb.append(linea_pdb(serial, nombre, "ALA", cadena, n, xyz, elemento))
            pdbqt.append(linea_pdbqt(serial, nombre, "ALA", cadena, n, xyz, tipo, carga=0.1))
            serial += 1
        # Un hidrógeno polar en el N: sólo en el PDBQT, como lo escribe Meeko.
        pdbqt.append(linea_pdbqt(serial, "H", "ALA", cadena, n,
                                 (origen[0] + 3.8 * n - 2.1, origen[1] + 1.4, origen[2]), "HD", carga=0.16))
        serial += 1
    if hetero:
        nombre_res, nombre_atomo, numero, xyz = hetero
        pdb.append(linea_pdb(serial, nombre_atomo, nombre_res, cadena, numero, xyz,
                             nombre_atomo[:2].strip(), registro="HETATM"))
    return pdb, pdbqt


def pdbqt_sintetico(**kwargs) -> str:
    return "\n".join(cadena_de_alaninas(**kwargs)[1]) + "\nTER\nEND\n"


def pdb_sintetico(**kwargs) -> str:
    return "\n".join(cadena_de_alaninas(**kwargs)[0]) + "\nEND\n"


def aislar_almacen(monkeypatch, tmp_path: Path) -> Path:
    """Redirige los datos del usuario a `tmp_path`, como hacen las pruebas de preparación."""
    from services.docking import preparer
    from utils import local_storage

    datos = tmp_path / "MolDesign" / "data"
    datos.mkdir(parents=True)
    temporal = tmp_path / "vina"
    temporal.mkdir()
    for ajustes in (preparer.settings, local_storage.settings):
        monkeypatch.setattr(ajustes, "local_data_dir", str(datos))
        monkeypatch.setattr(ajustes, "vina_temp_dir", str(temporal))
    assert local_storage.data_dir() == datos
    return datos


def distancia(a, b) -> float:
    return math.dist(a, b)


# ── mmCIF sintético ─────────────────────────────────────────────────────────

_CABECERA_ATOMOS = (
    "group_PDB id type_symbol label_atom_id label_alt_id label_comp_id label_asym_id label_entity_id "
    "label_seq_id pdbx_PDB_ins_code Cartn_x Cartn_y Cartn_z occupancy B_iso_or_equiv auth_seq_id "
    "auth_comp_id auth_asym_id auth_atom_id pdbx_PDB_model_num"
).split()


def mmcif_sintetico(cadenas, *, ensamblajes=None, modelos=1, metodo="X-RAY DIFFRACTION", resolucion=2.0):
    """Un mmCIF mínimo pero completo.

    ``cadenas``: lista de dicts con ``auth`` (nombre de la cadena), ``label`` (asym), ``residuos`` (lista de
    ``(nombre, numero, het, [(atomo, elemento, (x, y, z), altloc, ocupacion)])``).
    ``ensamblajes``: lista de ``(id, [(operadores, [label_asym…])])``; los operadores se dan por nombre y
    ``OPERADORES`` define su traslación en x.
    """
    lineas = ["data_TEST", "_entry.id TEST", "#", f"_exptl.method '{metodo}'",
              f"_refine.ls_d_res_high {resolucion}", "#"]
    lineas += ["loop_", "_entity.id", "_entity.type"]
    lineas += [f"{i} {'polymer' if c.get('polimero', True) else 'non-polymer'}" for i, c in enumerate(cadenas, 1)]
    lineas += ["#", "loop_", "_struct_asym.id", "_struct_asym.entity_id"]
    lineas += [f"{c['label']} {i}" for i, c in enumerate(cadenas, 1)]
    if ensamblajes:
        lineas += ["#", "loop_", "_pdbx_struct_assembly.id", "_pdbx_struct_assembly.details",
                   "_pdbx_struct_assembly.method_details", "_pdbx_struct_assembly.oligomeric_details",
                   "_pdbx_struct_assembly.oligomeric_count"]
        lineas += [f"{a_id} author_defined_assembly ? dimeric 2" for a_id, _ in ensamblajes]
        lineas += ["#", "loop_", "_pdbx_struct_assembly_gen.assembly_id", "_pdbx_struct_assembly_gen.oper_expression",
                   "_pdbx_struct_assembly_gen.asym_id_list"]
        for a_id, generadoras in ensamblajes:
            for operadores, asyms in generadoras:
                lineas.append(f"{a_id} {operadores} {','.join(asyms)}")
        lineas += ["#", "loop_", "_pdbx_struct_oper_list.id", "_pdbx_struct_oper_list.type",
                   "_pdbx_struct_oper_list.name", "_pdbx_struct_oper_list.symmetry_operation"] + [
            f"_pdbx_struct_oper_list.matrix[{i}][{j}]" for i in (1, 2, 3) for j in (1, 2, 3)] + [
            f"_pdbx_struct_oper_list.vector[{i}]" for i in (1, 2, 3)]
        for nombre, desplazamiento in OPERADORES.items():
            lineas.append(f"{nombre} 'identity operation' {nombre}_555 ? 1 0 0 0 1 0 0 0 1 {desplazamiento} 0 0")
    lineas += ["#", "loop_"] + [f"_atom_site.{c}" for c in _CABECERA_ATOMOS]
    serial = 0
    for modelo in range(1, modelos + 1):
        for i, c in enumerate(cadenas, 1):
            for nombre, numero, het, atomos in c["residuos"]:
                for atomo, elemento, (x, y, z), altloc, ocupacion in atomos:
                    serial += 1
                    desplazamiento = 0.5 * (modelo - 1)
                    lineas.append(
                        f"{'HETATM' if het else 'ATOM'} {serial} {elemento} {atomo} {altloc or '.'} {nombre} "
                        f"{c['label']} {i} {numero if not het else '.'} ? {x + desplazamiento:.3f} {y:.3f} {z:.3f} "
                        f"{ocupacion:.2f} 20.00 {numero} {nombre} {c['auth']} {atomo} {modelo}")
    lineas += ["#"]
    return "\n".join(lineas) + "\n"


#: Operadores de ensamblaje del mmCIF sintético: nombre → traslación en x (Å).
OPERADORES = {"1": 0.0, "2": 40.0, "3": 80.0}


def residuo_ala(numero: int, x0: float = 0.0, *, nombre: str = "ALA", altloc=None, ocupacion=1.0):
    atomos = [(a, e, (x0 + dx + 3.8 * numero, dy, dz), altloc, ocupacion)
              for a, e, dx, dy, dz in (("N", "N", -1.2, 0.8, 0.0), ("CA", "C", 0.0, 0.0, 0.0),
                                       ("C", "C", 1.2, 0.9, 0.0), ("O", "O", 1.2, 2.1, 0.0),
                                       ("CB", "C", 0.0, -1.0, 1.2))]
    return (nombre, numero, False, atomos)


def residuo_hetero(nombre: str, numero: int, posicion=(5.0, 5.0, 5.0), *, atomos=("C1", "O1")):
    x, y, z = posicion
    return (nombre, numero, True, [(a, a[0], (x + 1.4 * i, y, z), None, 1.0) for i, a in enumerate(atomos)])
