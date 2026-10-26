"""Comparabilidad entre corridas para la tabla SAR.

SOL-04 / AMP-02 (auditoría DevOps SOL, 2026-09-30): la tabla restaba
afinidades entre corridas cuya preparación química era distinta. La
reproducción real fue la serie benzoica contra 3F75 — base a pH 7,4 acopló
`O=C([O-])c1ccccc1` (carga −1), su repetición a pH 2 acopló `O=C(O)c1ccccc1`
(carga 0), y la tabla presentó ambas como «protocolo coincidente» con su
diferencia de afinidad calculada. El Δ confluaba el cambio de molécula con el
cambio de ESPECIE QUÍMICA.

# La regla

Una diferencia de afinidad sólo se certifica entre corridas preparadas bajo
la MISMA condición. Si la condición difiere o no está registrada, SAR se
abstiene: el delta no se fabrica y el motivo nombra los valores en conflicto.

Se comparan CONDICIONES, no especies. Los análogos de una serie acoplan
moléculas distintas por diseño — exigirles el mismo hash de ligando vaciaría
la tabla. Lo que debe coincidir es la REGLA con la que cada una fue
preparada: pH de protonación, motor de protonación, modo de tautómero —
además del protocolo estructural: receptor, versión, semilla, motor,
exhaustividad, poses, confórmeros y caja.

La condición química se lee de `ligand_state`, el estado del ligando que el
conformador registra en cada corrida (`chem/conformer.py`): protonación
aplicada o no, con qué motor y a qué pH, y el modo de tautómero. Una corrida
donde la protonación NO se aplicó (dimorphite ausente, forma neutra acoplada)
es una condición legítima y compartida, no un dato faltante: lo faltante es
no haber registrado nada.

Este módulo es puro: recibe registros con la forma de `EvaluationResultORM`
(columnas + JSON) y no toca base de datos ni HTTP.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

#: Rótulo de lo que falta cuando el registro no conserva la condición química.
ESTADO_QUIMICO_AUSENTE = "estado químico del ligando (protonación y tautomería)"

#: Lo que la fila enseña cuando la comparación procede.
RESUMEN_COMPARABLE = (
    "Protocolo estructural y condiciones químicas coincidentes; "
    "sin actividad experimental"
)

#: Campos estructurales de la firma: definen la corrida física.
_ESTRUCTURALES = (
    "receptor", "version", "semilla", "motor", "exhaustividad",
    "poses", "conformeros", "caja",
)

#: Etiquetas para los motivos: el nombre que el investigador lee.
_ETIQUETAS = {
    "receptor": "receptor preparado",
    "version": "versión de Vina",
    "semilla": "semilla",
    "motor": "motor de docking",
    "exhaustividad": "exhaustividad",
    "poses": "poses",
    "conformeros": "confórmeros ejecutados",
    "caja": "caja de búsqueda",
    "protonacion_aplicada": "protonación aplicada",
    "motor_protonacion": "motor de protonación",
    "ph": "pH de protonación",
    "modo_tautomerio": "modo de tautómero",
    "tautomeria_canonica": "canonicalización de tautómero",
}


@dataclass(frozen=True)
class Comparabilidad:
    """El veredicto de comparabilidad entre la base y un análogo.

    `motivo` es `None` cuando la comparación procede. En abstención NOMBRA
    los valores en conflicto o el dato que falta y de qué lado: «hay un
    problema» no sirve para decidir nada.
    """

    comparable: bool
    motivo: str | None

    @property
    def estado(self) -> str:
        """El estado del contrato de la fila: `descriptive` o `abstained`."""
        return "descriptive" if self.comparable else "abstained"

    @property
    def resumen(self) -> str:
        """La línea humana de la fila: la coincidencia o el motivo."""
        return RESUMEN_COMPARABLE if self.comparable else (self.motivo or "")


# ── Piezas ───────────────────────────────────────────────────────────


def _redondear(valor: Any) -> float | None:
    """NaN, infinitos y texto no son números; no se convierten en 0 ni en ruido."""
    if valor is None:
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    if numero != numero or abs(numero) == float("inf"):
        return None
    return round(numero, 3)


def _caja_de(procedencia: dict[str, Any]) -> tuple[tuple[float, ...], tuple[float, ...]] | None:
    """Centro y lado redondeados a 3 decimales, como firma el preflight.

    Sin el redondeo, `22.5` y `22.500000000004` —la misma caja— abstendrían
    la tabla solos. El preflight ya aprendió esa lección con su fingerprint.
    """
    centro = procedencia.get("box_center")
    lado = procedencia.get("box_size")
    if not centro or not lado:
        return None
    try:
        return (
            tuple(round(float(v), 3) for v in centro),
            tuple(round(float(v), 3) for v in lado),
        )
    except (TypeError, ValueError):
        return None


def _protonacion_de(evaluacion: Any) -> dict[str, Any] | None:
    estado = getattr(evaluacion, "ligand_state", None)
    if not isinstance(estado, dict):
        return None
    protonacion = estado.get("protonacion")
    return protonacion if isinstance(protonacion, dict) else None


def _tautomeria_de(evaluacion: Any) -> dict[str, Any] | None:
    estado = getattr(evaluacion, "ligand_state", None)
    if not isinstance(estado, dict):
        return None
    tautomeria = estado.get("tautomeria")
    return tautomeria if isinstance(tautomeria, dict) else None


def _firma_de(evaluacion: Any) -> dict[str, Any]:
    """Todos los campos firmados, estén o no presentes.

    `None` es un valor más: `campos_ausentes` decide qué `None` es un dato
    faltante y cuál una condición legítima (p. ej. protonación no aplicada).
    """
    protocolo = getattr(evaluacion, "docking_protocol", None)
    protocolo = protocolo if isinstance(protocolo, dict) else {}
    procedencia = protocolo.get("execution_provenance")
    procedencia = procedencia if isinstance(procedencia, dict) else {}
    protonacion = _protonacion_de(evaluacion) or {}
    tautomeria = _tautomeria_de(evaluacion) or {}
    return {
        "receptor": getattr(evaluacion, "receptor_sha256", None),
        "version": getattr(evaluacion, "vina_version", None),
        "semilla": getattr(evaluacion, "vina_random_seed", None),
        "motor": protocolo.get("engine"),
        "exhaustividad": protocolo.get("exhaustiveness"),
        "poses": protocolo.get("num_poses"),
        "conformeros": protocolo.get("conformers_generated"),
        "caja": _caja_de(procedencia),
        "protonacion_aplicada": protonacion.get("aplicada"),
        "motor_protonacion": protonacion.get("motor"),
        "ph": _redondear(protonacion.get("ph")),
        "modo_tautomerio": tautomeria.get("modo"),
        "tautomeria_canonica": tautomeria.get("aplicada"),
    }


def campos_ausentes(evaluacion: Any) -> list[str]:
    """Qué le falta a esta corrida para poder compararla, con su rótulo.

    Sólo los campos estructurales y el estado químico completo cuentan como
    faltantes. Una protonación no aplicada (motor y pH en `None`) es una
    condición REGISTRADA y legítima: la forma neutra acoplada.
    """
    firma = _firma_de(evaluacion)
    ausentes = [_ETIQUETAS[campo] for campo in _ESTRUCTURALES if firma[campo] is None]
    if _protonacion_de(evaluacion) is None or _tautomeria_de(evaluacion) is None:
        ausentes.append(ESTADO_QUIMICO_AUSENTE)
    return ausentes


def _formatear(campo: str, valor: Any) -> str:
    if campo == "ph":
        return f"{valor:g}" if valor is not None else "sin protonar"
    if campo == "protonacion_aplicada":
        return "aplicada" if valor else "no aplicada"
    if campo == "tautomeria_canonica":
        return "sí" if valor else "no"
    if campo == "receptor" and valor:
        return f"{str(valor)[:12]}…"
    if campo == "caja" and valor is not None:
        centro, lado = valor
        centro_txt = ", ".join(f"{v:g}" for v in centro)
        lado_txt = ", ".join(f"{v:g}" for v in lado)
        return f"centro ({centro_txt}) · lado ({lado_txt}) Å"
    if valor is None:
        return "sin registro"
    return str(valor)


# ── Contrato ─────────────────────────────────────────────────────────


def comparar_corridas(base: Any, análogo: Any) -> Comparabilidad:
    """¿Se puede certificar una diferencia de afinidad entre base y análogo?

    La abstención es una salida de primera clase. Los dos motivos posibles:

    - Falta un dato que la comparación necesita: el motivo dice QUÉ falta y
      de qué lado, para que la corrida se pueda corregir o rehacer.
    - Una condición difiere: el motivo nombra el campo y AMBOS valores
      («pH de protonación: 7.4 en la base, 2 en el análogo»). La advertencia
      explícita es parte del contrato, no un adorno.
    """
    ausentes_base = campos_ausentes(base)
    ausentes_análogo = campos_ausentes(análogo)
    if ausentes_base or ausentes_análogo:
        partes: list[str] = []
        if ausentes_base:
            partes.append(f"falta {', '.join(ausentes_base)} en la corrida base")
        if ausentes_análogo:
            partes.append(f"falta {', '.join(ausentes_análogo)} en el análogo")
        return Comparabilidad(False, "no se puede comparar: " + "; ".join(partes))

    firma_base = _firma_de(base)
    firma_análogo = _firma_de(análogo)
    diferencias = [
        campo for campo in firma_base if firma_base[campo] != firma_análogo[campo]
    ]
    if not diferencias:
        return Comparabilidad(True, None)

    detalle = "; ".join(
        f"{_ETIQUETAS[campo]}: {_formatear(campo, firma_base[campo])} en la base, "
        f"{_formatear(campo, firma_análogo[campo])} en el análogo"
        for campo in diferencias
    )
    return Comparabilidad(False, "condiciones de comparación distintas — " + detalle)


def condicion_quimica_publica(evaluacion: Any) -> dict[str, Any]:
    """La condición química que la fila expone: QUÉ especie se acopló.

    El auditor lo pidió con nombre propio: no es sólo una etiqueta de pH —
    la fila tiene que poder decir «carga −1» en vez de enseñar el SMILES
    neutro que escribió el usuario mientras se acopló otra cosa. Ausencias
    explícitas (`None`), nunca ceros ni inventos.
    """
    estado = getattr(evaluacion, "ligand_state", None)
    estado = estado if isinstance(estado, dict) else {}
    protonacion = _protonacion_de(evaluacion) or {}
    return {
        "ph_protonacion": _redondear(protonacion.get("ph")),
        "smiles_acoplado": estado.get("smiles_acoplado"),
        "carga_formal_neta": estado.get("carga_formal_neta"),
    }
