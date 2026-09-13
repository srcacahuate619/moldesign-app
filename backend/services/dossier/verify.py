"""
Verificador del paquete reproducible.

# La regla que no se negocia

**Nunca se extrae ni se ejecuta nada.** Se lee la tabla del ZIP y se hashea el
contenido en memoria. Un verificador que extrajera sería la vía de entrada más
obvia para un zip-slip: basta una entrada llamada `../../autostart/x.exe` para
que «comprobar la integridad» se convierta en escribir donde no debe.

Por eso el orden de comprobación empieza por las rutas, antes de leer un solo
byte de contenido.

# Qué se comprueba

1. las rutas: ninguna absoluta, con `..`, con `\\` o fuera de la raíz;
2. sin entradas duplicadas;
3. el manifiesto existe, es JSON y su versión es compatible;
4. cada archivo declarado existe;
5. tamaño y SHA-256 coinciden;
6. no hay archivos no declarados, salvo las tres exclusiones documentadas;
7. `checksums.sha256` concuerda con el contenido real.

El resultado es binario y con motivos: **VÁLIDO** o **INVÁLIDO**. Un paquete que
falle una sola comprobación es inválido — no hay «válido con reservas», porque
un lector que ve «válido» no lee la letra pequeña.
"""

from __future__ import annotations

import hashlib
import json
import posixpath
import zipfile
from dataclasses import dataclass, field
from typing import Any

from services.dossier.package import CHECKSUMS_NAME, MANIFEST_VERSION

#: Archivos que el manifiesto no declara por construcción, porque no pueden
#: contener su propio hash. Documentado en el README del propio paquete para que
#: un verificador ajeno pueda reproducir el criterio.
#:
#: Que estén excluidos de `files` NO los deja sin comprobar: `checksums.sha256`
#: cubre `manifest.json`, y el manifiesto cubre todo lo demás. El único archivo
#: sin hash propio es `checksums.sha256`, que es la raíz de la cadena.
# Archivos que no aparecen dentro de `manifest.files`. El manifiesto no puede
# declararse a si mismo y el indice de hashes tampoco forma parte de ese
# inventario.
_NO_DECLARADOS = {CHECKSUMS_NAME, "manifest.json"}

# Solo el indice de hashes queda fuera de su propia cobertura. `manifest.json`
# SI aparece en checksums.sha256; excluirlo tambien aqui dejaria modificable la
# pieza que define que archivos y hashes son validos.
_NO_HASHEADOS = {CHECKSUMS_NAME}


@dataclass
class ResultadoVerificacion:
    valido: bool = True
    raiz: str | None = None
    manifest_version: int | None = None
    archivos_declarados: int = 0
    archivos_presentes: int = 0
    errores: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    def error(self, mensaje: str) -> None:
        self.valido = False
        self.errores.append(mensaje)

    def as_dict(self) -> dict[str, Any]:
        return {
            "valido": self.valido,
            "raiz": self.raiz,
            "manifest_version": self.manifest_version,
            "archivos_declarados": self.archivos_declarados,
            "archivos_presentes": self.archivos_presentes,
            "errores": self.errores,
            "avisos": self.avisos,
        }

    def informe(self) -> str:
        cabecera = "VÁLIDO" if self.valido else "INVÁLIDO"
        lineas = [
            f"{cabecera}",
            f"  raíz:        {self.raiz or '(no determinada)'}",
            f"  manifiesto:  v{self.manifest_version if self.manifest_version is not None else '?'}",
            f"  archivos:    {self.archivos_presentes} presentes / {self.archivos_declarados} declarados",
        ]
        for aviso in self.avisos:
            lineas.append(f"  aviso:   {aviso}")
        for error in self.errores:
            lineas.append(f"  ERROR:   {error}")
        return "\n".join(lineas)


def _ruta_peligrosa(nombre: str) -> str | None:
    """Devuelve el motivo si la entrada no es segura, o `None` si lo es."""
    if nombre.startswith("/") or nombre.startswith("\\"):
        return "ruta absoluta"
    if len(nombre) > 1 and nombre[1] == ":":
        return "ruta con unidad de disco"
    if "\\" in nombre:
        return "separador de Windows en la entrada del ZIP"
    partes = nombre.split("/")
    if any(parte == ".." for parte in partes):
        return "componente `..` (escape de directorio)"
    if any(parte in ("", ".") for parte in partes[:-1]):
        return "componente vacío o `.`"
    return None


