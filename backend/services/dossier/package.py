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
import zipfile
from dataclasses import dataclass
from typing import Any, Iterable

from services.dossier.model import Artefacto, CaseDossier, hash_canonico
from services.dossier.taxonomy import ETIQUETA, GLOSARIO, Estado

#: Versión del manifiesto. El verificador la comprueba antes de nada.
MANIFEST_VERSION = 1

#: Nombre del índice de hashes. No se hashea a sí mismo.
CHECKSUMS_NAME = "checksums.sha256"

#: Fecha fija dentro del ZIP. Los timestamps reales harían que dos paquetes de
#: la misma corrida difirieran en bytes sin diferir en contenido.
_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def sanitizar(nombre: str, *, maximo: int = 64) -> str:
    """
    Reduce un texto a un componente de ruta seguro.

    Lista blanca, no lista negra: una lista negra siempre olvida un carácter, y
    aquí un olvido es un escape de directorio dentro del ZIP.
    """
    limpio = re.sub(r"[^A-Za-z0-9._-]+", "-", (nombre or "").strip())
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
    return f"""# Cómo reproducir esta corrida

Paquete: `{raiz}`
Modelo del dossier: v{dossier.schema_version}
Generado: {dossier.generated_at}

## 1. Qué se ejecutó

- Receptor: {dossier.target_label}
- Corrida: {dossier.task_id or "sin identificador"}
- Molécula: {dossier.molecule_id or "no resuelta"}

Los parámetros exactos están en `run/protocol.json`, campo `parametros`. Cada
uno lleva su estado: los que digan `NO_DISPONIBLE` no fueron serializados por la
corrida y **no se pueden reproducir a ciegas**.

## 2. Comprobar primero la integridad

```
python scripts/verify_dossier_package.py <este-archivo>.zip
```

Si el resultado no es `VÁLIDO`, no reproduzcas nada: el paquete no describe lo
que dice describir.

## 3. Repetir el acoplamiento

Con MolDesign: abre el caso, restaura los inputs de `case/case_snapshot.json`,
ejecuta la comprobación previa y compara la huella resultante con
`input_fingerprint`. Si coincide, la corrida nueva parte de la misma hipótesis.

Fuera de MolDesign: `run/protocol.json` lleva motor, versión, semilla,
exhaustividad y caja. Con el receptor y el ligando de `inputs/` puede repetirse
el acoplamiento con AutoDock Vina directamente.

## 3.1. La evidencia estructural, en crudo

- `evidencia/structural_evidence.json` — veredicto físico POR POSE tal y como lo
  persistió el backend: motor, cobertura, controles que fallan y su razón.
- `evidencia/pose_selection.json` — la recomendación del selector: Vina top-1,
  pose sugerida, margen, umbral, abstención y alternativas.
- `evidencia/pose_index.json` — qué pose es cuál y a qué bloque PDBQT exacto
  apunta. `outputs/poses.sdf` aparece además sólo cuando representa de verdad
  la colección; en un ensemble no se finge que el SDF de una conformación sea
  la piscina completa.
- `evidencia/pose_selector_model.json` — modelo, versión y SHA-256 del selector.

La configuración de la corrida NO se repite aquí: vive en `run/protocol.json`,
donde cada parámetro lleva además su estado. Un segundo archivo con los mismos
valores en plano crearía dos sitios donde mirar y ninguna comprobación nueva.

Conformeros y restarts no aparecen en ninguno de los dos: el resultado no los
persiste, y rellenarlos desde la configuración del caso les atribuiría a esta
corrida un ajuste que nadie guardó con ella.

El PDF es una lectura de estos archivos. Están en crudo para que se pueda
comprobar que el documento no añadió, quitó ni suavizó nada.

Dos cosas que estos archivos NO dicen: `review` no significa pose aprobada —la
batería no corrió entera—, y `not_evaluated` describe lo que le pasó al
validador, nunca a la molécula. Ninguna de las dos es evidencia negativa sobre
el compuesto.

## 4. Qué NO garantiza este paquete

- No garantiza que el resultado sea reproducible bit a bit: eso depende de la
  versión del motor y del hardware.
- No garantiza validez científica. Los estados del dossier dicen qué se
  comprobó y qué no.
- **Un checksum correcto demuestra integridad, no validez.** Prueba que los
  bytes no cambiaron desde que se generó el paquete. No prueba que el método
  fuera adecuado, que la preparación fuera correcta ni que la conclusión sea
  cierta. Que el paquete sea `VÁLIDO` es una afirmación sobre los archivos, no
  sobre la ciencia.
- No afirma que el compuesto sea activo, eficaz, seguro ni un candidato a
  fármaco. Nada en este paquete sostiene esa clase de conclusión.
"""


