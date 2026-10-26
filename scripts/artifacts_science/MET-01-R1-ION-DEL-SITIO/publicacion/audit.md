# MET-01-R1: metales con y sin ion — 2026-10-21

**NO_GO.** Mantener retirada y abstención. CON aporta una línea base para un futuro modelo de coordinación (M5).

Producto `9ce8b10490fcdd1c21b5dc0cf1efa8f3eae76d70`, prerregistro `dfdc9a269343f7993a8d36bc25e361407cf01035`, Vina 1.2.7, Meeko 0.7.1,
PoseBusters 0.6.5 dock MF-33-H-COR, 8/9/1, semillas 42–46.
La tabla compara el brazo normal a pH 7,4. RMSD / válido / conjunto son tres
conteos separados: RMSD ≤2 Å, PoseBusters passed y ambos a la vez. El gate
exacto de CAL además exige que todos los RMSD exitosos sean físicamente válidos.
Un guion es no medido, no cero de reproducción. Las cifras de cada corrida,
los nueve RMSD solicitados (o las poses realmente devueltas), distancias a cada
ion y requisitos completos están en `per_complex.jsonl` y sus crudos sellados.

| Entrada | Metal | Coordina | SIN RMSD / válido / conjunto | CON RMSD / válido / conjunto | Reproduce SIN / CON | His CON | Recomendación |
|---|---|---|---|---|---|---|---|
| 1BN1 | ZN | sí | 0/5 · 5/5 · 0/5 | 0/5 · 5/5 · 0/5 | no / no | 0/5 | Retirar y abstenerse; baseline M5 |
| 1C3R | ZN | sí | 2/5 · 5/5 · 2/5 | 1/5 · 5/5 · 1/5 | no / no | 0/5 | Retirar y abstenerse; baseline M5 |
| 1C3S | ZN | sí | 0/5 · 5/5 · 0/5 | 0/5 · 5/5 · 0/5 | no / no | 0/5 | Retirar y abstenerse; baseline M5 |
| 1J36 | ZN | sí | 0/5 · 5/5 · 0/5 | 0/5 · 5/5 · 0/5 | no / no | 5/5 | Retirar y abstenerse; baseline M5 |
| 1J37 | ZN | sí | 3/5 · 5/5 · 3/5 | 0/5 · 5/5 · 0/5 | sí / no | 5/5 | Retirar y abstenerse; baseline M5 |
| 1T69 | ZN | sí | 0/5 · 5/5 · 0/5 | 0/5 · 5/5 · 0/5 | no / no | 0/5 | Retirar y abstenerse; baseline M5 |
| 1VKG | ZN | sí | — | — | no / no | 0/5 | Abstenerse: excluida |
| 1W22 | ZN | sí | 0/5 · 5/5 · 0/5 | 1/5 · 5/5 · 1/5 | no / no | 0/5 | Retirar y abstenerse; baseline M5 |
| 1ZZ1 | ZN | sí | 2/5 · 5/5 · 2/5 | 0/5 · 5/5 · 0/5 | no / no | 0/5 | Retirar y abstenerse; baseline M5 |
| 2A3W | CA | sí | 1/5 · 3/5 · 1/5 | 2/5 · 5/5 · 2/5 | no / no | 0/5 | Retirar y abstenerse; baseline M5 |
| 2AW1 | ZN | sí | 5/5 · 5/5 · 5/5 | 5/5 · 5/5 · 5/5 | sí / sí | 5/5 | Retirar y abstenerse; baseline M5 |
| 2GH6 | ZN | sí | 0/5 · 5/5 · 0/5 | 1/5 · 5/5 · 1/5 | no / no | 0/5 | Retirar y abstenerse; baseline M5 |
| 2JDI | MG | sí | 1/5 · 5/5 · 1/5 | 2/5 · 5/5 · 2/5 | no / no | 0/5 | Retirar y abstenerse; baseline M5 |
| 2X8Z | ZN | sí | 0/5 · 5/5 · 0/5 | 0/5 · 5/5 · 0/5 | no / no | 5/5 | Retirar y abstenerse; baseline M5 |
| 2X90 | ZN | sí | 0/5 · 5/5 · 0/5 | 0/5 · 5/5 · 0/5 | no / no | 5/5 | Retirar y abstenerse; baseline M5 |
| 3QXX | MG | sí | 0/5 · 5/5 · 0/5 | 0/5 · 5/5 · 0/5 | no / no | 0/5 | Retirar y abstenerse; baseline M5 |
| 4CA7 | ZN | sí | 0/5 · 2/5 · 0/5 | 0/5 · 3/5 · 0/5 | no / no | 5/5 | Retirar y abstenerse; baseline M5 |
| 4CA8 | ZN | sí | 0/5 · 1/5 · 0/5 | 0/5 · 1/5 · 0/5 | no / no | 5/5 | Retirar y abstenerse; baseline M5 |
| 4CVL | MG | sí | 0/5 · 5/5 · 0/5 | 0/5 · 5/5 · 0/5 | no / no | 0/5 | Retirar y abstenerse; baseline M5 |
| 4PHL | MG, ZN | control | 5/5 · 5/5 · 5/5 | 5/5 · 5/5 · 5/5 | sí / sí | 5/5 | Retirar y abstenerse; baseline M5 |
| 4QA0 | ZN | sí | 4/5 · 5/5 · 4/5 | 0/5 · 5/5 · 0/5 | sí / no | 0/5 | Retirar y abstenerse; baseline M5 |
| 4QGE | MG, ZN | control | 0/5 · 5/5 · 0/5 | 0/5 · 5/5 · 0/5 | no / no | 5/5 | Retirar y abstenerse; baseline M5 |
| 4WUD | MG | sí | 5/5 · 5/5 · 5/5 | 5/5 · 5/5 · 5/5 | sí / sí | 0/5 | Retirar y abstenerse; baseline M5 |
| 5A2R | ZN | control | 0/5 · 5/5 · 0/5 | 0/5 · 5/5 · 0/5 | no / no | 5/5 | Retirar y abstenerse; baseline M5 |
| 5E92 | MG | sí | — | — | no / no | 0/5 | Abstenerse: excluida |
| 5I3T | K | control | — | — | no / no | 0/5 | Abstenerse: excluida |
| 5TY1 | ZN | sí | 0/5 · 5/5 · 0/5 | 0/5 · 5/5 · 0/5 | no / no | 5/5 | Retirar y abstenerse; baseline M5 |
| 5Z2R | MG | sí | 5/5 · 5/5 · 5/5 | 5/5 · 5/5 · 5/5 | sí / sí | 0/5 | Retirar y abstenerse; baseline M5 |
| 6E53 | MG | sí | 2/5 · 5/5 · 2/5 | 1/5 · 5/5 · 1/5 | no / no | 0/5 | Retirar y abstenerse; baseline M5 |
| 6HSK | ZN | sí | 0/5 · 5/5 · 0/5 | 0/5 · 5/5 · 0/5 | no / no | 0/5 | Retirar y abstenerse; baseline M5 |
| 6KE5 | CA | control | 0/5 · 5/5 · 0/5 | 0/5 · 5/5 · 0/5 | no / no | 0/5 | Retirar y abstenerse; baseline M5 |
| 6S1Y | ZN | sí | — | — | no / no | 0/5 | Abstenerse: excluida |
| 6S1Z | ZN | sí | — | — | no / no | 0/5 | Abstenerse: excluida |
| 6USR | K, MG | sí | — | — | no / no | 0/5 | Abstenerse: excluida |
| 7JVU | ZN | sí | 3/5 · 5/5 · 3/5 | 1/5 · 5/5 · 1/5 | sí / no | 0/5 | Retirar y abstenerse; baseline M5 |
| 7JVW | ZN | sí | 0/5 · 5/5 · 0/5 | 0/5 · 5/5 · 0/5 | no / no | 0/5 | Retirar y abstenerse; baseline M5 |
| 7SGG | ZN | sí | 0/5 · 5/5 · 0/5 | 0/5 · 5/5 · 0/5 | no / no | 0/5 | Retirar y abstenerse; baseline M5 |
| 8UBR | MG | sí | — | — | no / no | 0/5 | Abstenerse: excluida |
| 8WGR | K | control | — | — | no / no | 0/5 | Abstenerse: excluida |
| 9GKV | ZN | sí | — | — | no / no | 0/5 | Abstenerse: excluida |
| 9RJE | ZN | sí | 5/5 · 5/5 · 5/5 | 5/5 · 5/5 · 5/5 | sí / sí | 0/5 | Retirar y abstenerse; baseline M5 |

