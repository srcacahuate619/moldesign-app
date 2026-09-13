# MF-29-EMP — Más búsqueda del mismo tipo no rinde, y el testigo que decía lo contrario medía mal

## Diagnóstico: `OBJETIVO` — decisión `GO`

> **Nota de enmienda.** Esta lectura se selló primero como `INCONCLUSIVE`, porque dos
> instrumentos preregistrados apuntaban en direcciones opuestas. `MF-29-EMP-COR` —
> prerregistrado y sellado **antes** de correr— midió que uno de los dos no medía lo que
> decía medir. No se movió ningún umbral ni se eligió instrumento después de ver el
> resultado: se retiró un instrumento inválido. El historial completo está en el
> `decision_rationale` del manifest.

| Instrumento | Criterio preregistrado | Resultado | Estado |
|---|---|---|---|
| **Cantidad primaria** | fracción con `min(exh=512) < min(exh=8) − 0.10`: ≥0.30 BÚSQUEDA, <0.10 OBJETIVO | **3/48 = 0.0625** | **Válido → OBJETIVO** |
| Testigo `MF-13` | «si el cristal puntúa mejor que el brazo masivo, la búsqueda falló» | 34/48 = 70.8% | **Retirado**: comparaba dos escalas (`MF-29-EMP-COR`) |

**`MF-29` —el certificado— sigue ABIERTO.** La jerarquía de Lasserre se declaró NO
IMPLEMENTABLE en este hardware antes de correr, y una cota empírica no certifica nada.

## Lo que queda establecido

**Más presupuesto del mismo buscador ya no compra nada.** 64× de `exhaustiveness` costó
**83.3 h de CPU contra 4.1 h** —20× el tiempo, con 3 semillas contra 5— y a cambio movió
tres complejos:

| Complejo | Estrato | TORSDOF | Producción | Masivo | Ganancia |
|---|---|---:|---:|---:|---:|
| `1d7i` | COLOCACION | 2 | −2.371 | −2.653 | **+0.282** |
| `1m2x` | RESTO | 6 | −5.882 | −6.120 | +0.238 |
| `1bn1` | RESTO | 6 | −7.143 | −7.268 | +0.125 |

Ninguno llega a un tercio de kcal/mol. En **45 de 48** la diferencia cabe en el ruido
declarado de 0.10, y en **19** el masivo salió *peor* que producción —nunca por más de
0.05—. La sd entre semillas baja de **0.013 a 0.009** medianos: el brazo masivo está
**saturado**, que era justo la condición que le daba sentido a la cota.

| Estrato | n | Mejoran | Ganancia mediana | Ganancia máx |
|---|---:|---:|---:|---:|
| COLOCACION | 7 | 1 | 0.003 | 0.282 |
| CONTROL | 12 | 0 | 0.002 | 0.039 |
| RESTO | 29 | 2 | 0.001 | 0.238 |

Y ahora consta algo más, que la lectura original no podía afirmar: **lo que la búsqueda
encuentra iguala o supera el valor del cristal relajado a igual escala**, en 36 de 48.

## El testigo, y por qué se retiró

`MF-13` puntuó el cristal relajado sobre el mismo receptor, la misma caja y la misma
función, y su prerregistro lo declaró cota superior independiente del mínimo global. Sobre
esa base, el cruce daba 34 de 48 (70.8%) a favor del cristal, con déficit mediano de 0.49
kcal/mol y hasta 3.42 — y en 31 de esos 34 el brazo masivo ya estaba a menos de 2 Å.
Parecía «aterriza en la cuenca y no baja al fondo».

**Los dos números no estaban en la misma escala.** `MF-13` escribe el `rigid_str` de
`molflex.escribir_pdbqt` —`ROOT / átomos / ENDROOT / TORSDOF 0`— y `MF-29-EMP` dockea
`conf0.flex.pdbqt`, con hasta 6 torsiones activas. Vina divide la afinidad por
`(1 + w_rot · N_rot)`: un ligando con `TORSDOF 0` no paga esa penalización y uno con 6 sí,
de modo que **el rígido puntúa mejor para la misma pose**.

