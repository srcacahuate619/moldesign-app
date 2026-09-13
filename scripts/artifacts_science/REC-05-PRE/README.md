# REC-05-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Los metales del receptor son necesarios para colocar el ligando en de novo, y no un detalle de preparacion. Si lo son, quitarlos debe destruir la cobertura del oraculo en los complejos que los tienen. Es la hipotesis simetrica a la de REC-11 sobre las aguas, y sobre la unica de las tres clases del REC-05 original que admite medicion.

## Protocolo

Referencia: `Intervencion pareada, una sola variable: el receptor. Protocolo IDENTICO al de REC-11 POR CONSTRUCCION y no por copia: scripts/run_rec05_metales_denovo.py IMPORTA scripts/run_rec11_aguas_denovo.py -sellado como asset de REC-11- y reutiliza su funcion _brazo y sus constantes BOX=25.0, EXH=8, NUM_MODES=9, SEMILLAS={42,1,2,3,4}, UMBRAL_A=2.0 y LIGANDO=conf0.flex.pdbqt. El conjunto METALES se importa del modulo sellado de REC-12. Es el patron que exige el docs/49 seccion 17. COHORTE: derivada de artefactos sellados y no escrita a mano; los complejos de los 116 de MF-13 que REC-08-EXT marca con metales_sitio>0. Son 29. BRAZO CON: rec.pdbqt tal cual. BRAZO SIN: el mismo receptor sin ningun residuo cuyo nombre este en METALES. Se quitan TODOS los metales del receptor y no solo los del sitio, por la misma razon que REC-11 quito todas las aguas: en de novo no hay pose de referencia con la que decidir cual estorba. Consecuencia declarada: en algunos complejos se retiran especies que REC-08-EXT no contaba por estar fuera de los 8 A -HG en la serie 1bn/1cn, MN en 1ax0, CA en 1g3d/1g3e-. Verificado antes de sellar: los 29 pierden entre 1 y 18 atomos, 96 en total, y ninguno se queda a cero. El ligando es identico en los dos brazos, asi que la penalizacion torsional se cancela -leccion de MF-29-EMP-COR aplicada por diseno-. Contenedor moldesign-lab del servidor.`

## Gate

RE-ALCANCE DECLARADO ANTES DE CORRER, y esta es la parte que no se puede escribir despues. El REC-05 del docs/49 pedia ablacion en TRES clases con un gate de 'reglas por familia con evidencia'. Dos clases quedan fuera y el gate por familia NO ES ALCANZABLE: (a) AGUAS fuera, porque el prerregistro de REC-11 condicionaba abrir politicas intermedias a que saliera QUITARLAS MEJORA y salio SIN_DIFERENCIA_DETECTABLE; (b) COFACTORES fuera por falta de n, porque REC-12-R1 midio que el nucleo robusto son DOS complejos, 1gwv con UDP y 1lbk con GSH; (c) METALES dentro pero AGRUPADOS. PRIMARIA: cobertura del oraculo pareada sobre los 29, con b = complejos donde SIN cubre y CON no, y c = donde CON cubre y SIN no. McNemar exacto bilateral de estadistica_fnd04. TRES LECTURAS ESCRITAS ANTES: (1) p<0.05 con c>b => CONSERVARLOS_ES_NECESARIO, y la preparacion queda validada positivamente en esta clase, que hoy no lo esta -REC-08-EXT midio que se conservan 42 de 42, no que haga falta-; (2) p<0.05 con b>c => QUITARLOS_MEJORA, resultado sorprendente que exigiria replica antes de cualquier uso; (3) p>=0.05 => SIN_DIFERENCIA_DETECTABLE, sin leerlo como equivalencia. EFECTO MINIMO DETECTABLE DECLARADO ANTES: con n=29 y discordancia del 20% el MDE pareado es de 20.6 puntos porcentuales, unos 6 complejos netos; y con c=0 el McNemar exacto exige b>=6 para p<0.05. Diferencias menores NO son resolubles con esta cohorte y se reportaran como no concluyentes, nunca como tendencia -leccion de RS-14-. SECUNDARIO descriptivo y SIN gate: la misma tabla restringida a ZN, n=21, que es la UNICA familia con algo de potencia. DECLARADO NO LEIBLE: CA con n=7, MG con n=3, MN con n=3 y CU con n=2 no admiten lectura de familia y no se reportara ninguna, ni siquiera descriptiva. Esa es la razon de que el gate original de REC-05 se sustituya en vez de intentarse. PROHIBIDO: leer SIN_DIFERENCIA_DETECTABLE como equivalencia; emitir una regla por familia para CA, MG, MN o CU; leer esto como medicion de cobertura alcanzable, porque usa UN SOLO conformero igual que REC-11; y extender la lectura a los 87 complejos sin metal, sobre los que este experimento no dice nada.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `codex/mejora-producto`, commit `7a16fb14ea49a2182aba1ad3ce7b557e8d0400ab`, dirty=True

## Estado

- Creado: 2026-08-23T01:24:12.234199+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-23T01:24:14.256932+00:00)
- Finalizado: 2026-08-23T01:24:14.900960+00:00
- Razón de la decisión: Prerregistro sellado ANTES de ejecutar, con el hash del runner nuevo y el de los dos modulos sellados que reutiliza. Lo que hace falta declarar antes y no despues no es el gate sino el RE-ALCANCE: el REC-05 del docs/49 pedia tres clases y una regla por familia, y ninguna de las dos cosas es alcanzable. Aguas quedan fuera porque REC-11 no lo autorizo -su rama QUITARLAS MEJORA era la que abria las politicas intermedias, y salio SIN_DIFERENCIA_DETECTABLE-. Cofactores quedan fuera porque REC-12-R1 acaba de medir que el nucleo robusto son dos complejos. Y la regla por familia no se puede emitir con CA=7, MG=3, MN=3 y CU=2: solo ZN llega a 21 y aun asi es secundario descriptivo. El MDE se calcula ANTES con la biblioteca de FND-04 y se declara en dos formas -20.6 puntos porcentuales con discordancia del 20%, y b>=6 con c=0- para que ninguna diferencia pequena se pueda leer despues como tendencia; es la leccion explicita de RS-14 y el mismo trato que recibio REC-11. Se declara ademas una decision de implementacion que costo un bug y que quedo verificada antes de sellar: los metales se identifican SOLO por nombre de residuo. Probar tambien con el nombre de atomo y el campo de tipo del PDBQT retiraba entre 200 y 3900 atomos por complejo -la proteina entera-, porque `CA` es el carbono alfa de todo residuo y `NA` es el tipo AutoDock del nitrogeno aceptor. Con el criterio final los 29 complejos pierden entre 1 y 18 atomos, 96 en total, y ninguno se queda a cero.
- Hashes de dataset: 2 archivo(s) con SHA-256
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
