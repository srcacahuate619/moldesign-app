# MMGBSA-H3-FREESOLV-RADIOS

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

En GBn2 (con las correcciones de fosforo y de descreening de Amber), usar para Br e I el radio de Bondi (1.85 y 1.98 A) en vez del 1.5 A que asigna mbondi3 reduce el error absoluto medio de la energia libre de hidratacion calculada frente a la experimental de FreeSolv v0.52 en las moleculas con Br o I, con el termino no polar calibrado solo en moleculas sin halogeno.

## Protocolo

Referencia: `backend/audits/freesolv_h3.py. FreeSolv v0.52 (DOI 10.5281/zenodo.1161245, datos CC BY 4.0), 642 moleculas, coordenadas 3D de sus SDF, un confomero sin minimizar; regla de curacion declarada: los 37 nitro que el SDF de OEChem escribe como N(-O-)(-O-) se corrigen a [N+](=O)[O-] y se exige el InChIKey del SMILES (37/37 recuperados; 2 difieren solo en estereoquimica y se aceptan). GAFF2 + AM1-BCC (antechamber) + mbondi3 (tleap) en el contenedor moldesign-science. Polar: energia de la CustomGBForce de OpenMM 8.5.2 con apply_amber_gbn2_phosphorus y apply_amber_gbn2_descreening; brazo B cambia RADII de Br/I en el prmtop antes de construir el sistema. No polar: gamma*SASA+b, SASA de FreeSASA Lee-Richards (radios de Bondi, sin H), gamma y b por minimos cuadrados SOLO en las moleculas sin halogeno. PB de AmberTools (pbsa, radiopt=0, space 0.25, fillratio 4) como referencia electrostatica fuera del gate. Piloto previo de 6 moleculas (1 Br, 1 I, 1 nitro, 1 con S, 2 controles) solo para probar la cadena: no se comparo con el experimento.`

## Gate

Sin ajustar nada en Br ni en I, sobre las 37 moleculas con Br o I (21 Br, 4 Br mixtas, 12 I): GO si MAE_B <= 0.8*MAE_A y el IC bootstrap 95% (1000 remuestreos de moleculas, semilla 20260923) de MAE_B - MAE_A queda entero por debajo de 0. NO_GO en cualquier otro caso. Br e I se informan por separado sin las mixtas; los controles no cambian entre brazos por construccion; PB y el valor alquimico GAFF de FreeSolv se informan como referencia.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 20260923
- Git: rama `codex/release-hygiene`, commit `493f06a91d3878c995505b681d199e3eebda1b9d`, dirty=True

## Estado

- Creado: 2026-09-23T19:27:51.560147+00:00
- Status: finished
- Decisión: NO_GO
- Sellado: sí (2026-09-23T22:42:43.009619+00:00)
- Finalizado: 2026-09-23T22:42:55.859786+00:00
- Razón de la decisión: NO_GO por la letra del gate: sobre las 37 moleculas con Br o I, MAE_A (1.5 A, mbondi3) 1.930 y MAE_B (Bondi, Br 1.85 e I 1.98 A) 2.053 kcal/mol; reduccion relativa -6.4% (se exigia >= 20%) e IC95 bootstrap de MAE_B - MAE_A [-0.010, +0.246], que no queda entero bajo cero. Br (n 21): MAE 1.67 -> 1.80, sesgo +1.57 -> +1.73. I (n 12): MAE 1.13 -> 1.27, sesgo +0.06 -> +0.76. El brazo B reduce el error en 8 de 37 moleculas. Se cumple la clausula de refutacion de H3: el radio por defecto da menos error; con 1.5 A el Br ya queda infrasolvatado (sesgo positivo) y agrandar el radio lo empeora. No polar ajustado solo en 467 moleculas sin halogeno: gamma 0.02537 kcal/mol/A2, b -3.418 kcal/mol. La primera medida se perdio por un fallo del script, no de la quimica (pbsa corta los nombres de archivo a 80 caracteres; los 37 fallos son exactamente las 37 Br/I, registrados en failures.jsonl); corregido y declarado en f7871d8, se repitio solo la etapa medir sobre los mismos prmtop: 642/642, y las 605 moleculas que ya habian salido son identicas bit a bit. Caracterizacion exploratoria posterior al gate (freesolv_h3_caracterizar.py; no cambia la decision): con PB en lugar de GB y el no polar reajustado igual, Bondi tampoco mejora (Br/I MAE 1.15 -> 1.21; Br empeora, I mejora 1.28 -> 1.00), asi que el NO_GO no es un artefacto de la aproximacion GB. GBn2 sobresolvata frente a PB con los mismos radios las moleculas con 3 F (media -2.34 kcal/mol, n 13) y con 4 o mas F (-7.68, n 5), mientras con 1 o 2 F coincide (+0.55, +0.45); y el modelo deja un sesgo de +5.94 kcal/mol en las policloradas (4 o mas Cl, n 31) que PB no explica (GB-PB -0.40), atribuible al termino no polar. Son hipotesis nuevas, no resultados.
- Hashes de assets: 13 archivo(s) con SHA-256

## Flujo de trabajo

1. `init`: crea este directorio con `manifest.json` prellenado y skeletons vacíos.
2. Ejecutar el experimento: escribir `metrics.json`, `per_complex.jsonl` y `failures.jsonl`.
3. `validate`: verifica `manifest.json` contra `manifest.schema.json`.
4. `seal`: registra los SHA-256 de datasets/modelos/binarios/assets y congela el manifest.
5. `finish`: escribe la decisión (GO/NO_GO/INCONCLUSIVE), la razón y la duración.
6. `maintain`: documenta de forma auditada los assets sellados que cambian tras el sello.

Después del `seal`, `validate` falla si cualquier archivo sellado cambia o desaparece.

## Inmutabilidad post-seal

- No se permite volver a sellar un experimento ya sellado (protege el cegamiento FND-05).
- `finish` y `maintain` son las únicas operaciones que modifican `manifest.json` después del sellado.
- `maintain` solo actualiza `assets_hashes` y registra cada cambio en `seal_maintenance`; datasets/modelos/binarios son inmutables.
- El README.md regenerado por `seal`/`finish`/`maintain` es la excepción documentada a la regla anterior.
- Los artefactos de producción permanecen fuera de este árbol (docs/49, sección 17).

## Archivos

- `manifest.json`: registro único del experimento (config, hashes, código, ambiente, salida).
- `metrics.json`: métricas agregadas del experimento.
- `per_complex.jsonl`: una línea JSON por complejo evaluado.
- `failures.jsonl`: una línea JSON por fallo.
- `README.md`: este archivo.
