# REC-11-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Conservar todas las aguas del receptor -la politica declarada en docs/51- cambia el resultado del docking de novo. Puede BLOQUEAR la cuenca nativa, como REC-09 vio sobre el scoring del cristal, o puede GUIAR, si un agua estructural que media un puente de hidrogeno es parte del sitio y quitarla deja un bolsillo que no existe. Ninguna de las dos cosas esta medida hoy.

## Protocolo

Referencia: `Intervencion pareada, una sola variable. Cohorte: los 116 de train. Ligando conf0.flex.pdbqt FIJO y el mismo en los dos brazos, misma caja de 25 A, exhaustiveness=8, num_modes=9 y las mismas cinco semillas {42,1,2,3,4} del brazo de produccion de MF-29-EMP. Brazo CON: rec.pdbqt tal cual, la politica actual. Brazo SIN: el mismo receptor sin ningun residuo de agua (HOH/WAT/DOD), la politica alternativa. LO UNICO QUE CAMBIA ES EL RECEPTOR; el ligando es identico, asi que la penalizacion torsional se cancela en toda comparacion -leccion de MF-29-EMP-COR aplicada por diseno-. Se quitan TODAS las aguas y no solo las que chocarian, porque en produccion no existe una pose de referencia con la que decidir cuales estorban: esa asimetria es lo que hace que esto no sea REC-09 otra vez. Se mide por brazo el ORACULO -mejor rmsd_pose_pocket entre las poses de las cinco semillas- y el TOP-1 -rmsd de la pose de mejor score-. Contenedor moldesign-lab del servidor. Script: scripts/run_rec11_aguas_denovo.py.`

## Gate

PRIMARIA: cobertura del oraculo pareada sobre los 116, con b = complejos donde SIN cubre y CON no, y c = donde CON cubre y SIN no. McNemar exacto bilateral de estadistica_fnd04. TRES LECTURAS ESCRITAS ANTES: (1) p<0.05 con b>c => QUITARLAS MEJORA, la politica de docs/51 cambia y el coste de regenerar queda justificado; (2) p<0.05 con c>b => CONSERVARLAS MEJORA, y la politica queda confirmada POSITIVAMENTE, que hoy no lo esta -hoy solo esta declarada-; (3) p>=0.05 => SIN DIFERENCIA DETECTABLE, la politica se mantiene por inercia y se declara el limite de potencia, sin leerlo como equivalencia. EFECTO MINIMO DETECTABLE DECLARADO ANTES (seccion 20.9): si c=0, McNemar exacto exige b>=6 para p<0.05 (2*0.5^6=0.031); con discordancia realista del 20% el MDE pareado con n=116 es de 11.3 puntos porcentuales, unos 13 complejos netos, y con discordancia del 10% baja a 8.0 puntos. Diferencias menores NO son resolubles con esta cohorte y se reportaran como no concluyentes, nunca como tendencia -leccion de RS-14, que descubrio su limite de resolucion despues de ejecutar-. SECUNDARIO descriptivo y sin gate: la misma tabla sobre el top-1, que es lo que produccion entrega pero es mas ruidoso. PROHIBIDO: leer SIN_DIFERENCIA_DETECTABLE como equivalencia; adoptar el brazo SIN si sale QUITARLAS MEJORA, porque lo que eso autoriza es abrir la comparacion contra politicas intermedias -filtrar por B-factor, ocupancia o enterramiento- que aqui no se evaluan; leer esto como medicion de cobertura alcanzable, porque usa UN SOLO conformero y MF-33 midio que conf0.flex solo convierte 12 de 33 contra 26 del ensemble.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `f4728ae7fb7cada83af63136d81bc829716e9611`, dirty=True

## Estado

- Creado: 2026-08-20T22:28:37.524467+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-20T22:28:38.249306+00:00)
- Finalizado: 2026-08-20T22:28:38.458314+00:00
- Razón de la decisión: Prerregistro sellado ANTES de ejecutar, con el hash del script. Es el experimento que docs/51_POLITICA_DE_AGUAS.md nombro como lo unico que cambiaria la politica, y existe porque REC-09 midio la pregunta equivocada para decidirla: midio el efecto de las aguas sobre el scoring del CRISTAL, y la politica gobierna el docking DE NOVO. La diferencia no es formal. En de novo el buscador explora todo el sitio y choca con aguas que el cristal ni toca, y ademas no dispone de la pose de referencia que REC-09 uso para decidir cuales aguas estorbaban; por eso aqui se quitan TODAS. Se declara desde el principio que la hipotesis es bidireccional -las aguas pueden bloquear la cuenca nativa o pueden guiar, si son estructurales y parte del sitio- y las tres lecturas incluyen una que CONFIRMA la politica actual, que es algo que hoy no esta medido: docs/51 la declara, no la valida. El MDE se calcula antes con la biblioteca de FND-04 y se declara en dos formas -b>=6 con c=0, y 11.3 puntos porcentuales con discordancia del 20%- para que ninguna diferencia pequena se pueda leer despues como tendencia; es la leccion explicita de RS-14. Y se prohibe de antemano el error mas probable de interpretacion: que un QUITARLAS MEJORA se lea como permiso para adoptar el brazo SIN, cuando lo que autoriza es comparar contra politicas intermedias que este diseno no evalua.
- Hashes de dataset: 2 archivo(s) con SHA-256
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
