"""
Paquete reproducible: ZIP con manifiesto, hashes y receta.

# Qué problema resuelve

El PDF es la lectura humana; el ZIP es la contraparte verificable. Un tercero
tiene que poder abrirlo y contestar dos preguntas sin ejecutar nada:

    ¿qué archivos había? ¿siguen siendo los mismos?

Por eso el manifiesto declara **todos** los artefactos, incluidos los que no
están: un artefacto ausente aparece con `NO_DISPONIBLE` y su razón. Omitirlo
dejaría al lector sin saber si el archivo no se generó o si alguien lo quitó.

# Determinismo

Con los mismos inputs y el mismo `generated_at`, el ZIP es byte a byte
idéntico. Sin eso, dos exportaciones de la misma corrida diferirían y el
verificador no podría distinguir un cambio real de un cambio de reloj. Se
consigue con: orden fijo de entradas, timestamps congelados dentro del ZIP,
JSON canónico y compresión estable.

# Lo que NO entra, por construcción

`.env`, claves, tokens, la base de datos, rutas del perfil del usuario,
carpetas temporales, logs de otras corridas, enlaces simbólicos y cualquier
ruta con `..` o absoluta. No se filtra al final: sólo se escriben los
artefactos que este módulo construye, y sus nombres se sanean.

# Los tres ciclos de hash que hay que romper

    · el ZIP no se contiene a sí mismo;
    · `checksums.sha256` no se hashea a sí mismo;
    · `manifest.json` no se declara a sí mismo dentro de `files`.

Las tres exclusiones están documentadas en el README del paquete y en el propio
manifiesto, porque un verificador que no las conozca reportaría «archivo no
declarado». La del manifiesto no lo deja sin comprobar: `checksums.sha256` se
calcula después e incluye el manifiesto.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from typing import Any, Iterable

from core.i18n import current_locale, translate_text
from services.dossier.contrato_paquete import CHECKSUMS_NAME, MANIFEST_VERSION  # noqa: F401 (se reexportan)
from services.dossier.localization import dossier_dict_localizado, traducir_dossier
from services.dossier.model import Artefacto, CaseDossier, hash_canonico
from services.dossier.taxonomy import ETIQUETA, GLOSARIO, Estado

# MANIFEST_VERSION y CHECKSUMS_NAME viven en `contrato_paquete.py`, que el verificador importa sin el backend.

#: Fecha fija dentro del ZIP. Los timestamps reales harían que dos paquetes de
#: la misma corrida difirieran en bytes sin diferir en contenido.
_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def _sin_diacriticos(texto: str) -> str:
    """«Inhibición» → «Inhibicion», «ñandú» → «nandu».

    El nombre de archivo es ASCII por portabilidad (ZIP, cabeceras de descarga, otros sistemas), pero la
    lista blanca convertía cada letra con tilde en un guion («Inhibici-n»). Se descomponen y se quitan las
    marcas combinantes ANTES de la lista blanca. Mismo criterio en `services/cohort/repository.py` y en
    `frontend/lib/dossier.ts::sanitizeFilenamePart`: una prueba de paridad los ata (QA1-001).
    """
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def sanitizar(nombre: str, *, maximo: int = 64) -> str:
    """
    Reduce un texto a un componente de ruta seguro.

    Lista blanca, no lista negra: una lista negra siempre olvida un carácter, y
    aquí un olvido es un escape de directorio dentro del ZIP.
    """
    limpio = re.sub(r"[^A-Za-z0-9._-]+", "-", _sin_diacriticos((nombre or "").strip()))
    # Los puntos consecutivos se colapsan. Un `..` dentro de un componente no
    # puede escapar del directorio —no hay separador— pero deja el nombre con
    # aspecto de traversal, y un verificador ajeno haría bien en rechazarlo.
    # Que el nombre no PAREZCA peligroso también es parte del contrato.
    limpio = re.sub(r"\.{2,}", ".", limpio)
    limpio = re.sub(r"-{2,}", "-", limpio).strip("-._")
    if not limpio:
        limpio = "sin-nombre"
    return limpio[:maximo]


def raiz_paquete(case_id: str, task_id: str | None) -> str:
    """Raíz estable: `moldesign_case_<caso>_run_<corrida-corta>`."""
    corta = sanitizar(task_id or "sin-corrida", maximo=12)
    return f"moldesign_case_{sanitizar(case_id, maximo=40)}_run_{corta}"


@dataclass(frozen=True)
class EntradaManifiesto:
    path: str
    rol: str
    media_type: str
    tamano: int | None
    sha256: str | None
    fuente: str
    estado: str
    razon: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "rol": self.rol,
            "media_type": self.media_type,
            "tamano": self.tamano,
            "sha256": self.sha256,
            "fuente": self.fuente,
            "estado": self.estado,
            "razon": self.razon,
        }


def _json_canonico(payload: Any) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _sha256(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def _protocolo(dossier: CaseDossier) -> dict[str, Any]:
    """Parámetros con los que se puede repetir la corrida."""
    return {
        "schema_version": dossier.schema_version,
        "molecule_id": dossier.molecule_id,
        "task_id": dossier.task_id,
        "target": dossier.target_label,
        "parametros": {c.etiqueta: c.as_dict() for c in dossier.protocolo},
        "entradas": {c.etiqueta: c.as_dict() for c in dossier.entradas},
        "procedencia": dossier.procedencia,
    }


def _receta(dossier: CaseDossier, raiz: str) -> str:
    """
    Receta de reproducción. Describe, no promete.

    No incluye un comando que «reproduzca» la corrida con un clic: el producto
    todavía no expone una entrada por línea de comandos que acepte este
    protocolo, y escribir un comando que no existe sería peor que no escribir
    ninguno.
    """
    return """# {titulo}

