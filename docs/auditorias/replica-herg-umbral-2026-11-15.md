# Réplica al informe «Umbral de alerta de hERG en MolDesign»

15 de noviembre de 2026. Responde a [`herg-umbral-2026-11-15/README.md`](herg-umbral-2026-11-15/README.md) (base de producto `ffddd7e9`). No modifica esa carpeta: sus archivos son del investigador y esta réplica vive al lado.

## Veredicto

**La decisión operativa se acepta: conservar «score de Vina < −7,0 kcal/mol» para la alerta exploratoria de hERG.** Lo que no se acepta es la razón con que el informe la sostiene. «Endurecerlo a −7,5 perdería cuatro bloqueadores» presenta como medido un efecto que el piloto no distingue del ruido. La razón defendible es otra y más modesta: **no hay evidencia para cambiarlo**, y en un aviso de seguridad omitir un bloqueador cuesta más que una alerta de más (un juicio de coste, no una medida).

Además, tres limitaciones del propio piloto no están en el informe (R1, R3 y R4) y dos textos de la interfaz que el informe señala merecen cambio, pero ambos son texto visible para el usuario y esperan la aprobación del propietario (R6 y R7). No he implementado nada.

## Qué comprobé y cómo

| Afirmación del informe | Estado | Cómo |
|---|---|---|
| Recuentos del piloto: 7/10 y 3/10 bloqueadores, 3/6 y 2/6 controles; IC 95 % de Wilson; ρ = 0,39 (p = 0,19, n = 13) | **Reproducido** | Releídos de `resultados.json` y recalculados con la biblioteca estándar. |
| Rouen: 31/31, 1/22 y 2/22; sólo cambia diltiazem (−7,381) | **Reproducido** | CSV de la revisión fija `f85243eb…`, descargado a una carpeta aparte; su SHA-256 es `9d0cd23c…d537c`, el registrado. |
| El −7,0 de la alerta y el −7,5 del normalizador son parámetros distintos | **Confirmado en el código** | `selectivity.py` (panel, líneas 68–90 y 157), `scoring/normalizer.py` y `pro_features.py`. No volví a ejecutar las 23 pruebas ni la sonda de contrato. |
| Creanza −6,012 y −8,967 (Glide); Kramer 0,77 y 0,93 | **Confirmado**, con matices (R5) | Páginas leídas por un agente de lectura web. |
| Los 16 IC₅₀ de Yao et al. | **Confirmado** | Contrastados con la tabla 2. |
| Redondeo: «−7.0 < umbral −7.0» con −7,004 | **Confirmado** | `selectivity.py:141` y `ProSelectivityPanel.tsx:469-470` formatean con un decimal. |
| Página del artículo de Rouen et al. (*Biophys. J.*) | **No verificado** | La página no se pudo leer; no sé qué receptor ni qué caja hay detrás de cada columna de Vina. |

## R1. El ruido de semilla es del tamaño de la diferencia entre cortes

Los dos cortes están separados por 0,5 kcal/mol. Entre las ocho moléculas que se repitieron con la semilla 43, el score se movió:

| Compuesto | Semilla 42 | Semilla 43 | \|Δ\| |
|---|---:|---:|---:|
| amiodarona | −6,834 | −6,294 | **0,540** |
| verapamilo | −7,196 | −6,745 | **0,451** |
| tamoxifeno | −7,142 | −7,004 | 0,138 |
| haloperidol | −7,171 | −7,306 | 0,135 |
| cisaprida | −7,152 | −7,226 | 0,074 |
| amoxicilina | −7,394 | −7,435 | 0,041 |
| quinidina | −6,965 | −6,970 | 0,005 |
| esparfloxacino | −7,621 | −7,623 | 0,002 |

Dos de ocho se mueven prácticamente lo que separa a los cortes. Y el propio producto declara una dispersión de Vina de **2,0 kcal/mol** (`INCERTIDUMBRE_VINA_KCAL`, [`selectividadMargen.ts:43`](../../frontend/lib/selectividadMargen.ts)), cuatro veces la diferencia que se discute.

Consecuencias que el informe no saca:

- Con la semilla 43 donde existe y la 42 en el resto, la alerta de −7,0 detecta **6/10** y la de −7,5 sigue en 3/10: la diferencia es 3, no 4. De los cuatro «recuperados», el verapamilo no sobrevive al cambio de semilla.
- Los cuatro recuperados quedan a **0,14–0,20 kcal/mol** del propio −7,0 con la semilla 42, y el tamoxifeno queda a 0,004 con la 43. La sensibilidad del −7,0 también descansa en márgenes dentro del ruido.
- La ventana de repetición ([−7,8; −6,7]) cubre bien el entorno de −7,0 y mal el de −7,5. Droperidol (−7,950, a 0,45 de −7,5, lo que se movió el verapamilo) no se repitió, y tampoco terfenadina, ziprasidona ni moxifloxacino (a 0,54–0,59). Los tres positivos de −7,5 salen de moléculas sin repetir.

