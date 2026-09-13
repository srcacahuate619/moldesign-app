# 82 — De un clon limpio a un instalador, sin depender de que publiquemos nada

Estado: **abierto**. Cierra el bloqueo de arranque; no cierra la publicación.

## 1. El bloqueo

`git clone` y `npm run tauri:build` no bastaban. `python-embed/` está en
`.gitignore` —son ~2,2 GB que no viajan en el repositorio— y **nueve** scripts
npm lo invocan por ruta directa (`..\python-embed\python.exe`). La primera
puerta que lo hace es `check:csp`, así que el mensaje que recibía quien clonaba
hablaba de la política de seguridad de contenido cuando el problema era otro:

```
'..\python-embed\python.exe' is not recognized as an internal or external command
```

Y la única vía documentada para conseguirlo, `bootstrap_dev_tree.py --fetch`,
**se niega a correr**: descarga `runtime-base-v1.1.0.zip`, que no está
publicado, y sin SHA-256 declarado no descarga nada. Correcto, y sin salida.

Un repositorio público del que nadie puede reconstruir el binario distribuido
incumple la promesa que la AGPL le hace a quien lo recibe.

## 2. La decisión: dos vías, ninguna obligatoria

| Vía | Cuándo | Qué reproduce |
|---|---|---|
| `bootstrap_dev_tree.py --fetch` | cuando el artefacto esté publicado | los **bytes** exactos |
| `provision_python_embed.py --fetch` | **hoy**, sin publicar nada | la **lista** exacta del lockfile |

La segunda no necesita Hugging Face ni ninguna decisión de publicación: baja
CPython embebido de **python.org** y las dependencias de **PyPI**, con
`backend/requirements-embed.lock.txt`.

Lo que **no** garantiza, y conviene no confundirlo: bytes idénticos. Las ruedas
se republican y algunas traen extensiones nativas compiladas contra la máquina
que las construyó. Garantiza los 173 nombres y versiones del lockfile, que es
lo que hace falta para construir el instalador.

## 3. Lo medido, contra los índices reales — 2026-09-06

De los 173 paquetes del lockfile:

| Cuántos | De dónde | Cómo |
|---:|---|---|
| 170 | PyPI | rueda binaria; `--only-binary=:all:` los resuelve todos |
| 1 | `abetlen.github.io/llama-cpp-python/whl/cpu` | PyPI no publica rueda para CPython 3.11/Windows |
| 1 | `github.com/openmm/pdbfixer`, tag `v1.12` | **no está en PyPI en ninguna versión** |
| 1 | — | `pip`, que se instala antes que nada |

Los dos casos especiales no son manías. Sin el primero, pip cae a compilar el
sdist con `scikit_build_core` y exige CMake y MSVC; el fallo aparece veinte
minutos después disfrazado de error de compilador. Sin el segundo, `pip
install -r` muere con «No matching distribution found for pdbfixer==1.12.0».

Comprobado así, y reproducible:

```bash
python-embed/python.exe -m pip install --dry-run --no-deps \
  --only-binary=:all: -r backend/requirements-embed.lock.txt
```

## 4. Cómo se arranca

```bash
git clone <repo> && cd moldesign
python scripts/provision_python_embed.py --check     # dice qué falta
python scripts/provision_python_embed.py --fetch     # ~2,2 GB, una vez
```

Los binarios nativos (`tools/vina`, `tools/xtb`, `tools/llama` y
`tools/openbabel/bin`) siguen sin cubrirse por esta vía: sus orígenes están
declarados en `bootstrap_dev_tree.py` y hoy se traen a mano o del artefacto
cuando se publique. El runtime app-local de Visual C++ es la excepción: sus cinco
DLL x64, el manifiesto y los hashes sí están versionados en `tools/vc-runtime/`,
para que el resultado no dependa de una instalación accidental de Visual Studio.
**Sin los demás binarios el instalador no se construye**, y la puerta del §5 lo
dice con esas palabras.

## 5. La puerta que traduce el fallo

`frontend/scripts/check-runtime-arbol.mjs`, primera de las catorce de
`beforeBuildCommand`, antes de `check:csp`. Comprueba una sola cosa —que el
suelo sobre el que pisan las otras trece existe— y, si no, nombra las dos vías
del §2 en vez de dejar un error de ruta.

Corre con el **Python del sistema**, no con el embebido: preguntarle por su
propia existencia al intérprete que puede no estar devolvería el mismo mensaje
ilegible que sustituye.

## 6. La oferta de fuente GPL, ahora visible desde un clon

Open Babel se distribuye bajo GPL-2.0-only y la GPLv2 §3 obliga a acompañar el
binario del código correspondiente. Los dos `.tar.gz` existen, pero vivían en
`dist/`, que está en `.gitignore`: **la oferta entera existía sólo en la máquina
del mantenedor**, y un clon no podía ni leer qué se ofrecía.

La **declaración** —commits exactos, repositorios de origen y SHA-256 de los dos
tarballs y del binario distribuido— pasa a `tools/openbabel/SOURCE-OFFER.json`,
versionada. Los tarballs siguen fuera: son artefactos de publicación de 35 MB,
no fuente de este proyecto.

```bash
# en un clon: comprueba la declaración y DICE que no vio los tarballs
python scripts/verify_release_source_offer.py --check --permitir-artefactos-ausentes

# en la máquina que publica: sin la bandera, exige los archivos
python scripts/verify_release_source_offer.py --check
```

La bandera no imprime «verificado»: dice qué no comprobó. Es la misma regla que
`generate_sbom.py --permitir-runtime-ausente`, y existe porque un gate que
aprueba lo que no miró es peor que no tenerlo.

## 7. Lo que esto NO cierra

1. **La corrida completa SÍ se ejecutó, y encontró dos defectos.** El
   2026-09-06 se aprovisionó un árbol entero desde cero: 173/173 paquetes,
   2,1 GiB, y `--check` en verde. Los dos defectos vivían donde ninguna prueba
   unitaria los habría visto:

   - `tempfile.mkstemp` devuelve un descriptor **abierto** y en Windows un
     archivo abierto no se borra. Los 170 paquetes se instalaron bien y la
     corrida murió veinte minutos después, en el `finally`, con `WinError 32`
     — perdiendo los dos casos especiales y el recibo.
   - `pip freeze` **omite** pip, setuptools y wheel, y escribe
     `pdbfixer @ https://…` en vez de `pdbfixer==1.12.0` por venir de una URL.
     El informe anunciaba cuatro ausencias falsas sobre un árbol correcto.

   Los dos están corregidos y con prueba de regresión. Lo que sigue sin
   probarse es la corrida sobre una **máquina** limpia, no sólo un árbol
   limpio: aquí había caché de pip y red rápida.
2. **Los binarios nativos siguen fuera de esta vía** (§4).
3. **Nada de esto reemplaza publicar `runtime-base-v1.1.0.zip`**, que sigue
   siendo la vía rápida y determinista, ni cierra el doc 81.
4. **La revisión jurídica externa de la frontera con Open Babel sigue abierta**
   (doc 79 §10.1). Que la oferta de fuente sea ahora legible desde un clon
   mejora el cumplimiento verificable; no dictamina nada.
