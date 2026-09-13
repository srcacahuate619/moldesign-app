"""
Cuatro correcciones de la tercera auditoría científica, con su medición.

Cada una tenía una forma distinta de estar mal, y las cuatro producían un
número o una etiqueta que un revisor externo no habría podido defender.
"""

import ast
from pathlib import Path

import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parents[1]
FRONTEND = RAIZ.parent / "frontend"


# ═════════════════════════════════════════════════════════════════════════
# El ángulo del puente de hidrógeno era una tautología
# ═════════════════════════════════════════════════════════════════════════
#
# Se colocaba un hidrógeno ficticio a 1.0 Å del donador SOBRE el vector D→A, y
# luego se medía el ángulo entre D-H y H⋯A. Los dos vectores son colineales por
# construcción, así que cos θ ≡ 1 y la función devolvía 180.0° para TODO puente
# de hidrógeno. Comprobado sobre 2000 geometrías aleatorias: todos los valores
# entre 179.998 y 180.000, y esa variación es ruido de coma flotante.

def test_la_formula_vieja_era_constante():
    """Se reproduce el cálculo anterior para demostrar por qué se retiró."""

    def angulo_viejo(donor, acceptor):
        vec_da = acceptor - donor
        dist = float(np.linalg.norm(vec_da))
        if dist == 0:
            return 0.0
        h = donor + (vec_da / dist) * 1.0
        vec_dh = h - donor
        vec_ha = acceptor - h
        cos = np.dot(vec_dh, vec_ha) / (
            np.linalg.norm(vec_dh) * np.linalg.norm(vec_ha) + 1e-10
        )
        return 180.0 - float(np.degrees(np.arccos(max(-1.0, min(1.0, cos)))))

    generador = np.random.default_rng(0)
    valores = []
    for _ in range(500):
        d = generador.uniform(-20, 20, 3)
        a = d + generador.uniform(-3, 3, 3)
        if np.linalg.norm(a - d) < 1.2:
            continue
        valores.append(angulo_viejo(d, a))

    assert valores
    assert max(valores) - min(valores) < 0.01, (
        "la fórmula anterior no dependía de la geometría: devolvía 180° siempre"
    )


def test_ahora_se_declara_que_no_se_puede_calcular():
    """Sin hidrógenos explícitos el ángulo no es resoluble. Se dice."""
    from services.interactions.analyzer import _estimate_hbond_angle

    assert _estimate_hbond_angle(None, "ASP189.A", None, "LIG.O1") is None


def test_la_distancia_se_sigue_midiendo():
    """Se retiró el ángulo, no el puente: la distancia D⋯A es real."""
    fuente = (RAIZ / "services" / "interactions" / "analyzer.py").read_text(encoding="utf-8")
    assert "_estimate_distance" in fuente
    assert "distance=round(distance, 2)" in fuente


# ═════════════════════════════════════════════════════════════════════════
# ECIF: un carbono no acepta puentes de hidrógeno
# ═════════════════════════════════════════════════════════════════════════
#
# `ecif_N_don_C` y `ecif_O_don_C` se etiquetaban «Puentes H (N-donador → C)».
# Un carbono no tiene pares libres ni la electronegatividad para aceptar un
# puente de hidrógeno; ECIF cuenta contactos dentro de un radio de corte.

def _etiquetas_shap() -> str:
    return (FRONTEND / "components" / "interfaces" / "pro" / "ProXaiTab.tsx").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize("clave", ["ecif_N_don_C", "ecif_O_don_C"])
def test_ningun_contacto_con_carbono_se_llama_puente_de_hidrogeno(clave):
    fuente = _etiquetas_shap()
    linea = next(l for l in fuente.split("\n") if l.strip().startswith(f'"{clave}"'))
    assert "Puentes H" not in linea, (
        f"{clave} vuelve a llamarse puente de hidrógeno; el carbono no acepta"
    )
    assert "Contactos" in linea


@pytest.mark.parametrize("clave", ["ecif_N_don_N", "ecif_N_don_O", "ecif_O_don_O", "ecif_O_don_N"])
def test_los_pares_electronegativos_se_declaran_como_compatibles_no_como_medidos(clave):
    """ECIF cuenta por distancia: no comprueba geometría ni ángulo."""
    fuente = _etiquetas_shap()
    linea = next(l for l in fuente.split("\n") if l.strip().startswith(f'"{clave}"'))
    assert "Puentes H (" not in linea
    assert "distancia" in linea or "radio de corte" in linea