El protocolo fijaba la ventana y la semilla 42 como comparación primaria, así que no hay desviación. El defecto es del diseño, y debe constar.

## R2. La estadística no separa los cortes

- **Sensibilidad:** cuatro discordantes, todos en el mismo sentido. McNemar exacto bilateral, p = **0,125**. Los IC de Wilson (40–89 % y 11–60 %) se solapan entre 40 y 60 %.
- **Especificidad:** un discordante (amoxicilina), p = 1.
- Agrupando los cinco: 4 contra 1, p = 0,375 bilateral (0,19 unilateral).

Con una diferencia real como la observada, un McNemar exacto sólo cruza p < 0,05 a partir de seis discordantes en el mismo sentido: harían falta del orden de 15–20 bloqueadores, y 3 semillas por compuesto para promediar el ruido (cuenta de orden de magnitud, no un cálculo de potencia). No lo recomiendo para 1.0.4.

Una consideración de coherencia, que no es evidencia de acierto: para un ligando ordinario, la penalización del normalizador de 5VA1 empieza por encima de −7,0 (parámetro −7,5 más 0,5 de holgura). Alerta y normalizador coinciden hoy en −7,0, y pasar la alerta a −7,5 los separaría.

## R3. El microestado enreda la comparación

Según `resultados.json`, la preparación del producto acopló **neutros** a tres bloqueadores con amina terciaria básica: haloperidol, cisaprida y droperidol (IC₅₀ 0,015, 0,091 y 0,307 µM). Los demás con amina entraron como catión. El informe menciona sólo el haloperidol.

Dos de los cuatro bloqueadores «recuperados» por −7,0 (haloperidol y cisaprida) son de esos neutros. En Vina la amina neutra es aceptor de hidrógeno y la protonada es donante, de modo que la elección del microestado cambia la puntuación sin que el corte tenga nada que ver. No verifiqué los pKa de esas tres moléculas, y no sé si dimorphite, la ruta de ionización o la regla de preparación decidió cada caso: eso hay que averiguarlo antes de usar el piloto para algo más.

Hay además un microestado dudoso en el único coste del lado de −7,0. La amoxicilina (control, la «alerta adicional») entró con el **nitrógeno de la β-lactama protonado** (`C(=O)[NH+]2`) y la amina primaria neutra. Una lactama no es una base, y esa especie no existe a pH 7,4. No volví a ejecutar la preparación: la lectura es del microestado registrado en `resultados.json`. Si es un defecto, es de preparación y no del umbral, y conviene pasárselo a quien tenga D-04, que ya revisa «especie en revisión».

## R4. El reanálisis de Rouen usa una columna que no es comparable con el producto

El CSV trae dos columnas de Vina, y el informe, siguiendo el protocolo (que lo fijó tras inspeccionar nombres y columnas, antes de contar), usa `vina`. Con las 9 moléculas que coinciden con el piloto local, la diferencia con el score del producto es:

| Columna | Mediana de (Rouen − local) | Rango | Mediana de la columna |
|---|---:|---|---:|
| `vina` | **−3,13** | −4,13 a −1,25 | −9,68 |
| `cav_vina` | +0,37 | −0,43 a +1,89 | −6,61 |

Con `vina`, 31/31 casos TdP **y 21 de 22 casos sin TdP** alertan en −7,0 (20 de 22 en −7,5): los cortes saturan y el reanálisis no puede dar la razón a ninguno. Es lo que el informe llama saturación, pero lo atribuye al modelo y no a la columna elegida. El AUC de esa columna es 0,705.

Con `cav_vina`, que está en la escala del producto, los cortes sí se separan: −7,0 alerta 14/31 TdP y deja sin alertar 14/22 sin TdP; −7,5, 11/31 y 15/22. Discordan cilostazol, moxifloxacino y sunitinib (TdP) y linezolid (sin TdP). **Esto es exploratorio, posterior al registro, y no lo uso para decidir nada**: no sé qué receptor o caja hay detrás de cada columna ni qué significa «cav». Sólo muestra que la lectura «ninguna evidencia en Rouen» depende de cuál se use, y que ese reanálisis mide la no transferibilidad entre configuraciones, que ya era su objetivo declarado, y no apoya ningún corte.

## R5. Precisión de las citas

