# Pestaña «Explicabilidad»: controles de respuesta conocida (2026-11-08)

**Pregunta.** ¿Capta bien las señales lo que la pestaña le enseña a la persona, o hay un error en un
elemento concreto? Se midió con controles cuya respuesta se conoce por una vía independiente del código
(química de los 20 aminoácidos, geometría construida a mano, fórmulas moleculares, salidas reales de Vina
y la aritmética de XGBoost), y cada control se comprobó contra una **mutación**: un defecto sembrado a
propósito que el control tiene que detectar. Un control que no falla ante su defecto no cuenta.

**Alcance.** Qué número sale del extractor, cómo lo nombra el SHAP y cómo lo dice la interfaz. **No**
valida que Model A prediga bien la afinidad: eso lo miden `CAL-8HFI-01` y `CAL-D-01-R4-2-VMAT2-8T69`.

## Resultado

| | |
|---|---|
| Controles nuevos | **114 pruebas**: 52 del extractor, 19 del SHAP, 20 del mapa de contactos y de su caché, 23 de la interfaz |
| Errores del producto hallados y corregidos | **4** (el 2.º y el 3.º en el extractor, el 1.º y el 4.º en lo que se dice) |
| Límites y huecos **no** corregidos | 4 (ver más abajo) |
| Suites afectadas | rescoring 392 pasan, 9 saltadas; frontend 264 archivos y 2533 pruebas pasan, `tsc` limpio; backend, 194 y 81 pasan en los archivos que tocan PDF, informe, interacciones y rescoring |

## Errores hallados, con la medida

1. **El SHAP se leía como si explicara la afinidad entera, y no la explica.** Model A es de *delta*
   (`is_delta_model: true`): su salida es el pKi de Vina (−puntuación / 1,36), que se suma **fuera** de los
   árboles, más la corrección que sí explica el SHAP. Además se descartaba el valor base y se mostraban
   sólo las 10 mayores contribuciones. Medido con `model_a_universal` sobre 20 complejos sintéticos
   (10 ligandos × 2 poses frente a un decapéptido), lo omitido por el recorte tiene mediana 0,85 pK y
   máximo 1,14 pK, y es mayor que la barra más pequeña que se enseña en ≥ 80 % de los casos. Ahora la
   respuesta declara `shap_output` (`delta_pKi` o `pKi`, según el modelo), la interfaz lo dice, avisa de que
   las barras no suman la salida y advierte cuando el dominio de aplicabilidad es falso o desconocido.
   Controles: S01, S02, S05, S06, S07, P01 a P05.
2. **Átomos que no son ligando contaban como carbono, o no se contaban.** Un macrociclo de Vina trae
   pseudoátomos de pegado (`G0`) que el extractor leía como carbono; el boro y el silicio también caían en
   «C»; y las líneas PDBQT recortadas perdían átomos. Medido con la pose **real** de exaltólido
   (C15H28O2, 17 átomos pesados): `heavy_atom_count` valía **19** y ahora vale **17**. Esa cifra entra en
   `contacts_per_ha_*`. Controles: X09 a X12.
3. **Con hidrógenos escritos como átomos, todo N y todo O de la proteína salía «aceptor».**
   `_assign_prot_ecif_type` usaba `GetTotalNumHs()`, que cuenta los implícitos y no los hidrógenos del
   archivo. Medido sobre los PDB de receptor de la caché local (`~/MolDesign/data/targets`, 34 receptores;
   3 traen hidrógenos): en 5TBO, `N_don` pasa de 2 a 467 de 478 N (el mismo receptor sin hidrógenos da 466);
   en 8ZP2 de 9 a 667 (sin H, 660); en 1BN1 de 4 a 331 (sin H, 322). La diferencia residual es el estado de
   protonación que el archivo declara. Model A **sí usa** esas características: ganancia total de
   `ecif_N_don_*` + `ecif_O_don_*` = 5,6 % en `model_a_universal` y 39,8 % en `model_a_gpcr`, así que el
   modelo se entrenó viéndolas pobladas (inferencia; no se abrió el conjunto de entrenamiento) y un
   receptor protonado le llegaba con ellas a cero. Arreglado con `_tiene_hidrogeno`
   (`GetTotalNumHs(includeNeighbors=True)`); `CACHE_VERSION` pasa de 5 a 6 porque cambia lo que un
   receptor protonado produce en la caché de entrenamiento. Controles: X01 con hidrógenos y el X01 de
   equivalencia con y sin hidrógenos. **Lo que no se hizo:** las corridas ya guardadas con esos tres
   receptores no se recalculan, y no se midió cuántos de los 381 del catálogo traen hidrógenos.
4. **El texto de las características describía mal lo que mide.** El diccionario manual decía
   «nitrógenos donadores del ligando» de `ecif_N_don_C`, cuando el nombre es
   `ecif_{tipo de PROTEÍNA}_{elemento del LIGANDO}`: el donador es de la proteína y el ligando sólo se
   distingue por su elemento. Nueve entradas describían características que el modelo no tiene, y
   afirmaba lo que el extractor no mide («borde del solvente», «interactuando fuertemente», «puentes de H
   implícitos», «propiedad extraída del complejo» para `logp`). Ahora el texto sale de la gramática del
   nombre y las 167 características del modelo distribuido tienen etiqueta y descripción en los dos idiomas.
   Controles: K01 a K11, P07, P08.

