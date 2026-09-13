"""
El sitio de una anti-diana, resuelto en UN sitio.

# El fallo que arregla

El panel de anti-dianas vivía como una lista de diccionarios escrita a mano en
`selectivity.py`, con `"chain": "A"` en las cinco entradas, y los tres sitios de
llamada la pasaban tal cual a `run_vina_docking(target_chain=...)` **sin pasar
`site_chains`**. El camino principal de evaluación sí lo pasa: lo lee de
`TargetORM.site_chains`, que a su vez viene de `curated_targets.json`, y
`preparer.py` deriva de ahí el modo multicadena.

Resultado medido sobre el catálogo:

    5VA1  hERG (KCNH2)   panel: chain=A    catálogo: site_chains ["A","B"]
    6MVW  NaV1.5 (SCN5A) panel: chain=A    catálogo: site_chains ["C","D","A"]

El **mismo receptor** recibía la cavidad completa cuando se acoplaba como diana
principal y media cavidad cuando se acoplaba como anti-diana. Y las dos
afectadas son las dos anti-dianas cardíacas —las que existen para detectar la
prolongación del QT que retiró la terfenadina y la cisaprida—, así que el panel
de seguridad era más débil justo donde su razón de ser es ser fuerte.

# La regla

El catálogo es la ÚNICA autoridad sobre la composición del sitio. Este módulo
no guarda una segunda copia de `site_chains`: la lee de la fila del receptor.
Lo que sí conserva la definición del panel es la caja curada del bolsillo
tóxico, que es información del panel y no del catálogo.

# La abstención

Una anti-diana cuyo sitio no se puede resolver **no se acopla**. Antes, el
endpoint de anti-diana individual fabricaba `center=(0,0,0)` y `size=20³` para
cualquier receptor desconocido: eso acopla contra el origen del sistema de
coordenadas —espacio vacío, casi siempre— y devuelve la afinidad resultante
como un dato de seguridad. Un número inventado en un panel de toxicidad es peor
que la ausencia del número, porque la ausencia se ve.

# Por qué estructuras experimentales y no co-plegamiento

Dos de las cinco anti-dianas del panel son canales iónicos con el sitio en un
poro oligomérico: hERG/Kv11.1 (`5VA1`) y NaV1.5 (`6MVW`). Es exactamente la
familia donde las herramientas modernas de co-plegamiento proteína-ligando
—AlphaFold 3, Boltz-2, Protenix-v2— tienen un modo de fallo documentado:
colapsan la cavidad del poro.

    Zhu Y., Rahman T. (2026). «Benchmarking co-folding tools on Nav, Cav and Kv
    channels». Frontiers in Biophysics 4:1937302.
    https://doi.org/10.3389/frbis.2026.1937302

Por eso este módulo resuelve el sitio sobre la **estructura experimental
depositada**, ensamblada con las cadenas que el catálogo declara en
`site_chains`, y acopla con Vina sobre ella. No es conservadurismo: es que en
esta familia concreta el generador falla justo en la cavidad que el panel de
seguridad necesita medir.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from utils.logger import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class SitioDeAntiDiana:
    """Lo que hace falta para acoplar contra una anti-diana, ya resuelto."""

    pdb_id: str
    chain: str
    site_chains: list[str] | None
    center: tuple[float, float, float]
    size: tuple[float, float, float]
    #: De dónde salió la caja: `panel` (curada para el bolsillo tóxico) o
    #: `catalogo` (la del receptor). Viaja al resultado para que se pueda leer.
    procedencia_caja: str


@dataclass(frozen=True)
class AntiDianaSinSitio:
    """No se pudo resolver el sitio. NO se acopla; se declara."""

    pdb_id: str
    motivo: str


def _caja_valida(centro: tuple[float, float, float] | None) -> bool:
    """Una caja en el origen no es una caja: es un valor por defecto sin medir."""
    if centro is None:
        return False
    try:
        x, y, z = (float(c) for c in centro)
    except (TypeError, ValueError):
        return False
    return not (abs(x) < 1e-6 and abs(y) < 1e-6 and abs(z) < 1e-6)


async def resolver_sitio_de_anti_diana(
    definicion: dict[str, Any],
    repository: Any,
) -> SitioDeAntiDiana | AntiDianaSinSitio:
    """Completa la definición del panel con la composición real del sitio.

    `definicion` es una entrada de `ANTI_TARGET_PANEL` o el diccionario
    equivalente que arma el endpoint para una anti-diana de usuario.
    `repository` es un `db.repository.Repository` vivo.
    """
    pdb_id = str(definicion.get("pdb_id") or "").strip().upper()
    if not pdb_id:
        return AntiDianaSinSitio("", "la anti-diana no declara un PDB ID")

    fila = None
    try:
        fila = await repository.get_target_by_pdb_id(pdb_id)
    except Exception as exc:  # noqa: BLE001 — se reporta, no se traga
        log.warning(
            "anti_target_catalogo_ilegible",
            pdb_id=pdb_id,
            error=f"{type(exc).__name__}: {exc}",
        )

    # ── Las cadenas del sitio: SIEMPRE del catálogo ──────────────────────────
    site_chains = None
    if fila is not None:
        crudas = getattr(fila, "site_chains", None) or []
        site_chains = [str(c).strip() for c in crudas if str(c).strip()] or None

    # ── La caja: la del panel manda, porque describe el bolsillo tóxico ──────
    centro_panel = definicion.get("center")
    tamano_panel = definicion.get("size")
    if _caja_valida(centro_panel) and tamano_panel:
        centro = tuple(float(c) for c in centro_panel)
        tamano = tuple(float(s) for s in tamano_panel)
        procedencia = "panel"
    elif fila is not None and _caja_valida(
        (
            getattr(fila, "grid_center_x", None),
            getattr(fila, "grid_center_y", None),
            getattr(fila, "grid_center_z", None),
        )
    ):
        centro = (
            float(fila.grid_center_x),
            float(fila.grid_center_y),
            float(fila.grid_center_z),
        )
        tamano = (
            float(getattr(fila, "grid_size_x", None) or 20.0),
            float(getattr(fila, "grid_size_y", None) or 20.0),
            float(getattr(fila, "grid_size_z", None) or 20.0),
        )
        procedencia = "catalogo"
    else:
        return AntiDianaSinSitio(
            pdb_id,
            "no hay una caja de acoplamiento calibrada para este receptor, ni en el "
            "panel ni en el catálogo. Acoplar contra una caja por defecto daría un "
            "número de seguridad que no describe ningún bolsillo.",
        )

    # `chain` sólo se usa cuando el sitio es de una sola cadena; con dos o más,
    # `preparer.py` deriva el modo multicadena de `site_chains` e ignora este
    # valor. Se conserva por compatibilidad con el camino de una sola cadena.
    chain = str(definicion.get("chain") or (site_chains[0] if site_chains else "A"))

    if site_chains and len(set(site_chains)) > 1:
        log.info(
            "anti_target_multicadena",
            pdb_id=pdb_id,
            site_chains=site_chains,
            chain_declarada=chain,
        )

    return SitioDeAntiDiana(
        pdb_id=pdb_id,
        chain=chain,
        site_chains=site_chains,
        center=centro,
        size=tamano,
        procedencia_caja=procedencia,
    )
