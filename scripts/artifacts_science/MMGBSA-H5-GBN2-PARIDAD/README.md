# MMGBSA-H5-GBN2-PARIDAD

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Con la misma topologia y las mismas coordenadas, OpenMM 8.5.2 (Reference, doble precision) reproduce a sander en GBn2 sin termino de superficie para ligandos con Br o I: residuo de energia tras la conversion analitica de constantes < 0.001 kcal/mol y maximo error de fuerza convertida < 0.001 kcal/mol/A, en vacuum y GBn2_no_SA. El OpenMM del runtime que se entrega (Windows) reproduce al de Linux.

## Protocolo

Referencia: `backend/audits/gbn2_paridad_halogenos.py sobre las 55 topologias de lcpo_halogenos.py (GAFF2, cargas Gasteiger, mbondi3) en ~/moldesign-fep/halogenos_trabajo: medir con sander y OpenMM en el contenedor moldesign-science (servidor), medir --sin-sander con frontend/src-tauri/resources/python (esta maquina) sobre copias con el mismo SHA-256, comparar. Piloto previo de 3 ligandos declarado en docs/validacion_mmgbsa.md (H5): 1c5n falla por el azufre, no por el yodo.`

## Gate

GO si las 24 topologias con Br o I pasan en vacuum y GBn2_no_SA, o -solo si llevan S- el vacio pasa y el desacuerdo de GBn2 desaparece con el S como elemento generico (Z=34) en ambos programas; y OpenMM de Windows reproduce al de Linux con diferencia < 1e-6 kcal/mol y kcal/mol/A en todas las comparaciones con las mismas entradas. Cualquier otro fallo: NO_GO.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `codex/release-hygiene`, commit `d83d0af9a4e5dee98cf024d74fc9a0b83a38422d`, dirty=True

## Estado

- Creado: 2026-09-23T17:50:30.367042+00:00
- Status: finished
- Decisión: NO_GO
- Sellado: sí (2026-09-23T17:54:03.459385+00:00)
- Finalizado: 2026-09-23T17:54:03.627976+00:00
- Razón de la decisión: NO_GO por la letra del gate: 23/24 topologias con Br o I lo cumplen y 5mlj no. 19/24 pasan directamente (residuo de energia <= 2e-6 kcal/mol, fuerza <= 1.1e-4 kcal/mol/A); las 4 que llevan azufre fallan solo en GBn2 y las 4 recuperan la paridad con el S como elemento generico en ambos programas (residuo <= 6.3e-6). 5mlj (Br alifatico, sin S) falla ya en vacio (3.88 kcal/mol, 71 kcal/mol/A) por una geometria de entrada imposible, no por el bromo: el H22 del SDF de PDBBind esta a 0.259 A de C13 (angulo C13-C17-H22 = 1.2 grados) y toda la diferencia esta en el termino de angulo; el gate no preveia esa excepcion y no se cambia despues de medir. Controles F/Cl: 23/23 sin S pasan y 8/8 con S se atribuyen igual. OpenMM de Windows (python del runtime que se entrega) reproduce al de Linux en 110/110 comparaciones con las mismas entradas: 8.5e-14 kcal/mol y 1.6e-13 kcal/mol/A. Hallazgo aparte: el desacuerdo del azufre en GBn2 llega a 11.24 kcal/mol (2weg) y 4.87 (5eij, 2 S); afecta a cualquier Met/Cys del receptor. Siguiente: MMGBSA-H5-R1 con un filtro de validez geometrica declarado antes de medir.
- Hashes de assets: 9 archivo(s) con SHA-256

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
