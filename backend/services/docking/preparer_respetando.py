"""Camino B: un receptor que el equipo YA preparó. MolDesign no lo vuelve a preparar a su manera: lo respeta.

# Qué respeta

La receta del catálogo (y de la subida «cruda») retira todas las aguas y todo HETATM que no esté en una lista
blanca, y vuelve a protonar con las plantillas de Meeko. Para un receptor que su equipo ya protonó —y en el que
decidió qué aguas, metales y cofactores conservar— eso es deshacer su trabajo en silencio. Aquí:

* la **protonación** (``HID``/``HIE``/``HIP``, ``CYX``, ``CYM``, ``ASH``, ``GLH``, ``LYN``) se conserva, y después
  de Meeko se **comprueba residuo a residuo** que la plantilla aplicada es la que el archivo declaraba; si Meeko
  la cambia, falla con el motivo;
* los nombres de CHARMM (``HSD``/``HSE``/``HSP``) y ``WAT`` se traducen a los que Meeko conoce
  (``HID``/``HIE``/``HIP``/``HOH``) y **cada traducción queda declarada** con su recuento;
* las **aguas, los metales y los cofactores** que el archivo trae se conservan: no hay lista blanca porque la
  decisión ya está tomada. Lo que no se puede representar con honestidad —un Na⁺ (en PDBQT ``NA`` es un
  nitrógeno aceptor), un K⁺, un residuo sin plantilla— se abstiene con motivo si está junto al sitio y, lejos de
  él, se retira y se declara. Nunca se adivina.

# Qué sigue haciendo igual que el catálogo

Elegir la conformación mayoritaria de los altlocs, truncar (sin inventar coordenadas) las cadenas laterales
incompletas, medir huecos del esqueleto, recortar al sitio cuando éste se forma entre cadenas y abstenerse si
Meeko pierde residuos junto a la caja. Esas funciones son las mismas del catálogo y se importan de ``preparer``.

# Lo que NO se genera

La unidad biológica: se usa lo que trae el archivo, y el informe lo dice.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.metadata
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from core.config import get_settings
from core.exceptions import ProteinPreparationError
from services.docking import preparer as P
from services.targets.perfil_receptor import extras_del_informe
from utils.file_handlers import StoragePath, validate_pdbqt_content
from utils.local_storage import exists, read_text, write_file, write_text
from utils.logger import get_logger
from utils.procesos import BANDERAS_SIN_VENTANA, communicate_managed

log = get_logger(__name__)
settings = get_settings()

RECETA_RESPETANDO_VERSION = 1

#: Nombres que Meeko no conoce y que tienen un equivalente exacto. Cada uso queda en el informe.
TRADUCCIONES_DE_RESIDUO = {"HSD": "HID", "HSE": "HIE", "HSP": "HIP", "WAT": "HOH"}

#: Residuos con una protonación declarada en el nombre: la plantilla que aplique Meeko tiene que ser una de éstas
#: (la propia, o su variante N- o C-terminal). ``CYM`` es el tiolato; Meeko 0.7.1 lo llama ``CYX-``.
PLANTILLAS_EQUIVALENTES: dict[str, frozenset[str]] = {
    "HID": frozenset({"HID", "NHID", "CHID"}),
    "HIE": frozenset({"HIE", "NHIE", "CHIE"}),
    "HIP": frozenset({"HIP", "NHIP", "CHIP"}),
    "CYX": frozenset({"CYX", "NCYX", "CCYX"}),
    "CYM": frozenset({"CYX-", "NCYX-", "CCYX-"}),
    "ASH": frozenset({"ASH", "NASH", "CASH"}),
    "GLH": frozenset({"GLH", "NGLH", "CGLH"}),
    "LYN": frozenset({"LYN", "NLYN", "CLYN"}),
}

#: Variante de protonación → residuo estándar, para decidir qué átomos pesados le faltan.
_BASE_DE_VARIANTE = {"HID": "HIS", "HIE": "HIS", "HIP": "HIS", "ASH": "ASP", "GLH": "GLU", "LYN": "LYS",
                     "CYX": "CYS", "CYM": "CYS"}

_MOTIVOS = {
    "sodio": ("sodio: en PDBQT el tipo NA es un nitrógeno aceptor y Vina lo trataría como un nitrógeno fantasma",
              "sodium: in PDBQT the NA type is an acceptor nitrogen and Vina would treat it as a phantom nitrogen"),
    "sin_radio": ("Meeko no tiene radio covalente para este elemento",
                  "Meeko has no covalent radius for this element"),
    "sin_plantilla": ("no hay plantilla de Meeko para este residuo",
                      "there is no Meeko template for this residue"),
}


# ── Lectura del archivo ───────────────────────────────────────────────────


def traducir_residuos(texto: str) -> tuple[str, list[dict[str, Any]]]:
    """HSD/HSE/HSP/WAT → HID/HIE/HIP/HOH, con el recuento de residuos de cada traducción."""
    vistos: dict[str, set[tuple[str, str, str]]] = {}
    salida: list[str] = []
    for linea in texto.split("\n"):
        if linea.startswith(("ATOM", "HETATM")) and len(linea) >= 27:
            nombre = linea[17:20].strip()
            if nombre in TRADUCCIONES_DE_RESIDUO:
                vistos.setdefault(nombre, set()).add((linea[21:22], linea[22:26], linea[26:27]))
                linea = linea[:17] + f"{TRADUCCIONES_DE_RESIDUO[nombre]:>3}" + linea[20:]
        salida.append(linea)
    traducciones = [
        {"original": n, "pdb": TRADUCCIONES_DE_RESIDUO[n], "residuos": len(claves)}
        for n, claves in sorted(vistos.items())
    ]
    return "\n".join(salida), traducciones


def _altlocs_elegidos(texto: str) -> dict[tuple[str, str, str], str]:
    """La conformación mayoritaria por residuo (la misma regla que ``_filter_pdb_content``)."""
    ocupacion: dict[tuple[str, str, str], dict[str, float]] = {}
    for linea in texto.split("\n"):
        if linea[:6].strip() not in {"ATOM", "HETATM"} or len(linea) < 27:
            continue
        variante = linea[16:17].strip()
        if not variante:
            continue
        clave = (linea[21:22].strip() or "A", linea[22:26].strip(), linea[26:27])
        try:
            peso = float(linea[54:60])
        except ValueError:
            peso = 0.0
        ocupacion.setdefault(clave, {})[variante] = ocupacion.get(clave, {}).get(variante, 0.0) + peso
    return {clave: min(v, key=lambda x: (-v[x], x)) for clave, v in ocupacion.items()}


def filtrar_respetando(
    texto: str,
    cadenas: set[str],
    center: tuple[float, float, float],
    size: tuple[float, float, float],
) -> tuple[str, dict[str, Any]]:
    """Las cadenas pedidas con TODO lo que traen: aguas, metales, cofactores, hidrógenos.

    Un HETATM entra si es de una de las cadenas pedidas o si pertenece a una cadena que no tiene proteína
    (aguas e iones en su propia cadena) y está dentro del margen del sitio; el resto de la estructura no es el
    receptor. Los altlocs se resuelven como en el catálogo. ``MSE`` se convierte en ``MET`` (Meeko no tiene radio
    covalente para el Se) y se cuenta.
    """
    elegidos = _altlocs_elegidos(texto)
    con_proteina = {(l[21:22].strip() or "A") for l in texto.split("\n") if l.startswith("ATOM") and len(l) > 21}
    salida: list[str] = []
    mse = hetero_externos = 0
    for linea in texto.split("\n"):
        registro = linea[:6].strip()
        if registro == "TER":
            if (linea[21:22].strip() or "A") in cadenas:
                salida.append(linea)
            continue
        if registro not in {"ATOM", "HETATM"} or len(linea) < 54:
            continue
        cadena = linea[21:22].strip() or "A"
        pertenece = cadena in cadenas
        if not pertenece:
            if registro != "HETATM" or cadena in con_proteina:
                continue
            try:
                pos = tuple(float(linea[i:i + 8]) for i in (30, 38, 46))
            except ValueError:
                continue
            if P._distancia_a_caja(pos, center, size) > P.MARGEN_SITIO_A:
                continue
            hetero_externos += 1
        variante = linea[16:17].strip()
        if variante:
            if variante != elegidos.get((cadena, linea[22:26].strip(), linea[26:27])):
                continue
            linea = linea[:16] + " " + linea[17:]
        if linea[17:20].strip() == "MSE":
            convertida = P._convert_mse_to_met(linea)
            if convertida:
                linea = convertida
                mse += 1
        salida.append(linea)
    return "\n".join(salida) + "\n", {"mse_a_met": mse, "hetero_de_cadenas_sin_proteina": hetero_externos}


# ── Especies que no se pueden representar ─────────────────────────────────


def especies_sin_representacion(
    texto: str, center: tuple[float, float, float], size: tuple[float, float, float],
) -> list[dict[str, Any]]:
    """Residuos del archivo que Meeko no puede parametrizar sin red, con su motivo y su distancia a la caja."""
    con_plantilla = P.residuos_con_plantilla() | {"MET"}
    instancias: dict[tuple[str, str, str, str], list[tuple[float, float, float]]] = {}
    atomos: dict[tuple[str, str, str, str], str] = {}
    for linea in texto.split("\n"):
        if not linea.startswith(("ATOM", "HETATM")) or len(linea) < 54:
            continue
        nombre = linea[17:20].strip()
        if nombre in con_plantilla:
            continue
        try:
            pos = tuple(float(linea[i:i + 8]) for i in (30, 38, 46))
        except ValueError:
            continue
        clave = (linea[21:22].strip() or "A", linea[22:26].strip(), linea[26:27].strip(), nombre)
        instancias.setdefault(clave, []).append(pos)
        atomos.setdefault(clave, linea[12:16].strip())
    filas = []
    for (cadena, numero, insercion, nombre), posiciones in sorted(instancias.items()):
        if nombre == "NA" and atomos[(cadena, numero, insercion, nombre)] == "NA":
            motivo = "sodio"
        elif nombre in P.METAL_COFACTORS:
            motivo = "sin_radio"
        else:
            motivo = "sin_plantilla"
        distancia = min(P._distancia_a_caja(p, center, size) for p in posiciones)
        filas.append({"chain": cadena, "residue_number": numero, "insertion_code": insercion, "name": nombre,
                      "motivo": motivo, "distance_to_box_A": round(distancia, 3)})
    return filas


def _etiqueta(fila: dict[str, Any]) -> str:
    return f"{fila['name']} {fila['chain']}:{fila['residue_number']}{fila['insertion_code']}"


# ── Truncado de cadenas laterales, con los nombres de variante ────────────


def truncar_respetando(
    texto: str, center: tuple[float, float, float], size: tuple[float, float, float],
) -> tuple[str, list[dict[str, Any]]]:
    """``truncar_cadenas_laterales_incompletas`` entiende ``HIS`` pero no ``HID``: se le pasan los nombres base
    y se restauran los de variante después, para que un residuo incompleto con protonación declarada se trunque
    en vez de que Meeko lo borre entero."""
    originales: dict[tuple[str, str, str], str] = {}
    sustituido: list[str] = []
    for linea in texto.split("\n"):
        if linea.startswith("ATOM") and len(linea) >= 27 and linea[17:20].strip() in _BASE_DE_VARIANTE:
            nombre = linea[17:20].strip()
            originales[(linea[21:22].strip() or "A", linea[22:26].strip(), linea[26:27].strip())] = nombre
            linea = linea[:17] + f"{_BASE_DE_VARIANTE[nombre]:>3}" + linea[20:]
        sustituido.append(linea)
    truncado, filas = P.truncar_cadenas_laterales_incompletas("\n".join(sustituido), center, size)
    if not originales:
        return truncado, filas
    restaurado: list[str] = []
    for linea in truncado.split("\n"):
        if linea.startswith("ATOM") and len(linea) >= 27:
            clave = (linea[21:22].strip() or "A", linea[22:26].strip(), linea[26:27].strip())
            variante = originales.get(clave)
            if variante and linea[17:20].strip() in set(_BASE_DE_VARIANTE.values()) | {"ALA", "GLY"}:
                # ALA/GLY sólo si el residuo se truncó; un residuo completo conserva su variante
                if linea[17:20].strip() == _BASE_DE_VARIANTE[variante]:
                    linea = linea[:17] + f"{variante:>3}" + linea[20:]
        restaurado.append(linea)
    for fila in filas:
        variante = originales.get((str(fila["chain"]), str(fila["residue_number"]), str(fila["insertion_code"])))
        if variante:
            fila["name"] = variante
    return "\n".join(restaurado), filas


# ── Identidad ─────────────────────────────────────────────────────────────


def receta_respetando(
    origen: str, cadenas: set[str], center: tuple[float, float, float], size: tuple[float, float, float],
) -> str:
    multicadena = len(cadenas) > 1
    crop = None
    if multicadena:
        from services.docking.preparer_multichain import radio_para_caja

        crop = {"center": [round(float(v), 3) for v in center], "radius": float(radio_para_caja(tuple(size)))}
    documento = {
        "version": RECETA_RESPETANDO_VERSION,
        "modo": "respetar",
        "source_sha256": hashlib.sha256(origen.encode("utf-8")).hexdigest(),
        "chains": sorted(cadenas),
        "box_center": [round(float(v), 3) for v in center],
        "box_size": [round(float(v), 3) for v in size],
        "crop": crop,
        "traducciones": sorted(TRADUCCIONES_DE_RESIDUO.items()),
        "margen_sitio_A": P.MARGEN_SITIO_A,
        "meeko_version": P._version_de("meeko"),
        "cofactor_templates_sha256": P._plantillas_sha256(),
    }
    canonico = json.dumps(documento, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonico.encode("ascii")).hexdigest()


# ── Meeko, sin la degradación del catálogo ────────────────────────────────


async def _correr_meeko(entrada: Path, salida: Path, center, size, cwd: Path) -> tuple[bytes, bytes, int]:
    orden = [
        sys.executable, "-m", "meeko.cli.mk_prepare_receptor",
        "--read_pdb", str(entrada), "-o", str(salida), "-p", "-j", "-v", "-a",
        "--default_altloc", settings.meeko_default_altloc,
        "--box_size", *(str(v) for v in size), "--box_center", *(str(v) for v in center),
    ]
    if P.RUTA_PLANTILLAS_COFACTORES.is_file():
        orden += ["--add_templates", str(P.RUTA_PLANTILLAS_COFACTORES)]
    proceso = await asyncio.create_subprocess_exec(
        *orden, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        creationflags=BANDERAS_SIN_VENTANA, cwd=str(cwd))
    stdout, stderr = await communicate_managed(proceso, timeout=600.0)
    return stdout, stderr, proceso.returncode


def _comprobar_protonacion(monomeros: dict[str, Any]) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Plantilla aplicada frente a plantilla declarada, residuo a residuo."""
    aplicadas: dict[str, dict[str, str]] = {}
    cambiadas: list[str] = []
    for resid, fila in monomeros.items():
        entrada, plantilla = fila.get("input_resname"), fila.get("residue_template_key")
        if entrada in PLANTILLAS_EQUIVALENTES or entrada in {"HIS", "ASP", "GLU", "CYS", "LYS", "TYR", "ARG"}:
            aplicadas[resid] = {"input_resname": entrada, "template": plantilla}
        if entrada in PLANTILLAS_EQUIVALENTES and plantilla not in PLANTILLAS_EQUIVALENTES[entrada]:
            cambiadas.append(f"{resid} {entrada} → {plantilla}")
    return aplicadas, cambiadas


