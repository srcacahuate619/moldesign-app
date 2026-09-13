# MF-33-B-RET-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La ventaja del ensemble flexible que MF-33 y MF-33-A3 midieron sobre la COBERTURA DEL ORACULO llega tambien a lo que el usuario recibe -el top-1 por score-. Si no llega, la diversidad conformacional resuelve el cuello de generacion y lo desplaza al selector, que es una conclusion distinta y reencuadra el paper.

## Protocolo

Referencia: `Repite el brazo B de MF-33 cambiando UNA SOLA COSA: registra (score, rmsd_pose_pocket) de cada pose en vez de tirarlas. Cohorte: los 48 de MF-33, la del paper. Todos los conf*.flex.pdbqt con los parametros del brazo de control de MF-28 -de donde MF-33 reuso su brazo B-: exhaustiveness=8, num_modes=9, seed=42, caja 25 A, --cpu 1. Brazos pareados SINGLE (las 9 poses de conf0.flex) y ENSEMBLE (las Kx9 de todos). Se anade pb_valid_fisica de posebusters_metrica sobre el top-1 de cada brazo. Corre en la maquina LOCAL porque posebusters no esta en la imagen moldesign-lab. Coste ~42.6 CPU-h medidos del consumo real del brazo B, unas 4.5 h con 10 workers. NO se re-corre sobre los 116: MF-33-EXT ya lo hace para la cobertura y duplicarlo gastaria 103 CPU-h para una pregunta que se contesta con 42.6 sobre la cohorte del paper. Script: scripts/run_mf33bret_top1_flexible.py.`

## Gate

G1 DE CORDURA ANTES DEL PRIMARIO: el oraculo del brazo ENSEMBLE debe reproducir el rmsd_min del brazo B sellado en MF-33 dentro de 0.001 A en >=95% de los complejos. Mismo protocolo, misma semilla, mismo binario: si no reproduce, algo cambio y NADA de lo que sigue se lee. Es la unica forma de saber que este re-run es el mismo experimento y no uno parecido. PRIMARIO: McNemar exacto pareado sobre acierta <=2 A, por separado en top1, top5 y oraculo. TRES LECTURAS ESCRITAS ANTES: (1) LA VENTAJA LLEGA AL USUARIO si el ensemble mejora oraculo Y top1 con p<0.05, y entonces el claim del paper pasa de mejoramos el pool a mejoramos la entrega; (2) EL CUELLO SE DESPLAZA A LA SELECCION si mejora oraculo y NO top1, y entonces la diversidad resuelve el cuello de generacion y lo traslada al selector -este desenlace NO debilita el paper, lo reencuadra, y conecta con la cartera RS y con MF-09-; (3) SIN EFECTO EN LA ENTREGA si no mejora ninguno, y habria que decirlo tal cual. Se reporta ademas el margen de seleccion: complejos con pose buena disponible que el brazo no entrega. PROHIBIDO: ordenar por otra cosa que el score de Vina -el rescoring es cartera RS y meterlo aqui confundiria generacion, seleccion y funcion de puntuacion en un numero-; elegir conf0 por calidad en vez de por indice; reabrir MF-33 o MF-33-A3, cuyas cantidades son de oraculo y siguen como estan.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `5c2cd20ce810fb43f520947c13faa2189896e041`, dirty=True

## Estado

- Creado: 2026-08-21T04:26:26.245865+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-21T04:26:27.863177+00:00)
- Finalizado: 2026-08-21T04:26:28.640348+00:00
- Razón de la decisión: Prerregistro sellado con el hash del script ANTES de correr, y antes incluso de que la maquina este libre. Existe porque el paper de MF-33 tiene una amenaza a la validez que un revisor ataca primero y que hoy no esta medida sobre el brazo que el paper defiende: la metrica es de ORACULO y no de RESULTADO. MF-09 midio top-1 acierta 0/33 y top-20 2/33 en el estrato dificil, asi que subir el techo de 1/33 a 26/33 podria no mover nada de lo que el usuario recibe. No se puede medir con lo que hay: run_mf28_roadmap.py escribio las poses del brazo B en un TemporaryDirectory y se borraron al terminar; MF-33-TOP1 da el precedente en el protocolo RIGIDO, cuyas poses si sobrevivieron, pero ese no es el brazo del paper. DOS DECISIONES QUE SE TOMAN AQUI. PRIMERA, el G1 de cordura: exigir que el oraculo del ENSEMBLE reproduzca el brazo B sellado dentro de 0.001 A. Es identico protocolo, semilla y binario, asi que debe reproducir exactamente; si no lo hace, este re-run no es el mismo experimento y leerlo seria comparar dos cosas distintas. Ningun otro experimento del programa ha tenido que reproducirse a si mismo y conviene que este lo demuestre. SEGUNDA, y es la que evita el sesgo: se declara de antemano que el desenlace (2) -el cuello se desplaza a la seleccion- NO debilita el paper sino que lo reencuadra. Sin esa declaracion previa, la tentacion al ver un top-1 plano seria enterrar la medicion o presentarla como limitacion menor, cuando en realidad seria el hallazgo mas interesante: la diversidad conformacional resolviendo el cuello de generacion y trasladandolo al selector, que es exactamente donde vive la cartera RS. Se declara ademas que no se re-corre sobre los 116 aunque MF-33-EXT lo este haciendo: duplicarlo costaria 103 CPU-h para contestar con menos precision una pregunta que la cohorte del paper contesta con 42.6.
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
