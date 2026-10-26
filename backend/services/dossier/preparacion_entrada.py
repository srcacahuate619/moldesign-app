"""Cómo llegó el archivo del receptor, en las frases que Preparación imprime.

Un receptor propio puede haber pasado por una conversión (mmCIF → PDB clásico), un renombrado de cadenas o
de códigos CCD largos, una decisión de ensamblaje o una comprobación contra su estructura de origen. Nada de eso
puede quedar implícito: «Nada se trunca ni se renombra en silencio». Aquí se componen las partes, una frase
por hecho, para que la traducción (``core/i18n_receptores_propios.py``) las lleve una a una.

Los datos que salen de los archivos (cadenas, códigos, hashes) se copian sin traducir.
"""

from __future__ import annotations

from typing import Any

from services.dossier.model import _v

SEPARADOR = " · "

MODOS_DE_PREPARACION = {
    "automatico": "estructura cruda, preparada por MolDesign",
    "respetar": "estructura preparada por el usuario, respetada tal como venía",
    "pdbqt_sin_origen": "PDBQT listo para Vina, sin estructura de origen",
    "pdbqt_con_origen": "PDBQT listo para Vina, con estructura de origen",
}


def partes_de_conversion(conversion: dict[str, Any]) -> list[str]:
    """Una frase por cada decisión que hubo que tomar al pasar el mmCIF a PDB clásico."""
    partes = ["convertido de mmCIF a PDB clásico"]
    modelos = conversion.get("modelos") or {}
    if int(modelos.get("en_el_archivo") or 1) > 1:
        partes.append(f"modelo 1 de {modelos['en_el_archivo']}")
    cadenas = [f"{c['original']} → {c['pdb']}" for c in conversion.get("cadenas") or [] if c.get("renombrada")]
    if cadenas:
        partes.append("cadenas renombradas: " + ", ".join(cadenas))
    residuos = [
        f"{r['original']} → {r['pdb']} ({r['cadena']}:{r['numero']}{r.get('insercion') or ''})"
        for r in conversion.get("residuos_renombrados") or []
    ]
    if residuos:
        partes.append("códigos largos sustituidos: " + ", ".join(residuos))
    ensamblaje = conversion.get("ensamblaje") or {}
    if ensamblaje.get("estado") == "aplicado":
        n = ensamblaje.get("operadores_aplicados")
        partes.append(f"ensamblaje {ensamblaje.get('usado')} aplicado ({n} operador{'' if n == 1 else 'es'})")
    elif ensamblaje.get("motivo"):
        partes.append("unidad asimétrica: " + str(ensamblaje["motivo"]))
    if conversion.get("serie_renumerada"):
        partes.append("números de serie de átomo repetidos (más de 99 999 átomos)")
    return partes


def partes_de_pqr(pqr: dict[str, Any]) -> list[str]:
    """Lo que se hizo al leer un PQR: se convirtió y se descartaron cargas y radios que Vina no usa."""
    partes = ["convertido de PQR a PDB clásico",
              f"cargas y radios del PQR descartados en {pqr.get('cargas_y_radios_descartados', 0)} átomos "
              "(Vina no los usa)"]
    if pqr.get("atomos_sin_cadena"):
        partes.append(f"cadena asignada (A) a {pqr['atomos_sin_cadena']} átomos sin cadena")
    if pqr.get("residuos_terminales_reducidos"):
        partes.append("residuos terminales reducidos: " + ", ".join(
            f"{k} → {v}" for k, v in sorted(pqr["residuos_terminales_reducidos"].items())))
    return partes


def partes_de_normalizacion(normalizacion: dict[str, Any]) -> list[str]:
    """Lo que se hizo al PDB para que Meeko lo leyera: varios modelos, elemento ausente."""
    partes = []
    modelos = normalizacion.get("modelos") or {}
    if int(modelos.get("en_el_archivo") or 1) > 1:
        partes.append(f"modelo 1 de {modelos['en_el_archivo']}")
    if normalizacion.get("elementos_inferidos"):
        partes.append(f"elemento inferido del nombre en {normalizacion['elementos_inferidos']} átomos")
    if normalizacion.get("nombres_charmm"):
        partes.append("nombres de residuo traducidos: " + ", ".join(
            f"{t['original']} → {t['pdb']} ({t['residuos']})" for t in normalizacion["nombres_charmm"]))
    return partes


def partes_de_entrada(prep: Any) -> list[str]:
    """Las frases de «Archivo del receptor»; vacío si el receptor es del catálogo."""
    entrada = _v(prep, "entrada")
    if not isinstance(entrada, dict):
        return []
    modo_clave = str(_v(prep, "modo_de_preparacion"))
    partes = [str(entrada.get("formato") or "formato desconocido"),
              f"modo: {MODOS_DE_PREPARACION.get(modo_clave, modo_clave)}"]
    if entrada.get("sha256"):
        partes.append(f"SHA-256 {entrada['sha256']}")
    if isinstance(entrada.get("conversion"), dict):
        partes.extend(partes_de_conversion(entrada["conversion"]))
    if isinstance(entrada.get("pqr"), dict):
        partes.extend(partes_de_pqr(entrada["pqr"]))
    if isinstance(entrada.get("normalizacion"), dict):
        partes.extend(partes_de_normalizacion(entrada["normalizacion"]))
    traducciones = _v(prep, "traducciones")
    if isinstance(traducciones, list) and traducciones:
        partes.append("nombres de residuo traducidos: " + ", ".join(
            f"{t['original']} → {t['pdb']} ({t['residuos']})" for t in traducciones))
    origen = _v(prep, "origen")
    if isinstance(origen, dict):
        partes.append(f"origen: {origen.get('formato')} SHA-256 {origen.get('sha256')}")
        if isinstance(origen.get("conversion"), dict):
            partes.extend(partes_de_conversion(origen["conversion"]))
        if isinstance(origen.get("pqr"), dict):
            partes.extend(partes_de_pqr(origen["pqr"]))
        if isinstance(origen.get("normalizacion"), dict):
            partes.extend(partes_de_normalizacion(origen["normalizacion"]))
    correspondencia = _v(prep, "correspondencia_con_el_origen")
    if isinstance(correspondencia, dict) and correspondencia.get("residuos_del_pdbqt"):
        partes.append(
            f"el PDBQT corresponde al origen ({correspondencia['residuos_que_coinciden']} de "
            f"{correspondencia['residuos_del_pdbqt']} residuos; desplazamiento mediano "
            f"{correspondencia['desplazamiento_mediano_A']} Å)"
        )
    return partes