# ═════════════════════════════════════════════════════════════════════════
# El desacoplamiento de métricas estaba roto dentro del propio motor
# ═════════════════════════════════════════════════════════════════════════
#
# `engine.py` declara que ADME, drug-likeness y demás NUNCA alteran el score de
# afinidad. Y `normalize_affinity` multiplicaba `base_score` por un factor
# derivado de logP —hasta −60 %— a través de la eficiencia lipofílica.

def test_la_afinidad_normalizada_no_depende_del_logp():
    from scoring.normalizer import normalize_affinity

    referencia = normalize_affinity(-9.5, 30, 2.0)
    for log_p in (-1.0, 0.5, 2.0, 5.2, 8.0):
        assert normalize_affinity(-9.5, 30, log_p) == referencia, (
            f"logP={log_p} sigue moviendo el score de afinidad; la regla de oro "
            f"de engine.py dice que las propiedades farmacocinéticas no lo tocan"
        )


def test_el_factor_lle_ya_no_esta_en_el_normalizador():
    """Comprobación estructural: que no vuelva por otra vía."""
    arbol = ast.parse((RAIZ / "scoring" / "normalizer.py").read_text(encoding="utf-8"))
    funcion = next(
        n for n in ast.walk(arbol)
        if isinstance(n, ast.FunctionDef) and n.name == "normalize_affinity"
    )
    nombres = {n.id for n in ast.walk(funcion) if isinstance(n, ast.Name)}
    assert "lle_factor" not in nombres
    # `log_p` sigue en la firma por compatibilidad, pero no se usa en el cuerpo.
    usos = [n for n in ast.walk(funcion) if isinstance(n, ast.Name) and n.id == "log_p"]
    assert not usos, "log_p volvió a usarse dentro de normalize_affinity"


# ═════════════════════════════════════════════════════════════════════════
# SAR: huella circular, no de caminos
# ═════════════════════════════════════════════════════════════════════════
#
# `RDKFingerprint` enumera caminos topológicos lineales. Para una serie
# congenérica —que se diferencia por sustituyentes sobre un andamio común— la
# similitud se satura y la columna deja de discriminar justo entre las
# moléculas que el usuario compara. Morgan r=2 / 1024 bits (ECFP4) es la
# convención para este uso.

def test_la_huella_de_sar_es_morgan_ecfp4():
    from api.routers.sar import _huella_morgan
    from rdkit import Chem

    fuente = (RAIZ / "api" / "routers" / "sar.py").read_text(encoding="utf-8")

    # Sobre el ÁRBOL, no sobre el texto: el nombre viejo sigue apareciendo en
    # el comentario que explica por qué se cambió, y esa explicación debe poder
    # quedarse.
    arbol = ast.parse(fuente)
    nombres_usados = {
        getattr(n.func, "id", None) or getattr(n.func, "attr", None)
        for n in ast.walk(arbol)
        if isinstance(n, ast.Call)
    }
    importados = {
        alias.name
        for n in ast.walk(arbol)
        if isinstance(n, ast.ImportFrom)
        for alias in n.names
    }
    assert "RDKFingerprint" not in nombres_usados
    assert "RDKFingerprint" not in importados

    # Radio y bits explícitos: cambiarlos cambia toda la tabla.
    assert "radius=2" in fuente and "fpSize=1024" in fuente

    huella = _huella_morgan(Chem.MolFromSmiles("CC(=O)Oc1ccccc1C(=O)O"))
    assert huella.GetNumBits() == 1024


def test_la_similitud_discrimina_entre_analogo_y_molecula_distinta():
    from api.routers.sar import _huella_morgan, _tanimoto_similarity
    from rdkit import Chem

    base = _huella_morgan(Chem.MolFromSmiles("CC(=O)Oc1ccccc1C(=O)O"))  # aspirina

    identica = _tanimoto_similarity(base, "CC(=O)Oc1ccccc1C(=O)O")
    analogo = _tanimoto_similarity(base, "OC(=O)c1ccccc1O")            # salicílico
    distinta = _tanimoto_similarity(base, "Cn1cnc2c1c(=O)n(C)c(=O)n2C")  # cafeína

    assert identica == 1.0
    assert distinta < analogo < identica, "la columna debe separar análogo de ajena"


def test_un_smiles_ilegible_no_vale_como_cien_por_cien():
    from api.routers.sar import _huella_morgan, _tanimoto_similarity
    from rdkit import Chem

    base = _huella_morgan(Chem.MolFromSmiles("CCO"))
    assert _tanimoto_similarity(base, "esto((no es un smiles") is None
    assert _tanimoto_similarity(None, "CCO") is None
