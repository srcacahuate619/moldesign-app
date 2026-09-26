# Verificación independiente de las fases 0-7 — 2026-09-26

Revisión hecha antes de publicar, sobre la punta de la fase 7 (`06d27b6`).
No sustituye la revisión del auditor: dice qué se midió, con qué, y qué se
corrigió después. Cada cifra lleva su condición.

## Método

- Runtime: el Python 3.11.9 embebido que coincide con
  `backend/requirements-embed.lock.txt` (starlette 1.7.0, PyJWT 2.15.0,
  cryptography 50.0.1).
- Suites y puertas ejecutadas como `.github/workflows/ci.yml`: las pruebas del
  backend **desde `backend/`**, no desde la raíz. Esa diferencia importa (ver
  más abajo).
- Base de comparación: `27c4b79`, cuyo `backend/` y `rescoring/` son idénticos
  a los del commit auditado `ae4db6a` (`git diff --quiet` sobre ambos
  directorios).

## Lo que se sostiene

**Las pruebas nuevas detectan el defecto que dicen corregir.** Las 36 pruebas
nuevas de `backend/tests/` se ejecutaron contra el código base:

- 96 fallan;
- 11 archivos ni siquiera se importan, porque usan funciones que no existían;
- 23 pasan: son controles negativos parametrizados. Por ejemplo, `inf` ya se
  rechazaba antes, pero `NaN` y `−inf` no.

Cada uno de los 36 archivos tiene al menos una prueba que falla sin la
corrección.

**LIG-001, con el script `t2_determinismo.py` del auditor**, en 5 procesos
independientes con `PYTHONHASHSEED` aleatorio:

- en la base, 4 de 20 moléculas cambian de especie entre procesos (la
  talidomida S produce 3 especies distintas, igual que en el hallazgo);
- en la fase 7, 0 de 20.

Las especies elegidas son químicamente razonables: losartán −1 (tetrazolato),
metformina +1, cimetidina 0, glucosa-6-fosfato −2. El imatinib sale +2; ya salía
así en la base y el propio `chem/ionizacion.py` lo declara como fallo conocido
de la tabla por clases.

**SCORE-007.** Se recalculó el AUC desde `resultados/predictions.jsonl` (ese
archivo no se publica, ver el índice), sin usar el código del proyecto:

| Estrato | n | AUC |
|---|---:|---:|
| Holdout completo | 328 | 0.8818 |
| Proteínas vistas en el pool | 233 | 0.8852 |
| Proteínas no vistas | 95 | 0.8544 |

Las cifras son idénticas a las de `fase6.md`.

**Hashes.** Todos los hashes citados en las bitácoras coinciden con los bytes
versionados:

- dominio de aplicabilidad;
- `model_a_universal` y `classifier_binder`;
- golden E2E;
- copia histórica de PREP-01;
- evidencia de la fase 6;
- `config_hash` v2 del registro.

Los hashes de archivos `.py` son de los bytes en git: un checkout de Windows
con conversión CRLF produce otro valor. Pasó con
`scripts/phase6_classifier_holdout.py`, cuyo blob sí es `8ff82896…`.

**Cobertura.** 128 de los 131 hallazgos se nombran en las bitácoras de fase:

- ENG-A17 y PROV-017 no se nombran, pero quedan resueltos por ENG-A03 y LIG-005;
- DOCK-012 no se corrigió (ver pendientes).

## Lo que no se sostenía en `06d27b6`, y cómo se corrigió

Ejecutada como la CI, la punta de la fase 7 dejaba estas puertas en rojo:

| Puerta | Causa | Corregido en |
|---|---|---|
| Suite backend: 2 fallos | `unload_admet_model()` seguía leyendo `_tabpfn_classifier`, retirado en fase 6: `NameError` en cada descarga por inactividad del modelo ADMET | `3fcf35f` |
| Suite backend: 2 fallos | Pruebas no actualizadas a M4 v2 ni al sello de la versión activa | `3fcf35f` |
| Suite backend: 1 fallo | `test_phase6_peptide_policy` usaba una ruta relativa al directorio de trabajo: pasaba desde la raíz y fallaba desde `backend/` | `d3c0e0b` |
| Suite rescoring: 1 fallo | La prueba de integración seguía exigiendo el AD antiguo (`threshold_p99`) | `3fcf35f` |
| `report_test_counts --check` | Registro sin actualizar: 2571 → 2767; sólo bajan `test_corridas_doradas` (30→27, fase 4) y `test_fallback_open_babel` (10→5, fase 1) | `3fcf35f` |
| `generate_openapi_contract --check` | La fase 7 añadió `POST /evaluation/batch/{batch_id}/cancel` y retiró `num_workers` sin regenerar el contrato | `d3c0e0b` |
| `generate_runtime_inventory --check` | Seguía declarando el manifiesto v4 y el hash del catálogo anterior a la fase 1 | `d3c0e0b` |

Además se corrigieron dos defectos que la CI no veía, ambos en `3fcf35f`:

- **Sesión de escritorio.** Tras reiniciar la app, la renovación del token
  podía convertir una cuenta personal en invitado o perder la sesión del
  invitado. La fase 5 lo agravó al ligar los tokens de invitado al arranque.
