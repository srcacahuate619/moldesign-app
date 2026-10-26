# Fase 1b — correcciones de los registros C1 de la Fase B

**Estado:** abierto. **Plan y orden:** `docs/100_CORRECCIONES_AUDITORIA_CIENCIA_20261015.md`,
sección «Fase 1b» (129 registros, por severidad y por ID). Este documento lleva el detalle de
cada cierre, con su verificación y su commit, en el formato de `docs/85`.

**Rama:** `claude/fase-1b`, desde `9c669db3`. Se trabaja aparte de la sesión que lleva
ABS-TR-01 y CAL-D-01 (`claude/abs-tr-01-validez`), que también escribe `docs/100`, `AGENTS.md`
y el registro científico: el detalle va aquí para no pisar su texto.

## Reglas de esta fase

1. **Verificar el hallazgo antes de aceptarlo**, en el código y en los artefactos.
2. **Los artefactos sellados no se tocan** (restricción 5 de `AGENTS.md`). Un productor
   sellado tampoco: la regla nueva vive aparte, como en SCI-B-016.
3. **Prueba que falla sin el arreglo**, o un control negativo que demuestre que la prueba ve.
4. **Si el hallazgo resulta no sostenerse en parte, se dice**, con la medida que lo muestra.
5. La parte C0 de un registro (texto) va a la sección «Correcciones» del paper; la C1
   (código), aquí.

---

## SCI-B-096 — el sello de MF-16-R1 no acreditaba su productor

**Veredicto del ledger:** `FALSA`, S1. **Verificado:** sí, y **en parte no se sostiene**.

### Diagnóstico

Lo que se sostiene: el manifiesto de MF-16-R1 sella `scripts/run_mf16_embudo_ff.py`
(SHA-256 `78b031eb…`, igual al fichero actual). Ese script es el runner de punto único de
MF-16: llama a `getPotentialEnergy` sin minimizar, no lee la salida de MF-10, escribe en
`MF-16` y emite `rho_ff`, no los campos de R1 (`rho_ff_relajado`, `rho_ff_punto_unico`). El
sello no acreditaba quién produjo esas cifras.

Lo que no se sostiene: que las cifras de R1 no sean energías minimizadas. Recalculadas desde
`MF-10/per_complex.jsonl`, que construye y minimiza cada pose por separado
(`run_mf10_relax_insitu.py:206-226`), **coinciden las 38 filas y el resumen sellado, sin una
sola diferencia**:

| Campo de R1 | Definición que lo reproduce (38 de 38) |
|---|---|
| `rho_ff_relajado` | Spearman(`rmsd_despues`, `energia_despues`) |
| `rho_ff_punto_unico` | Spearman(`rmsd_antes`, `energia_antes`) |
| `rho_vina` | Spearman(`rmsd_antes`, `score`) |

Con el RMSD de antes, la ρ relajada coincide sólo en 3 de 38: R1 compara objetos distintos,
como ya declaraba.

### Decisión

`scripts/analisis_mf16_r1_desde_mf10.py` es el productor trazable de R1: lee MF-10, registra
el SHA-256 de lo que leyó y compara con lo sellado (`--comprobar`, sale con 1 si algo
difiere). El sello de R1 no se reescribe. El paper lleva su corrección fechada.

### Verificación

- `scripts/tests/test_mf16_r1_desde_mf10.py`, 4 pruebas: Spearman con empates igual que
  `scipy.stats.spearmanr`; las 38 filas y el resumen; el RMSD de antes no reproduce la ρ
  relajada; y **control negativo**: cambiar una energía de 10gs en una copia de MF-10 hace
  que la comparación marque 10gs y el resumen.
- Fuente leída: `MF-10/per_complex.jsonl`, SHA-256 `56b663b0dcd82fb1…5f19`.

## SCI-B-097 — el runner de MF-16 reutiliza los hidrógenos de la primera pose

**Veredicto del ledger:** `FALSA`, S1. **Verificado:** sí en el código; **su consecuencia para
R1, no**.

### Diagnóstico

`run_mf16_embudo_ff.py:107-127` construye el sistema una vez con la primera pose y, para cada
pose siguiente, sólo mueve los átomos pesados del ligando (`idx_lig`): los hidrógenos se quedan
donde estaban en la primera. La energía de cada pose es la de una geometría híbrida.

Pero ninguna cifra publicada sale de ese bucle. R1 se reproduce entero desde MF-10 (arriba), y
MF-10 construye el sistema pose a pose (`run_mf10_relax_insitu.py:214`), así que sus
hidrógenos corresponden a cada pose. Las «36 poses por encima de 10⁴ kcal/mol» del paper
también salen de MF-10 (`energia_antes`, 36 contadas aquí). El defecto sí afectaba a la corrida
original de MF-16, que no está sellada y cuya conclusión R1 ya invalidaba.

### Decisión

El runner es un productor sellado y no se toca. Deja de ser el productor de referencia de R1
(SCI-B-096), así que ninguna cifra viva depende de él. Corrección en el paper de MF-16-R1.

**Fuera del ledger, sin medir:** `run_mf18_embudo_gb.py:166-192` usa el mismo patrón (sistema
construido con la primera pose y sólo los pesados movidos), pero minimiza antes de puntuar, lo
que corrige en parte la geometría de los hidrógenos. Queda anotado para revisar con MF-18.

### Verificación

La misma prueba que SCI-B-096: si alguna cifra de R1 dependiera del runner, la reconstrucción
desde MF-10 no daría 38 de 38.

## SCI-B-076 — el GO de MF-12 se decidía con el intervalo de la exactitud

**Veredicto del ledger:** `FALSA`, S1. **Verificado:** sí. **El GO se sostiene** con el
estimando correcto.

### Diagnóstico

