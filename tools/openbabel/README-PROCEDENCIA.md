# Open Babel — programa independiente distribuido con MolDesign AI

Este directorio contiene **Open Babel 3.1.1**, un programa
independiente cuyo copyright pertenece a sus autores y colaboradores. Se
distribuye bajo **GNU General Public License, versión 2 (GPL-2.0-only)**, cuyo
texto íntegro está en `LICENSE-GPL-2.0.txt`.

Open Babel se entrega **SIN NINGUNA GARANTÍA**, ni siquiera la garantía
implícita de comerciabilidad o idoneidad para un propósito determinado; véanse
las secciones 11 y 12 de la GPLv2.

## Relación con MolDesign AI

MolDesign AI es una obra separada, bajo **PolyForm Noncommercial 1.0.0** (ver
`LICENSE` en la raíz del proyecto). **No enlaza con Open Babel ni importa sus
bindings de Python.** Lo invoca como herramienta de línea de órdenes
(`bin/obabel.exe`) mediante subproceso, pasando y recibiendo archivos
moleculares. Viajar en el mismo instalador es agregación en un medio de
distribución, no combinación en una sola obra.

> **Corregido el 2026-09-12.** Este párrafo declaraba que MolDesign AI estaba
> bajo AGPL-3.0-only. Era falso y el fichero viaja dentro del paquete: un lector
> podía concluir que tenía derechos AGPL sobre MolDesign. La licencia es y ha
> sido PolyForm Noncommercial 1.0.0. El error no afecta al análisis de frontera
> con Open Babel, que no depende de cuál sea la licencia de la obra separada.

## Procedencia exacta de estos bytes

| | |
|---|---|
| Paquete | `openbabel-wheel==3.1.1.23` |
| Wheel | `openbabel_wheel-3.1.1.23-cp311-cp311-win_amd64.whl` |
| SHA-256 del wheel | `f0568906e6959fc541518c8e4cea26973e58707bd2434fb7cddfc5f745c32df7` |
| Plataforma | CPython 3.11, Windows x86-64 |
| Repositorio del empaquetador | https://github.com/njzjz/openbabel-wheel |
| Commit del empaquetador | `c6b2731dbd0a559ee56b8084b6d9997df1beb16f` |
| Fuentes Open Babel incorporadas | https://github.com/njzjz/openbabel |
| Commit de las fuentes | `77993b9a3b96fb9bd86249098beb97ab0fcbafc6` |
| Basado en Open Babel oficial | 3.1.1 (https://github.com/openbabel/openbabel) |
| Licencia efectiva declarada | `GPL-2.0-only` |

El binario contesta `Open Babel 3.1.0` a `obabel -V`. Open Babel
3.1.1 fue una publicación de corrección de empaquetado que no actualizó la
cadena de versión interna; la discrepancia es de origen y está declarada, no es
un error de este paquete.

## Cómo obtener el código fuente correspondiente

La GPLv2 §3 obliga a acompañar el binario del código fuente correspondiente, o
de una oferta escrita válida para obtenerlo. Cada publicación de MolDesign
adjunta el archivo de fuentes de **esta versión exacta**; además puede
reconstruirse así:

```bash
# 1. Las fuentes que se compilaron, por commit exacto
git clone https://github.com/njzjz/openbabel openbabel-src
cd openbabel-src && git checkout 77993b9a3b96fb9bd86249098beb97ab0fcbafc6

# 2. Las recetas de compilación que produjeron este wheel
git clone https://github.com/njzjz/openbabel-wheel openbabel-wheel-src
cd openbabel-wheel-src && git checkout c6b2731dbd0a559ee56b8084b6d9997df1beb16f

# 3. El wheel publicado, cuyo SHA-256 debe ser el declarado arriba
pip download openbabel-wheel==3.1.1.23 \
    --no-deps --only-binary :all: \
    --python-version 3.11 --platform win_amd64
```

Un enlace a una web no basta por sí solo: la publicación debe ofrecer acceso al
código fuente correspondiente **de la versión exacta distribuida**. Ver
`frontend/public/legal/SOURCE_CODE_AND_RELINKING.md`.

## Reemplazo

No hay medida técnica que impida sustituir este programa. Otra compilación de
Open Babel con el mismo contrato de línea de órdenes funciona igual, siempre que
se actualice `openbabel-manifest.json` con sus hashes: MolDesign verifica el
hash antes de ejecutar y se abstiene si no coincide.

> Este documento describe la ingeniería y la procedencia. No es asesoría
> jurídica.