- **Caché de features del rescoring.** Se indexaba por la ruta del receptor y
  no por su contenido: un receptor sustituido reutilizaba contactos del
  anterior.

La prueba peptídica corregida sigue detectando el defecto: el sidecar de
`27c4b79` acepta una petición sin caja, y el actual la rechaza con
`SIN_CAJA_DECLARADA`.

## XGBoost sobre poses de Vina

Un diagnóstico aparte, hecho durante esta revisión, midió el clasificador sobre
las poses de Vina históricas de 320 de los 328 complejos del holdout. Las 8
ausencias son positivos. La etiqueta es pKi ≥ 7 dentro de PDBBind, así que la
medida separa ligandos fuertes de débiles, no activos de inactivos.

| Subconjunto | n | AUC clasificador | AUC −Vina | ρ Model A | ρ −Vina |
|---|---:|---:|---:|---:|---:|
| Todos | 320 | 0.841 | 0.769 | 0.574 | 0.447 |
| Proteínas vistas | 228 | 0.859 | 0.764 | 0.573 | 0.442 |
| **Proteínas no vistas** | 92 | **0.766** | **0.812** | 0.507 | 0.455 |

Condiciones del diagnóstico:

- bootstrap pareado por clúster, 2000 réplicas, semilla 42;
- en proteínas no vistas, el IC95 % de la diferencia de AUC clasificador−Vina
  es [−0.138, 0.034];
- geometría reextraída de la primera pose histórica con el `_protein.pdb`, sin
  la preparación de receptor de las fases 1-2 ni el selector de poses de
  producción.

**Conclusión.** En proteínas parecidas a las de entrenamiento el clasificador
añade señal; en proteínas nuevas no hay evidencia de que mejore a Vina. Por eso
se mantiene M4 v2 (XGBoost con peso 0 en el ranking) sin afirmar que XGBoost
carezca de valor. Las predicciones por complejo no se publican porque derivan de
afinidades de PDBBind.

## Hallazgos de esta revisión que siguen abiertos

Estado al cerrar la primera parte. Los puntos 1 a 3 se corrigen o se miden
en la segunda parte, más abajo.

1. **DOCK-012 (MEDIA) no se corrigió.** `_check_ligand_fits_box` sigue
   comparando la caja con la extensión por ejes del confórmero de entrada, que
   depende de su orientación.
2. **La guarda de cofactores (DOCK-003) bloquea 12 de las 380 dianas del
   catálogo.** Diez casos están justificados porque el cofactor está en el sitio
   o a ≤ 4,3 Å de la caja: HEM en 2NNJ, 2VE3, 4EJJ, 4NY4 y 4O1Z; ADP en 1HWK;
   SEP en 7TM9; PTR en 4E4N y 6N7B. 4BCF queda en el límite (TPO a 5,9 Å). Dos
   son exceso de bloqueo:
   - **5TGZ (CB1)**, por un FMN a 30,7 Å, de la proteína de fusión de
     cristalización;
   - **6GUE (CDK2/ciclina A)**, por la fosfotreonina 160 a 7,9 Å, fuera del
     margen de 6 Å que la fase 1 aplica a los residuos perdidos.
3. **El panel de selectividad declara tres anti-dianas, pero una no se evalúa.**
   CYP3A4 (4NY4) está entre las 12 bloqueadas: el panel la marcará siempre como
   `unpreparable`. En la práctica evalúa hERG y 5-HT2B.
4. **El runtime del árbol principal no coincide con el lockfile.** Tiene
   starlette 1.0.0, PyJWT 2.8.0 y cryptography 42.0.7. Un instalador
   construido sin regenerarlo no llevaría las actualizaciones de API-015.
5. **No se construyó un instalador NSIS** ni se probó una instalación limpia.

## Segunda parte: lo que se corrigió después (commit `30a9eb5`)

### Guarda de cofactores con margen de sitio (DOCK-003)

La guarda de la fase 1 bloqueaba cualquier cofactor sin plantilla Meeko,
estuviera donde estuviera. Ahora aplica el mismo margen que la fase 1 usa para
los residuos que pierde Meeko (`MARGEN_SITIO_A = 6.0`):

- a 6 Å o menos de la caja, bloquea;
- más lejos, los fosfo-residuos vuelven a su aminoácido (TPO→THR, SEP→SER,
  PTR→TYR, retirando el fosfato, como ya se hacía con MSE→MET) y los demás
  cofactores se retiran;
- todo queda declarado en el informe de preparación, en la procedencia de la
  corrida y en el aviso `COFACTORES_SIN_PLANTILLA_FUERA_DEL_SITIO`.

La receta del receptor sube a la versión 6.

Comprobación de extremo a extremo con Meeko 0.7.1 y Vina 1.2.7:

- **6GUE (CDK2/ciclina A):** la TPO160 está a 7,9 Å de la caja. Se prepara con
  THR160 y Vina devuelve 5 poses; la mejor, −8,67 kcal/mol con roscovitina, es
  un control de ejecución, no una afinidad validada.