async def preparar_respetando(
    pdb_id: str,
    perfil: dict[str, Any],
    *,
    chain_id: str,
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    site_chains: list[str] | None,
) -> str:
    """Prepara el receptor respetando lo que el archivo trae y devuelve la ruta lógica del PDBQT."""
    cadenas_del_sitio = {c.strip() for c in (site_chains or []) if c and c.strip()}
    multicadena = len(cadenas_del_sitio) > 1
    cadenas = cadenas_del_sitio if multicadena else {chain_id.strip()}
    if tuple(float(v) for v in center) == (0.0, 0.0, 0.0):
        center, size = P.resolve_effective_docking_box(
            pdb_id=pdb_id, chain_id=chain_id, center=center, size=size, site_chains=site_chains)

    origen = await read_text(StoragePath.target_raw(pdb_id))
    receta = receta_respetando(origen, cadenas, center, size)
    ruta = StoragePath.target_prepared(pdb_id, receta)
    ruta_informe = P._meeko_report_path(ruta)
    if await exists(ruta) and await exists(ruta_informe):
        return ruta

    traducido, traducciones = traducir_residuos(origen)
    filtrado, info = filtrar_respetando(traducido, cadenas, center, size)
    if info["mse_a_met"]:
        traducciones.append({"original": "MSE", "pdb": "MET", "residuos": info["mse_a_met"],
                             "nota": "selenometionina → metionina (Se → S)"})
    atomos_proteina = sum(1 for l in filtrado.split("\n") if l.startswith("ATOM"))
    if atomos_proteina == 0:
        raise ProteinPreparationError(
            pdb_id=pdb_id, step="chain_filtering",
            detail=f"No quedaron átomos ATOM tras filtrar la cadena '{'+'.join(sorted(cadenas))}'.")

    # Especies que no se pueden representar: junto al sitio se abstiene; lejos se retiran y se declaran.
    sin_representacion = especies_sin_representacion(filtrado, center, size)
    cerca = [f for f in sin_representacion if f["distance_to_box_A"] <= P.MARGEN_SITIO_A]
    lejos = [f for f in sin_representacion if f["distance_to_box_A"] > P.MARGEN_SITIO_A]
    if cerca:
        raise ProteinPreparationError(
            pdb_id=pdb_id, step="especie_no_representable",
            detail=json.dumps([{**f, "motivo_texto": _MOTIVOS[f["motivo"]][0]} for f in cerca], ensure_ascii=False))
    if lejos:
        filtrado = P.retirar_cofactores_fuera_del_sitio(filtrado, lejos)
        log.warning("especies_sin_representacion_fuera_del_sitio", pdb_id=pdb_id, especies=lejos)

    filtrado, truncadas = truncar_respetando(filtrado, center, size)
    huecos = P.huecos_del_esqueleto(filtrado, origen, center, size)
    if multicadena:
        filtrado = P._recortar_al_sitio(filtrado, pdb_id=pdb_id, center=center, size=size, cadenas=sorted(cadenas))
        if P.prepared_receptor_chains(filtrado) != cadenas:
            raise ProteinPreparationError(
                pdb_id=pdb_id, step="site_chains_missing",
                detail=(f"El sitio se forma entre {sorted(cadenas)} y el receptor preparado solo contendria "
                        f"{sorted(P.prepared_receptor_chains(filtrado))}."))

    from services.docking.preflight import diff_de_especies_de_la_corrida

    species_diff = diff_de_especies_de_la_corrida(
        traducido, filtrado, cadenas="+".join(sorted(cadenas)), center=center, size=size, site_ligand=None)

    # La copia en PDB que consumen el rescoring y la validación física: el mismo receptor que se acopla.
    await write_text(f"targets/{pdb_id}.pdb", filtrado)

    Path(settings.vina_temp_dir).mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True, dir=settings.vina_temp_dir) as tmp:
        tmp_path = Path(tmp)
        entrada = tmp_path / f"{pdb_id}_{chain_id}.pdb"
        entrada.write_text(filtrado, encoding="utf-8")
        base = tmp_path / f"{pdb_id}_{chain_id}_prepared"
        stdout, stderr, codigo = await _correr_meeko(entrada, base, center, size, tmp_path)
        if codigo != 0:
            log.error("meeko_respetando_fallo", pdb_id=pdb_id, stderr=stderr.decode("utf-8", "replace")[-1500:],
                      stdout=stdout.decode("utf-8", "replace")[-600:])
            raise ProteinPreparationError(
                pdb_id=pdb_id, step="mk_prepare_receptor",
                detail="Meeko no pudo preparar el receptor respetando su protonación y sus especies.")
        salida = Path(f"{base}.pdbqt")
        if not salida.exists():
            raise ProteinPreparationError(pdb_id=pdb_id, step="mk_prepare_receptor_output",
                                          detail="La preparación terminó sin generar el receptor .pdbqt.")
        contenido = salida.read_text(encoding="utf-8", errors="replace")
        valido, error = validate_pdbqt_content(contenido)
        if not valido:
            raise ProteinPreparationError(pdb_id=pdb_id, step="validate_pdbqt", detail=error)

        eliminados = P._residuos_eliminados(filtrado, contenido, center=center, size=size)
        criticos = [r for r in eliminados if r["site_critical"]]
        if criticos:
            raise ProteinPreparationError(
                pdb_id=pdb_id, step="receptor_site_residues_missing",
                detail=("Meeko eliminó residuos a 6 Å o menos de la caja: " + json.dumps(criticos, ensure_ascii=False)
                        + ". No se ejecuta docking contra un sitio incompleto."))
        json_parametrizado = Path(f"{base}.json")
        if not json_parametrizado.is_file():
            raise ProteinPreparationError(pdb_id=pdb_id, step="meeko_parameterized_json_missing",
                                          detail="Meeko no escribió el JSON de plantillas del receptor.")
        bytes_json = json_parametrizado.read_bytes()
        try:
            monomeros = json.loads(bytes_json)["monomers"]
        except (ValueError, KeyError, TypeError) as exc:
            raise ProteinPreparationError(pdb_id=pdb_id, step="meeko_parameterized_json_invalid",
                                          detail=f"No se pudieron leer las plantillas elegidas por Meeko: {exc}") from exc
        plantillas, cambiadas = _comprobar_protonacion(monomeros)
        if cambiadas:
            raise ProteinPreparationError(
                pdb_id=pdb_id, step="protonacion_cambiada",
                detail=json.dumps(cambiadas, ensure_ascii=False))

        declaradas = sum(1 for f in plantillas.values() if f["input_resname"] in PLANTILLAS_EQUIVALENTES)
        informe = {
            "species_diff": species_diff,
            "meeko_parameterized_json_sha256": hashlib.sha256(bytes_json).hexdigest(),
            "protonation_templates": plantillas,
            "protonation_method": (
                "Declarada por quien preparó el archivo; Meeko " + P._version_de("meeko") +
                " aplicó las plantillas declaradas (comprobado residuo a residuo); sin pH declarado"),
            "protonacion_declarada": {
                "origen": "usuario", "plantillas_declaradas": declaradas, "plantillas_coinciden": True,
                "traducciones": traducciones,
                "formato_del_archivo": (extras_del_informe(pdb_id).get("entrada") or {}).get("formato"),
            },
            "traducciones": traducciones,
            "recipe_hash": receta,
            "receptor_sha256": hashlib.sha256(salida.read_bytes()).hexdigest(),
            "removed_residues": eliminados,
            "truncated_sidechains": truncadas,
            "backbone_gaps": huecos,
            "cofactor_templates_sha256": P._plantillas_sha256(),
            "cofactors_outside_site": [{**f, "action": "retirado"} for f in lejos],
            "meeko_reported_residues": [],
            **{k: v for k, v in extras_del_informe(pdb_id, texto=origen, center=center, size=size).items()
               if k != "modo_de_preparacion"},
            "modo_de_preparacion": "respetar",
        }
        await write_text(ruta_informe, json.dumps(informe, sort_keys=True))
        await write_file(salida, ruta)
    log.info("receptor_respetado_listo", pdb_id=pdb_id, chain="+".join(sorted(cadenas)), traducciones=traducciones,
             sin_representacion=len(sin_representacion))
    return ruta