def _readme(dossier: CaseDossier, entradas: list[EntradaManifiesto], raiz: str) -> str:
    ausentes = [e for e in entradas if e.estado != Estado.REGISTRADO.value]
    lineas_ausentes = (
        "\n".join(f"- `{e.path}` — **{e.estado}**: {e.razon or 'sin razón registrada'}" for e in ausentes)
        or "- Ninguno: todos los artefactos declarados están presentes."
    )
    glosario = "\n".join(f"- **{ETIQUETA[e]}** — {GLOSARIO[e]}" for e in Estado)

    return f"""# Dossier reproducible · {dossier.case_name}

Paquete: `{raiz}`
Caso: `{dossier.case_id}`
Corrida: `{dossier.task_id or "sin identificador"}`
Receptor: {dossier.target_label}
Generado: {dossier.generated_at}
Modelo del dossier: v{dossier.schema_version} · manifiesto v{MANIFEST_VERSION}

## Qué es esto

La contraparte verificable de `dossier.pdf`. El PDF es la lectura humana del
caso; este paquete permite comprobar que esa lectura se hizo sobre los archivos
que declara, y detectar si alguno falta o cambió.

**Ninguno sustituye al otro.**

## Qué NO es

No es una recomendación. No afirma que la molécula sea un fármaco, un candidato
clínico ni un compuesto seguro. Los índices 0-100 que aparecen en el apéndice
del PDF no son probabilidad, confianza ni calidad, y no son decisionales.

## Estructura

```
{raiz}/
├── README.md              este archivo
├── dossier.pdf            lectura humana del caso
├── manifest.json          rol, tamaño, SHA-256 y estado de cada archivo
├── checksums.sha256       índice ordenado de hashes
├── case/                  proyección del caso y modelo canónico
├── run/                   protocolo y receta de reproducción
├── inputs/                receptor y ligando, cuando existen
├── outputs/               poses y resultados serializados
├── evidencia/             evidencia estructural, selección y controles
└── logs/                  advertencias y errores de ESTA corrida
```

## Integridad

Para verificar:

```
python scripts/verify_dossier_package.py <este-archivo>.zip
```

El verificador comprueba, sin extraer ni ejecutar nada: que ninguna entrada
escape del directorio raíz, que el manifiesto sea de una versión compatible,
que todos los archivos declarados existan, que sus SHA-256 y tamaños coincidan,
que no haya duplicados y que no haya archivos no declarados.

### Tres exclusiones deliberadas

1. **El ZIP no se contiene a sí mismo.** Un paquete que llevara su propia copia
   no podría cerrarse: su hash cambiaría al incluirlo.
2. **`checksums.sha256` no se hashea a sí mismo.** Escribir su hash dentro de sí
   mismo es imposible por la misma razón.
3. **`manifest.json` no se declara a sí mismo** dentro de `files`, por lo mismo.
   Su integridad **sí** queda cubierta: `checksums.sha256` se calcula después e
   incluye el manifiesto, así que una modificación del manifiesto se detecta.

El verificador conoce las tres y no las reporta como archivos no declarados.

### Qué demuestra un checksum, y qué no

Un checksum correcto demuestra **integridad, no validez**: prueba que los bytes
no cambiaron desde que se generó el paquete. No prueba que el método fuera
adecuado, que la preparación fuera correcta, que las poses sean físicamente
razonables ni que la conclusión sea cierta. Que el verificador diga `VÁLIDO` es
una afirmación sobre los ARCHIVOS, nunca sobre la ciencia — y nada en este
paquete afirma que el compuesto sea activo, eficaz o seguro.

## Artefactos ausentes

Un archivo ausente se declara; no se sustituye por un marcador que parezca el
artefacto.

{lineas_ausentes}

## Glosario de estados

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
                razon=archivo.razon or "El artefacto no estaba disponible al construir el paquete.",
            ))

    manifiesto = {
        "manifest_version": MANIFEST_VERSION,
        "root": raiz,
        **(manifiesto_extra or {}),
        "exclusiones": {
            "manifest.json": (
                "No se declara a sí mismo: su hash cambiaría al escribirlo. Su integridad la "
                "cubre `checksums.sha256`, que se calcula después."
            ),
            "checksums.sha256": "No se hashea a sí mismo: su hash cambiaría al escribirlo.",
            "<paquete>.zip": "El paquete no se contiene a sí mismo.",
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
) -> tuple[bytes, list[EntradaManifiesto], str]:
    """
    Arma el ZIP del CASO. Devuelve `(bytes, entradas, raiz)`.

    Decide QUÉ va dentro; el CÓMO —manifiesto, checksums, escritura
    determinista— lo pone `empaquetar`, que es el mismo núcleo que usa el
    paquete de cohorte. Un solo protocolo, un solo verificador.
    """
    raiz = raiz_paquete(dossier.case_id, dossier.task_id)
    archivos: list[ArchivoPaquete] = [
        ArchivoPaquete("dossier.pdf", pdf_bytes, "lectura_humana",
                       "application/pdf", "services.dossier.pdf"),
        ArchivoPaquete("case/case_snapshot.json", projection_json.encode("utf-8"),
                       "proyeccion_del_caso", "application/json",
                       "cliente (proyección validada)"),
        ArchivoPaquete("case/dossier_model.json", dossier.json_canonico().encode("utf-8"),
                       "modelo_canonico", "application/json", "services.dossier.model"),
        ArchivoPaquete("run/protocol.json", _json_canonico(_protocolo(dossier)),
                       "protocolo", "application/json", "services.dossier.model"),
        ArchivoPaquete("run/reproduce.md", _receta(dossier, raiz).encode("utf-8"),
                       "receta", "text/markdown", "services.dossier.package"),
        ArchivoPaquete("evidencia/evidence_summary.json", _json_canonico({
            "controles": [c.as_dict() for c in dossier.controles],
            "dimensiones": [d.as_dict() for d in dossier.dimensiones],
            "supuestos": dossier.supuestos,
            "incertidumbres": dossier.incertidumbres,
            "siguiente_accion": dossier.siguiente_accion.as_dict(),
            "decisiones_humanas": dossier.decisiones,
            "avisos_integridad": dossier.avisos_integridad,
        }), "evidencia", "application/json", "services.dossier.model"),
    ]

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
            razon=None if disponible else artefacto.razon,
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
            "dossier_model_sha256": hash_canonico(dossier),
        },
    )
