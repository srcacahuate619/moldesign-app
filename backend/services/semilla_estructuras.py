"""Siembra las estructuras empaquetadas en el almacenamiento del usuario.

# El fallo que arregla

En una instalación limpia, TODO receptor bloqueaba la comprobación previa:

    BLOQUEA - Fuente del receptor
    El PDB de 1FH0 todavía no está en disco y no se pudo sellar su contenido.

El instalador empaqueta 111 estructuras en `<recursos>/data/targets/*.pdb`. El
preflight, en cambio, las busca en `<local_data_dir>/targets/<ID>/raw.pdb`, que
es `~/MolDesign/data/...` — un directorio **por usuario**, vacío tras instalar.

Dos discrepancias a la vez: la ubicación y la forma. Y un `grep` sobre el
backend entero confirma lo peor: **nadie leía `resources/data/targets`**. Esos
67 MB viajaban en cada instalador sin que ninguna línea de código los abriera.

En la máquina de desarrollo no se notaba porque `~/MolDesign/data/` se había
ido llenando con meses de uso. Es el mismo patrón que ya nos costó tres
instaladores: el entorno donde se construye tiene algo que el del usuario no.

# Lo que hace, y lo que deliberadamente no

Copia cada estructura empaquetada al sitio donde el preflight la busca, si no
está ya. Nunca sobreescribe: un archivo que el usuario importó o preparó manda
sobre el del instalador.

**No descarga nada.** El preflight tampoco, por diseño, y esta siembra no puede
ser la excepción que meta red en el arranque.

# Alcance real, dicho sin adornos

El catálogo declara 380 objetivos y el instalador los trae **todos**, en gzip
(`scripts/descargar_estructuras_catalogo.py` los baja del RCSB cuando el
catálogo crece; no se hace en el build, que no puede depender de la red).

Un investigador sin conexión puede por tanto trabajar con cualquier objetivo
del catálogo. Traer uno que NO esté en él sigue exigiendo `POST /targets/ingest`
y por tanto red, que es lo que el propio mensaje del control indica.
"""

from __future__ import annotations

import gzip
import re
import shutil
from pathlib import Path

from utils.logger import get_logger

log = get_logger(__name__)

#: `1FH0`, `7e2y`. Se excluyen los recortes por cadena -`7e2y_chainB`- porque no
#: son identificadores del catálogo y sembrarlos crearía objetivos fantasma.
_ID_PDB = re.compile(r"^[0-9][A-Za-z0-9]{3}$")


def _directorio_empaquetado() -> Path | None:
    """`<recursos>/data/targets`, tanto instalado como en el repositorio.

    El backend vive en `<recursos>/backend` en una instalación y en
    `<repo>/backend` en desarrollo; en los dos casos las estructuras cuelgan del
    padre. Se comprueba que exista en vez de suponerlo.
    """
    for candidato in (
        Path(__file__).resolve().parents[2] / "data" / "targets",
        Path(__file__).resolve().parents[3] / "data" / "targets",
    ):
        if candidato.is_dir():
            return candidato
    return None


