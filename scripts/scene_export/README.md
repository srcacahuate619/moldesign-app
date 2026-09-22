# Paquete de escena — el contrato entre MolDesign y Blender

Este directorio produce **paquetes de escena**: geometría más un contrato que
dice qué puede afirmar un render de ese receptor y qué no.

No contiene nada de Blender, y no debe contenerlo. La frontera está aquí a
propósito — ver [§ Por qué dos proyectos](#por-qué-dos-proyectos).

```bash
# los doce de prueba (uno por familia estructural, las grandes primero)
PYTHONPATH=backend python scripts/scene_export/build_scene_package.py \
    --muestra-por-familia 1 --out dist/scenes

# uno concreto
PYTHONPATH=backend python scripts/scene_export/build_scene_package.py \
    --pdb-id 2NNJ --out dist/scenes

# la tanda completa (380)
PYTHONPATH=backend python scripts/scene_export/build_scene_package.py \
    --todos --out dist/scenes
```

Salida por receptor:

```
dist/scenes/<PDB_ID>/
    scene.json          el contrato
    geometry/
        deposited.pdb   unidad biológica del archivo depositado
        prepared.pdb    el receptor que el acoplamiento ejecuta de verdad
        site_ligand.pdb ligando cocristalizado, si lo hay
    MANIFEST.sha256
```

---

## Las dos geometrías no son intercambiables

Esto es lo primero que hay que entender, porque es donde un render miente sin
que nadie se dé cuenta.

| | `deposited.pdb` | `prepared.pdb` |
|---|---|---|
| qué es | la unidad biológica del PDB, con BIOMT aplicado | lo que Vina ve |
| aguas | todas las depositadas | **ninguna** |
| metales | los que haya | **ninguno** |
| cofactores (HEM, GDP…) | los que haya | **ninguno** |
| cadenas | todas | sólo las del sitio |
| huecos de cadena | los del depósito | los mismos, declarados |

La segunda columna es consecuencia de que `cofactors_whitelist` esté **vacío en
las 380 entradas** de `curated_targets.json`: la puerta que conserva metales y
cofactores depende de esa lista, así que en la práctica no conserva nada.

Medido sobre **los 380, cero abstenciones**:

| lo que desaparece en `prepared.pdb` | receptores |
|---|---|
| aguas | **332 / 380 (87%)** |
| metales | **115 / 380 (30%)** |
| cofactores (HEM, GDP, NAD…) | **35 / 380 (9%)** |

Tres casos que enseñan el problema:

- **1BN1** (anhidrasa carbónica II) — el **zinc catalítico** no está en el
  receptor acoplado. Alerta `ESPECIE_DEL_SITIO_ELIMINADA: ['ZN']`.
- **2NNJ** (citocromo P450) — el **grupo HEM completo**, 43 átomos, tampoco.
  Un P450 sin su hemo no es un P450, y es lo más vistoso de la estructura.
- **3QXX** (ligasa) — se van `MG` y el cofactor `GDP`.

Si el vídeo enseña `deposited.pdb` y el rótulo dice *«el receptor que MolDesign
evalúa»*, el vídeo es falso. Enseña la que quieras, pero llámala por su nombre.

---

## `scene.json`, bloque a bloque

### `encuadre` — a dónde apunta la cámara

```json
"encuadre": {
  "objetivo": [60.018, -7.771, 34.741],
  "caja": [30.0, 30.0, 30.0],
  "fuente": "curated_targets.json: grid_center_* / grid_size_*"
}
```

`objetivo` es el **centro de la caja de acoplamiento adjudicada**, no el
centroide de la proteína. Los 380 lo tienen. Es el dato que hace automatizable
todo esto: el problema difícil de renderizar N estructuras es decidir a dónde
mirar, y aquí ya está resuelto y auditado.

### `resaltar` — qué residuos destacar

`hotspots` viene ya parseado a `{cadena, resname, numero, importancia}` y
ordenado. `importancia` **no es energía de unión ni contribución medida**: es un
orden de residuos del bolsillo. No la conviertas en una barra ni en un número
con unidades.

### `declarado` — lo que se midió

- `aguas` — censo de `services/chemistry/censo_de_aguas.py`: cuántas había en la
  estructura, cuántas en la caja, cuántas bien coordinadas, y cada una con su
  enterramiento. `candidatas_a_conservar` **no es una política**; es el corte que
  la medición deja en pie, pendiente de contrastar. No la dibujes como decidida.
- `huecos_de_cadena` — roturas del esqueleto en `prepared.pdb`, Cα-Cα > 4.5 Å,
  con los residuos ausentes de cada una.
- `politica_de_preparacion` — qué se eliminó, por nombre.
- `diff_fuente_preparado` — el reporte completo de
  `services/chemistry/preparation_report.py`, con sus alertas y hashes.

### `no_dibujar` — prohibiciones duras

Cada entrada trae `id`, `razon`, `fuente` (el módulo que la respalda) y
`permitido_en_su_lugar`. No hace falta creerle nada a este README: la `fuente`
se puede auditar.

Tres salen siempre:

| id | por qué |
|---|---|
| `angulo_puente_hidrogeno` | El receptor no llega protonado al PLIF, así que `_estimate_hbond_angle` devuelve `None` **a propósito** (`backend/services/interactions/analyzer.py:278` — el comentario dice que la estimación anterior «no era mala: era una tautología»). Puedes dibujar la línea punteada del contacto y su distancia. **No** el hidrógeno ni la geometría angular. |
| `trayectoria_de_union` | MolDesign no ejecuta MD. La unión real ocurre en µs–ms: ninguna trayectoria renderizable contiene ese evento. Un ligando que entra volando al bolsillo es una interpolación. |
| `movimiento_del_receptor_como_resultado` | Vina acopla con receptor rígido. Toda deformación animada es invención del render. Mueve la cámara, o usa modos normales (ProDy/ANM) rotulados como aproximación armónica. |

Las demás dependen del receptor:

| id | cuándo aparece | medido sobre los 380 |
|---|---|---|
| `aguas_en_prepared` | había aguas y se retiraron todas | 332 (87%) |
| `cinta_continua_sobre_hueco` | el esqueleto está roto | **195 (51%)** |
| `metales_en_prepared` | se eliminó algún metal | 115 (30%) |
| `cofactores_en_prepared` | se eliminó algún cofactor | 35 (9%) |

`cinta_continua_sobre_hueco` es la que más te va a afectar: **Molecular Nodes
dibuja el estilo cartoon continuo por defecto**, así que sin hacer nada la cinta
cruza el hueco y la escena inventa conectividad. Pasa en **más de la mitad del
catálogo**: 195 receptores, 503 roturas, 5.836 residuos ausentes en total. 2B2A
tiene 6 roturas y la mayor salta **19.66 Å entre los residuos 77 y 87**, con 9
residuos ausentes. Corta la cinta o marca el hueco con línea discontinua; las
posiciones exactas están en `declarado.huecos_de_cadena`.

Que el 51% tenga hueco concuerda con el 42% que midió `FEP-02` sobre 203
complejos por un camino distinto.

### Dimensionado del rig

| | mín | p50 | p90 | máx |
|---|---:|---:|---:|---:|
| átomos en `prepared.pdb` | 312 | 2.834 | 5.400 | 12.932 |
| átomos en `deposited.pdb` | 841 | 4.686 | 15.292 | **52.604** |

`prepared` es uniformemente manejable. `deposited` tiene una cola larga —el peor
caso es 6× el p90—, así que si el plano usa superficie sobre `deposited`, el
presupuesto de malla hay que dimensionarlo por el máximo, no por la mediana.

Otros datos para planificar: **271/380** tienen ligando cocristalizado,
**110/380** tienen el sitio repartido entre varias cadenas (no puedes
desvanecer «las otras cadenas» en esos), y **37/380** generan cadenas nuevas por
simetría BIOMT.

### `declarar_si_se_dibuja` — permitido con su condición

Lo que puede aparecer siempre que el rótulo lo acompañe:

- **`hidrogenos`** — las estructuras no traen H. Cualquiera en pantalla está
  reconstruido, y la validez física sólo es comparable bajo el protocolo de
  `MF-33-H-COR`.
- **`superficie_molecular`** — el estilo de superficie de Molecular Nodes es una
  isosuperficie gaussiana, **no** una SES de Connolly con sonda de 1.4 Å. Para
  un plano que argumente el encaje, calcula la SES fuera (ChimeraX/MSMS) o no la
  llames «superficie molecular».
- **`ligando_del_sitio`** — `site_ligand.pdb` sale de registros HETATM y **no
  lleva órdenes de enlace**: los aromáticos se infieren por distancia y salen
  mal. Para química correcta, trae el SDF ideal del Chemical Component
  Dictionary de ese código HET.
- **`unidad_biologica`** — las cadenas generadas por BIOMT son copias exactas por
  simetría, no conformaciones independientes.
- **`cadena_proxima_al_sitio_ausente`** — hay cadenas que tocan el sitio en
  `deposited` y no están en `prepared`.

### `procedencia`

`git_sha`, `arbol_sucio`, sha256 de `curated_targets.json` y de la estructura
fuente, versión de Python. Si `arbol_sucio` es `true`, ese paquete no es
reproducible desde el repositorio.

Quema el `pdb_id` y el `git_sha` corto en una esquina del frame. Un render con
procedencia es coherente con todo lo demás que hace el producto.

---

## Por qué dos proyectos

La separación no es organizativa, está **forzada**:

1. **Blender trae su propio Python.** Importar el backend de MolDesign dentro de
   Blender arrastraría rdkit, prolif, torch y el resto, en un intérprete que no
   es el que se distribuye (3.11.9 embebido). Es inviable y además rompería la
   equivalencia entre lo que se verifica y lo que se entrega.
2. **La frontera GPL con Open Babel** (`docs/79_ADR_FRONTERA_OPEN_BABEL.md`) no
   debe cruzar hacia un tercer entorno. Nueve guardas la vigilan; un import
   desde un addon de Blender no estaría cubierto por ninguna.
3. **El contrato es el entregable.** Es la misma tesis que `FEP-05`/`FEP-06`: un
   tercero debe poder reconstruir el paquete con sus archivos, hashes y
   decisiones, sin conocer la sesión. Si la escena se pudiera armar leyendo la
   base de datos en vivo, no habría nada transferible.

El exportador es ligero: los cuatro módulos que usa importan con sólo
`PYTHONPATH=backend`, sin FastAPI y sin torch.

**Regla de oro:** el proyecto de Blender lee `scene.json` y los `.pdb`, y nada
más. No importa nada de `backend/`, no abre la base de datos, no llama a la API.
Si el render necesita un dato que el contrato no trae, el arreglo es añadirlo
aquí — no ir a buscarlo por su cuenta.

---

## Lo que este exportador todavía no hace

- **No trae poses de Vina.** Sólo receptor y ligando cocristalizado. Para
  escenas con poses hay que pasar por `services/docking/pose_recovery.py`, que
  tiene seis puertas y puede abstenerse; no vale leer el SDF de la corrida.
- **No trae el PLIF.** `services/interactions/analyzer.py` da los contactos, pero
  necesita una pose, así que va con lo anterior.
- **No trae el SDF ideal del CCD** para el ligando del sitio.
- **No calcula SES.** Declarado, no resuelto.
- **`prepared.pdb` no lleva el recorte al sitio** que el camino multicadena real
  aplica (`_recortar_al_sitio`). La química conservada es la misma; la extensión
  no. Está declarado en `geometria.prepared.recorte_al_sitio_aplicado`.
