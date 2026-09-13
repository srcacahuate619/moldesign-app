# REC-05 — Quitar los metales no mueve la cobertura de forma detectable, y el diseño no resuelve menos de quince puntos

## Diagnóstico: `SIN_DIFERENCIA_DETECTABLE` — decisión `INCONCLUSIVE`

`REC-05` pedía en el `docs/49` ablación por clase en **tres** clases y un gate de «reglas
por familia con evidencia». Dos clases quedaron fuera y el gate por familia se declaró
inalcanzable **antes de correr** — eso, y no el resultado, es la parte de este experimento
que no se podía escribir después.

| Clase | Estado | Por qué |
|---|---|---|
| Aguas | **Fuera** | `REC-11` condicionaba abrir políticas intermedias a `QUITARLAS MEJORA`; salió `SIN_DIFERENCIA_DETECTABLE` |
| Cofactores | **Fuera** | `REC-12-R1` midió que el núcleo robusto son 2 complejos |
| Metales | **Dentro, agrupados** | 29 complejos; `ZN`=21 descriptivo; `CA`/`MG`/`MN`/`CU` no leíbles |

## Lo que queda establecido

29 de 29, cero fallos, **96 átomos de metal retirados** —entre 1 y 18 por complejo, ninguno
a cero—.

| Brazo | Cobertura del oráculo | |
|---|---:|---:|
| CON metales | 24 / 29 | 0.8276 |
| SIN metales | **25 / 29** | 0.8621 |

`b`=2, `c`=1, **McNemar exacto p = 1.0**, discordancia 10.3%.

**MDE observado 14.84 pp — mejor que los 20.6 pp declarados**, porque la discordancia real
salió por debajo del 20% que supuse al calcularlo. Aun así el diseño no resuelve diferencias
menores a ~15 puntos, unos 4 complejos netos sobre 29.

**Secundario descriptivo, la única familia con `n`:** `ZN` sobre 21 da CON 16, SIN 17, `b`=2,
`c`=1, p=1.0, MDE 19.72 pp. Apunta igual que el agrupado y tampoco resuelve nada.

**Los dos discordantes:** `1mmq` (CON 1.134, SIN 2.083 → gana CON) y `1mmr` (CON 4.018,
SIN 1.071 → gana SIN). `1mmr` ya estaba entre los diez que `REC-11` rescató al quitar las
**aguas**; que también mejore al quitar los metales sugiere que ese complejo se beneficia de
vaciar el receptor por razones que este diseño no identifica. **Es un caso.**

## Lo que NO queda establecido

- **No es equivalencia.** Es ausencia de detección con MDE de 14.84 pp. Prohibido por el
  prerregistro leerlo de otra forma.
- **No hay reglas por familia.** `CA`=7, `MG`=3, `MN`=3 y `CU`=2 se declararon no leíbles
  antes de correr y no se emite ninguna, ni siquiera descriptiva.
- **Un solo confórmero**, igual que `REC-11`: mide el efecto a confórmero igualado, no la
  cobertura alcanzable.
- **Nada sobre los 87 complejos sin metal.**

## Consecuencia de producto — declarada aquí porque no era el propósito

La preparación del producto (`services/docking/preparer.py`) elimina hoy **el 100% de los
metales de los 387 targets** del catálogo, porque su puerta de conservación depende de un
`cofactors_whitelist` que está vacío en todos ellos.

`REC-05` mide que, **sobre estos 29 y con un confórmero, eso no es detectablemente dañino.**
No dice que sea inocuo: con un MDE de 14.84 pp, un daño de hasta cuatro complejos netos
sería invisible para este diseño. Es una cota, no una absolución.

## Procedencia

Protocolo idéntico al de `REC-11` **por construcción**: el runner importa
`run_rec11_aguas_denovo.py` —sellado como asset de `REC-11`— y reutiliza su `_brazo` y sus
constantes; el conjunto `METALES` viene del módulo sellado de `REC-12`. La cohorte se deriva
de artefactos sellados en tiempo de ejecución.

Decisión de implementación verificada antes de sellar: los metales se identifican **sólo por
nombre de residuo**. Mirar además el nombre de átomo y el campo de tipo del PDBQT retiraba
entre 200 y 3900 átomos por complejo —la proteína entera— porque `CA` es el carbono alfa de
todo residuo y `NA` es el tipo AutoDock del nitrógeno aceptor, no el sodio.

Ejecutado en el contenedor `moldesign-lab` del servidor; artefactos descargados con SHA-256
verificado contra el remoto.