- **5TGZ (CB1):** su FMN está a 30,7 Å (pertenece a la flavodoxina fusionada
  para cristalizar) y ya no bloquea. Sigue sin prepararse por otra razón:
  Meeko elimina 5 residuos del sitio con la cadena lateral incompleta.

### Disponibilidad del catálogo: medida, no supuesta

`backend/data/disponibilidad_catalogo.json` lo genera
`scripts/generate_catalog_availability.py`:

- la parte de cofactores se recalcula con la misma función que usa
  `prepare_target` y se comprueba en la suite;
- `--barrido` prepara de verdad las 370 dianas restantes con Meeko.

Se ejecutó dos veces con resultado idéntico. De 380 dianas:

| Motivo | Dianas |
|---|---:|
| Meeko elimina residuos a ≤ 6 Å de la caja (guarda DOCK-002 de la fase 1) | 119 |
| Meeko no puede construir el receptor (errores internos de la cadena, p. ej. «Expected 2 paddings») | 11 |
| Cofactor sin plantilla a ≤ 6 Å de la caja (DOCK-003) | 10 |
| **No disponibles** | **140 (36,8 %)** |

De los 846 residuos que Meeko elimina en esas 119 dianas, 842 tienen la cadena
lateral incompleta en el PDB depositado (sobre todo Lys, Glu, Arg y Gln). En
1.0.1 esos residuos se borraban en silencio y se acoplaba contra el hueco
(DOCK-002). La fase 1 convirtió ese borrado en bloqueo, pero no midió cuántas
dianas afectaba. Las 140 siguen en el catálogo, marcadas con `disponible: false`
y su motivo: la interfaz las muestra y no deja elegirlas.

Resolver las 119 exige decidir cómo completar esas cadenas laterales
(reconstruirlas o truncarlas a los átomos observados, en ambos casos
declarado). Es una decisión científica abierta.

### DOCK-012

`_check_ligand_fits_box` compara el diámetro del ligando (la máxima distancia
entre dos átomos) con el lado menor de la caja. Ya no depende de la orientación
del confórmero de entrada, y el `except Exception: pass` se sustituyó por
errores concretos, que se registran en el log.

### Panel de selectividad

- **Por defecto:** hERG (5VA1) y 5-HT2B (4NC3). Ambas pertenecen al panel
  mínimo de 44 dianas de Bowes et al. 2012 (Nat Rev Drug Discov 11:909).
- **CYP3A4 sale del panel por defecto:** no está entre esas 44 (su inhibición
  es una interacción fármaco-fármaco que ya estima ADMET) y 4NY4 no se puede
  preparar sin plantilla del hemo.
- **La interfaz pedía por defecto 5VA1, 4NY4, 4NC3, 1SO2 y 6MVW** en tres
  componentes. 1SO2 (PDE3B) y 6MVW (NavAb) eran las identidades erróneas que la
  fase 1 retiró del panel; el backend las seguía acoplando como «anti-diana del
  usuario». Ahora la interfaz pide el panel del backend, y una prueba lo fija.
- **Se ofrecen, sin marcar**, 9 dianas más de Bowes 2012 cuya identidad humana
  se comprobó en la cabecera COMPND/SOURCE de su PDB: 5-HT1A, 5-HT1B, 5-HT2A,
  β1, β2, CB1, NET, receptor de andrógenos y COX-2. Se excluyeron 4BVN (β1 de
  pavo), 1GPK (AChE de *Torpedo*) y 6Y5A (5-HT3 de ratón).
- **Con el inventario actual sólo se pueden preparar hERG, 5-HT1A y NET.**
  5-HT2B y las demás quedan no disponibles por cadenas laterales incompletas en
  el sitio.

### Metadatos de organismo del catálogo

20 de las 380 entradas declaran *Homo sapiens*, pero su PDB es de otro
organismo según su propio registro SOURCE. Entre ellas: la proteasa del VIH,
la Mpro del SARS-CoV-2, varias enzimas bacterianas, NavAb, el β1 de pavo y la
AChE de *Torpedo*. No se ha corregido: cambiaría datos del catálogo. Queda
abierto, con la lista reproducible en esta verificación.

### MolChat (ORQ-001)

Los 8 fármacos en cuarentena (12 nombres y alias) vuelven al diccionario con el
SMILES isomérico de PubChem: naproxeno, paroxetina, captopril, penicilina G,
amoxicilina, adrenalina, glutamato y nicotina. Se verificaron de dos formas:

- el InChIKey completo recalculado con RDKit coincide con el de PubChem;
- la configuración CIP de cada centro es la del fármaco: (S)-naproxeno,
  (3S,4R)-paroxetina, (2S,5R,6R)-penicilinas, (R)-adrenalina, L-glutamato y
  (S)-nicotina.

El diccionario conserva 25 entradas con centros sin asignar. Casi todas son
fármacos que se comercializan como racemato, para los que el SMILES sin
estereoquímica es correcto. Dos quedan por revisar: el tramadol (racemato
*cis*: sin estereoquímica admite también el diastereómero *trans*) y la
metanfetamina (el fármaco es el enantiómero S).
