"""
Elevación del dibujo 2D a 3D: el modelo que gira la ficha de Moldex y el visor
alternativo a Ketcher.

QUÉ PROBLEMA RESUELVE. La miniatura 2D de una molécula y su geometría 3D son
dos dibujos distintos: si se cambia de uno a otro, el ojo pierde qué átomo es
cuál. Aquí se alinea la geometría 3D con el dibujo plano, de modo que el visor
pueda interpolar átomo por átomo entre las dos posiciones: el dibujo «se
levanta» y después gira.

DE DÓNDE SALE LA IDEA. Del visor de MolTalk (Dominic Fico, MIT; ver
`third_party/moltalk/`). Se adaptó su ajuste: una rotación PROPIA por mínimos
cuadrados ponderados —nunca una reflexión, así que R/S se conserva—, con peso
alto en los estereocentros y sus vecinos y repesado robusto para que una cadena
flexible no gire el resto. No se copió su elección de conformador ni su dibujo.

TRES FUENTES, Y NUNCA SE MEZCLAN.

    pose_vina_top1          el primer registro del SDF de la corrida (la pose
                            principal: Vina top-1). Es la geometría que la
                            corrida produjo; no se recalcula ni se relaja.
    conformador_calculado   ETKDGv3 + MMFF94 (o UFF) a partir del SMILES, para
                            el editor. Es UN conformador, no una pose ni una
                            estructura única, y así se declara.
    especie_acoplada        el editor antes de evaluar: la especie y el
                            conformador de partida que prepararía la corrida
                            (`chem.conformer._construir_conformero`, con su pH y
                            su modo de tautómero), sobre el dibujo escrito.

Moldex sólo usa la primera. Si la corrida no conserva su SDF, la ficha se queda
en 2D: rellenar el hueco con un conformador presentaría como evidencia de la
corrida una geometría que la corrida no produjo.

CUÁNDO SE ABSTIENE. Si, de media, los átomos tendrían que moverse más de un
enlace para que la geometría coincidiera con el dibujo, la elevación no se
presenta como levantamiento: `fiel` es falso y el visor lo dice. Es una media
(RMS, con los estereocentros y sus vecinos ×10): un átomo suelto puede moverse
más. El criterio es `razon_enlaces` ≤ UMBRAL_ENLACES, con el desajuste MEDIANO de
las semillas de `SEMILLAS_CRITERIO` dividido entre la longitud media de enlace
del dibujo. Con una sola semilla (la petición rápida del editor) la decisión es
provisional y se dice (`abstencion_provisional`). El umbral se fijó antes de medir la cola de
la distribución (167 moléculas de los paneles congelados y conocidas; no hay un
hueco claro alrededor de 1 enlace, así que la decisión por molécula es frágil).

EL DIBUJO PLANO ES EL MISMO QUE YA SE VE. `dibujo_2d` es la única forma de
dibujar la miniatura (también la usa `/chem/render/{id}`), y devuelve la
posición en el lienzo de cada átomo pesado. Así el instante inicial de la
elevación coincide con la imagen que había.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem, rdDepictor
from rdkit.Chem.Draw import rdMolDraw2D

#: Contrato de la respuesta. Cambiar su forma obliga a cambiar el visor.
CONTRATO = "elevacion/v1"

#: Lienzo de la miniatura, en píxeles. Lo comparte `/chem/render/{id}`.
LIENZO = 300

#: Por encima de esto el conformador tarda demasiado para una vista previa.
MAX_ATOMOS_PESADOS = 150

FUENTE_POSE = "pose_vina_top1"
FUENTE_CONFORMADOR = "conformador_calculado"
FUENTE_ESPECIE = "especie_acoplada"

#: Abstención: la elevación se abstiene si el desajuste mediano supera este número
#: de longitudes de enlace del dibujo. Fijado antes de medir la cola.
UMBRAL_ENLACES = 1.0

#: Semillas del muestreo para el criterio. Una sola semilla no es estable: el
#: mismo imatinib da entre 1,06 y 1,56 enlaces según la semilla (16 candidatos).
SEMILLAS_CRITERIO = (1, 2, 3)

#: Plana: ningún átomo pesado a más de esto del plano medio, en Å.
ESPESOR_PLANA_A = 0.15

#: Anillos que Meeko 0.7.1 abre para que Vina explore su forma (`min_ring_size` y
#: `max_ring_size` por defecto de `mk_prepare_ligand`, que es como lo llama
#: `services/docking/vina_service.py`). Fuera de este rango el anillo es rígido.
MACROCICLO_MIN, MACROCICLO_MAX = 7, 33


class ElevacionNoDisponible(ValueError):
    """No hay modelo 3D que se pueda presentar sin inventarlo."""


@dataclass(frozen=True)
class Dibujo2D:
    svg: str
    #: Posición en el lienzo (px, y hacia abajo) de cada átomo pesado, en el
    #: orden de la molécula leída del SMILES.
    lienzo: np.ndarray
    #: Coordenadas del depictor (unidades de RDKit, y hacia arriba).
    plano: np.ndarray


def dibujo_2d(mol: Chem.Mol, *, conservar: bool = False) -> Dibujo2D:
    """La miniatura en blanco y negro de Moldex, con la posición de cada átomo.

    `mol` se modifica: recibe las coordenadas 2D del depictor. Con `conservar`, se
    dibujan las coordenadas que ya trae (el dibujo de Ketcher). `DrawMolecule`
    añade sus hidrógenos quirales al FINAL, así que los índices de los átomos
    pesados se conservan y `GetDrawCoords(i)` sigue siendo el átomo i.
    """
    d2d = rdMolDraw2D.MolDraw2DSVG(LIENZO, LIENZO)
    options = d2d.drawOptions()
    options.useBWAtomPalette()  # Blanco y negro elegante
    options.bondLineWidth = 2
    options.fixedFontSize = 14
    options.addStereoAnnotation = True

    if not (conservar and mol.GetNumConformers()):
        rdDepictor.Compute2DCoords(mol)
    d2d.DrawMolecule(mol)
    d2d.FinishDrawing()
    n = mol.GetNumAtoms()
    lienzo = np.array([[d2d.GetDrawCoords(i).x, d2d.GetDrawCoords(i).y] for i in range(n)], dtype=float)
    plano = mol.GetConformer().GetPositions()[:, :2].copy()
    return Dibujo2D(svg=d2d.GetDrawingText(), lienzo=lienzo, plano=plano)


def _mapa_al_lienzo(plano: np.ndarray, lienzo: np.ndarray) -> tuple[float, float, float]:
    """(a, bx, by) con lienzo ≈ (bx + a·x, by − a·y): el dibujo de RDKit es una
    escala uniforme con el eje y invertido. Con un solo átomo no hay escala que
    medir, y se usa la que RDKit aplicaría a un enlace (un tercio del lienzo)."""
    if len(plano) < 2 or float(np.ptp(plano, axis=0).max()) < 1e-6:
        return LIENZO / 4.5, float(lienzo[0, 0]), float(lienzo[0, 1])
    centro_p, centro_l = plano.mean(0), lienzo.mean(0)
    p = plano - centro_p
    l = (lienzo - centro_l) * np.array([1.0, -1.0])
    a = float((p * l).sum() / (p * p).sum())
    bx = float(centro_l[0] - a * centro_p[0])
    by = float(centro_l[1] + a * centro_p[1])
    return a, bx, by


def _ajuste(xyz: np.ndarray, xy: np.ndarray, pesos: np.ndarray) -> tuple[np.ndarray, float]:
    """Coloca las coordenadas 3D sobre el dibujo plano.

    Rotación propia (det = +1: nunca refleja, así que la quiralidad del modelo
    se conserva), escala y traslación por mínimos cuadrados ponderados, con
    repesado iterativo: un átomo que no puede coincidir con el dibujo —una cola
    flexible plegada de otro modo en 3D— pierde peso y la parte rígida decide la
    orientación. Adaptado de `moltalk/conformer.py::_fit` (MIT).

    Devuelve las coordenadas alineadas (unidades del dibujo; z hacia quien mira)
    y el desajuste RMS ponderado en esas unidades.
    """
    base = np.asarray(pesos, dtype=float)
    w = base[:, None]
    residuo = np.zeros(len(xyz))
    alineado = xyz - xyz.mean(0)
    for _ in range(5):
        p0, q0 = (w * xyz).sum(0) / w.sum(), (w * xy).sum(0) / w.sum()
        p = xyz - p0
        q = np.column_stack([xy - q0, np.zeros(len(xy))])
        u, _, vt = np.linalg.svd((w * p).T @ q)
        d = np.sign(np.linalg.det(vt.T @ u.T)) or 1.0
        rot = vt.T @ np.diag([1.0, 1.0, d]) @ u.T
        alineado = p @ rot.T
        dispersion = float(np.sum(w * alineado[:, :2] ** 2))
        escala = float(np.sum(w * alineado[:, :2] * q[:, :2]) / dispersion) if dispersion > 1e-6 else 1.0
        if escala <= 0:
            escala = 1.0
        alineado = alineado * escala + np.append(q0, 0.0)
        residuo = np.linalg.norm(alineado[:, :2] - xy, axis=1)
        c = max(0.5, 2.0 * float(np.median(residuo)))
        w = (base / (1.0 + (residuo / c) ** 2))[:, None]
    rms = float(np.sqrt((base * residuo ** 2).sum() / base.sum()))
    return alineado, rms


def _pesos(mol: Chem.Mol) -> np.ndarray:
    """Los estereocentros y sus vecinos mandan en el ajuste: su forma local es
    rígida, y que coincida con el dibujo hace que las cuñas apunten hacia quien
    mira cuando el dibujo se levanta."""
    pesos = np.ones(mol.GetNumAtoms())
    for indice, _ in Chem.FindMolChiralCenters(mol, includeUnassigned=True, useLegacyImplementation=False):
        pesos[indice] = 10.0
        for vecino in mol.GetAtomWithIdx(indice).GetNeighbors():
            pesos[vecino.GetIdx()] = 10.0
    return pesos


def _esqueleto(mol: Chem.Mol) -> Chem.Mol:
    """Sólo elementos y conectividad de los átomos pesados.

    La especie acoplada no es siempre la del SMILES guardado: la protonación
    cambia cargas e hidrógenos, y un tautómero cambia órdenes de enlace. El
    grafo de átomos pesados es lo que las dos comparten.
    """
    rw = Chem.RWMol()
    indices = [a.GetIdx() for a in mol.GetAtoms() if a.GetAtomicNum() > 1]
    nuevo = {}
    for i in indices:
        atomo = Chem.Atom(mol.GetAtomWithIdx(i).GetAtomicNum())
        atomo.SetNoImplicit(True)
        nuevo[i] = rw.AddAtom(atomo)
    for enlace in mol.GetBonds():
        a, b = enlace.GetBeginAtomIdx(), enlace.GetEndAtomIdx()
        if a in nuevo and b in nuevo:
            rw.AddBond(nuevo[a], nuevo[b], Chem.BondType.SINGLE)
    esqueleto = rw.GetMol()
    esqueleto.UpdatePropertyCache(strict=False)
    esqueleto.SetProp("_indices_origen", json.dumps(indices))
    return esqueleto


def _orden_de_enlace(enlace: Chem.Bond) -> float:
    return 1.5 if enlace.GetIsAromatic() else enlace.GetBondTypeAsDouble()


def _enlaces_discrepantes(mol: Chem.Mol, pose: Chem.Mol, pose_de: list[int]) -> int:
    """Enlaces de `mol` cuyo orden no es el del enlace que les toca en la pose.

    Un enlace aromático casa con uno sencillo o doble: la pose puede venir en
    forma de Kekulé (leída sin sanitizar) y un tautómero mueve dobles enlaces.
    """
    discrepantes = 0
    for enlace in mol.GetBonds():
        otro = pose.GetBondBetweenAtoms(pose_de[enlace.GetBeginAtomIdx()], pose_de[enlace.GetEndAtomIdx()])
        a, b = _orden_de_enlace(enlace), _orden_de_enlace(otro)
        if a != b and not (1.5 in (a, b) and {a, b} <= {1.0, 1.5, 2.0}):
            discrepantes += 1
    return discrepantes


def _mejor_correspondencia(mol: Chem.Mol, pose: Chem.Mol, xyz_pose: np.ndarray, xy: np.ndarray,
                           pesos: np.ndarray) -> tuple[np.ndarray, float, np.ndarray, list[int]]:
    """Coordenadas de la pose en el orden de `mol`, con la correspondencia que
    mejor se ajusta al dibujo, y esa correspondencia (`pose_de[i]` es el átomo
    de la pose que corresponde al átomo i de `mol`).

    Se casa por el esqueleto (ver `_esqueleto`) y se prefiere la correspondencia
    que conserva los órdenes de enlace, como `services/molcy/ensamble.py`. Sin
    eso, ramas que sólo distingue el orden (vinilo y etilo, el C=O y el OH de un
    carboxilo) se podían intercambiar si encajaban mejor en el dibujo: la pose
    salía con un centro «invertido» que no lo estaba. Entre las que empatan
    —las simetrías reales: un fenilo que gira, los dos oxígenos de un
    carboxilato—, cualquiera es química correcta, y gana la que menos se mueve
    al levantarse."""
    plantilla = _esqueleto(mol)
    objetivo = _esqueleto(pose)
    if plantilla.GetNumAtoms() != objetivo.GetNumAtoms():
        raise ElevacionNoDisponible("La pose no tiene los mismos átomos pesados que la molécula guardada.")
    origen = json.loads(objetivo.GetProp("_indices_origen"))
    correspondencias = objetivo.GetSubstructMatches(plantilla, uniquify=False, useChirality=False, maxMatches=256)
    if not correspondencias:
        raise ElevacionNoDisponible("La pose no tiene la conectividad de la molécula guardada.")
    por_discrepancias: dict[int, list[list[int]]] = {}
    for corr in correspondencias:
        pose_de = [origen[j] for j in corr]
        por_discrepancias.setdefault(_enlaces_discrepantes(mol, pose, pose_de), []).append(pose_de)
    mejor = None
    for pose_de in por_discrepancias[min(por_discrepancias)]:
        xyz = xyz_pose[pose_de]
        alineado, rms = _ajuste(xyz, xy, pesos)
        if mejor is None or rms < mejor[1]:
            mejor = (alineado, rms, xyz, pose_de)
    return mejor


def _fragmento_acoplado(mol: Chem.Mol, dibujo: Dibujo2D, pose: Chem.Mol,
                        xyz_pose: np.ndarray) -> tuple[Chem.Mol, Dibujo2D, tuple, list[str]]:
    """El fragmento del SMILES guardado que se acopló, con su parte del dibujo.

    El SMILES se guarda como lo escribió el usuario, con el contraión de una sal,
    y `chem/validator.py` lo quita antes de acoplar. Se prueba cada fragmento con
    los mismos átomos pesados que la pose, del mayor al menor; los demás se
    declaran como contraiones (SMILES canónico) y no se levantan: Vina no los vio.
    """
    fragmentos = Chem.GetMolFrags(mol)
    if len(fragmentos) == 1:
        return mol, dibujo, _mejor_correspondencia(mol, pose, xyz_pose, dibujo.plano, _pesos(mol)), []
    pesados_pose = sum(1 for a in pose.GetAtoms() if a.GetAtomicNum() > 1)
    for indices in sorted(fragmentos, key=len, reverse=True):
        if len(indices) != pesados_pose:
            continue
        indices = sorted(indices)
        fragmento = Chem.RWMol(mol)
        for i in sorted(set(range(mol.GetNumAtoms())) - set(indices), reverse=True):
            fragmento.RemoveAtom(i)
        fragmento = fragmento.GetMol()  # RemoveAtom conserva el orden relativo
        parte = Dibujo2D(svg=dibujo.svg, lienzo=dibujo.lienzo[indices], plano=dibujo.plano[indices])
        try:
            ajuste = _mejor_correspondencia(fragmento, pose, xyz_pose, parte.plano, _pesos(fragmento))
        except ElevacionNoDisponible:
            continue
        resto = Chem.RWMol(mol)
        for i in sorted(indices, reverse=True):
            resto.RemoveAtom(i)
        contraiones = sorted(Chem.MolToSmiles(f) for f in Chem.GetMolFrags(resto.GetMol(), asMols=True))
        return fragmento, parte, ajuste, contraiones
    raise ElevacionNoDisponible("La pose no tiene los mismos átomos pesados que la molécula guardada.")


def _enlaces(mol: Chem.Mol) -> list[dict]:
    """Enlaces en forma de Kekulé, como los dibuja RDKit en la miniatura."""
    kek = Chem.Mol(mol)
    try:
        Chem.Kekulize(kek, clearAromaticFlags=True)
    except Exception:
        kek = mol
    orden = {Chem.BondType.SINGLE: 1, Chem.BondType.DOUBLE: 2, Chem.BondType.TRIPLE: 3}
    return [
        {"a": e.GetBeginAtomIdx(), "b": e.GetEndAtomIdx(), "orden": orden.get(e.GetBondType(), 1)}
        for e in kek.GetBonds()
    ]


def _longitud_de_enlace_px(mol: Chem.Mol, dibujo: Dibujo2D, a: float) -> float | None:
    """Longitud media de enlace del dibujo, en px del lienzo. None sin enlaces."""
    if not mol.GetNumBonds():
        return None
    longitudes = [
        float(np.linalg.norm(dibujo.plano[e.GetBeginAtomIdx()] - dibujo.plano[e.GetEndAtomIdx()]))
        for e in mol.GetBonds()
    ]
    return a * float(np.mean(longitudes))


def _es_fiel(razon: float | None) -> bool:
    """Sin enlaces no hay nada que abstenerse; si no, el desajuste mediano no pasa
    de UMBRAL_ENLACES longitudes de enlace."""
    return razon is None or razon <= UMBRAL_ENLACES


def _respuesta(mol: Chem.Mol, dibujo: Dibujo2D, alineado: np.ndarray, rms: float, fuente: str,
               mediana_rms: float, extra: dict) -> dict:
    a, bx, by = _mapa_al_lienzo(dibujo.plano, dibujo.lienzo)
    # En px del lienzo, como `plano`: x a la derecha, y hacia ABAJO, z hacia
    # quien mira. El visor pasa a y hacia arriba antes de rotar, para que sus
    # rotaciones sigan siendo propias.
    espacio = np.column_stack([bx + a * alineado[:, 0], by - a * alineado[:, 1], a * alineado[:, 2]])
    atomos = []
    for i, atomo in enumerate(mol.GetAtoms()):
        atomos.append({
            "elemento": atomo.GetSymbol(),
            "carga": atomo.GetFormalCharge(),
            "hidrogenos": atomo.GetTotalNumHs(),
            "plano": [round(float(v), 2) for v in dibujo.lienzo[i]],
            "xyz": [round(float(v), 2) for v in espacio[i]],
        })
    enlace = _longitud_de_enlace_px(mol, dibujo, a)
    # La abstención se decide con la mediana de las semillas, no con la mejor
    # vista: una cifra afortunada no debe presentar como fiel un dibujo que no lo es.
    razon = None if enlace is None else round(mediana_rms * a / enlace, 3)
    return {
        "contrato": CONTRATO,
        "fuente": fuente,
        "lienzo": LIENZO,
        "svg": dibujo.svg,
        "atomos": atomos,
        "enlaces": _enlaces(mol),
        # Desajuste de la vista que se muestra (la mejor), en px del lienzo.
        "desajuste_px": round(rms * a, 1),
        # Criterio de abstención: desajuste mediano frente a la longitud de enlace.
        "enlace_px": None if enlace is None else round(enlace, 1),
        "razon_enlaces": razon,
        "fiel": _es_fiel(razon),
        "abstencion_provisional": False,
        "dibujo": {"fuente": "rdkit", "motivo": None},
        **extra,
    }


def _detectores(escrita: Chem.Mol, especie: Chem.Mol | None = None,
                 pose_de: list[int] | None = None) -> list[dict]:
    """Lo que los detectores del producto encuentran, con los átomos del modelo.

    Mismas funciones que el resto del producto: las ojivas y la especie en
    revisión se miran en la especie que se acopla (como Preparación y el
    expediente) cuando se conoce (`especie`, con `pose_de` para volver a los
    índices del dibujo); los PAINS, en la molécula escrita (como Propiedades).
    """
    from chem.especie_en_revision import revisiones_en_mol
    from chem.ojivas_covalentes import ojivas_en_mol
    from chem.pains import pains_en_mol

    if especie is not None and pose_de is not None:
        pesados = [a.GetIdx() for a in especie.GetAtoms() if a.GetAtomicNum() > 1]
        sin_h = Chem.RemoveHs(especie, sanitize=False)
        sin_h.UpdatePropertyCache(strict=False)
        Chem.FastFindRings(sin_h)
        posicion = {indice: orden for orden, indice in enumerate(pesados)}
        al_modelo = {posicion[j]: i for i, j in enumerate(pose_de)}
        quimica = sin_h
    else:
        quimica, al_modelo = escrita, {i: i for i in range(escrita.GetNumAtoms())}

    def modelo(atomos) -> list[int]:
        return sorted({al_modelo[a] for a in atomos if a in al_modelo})

    hallados = [{"tipo": "ojiva", "codigo": nombre, "nombre": nombre, "atomos": modelo(atomos)}
                for nombre, atomos in ojivas_en_mol(quimica)]
    hallados += [{"tipo": "pains", "codigo": m["name"], "nombre": m["name"], "atomos": m["atom_indices"]}
                 for m in pains_en_mol(escrita)]
    hallados += [{"tipo": "especie_en_revision", "codigo": motivo.codigo, "nombre": motivo.texto,
                  "atomos": modelo(atomos)}
                 for motivo, atomos in revisiones_en_mol(quimica)]
    return hallados


def _geometria(mol: Chem.Mol, xyz: np.ndarray) -> dict:
    """Lo que la geometría implica para Vina: si es plana y qué anillos abre Meeko.

    `xyz` en Å, en el orden de `mol`. El espesor es la mayor distancia de un
    átomo pesado al plano medio.
    """
    espesor = None
    if len(xyz) >= 3:
        centrado = xyz - xyz.mean(0)
        normal = np.linalg.svd(centrado)[2][2]
        espesor = round(float(np.abs(centrado @ normal).max()), 2)
    tamanos = sorted(len(anillo) for anillo in mol.GetRingInfo().AtomRings())
    return {
        "espesor_A": espesor,
        "plana": espesor is not None and espesor <= ESPESOR_PLANA_A,
        "macrociclos": [t for t in tamanos if MACROCICLO_MIN <= t <= MACROCICLO_MAX],
        "anillos_rigidos_grandes": [t for t in tamanos if t > MACROCICLO_MAX],
    }


#: Longitud de enlace del depictor de RDKit. Un dibujo de Ketcher se lleva a esta
#: escala antes de ajustar: el peso robusto de `_ajuste` tiene un suelo en esas
#: unidades, y así el criterio de abstención es el mismo con los dos dibujos.
LONGITUD_DEPICTOR = 1.5


def _molecula_y_dibujo(smiles: str, molfile: str | None) -> tuple[Chem.Mol, Dibujo2D, dict]:
    """La molécula escrita y su dibujo: el de Ketcher si llega y es esa molécula.

    El levantamiento parte del dibujo que el investigador ve en Ketcher, no del
    que RDKit haría del SMILES. Se usa sólo si es la misma molécula, con su
    estereoquímica (las cuñas incluidas): un dibujo que no corresponde al SMILES
    se descarta y se dice por qué. Los hidrógenos dibujados no cuentan como átomos.
    """
    escrita = _molecula(smiles)
    motivo = None
    dibujada = None
    if molfile:
        try:
            dibujada = Chem.MolFromMolBlock(molfile, removeHs=False)
        except Exception:  # noqa: BLE001 — un dibujo ilegible no tumba la vista
            dibujada = None
        if dibujada is None or not dibujada.GetNumConformers():
            motivo = "El dibujo de Ketcher no se pudo leer; se usa el de RDKit."
        else:
            dibujada = Chem.RemoveHs(dibujada)
            if Chem.MolToSmiles(dibujada) != Chem.MolToSmiles(escrita):
                motivo = "El dibujo de Ketcher no es la molécula del SMILES; se usa el de RDKit."
    if not molfile or motivo:
        return escrita, dibujo_2d(escrita), {"fuente": "rdkit", "motivo": motivo}
    if dibujada.GetNumAtoms() > MAX_ATOMOS_PESADOS:
        raise ElevacionNoDisponible(f"Más de {MAX_ATOMOS_PESADOS} átomos pesados.")
    conf = dibujada.GetConformer()
    xy = np.array([[conf.GetAtomPosition(i).x, conf.GetAtomPosition(i).y] for i in range(dibujada.GetNumAtoms())])
    if dibujada.GetNumBonds():
        media = float(np.mean([np.linalg.norm(xy[e.GetBeginAtomIdx()] - xy[e.GetEndAtomIdx()])
                               for e in dibujada.GetBonds()]))
        if media > 1e-6:
            xy = xy * (LONGITUD_DEPICTOR / media)
    for i, (x, y) in enumerate(xy):
        conf.SetAtomPosition(i, (float(x), float(y), 0.0))
    conf.Set3D(False)
    return dibujada, dibujo_2d(dibujada, conservar=True), {"fuente": "ketcher", "motivo": None}


def _molecula(smiles: str) -> Chem.Mol:
    mol = Chem.MolFromSmiles(smiles or "")
    if mol is None or mol.GetNumAtoms() == 0:
        raise ElevacionNoDisponible("SMILES inválido.")
    if mol.GetNumAtoms() > MAX_ATOMOS_PESADOS:
        raise ElevacionNoDisponible(f"Más de {MAX_ATOMOS_PESADOS} átomos pesados.")
    return mol


def _primer_registro(sdf: str) -> tuple[Chem.Mol, dict]:
    bloque = sdf.split("$$$$", 1)[0]
    if not bloque.strip():
        raise ElevacionNoDisponible("El SDF de la corrida está vacío.")
    # El lector de SDF, no el de bloques MOL: sólo él lee las propiedades
    # (`<meeko>`) que siguen a `M  END`.
    pose = None
    for sanitizar in (True, False):
        lector = Chem.SDMolSupplier()
        lector.SetData(bloque + "$$$$\n", sanitize=sanitizar, removeHs=False)
        pose = next(iter(lector), None)
        if pose is not None:
            break
    if pose is None or pose.GetNumConformers() == 0:
        raise ElevacionNoDisponible("El primer registro del SDF no se puede leer.")
    meeko: dict = {}
    if pose.HasProp("meeko"):
        try:
            meeko = json.loads(pose.GetProp("meeko"))
        except ValueError:
            meeko = {}
    return pose, meeko


def _estereo_de_la_pose(mol: Chem.Mol, xyz: np.ndarray) -> dict:
    """Compara, centro a centro, la configuración que declara el SMILES con la
    geometría de la pose (`xyz`, en el orden de `mol`).

    Centros tetraédricos (R/S) y dobles enlaces declarados (E/Z). Un centro que
    el SMILES no declara no es una inversión: la pose le asigna una configuración
    que nadie pidió, y se cuenta aparte.
    """
    declarados = Chem.FindMolChiralCenters(mol, includeUnassigned=False, useLegacyImplementation=False)
    sin_declarar = [i for i, etiqueta in Chem.FindMolChiralCenters(
        mol, includeUnassigned=True, useLegacyImplementation=False) if etiqueta == "?"]
    # Misma topología, geometría de la pose: si la configuración coincide, RDKit
    # da la misma etiqueta R/S en los dos casos.
    copia = Chem.Mol(mol)
    Chem.RemoveStereochemistry(copia)
    copia.RemoveAllConformers()
    conf = Chem.Conformer(copia.GetNumAtoms())
    for i, p in enumerate(xyz):
        conf.SetAtomPosition(i, p.tolist())
    copia.AddConformer(conf, assignId=True)
    Chem.AssignStereochemistryFrom3D(copia)
    en_pose = dict(Chem.FindMolChiralCenters(copia, includeUnassigned=True, useLegacyImplementation=False))
    conservados, invertidos, no_asignables = 0, [], []
    for i, etiqueta in declarados:
        en_la_pose = en_pose.get(i, "?")
        if en_la_pose == "?":
            no_asignables.append(i)
        elif en_la_pose == etiqueta:
            conservados += 1
        else:
            invertidos.append({"atomo": i, "smiles": etiqueta, "pose": en_la_pose})
    dobles_declarados, dobles_invertidos = _dobles_de_la_pose(mol, copia)
    return {
        "declarados": len(declarados),
        "conservados": conservados,
        "invertidos": invertidos,
        "no_asignables": no_asignables,
        "sin_declarar": sin_declarar,
        "dobles_declarados": dobles_declarados,
        "dobles_invertidos": dobles_invertidos,
    }


def _etiqueta_ez(mol: Chem.Mol) -> dict[tuple[int, int], str]:
    """E o Z (CIP) de cada doble enlace con configuración, por sus dos átomos."""
    copia = Chem.Mol(mol)
    Chem.AssignStereochemistry(copia, cleanIt=True, force=True)
    etiquetas = {}
    for enlace in copia.GetBonds():
        estereo = enlace.GetStereo()
        if estereo in (Chem.BondStereo.STEREOE, Chem.BondStereo.STEREOZ):
            clave = tuple(sorted((enlace.GetBeginAtomIdx(), enlace.GetEndAtomIdx())))
            etiquetas[clave] = "E" if estereo == Chem.BondStereo.STEREOE else "Z"
    return etiquetas


def _dobles_de_la_pose(mol: Chem.Mol, con_geometria: Chem.Mol) -> tuple[int, list[dict]]:
    """Dobles enlaces que el SMILES declara y los que la pose tiene al revés.

    `con_geometria` es `mol` con la geometría de la pose y la estereoquímica
    asignada desde el 3D (la copia de `_estereo_de_la_pose`)."""
    declarados = _etiqueta_ez(mol)
    en_pose = _etiqueta_ez(con_geometria)
    invertidos = [
        {"enlace": list(par), "smiles": etiqueta, "pose": en_pose[par]}
        for par, etiqueta in declarados.items()
        if par in en_pose and en_pose[par] != etiqueta
    ]
    return len(declarados), invertidos


def _especie_de_la_pose(mol: Chem.Mol, pose: Chem.Mol) -> dict:
    """La carga neta de lo que Vina acopló frente a la del SMILES guardado.

    Vina puntúa la especie que se preparó (p. ej. la amina protonada), y sus
    energías no son comparables con las de otra especie. Sólo se compara la
    carga neta: un zwitterión con la misma carga neta no se distingue aquí, y el
    número de hidrógenos tampoco se compara, porque el SDF de Meeko funde los
    apolares.
    """
    return {
        "carga_smiles": Chem.GetFormalCharge(mol),
        "carga_acoplada": Chem.GetFormalCharge(pose),
    }


def modelo_desde_pose(smiles: str, sdf: str) -> dict:
    """La pose principal de la corrida, alineada con la miniatura 2D.

    Además dice lo que la pose no dice igual que el SMILES guardado: la
    configuración de sus centros (`estereo`), la carga de la especie que Vina
    acopló (`especie`) y los contraiones que no se acoplaron (`contraiones`). El visor lo declara en lugar de enseñar la pose como si
    fuera la molécula guardada.
    """
    mol = _molecula(smiles)
    dibujo = dibujo_2d(mol)
    pose, meeko = _primer_registro(sdf)
    xyz_pose = pose.GetConformer().GetPositions()
    mol, dibujo, (alineado, rms, xyz, _), contraiones = _fragmento_acoplado(mol, dibujo, pose, xyz_pose)
    energia = meeko.get("free_energy")
    return _respuesta(mol, dibujo, alineado, rms, FUENTE_POSE, rms, {
        "geometria": _geometria(mol, xyz),
        "pose": {
            "registro": 1,
            "afinidad_kcal_mol": float(energia) if isinstance(energia, (int, float)) else None,
            "sdf_sha256": hashlib.sha256(sdf.encode("utf-8")).hexdigest(),
            "estereo": _estereo_de_la_pose(mol, xyz),
            "especie": _especie_de_la_pose(mol, pose),
            # Fragmentos del SMILES guardado que no se acoplaron: no se levantan.
            "contraiones": contraiones,
        },
    })


def _campo(registro, nombre: str):
    return registro.get(nombre) if isinstance(registro, dict) else getattr(registro, nombre, None)


def evidencia_de_la_corrida(resultado) -> dict:
    """Lo que la corrida ya guardó de su pose top-1: su afinidad y su validez física.

    Se LEE, no se recalcula (como `services/chemistry/pose_selection.py`): la
    validación física ya corrió y su veredicto es el que vale. Sin evidencia
    guardada es None, que significa «no se validó», nunca «falló».
    """
    primera = next((p for p in (getattr(resultado, "docking_poses", None) or []) if _campo(p, "rank") == 1), None)
    afinidad = _campo(primera, "affinity") if primera is not None else None
    if not isinstance(afinidad, (int, float)):
        afinidad = getattr(resultado, "affinity_kcal", None)
    evidencia = getattr(resultado, "structural_evidence", None)
    fisica = next((p for p in (evidencia.get("poses") or []) if p.get("rank") == 1), None)         if isinstance(evidencia, dict) else None
    return {
        "afinidad_kcal_mol": float(afinidad) if isinstance(afinidad, (int, float)) else None,
        "validez_fisica": None if fisica is None else {
            "status": fisica.get("status"),
            "label": fisica.get("label"),
            "motor": fisica.get("engine"),
            "comprobaciones_que_fallan": list(fisica.get("checks_que_fallan") or []),
        },
    }


def _candidatos(pesados: int) -> int:
    """Cuántos conformadores probar por semilla.

    De 31 a 60 átomos pesados, 16 en vez de 8 desde el 2026-10-24: en 37 moléculas
    de 35 a 51 la abstención bajó de 16 a 8 y la mediana pasó de 4,0 s a 7,5 s
    (máx. 15,1 s), dentro del criterio fijado antes de medir
    (`docs/auditorias/elevacion-abstencion-2026-10-24/candidatos_grandes.py`). De 52
    a 60 no se midió. Por encima de 60 siguen 4: no hay medida de cuánto tardarían
    más."""
    return 16 if pesados <= 60 else 4


def _conformadores(mol: Chem.Mol, conformadores: int,
                   semilla: int) -> tuple[list[np.ndarray], list[float | None], str]:
    """Geometrías de hasta `conformadores` candidatos (sólo átomos pesados, en el
    orden de `mol`), su energía en el campo de fuerza (kcal/mol; None sin campo) y
    el campo con que se optimizaron."""
    con_h = Chem.AddHs(mol)
    parametros = AllChem.ETKDGv3()
    parametros.randomSeed = semilla
    parametros.pruneRmsThresh = 0.1
    ids = list(AllChem.EmbedMultipleConfs(con_h, numConfs=conformadores, params=parametros))
    if not ids:
        parametros.useRandomCoords = True
        ids = list(AllChem.EmbedMultipleConfs(con_h, numConfs=conformadores, params=parametros))
    if not ids:
        raise ElevacionNoDisponible("RDKit no pudo generar una geometría 3D para esta molécula.")
    campo = "MMFF94"
    energias: list[float | None] = [None] * len(ids)
    if AllChem.MMFFHasAllMoleculeParams(con_h):
        resultado = AllChem.MMFFOptimizeMoleculeConfs(con_h, maxIters=200)
    elif AllChem.UFFHasAllMoleculeParams(con_h):
        campo = "UFF"
        resultado = AllChem.UFFOptimizeMoleculeConfs(con_h, maxIters=200)
    else:
        campo, resultado = "ninguno", None
    if resultado is not None:
        # Una entrada por conformador del molécula, en el orden de sus ids.
        por_id = {conf.GetId(): e for conf, (_, e) in zip(con_h.GetConformers(), resultado)}
        energias = [float(por_id[cid]) for cid in ids]
    n = mol.GetNumAtoms()  # AddHs añade los hidrógenos al final
    return [con_h.GetConformer(cid).GetPositions()[:n] for cid in ids], energias, campo


def modelo_desde_conformador(smiles: str, *, conformadores: int | None = None,
                             semillas: tuple[int, ...] = SEMILLAS_CRITERIO,
                             molfile: str | None = None) -> dict:
    """Conformadores ETKDGv3 + MMFF94 (UFF si MMFF no tiene parámetros), por cada
    semilla. Se muestra el que mejor coincide con el dibujo entre todas; la
    abstención se decide con la mediana del mejor de cada semilla. Con las mismas
    semillas, el mismo SMILES da el mismo modelo. Con `molfile` (Ketcher), parte
    de ese dibujo y en el orden de sus átomos.
    """
    mol, dibujo, origen_del_dibujo = _molecula_y_dibujo(smiles, molfile)
    conformadores = conformadores or _candidatos(mol.GetNumAtoms())
    pesos = _pesos(mol)
    mejores_por_semilla = []
    mejor = None
    campo = "ninguno"
    todas_las_energias: list[float] = []
    for semilla in semillas:
        geometrias, energias, campo = _conformadores(mol, conformadores, semilla)
        todas_las_energias += [e for e in energias if e is not None]
        de_la_semilla = None
        for xyz, energia in zip(geometrias, energias):
            alineado, rms = _ajuste(xyz, dibujo.plano, pesos)
            if de_la_semilla is None or rms < de_la_semilla[1]:
                de_la_semilla = (alineado, rms, xyz, energia)
        mejores_por_semilla.append(de_la_semilla[1])
        if mejor is None or de_la_semilla[1] < mejor[1]:
            mejor = de_la_semilla
    # El elegido es el que mejor encaja con el dibujo, no el de menor energía: se
    # dice cuánto paga (campo de fuerza en fase gas, sobre el más bajo encontrado).
    delta_e = (round(mejor[3] - min(todas_las_energias), 1)
               if mejor[3] is not None and todas_las_energias else None)
    respuesta = _respuesta(mol, dibujo, mejor[0], mejor[1], FUENTE_CONFORMADOR,
                           float(np.median(mejores_por_semilla)), {
                               "conformador": {"metodo": "ETKDGv3", "campo_de_fuerza": campo,
                                               "semillas": list(semillas),
                                               "candidatos_por_semilla": conformadores,
                                               "delta_e_kcal_mol": delta_e},
                               "geometria": _geometria(mol, mejor[2]),
                               "detectores": _detectores(mol),
                               "dibujo": origen_del_dibujo,
                           })
    respuesta["abstencion_provisional"] = len(semillas) < len(SEMILLAS_CRITERIO)
    return respuesta


def _cambios_de_la_preparacion(mol: Chem.Mol, especie: Chem.Mol, pose_de: list[int],
                               enlaces: list[dict]) -> tuple[list[dict], list[dict], tuple[list, list]]:
    """Átomos y enlaces con la química de la especie preparada, y lo que cambió.

    Los enlaces que la preparación no cambia conservan el Kekulé del dibujo
    escrito: si no, alternar la vista haría saltar los dobles de un anillo
    aromático que nadie tocó. Un enlace cambia si su orden, con el aromático como
    1,5, no es el escrito.
    """
    atomos, cambios_atomos = [], []
    for i, escrito in enumerate(mol.GetAtoms()):
        preparado = especie.GetAtomWithIdx(pose_de[i])
        antes = (escrito.GetFormalCharge(), escrito.GetTotalNumHs())
        despues = (preparado.GetFormalCharge(), preparado.GetTotalNumHs(includeNeighbors=True))
        atomos.append({"carga": despues[0], "hidrogenos": despues[1]})
        if antes != despues:
            cambios_atomos.append({"atomo": i, "carga": [antes[0], despues[0]], "hidrogenos": [antes[1], despues[1]]})
    kekule = Chem.Mol(especie)
    try:
        Chem.Kekulize(kekule, clearAromaticFlags=True)
    except Exception:
        kekule = especie
    orden = {Chem.BondType.SINGLE: 1, Chem.BondType.DOUBLE: 2, Chem.BondType.TRIPLE: 3}
    nuevos, cambios_enlaces = [], []
    for dibujado in enlaces:
        a, b = dibujado["a"], dibujado["b"]
        antes = _orden_de_enlace(mol.GetBondBetweenAtoms(a, b))
        despues = _orden_de_enlace(especie.GetBondBetweenAtoms(pose_de[a], pose_de[b]))
        if antes == despues:
            nuevos.append(dibujado)
            continue
        cambios_enlaces.append({"a": a, "b": b, "orden": [antes, despues]})
        nuevos.append({"a": a, "b": b, "orden": orden.get(
            kekule.GetBondBetweenAtoms(pose_de[a], pose_de[b]).GetBondType(), 1)})
    return atomos, nuevos, (cambios_atomos, cambios_enlaces)


def modelo_de_la_especie_acoplada(smiles: str, *, ph: float | None = None,
                                  tautomero: str | None = None, molfile: str | None = None) -> dict:
    """Lo que la corrida acoplaría a partir de este SMILES, sobre su dibujo.

    La especie (tautómero, protonación al pH de la corrida, sin contraiones) y su
    conformador de partida salen de `chem.conformer._construir_conformero`, la
    misma función que prepara la corrida, con el mismo pH y el mismo modo de
    tautómero. Cada átomo conserva su sitio en el dibujo escrito y lleva la carga,
    los hidrógenos y los enlaces de la especie preparada; lo que cambió se lista.
    No es una pose: Vina todavía no ha corrido.
    """
    from chem.conformer import _construir_conformero

    mol, dibujo, origen_del_dibujo = _molecula_y_dibujo(smiles, molfile)
    try:
        datos = _construir_conformero(smiles, ph, tautomero)
    except Exception as exc:  # noqa: BLE001 — se responde lo que la corrida respondería
        raise ElevacionNoDisponible(f"La corrida no podría preparar esta molécula: {exc}") from exc
    especie, _ = _primer_registro(datos["sdf_content"])
    xyz_especie = especie.GetConformer().GetPositions()
    mol, dibujo, (alineado, rms, xyz, pose_de), contraiones = _fragmento_acoplado(
        mol, dibujo, especie, xyz_especie)
    respuesta = _respuesta(mol, dibujo, alineado, rms, FUENTE_ESPECIE, rms, {
        "geometria": _geometria(mol, xyz),
        "detectores": _detectores(mol, especie, pose_de),
        "dibujo": origen_del_dibujo,
    })
    quimica, respuesta["enlaces"], (cambios_atomos, cambios_enlaces) = _cambios_de_la_preparacion(
        mol, especie, pose_de, respuesta["enlaces"])
    for atomo, preparado in zip(respuesta["atomos"], quimica):
        atomo.update(preparado)
    estado = datos["estado_del_ligando"]
    protonacion = estado.get("protonacion") or {}
    tautomeria = estado.get("tautomeria") or {}
    conformero = estado.get("conformero") or {}
    respuesta["especie_acoplada"] = {
        "smiles": datos["canonical_smiles"],
        "ph": protonacion.get("ph"),
        "aviso_de_ph": protonacion.get("aviso_de_ph"),
        "protonacion": {k: protonacion.get(k) for k in ("aplicada", "motor", "alternativas", "seleccion", "motivo")},
        "tautomero": {k: tautomeria.get(k) for k in ("modo", "aplicada", "alternativas", "motivo", "aviso_de_modo")},
        "conformador": {"semilla": conformero.get("semilla"), "campo_de_fuerza": conformero.get("campo_fuerza_final"),
                        "convergio": conformero.get("optimizacion_convergida")},
        "sdf_sha256": conformero.get("sdf_sha256"),
        "cambios": {"atomos": cambios_atomos, "enlaces": cambios_enlaces},
        "estereo": _estereo_de_la_pose(mol, xyz),
        "contraiones": contraiones,
    }
    return respuesta
