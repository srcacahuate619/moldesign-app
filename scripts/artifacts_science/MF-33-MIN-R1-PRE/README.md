# MF-33-MIN-R1-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El 97.3% de fallos de internal_energy que midio MF-33-PB es un ARTEFACTO del protocolo -conformeros rigidos que nunca se relajan- y no fisica real del ligando unido. Si lo es, la tension se puede liberar SIN mover la pose y una minimizacion restringida arregla la validez fisica sin degradar la geometria. La alternativa es que la tension sea intrinseca a estar colocado ahi, en cuyo caso liberarla exige mover la pose y minimizar comprara validez fisica a costa de precision geometrica.

## Protocolo

Referencia: `Sin dockear ni una sola pose nueva: se relajan las 8215 ya retenidas por MF-33-B-RET-R1 y MF-33-B-RET-R2 y se vuelve a medir. Cohorte: los 48 de MF-33, que es donde hay cristal y por tanto donde se puede arbitrar si moverse fue bueno o malo. DOS BRAZOS DE RELAJACION sobre LAS MISMAS poses, pareado perfecto: RESTRINGIDA, minimizacion MMFF con restricciones armonicas de 10 kcal/mol/A2 sobre cada atomo pesado, que deja relajar enlaces, angulos y torsiones pero penaliza el desplazamiento; responde si la tension se puede liberar EN EL SITIO. LIBRE, minimizacion MMFF sin restricciones; responde CUANTO tiene que moverse la molecula para dejar de estar tensa. Maximo 500 iteraciones en los dos. Por pose se mide, antes y despues: validez fisica con PoseBusters en configuracion redock reusando el modulo sellado posebusters_metrica.py; el desplazamiento respecto a la pose de partida, SIN alineamiento, porque interesa cuanto se movio en el marco del receptor y alinear borraria justo esa senal; y el rmsd_pose_pocket al cristal. La geometria cruda de 47 complejos vive en MF-33-B-RET-R1 y la de 1afl en R2, que es el unico que R2 recomputo; el runner resuelve en ese orden y registra cual uso. Contenedor moldesign-lab-pb:0.6.5 del servidor. Script: scripts/run_mf33min_relajacion.py. CAMBIO DE IMPLEMENTACION, NO DE PROTOCOLO: las restricciones posicionales se ponen con `ff.MMFFAddPositionConstraint`, la API soportada, en vez de montarlas a mano con AddExtraPoint mas AddDistanceConstraint. Los dos brazos, sus constantes y todas las cantidades medidas son identicos.`

## Gate

DOS CO-PRIMARIAS, y las dos se leen JUNTAS. Es la razon de ser de este diseno: medir solo la fisica produciria un GO para un cambio que puede estar rompiendo lo unico que hoy funciona bien. CO-PRIMARIA 1, FISICA: fraccion de complejos cuyo top-1 pasa la bateria completa, pareada antes/despues, McNemar exacto bilateral. CO-PRIMARIA 2, GEOMETRIA: fraccion de complejos cuyo top-1 sigue cubriendo a <=2.0 A, pareada antes/despues, McNemar exacto bilateral. CUATRO LECTURAS ESCRITAS ANTES, por brazo: (1) la fisica mejora con p<0.05 y la geometria NO se degrada => ERA_ARTEFACTO_SE_PUEDE_ADOPTAR, y la minimizacion entra al pipeline; (2) la fisica mejora pero la geometria se degrada con p<0.05 => COMPRA_FISICA_A_COSTA_DE_GEOMETRIA_NO_ADOPTAR, y el resultado es que la tension sostenia la colocacion; (3) la fisica no mejora => LA_MINIMIZACION_NO_ARREGLA_LA_FISICA y la hipotesis sobre internal_energy era falsa; (4) el resto => SIN_DIFERENCIA_DETECTABLE, sin leerlo como equivalencia. EFECTO MINIMO DETECTABLE DECLARADO ANTES: con n=48, el MDE pareado es de 11.85 pp si la discordancia sale del 10%, 16.77 pp si del 20% y 20.53 pp si del 30%; y con c=0 el McNemar exacto exige b>=6 para p<0.05. SECUNDARIO descriptivo y sin gate: el desplazamiento mediano de cada brazo, y la misma tabla sobre el conjunto completo de poses y no solo el top-1. PROHIBIDO: adoptar la minimizacion si sale la lectura (2), por mucho que la mejora fisica sea grande; leer la lectura (1) como permiso para minimizar en produccion sin medir antes el efecto sobre el ranking, que este experimento NO toca; presentar el desplazamiento como criterio de descarte en produccion, donde no hay cristal para arbitrar y la regla seria circular; y comparar estas tasas con MF-33-TOP1 o con la configuracion dock de produccion. NADA DE ESTE GATE CAMBIA respecto a MF-33-MIN-PRE: se reproduce palabra por palabra, incluidas las dos co-primarias, las cuatro lecturas, el MDE y las prohibiciones. LA CEGUERA SE CONSERVA ENTERA: la version anterior no llego a producir ni un solo resultado -reventaba en el campo de fuerzas antes de evaluar nada-, y la prueba que lo destapo corrio con `--limite`, que por contrato fuerza NO_LEER_GATES_TECNICOS.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `codex/mejora-producto`, commit `7430ef25a578bea9161a253169a5f075dfe26a99`, dirty=True

## Estado

- Creado: 2026-08-23T08:27:03.419621+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-23T08:27:04.183116+00:00)
- Finalizado: 2026-08-23T08:27:04.340473+00:00
- Razón de la decisión: Prerregistro sellado ANTES de ejecutar. Existe por la misma razon mecanica que MF-33-PB-R1-PRE: el anterior sello un script que no corria, y un prerregistro sellado no se re-sella. EL DEFECTO: las restricciones posicionales del brazo RESTRINGIDA se montaban a mano con AddExtraPoint mas AddDistanceConstraint, y eso rompe el campo de fuerzas -'Pre-condition Violation: size mismatch' en ForceField.cpp- porque anadir puntos extra despues de construirlo exige reinicializarlo. Se sustituye por ff.MMFFAddPositionConstraint, que es la via soportada, en vez de parchear la artesanal. Verificado antes de sellar sobre una molecula tensionada a proposito: la restringida baja la energia de 143.71 a 19.76 desplazandose 0.102 A y la libre baja a 18.91 desplazandose 0.145 A, que es exactamente el comportamiento que el diseno pide. LA CEGUERA SE CONSERVA ENTERA, y este caso es mas limpio que el de MF-33-PB: alli la version rota llego a devolver 261 poses no evaluadas; aqui reventaba en el campo de fuerzas ANTES de evaluar nada, asi que no se produjo ni un numero. La prueba que lo destapo corrio con --limite, que por contrato nunca produce decision. LECCION DE PROCESO, que va al docs/50 seccion 12.3: es la SEGUNDA vez en el dia que un prerregistro sella un script que la prueba tecnica destapa como roto. El orden correcto es escribir el runner, pasar la prueba tecnica, y SOLO ENTONCES sellar. Sellar antes no gana ceguera -la prueba tecnica no produce decision- y cuesta un prerregistro extra cada vez.
- Hashes de dataset: 2 archivo(s) con SHA-256
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
