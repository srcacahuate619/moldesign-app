# MF-29-EMP

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Separar BUSQUEDA de OBJETIVO en el regimen de <=6 torsiones: si un presupuesto 64x no encuentra scores mejores, la busqueda alcanza practicamente el minimo de la funcion de Vina y el fallo es de la funcion (OBJETIVO); si los encuentra, el fallo es del buscador (BUSQUEDA). Es una cota superior EMPIRICA del minimo global, NO un certificado: por eso MF-29-EMP y no MF-29, que sigue ABIERTO.

## Protocolo

Referencia: `Prerregistro en el docstring de scripts/run_mf29emp_optimo_global.py. Contenedor moldesign-lab en el servidor local (4 nucleos, 4 workers). Cohorte de 50 complejos con TORSDOF<=6 en el propio PDBQT -la dimension que Vina busca, no el conteo de RDKit-. Ligando conf0.flex.pdbqt flexible, fijo y el mismo en los dos brazos, con su propio receptor y caja de 25 A y num_modes 9. Brazo produccion exh=8 semillas {42,1,2,3,4}; brazo masivo exh=512 semillas {42,7,13}. Se registra el mejor score de cada corrida y, como contexto, el mejor rmsd_pose_pocket. Sustituye a la jerarquia de Lasserre de la seccion 20.11(b) del doc. 49, declarada NO IMPLEMENTABLE en este hardware antes de correr.`

## Gate

Cantidad primaria: fraccion de complejos donde min(score exh=512) < min(score exh=8) - 0.10 kcal/mol, con 0.10 declarado antes como ruido numerico. Lectura preregistrada: >=0.30 BUSQUEDA, <0.10 OBJETIVO, intermedio MIXTO. Testigo declarado antes de correr: el cristal relajado localmente por MF-13 es cota superior independiente; si puntua mejor que el brazo masivo, la busqueda no llego al fondo. El estrato COLOCACION aporta n pequeno: comparacion pareada, nunca mediana por estrato.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `83079e9e5f67e1e912037345395e458cb6f91039`, dirty=True

## Estado

- Creado: 2026-08-20T19:15:01.107365+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-20T19:18:44.230882+00:00)
- Finalizado: 2026-08-20T19:41:08.222561+00:00
- Razón de la decisión: DECISION ENMENDADA EL 2026-08-20 tras MF-29-EMP-COR, que se prerregistro y sello ANTES de correr y cuya regla autoriza este cambio. La decision anterior fue INCONCLUSIVE porque dos instrumentos preregistrados apuntaban en direcciones opuestas: la cantidad primaria leia OBJETIVO (3 de 48 = 0.0625) y el testigo de MF-13 leia fallo de busqueda (34 de 48 = 70.8%). MF-29-EMP-COR midio que el testigo NO ERA UN INSTRUMENTO VALIDO: MF-13 puntuo el cristal como PDBQT RIGIDO con TORSDOF 0 y MF-29-EMP dockeo conf0.flex.pdbqt con hasta 6 torsiones, y Vina divide la afinidad por (1 + w_rot * N_rot), de modo que el rigido puntua mejor PARA LA MISMA POSE. Preparando el mismo cristal como flexible -unico cambio, mismo receptor, caja, semilla y binario- el salto de escala es de 1.055 kcal/mol medianos, que cubre de sobra el deficit de 0.491 que el testigo leia; el deficit corregido se invierte a -0.406 y el brazo masivo puntua MEJOR que el cristal relajado en 36 de 48, quedando solo 4 con ventaja para el cristal (f=0.0833, banda ARTEFACTO DE ESCALA <=0.30). Sus dos gates de validez pasaron antes del primario: G1=1.0 de coincidencia de TORSDOF y G2=0.3425 A de deriva, casi identica a los 0.322 A del rigido en MF-13. No se movio ningun umbral y no se eligio instrumento despues de ver el resultado: se midio que uno de los dos no medía lo que decia medir, y se retiro. La cantidad primaria queda sola y su lectura preregistrada OBJETIVO se sostiene: en el regimen de <=6 torsiones, 64x de presupuesto no encuentra scores mejores, y ahora ademas consta que lo que encuentra iguala o supera el valor del cristal relajado a igual escala. MAS BUSQUEDA DEL MISMO TIPO NO RINDE: el brazo masivo costo 83.3 h de CPU contra 4.1 h -20x el tiempo- para mover tres complejos (1d7i +0.282, 1m2x +0.238, 1bn1 +0.125), ninguno por encima de un tercio de kcal/mol, con 45 de 48 dentro del ruido de 0.10 y 19 en que el masivo salio peor sin pasar de 0.05; la sd entre semillas bajo de 0.013 a 0.009 medianos, que es la saturacion que daba sentido a la cota. QUEDA ANULADO el confusor del confórmero que esta lectura habia declarado: no hace falta comprobarlo porque el deficit que se le iba a atribuir no existe. LO QUE SIGUE SIN AUTORIZAR: esto NO es el certificado de MF-29, que sigue ABIERTO -la jerarquia de Lasserre se declaro NO IMPLEMENTABLE en este hardware antes de correr y una cota empirica no certifica-; el estrato COLOCACION aporta n=7 y se reporta pareado, no por mediana; nada extrapola fuera del regimen de <=6 torsiones. LIMITE de cobertura: n=48 y no 50 porque 1mmr y 1nm6 aparecen como VINA_FALLO en las 3 semillas del brazo masivo y NO son fallos sino plazos vencidos -43200.4 y 43200.6 s, tres veces el timeout de 14400 s en duro-, documentados en failures.jsonl y recuperables por ~12 h de servidor sin efecto en la lectura salvo empate improbable.
- Hashes de dataset: 1 archivo(s) con SHA-256
- Hashes de assets: 3 archivo(s) con SHA-256

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