El prerregistro (`MF-12-PRE/PREREGISTRO.md`, §3 y §5) fija como métrica primaria la precisión
balanceada del nivel L y pide para G2 que su CI95 bootstrap excluya el cero frente al baseline
mayoritario. `run_mf12_triage.py:179-181` calcula ese punto, pero pasa al bootstrap la
diferencia de **aciertos** por complejo: el `ci95_bca` sellado, [0,0805; 0,3218], es el de una
diferencia de exactitud (+0,2184). El paper lo presenta como si fuera el de la métrica primaria.

### Decisión

El ledger daba el GO por no verificado hasta tener el intervalo del estimando prerregistrado.
Se pudo calcular sin cómputo nuevo: el `per_complex.jsonl` sellado trae los rasgos y el
desenlace de los 203 complejos, y reajustar el mismo modelo sobre train **reproduce todo lo
publicado** (coeficientes de L y L+S, precisiones balanceadas, exactitudes y el intervalo de
exactitud, al cuarto decimal). Con esas 87 predicciones y el mismo bootstrap (BCa, 10 000
réplicas, semilla 42), con la diferencia de precisión balanceada como estadístico:

| Nivel | Diferencia de precisión balanceada | IC 95 % BCa | Intervalo publicado (exactitud) |
|---|---:|---|---|
| L | **+0,1536** | **[0,0493; 0,2446]** | [0,0805; 0,3218] |
| L+S | +0,1691 | [0,0643; 0,2608] | [0,0920; 0,3563] |

G2 se cumple con el estimando correcto: el GO de MF-12 se mantiene, con un efecto menor que el
publicado. Val+test tiene 51 positivos y 36 negativos, así que una réplica sin una de las dos
clases (métrica indefinida) es despreciable. El sello no se toca; el paper lleva la corrección.

La frase del paper «el efecto observado supera el MDE» queda sin citar hasta cerrar
SCI-B-077 (el MDE usa n = 203 y la evaluación pareada tiene 87).

### Verificación

- `scripts/analisis_mf12_ci_balanceada.py` sale con 1 si no reproduce lo sellado.
- `scripts/tests/test_mf12_ci_balanceada.py`, 3 pruebas: la métrica y su indefinición; la
  reproducción y el intervalo prerregistrado, distinto del publicado; y **control negativo**:
  cambiar un solo desenlace de train en una copia rompe la reproducción.

## SCI-B-088, SCI-B-089 y SCI-B-092 — MF-15 y MF-15-EXT, lo que se puede leer por radio

**Veredictos del ledger:** `SOBREAFIRMADA`, S1, los tres. **Verificados:** sí.

### Diagnóstico

Las dos medidas resumen la ρ (RMSD frente a score) por radio con la mediana de los complejos
que tienen al menos 8 poses en ese radio; los demás dan ρ nula y salen del resumen. Medido
sobre las salidas selladas (`MF-15/per_complex_train.jsonl` y `MF-15-EXT/per_complex.jsonl`),
en el estrato difícil (33 complejos):

| Radio | MF-15 medibles | MF-15-EXT medibles (mediana sin corregir simetría) |
|---|---:|---:|
| ≤ 2 Å | 0 | 0 |
| ≤ 3 Å | 2 | 2 |
| ≤ 4 Å | 10 | 11 (0,279) |
| ≤ 6 Å | 25 | 27 (0,140) |
| ≤ 8 Å | 31 | 32 |
| ≤ 12 Å | 33 | 32 |

Sólo 2 complejos son medibles en todos los radios con medida. Por eso «débil a todos los
radios» (MF-15, SCI-B-088) y «más poses resuelven el embudo» (MF-15-EXT, SCI-B-092) no se
sostienen: a 2 Å no hay medida, y la serie de medianas compara grupos distintos. SCI-B-089 es
de lectura: una correlación sobre poses fijas no mide si una búsqueda puede seguir el score,
así que no descarta familias de métodos.

### Decisión

`scripts/analisis_mf15_cobertura_por_radio.py` publica la cobertura por estrato y radio desde
lo sellado, sin recalcular ninguna ρ. Los dos papers llevan su corrección fechada. Lo que se
sostiene: la ρ global por estrato (0,186 frente a 0,507) y que no era un artefacto del
muestreo ni de la simetría.

### Verificación

`scripts/tests/test_mf15_cobertura_por_radio.py`, 3 pruebas: la cobertura del estrato
difícil en las dos medidas, con las dos cifras de la tabla del paper; que el estrato de
control sí tiene radios cortos (8 complejos a 2 Å); y **control negativo**: una ρ plantada a
2 Å en una copia aparece como medible.

## SCI-B-083 — el radio nominal de MF-14 no es un RMSD de partida

**Veredicto del ledger:** `FALSA`, S1. **Verificado:** sí; la lectura de rugosidad queda
**reducida, no anulada**.

### Diagnóstico

`run_mf14_radio_captura.py:_perturbar` aplica una rotación aleatoria de hasta 30° alrededor
del centroide y una traslación de norma r, y el resumen agrupa por r. Cada réplica guarda su
`rmsd_inicial`, que no es r: con r = 0,5 Å la mediana es 0,935 Å en el estrato difícil (máximo
2,65 Å). El 22,2 % que «no regresa desde 0,5 Å» no parte a media angstrom del mínimo.

### Decisión

`scripts/analisis_mf14_por_rmsd_inicial.py` reagrupa las 1440 réplicas selladas por su RMSD de
partida real, sin acoplar nada:

| RMSD de partida | Difícil: vuelven | Complejos (con algún fallo) | Control: vuelven |
|---|---:|---:|---:|
| < 0,75 Å | 60 de 74 (81 %) | 30 (5) | 55 de 58 (95 %) |
| 0,75–1,25 Å | 114 de 141 (81 %) | | 71 de 74 (96 %) |
| 1,25–2 Å | 106 de 141 (75 %) | | 39 de 41 (95 %) |
| 2–3 Å | 118 de 233 (51 %) | | 70 de 97 (72 %) |