## Exclusiones anteriores al docking

- **1VKG**: CATALOG_UNPREPARABLE: Error preparando proteína '1VKG' en el paso 'mk_prepare_receptor'; SIN_NOT_REPRESENTABLE: POST /targets/1VKG/variants: HTTP 500, esperado [201]: {"error":"InternalServerError","message":"Ocurrió un error interno no controlado","detail":null}; CON_NOT_REPRESENTABLE: POST /targets/1VKG/variants: HTTP 500, esperado [201]: {"error":"InternalServerError","message":"Ocurrió un error interno no controlado","detail":null}; CAL_REFERENCE_UNMAPPABLE: el ligando del cristal no casa con el SMILES de la desipramina
- **5E92**: CAL_REFERENCE_UNMAPPABLE: Explicit valence for atom # 14 C, 5, is greater than permitted
- **5I3T**: CATALOG_UNPREPARABLE: Error preparando proteína '5I3T' en el paso 'mk_prepare_receptor'; SIN_NOT_REPRESENTABLE: POST /targets/5I3T/variants: HTTP 500, esperado [201]: {"error":"InternalServerError","message":"Ocurrió un error interno no controlado","detail":null}; CON_NOT_REPRESENTABLE: POST /targets/5I3T/variants: HTTP 500, esperado [201]: {"error":"InternalServerError","message":"Ocurrió un error interno no controlado","detail":null}
- **6S1Y**: CAL_REFERENCE_UNMAPPABLE: Explicit valence for atom # 3 C, 5, is greater than permitted
- **6S1Z**: CAL_REFERENCE_UNMAPPABLE: Explicit valence for atom # 13 C, 5, is greater than permitted
- **6USR**: CON_NOT_REPRESENTABLE: POST /targets/6USR/variants: HTTP 500, esperado [201]: {"error":"InternalServerError","message":"Ocurrió un error interno no controlado","detail":null}; CAL_REFERENCE_UNMAPPABLE: No matching found
- **8UBR**: SIN_DIFFERS_FROM_CATALOG; Variant SIN retains 70 additional atoms of ATP A1502/A1503; every shared protein atom is identical. Catalogue preparation passes site_ligand=ATP and removes that reference cofactor; variant ingestion omits site_ligand during prepare_target for the new USR ID, retaining the other ATP instances. Thus SIN is not the catalogue baseline. Excluded before docking; no product patch.
- **8WGR**: CON_NOT_REPRESENTABLE: POST /targets/8WGR/variants: HTTP 500, esperado [201]: {"error":"InternalServerError","message":"Ocurrió un error interno no controlado","detail":null}; CAL_REFERENCE_UNMAPPABLE: el ligando del cristal no casa con el SMILES de la desipramina
- **9GKV**: CAL_REFERENCE_UNMAPPABLE: el ligando del cristal no casa con el SMILES de la desipramina