{paquete}: `{raiz}`
{modelo}: v{version}
{generado}: {fecha}

## {que_se_ejecuto}

- {receptor}: {target}
- {corrida}: {task_id}
- {molecula}: {molecule_id}

{parametros}

## {integridad}

```
python scripts/verify_dossier_package.py <este-archivo>.zip
```

{veredicto}

## {repetir}

{con_moldesign}

{fuera_moldesign}

## {evidencia_cruda}

{evidencia_estructural}
{seleccion}
{indice}
{modelo_selector}

{configuracion}

{conformeros}

{pdf}

{dos_cosas}

## {garantias}

{reproducibilidad}
{validez}
{checksum}
{compuesto}
""".format(
        titulo=translate_text("Cómo reproducir esta corrida"),
        paquete=translate_text("Paquete"),
        raiz=raiz,
        modelo=translate_text("Modelo del dossier"),
        version=dossier.schema_version,
        generado=translate_text("Generado"),
        fecha=dossier.generated_at,
        que_se_ejecuto=translate_text("1. Qué se ejecutó"),
        receptor=translate_text("Receptor"),
        target=dossier.target_label,
        corrida=translate_text("Corrida"),
        task_id=dossier.task_id or translate_text("sin identificador"),
        molecula=translate_text("Molécula"),
        molecule_id=dossier.molecule_id or translate_text("no resuelta"),
        parametros=translate_text(
            "Los parámetros exactos están en `run/protocol.json`, campo `parametros`. Cada\n"
            "uno lleva su estado: los que digan `NO_DISPONIBLE` no fueron serializados por la\n"
            "corrida y **no se pueden reproducir a ciegas**."
        ),
        integridad=translate_text("2. Comprobar primero la integridad"),
        veredicto=translate_text(
            "Si el resultado no es `VÁLIDO`, no reproduzcas nada: el paquete no describe lo\n"
            "que dice describir."
        ),
        repetir=translate_text("3. Repetir el acoplamiento"),
        con_moldesign=translate_text(
            "Con MolDesign: abre el caso, restaura los inputs de `case/case_snapshot.json`,\n"
            "ejecuta la comprobación previa y compara la huella resultante con\n"
            "`input_fingerprint`. Si coincide, la corrida nueva parte de la misma hipótesis."
        ),
        fuera_moldesign=translate_text(
            "Fuera de MolDesign: consulta el estado de cada campo en `run/protocol.json`.\n"
            "Sólo los valores `REGISTRADO` proceden de la corrida; los `NO_DISPONIBLE`\n"
            "impiden afirmar que el cálculo puede reconstruirse. Usa\n"
            "`inputs/ligand_docked.smi` para la especie acoplada y `inputs/ligand.smi`\n"
            "para la entrada original, cuando ambos archivos estén registrados. Comprueba\n"
            "también el receptor preparado y la caja de búsqueda efectiva antes de repetir Vina.\n"
            "Los archivos `inputs/ligand_input.sdf`, `inputs/ligand_input.pdbqt` y\n"
            "`logs/vina.log` llevan los bytes archivados cuando sus SHA-256 coincidieron\n"
            "con la procedencia de la corrida; su ausencia queda declarada en el manifiesto."
        ),
        evidencia_cruda=translate_text("3.1. La evidencia estructural, en crudo"),
        evidencia_estructural=translate_text(
            "- `evidencia/structural_evidence.json` — veredicto físico POR POSE tal y como lo\n"
            "  persistió el backend: motor, cobertura, controles que fallan y su razón."
        ),
        seleccion=translate_text(
            "- `evidencia/pose_selection.json` — la recomendación del selector: Vina top-1,\n"
            "  pose sugerida, margen, umbral, abstención y alternativas."
        ),
        indice=translate_text(
            "- `evidencia/pose_index.json` — qué pose es cuál y a qué bloque PDBQT exacto\n"
            "  apunta. `outputs/poses.sdf` aparece además sólo cuando representa de verdad\n"
            "  la colección; en un ensemble no se finge que el SDF de una conformación sea\n"
            "  la piscina completa."
        ),
        modelo_selector=translate_text(
            "- `evidencia/pose_selector_model.json` — modelo, versión y SHA-256 del selector."
        ),
        configuracion=translate_text(
            "La configuración de la corrida NO se repite aquí: vive en `run/protocol.json`,\n"
            "donde cada parámetro lleva además su estado. Un segundo archivo con los mismos\n"
            "valores en plano crearía dos sitios donde mirar y ninguna comprobación nueva."
        ),
        conformeros=translate_text(
            "El protocolo registra conformeros solicitados y generados cuando la etapa\n"
            "los informó. No registra una serie completa de restarts; ningún campo ausente\n"
            "se rellena desde la configuración declarada por el caso."
        ),
        pdf=translate_text(
            "El PDF es una lectura de estos archivos. Están en crudo para que se pueda\n"
            "comprobar que el documento no añadió, quitó ni suavizó nada."
        ),
        dos_cosas=translate_text(
            "Dos cosas que estos archivos NO dicen: `review` no significa pose aprobada —la\n"
            "batería no corrió entera—, y `not_evaluated` describe lo que le pasó al\n"
            "validador, nunca a la molécula. Ninguna de las dos es evidencia negativa sobre\n"
            "el compuesto."
        ),
        garantias=translate_text("4. Qué NO garantiza este paquete"),
        reproducibilidad=translate_text(
            "- No garantiza que el resultado sea reproducible bit a bit: eso depende de la\n"
            "  versión del motor y del hardware."
        ),
        validez=translate_text(
            "- No garantiza validez científica. Los estados del dossier dicen qué se\n"
            "  comprobó y qué no."
        ),
        checksum=translate_text(
            "- **Un checksum correcto demuestra integridad, no validez.** Prueba que los\n"
            "  archivos coinciden con el manifiesto y los checksums que trae el propio paquete;\n"
            "  que no cambiaron desde la exportación sólo se comprueba contra una huella\n"
            "  guardada aparte. No prueba que el método\n"
            "  fuera adecuado, que la preparación fuera correcta ni que la conclusión sea\n"
            "  cierta. Que el paquete sea `VÁLIDO` es una afirmación sobre los archivos, no\n"
            "  sobre la ciencia."
        ),
        compuesto=translate_text(
            "- No afirma que el compuesto sea activo, eficaz, seguro ni un candidato a\n"
            "  fármaco. Nada en este paquete sostiene esa clase de conclusión."
        ),
    )


def _readme(dossier: CaseDossier, entradas: list[EntradaManifiesto], raiz: str) -> str:
    ausentes = [e for e in entradas if e.estado != Estado.REGISTRADO.value]
    lineas_ausentes = (
        "\n".join(
            f"- `{e.path}` — **{e.estado}**: {translate_text(e.razon or 'sin razón registrada')}"
            for e in ausentes
        )
        or f"- {translate_text('Ninguno: todos los artefactos declarados están presentes.')}"
    )
    glosario = "\n".join(
        f"- **{translate_text(ETIQUETA[e])}** — {translate_text(GLOSARIO[e])}"
        for e in Estado
    )
    contraparte = translate_text(
        "La contraparte verificable de `dossier.pdf`. El PDF es la lectura humana del\n"
        "caso; este paquete permite comprobar que esa lectura se hizo sobre los archivos\n"
        "que declara, y detectar si alguno falta o cambió."
    )
    declaracion_no_recomendacion = translate_text(
        "No es una recomendación. No afirma que la molécula sea un fármaco, un candidato\n"
        "clínico ni un compuesto seguro. Los índices 0-100 que aparecen en el apéndice\n"
        "del PDF no son probabilidad, confianza ni calidad, y no son decisionales."
    )
    texto_verificador = translate_text(
        "El verificador comprueba, sin extraer ni ejecutar nada: que ninguna entrada\n"
        "escape del directorio raíz, que el manifiesto sea de una versión compatible,\n"
        "que todos los archivos declarados existan, que sus SHA-256 y tamaños coincidan,\n"
        "que no haya duplicados y que no haya archivos no declarados."
    )
    exclusion_zip = translate_text(
        "1. **El ZIP no se contiene a sí mismo.** Un paquete que llevara su propia copia\n"
        "   no podría cerrarse: su hash cambiaría al incluirlo."
    )
    exclusion_checksums = translate_text(
        "2. **`checksums.sha256` no se hashea a sí mismo.** Escribir su hash dentro de sí\n"
        "   mismo es imposible por la misma razón."
    )
    exclusion_manifest = translate_text(
        "3. **`manifest.json` no se declara a sí mismo** dentro de `files`, por lo mismo.\n"
        "   Su integridad **sí** queda cubierta: `checksums.sha256` se calcula después e\n"
        "   incluye el manifiesto, así que una modificación del manifiesto se detecta."
    )
    explicacion_checksum = translate_text(
        "Un checksum correcto demuestra **integridad, no validez**: prueba que los archivos\n"
        "coinciden con el manifiesto y los checksums que trae el propio paquete; que no\n"
        "cambiaron desde la exportación sólo se comprueba contra una huella guardada aparte.\n"
        "No prueba que el método fuera\n"
        "adecuado, que la preparación fuera correcta, que las poses sean físicamente\n"
        "razonables ni que la conclusión sea cierta. Que el verificador diga `VÁLIDO` es\n"
        "una afirmación sobre los ARCHIVOS, nunca sobre la ciencia — y nada en este\n"
        "paquete afirma que el compuesto sea activo, eficaz o seguro."
    )
    texto_artefacto_ausente = translate_text(
        "Un archivo ausente se declara; no se sustituye por un marcador que parezca el\n"
        "artefacto."
    )

    return f"""# {translate_text('Dossier reproducible')} · {dossier.case_name}

