"""Avisos persistibles sobre decisiones químicas que la corrida no resolvió."""

from __future__ import annotations

from services.avisos import Severidad, aviso


def avisos_estado_ligando(estado: dict | None) -> list[dict]:
    if not isinstance(estado, dict):
        return []
    resultado: list[dict] = []
    if estado.get("cambio_respecto_a_la_entrada"):
        resultado.append(aviso(
            "ESPECIE_ACOPLADA_DISTINTA", Severidad.PRECAUCION,
            f"La especie acoplada no es la entrada: {estado.get('smiles_entrada')} "
            f"→ {estado.get('smiles_acoplado')}. Las alternativas no evaluadas "
            "siguen siendo incertidumbre química.",
        ))
    elif (estado.get("protonacion") or {}).get("motivo"):
        resultado.append(aviso(
            "SIN_CORRECCION_DE_PROTONACION", Severidad.PRECAUCION,
            str(estado["protonacion"]["motivo"]),
        ))
    seleccion = (estado.get("protonacion") or {}).get("seleccion") or {}
    if seleccion.get("criterio") == "primer_smiles_alfabetico_sin_centros":
        resultado.append(aviso(
            "MICROESTADO_SIN_CRITERIO_QUIMICO", Severidad.PRECAUCION,
            "La tabla de pKa no reconoció centros ionizables. El microestado "
            "se eligió por orden del SMILES canónico para reproducibilidad; "
            "ese orden no estima su población a pH fisiológico.",
        ))
    if seleccion.get("criterio") == "grupo_reconocido_sin_pka" or seleccion.get("clases_sin_pka"):
        clases = ", ".join(seleccion.get("clases_sin_pka") or [])
        resultado.append(aviso(
            "MICROESTADO_PKA_NO_VERIFICADO", Severidad.PRECAUCION,
            f"Se reconoció {clases}, pero falta un pKa acuoso verificado. "
            "La especie seleccionada se conserva con incertidumbre química explícita.",
        ))
    if seleccion.get("revision_biguanida"):
        resultado.append(aviso(
            "BIGUANIDA_ESTADO_EN_REVISION", Severidad.PRECAUCION,
            "Se eligió un monocatión de biguanida como hipótesis reproducible. "
            "Hay modelos experimentales discrepantes sobre la segunda protonación "
            "de metformina cerca de pH fisiológico; revisar la especie antes de interpretar la pose.",
        ))
    estereo = estado.get("estereoquimica") or {}
    centros = int(estereo.get("centros_sin_asignar") or 0)
    dobles = int(estereo.get("dobles_sin_asignar") or 0)
    if centros or dobles:
        smiles_3d = estereo.get("smiles_3d_efectivo")
        dato = (
            f"Isómero derivado del conformero 3D: {smiles_3d}."
            if smiles_3d else
            "No se pudo identificar el isómero derivado del conformero 3D."
        )
        sin_clasificar = estereo.get("dobles_sin_clasificar_3d")
        if sin_clasificar:
            dato += f" {sin_clasificar} doble(s) enlace(s) siguen sin clasificar desde 3D."
        resultado.append(aviso(
            "ESTEREOQUIMICA_NO_DECLARADA", Severidad.CRITICA,
            f"La entrada dejó {centros} centro(s) quirales y {dobles} doble(s) "
            f"enlace(s) E/Z sin especificar. {dato} "
            "No se evaluaron los demás estereoisómeros.",
        ))
    return resultado
