# MF-33-ORD

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La desviacion de la distribucion del primer acierto respecto a una geometrica homogenea que midio MF-33-EXT-MOD esta producida por el ORDEN NO INTERCAMBIABLE de los conformeros -conf0 es el primero de ETKDG y puede ser sistematicamente mejor- y no requiere heterogeneidad entre complejos.

## Protocolo

Referencia: `Ver prerregistro MF-33-ORD-PRE, sellado antes de correr. RE-ANALISIS PURO SIN COMPUTO DE DOCKING: cada conformero se dockeo independientemente con la misma semilla y su rmsd_min esta guardado por separado, asi que permutar el orden es una re-lectura EXACTA. Tres contrastes: rango de conf0 entre sus K conformeros; 10000 permutaciones del orden recalculando el chi2 con el procedimiento identico al de MF-33-EXT-MOD; y verificacion de invariancia del conjunto nunca cubierto. Semilla 42.`

## Gate

PRIMARIO: p_permutacion del chi2 observado contra la nula bajo orden intercambiable. p_perm<0.05 LA DESVIACION ERA EL ORDEN; p_perm>=0.05 LA DESVIACION SOBREVIVE AL ORDEN. El contraste del rango de conf0 se reporta siempre. PROHIBIDO leer p_perm>=0.05 como que la heterogeneidad queda ESTABLECIDA.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `9fcb6f891963ee10e194d72024a62ac8c6b73adb`, dirty=True

## Estado

- Creado: 2026-08-21T15:52:03.864741+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-21T15:52:04.638594+00:00)
- Finalizado: 2026-08-21T16:01:47.115961+00:00
- Razón de la decisión: LA HIPOTESIS QUEDA FALSIFICADA EN LA DIRECCION DECLARADA, y la explicacion que yo mismo habia elevado a mas plausible se cae con dos contrastes independientes. CONTRASTE 1 - CONF0 NO ES ESPECIAL. Su rango normalizado medio entre los K conformeros del propio complejo es 0.503 contra 0.5 esperado bajo intercambiabilidad: z=0.116, p=0.908. conf0 es EXACTAMENTE UN CONFORMERO MEDIO. La idea de que el primer conformero de ETKDG tuviera ventaja intrinseca -que en MF-33-EXT-MOD llegue a llamar la explicacion mas simple y mas probable del exceso en k=1- no tiene ningun apoyo. CONTRASTE 2 - LA DESVIACION SOBREVIVE AL ORDEN, y en la direccion contraria a la esperada: chi2 observado 11.03 contra una nula por permutacion con mediana 25.14 y p95 39.33, p_perm=0.9773. Solo un 2.3% de los ordenes aleatorios dan un chi2 tan pequeno o menor que el real. Es decir, EL ORDEN REAL ATENUA la desviacion en vez de crearla: si el exceso en k=1 fuese artefacto de haber puesto primero un conformero privilegiado, randomizar deberia acercar a la geometrica, y ocurre lo contrario. Eso permite retirar el efecto de posicion con seriedad. POR QUE ESO NO ESTABLECE LA HETEROGENEIDAD, y el prerregistro lo prohibe expresamente: la permutacion CONSERVA el multiconjunto de rmsds de cada complejo, de modo que la nula ya incluye toda la heterogeneidad entre complejos. Este contraste NO la pone a prueba: solo pone a prueba el orden. La formulacion correcta es que la heterogeneidad entre complejos sigue siendo una explicacion PLAUSIBLE de la desviacion, no la explicacion en pie por descarte: quedan sin separar la dependencia entre conformeros, la heterogeneidad en el NUMERO de conformeros, la geometria de los estados generados, las diferencias entre bolsillos, la interaccion conformero-receptor y la estructura de orden posterior. Establecer un componente refractario seguiria exigiendo modelos de mezcla que aqui no se ajustan. OBSERVACION SIN EXPLICAR, declarada como tal: que el chi2 observado sea MENOR que el de casi todos los ordenes aleatorios sugiere alguna estructura en el orden que ETKDG genera, no caracterizada y no usada para nada. CONTRASTE 3 - C11 ES INVARIANTE, VERIFICADO en 200 permutaciones. MEDICION ANADIDA SOBRE LOS MISMOS DATOS, que cuantifica por que C11 pesa mas que la separacion G1/G2: con P(G1) = m/K, donde m es el numero de conformeros que cubren, 64 complejos tienen P(G1)>=0.80, 36 caen en la zona inestable 0.20<P(G1)<0.80 y 7 tienen P(G1)<=0.20. DE LOS 107 CUBIERTOS, 43 -EL 40.2%- PUEDEN CAMBIAR DE CLASE G1<->G2 SEGUN EL ORDEN. G1 y G2 no son propiedades del complejo sino del PAR complejo-orden; G3 es propiedad del conjunto completo de candidatos generados y no depende del orden. CONSECUENCIA PARA LA POLITICA DE PARADA, que no se buscaba y aparece igual: una politica no debe intentar aprender que un complejo ES G1, porque no es una propiedad intrinseca. La pregunta correcta es secuencial -dado lo observado, cual es la probabilidad de que mas inicializaciones aporten una cuenca util nueva- mientras que G3 plantea otra distinta: hay senales de que seguir muestreando ataque el mecanismo equivocado. Son STOP_SUCCESS contra CONTINUE contra ABSTAIN/REVIEW_INPUT, las mismas primitivas a las que llego el analisis de coste por otra via. LIMITES: no toca la cobertura de MF-33-EXT, que tampoco depende del orden; no ajusta modelos de mezcla; la permutacion asume intercambiabilidad bajo la nula, que es la hipotesis contrastada y no un supuesto.
- Hashes de dataset: 1 archivo(s) con SHA-256
- Hashes de assets: 1 archivo(s) con SHA-256

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