Además, la pestaña dejó de pedir al backend el mapa de contactos en cada visita: se guarda el informe ya
verificado de cada pose (frontend) y el backend repite, como mucho, un cálculo por corrida y pose en un
caché acotado a 16 entradas con la clave que incluye el hash del SDF y del receptor (M07, C01 a C03). Se
retiraron además la rama del beeswarm heredado y el radar GNN, que dibujaban una heurística sin validar.

## Lo que se comprobó correcto (señales que sí se captan)

| Control | Qué se conoce de antemano | Resultado |
|---|---|---|
| X01 | tipo de átomo de los 20 aminoácidos, con y sin H | coincide con la química (tras el arreglo 3) |
| X02 | el primer elemento del nombre es el de la **proteína** | sí, en ECIF y en capas |
| X03 y X04 | capas `[d, D)` con distancias exactas y conteo de **pares**, no densidad | sí |
| X05 | ECIF a 6 Å frente a capa 4–8 Å | sí |
| X06 y X07 | los hidrógenos del ligando no se cuentan; `contacts_per_ha` = contactos / átomos pesados | sí |
| X09 | SDF (entrenamiento) y PDBQT de Meeko (inferencia) dan las mismas características para 10 ligandos con C, O, N, S, F, Cl, Br, I, P, B y Si | sí, tras el arreglo 2 |
| X13 y X14 | invariancia a un movimiento rígido y al orden de los átomos | sí |
| S01 y S02 | base + Σφ = salida del modelo; en producción, `score_a = pKi_Vina + margen` | sí |
| S03 | una señal plantada en una columna aparece con ese nombre con tres órdenes de columnas | sí; con los nombres invertidos falla |
| S04 | una característica que ningún árbol usa vale exactamente 0 y no mueve la salida | sí |
| S07 y S08 | el orden de nombres del metadato es el del booster; la respuesta sólo nombra características del modelo | sí |
| M01 | π-stacking Phe–tolueno a 3,8 Å resalta los 6 átomos del anillo y no el metilo | sí |
| M02 | puente de H Ser, Thr y Tyr a 2,8 Å resalta sólo el O aceptor | sí |
| M03 | el resaltado sigue al átomo si se permutan los índices del SDF (semillas 1, 4, 9) | sí; al mezclar sin seguirlo, falla |
| M04 y M05 | umbrales 2,8 y 3,2 Å se detectan; 4,0 y 4,6 Å no; a 40 Å no hay contacto | sí |
| M06 | Meeko→SDF conserva el elemento de cada átomo (paracetamol real de Vina, exaltólido, aspirina, fosfonato, fosfina) | sí |

M06 descartó una sospecha: Meeko **no** introduce fósforo donde el ligando no lo tiene. El «PH» visto en un
mapa de una molécula concreta tiene que venir del SMILES evaluado; no se pudo confirmar para esa corrida.

## Mutaciones: cada control falla ante su defecto

| Defecto sembrado | Controles que fallan |
|---|---|
| extractor de `HEAD` (sin el arreglo 2; medido antes de añadir el arreglo 3) | 11 del extractor |
| `resumir_shap` con nombres desalineados | 3 de S03 |
| `omitido` mal calculado | 7 |
| caché del backend desactivada | M07 |
| índice del resaltado desplazado en uno | 7 de 20 (el resto no depende de él) |
| tipado sin `includeNeighbors` | 2 (X01 con H y la equivalencia con y sin H) |
| mapa de la interfaz sin caché | C01 y C02 |
| `shap_output` ausente tratado como delta | P01 y P04 |
| etiqueta ECIF con el ligando primero | K04, K05, P07 |
| «propiedad del complejo» reintroducida en `logp` | K07 |
| descriptor sin registrar | K01, K02, K11 |
| sin aviso de dominio cuando es `null` | P05 |

## Límites medidos que **no** se corrigieron

1. **`close_contacts_*` y `contacts_per_ha_*` cuentan hidrógenos**, así que dependen de cómo venga
   protonado el archivo (X08 lo mide y fija el límite). Corregirlo cambiaría la distribución con la que se
   entrenó el modelo. La descripción lo dice.
2. **No hay característica de capa para el yodo** (`shell_*` llega a F, P, Cl y Br; ECIF lo agrupa en `Hal`).
   Es coherente entre entrenamiento e inferencia y no se puede cambiar sin reentrenar.
3. **La interfaz no enseña el valor base ni la suma de lo omitido**, sólo declara que existen. El backend ya
   calcula ambos (`ResumenShap.base` y `.omitido`); falta decidir si se muestran.
4. **No se midió** el instalador (WebView2, Tauri): las pruebas corren sobre el código, el export estático y
   el runtime de desarrollo con python-embed 3.11.9.

## Reproducir

```bash
cd rescoring && ../python-embed/python.exe -m pytest tests/test_xai_controles_extractor.py tests/test_xai_controles_shap.py -q
cd backend && ../python-embed/python.exe -m pytest tests/test_xai_controles_mapa_contactos.py -q
cd frontend && npx vitest run lib/__tests__/xaiFeatures.test.ts components/interfaces/pro/__tests__/ProXaiControles.test.tsx
```