def verificar_paquete(datos: bytes) -> ResultadoVerificacion:
    """Verifica un paquete en memoria. No extrae, no ejecuta, no escribe."""
    resultado = ResultadoVerificacion()

    try:
        zf = zipfile.ZipFile(__import__("io").BytesIO(datos))
    except zipfile.BadZipFile as exc:
        resultado.error(f"El archivo no es un ZIP legible: {exc}")
        return resultado

    with zf:
        infos = zf.infolist()
        if not infos:
            resultado.error("El paquete está vacío.")
            return resultado

        # ── 1. Rutas, ANTES de leer contenido ────────────────────────
        vistos: set[str] = set()
        for info in infos:
            motivo = _ruta_peligrosa(info.filename)
            if motivo:
                resultado.error(f"Entrada insegura `{info.filename}`: {motivo}.")
            if info.filename in vistos:
                resultado.error(f"Entrada duplicada en el ZIP: `{info.filename}`.")
            vistos.add(info.filename)
            # Enlaces simbólicos: bit S_IFLNK en los permisos Unix del ZIP.
            if (info.external_attr >> 16) & 0xF000 == 0xA000:
                resultado.error(f"Entrada `{info.filename}` es un enlace simbólico.")

        if not resultado.valido:
            return resultado

        # ── 2. Raíz única ────────────────────────────────────────────
        raices = {name.split("/")[0] for name in vistos}
        if len(raices) != 1:
            resultado.error(f"El paquete debe tener una sola carpeta raíz; tiene {sorted(raices)}.")
            return resultado
        raiz = raices.pop()
        resultado.raiz = raiz

        relativos = {
            posixpath.relpath(name, raiz): name
            for name in vistos
            if name != f"{raiz}/" and not name.endswith("/")
        }

        # ── 3. Manifiesto ────────────────────────────────────────────
        if "manifest.json" not in relativos:
            resultado.error("Falta `manifest.json`.")
            return resultado
        try:
            manifiesto = json.loads(zf.read(relativos["manifest.json"]).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            resultado.error(f"`manifest.json` no es JSON válido: {exc}")
            return resultado

        version = manifiesto.get("manifest_version")
        resultado.manifest_version = version if isinstance(version, int) else None
        if not isinstance(version, int):
            resultado.error("`manifest.json` no declara `manifest_version` entera.")
            return resultado
        if version < 1 or version > MANIFEST_VERSION:
            resultado.error(
                f"El manifiesto es v{version} y este verificador soporta "
                f"versiones entre v1 y v{MANIFEST_VERSION}."
            )
            return resultado

        declarados = manifiesto.get("files")
        if not isinstance(declarados, list):
            resultado.error("`manifest.json` no declara una lista `files`.")
            return resultado
        resultado.archivos_declarados = len(declarados)

        # ── 4. Cada archivo declarado ────────────────────────────────
        paths_declarados: set[str] = set()
        for entrada in declarados:
            if not isinstance(entrada, dict):
                resultado.error("Una entrada del manifiesto no es un objeto JSON.")
                continue
            path = entrada.get("path")
            if not isinstance(path, str) or not path:
                resultado.error("Una entrada del manifiesto no tiene `path`.")
                continue
            motivo = _ruta_peligrosa(path)
            if motivo:
                resultado.error(f"Ruta insegura en el manifiesto `{path}`: {motivo}.")
                continue
            if path in paths_declarados:
                resultado.error(f"Ruta duplicada en el manifiesto: `{path}`.")
                continue
            paths_declarados.add(path)

            estado = entrada.get("estado")
            if estado != "REGISTRADO":
                # Ausencia declarada: correcta si de verdad no está.
                if path in relativos:
                    resultado.error(
                        f"`{path}` se declara `{estado}` pero el paquete SÍ lo contiene."
                    )
                continue

            if path not in relativos:
                resultado.error(f"Falta el archivo declarado `{path}`.")
                continue

            contenido = zf.read(relativos[path])
            resultado.archivos_presentes += 1

            tamano = entrada.get("tamano")
            if isinstance(tamano, int) and tamano != len(contenido):
                resultado.error(
                    f"`{path}`: tamaño {len(contenido)} B, el manifiesto declara {tamano} B."
                )
            sha = entrada.get("sha256")
            real = hashlib.sha256(contenido).hexdigest()
            if isinstance(sha, str) and sha != real:
                resultado.error(f"`{path}`: SHA-256 no coincide (modificado).")

        # ── 5. Archivos no declarados ────────────────────────────────
        for path in sorted(relativos):
            if path in _NO_DECLARADOS or path in paths_declarados:
                continue
            resultado.error(f"`{path}` está en el paquete y no lo declara el manifiesto.")

        # ── 6. checksums.sha256 ──────────────────────────────────────
        if CHECKSUMS_NAME not in relativos:
            resultado.error(f"Falta `{CHECKSUMS_NAME}`.")
        else:
            try:
                lineas = zf.read(relativos[CHECKSUMS_NAME]).decode("utf-8").splitlines()
            except UnicodeDecodeError as exc:
                resultado.error(f"`{CHECKSUMS_NAME}` no es texto UTF-8: {exc}")
                lineas = []
            indice: dict[str, str] = {}
            for linea in lineas:
                if not linea.strip():
                    continue
                partes = linea.split("  ", 1)
                if len(partes) != 2:
                    resultado.error(f"Línea mal formada en `{CHECKSUMS_NAME}`: {linea[:60]!r}")
                    continue
                path_indice = partes[1]
                if path_indice in indice:
                    resultado.error(
                        f"`{CHECKSUMS_NAME}` contiene una ruta duplicada: `{path_indice}`."
                    )
                    continue
                indice[path_indice] = partes[0]

            if lineas != sorted(lineas):
                resultado.error(f"`{CHECKSUMS_NAME}` no está ordenado.")

            for path, nombre_zip in sorted(relativos.items()):
                if path in _NO_HASHEADOS:
                    continue
                esperado = indice.get(path)
                if esperado is None:
                    resultado.error(f"`{path}` no aparece en `{CHECKSUMS_NAME}`.")
                    continue
                real = hashlib.sha256(zf.read(nombre_zip)).hexdigest()
                if esperado != real:
                    resultado.error(f"`{path}`: el hash de `{CHECKSUMS_NAME}` no coincide.")
            for path in sorted(set(indice) - set(relativos)):
                resultado.error(f"`{CHECKSUMS_NAME}` lista `{path}`, que no está en el paquete.")
            for path in sorted(_NO_HASHEADOS & set(indice)):
                resultado.error(
                    f"`{CHECKSUMS_NAME}` no debe contener su propio hash (`{path}`)."
                )

    return resultado


def verificar_archivo(ruta: str) -> ResultadoVerificacion:
    """Verifica un ZIP en disco. Lo lee entero: nunca lo abre por ruta interna."""
    with open(ruta, "rb") as fh:
        return verificar_paquete(fh.read())
