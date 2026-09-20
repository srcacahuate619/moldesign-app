# Usar el servidor para validar esto

Plan de trabajo. Anotado el 2026-09-17 al cerrar los tres commits de `c8b5d59`,
`b2996b0` y `696c616`.

**Estado al 2026-09-19.** Ejecutados los **bloques 1 y 2** y la mitad de dominio
del **bloque 4**, los tres en la estación del mantenedor y ninguno en el
servidor. Siguen sin ejecutarse los bloques 3, 5, 6 y 7. Cada bloque dice abajo
en qué quedó.

Existe porque hay un servidor casero disponible que puede quedar corriendo 24 h
o más, y porque lo que queda abierto en [la revisión del ensamble](ENSEMBLE_REVIEW.md)
y en [la validación de MM-GBSA](MMGBSA_VALIDATION.md) ya no es código: es
medición. Cada bloque de aquí abajo dice qué produce y qué NO demuestra.

## El hallazgo que ordena la lista

El producto acopla con **`exhaustiveness=32`** (`services/pipeline/runner.py:696`,
`params.get("exhaustiveness", 32)`). La evidencia sellada en la que se apoya el
ensemble —`MF-33-B-RET-R2`— corrió con **`exhaustiveness=8`** (su `metrics.json`
lo declara, junto a `num_modes=9`, `seed=42`, caja de 25 Å y `cpu=1`).

No es un detalle de coste. La exhaustividad **es** el eje de presupuesto contra el
que el ensemble compite: a exh=32 un solo confórmero recibe cuatro veces más
búsqueda, así que la ventaja de cobertura medida a exh=8 puede ser menor —o no
existir— en el protocolo que la gente ejecuta. Sumado a que hasta el 2026-09-17 el
camino del producto acoplaba K veces la MISMA geometría (ENS-05), la conclusión
que hay que escribir sin adornos es:

> **No existe ninguna medida del ensemble conformacional sobre el pipeline actual.**
> Lo que hay es evidencia de otro protocolo, con otro presupuesto, producida por
> otro arnés.

Por eso el orden de abajo no empieza por el ensayo grande.

## Bloque 1 — Piloto técnico del arreglo (2-3 h)

Lo que se demostró el 2026-09-17 es que **Meeko recibe el SDF correcto** de cada
conformación. Falta demostrar que la piscina *contiene* diversidad.

- K=30 con Vina real sobre 10-20 ligandos fuera de cualquier holdout futuro.
- Medir RMSD pareado entre poses etiquetadas con `conformer_index` distinto, y
  cuántas conformaciones distintas sobreviven al top-9 entregado.
- Comprobar que `source_provenance.ligand_input.conformer_sha256` difiere por
  conformación en la corrida real, no sólo en las pruebas.
- Recuperar con `services/docking/pose_recovery.py` la pose de cada corrida y
  confirmar que las seis puertas pasan sobre artefactos reales de Vina y Meeko
  —no sólo sobre los SDF escritos a mano de las pruebas—. Con ligandos
  macrocíclicos incluidos, para ejercitar el descarte de pseudo-átomos de pegado.

**Produce:** un informe con RMSD intra-piscina y la fracción de conformaciones
representadas. **No demuestra** ninguna ventaja: es verificación de que el arreglo
hace lo que dice.

### HECHO el 2026-09-19 — `scripts/artifacts_science/ENS-PILOT-01/`

10 ligandos, K=30, exhaustividad **32** (la del producto), 300 conformaciones y
172 acoplamientos con Vina real. El arreglo hace lo que dice: **90/90 poses con
SHA que coincide con su generador**, 30 hashes distintos por ligando, mediana de
**9 conformaciones distintas** en el top-9. Control negativo limpio: cafeína,
sin rotores, colapsa a 0.026 Å.

Y encontró **dos defectos ajenos al ensemble** que el plan no anticipaba, porque
exigía incluir macrociclos:

1. `parse_vina_output_sdf` no leía la cabecera real de Meeko. **171 de 172
   acoplamientos** salieron por el respaldo de Open Babel; cero por Meeko.