def sembrar_estructuras_empaquetadas() -> dict[str, int]:
    """Copia lo que falte. Idempotente y sin sobreescribir nada.

    Returns:
        Recuento de `sembradas`, `ya_estaban` y `descartadas`.
    """
    from utils.local_storage import data_dir

    origen = _directorio_empaquetado()
    if origen is None:
        log.warning("semilla_estructuras_sin_origen")
        return {"sembradas": 0, "ya_estaban": 0, "descartadas": 0}

    destino_raiz = data_dir() / "targets"
    sembradas = ya_estaban = descartadas = 0

    # Las estructuras viajan en gzip. Un PDB es texto y comprime ~4x: las 407
    # sin comprimir dejarian el runtime en ~2065 MiB y `makensis` -32 bits-
    # muere a los 2 GiB, asi que empaquetarlas en crudo no daria un instalador
    # grande sino NINGUNO. Se descomprimen aqui, una vez, al sembrar.
    candidatos = sorted(origen.glob("*.pdb.gz")) + sorted(origen.glob("*.pdb"))
    for archivo in candidatos:
        identificador = archivo.name[:-7] if archivo.name.endswith(".pdb.gz") else archivo.stem
        if not _ID_PDB.fullmatch(identificador):
            descartadas += 1
            continue
        destino = destino_raiz / identificador.upper() / "raw.pdb"
        if destino.exists():
            ya_estaban += 1
            continue
        if _copiar(archivo, destino):
            sembradas += 1

    if sembradas:
        log.info("estructuras_sembradas", sembradas=sembradas, ya_estaban=ya_estaban)
    return {"sembradas": sembradas, "ya_estaban": ya_estaban, "descartadas": descartadas}


def _copiar(archivo: Path, destino: Path) -> bool:
    """Materializa una estructura empaquetada. `False` si no se pudo."""
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        if archivo.name.endswith(".pdb.gz"):
            # Se escribe a un temporal y se renombra: si la descompresion se
            # corta a medias, no queda un raw.pdb truncado que el preflight
            # sellaria como si fuera la estructura completa.
            parcial = destino.with_suffix(".parcial")
            with gzip.open(archivo, "rb") as entrada, open(parcial, "wb") as salida:
                shutil.copyfileobj(entrada, salida)
            parcial.replace(destino)
        else:
            shutil.copy2(archivo, destino)
        return True
    except OSError as exc:
        # Una estructura que no se puede copiar no justifica tumbar el arranque:
        # el resto sigue sirviendo y el control lo dira.
        log.warning("semilla_estructura_fallo", archivo=archivo.name, error=str(exc)[:120])
        return False


def sembrar_una(pdb_id: str) -> Path | None:
    """Materializa UNA estructura empaquetada, ya, y devuelve su ruta.

    # La carrera que arregla

    La siembra del arranque copia las 407 en un hilo de fondo y tarda decenas de
    segundos: son ~400 MB descomprimidos. Quien abra la aplicacion y pida un
    receptor dentro de ese hueco —que es exactamente lo que hace alguien que
    acaba de instalar— se encontraba el control de la fuente del receptor
    **bloqueando**:

        BLOQUEA - Fuente del receptor
        El PDB de 7E2Y todavia no esta en disco y no se pudo sellar su contenido.

    con un mensaje que le pedia importar o preparar un receptor que **ya venia en
    el instalador**. Medido en el gate de Evaluacion sobre el runtime staged:
    **57 de 407 sembradas** cuando llego la primera peticion, y 7E2Y no estaba
    entre ellas. Peor que el mensaje: `prepare_target` caia al RCSB, o sea a la
    RED, en un producto que se vende como offline.

    Copiar un archivo del bundle no es descargar nada, asi que esto se puede
    llamar desde el preflight sin romper su regla —no toca la red— y desde la
    preparacion antes de considerar el RCSB.

    Returns:
        La ruta al `raw.pdb` si esta disponible (ya estaba o se acaba de
        sembrar), o `None` si esa estructura no viaja en el instalador.
    """
    from utils.local_storage import data_dir

    identificador = pdb_id.strip().upper()
    if not _ID_PDB.fullmatch(identificador):
        return None

    destino = data_dir() / "targets" / identificador / "raw.pdb"
    if destino.exists():
        return destino

    origen = _directorio_empaquetado()
    if origen is None:
        return None
    for nombre in (f"{identificador}.pdb.gz", f"{identificador}.pdb",
                   f"{identificador.lower()}.pdb.gz", f"{identificador.lower()}.pdb"):
        archivo = origen / nombre
        if archivo.is_file():
            if _copiar(archivo, destino):
                log.info("estructura_sembrada_a_peticion", pdb_id=identificador)
                return destino
            return None
    return None