Lo que queda: desde muy cerca, el estrato difícil pierde más que el control, pero los 14
fallos por debajo de 0,75 Å salen de 5 complejos de 30. Es una propiedad de esos complejos, no
una rugosidad general de la cuenca, y el experimento no localiza barreras. El paper lleva la
corrección; el sello no se toca. MF-14 ya era un registro retroactivo sin prerregistro, y sus
lecturas se citan como post hoc.

### Verificación

`scripts/tests/test_mf14_por_rmsd_inicial.py`, 4 pruebas: el RMSD de partida en r = 0,5 Å; la
concentración del fallo cercano en 5 complejos y el contraste con el control; que las bandas
cubren todas las réplicas; y **control negativo**: fijar a 0,5 Å el RMSD de partida en una
copia cambia la mediana.

## SCI-B-022 — REC-07 medía el contacto con una cisteína que no estaba (REC-07-R1, NO_GO)

**Veredicto del ledger:** `FALSA`, S1. **Verificado:** sí, y **más grave** de lo que decía el
ledger. Repetido con cómputo autorizado por el propietario (10 hilos).

### Diagnóstico

El ledger decía que el SG de la Cys25 no estaba en el receptor acoplado. Sobre los ficheros de
trabajo originales de REC-07, con sus SHA-256 sellados (`5TUN_receptor.pdbqt` `eceefe6d…`), no
está **ningún átomo** de la Cys25. `filtrar_pdb` de `run_rec07_grid_5tun.py` elige por residuo
la variante mayoritaria contando los átomos sin altloc: en la Cys25 de 5TUN, N, C y O no tienen
altloc y CA, CB y SG vienen en A y B, así que gana el vacío (3 contra 3). Quedan N, C y O, y
Meeko (`-a`) descarta el residuo. Las distancias de 0,4–1,2 Å eran el ligando en el hueco de la
cisteína. `backend/services/docking/preparer.py` no tiene este defecto (átomos comunes siempre;
variante por ocupación entre las no vacías): es del experimento, no del producto.

### Decisión

Experimento nuevo, `REC-07-R1`, prerregistrado y versionado antes de acoplar (`b8e278a0`):

- `scripts/run_rec07r1_grid_5tun.py` importa del runner sellado toda la configuración congelada
  y cambia sólo la regla de altloc (la de `preparer.py`) y añade G0, que aborta si la tríada no
  está en el receptor acoplado;
- mismo ligando que REC-07 (`e82cbe4e…`), mismo Vina (`e0c4b271…`), 18 corridas con `--cpu 1`
  en 10 hilos, 778 s de pared.

| Caja | Contacto top-1 | Distancia top-1 a Cys25 SG | Score top-1 mediano |
|---|---:|---|---:|
| `G_DB` (catálogo) | 4 de 5 | 2,46–5,89 Å | −2,64 |
| `G_MP` | 0 de 5 | 12,91–13,06 Å | −5,30 |
| `G_ADAPT` (recomendada) | 0 de 5 | 12,95–13,06 Å | −5,30 |

G0, G1, G2, G3, G6 y G7 pasan; **G4 y G5 fallan → NO_GO**, por la regla prerregistrada. La
recomendación de REC-07 queda refutada. El catálogo no cambia (REC-07 no lo había cambiado).
Sellado: 2 entradas, 1 binario, 6 activos. Paper `docs/papers/REC-07-R1.md`; el de REC-07 lleva
la corrección.

### Verificación

`scripts/tests/test_rec07r1_receptor.py`, 4 pruebas sin acoplar: el filtro sellado deja la
Cys25 con N, C y O; el coherente la conserva entera en altloc A con el SG en sus coordenadas;
ningún átomo sin altloc se pierde; y el aborto rechaza un receptor sin SG o con el NE2 movido
0,5 Å. G6 repitió la semilla 42 en las tres cajas con resultado idéntico.

## SCI-B-045 — los sellos nuevos exigen entradas, salidas y versiones

**Veredicto del ledger:** `NO_VERIFICABLE`, S1. **Verificado:** sí, en el manifiesto de FEP-04
(`dependencies.packages` vacío, sin `dataset_hashes`) y en la herramienta: `seal` acepta un sello
sin ninguna entrada (sólo avisa), `finish` no registra salidas e `init` deja `packages: []`.

### Decisión

`scripts/experiment_manifest.py` y `scripts/artifacts_science/manifest.schema.json` **no se
tocan**: están sellados como activos en 27 experimentos, y el esquema (`additionalProperties:
false`) no admite campos nuevos. La regla vive aparte, como la de SCI-B-016:

- `scripts/sellar_experimento.py sellar` exige `--entradas` (o `--sin-entradas` con un motivo
  declarado), llama al `seal` de siempre con esas rutas como `--dataset` y escribe
  `<experimento>/procedencia.json` con los hashes de entrada, el intérprete y la versión de
  cada paquete instalado;
- `cerrar` exige un `metrics.json` no vacío y `per_complex.jsonl`, registra el SHA-256 de las
  salidas y llama al `finish` de siempre;
- `comprobar` verifica entradas y salidas contra esos hashes.

**Fail-closed para lo nuevo, nada retroactivo:** `scripts/tests/test_procedencia_obligatoria.py`
falla si un experimento **sellado y creado desde el 2026-10-23** no tiene procedencia completa.
Los 173 sellos existentes no se miran ni se tocan. FEP-04 lleva su corrección en el paper
(se reproducen los agregados desde `per_complex`, no las filas desde las fuentes crudas). El
sello de FEP-04 no se rehace.

Al integrar: la sesión de ABS-TR-01 sella con `experiment_manifest.py`. Sus experimentos son del
2026-10-22, antes del corte; cualquier experimento nuevo debe usar `sellar_experimento.py`.

### Verificación

