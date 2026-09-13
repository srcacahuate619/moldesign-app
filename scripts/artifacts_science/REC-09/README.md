# REC-09

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Los cristales que puntuan absurdamente mal no son sistemas a los que les FALTA algo sino a los que les SOBRA: el pipeline conserva todas las aguas -politica que nadie declaro, hallazgo abierto de REC-08-EXT- incluidas las que el ligando desplaza, y un agua que ocupa el sitio choca con el cristal y dispara el termino de repulsion.

## Protocolo

Referencia: `Ver prerregistro sellado REC-09-PRE, anterior a esta corrida. Sin recomputar ningun docking. Por complejo: contar aguas del receptor con algun atomo a <= d_clash=2.6 A de un atomo pesado del ligando cristalografico -mismo d_clash que MF-28 declaro antes de correr-; score_only del cristal contra rec.pdbqt; score_only contra el mismo receptor sin esas aguas y solo esas; delta = con - sin. Cristal preparado RIGIDO, identico a MF-13, caja 25 A, semilla 42. Los dos scores de cada pareja salen del MISMO PDBQT de ligando, asi que la penalizacion torsional se cancela en el delta. Contenedor moldesign-lab del servidor, 116 complejos, 233 s.`

## Gate

G1 de validez antes del primario: score_con_aguas reproduce el score_cristal de MF-13 dentro de 0.10 en >=95%. Umbral de absurdo declarado antes: score >= -3.0, de la lectura sellada de MF-13. PRIMARIO: f = fraccion de los ABSURDOS que bajan de -3.0 al quitar solo las aguas que chocan. f>=0.70 con delta de control <0.5 => LAS AGUAS BLOQUEAN; f<=0.30 => NO SON LA EXPLICACION; intermedio => MIXTO.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `9e385a7f2cef002fb1ca16352534966841a1d116`, dirty=True

## Estado

- Creado: 2026-08-20T20:44:55.835510+00:00
- Status: finished
- Decisión: INCONCLUSIVE
- Sellado: sí (2026-08-20T20:44:58.213020+00:00)
- Finalizado: 2026-08-20T20:45:21.558362+00:00
- Razón de la decisión: Lectura MIXTO por la regla preregistrada, y por tres centesimas: f = 2 de 6 = 0.3333, justo por encima del corte de 0.30 que habria dado LAS AGUAS NO SON LA EXPLICACION. El prerregistro prohibe mover el umbral tras ver la fraccion, asi que queda MIXTO y la decision es INCONCLUSIVE respecto a la pregunta binaria -la misma situacion que dejo a MF-13 en MIXTO tres milesimas por debajo de su corte-. G1 pasa perfecto: score_con_aguas reproduce el score_cristal de MF-13 en 116 de 116 dentro de 0.10 kcal/mol, asi que se esta puntuando exactamente lo mismo. EL MECANISMO ES REAL Y ENORME DONDE APLICA, y eso es lo que vale aunque el gate salga MIXTO. 1fkh -el complejo insignia que MF-13 nombro como sistema mal montado, con -1.631- pasa de +2.550 a -10.369 al quitar DOS moleculas de agua: 12.919 kcal/mol de artefacto producidos por dos aguas que el pipeline conservo y el ligando desplaza. 1eld pasa de -0.610 a -4.093 y tambien normaliza. Los otros cuatro absurdos no: 1afl y 1ew8 tienen aguas bloqueantes pero de efecto pequeno -0.426 y 0.324-, y 1d7i y 1ew9 NO TIENEN NINGUNA, de modo que su absurdo tiene otra causa y este experimento la descarta explicitamente. EL CONTROL SALE LIMPIO, que era la mitad del diseno: entre los 110 no absurdos el delta mediano es 0.000, es decir, quitar las aguas bloqueantes no mejora a los sanos y la mejora de 1fkh no es un efecto global disfrazado. Pero el maximo de ese control es 4.008 y 11 de los 110 se mueven mas de 0.5 kcal/mol, lo que dice que el problema NO se limita a los seis raros. ALCANCE MEDIDO: 26 de 116 complejos tienen al menos un agua bloqueante. CONSECUENCIA PARA LA POLITICA DE AGUAS, que era la razon de correrlo: conservarlas todas tiene consecuencia demostrada y cuantificada sobre la funcion de puntuacion, no es una decision inocua. Queda establecido que la politica hay que DECIDIRLA; NO queda establecido que la respuesta sea quitarlas todas, y el prerregistro lo prohibe expresamente, porque el criterio es puramente geometrico y no distingue un agua desplazable de una estructural que media un puente de hidrogeno. LO QUE ABRE: 1d7i y 1ew9 puntuan absurdo con cero aguas bloqueantes; la siguiente hipotesis son los cofactores no metalicos -HETATM que no son ni agua ni metal, que nadie ha inventariado- o la protonacion. LIMITES: no decide la politica por si solo porque no mide el efecto sobre docking de novo, que es donde una pose explora el sitio y choca con aguas que el cristal no toca; no relee MF-13, cuyo ~30% de puntuacion incluye complejos que no son absurdos.
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