`MF-29-EMP-COR` lo midió repitiendo `MF-13` con un solo cambio, el `flex_str` en vez del
`rigid_str`:

| Cantidad | Valor |
|---|---:|
| Salto de escala (mismo cristal, flexible − rígido) | **+1.055** kcal/mol medianos (máx. 3.895) |
| Déficit que el testigo leía | +0.491 |
| Déficit corregido, a igual escala | **−0.406** (el masivo puntúa **mejor**) |
| Complejos donde el cristal aún gana | **4 de 48** (`f` = 0.0833 ≤ 0.30) |

El artefacto de escala cubre de sobra el déficit que se estaba leyendo como fallo de
búsqueda. Los dos gates de validez del corrigendum pasaron antes del primario: **G1 = 1.0**
de coincidencia de TORSDOF y **G2 = 0.3425 Å** de deriva, casi idéntica a los 0.322 Å que
derivó el rígido en `MF-13`.

**Queda anulado el confusor del confórmero** que esta lectura había declarado como
siguiente paso obligado: no hay que comprobarlo, porque el déficit que se le iba a atribuir
no existe.

## n=48 y no 50: los dos que faltan expiraron, no fallaron

`1mmr` y `1nm6` aparecen como `VINA_FALLO` en las tres semillas del brazo masivo, con
`t_total_s: 0`, que **parece** una caída instantánea. No lo es —`t_total_s` sólo suma las
corridas con éxito—. El tiempo de fila menos el del brazo de producción da **43200.4 s** y
**43200.6 s**: exactamente 3 × el `timeout=14400` que está **en duro** en
`run_mf29emp_optimo_global.py:146`. Son tres plazos vencidos.

Es la trampa de §12.3 del roadmap otra vez: *un timeout por debajo del tiempo de un
complejo produce síntomas idénticos a un fallo real*. A `exh=512` estos dos necesitan más
de 4 h por semilla.

**Son recuperables**: tocar esa constante y re-correr sólo su brazo masivo, ~12 h de
servidor. No cambiaría la lectura salvo empate improbable —con 3/48 = 0.0625, harían falta
los dos mejorando para llegar a 5/50 = 0.10 y sólo entonces tocar el corte—. Detalle en
`failures.jsonl`.

Con gracia: son justo los dos complejos que entran a la cohorte por el criterio TORSDOF del
PDBQT y no por el conteo de RDKit, la diferencia que el propio diseño anotó.

## Qué autoriza y qué no

**Autoriza** cerrar la vía de «subir el presupuesto del mismo buscador»: está medido, está
saturado y cuesta 20× para nada. Refuerza lo que `MF-25` vio con 16×.

**No autoriza** declarar resuelto el diagnóstico de `MF-13`, que quedó `MIXTO` con un
componente de búsqueda flagrante. Ese `MIXTO` se midió contra el **mejor dock del conjunto
v2** —otro protocolo, ~751 poses por complejo— y no contra el brazo masivo de aquí. Se
comprobó además, en `MF-13-ESCALA`, que `MF-13` **no** arrastra el desajuste de escala que
`MF-29-EMP-COR` retiró: su top-1 viene de `molflex`, que dockea el PDBQT rígido, y su gate
queda idéntico —23/33 = 0.6970— al restringirlo a poses rígidas. `MF-13` sigue en pie.

**No reabre** `MF-03/04/05/07/12`: son parámetros del mismo buscador, y esto es una razón
más para no volver ahí.

## Nota de registro

El artefacto se creó **retroactivamente** al cerrar la corrida: el experimento se lanzó al
servidor sin manifest, y `created_at` es del sellado, no del lanzamiento. Mismo caso que
`MF-14` y `MF-19`. El prerregistro real es el docstring del script, sellado por hash en
`assets_hashes`, y es anterior a la corrida.