- **Diltiazem a 6,6 µM** viene de un estudio anterior que cita PMC12640937. Ese artículo mide **8,9 µM**. La conclusión no cambia, pero la cifra y su fuente deben coincidir.
- **Creanza:** sus umbrales separan IC₅₀ ≤ 1 µM de > 80 µM en Glide, y la 5VA1 sin ajuste inducido rindió peor que los modelos de ajuste inducido (las métricas que da cada una no son la misma, así que no pongo cifras). Ayuda a decir que el corte depende del método; no ayuda a elegir entre −7,0 y −7,5 en Vina.
- **Kramer:** el AUC de 0,93 no es exclusivo del modelo 5; el modelo 2 también da 0,93.
- **Yao et al.** midió a 25 °C, según la lectura de sus métodos, y no a 37 °C. El informe no menciona la temperatura, y él mismo cita (Milnes et al.) que el IC₅₀ de hERG depende del protocolo: conviene que la diga.

## R6. El redondeo: propuesta, a la espera de aprobación

Es real: con −7,004 el mensaje dice «afinidad −7.0 kcal/mol < umbral −7.0». La decisión usa el valor completo y el texto, uno. Propongo una regla mínima, sin tocar la decisión: en [`texto_de_alerta`](../../backend/services/docking/selectivity.py) y en [`ProSelectivityPanel.tsx`](../../frontend/components/interfaces/pro/ProSelectivityPanel.tsx), usar un decimal y, **sólo si el valor redondeado coincide con el umbral**, tres. Toca texto de alerta, claves de traducción y posiblemente la instantánea del dossier, así que no lo hago sin su visto bueno.

## R7. «SIN ALERTA EN ESTE PANEL»: propuesta, a la espera de aprobación

El veredicto de la línea 495 de `ProSelectivityPanel.tsx` dice que ningún anti-target rebasó el umbral. En el piloto, **3 de 10 bloqueadores medidos (≤ 10 µM) no alertaron** con −7,0: amiodarona (0,546 µM), quinidina (1,5 µM) y propranolol (9,9 µM). Sensibilidad 70 % (IC 95 % 40–89 %, n = 10). Frase propuesta para el aviso, en el idioma del producto: «Sin alerta no descarta el bloqueo de hERG: en un piloto de 16 compuestos con este método, 3 de 10 bloqueadores medidos no alertaron». Es texto de usuario que cita una cifra, y la cifra es de un piloto sin validación poblacional, así que decide el propietario si entra, con qué cifra y dónde.

El informe también propone distinguir en el Explorador «corte de alerta exploratoria hERG (score de Vina)» de «parámetro de normalización de afinidad de la diana principal» ([`resultFieldPresentation.ts:77`](../../frontend/lib/resultFieldPresentation.ts)). Lo apoyo. Es de la misma clase, y espera la misma aprobación.

## Lo que pido al investigador

1. Reformular la frase de decisión: sustituir «perdería cuatro bloqueadores» por la razón de R2.
2. Añadir R1 y R3 como limitaciones del piloto, con el desglose de semillas.
3. Decir en el reanálisis de Rouen qué columna se usó y por qué satura, y que la otra está en la escala del producto (R4), sin usarla como evidencia.
4. Corregir las tres citas de R5 y el 25 °C.

## Reproducir

Con python-embed y sólo la biblioteca estándar. El CSV va a una carpeta nueva y vacía; el script no vive en ella.

```bash
./python-embed/python.exe -I -c "import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" <carpeta>/data_clean.csv
```

El resultado debe ser `9d0cd23c08c93071a69661f9538c3b001a4f41e1bd6bc4db382c522f5a0d537c`. Las tablas de R1, R2 y R3 salen de `piloto.semillas_y_fallos` en [`resultados.json`](herg-umbral-2026-11-15/resultados.json) (campos `compound`, `seed`, `score` y `microstate`), y las de R4 de las columnas `TdP`, `Name`, `vina` y `cav_vina` del CSV, comparadas por nombre con la semilla 42 del piloto.

## No verificado

- La página del artículo de Rouen et al. y, con ella, el receptor de cada columna.
- Los pKa de haloperidol, cisaprida y droperidol, y qué regla de preparación eligió cada microestado.
- Las 23 pruebas y la sonda de contrato del informe: leí el código, no las repetí.
- Si el 5-HT2B del panel por defecto (−7,5 en `ANTI_TARGET_PANEL`) y el que ofrece el selector de Bowes (−7,0 por omisión, [`selectivity.py:157`](../../backend/services/docking/selectivity.py)) usan el mismo corte. Queda fuera de hERG y no lo he comprobado.