7 pruebas sobre un `ARTIFACTS_BASE` temporal: sellar sin entradas falla y no sella; con entradas
registra hashes y paquetes; el motivo declarado sustituye a las entradas; cerrar con
`metrics.json` vacío falla y con salidas las registra; `comprobar` ve una salida cambiada; y la
guarda ve un sello nuevo sin procedencia e ignora uno anterior al corte. `git diff` sobre
`experiment_manifest.py` y el esquema: vacío.

---

## Lote S2 de esta sesión (56 registros, IDs < 105)

**Fecha:** 2026-10-22. Los 63 registros con ID ≥ 105 los cierra Sol en un encargo aparte
(`D:\moldesign-audits\FASE_1B_lote_sol\`), que se calificará antes de integrar.

Cada registro se verificó contra el código y los artefactos sellados. Los que piden una cifra
nueva tienen un analizador que lee sólo salidas selladas y una prueba con control negativo;
el texto va a la sección «Correcciones» de cada paper. Ningún artefacto sellado cambia.

**Lo que la verificación cambió del ledger:**

- SCI-B-008 era peor de lo que decía: con componentes conexos, 11 dianas con ≥ 10 ligandos
  (no 28) y 4 con ≥ 20 (no 12).
- SCI-B-055: el paper de FND-03 decía que ningún complejo cambia de veredicto; en el control
  cambia 1 de 15.
- SCI-B-094 se sostiene como límite, pero no recorta nada: el máximo es 144 automorfismos.
- SCI-B-101 se sostiene sólo en parte: el r50 que leyó MF-17 coincide 48 de 48 con el sellado.
- SCI-B-077: el MDE con n = 87 es 0.203; el estimando primario de MF-12 (+0.154) queda debajo.

| ID | Verificado | Arreglo | Dónde |
|---|---|---|---|
| SCI-B-002 | sí | MDE con la varianza observada: 15.6 / 16.9 pp, no 22.3 | `analisis_fnd04_potencia_dominio.py`; FND-04, RS-14 |
| SCI-B-003 | sí | acotado a índices únicos que cubren los pesados | FEP-01 |
| SCI-B-008 | sí | por componente conexo: 11 y 4 dianas, no 28 y 12 | `analisis_fep03pdbbind_componentes.py`; FEP-03-PDBBIND |
| SCI-B-018 | sí | MF-19 y MF-08: MDE 0.132 > d = 0.091, fuera del dominio; «no alcanzable» | `analisis_fnd04_potencia_dominio.py`; FND-04 |
| SCI-B-023 | sí | emparejamiento por proximidad: no es cota superior garantizada | REC-08-EXT |
| SCI-B-025 | sí | el «BCa» es percentil; BCa real [−0.159, 0.054] y [−0.221, 0.018], gate igual | `analisis_rs14_bca.py`; RS-14, RS-14-R1 |
| SCI-B-026 | sí | el nulo usa otra estadística; p empírico no calibrado, lectura diagnóstica | RS-14 |
| SCI-B-038 | sí | 673 Kekulize + 2 de valencia + 9 carpetas que no son complejos | FEP-01-EXT |
| SCI-B-039 | sí | 4 sellos con experiment_id heredado, declarados y vigilados | `identidad_de_metricas.json` + prueba; FEP-01-EXT |
| SCI-B-040 | sí | «documentado» = dos criterios de cribado, no readiness | FEP-02 |
| SCI-B-041 | sí | 1460/3684 vs 83/203 como coincidencia descriptiva, sin GO de equivalencia | FEP-02 |
| SCI-B-042 | sí | 1438 SIN_PDB no son SIN_HUECOS: 2210 de 3887 evaluables (56.9 %) | `analisis_fep02ext_pdbbind_cobertura.py`; FEP-02-EXT |
| SCI-B-049 | sí | 400 = prioridad del clasificador; 59 también tautómero; no «se recuperan» | FEP-07 |
| SCI-B-050 | sí | diferencia puntual, sin equivalencia ni emparejamiento | FEP-08-CONTROL-POSITIVO |
| SCI-B-051 | sí | control positivo del filtro, no del auditor completo | FEP-08-CONTROL-POSITIVO |
| SCI-B-052 | sí | FND-01-SMOKE es un smoke de infraestructura: su GO no registra comando ni exit code y no cuenta como medición | aquí |
| SCI-B-053 | sí | `validate` falla (hash vivo de `experiment_manifest.py`); la copia sellada está en `sellado_original/` y `validar_sellos` la usa | aquí |
| SCI-B-055 | sí, y más: 1 de 15 del control cambia de veredicto | estabilidad del oráculo best-of-9, no del top-1 | FND-03 |
| SCI-B-057 | sí | el guard de la denylist es opt-in | FND-05 |
| SCI-B-058 | sí | `--strict-unknown` opt-in: la garantía no es automática | FND-06 |
| SCI-B-060 | sí | se cargan metadatos de 113 registros sólo de test; no hay fuga de etiquetas | MF-01-UNION |
| SCI-B-061 | sí | 61.5 % y 61.0 % son puntos cercanos; no prueban que el selector no contribuya | aquí (MF-02-PRE no tiene paper) |
| SCI-B-062 | sí | «eje agotado» → meseta en train, rendimientos decrecientes en PDBBind | MF-02A-EXT (el doc. 49 está sellado en FND-06: no se edita) |
| SCI-B-063 | sí | porcentajes condicionados a los 4636 embebidos; 16 sin enumerar | MF-02A-EXT |
| SCI-B-065 | sí | R1 mide el oráculo de todas las poses; el endpoint top-K entregado queda sin medir | aquí |
| SCI-B-066 | sí | MF-02C-PRE cita 93.1 % (corregido a 79.3 %): G3 ≥ 90 % no es «no degradación»; no ejecutar sin enmendar | aquí |
| SCI-B-067 | sí | el runner calcula RMSD contra cristal por caso para reporte; no ajusta ni decide gates con él | aquí |
| SCI-B-068 | sí | G5 preregistrado y no implementado | MF-08 |
| SCI-B-069 | sí | 3 de 33 de COLOCACION son fallos de puntuación | MF-09 |
| SCI-B-070 | sí | «verificado» = consistencia de agregados | MF-09 |
| SCI-B-071 | sí | el sello de MF-09-SYM sólo fija el analizador | MF-09 |
| SCI-B-072 | sí | contrato detallado de R1 no capturado antes | MF-11 |
| SCI-B-074 | sí | umbral elegido y evaluado en la misma partición | MF-11 |
| SCI-B-075 | sí | sello sin métricas ni entradas | MF-11 |
| SCI-B-077 | sí | MDE con n = 87: 0.203; el estimando balanceado (+0.154) queda por debajo | `analisis_fnd04_potencia_dominio.py`; MF-12 |
| SCI-B-078 | sí | sellos de MF-12 y MF-12-PRE sin métricas, entradas ni preregistro | MF-12 |
| SCI-B-079 | sí | el GO de MF-12-PRE aprueba el protocolo, no un gate | MF-12 |
| SCI-B-080 | sí | el join omite con `continue` los pids sin poses v2: denominador no garantizado | aquí |
| SCI-B-082 | sí | MF-13-PRE sella el runner, no el texto del preregistro | aquí |
| SCI-B-084 | sí | medianas de r50 condicionadas a r50 definido | MF-14 |
| SCI-B-085 | sí | ligando rígido (TORSDOF 0) | MF-14 |
| SCI-B-086 | sí | semilla con `hash(pid)` sin PYTHONHASHSEED: no regenerable | MF-14 |
| SCI-B-087 | sí | sello retroactivo: exploratorio post hoc | MF-14 |
| SCI-B-090 | sí | sólo train | MF-15 |
| SCI-B-091 | sí | sello sin entrada ni salida | MF-15 |
| SCI-B-093 | sí | consistencia sobre el mismo material, no réplica | MF-15-EXT |
| SCI-B-094 | sí, pero sin efecto: máximo 144 automorfismos en 52 ligandos | límite declarado y medido | `analisis_mf15ext_tope_automorfismos.py`; MF-15-EXT |
| SCI-B-095 | sí | sello sin material ni métricas | MF-15-EXT |
| SCI-B-098 | sí | runner sellado escribe en MF-16 (cifras de R1 ya reproducidas, SCI-B-096) | MF-16-R1 |
| SCI-B-099 | sí | G1/G2 del productor no preregistrados: no deciden | MF-16-R1 |
| SCI-B-100 | sí | análisis de casos completos | MF-16-R1 |
| SCI-B-101 | en parte: el r50 que usó coincide 48 de 48 con MF-14 sellado | la entrada de scratch era la sellada; la ruta sigue sin hash | `analisis_mf17_trazabilidad.py`; aquí |
| SCI-B-102 | sí | los 48 pids de MF-09 están en las otras tres fuentes; N por mecanismo publicado aquí | `analisis_mf17_trazabilidad.py`; aquí |
| SCI-B-103 | sí | fuente del confórmero y nº de candidatos confundidos | MF-19 |
| SCI-B-104 | sí | resultado reportado, no reconstruible desde el sello | MF-19 |
| SCI-B-064 | sí | el registro público marca MF-02B como reemplazado por MF-02B-R1 (14/38 y 79.3 %) | `_taxonomia.json` (reemplazos, editorial) |

**Pruebas nuevas:** `test_fnd04_potencia_dominio.py`, `test_rs14_bca.py`,
`test_fep03pdbbind_componentes.py`, `test_fep02ext_pdbbind_cobertura.py`,
`test_identidad_de_metricas.py`, `test_mf15ext_tope_automorfismos.py`,
`test_mf17_trazabilidad.py`.

---

## Lote de Sol (63 registros, IDs ≥ 105)

**Entrega:** `D:\moldesign-audits\FASE_1B_lote_sol\` (INFORME.md, ledger_cierre.json). Sol trabajó
en un worktree de sólo lectura; la integración es de esta sesión.

**Calificación** contra la clave sellada antes del encargo (`clave-fase-1b-lote-sol-2026-10-22.md`,
SHA-256 `937606ff…`): los cinco FALSA (133, 144, 148, 159, 164) coinciden con veredictos propios
escritos antes de abrir la entrega (`13b86981…`), incluida la p con censura de SCI-B-133 (0.2838);
la muestra de 12 (`random.Random(20261022)`) se reproduce sin ningún veredicto falso. **Fiable.**

**Lo que la entrega encontró fuera del lote:** el runner sellado de REC-07-R1 no tenía `-text` y
un checkout nuevo con `autocrlf=true` lo escribía con CRLF: el sello no validaba fuera del
worktree donde se selló. Arreglado, con una guarda para todo fichero sellado
(`test_sellados_sin_conversion_de_lineas.py`).

**Cifras que cambian:** SCI-B-133 p 0.2838 (no 0.5815); SCI-B-144 17.4 % (no 21 %); SCI-B-137
62 de 107 intercambiables (no 43); SCI-B-127 cociente 7.43 dentro de COLOCACION (11.71 mezclado);
SCI-B-153 los ejemplos de score de la narración de REC-09 eran de otro complejo.

**Analizadores:** `analisis_fase1b_{cohortes,falsas,limites,procedencia,rec01_agregacion}.py`, con
43 pruebas (`test_fase1b_*.py`). Son de Sol: estilo compacto, distinto del resto de `scripts/`.

**Sin paper en el repositorio** (MF-13, MF-24, MF-27, MF-29-EMP-EXT, MF-30-ALCANCE, MMGBSA-H5-R1,
PREP-01, REC-04, REC-09, REC-11): su corrección queda aquí; crear esos papers cambiaría el sitio
público y es otra decisión. Los documentos internos que Sol marca (doc. 02, 42, 52, 53, 80) quedan
por acotar; el doc. 49 está sellado en FND-06.

| ID | Verificación | Clase | Paper |
|---|---|---|---|
| SCI-B-105 | CONFIRMADO | A (texto) | `MF-21.md` |
| SCI-B-106 | PARCIAL | B (reanálisis) | `MF-21.md` |
| SCI-B-107 | PARCIAL | C (procedencia) | `MF-21.md` |
| SCI-B-108 | CONFIRMADO | A (texto) | aquí, abajo |
| SCI-B-109 | CONFIRMADO | A (texto) | aquí, abajo |
| SCI-B-110 | PARCIAL | B (reanálisis) | aquí, abajo |
| SCI-B-111 | CONFIRMADO | C (procedencia) | aquí, abajo |
| SCI-B-112 | CONFIRMADO | C (procedencia) | aquí, abajo |
| SCI-B-113 | CONFIRMADO | C (procedencia) | aquí, abajo |
| SCI-B-114 | CONFIRMADO | A (texto) | aquí, abajo |
| SCI-B-115 | CONFIRMADO | C (procedencia) | `MF-28.md` |
| SCI-B-116 | CONFIRMADO | B (reanálisis) | `MF-29-EMP.md` |
| SCI-B-117 | CONFIRMADO | C (procedencia) | `MF-29-EMP.md` |
| SCI-B-118 | CONFIRMADO | C (procedencia) | `MF-29-EMP-COR.md` |
| SCI-B-119 | PARCIAL | B (reanálisis) | `MF-29-EMP-COR.md` |
| SCI-B-120 | CONFIRMADO | C (procedencia) | `MF-29-EMP-COR.md` |
| SCI-B-121 | PARCIAL | B (reanálisis) | aquí, abajo |
| SCI-B-122 | CONFIRMADO | C (procedencia) | aquí, abajo |
| SCI-B-123 | PARCIAL | B (reanálisis) | `MF-29-EMP.md` |
| SCI-B-124 | PARCIAL | B (reanálisis) | aquí, abajo |
| SCI-B-125 | CONFIRMADO | A (texto) | aquí, abajo |
| SCI-B-126 | PARCIAL | B (reanálisis) | `MF-33.md` |
| SCI-B-127 | CONFIRMADO | B (reanálisis) | `MF-33.md` |
| SCI-B-128 | PARCIAL | B (reanálisis) | `MF-33-EXT.md` |
| SCI-B-129 | CONFIRMADO | C (procedencia) | `MF-33-EXT.md` |
| SCI-B-130 | CONFIRMADO | B (reanálisis) | `MF-33-EXT.md` |
| SCI-B-131 | CONFIRMADO | D (medida nueva pendiente) | `MF-33-EXT.md` |
| SCI-B-132 | PARCIAL | C (procedencia) | `MF-33-EXT.md` |
| SCI-B-133 | CONFIRMADO | B (reanálisis) | `MF-33-EXT.md` |
| SCI-B-134 | CONFIRMADO | C (procedencia) | `MF-33-EXT.md` |
| SCI-B-135 | CONFIRMADO | C (procedencia) | `MF-33-EXT.md` |
| SCI-B-136 | CONFIRMADO | A (texto) | `MF-33-ORD.md` |
| SCI-B-137 | CONFIRMADO | B (reanálisis) | `MF-33-ORD.md` |
| SCI-B-138 | PARCIAL | B (reanálisis) | `MMGBSA-H13-AZUFRE-AMBER.md` |
| SCI-B-139 | PARCIAL | B (reanálisis) | aquí, abajo |
| SCI-B-140 | CONFIRMADO | A (texto) | aquí, abajo |
| SCI-B-141 | CONFIRMADO | C (procedencia) | aquí, abajo |
| SCI-B-142 | CONFIRMADO | A (texto) | aquí, abajo |
| SCI-B-143 | CONFIRMADO | A (texto) | `RC-F0-V2.md` |
| SCI-B-144 | CONFIRMADO | B (reanálisis) | `RC-F0-V2.md` |
| SCI-B-145 | PARCIAL | B (reanálisis) | `RC-F0-V2.md` |
| SCI-B-146 | CONFIRMADO | A (texto) | `RC-F0-V2.md` |
| SCI-B-147 | CONFIRMADO | A (texto) | `RC-F0-V2-EXT.md` |
| SCI-B-148 | CONFIRMADO | B (reanálisis) | `REC-01.md` |
| SCI-B-149 | CONFIRMADO | C (procedencia) | `REC-01.md` |
| SCI-B-150 | CONFIRMADO | A (texto) | `REC-03.md` |
| SCI-B-152 | CONFIRMADO | A (texto) | aquí, abajo |
| SCI-B-153 | PARCIAL | B (reanálisis) | aquí, abajo |
| SCI-B-154 | CONFIRMADO | A (texto) | aquí, abajo |
| SCI-B-155 | CONFIRMADO | D (medida nueva pendiente) | `RS-03-PARAM-A.md` |
| SCI-B-156 | CONFIRMADO | D (medida nueva pendiente) | `RS-03-PARAM-A.md` |
| SCI-B-157 | CONFIRMADO | C (procedencia) | `RS-09.md` |
| SCI-B-158 | CONFIRMADO | A (texto) | `RS-09.md` |
| SCI-B-159 | CONFIRMADO | A (texto) | `RS-04-OOF.md` |
| SCI-B-160 | CONFIRMADO | A (texto) | `RS-08.md` |
| SCI-B-161 | CONFIRMADO | A (texto) | `FND-08.md` |
| SCI-B-162 | CONFIRMADO | B (reanálisis) | `MF-01.md` |
| SCI-B-163 | CONFIRMADO | A (texto) | aquí, abajo |
| SCI-B-164 | CONFIRMADO | A (texto) | `MF-26.md` |
| SCI-B-165 | CONFIRMADO | B (reanálisis) | `MF-25.md` |
| SCI-B-166 | CONFIRMADO | A (texto) | `MF-32.md` |
| SCI-B-167 | CONFIRMADO | A (texto) | `MF-28.md` |
| SCI-B-169 | CONFIRMADO | A (texto) | `MF-31.md` |

### Correcciones sin paper

- SCI-B-108 (MF-24). Las correlaciones de MF-24 son descriptivas y parte de sus variables
  requiere la estructura cristalográfica. rmsd_conf compara contra el cristal y se resta también
  en la definición del coste de colocación; su correlación con ese coste no es una señal
  operativa independiente disponible para un sistema sin pose nativa. Enterramiento también usa
  contactos en la pose cristalográfica. Ninguna de estas asociaciones valida por sí sola un
  predictor previo al docking.
- SCI-B-109 (MF-24). El enterramiento presenta una asociación marginal con el coste de
  colocación en dirección contraria a varios descriptores de tamaño. No se estimó su
  contribución independiente después de ajustar tamaño y flexibilidad ni se validó una ventaja
  predictiva propia. Se retira que sea el único predictor que no es tamaño disfrazado y que la
  asociación establezca que cerrar el bolsillo cause la mejora.
- SCI-B-110 (MF-24). La comprobación posterior de identidad encuentra 116 complejos en train y
  87 en val+test, sin solapamiento y con respuesta y torsiones presentes en cada fila. Coinciden
  con las particiones registradas en RC-F0-SYM. Esto verifica las salidas conservadas; no
  convierte la selección por directorio y variable de entorno en un control de partición
  ejecutado originalmente.
- SCI-B-111 (MF-24). El sello fija el analizador principal de MF-24; no fija las estructuras,
  conformeros, mapas, poses, helper ni el valor de la variable de entorno que eligió el
  material. La identidad de las particiones conservadas se ha contrastado posteriormente; no
  equivale a reconstruir las mediciones desde sus entradas originales. Esta procedencia no se
  completa retroactivamente. La exigencia de sellado de SCI-B-045 se aplica a experimentos
  nuevos desde el 2026-10-23; no sanea este registro retroactivamente.
- SCI-B-112 (MF-27). MF-27 conserva una narración de resultados, pero metrics.json contiene un
  objeto vacío y per_complex.jsonl no tiene filas. El sello fija el archivo declarado, no una
  tabla de mediciones que permita recontar el subgrupo y sus agregados. Las cifras narradas no
  quedan reproducidas por este cierre; se presentan como resultados históricos sin soporte
  tabular local recuperado. La exigencia de sellado de SCI-B-045 se aplica a experimentos nuevos
  desde el 2026-10-23; no sanea este registro retroactivamente.
- SCI-B-113 (MF-27). El sello fija analisis_mf24_predictores.py, que calcula el análisis global
  de MF-24; no fija un productor del subgrupo de MF-27, sus medianas, cocientes y MDE. No se
  atribuye a ese script la reproducción de ese análisis. Reconstruirlo ahora sería un análisis
  posterior nuevo, con sus propias entradas y salidas, y no la recuperación del productor
  histórico. La exigencia de sellado de SCI-B-045 se aplica a experimentos nuevos desde el
  2026-10-23; no sanea este registro retroactivamente.
- SCI-B-114 (MF-27). Ocupación de caja y radio de giro son descriptores relacionados de
  extensión, pero no transformaciones exactas entre sí: la ocupación usa el cubo del radio
  máximo al centroide y el radio de giro usa la raíz de la distancia cuadrática media. No se
  cuentan automáticamente como evidencias independientes ni se afirma una igualdad algebraica
  que el código no implementa.
- SCI-B-121 (MF-29-EMP-EXT). La extensión conservada contiene los dos complejos pendientes y,
  en cada uno, las tres semillas 42, 7 y 13 con score finito. Su unión sin duplicados con los 48
  casos completos anteriores contiene los 50 planificados y 4 mejoras, fracción 0,08. La
  comprobación de miembros y presupuesto se ha añadido al reanálisis; el productor original
  podía emitir una lectura con menos semillas o unidades.
- SCI-B-122 (MF-29-EMP-EXT). El sello fija el runner de la extensión y los resultados previos
  reutilizados; no fija las estructuras y conformeros preparados, centros, mapas, helper y
  binario de las corridas recuperadas. El reanálisis comprueba sus semillas y la unión
  conservada, sin afirmar que el sello permita reconstruir los mismos sistemas de cálculo. La
  exigencia de sellado de SCI-B-045 se aplica a experimentos nuevos desde el 2026-10-23; no
  sanea este registro retroactivamente.
- SCI-B-124 (MF-30-ALCANCE). Los dos grupos COLOCACION contienen exactamente los mismos 33
  identificadores. MF-09 cubre 3 y el brazo B de MF-33 cubre 26: el cociente descriptivo es 26/3
  = 8,67. La igualdad de miembros queda comprobada en este reanálisis, aunque el productor sólo
  comparaba agregados. Son protocolos diferentes y el cociente no identifica el efecto causal de
  un único cambio.
- SCI-B-125 (MF-30-ALCANCE). La restricción medida es la del runtime distribuido, con PyTorch
  CPU. La compatibilidad, el tiempo y la memoria de un generador alternativo concreto tendrían
  que medirse antes de incorporarlo. MF-30 no evaluó tal candidato y no demuestra que toda la
  familia de modelos generativos requiera GPU. La decisión de alcance se refiere a las
  capacidades demostradas de esta instalación.
- SCI-B-139 (MMGBSA-H5-R1). El reanálisis conjuga ausencia de fallos, paridad Windows/Linux con
  las mismas entradas y geometría, y el requisito Br/I: 24 topologías Br/I, una indeterminada
  por geometría y 23 evaluables que pasan. La conjunción pasa en los datos conservados. El
  booleano original sólo implementaba el último requisito y no bastaba por sí solo para
  acreditar el gate completo. La paridad entre plataformas se comprueba con sus diferencias
  directas, no con el flag de comparación frente a Sander.
- SCI-B-140 (PREP-01). El contador identifica especies cuyo inventario global disminuye y que
  tenían alguna copia próxima al sitio. No identifica qué copia desapareció: una retirada remota
  de la misma especie puede activar el aviso. Las cifras se describen bajo ese proxy y se retira
  su lectura como número exacto de pérdidas locales funcionales. La magnitud de esa sobrecuenta
  no se ha medido; las filas resumidas no permiten reconstruir el emparejamiento por copia.
- SCI-B-141 (PREP-01). El mantenimiento del sello conserva el hash anterior de preparer.py,
  pero la copia histórica suministrada coincide con el hash nuevo, no con el productor que el
  propio registro atribuye a los resultados. El sello fija el mantenimiento y esa copia; no
  recupera los bytes del filtro original. La versión original del módulo de reporte sí está
  conservada por separado y no reemplaza el filtro faltante. No se recalculan ni se reatribuyen
  las cifras usando el módulo vivo. La exigencia de sellado de SCI-B-045 se aplica a
  experimentos nuevos desde el 2026-10-23; no sanea este registro retroactivamente.
- SCI-B-142 (PREP-01). PREP-01 observó menos pérdidas de cofactores conocidos por su contador
  en la ruta del producto que en el dataset experimental. Esto describe retención bajo las
  políticas comparadas, sin resolver si cada copia era funcional, desplazable o aditiva. Se
  retira «mejor preparación» y la atribución causal a una lista positiva; el análisis no midió
  docking, cobertura ni calidad del sistema transferido.
- SCI-B-152 (REC-04). El inventario de titulables próximos se calculó con el primer registro
  encontrado de cada residuo, no con la distancia mínima de todos sus átomos. Además, la falta
  de centro no se distingue de una ausencia geométrica de residuos próximos. Se retiran estos
  recuentos como medida exhaustiva del sitio y la conclusión de que el receptor es mejor de lo
  temido basada en ellos. Recontar requiere las estructuras y centros identificados, con un
  estado no evaluable explícito cuando falten.
- SCI-B-153 (REC-09). La comparación por identificador verifica los 116 scores de cristal de
  MF-13 frente al brazo CON de REC-09: coinciden exactamente en los valores almacenados. En 1fkh
  ambos valen +2,550 y en 1ew8 +2,064 kcal/mol; −0,610 corresponde a 1eld en ambos archivos. Se
  retiran los valores −1,631 y −2,181 usados como ejemplos previos, y la comparación de −2,181
  con 1eld que mezclaba casos. El problema es la discordancia del texto con sus salidas, no un
  fallo observado de reproducción de los 116.
- SCI-B-154 (REC-11). El MDE es una magnitud de planificación bajo un tamaño, discordancia,
  nivel de significación y potencia supuestos. No es una resolución absoluta del instrumento ni
  un intervalo de incertidumbre del efecto observado. Un efecto menor puede resultar
  significativo en una realización sin alcanzar la potencia objetivo. Se retiran «no resoluble»
  y «límite de resolución medido»; el resultado se interpreta con su estimación, intervalo y
  potencia limitada.
- SCI-B-163 (MF-13). MF-13 compara el score de la referencia cristalográfica relajada
  localmente con el mejor candidato conservado. El resultado describe qué referencia observada
  prefiere esa función bajo esos protocolos; no demuestra dónde está su óptimo global ni si otra
  búsqueda puede recuperar una pose válida mejor puntuada. Se retira la partición causal
  exhaustiva entre búsqueda y puntuación y la afirmación de que ninguna búsqueda ayudaría cuando
  gana el candidato.

---

## SCI-B-155 y SCI-B-156 — RS-03-PARAM-A-R1 (medida nueva)

Preregistro `7dccb5dd`, antes de calcular. Contenedor `moldesign-science` del servidor (el del
original; openff-toolkit 0.18.0, openmm 8.5.2, NAGL `7981e7f5…`), 4 núcleos, 110 s. Sellado con
`sellar_experimento.py` (procedencia completa). **NO_GO preregistrado:** 1nw5 tiene un tiol con
H implícito que OpenFF añade como átomo 51, y su `System` tiene 52 partículas para 51 átomos del
SDF. En los 115 restantes: cargas a 5e-7 e de las selladas, energía finita, serialización exacta
y correspondencia de elementos, cargas y conectividad. 31 fallaron el criterio preregistrado sólo
por la etiqueta aromática del enlace (OpenFF kekuliza): diagnóstico posterior, declarado en
`LECTURA.md`, que no cambia la decisión. Controles negativos 229/229. Paper: RS-03-PARAM-A,
«Correcciones». Runner `scripts/run_rs03_param_a_r1.py`, pruebas `test_rs03_param_a_r1.py`.

---

## SCI-B-131 — MF-33-EXT-MOD-R1 (medida nueva)

Preregistro `01395459`, antes de calcular. CPU local, sin docking; importa sin modificar los
productores sellados de MF-33-DOSIS y MF-33-EXT-MOD. G0: reproduce exactamente MF-33-DOSIS en
los 48. G1: 65 de 68 completos. **GO preregistrado:** los cuatro descriptores sobreviven a BH en
los 68 (ρ 0.33–0.43; control barajado sin supervivientes). **Diagnóstico posterior declarado:**
controlando por `n_conformeros` (la dosis), ninguno conserva asociación (ρ parcial −0.17 a
−0.09). Son candidatos según el PRE, sin señal propia más allá de K. Sellado con
`sellar_experimento.py`. Runner `scripts/run_mf33extmod_r1.py`; pruebas `test_mf33extmod_r1.py`.