{translate_text('Paquete')}: `{raiz}`
{translate_text('Caso')}: `{dossier.case_id}`
{translate_text('Corrida')}: `{dossier.task_id or translate_text('sin identificador')}`
{translate_text('Receptor')}: {dossier.target_label}
{translate_text('Generado')}: {dossier.generated_at}
{translate_text('Modelo del dossier')}: v{dossier.schema_version} · {translate_text('manifiesto')} v{MANIFEST_VERSION}

## {translate_text('Qué es esto')}

{contraparte}

{translate_text('**Ninguno sustituye al otro.**')}

## {translate_text('Qué NO es')}

{declaracion_no_recomendacion}

## {translate_text('Estructura')}

```
{raiz}/
├── README.md              {translate_text('este archivo')}
├── dossier.pdf            {translate_text('lectura humana del caso')}
├── manifest.json          {translate_text('rol, tamaño, SHA-256 y estado de cada archivo')}
├── checksums.sha256       {translate_text('índice ordenado de hashes')}
├── case/                  {translate_text('proyección del caso y modelo canónico')}
├── run/                   {translate_text('protocolo y receta de reproducción')}
├── inputs/                {translate_text('receptor y ligando, cuando existen')}
├── outputs/               {translate_text('poses y resultados serializados')}
├── evidencia/             {translate_text('evidencia estructural, selección y controles')}
├── preparacion/           {translate_text('auditoría de preparación: qué bloquea, qué revisar y qué se decidió')}
└── logs/                  {translate_text('advertencias y errores de ESTA corrida')}
```

