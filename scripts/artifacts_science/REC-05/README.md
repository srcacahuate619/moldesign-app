# REC-05

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Los metales del receptor son necesarios para colocar el ligando en de novo, y no un detalle de preparacion. Si lo son, quitarlos debe destruir la cobertura del oraculo en los complejos que los tienen. Es la hipotesis simetrica a la de REC-11 sobre las aguas, y sobre la unica de las tres clases del REC-05 original que admite medicion.

## Protocolo

Referencia: `Ver prerregistro sellado REC-05-PRE, anterior a esta corrida y con el hash de los tres scripts. Intervencion pareada, una sola variable: el receptor. Protocolo IDENTICO al de REC-11 POR CONSTRUCCION y no por copia: scripts/run_rec05_metales_denovo.py IMPORTA scripts/run_rec11_aguas_denovo.py -sellado como asset de REC-11- y reutiliza su funcion _brazo y sus constantes BOX=25.0, EXH=8, NUM_MODES=9, SEMILLAS={42,1,2,3,4}, UMBRAL_A=2.0 y LIGANDO=conf0.flex.pdbqt. El conjunto METALES se importa del modulo sellado de REC-12. Es el patron que exige el docs/49 seccion 17. COHORTE: derivada de artefactos sellados y no escrita a mano; los complejos de los 116 de MF-13 que REC-08-EXT marca con metales_sitio>0. Son 29. BRAZO CON: rec.pdbqt tal cual. BRAZO SIN: el mismo receptor sin ningun residuo cuyo nombre este en METALES. Se quitan TODOS los metales del receptor y no solo los del sitio, por la misma razon que REC-11 quito todas las aguas: en de novo no hay pose de referencia con la que decidir cual estorba. Consecuencia declarada: en algunos complejos se retiran especies que REC-08-EXT no contaba por estar fuera de los 8 A -HG en la serie 1bn/1cn, MN en 1ax0, CA en 1g3d/1g3e-. Verificado antes de sellar: los 29 pierden entre 1 y 18 atomos, 96 en total, y ninguno se queda a cero. El ligando es identico en los dos brazos, asi que la penalizacion torsional se cancela -leccion de MF-29-EMP-COR aplicada por diseno-. Contenedor moldesign-lab del servidor.`

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

- Creado: 2026-08-23T05:14:17.224480+00:00
- Status: finished
- Decisión: INCONCLUSIVE
- Sellado: sí (2026-08-23T05:14:18.063812+00:00)
- Finalizado: 2026-08-23T05:14:18.219570+00:00
- Razón de la decisión: Cohorte completa: los 29 complejos de los 116 que REC-08-EXT marca con metal en el sitio, n_ok 29 de 29, cero fallos. Se retiraron 96 atomos de metal en total, entre 1 y 18 por complejo, y ninguno se quedo a cero. CANTIDAD PRIMARIA: cobertura del oraculo pareada. CON metales 24 de 29 = 0.8276; SIN metales 25 de 29 = 0.8621. Discordantes 3 de 29 = 0.1034, con b -gana SIN- = 2 y c -gana CON- = 1. McNemar exacto bilateral p = 1.0. Cae en la rama (3) de las tres lecturas escritas antes: SIN_DIFERENCIA_DETECTABLE. INCONCLUSIVE y no GO por el mismo criterio con que se sellaron REC-11, REC-09 y MF-13: esa rama es la que el gate reserva para 'no se distingue', el prerregistro PROHIBE leerla como equivalencia, y obliga a declarar el limite de potencia. MDE OBSERVADO 14.84 pp, MEJOR que los 20.6 pp declarados antes de correr, porque la discordancia real -10.3%- salio por debajo del 20% supuesto al calcularlo. El diseno sigue sin resolver diferencias menores a unos 15 puntos porcentuales, unos 4 complejos netos sobre 29. SECUNDARIO DESCRIPTIVO, la unica familia con n: ZN sobre 21 complejos da CON 16, SIN 17, b=2, c=1, p=1.0 y MDE 19.72 pp. Apunta igual que el agrupado y tampoco resuelve nada. Las familias CA -7-, MG -3-, MN -3- y CU -2- se declararon NO LEIBLES antes de correr y no se reporta ninguna regla para ellas, que era la razon de re-alcanzar el REC-05 original en vez de intentar su gate por familia. LOS DOS DISCORDANTES, nominalmente: 1mmq -CON 1.134, SIN 2.083, gana CON- y 1mmr -CON 4.018, SIN 1.071, gana SIN-. 1mmr ya figuraba entre los 10 que REC-11 rescato al quitar las AGUAS; que tambien mejore al quitar los metales sugiere que ese complejo se beneficia de vaciar el receptor por razones que este diseno no identifica. Es UN caso y no se generaliza. CONSECUENCIA DE PRODUCTO, declarada aqui porque no era el proposito del experimento y conviene que no se sobreinterprete: la preparacion del producto -preparer.py- elimina hoy el 100% de los metales de los 387 targets del catalogo, porque su puerta de conservacion depende de un cofactors_whitelist vacio. REC-05 mide que, sobre estos 29 y con un solo conformero, eso NO ES DETECTABLEMENTE DANINO. NO dice que sea inocuo: con MDE de 14.84 pp, un dano de hasta cuatro complejos netos seria invisible para este diseno. LIMITES: un solo conformero, igual que REC-11, asi que mide el efecto a conformero igualado y no la cobertura alcanzable; se quitaron TODOS los metales del receptor y no solo los del sitio, lo que en algunos complejos retiro especies que REC-08-EXT no contaba por estar fuera de los 8 A; no dice nada de los 87 complejos sin metal; y no toca ningun artefacto sellado ni cambia ningun receptor. Ejecutado en el contenedor moldesign-lab del servidor. Artefactos descargados con sha256 verificado contra el remoto, y los tres scripts coinciden con lo sellado en REC-05-PRE en local y en el servidor.
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
