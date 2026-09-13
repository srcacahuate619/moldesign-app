# REC-11 — Quitar todas las aguas no mueve la cobertura de novo, y el diseño no resuelve menos de diez puntos

## Diagnóstico: `SIN_DIFERENCIA_DETECTABLE` — decisión `INCONCLUSIVE`

Es el experimento que `docs/51_POLITICA_DE_AGUAS.md` §5 nombró como **lo único que
cambiaría la política**. `REC-09` había medido el efecto de las aguas sobre el scoring del
**cristal**; la política gobierna el docking **de novo**, donde no existe pose de
referencia con la que decidir qué agua estorba. Por eso aquí se quitan **todas**.

| Instrumento | Criterio preregistrado | Resultado | Estado |
|---|---|---|---|
| **Cantidad primaria** | McNemar exacto bilateral sobre la cobertura del oráculo pareada; tres lecturas escritas antes | `b`=10, `c`=8, **p = 0.814529** | **Válido → rama (3)** |
| **MDE declarado antes de correr** | `b`≥6 con `c`=0 para p<0.05; 11.3 pp con discordancia del 20%, 8.0 pp con el 10% | discordancia observada **15.5%**, MDE **9.92 pp** | **Se cumplió lo declarado** |
| Secundario top-1 | descriptivo, **sin gate** | CON 59 vs SIN 50; `b`=12, `c`=21, p=0.162756 | **No se cita como evidencia** |

`INCONCLUSIVE` y no `GO` porque la rama (3) es justamente la que el gate reserva para «no
se distingue». Mismo criterio con que se sellaron `REC-09` y `MF-13` con lectura `MIXTO`.

## Lo que queda establecido

**Con 116 de 116 y cero fallos, quitar todas las aguas no cambia la cobertura de forma
detectable.** Coste: **61.27 CPU-h** — 31.04 el brazo CON, 30.23 el SIN — en 30.8 h de pared.

| Brazo | Cobertura del oráculo | |
|---|---:|---:|
| CON aguas — la política actual | **94 / 116** | 0.8103 |
| SIN aguas — receptor seco | **96 / 116** | 0.8276 |

Dos complejos de diferencia agregada, y **18 discordantes** repartidos casi por igual:
`b`=10 donde gana SIN, `c`=8 donde gana CON. Δ del oráculo mediano **−0.021 Å**. La
intervención no fue cosmética: mediana de **156 átomos de agua** retirados por receptor,
rango de 0 a 2279.

| `b` — quitarlas gana | `c` — conservarlas gana |
|---|---|
| `10gs` `1d7i` `1d9i` `1dgm` `1ela` `1fh7` `1fkh` `1kav` `1mmr` `1nje` | `1bma` `1cet` `1cnw` `1gwv` `1hmr` `1j4r` `1lbk` `1m2x` |

**`1fkh` está en la columna izquierda.** Es el caso que `docs/51` usa como demostración del
bloqueo —de +2.550 a −10.369 kcal/mol quitando dos aguas— y en de novo también mejora al
quitarlas: 5.131 Å con aguas contra 1.914 Å sin ellas. Es **un caso**, no una tendencia, y
así debe citarse.

## Lo que NO queda establecido

- **Esto no es equivalencia.** Es ausencia de detección con un MDE de **9.92 pp**, unos 13
  complejos netos. Diferencias menores no son resolubles con esta cohorte y **no se
  reportan como tendencia** — lección explícita de `RS-14`.
- **La política no queda confirmada positivamente.** Ésa era la rama (2) del gate y no
  salió. `docs/51` sigue *declarada*, ahora con su límite de resolución medido.
- **El secundario top-1 apunta al revés que el primario** —a favor de conservar, `c`=21
  contra `b`=12— y **no es significativo** (p=0.163). No tiene gate y no se cita en ninguna
  dirección. Está aquí porque estaba preregistrado, no porque diga algo.
- **Un solo confórmero.** Mide el efecto de las aguas *a confórmero igualado*, no la
  cobertura alcanzable: `MF-33` midió que `conf0.flex` convierte 12 de 33 contra 26 del
  ensemble.
- **Quitarlas todas no es la única alternativa.** Las políticas intermedias —B-factor,
  ocupancia, enterramiento— no se evalúan aquí. Un `QUITARLAS MEJORA` no habría autorizado
  adoptar el brazo SIN, sino abrir esa comparación.

## Exploratorio, post-hoc y sin gate

**No estaba preregistrado. No es un resultado.** Se registra porque genera una hipótesis
falsable, y se marca para que nadie lo cite como hallazgo:

| Estrato | n | CON | SIN | `b` | `c` | p (post-hoc) |
|---|---:|---:|---:|---:|---:|---:|
| `COLOCACION` | 33 | 17 | **22** | 7 | 2 | 0.180 |
| `RESTO` | 68 | **62** | 59 | 3 | 6 | 0.508 |
| `CONTROL` | 15 | 15 | 15 | 0 | 0 | 1.000 |

Los dos estratos grandes apuntan en direcciones **opuestas** y se cancelan en el agregado.
**Ninguno alcanza significación**, ni siquiera por separado, así que esto no rescata nada:
es, como mucho, el diseño de un futuro prerregistro con la estratificación declarada
*antes*. El `CONTROL` sale limpio —15 de 15 en los dos brazos, cero discordantes—, que es
lo que se le pide a un control.

## Procedencia

| Artefacto | Qué aporta |
|---|---|
| `REC-11-PRE` | Prerregistro sellado el 2026-08-20, con el hash del runner y el MDE calculado antes |
| `REC-09` | El efecto sobre el scoring del cristal; 26 de 116 con agua bloqueante |
| `MF-13` | La cohorte y el umbral de −3.0 kcal/mol |
| `docs/51` §5 | La pregunta que este experimento responde |

Ejecutado en el contenedor del servidor. Artefactos descargados con SHA-256 verificado
contra el remoto; el hash de `scripts/run_rec11_aguas_denovo.py` coincide con el sellado en
`REC-11-PRE` tanto en local como en el servidor.