Las exclusiones de referencia describen el alcance del método CAL, no prueban
que el depósito sea erróneo. Los HTTP 500 de variantes se contrastan con el
fallo determinista del preparador del catálogo; no son corridas fallidas de Vina.
Los errores completos y hashes están en el protocolo.

## Potencia, gate y límites

Discordancias CON:SIN=0:3,
n=28, p=0.25,
exclusiones principales=7/35.
Efecto mínimo preregistrado=40 puntos; q=0,5 declarado; potencia
con n=35: 94.76 %, con n evaluable: 87.24 %.
Las tablas exactas y los repartos significativos están en `entrada/potencia.json`.
Controles completos=False; pérdidas demostradas=0.
No se aplica selección retrospectiva ni se proponen entradas Verificadas.

## Reproducción mínima

1. Aprovisionar el runtime declarado y verificar sus hashes.
2. `python scripts/medir_met01r1.py selftest` y `analyze` reconstruyen el análisis
   desde los archivos versionados, sin cápsula ni token.
3. Para una nueva corrida, crear cápsulas nuevas. Para cada entrada/arm:
   `POST /targets/{pdb_id}/variants` con `name` y `cofactors_whitelist` de
   `entrada/protocolo.json`; heredar caja/cadena y verificar SHA-256 esperado.
4. El arnés llama sin modificación a `calibracion_receptor.Backend.evaluar`:
   preflight → submit → status → result persistido → SDF de poses → Preparación.
   `run --phase confirmatory --shard 1` (también 2 y 3) omite registros terminales;
   para repetir evidencia hay que usar un directorio nuevo, nunca reescribirla.
5. Verificar `scripts/validar_sellos.py --check`. Los privados de las cápsulas
   no se distribuyen; las salidas científicas necesarias sí.

## Condiciones diagnósticas y del validador

Reglas SMARTS, forma completa, pH y dos comprobaciones por proceso están en
el prerregistro. 6 entradas diagnósticas ejecutables,
60 corridas, fuera del gate. El producto no ofrece una
opción general para fijar cualquier protonación de ligando; las formas
no representables están declaradas.

Cristales CON con fallo de controles inorgánicos:
ninguno de los evaluados.
Avisos de His coordinante con H: 55/160 corridas CON normales.
No se corrige preparación ni PoseBusters para conseguir otro veredicto.

La decisión es del propietario. Redocking no mide actividad ni energía de
coordinación; no acredita compatibilidad con FEP ni generaliza al catálogo.
