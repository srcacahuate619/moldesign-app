"""Donde esta todo. Unico sitio con rutas absolutas del codigo Python.

Si algo se mueve de disco, se cambia aqui. Los lanzadores que no son Python
(`correr_caso.ps1`, `produccion.sh`, `abrir.bat`) no pueden importar este
archivo: el runner recibe `-Root` y `-Blender` de la interfaz, y los otros dos
declaran sus rutas en las primeras lineas.

Sin `bpy`: lo importan tambien la interfaz y las pruebas, fuera de Blender.
"""
from __future__ import annotations

import os
from pathlib import Path

#: Raiz del proyecto: la carpeta que contiene `scripts/` y `moldesign/`.
PROYECTO = Path(__file__).resolve().parents[2]

#: Paquetes de escena producidos por moldesign-build. La CIENCIA. Ninguna ruta de una maquina concreta: MolDesign pasa
#: `MOLCY_SCENES_DIR`; a mano, sin la variable, se busca `dist/scenes` junto al proyecto.
ESCENAS = Path(os.environ.get("MOLCY_SCENES_DIR") or PROYECTO / "dist" / "scenes")

#: Un caso por receptor, siguiendo la convencion de 001_egfr_1M17. MolDesign pasa `MOLCY_CASES_DIR`.
CASOS = Path(os.environ.get("MOLCY_CASES_DIR") or PROYECTO / "moldesign" / "cases")

#: Direccion de arte: materiales, luces y prototipos de etiqueta, SIN una sola
#: clave de animacion. Se genera con `herramientas/extraer_plantilla_arte.py`
#: a partir del caso 001. No apuntar aqui al .blend de EGFR hecho a mano: sus
#: acciones se heredan al copiar y pisan los valores que se asignen despues,
#: en cada cambio de fotograma. De ahi salieron cuatro fallos distintos.
PLANTILLA_ARTE = Path(os.environ.get(
    "MOLCY_ART_TEMPLATE",
    str(PROYECTO / "moldesign" / "assets" / "blender" / "plantilla_arte.blend"),
))

#: Blender con Molecular Nodes. Solo lo usa la interfaz Flask, que se lo pasa al runner; el runner recibe `-Blender`.
#: Sin ruta fija: `MOLCY_BLENDER`, o `blender.exe` si Windows lo encuentra en el PATH.
BLENDER = Path(os.environ.get("MOLCY_BLENDER") or "blender.exe")
ADDON_MN = "bl_ext.blender_org.molecularnodes"

#: Raiz de este proyecto de scripts.
RAIZ = Path(__file__).resolve().parents[1]


def carpeta_de_caso(pdb_id: str, familia: str | None,
                    casos: Path = CASOS) -> Path:
    """La carpeta del caso: la que ya exista, o el siguiente numero libre.

    Solo CALCULA. Quien la vaya a usar tiene que crearla en el acto y bajo su
    propio cerrojo: dos llamadas seguidas sin `mkdir` entre medias devuelven el
    mismo numero. Asi salian `026_…` repetidos cuando la interfaz calculaba la
    carpeta de toda una tanda al encolar.
    """
    ya = sorted(casos.glob(f"*_{pdb_id}"))
    if ya:
        return ya[0]
    usados = [int(d.name[:3]) for d in casos.iterdir()
              if d.is_dir() and d.name[:3].isdigit()]
    return casos / f"{max(usados or [0]) + 1:03d}_{familia or 'desconocida'}_{pdb_id}"
