# MF-33-H-COR-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El indicador de validez fisica de PoseBusters que el programa viene reportando esta dominado por un defecto de la capa de RECONSTRUCCION, no por tension real del ligando dockeado. Si es asi, regenerar los hidrogenos desde la geometria de atomos pesados dockeada -manteniendolos completamente fijos- cambia la tasa de validez de forma material sin mover un solo atomo pesado.

## Protocolo

Referencia: `EL DEFECTO, confirmado en el codigo. posebusters_metrica.mol_con_hidrogenos anade TODOS los hidrogenos sobre la geometria CRISTALOGRAFICA; pose_a_mol reemplaza despues solo las coordenadas presentes en el PDBQT, que de Vina trae unicamente los polares. Los no polares se quedan en posiciones del cristal, incompatibles con la pose en cuanto los pesados se mueven. PoseBusters optimiza solo los hidrogenos que el mismo anade y deja fijos los explicitos que recibe. El resultado es una molecula HIBRIDA cuya energia interna se dispara sin que haya tension real. RECONSTRUCCION CORREGIDA: se parte del grafo de atomos pesados con las coordenadas dockeadas, se eliminan TODOS los hidrogenos, se regeneran desde esa geometria y se optimizan con los pesados COMPLETAMENTE FIJOS -AddFixedPoint sobre cada pesado-, maximo 500 iteraciones. Ningun hidrogeno hereda coordenadas cristalograficas por construccion. INVARIANTES QUE SE VERIFICAN Y SE REPORTAN POR POSE: desplazamiento pesado maximo dentro de 1e-6 A; SMILES canonico identico; carga formal identica; numero de enlaces identico; cero hidrogenos heredados del cristal; y resultado determinista. Una pose que viole cualquiera de ellas se cuenta aparte y no entra en la tasa. DOS AMBITOS, porque corregir uno solo dejaria el otro suspendido en vez de reemplazado. AMBITO A, MF-33-PB: los 48 complejos y las 8215 poses del brazo flexible retenidas por MF-33-B-RET-R1 y R2. AMBITO B, MF-33-TOP1: los 116 complejos del protocolo rigido, top-1 de los dos brazos, reconstruidos desde los conf<i>.out.pdbqt que siguen en disco. Se reportan LADO A LADO, por pose: reconstruccion historica, reconstruccion corregida, energia interna de cada una, cada control individual y el PB-valid total. LOS ARTEFACTOS ORIGINALES NO SE TOCAN: MF-33-PB y MF-33-TOP1 quedan sellados e inmutables. Esto produce un artefacto nuevo. Script: scripts/run_mf33hcor_reconstruccion.py.`

## Gate

SIN GATE DE ACEPTACION, Y ES DELIBERADO. Un corrigendum de implementacion no se aprueba ni se rechaza: se ejecuta y se reporta. La cantidad que produce es la tasa de validez fisica bajo la reconstruccion corregida, con la historica al lado para que la diferencia sea auditable. NO ES CIEGO Y NO LO FINGE. Los 12 casos del piloto diagnostico ya fueron inspeccionados, y la prueba tecnica previa a este sellado mostro ademas el complejo 10gs del ambito B. El piloto DEMUESTRA EL DEFECTO Y DISENA LA CORRECCION; no estima la tasa nueva, que es lo que este artefacto mide sobre las cohortes completas. QUEDA SUSPENDIDO hasta que este corrigendum cierre, y no debe citarse: 217/8215 = 2.64% de poses validas; el 97.3% de fallos por internal_energy; el 8/48 contra 10/48 de MF-33-PB; el 8.62% contra 15.52% de MF-33-TOP1; y las conclusiones 'la validez fisica es deficiente', 'el ensemble no arregla la validez fisica' y 'una minimizacion post-docking atacaria directamente el problema'. NO QUEDA INVALIDADO y puede seguir citandose: RMSD y cobertura del oraculo; top-1, top-5 y la cascada de conversion; las coordenadas de atomos pesados; y los controles exclusivamente geometricos de pesados, que se reportan por separado. El indicador compuesto PB-valid SI se recalcula, porque exige que internal_energy pase. PROHIBIDO: modificar o re-sellar MF-33-PB y MF-33-TOP1; presentar la tasa corregida como si viniera de una medicion ciega; concluir del corrigendum nada sobre el PROTOCOLO DE DOCKING, que no se toca aqui; y ejecutar MF-33-MIN, cuya premisa depende de la cifra suspendida.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `codex/mejora-producto`, commit `7430ef25a578bea9161a253169a5f075dfe26a99`, dirty=True

## Estado

- Creado: 2026-08-23T08:56:45.544660+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-23T08:56:46.299043+00:00)
- Finalizado: 2026-08-23T08:56:46.439312+00:00
- Razón de la decisión: Prerregistro sellado ANTES de ejecutar la corrida completa y DESPUES de la prueba tecnica, que es el orden que hoy se aprendio a golpes: dos prerregistros de esta misma jornada sellaron scripts rotos y costaron un R1 cada uno. Sellar antes de probar no gana ceguera -la prueba tecnica no produce decision por contrato- y cuesta un artefacto extra. ES UN CORRIGENDUM DE IMPLEMENTACION, no un experimento nuevo, y suspende provisionalmente una medicion DOMINANTE que ya esta citada en docs/50, docs/52, el manuscrito y un informe de auditoria externa. Por eso se escribe antes de tocar nada y por eso enumera explicitamente que queda suspendido y que no. El mecanismo esta confirmado en el codigo y verificado en la prueba tecnica: sobre 10gs, la reconstruccion historica da 295660741 kcal/mol y la corregida 124.8, con desplazamiento de atomos pesados de 0.0 A, mismo SMILES, misma carga formal, mismo numero de enlaces y los mismos 28 hidrogenos, cero heredados del cristal. La pose pasa de invalida a valida sin que se mueva un solo atomo pesado. SE CORRIGEN LOS DOS AMBITOS a proposito. Recalcular solo MF-33-PB dejaria el 8.62% y el 15.52% de MF-33-TOP1 suspendidos para siempre en vez de reemplazados, y esas dos cifras son las que estan citadas fuera del registro. MF-33-TOP1 es recalculable porque sus 8570 conf<i>.out.pdbqt siguen en disco. MF-33-MIN NO SE EJECUTA. Su brazo RESTRINGIDA deja los hidrogenos libres, asi que mediria exactamente este artefacto y 'confirmaria' de forma trivial que la minimizacion arregla la fisica. Se registra como cancelado antes de ejecutar y superado por este corrigendum; NO como NO_GO, porque su hipotesis no llego a probarse: lo que desaparecio fue la validez de su premisa. Este corrigendum no debilita el programa. Es la demostracion de para que sirven la procedencia, la retencion forense y el derecho a corregir una medicion plausible pero equivocada antes de publicarla.
- Hashes de dataset: 3 archivo(s) con SHA-256
- Hashes de assets: 2 archivo(s) con SHA-256

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