2. Ese respaldo entrega los macrociclos con dos carbonos del anillo como
   pseudo-átomos y el ciclo abierto. G5 de `pose_recovery` los rechazó:
   **72/90** poses recuperables, con los 18 fallos concentrados en muscona y
   exaltólida.

Ambos viajaron en **1.0.0** y se corrigieron el mismo día para 1.0.1. Las seis
puertas se verificaron sobre artefactos reales de Vina y Meeko, que era el
requisito del bloque. Detalle en el README del artefacto.

## Bloque 2 — Determinismo de Vina con `vina_cpu=0` (30 min)

Quedó explícitamente sin medir y sin afirmar. `vina_cpu` vale 0 por defecto
(auto-detección de núcleos, `core/config.py:108`) y la búsqueda paralela de Vina
no garantiza reproducibilidad bit a bit.

- Misma entrada, misma semilla, 10 corridas: comparar bytes de PDBQT y afinidades.
- Repetir con `cpu=1` y con `cpu=N`.

**Produce:** un hecho, en cualquier dirección. Si los bytes cambian, la promesa de
«paquete reproducible» necesita una condición escrita, igual que la validez física
necesita su condición de reconstrucción de hidrógenos.

## Bloque 3 — ENS-PROD-01, los 248 complejos

El experimento que decide si el ensemble se queda en el producto. El dimensionado
ya está cerrado en [`ens_prod_01_potencia.py`](ens_prod_01_potencia.py): potencia
0.150 en R2, **248 complejos para 80%** y 324 para 90%, bajo la estructura de
discordancia observada.

Tres brazos —K=1, K=30, reinicios desde un confórmero con presupuesto igualado—
son ≈ 15.100 corridas de Vina. **Estimaciones a reemplazar por la medida del
piloto, no datos:**

| protocolo | coste estimado | en 16 hilos |
|---|---:|---:|
| exh=8 (como R2) | ~190 CPU-h | ~12 h |
| exh=32 (como el producto) | ~760 CPU-h | ~2 días |
| PoseBusters sobre ~136k poses | ~75 CPU-h | ~5 h |

Decisión pendiente y no trivial: **¿a qué exhaustividad se corre?** A exh=8 el
resultado es comparable con R2 y no describe el producto; a exh=32 describe el
producto y no es comparable con R2. Lo defendible es correr el primario a exh=32
—que es lo que el usuario ejecuta— y dejar exh=8 como estrato declarado para
poder contrastar con lo sellado. Eso duplica el presupuesto y hay que decidirlo
antes, no a mitad.

Requisito de procedimiento, no de comodidad: **una corrida prerregistrada no
comparte máquina**. La contención con pytest y generación de confórmeros ya mató
un dock de 970 en `MF-33-B-RET-R1`, tiró su G0 y dejó ilegibles bloques
científicos ya calculados. Máquina dedicada, nada encima, y comprobar que está en
reposo antes de lanzar.

Sigue abierto y **no lo resuelve el servidor**: la cohorte (pública,
independiente de MF-33 y de los ajustes previos, con solapamiento de diana/serie
documentado), el presupuesto y el umbral de relevancia práctica. El informe de
potencia trae el precio de cada umbral (5 pp cuestan 684 complejos; 20 pp, 40)
precisamente para que esa decisión se tome con la cifra delante.

**Advertencia que va en el manifiesto:** las cifras de potencia son **cotas
inferiores**, porque se dimensionaron con el efecto observado en la corrida que
motivó el ensayo. Si el efecto real es la mitad, 248 complejos no bastan. Es otra
razón para correr el bloque 1 antes de comprometer dos días de máquina.

## Bloque 4 — MM-GBSA puerta 1: la mitad de dominio (barato)

Se sabe que el desacuerdo del cloro es exactamente el respaldo de carbono de
Amber (`C_sp2_2`, radio 1.7 Å). Lo que no se sabe es **cuál de los dos conjuntos
es correcto**, y eso no se decide leyendo código.