## {translate_text('Integridad')}

{translate_text('Para verificar')}:

```
python scripts/verify_dossier_package.py <este-archivo>.zip
```

{texto_verificador}

### {translate_text('Tres exclusiones deliberadas')}

{exclusion_zip}
{exclusion_checksums}
{exclusion_manifest}

{translate_text('El verificador conoce las tres y no las reporta como archivos no declarados.')}

### {translate_text('Qué demuestra un checksum, y qué no')}

{explicacion_checksum}

## {translate_text('Artefactos ausentes')}

{texto_artefacto_ausente}

{lineas_ausentes}

## {translate_text('Glosario de estados')}

{glosario}
"""


# ── Núcleo genérico del protocolo ────────────────────────────────────
#
# EXISTE PARA QUE NO HAYA DOS PROTOCOLOS. El paquete del CASO (Sprint 4) y el
# de la COHORTE (Sprint 5D) empaquetan cosas distintas, pero la forma de
# declarar, hashear y sellar es la misma — y tiene que seguir siéndolo, porque
# `services/dossier/verify.py` es un solo verificador para los dos.
#
# Lo que este núcleo fija, y ninguno de los dos llamadores puede cambiar:
#
#   · `manifest.json` no se declara a sí mismo (su hash cambiaría al escribirlo)
#   · `checksums.sha256` se calcula DESPUÉS, sobre todo lo demás, incluido el
#     manifiesto — que es lo que hace que adulterar el manifiesto se detecte
#   · una sola carpeta raíz, escritura determinista, sin symlinks
#   · un artefacto ausente se DECLARA con su estado y su razón; no se omite
#
# Duplicar esto para las cohortes habría creado un segundo protocolo que
# divergiría a la primera corrección, y un verificador que sólo entiende a uno
# de los dos.


@dataclass(frozen=True)
class ArchivoPaquete:
    """
    Un archivo del paquete. `datos=None` significa AUSENTE, no vacío.

    La diferencia importa: un archivo vacío es un archivo, y uno ausente es una
    declaración de que no se pudo incluir. El manifiesto los distingue con
    `estado` y `razon`, y quien verifique tiene que poder leer esa diferencia.
    """

    path: str
    datos: bytes | None
    rol: str
    media_type: str
    fuente: str
    estado: str = Estado.REGISTRADO.value
    razon: str | None = None


def empaquetar(
    *,
    raiz: str,
    archivos: Iterable[ArchivoPaquete],
    manifiesto_extra: dict[str, Any] | None = None,
) -> tuple[bytes, list[EntradaManifiesto], str]:
    """
    Arma el ZIP con el protocolo del producto. Devuelve `(bytes, entradas, raiz)`.

    El orden de escritura es fijo: los archivos en el orden en que llegan, y
    después `manifest.json` y `checksums.sha256`, que describen a los
    anteriores. La escritura al ZIP se ordena por ruta y con marca de tiempo
    fija, para que dos paquetes con el mismo contenido sean byte a byte iguales.
    """
    entradas: list[EntradaManifiesto] = []
    contenidos: list[tuple[str, bytes]] = []

    for archivo in archivos:
        if archivo.datos is not None:
            entradas.append(EntradaManifiesto(
                path=archivo.path, rol=archivo.rol, media_type=archivo.media_type,
                tamano=len(archivo.datos), sha256=_sha256(archivo.datos),
                fuente=archivo.fuente, estado=Estado.REGISTRADO.value,
            ))
            contenidos.append((archivo.path, archivo.datos))
        else:
            entradas.append(EntradaManifiesto(
                path=archivo.path, rol=archivo.rol, media_type=archivo.media_type,
                tamano=None, sha256=None, fuente=archivo.fuente,
                estado=archivo.estado,
                razon=archivo.razon or translate_text(
                    "El artefacto no estaba disponible al construir el paquete."
                ),
            ))

    manifiesto = {
        "manifest_version": MANIFEST_VERSION,
        "root": raiz,
        **(manifiesto_extra or {}),
        "exclusiones": {
            "manifest.json": (
                translate_text(
                    "No se declara a sí mismo: su hash cambiaría al escribirlo. Su integridad la "
                    "cubre `checksums.sha256`, que se calcula después."
                )
            ),
            "checksums.sha256": translate_text(
                "No se hashea a sí mismo: su hash cambiaría al escribirlo."
            ),
            "<paquete>.zip": translate_text("El paquete no se contiene a sí mismo."),
        },
        "files": [e.as_dict() for e in sorted(entradas, key=lambda e: e.path)],
    }
    contenidos.append(("manifest.json", _json_canonico(manifiesto)))

    lineas = sorted(f"{_sha256(datos)}  {path}" for path, datos in contenidos)
    contenidos.append((CHECKSUMS_NAME, ("\n".join(lineas) + "\n").encode("utf-8")))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path, datos in sorted(contenidos, key=lambda item: item[0]):
            info = zipfile.ZipInfo(f"{raiz}/{path}", date_time=_ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            info.create_system = 0  # MS-DOS: estable entre plataformas
            zf.writestr(info, datos)

    return buf.getvalue(), entradas, raiz


def construir_paquete(
    *,
    dossier: CaseDossier,
    pdf_bytes: bytes,
    projection_json: str,
    artefactos: Iterable[Artefacto] = (),
    preparacion: dict[str, Any] | None = None,
) -> tuple[bytes, list[EntradaManifiesto], str]:
    """
    Arma el ZIP del CASO. Devuelve `(bytes, entradas, raiz)`.

    Decide QUÉ va dentro; el CÓMO —manifiesto, checksums, escritura
    determinista— lo pone `empaquetar`, que es el mismo núcleo que usa el
    paquete de cohorte. Un solo protocolo, un solo verificador.

    `preparacion` es la auditoría que enseña la pestaña, la MISMA que se
    serializa aquí: quien reciba el paquete tiene que poder leer qué bloqueaba,
    qué pedía revisión y qué decidió el investigador, sin volver a calcularla.
    """
    dossier = traducir_dossier(dossier, current_locale())
    raiz = raiz_paquete(dossier.case_id, dossier.task_id)
    modelo_json = _json_canonico(dossier_dict_localizado(dossier, current_locale()))
    archivos: list[ArchivoPaquete] = [
        ArchivoPaquete("dossier.pdf", pdf_bytes, "lectura_humana",
                       "application/pdf", "services.dossier.pdf"),
        ArchivoPaquete("case/case_snapshot.json", projection_json.encode("utf-8"),
                       "proyeccion_del_caso", "application/json",
                       translate_text("cliente (proyección validada)")),
        ArchivoPaquete("case/dossier_model.json", modelo_json,
                       "modelo_canonico", "application/json", "services.dossier.model"),
        ArchivoPaquete("run/protocol.json", _json_canonico(_protocolo(dossier)),
                       "protocolo", "application/json", "services.dossier.model"),
        ArchivoPaquete("run/reproduce.md", _receta(dossier, raiz).encode("utf-8"),
                       "receta", "text/markdown", "services.dossier.package"),
        ArchivoPaquete("evidencia/evidence_summary.json", _json_canonico(traducir_dossier({
            "controles": [c.as_dict() for c in dossier.controles],
            "dimensiones": [d.as_dict() for d in dossier.dimensiones],
            "supuestos": dossier.supuestos,
            "incertidumbres": dossier.incertidumbres,
            "siguiente_accion": dossier.siguiente_accion.as_dict(),
            "decisiones_humanas": dossier.decisiones,
            "avisos_integridad": dossier.avisos_integridad,
        }, current_locale())), "evidencia", "application/json", "services.dossier.model"),
    ]
    if preparacion is not None:
        # No se declara ausente cuando no se pasa: eso diría «no se pudo construir» de
        # algo que nadie intentó. La ruta del paquete la construye siempre.
        archivos.append(ArchivoPaquete(
            "preparacion/audit.json", _json_canonico(preparacion),
            "auditoria_de_preparacion", "application/json", "services.dossier.preparacion",
        ))

    for artefacto in artefactos:
        path = f"{artefacto.rol}/{sanitizar(artefacto.nombre, maximo=80)}"
        disponible = artefacto.estado == Estado.REGISTRADO and artefacto.contenido
        archivos.append(ArchivoPaquete(
            path=path,
            datos=artefacto.contenido if disponible else None,
            rol=artefacto.rol,
            media_type=artefacto.media_type,
            fuente=artefacto.fuente,
            estado=Estado.REGISTRADO.value if disponible else artefacto.estado.value,
            razon=None if disponible else translate_text(artefacto.razon or ""),
        ))

    # El README necesita conocer las ausencias, así que se calculan las entradas
    # una primera vez sin él y se vuelve a empaquetar con él dentro. Es barato
    # (todo está en memoria) y evita un README que declare archivos que no están.
    _, entradas_previas, _ = empaquetar(raiz=raiz, archivos=archivos)
    archivos.append(ArchivoPaquete(
        "README.md", _readme(dossier, entradas_previas, raiz).encode("utf-8"),
        "lectura_humana", "text/markdown", "services.dossier.package",
    ))

    return empaquetar(
        raiz=raiz,
        archivos=archivos,
        manifiesto_extra={
            "dossier_schema_version": dossier.schema_version,
            "generated_at": dossier.generated_at,
            "case_id": dossier.case_id,
            "task_id": dossier.task_id,
            "molecule_id": dossier.molecule_id,
            "dossier_model_sha256": _sha256(modelo_json),
            **({"preparacion": {
                "estado": preparacion.get("estado"),
                "bloqueantes": preparacion.get("bloqueantes"),
                "en_revision": preparacion.get("en_revision"),
                # Cuáles de ésas pide toda corrida de esta ruta: el resto es de este caso.
                "en_revision_rutinaria": preparacion.get("en_revision_rutinaria"),
                "decididos": preparacion.get("decididos"),
            }} if preparacion else {}),
        },
    )
