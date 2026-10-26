"""Sección del catálogo y avisos medidos, sin alterar la disponibilidad."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from utils.logger import get_logger

log = get_logger(__name__)
DATOS = Path(__file__).resolve().parents[2] / "data"
RUTA_VERIFICADOS = DATOS / "receptores_verificados.json"
RUTA_AVISOS = DATOS / "avisos_catalogo.json"
RUTA_INTENTOS = DATOS / "intentos_de_verificacion.json"


@lru_cache(maxsize=2)
def _leer(ruta: Path) -> dict[str, Any]:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        if not isinstance(datos, dict):
            raise ValueError("Se esperaba un objeto JSON")
        return datos
    except (OSError, ValueError) as exc:
        log.warning("seccion_catalogo_ilegible", ruta=str(ruta), error=str(exc))
        return {}


#: Umbrales preregistrados (decisión del propietario, 2026-10-08). Una entrada
#: que no los supera no es «verificado» aunque alguien la escriba en el archivo:
#: un resultado desfavorable se publica, pero el receptor sigue en Demostración.
SEMILLAS_DEL_PROTOCOLO = 5
SEMILLAS_CON_RMSD_OK_MINIMAS = 3


def _numero(valor: Any) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def _entero(valor: Any) -> bool:
    # `True` es un `int` para Python: sin esta guarda, «n: true» pasaba por una
    # muestra de tamaño 1 (SCI-D-002).
    return isinstance(valor, int) and not isinstance(valor, bool)


def supera_el_protocolo(entrada: Any) -> bool:
    """¿La entrada acredita pose reproducida y calibración con los umbrales fijados?

    Pose: el ligando del cristal en el top-1 a RMSD ≤ 2 Å en al menos 3 de 5
    semillas, y pose físicamente válida. Calibración: límite inferior del
    intervalo de confianza al 95 % de la ρ por encima de 0. Además, el hash del
    receptor que se midió y la receta vigente: sin ellos el sello no se puede
    atar a los bytes que acopla la aplicación.
    """
    if not isinstance(entrada, dict):
        return False
    # Import diferido: leer el catálogo no carga la preparación al arrancar.
    from services.docking.preparer import RECEPTOR_RECIPE_VERSION

    pose, cal = entrada.get("pose"), entrada.get("calibracion")
    if entrada.get("receta_receptor") != RECEPTOR_RECIPE_VERSION:
        return False
    # Los parámetros con los que se midió: el sello sólo describe corridas con
    # esos parámetros, y la interfaz tiene que poder decirlo.
    protocolo = entrada.get("protocolo")
    if not (isinstance(protocolo, dict)
            and all(isinstance(protocolo.get(k), int) and not isinstance(protocolo.get(k), bool)
                    for k in ("exhaustiveness", "num_poses", "semilla"))):
        return False
    # Las condiciones del resultado (receptor sin iones, serie congenérica...) se
    # declaran siempre; una lista vacía es una declaración, su ausencia no.
    condiciones = entrada.get("condiciones")
    if not (isinstance(condiciones, list) and all(isinstance(c, str) and c for c in condiciones)):
        return False
    if not isinstance(entrada.get("receptor_sha256"), str) or not entrada["receptor_sha256"]:
        return False
    if not isinstance(pose, dict) or not isinstance(cal, dict):
        return False
    semillas, ok = pose.get("semillas"), pose.get("semillas_rmsd_ok")
    if not (_entero(semillas) and _entero(ok)):
        return False
    # SCI-D-002. Antes bastaba `semillas >= 5`, así que un resumen de «3 de 100
    # semillas» superaba el gate de pose: 3 aciertos de 100 intentos no es el
    # 3 de 5 que declara el protocolo, es veinte veces menos reproducible. El
    # protocolo fija CINCO semillas, no un mínimo de cinco.
    if semillas != SEMILLAS_DEL_PROTOCOLO:
        return False
    if not SEMILLAS_CON_RMSD_OK_MINIMAS <= ok <= semillas:
        return False
    if pose.get("posebusters_valida") is not True:
        return False
    ic95 = cal.get("ic95")
    if not (isinstance(ic95, list) and len(ic95) == 2 and all(_numero(v) for v in ic95)):
        return False
    if not (0 < ic95[0] <= ic95[1]) or not _numero(cal.get("rho")):
        return False
    # SCI-D-002. Una ρ de Spearman vive en [−1, 1], y su intervalo también: un
    # resumen con IC [1,1; 1,3] no describe ninguna correlación posible, y el
    # gate lo aceptaba porque sólo miraba que el límite inferior fuera positivo.
    if not all(-1.0 <= valor <= 1.0 for valor in (*ic95, cal["rho"])):
        return False
    # Y si el intervalo afirma que ρ es positiva, una ρ puntual negativa
    # contradice su propio resumen: el ejecutor no produce esa combinación, así
    # que describiría un fichero escrito a mano o un error de método. No se
    # exige que el IC contenga la estimación —un bootstrap percentil no lo
    # garantiza siempre—, sólo que no se contradiga en el signo que el gate ya
    # mira.
    if cal["rho"] <= 0:
        return False
    return (_entero(cal.get("n")) and cal["n"] > 0
            and bool(cal.get("panel")) and bool(cal.get("endpoint")))


def verificacion_del_receptor(pdb_id: str | None) -> dict | None:
    """La entrada sólo si supera el protocolo con la receta vigente."""
    verificados = _leer(RUTA_VERIFICADOS).get("verificados")
    if not isinstance(verificados, dict):
        return None
    entrada = verificados.get(str(pdb_id or "").upper())
    if supera_el_protocolo(entrada):
        return entrada
    if entrada is not None:
        log.warning("verificado_sin_superar_protocolo", pdb_id=str(pdb_id).upper())
    return None


def seccion_del_receptor(target: Any) -> str | None:
    """Los privados y de comunidad no pertenecen al catálogo incluido."""
    if getattr(target, "is_private", False) or getattr(target, "is_community", False):
        return None
    return "verificado" if verificacion_del_receptor(target.pdb_id) else "demostracion"


def avisos_del_receptor(pdb_id: str | None) -> list[str]:
    """Códigos medidos; el cliente pone el texto en su idioma."""
    avisos = _leer(RUTA_AVISOS).get("avisos")
    if not isinstance(avisos, dict):
        return []
    codigos = avisos.get(str(pdb_id or "").upper(), [])
    return [codigo for codigo in codigos if isinstance(codigo, str)] if isinstance(codigos, list) else []


def intentos_del_receptor(pdb_id: str | None) -> list[dict[str, Any]]:
    """Intentos de verificación publicados para un receptor, pasen o no.

    Un intento NO_GO o INCONCLUSIVE no promociona nada: su receptor sigue en Demostración. Se
    publica para que el investigador vea qué se midió y por qué no basta.
    """
    intentos = _leer(RUTA_INTENTOS).get("intentos")
    if not isinstance(intentos, list):
        return []
    clave = str(pdb_id or "").upper()
    return [i for i in intentos if isinstance(i, dict) and str(i.get("pdb_id") or "").upper() == clave
            and i.get("decision") in {"GO", "NO_GO", "INCONCLUSIVE"}]


#: Parámetros de la corrida (`docking_protocol`) frente a los del sello (`protocolo`).
_PARAMETROS_DEL_SELLO = (("exhaustiveness", "exhaustiveness"), ("num_poses", "num_poses"),
                         ("seed", "semilla"))


def catalogo_de_la_corrida(target: Any, docking_protocol: Any) -> dict[str, Any]:
    """La sección del receptor de UNA corrida y si su sello la describe.

    Un sello de «verificado» se midió sobre unos bytes de receptor y con unos
    parámetros. Describe esta corrida sólo si coinciden los dos: el mismo
    receptor preparado y la misma exhaustividad, número de poses y semilla. Si
    no, el receptor sigue siendo verificado, pero esta corrida no lo está: es
    la distinción que el dossier y Preparación tienen que poder decir.

    La sección es la de hoy, no la del día de la corrida; por eso se compara con
    la procedencia que la corrida sí serializó y no se infiere nada más.

    Lo que la corrida no declara no es una diferencia, pero tampoco una
    coincidencia: va a `sin_declarar` y el sello tampoco la describe.
    """
    if target is None:
        return {"seccion": None, "pdb_id": None, "aplica_a_esta_corrida": False,
                "difiere_en": [], "sin_declarar": [], "avisos": [], "verificacion": None}
    pdb_id = str(getattr(target, "pdb_id", "") or "").upper() or None
    seccion = seccion_del_receptor(target)
    verificacion = verificacion_del_receptor(pdb_id) if seccion == "verificado" else None
    difiere: list[str] = []
    sin_declarar: list[str] = []
    if verificacion is not None:
        protocolo = docking_protocol if isinstance(docking_protocol, dict) else {}
        procedencia = protocolo.get("execution_provenance") or {}
        pares = [("receptor", procedencia.get("receptor_sha256"), verificacion["receptor_sha256"])]
        pares += [(de_la_corrida, protocolo.get(de_la_corrida), verificacion["protocolo"][del_sello])
                  for de_la_corrida, del_sello in _PARAMETROS_DEL_SELLO]
        for campo, de_la_corrida, del_sello in pares:
            if de_la_corrida is None:
                sin_declarar.append(campo)
            elif de_la_corrida != del_sello:
                difiere.append(campo)
    return {
        "seccion": seccion,
        "pdb_id": pdb_id,
        "aplica_a_esta_corrida": verificacion is not None and not difiere and not sin_declarar,
        "difiere_en": difiere,
        "sin_declarar": sin_declarar,
        "avisos": avisos_del_receptor(pdb_id) if seccion else [],
        "verificacion": verificacion,
    }
