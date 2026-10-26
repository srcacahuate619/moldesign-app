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
    if (estado.get("protonacion") or {}).get("recortado"):
        # CLAVE-09: con la lista en el tope de dimorphite, el conjunto de
        # microestados puede estar incompleto y el elegido sale de un subconjunto.
        tope = ((estado["protonacion"].get("parametros") or {}).get("max_variants")) or "el tope"
        resultado.append(aviso(
            "MICROESTADOS_RECORTADOS", Severidad.PRECAUCION,
            f"dimorphite-dl devolvió {tope} microestados, su máximo: el conjunto puede "
            "estar incompleto y la especie acoplada se eligió entre los que devolvió.",
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
    perdida = estereo.get("perdida_en_la_especie_acoplada") or {}
    centros_perdidos = int(perdida.get("centros") or 0)
    dobles_perdidos = int(perdida.get("dobles") or 0)
    if centros_perdidos or dobles_perdidos:
        resultado.append(aviso(
            "ESTEREOQUIMICA_PERDIDA_AL_NORMALIZAR", Severidad.CRITICA,
            f"La entrada declaraba {centros_perdidos} estereocentro(s) y "
            f"{dobles_perdidos} doble(s) enlace(s) E/Z que la especie acoplada no "
            "conserva: la normalización de tautómero o protonación cambió esos "
            f"átomos. Lo acoplado ({estado.get('smiles_acoplado')}) no es el "
            "estereoisómero que se escribió.",
        ))
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
