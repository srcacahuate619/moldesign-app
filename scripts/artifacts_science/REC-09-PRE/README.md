# REC-09-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Los cristales que puntuan absurdamente mal no son sistemas a los que les FALTA algo, sino a los que les SOBRA: el pipeline conserva todas las aguas -politica que nadie declaro, hallazgo abierto de REC-08-EXT- incluidas las que el ligando desplaza al unirse, y un agua que ocupa el sitio choca con el ligando cristalografico y dispara el termino de repulsion de Vina.

## Protocolo

Referencia: `Sin recomputar ningun docking. Para cada complejo de train: contar aguas del receptor con algun atomo a <= d_clash=2.6 A de un atomo pesado del ligando cristalografico -d_clash es el mismo valor que MF-28 declaro antes de correr, se reusa y no se ajusta-; score_only del cristal contra rec.pdbqt tal cual; score_only contra el mismo receptor SIN esas aguas y solo esas; delta = con - sin. El cristal se prepara RIGIDO, el rigid_str de molflex.escribir_pdbqt, identico a MF-13, misma caja de 25 A, misma semilla 42, mismo binario. Leccion de MF-29-EMP-COR aplicada: los dos scores de cada pareja salen del MISMO PDBQT de ligando, asi que la penalizacion torsional se cancela en el delta. Contenedor moldesign-lab del servidor. Script: scripts/run_rec09_aguas_bloqueantes.py.`

## Gate

G1 DE VALIDEZ, ANTES DEL PRIMARIO: score_con_aguas reproduce el score_cristal de MF-13 dentro de 0.10 kcal/mol en >=95% de los complejos; si no reproduce, no se esta puntuando lo mismo que MF-13 y nada se lee. UMBRAL DE ABSURDO DECLARADO ANTES Y NO AJUSTADO: score_cristal >= -3.0 kcal/mol, que no sale de mirar estos datos sino de la lectura ya sellada de MF-13, que nombro -1.631 (1fkh) y -2.181 (1ew8) como sistemas mal montados. PRIMARIO: f = fraccion de los ABSURDOS que se normalizan -bajan de -3.0- al quitar solo las aguas que chocan. TRES LECTURAS ESCRITAS ANTES: (1) f>=0.70 Y delta mediano en los NO absurdos < 0.5 => LAS AGUAS BLOQUEAN, conservarlas todas es defecto de produccion y la politica hay que cambiarla, no solo declararla; (2) f<=0.30 => LAS AGUAS NO SON LA EXPLICACION, hay que buscar en cofactores no metalicos o protonacion; (3) intermedio, o f>=0.70 con delta de control >=0.5 => MIXTO, porque si quitar aguas mejora a todos por igual el efecto es global y no explica el absurdo. EL CONTROL DE LOS NO ABSURDOS ESTA EN LA REGLA A PROPOSITO: sin el, cualquier mejora se leeria como confirmacion. PROHIBIDO: mover d_clash o el umbral de -3.0 despues de ver los resultados; leer esto como que la respuesta sea quitar todas las aguas, porque el criterio es puramente geometrico y no distingue agua desplazable de agua estructural.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `9e385a7f2cef002fb1ca16352534966841a1d116`, dirty=True

## Estado

- Creado: 2026-08-20T20:39:12.307935+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-20T20:39:13.755805+00:00)
- Finalizado: 2026-08-20T20:39:14.037780+00:00
- Razón de la decisión: Prerregistro sellado ANTES de ejecutar, con el hash del script. La hipotesis se invierte respecto a lo que MF-13 supuso: aquel apunto a que FALTASE un cofactor, un metal o un agua estructural, pero REC-08-EXT ya midio que la preparacion no pierde nada -42 de 42 metales del sitio y 1788 de 1788 aguas conservadas-. Si no falta nada, sobra: 1ew8 conserva 511 atomos de agua en su rec.pdbqt y es justo el que MF-29-EMP-COR vio cruzar a +1.714 preparado flexible. Los dos parametros que podrian ajustarse a conveniencia estan fijados de fuentes anteriores e independientes: d_clash=2.6 A viene del prerregistro de MF-28 y el umbral de -3.0 de la lectura sellada de MF-13. El control de los no absurdos entra en la regla de lectura, no como analisis posterior, precisamente para que una mejora global no se pueda leer como confirmacion. Se declara ademas que esto NO decide la politica de aguas por si solo -falta el efecto sobre docking de novo- y que su lectura maxima es que la politica hay que decidirla, no que la respuesta sea quitarlas todas.
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