Se puede adjudicar sin licencias nuevas y sin red:

- Calcular **SASA numérica exacta** (Shrake-Rupley con malla fina, o analítica)
  sobre ligandos halogenados con los mismos radios del prmtop.
- Comparar qué parametrización LCPO la aproxima mejor: la publicada de Weiser,
  Shenkin y Still, o el respaldo de carbono que usa Amber.
- Si gana la publicada, el candidato es **más** correcto que la referencia, y eso
  pasa a ser una afirmación con medida detrás en lugar de una inferencia a partir
  de un comentario del código de OpenMM.

Ampliar además de 8 ligandos diagnósticos a ~50 cubriendo F, Cl, Br, I, azufre,
estados de carga y tautómeros: son 2-3 CPU-h. **El cuello es curar el conjunto,
no calcular.** Pide **Linux nativo con AmberTools**, que es mejor sitio que la WSL
de la estación de trabajo.

**No cambia** el estado del protocolo por sí solo: `EXPERIMENTAL_NOT_ENABLED`
sigue hasta que alguien decida, y el guardián
`test_produccion_no_copia_el_respaldo_de_carbono_para_el_cloro` sigue impidiendo
que la paridad se consiga copiando el respaldo.

## Bloque 5 — Batería completa sobre clon limpio, cada noche

El uso con mejor relación valor/hora y el único permanente. Un `git clone` del
propio repositorio destapó en su día **diez fallos del backend y tres gates
rotos** que 2082 pruebas locales no veían. Hoy mismo, el conteo declarado en
`docs/api/test-counts.json` estaba en 2117 cuando había 2505.

- Clonar, armar el runtime, correr backend + frontend + los catorce gates de
  `beforeBuildCommand`.
- **En una máquina que no es la de build**, que es justo lo que le da valor.

**Produce:** la señal que la máquina del mantenedor no puede dar. Un gate que no
puede comprobar y aun así imprime «verificado» es peor que no tenerlo.

## Bloque 6 — MM-GBSA puerta 3 (depende de GPU)

Sistemas receptor-ligando completos, tres subsistemas, retención de
aguas/metales/cofactores y minimización. En CPU son 10-30 min por pose, así que
un piloto de 50 poses se va a ~25 h; con CUDA se vuelve cómodo. **Entra en el
plan sólo si el servidor tiene GPU**; si no, espera.

## Bloque 7 — Lo que cabe en los huecos

- **Stacking M4 aparte**, sobre actividad experimental con cortes por
  serie/diana/fecha: ¿se justifica Vina=0.25 / XGB=0.75, hoy declarado sin
  calibrar? Cómputo barato, trabajo de datos.
- **Re-auditar FEP-01/02/03** sobre los 203 complejos y reconstruir la cohorte
  congenérica desde PDBBind. Mayormente parseo y preparación.

## Lo que el servidor NO resuelve

No elige la cohorte. No fija el umbral de relevancia práctica. No toma la
decisión de dominio sobre halógenos. No consigue licencias. Y no convierte una
medida de otro protocolo en una medida del producto.

Regla de entrada: el servidor **produce evidencia con hashes y manifiestos; no
decide gates por su cuenta**. El sellado sigue siendo un acto explícito, con su
prueba técnica antes —nunca después— del prerregistro.

## Lo que falta saber para concretar el plan de 24 h

1. **Núcleos y RAM**, y si es **Linux nativo** (decide el bloque 4).
2. **¿GPU CUDA?** (decide si el bloque 6 entra o espera).
3. **Disco libre.** Una cohorte de 248 complejos con poses y PDBQT por
   conformación son decenas de GB de evidencia que no se borra a la ligera.
   Recordar que `tmp/` de este repositorio **no** es temporal: guarda evidencia
   de gates.
4. **¿Puede quedar dedicado** durante la corrida prerregistrada?

Con acceso SSH y un directorio de trabajo propio basta. Un artefacto por corrida
y por shard, **nunca reusando el directorio de salida**: hacerlo ya destruyó 102
resultados de `RS-03-PARAM-B`.
