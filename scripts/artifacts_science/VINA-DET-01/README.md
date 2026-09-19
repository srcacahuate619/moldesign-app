# VINA-DET-01 — ¿es reproducible una corrida de Vina?

**2026-09-19.** Bloque 2 de [`VALIDACION_EN_SERVIDOR.md`](../../../backend/audits/VALIDACION_EN_SERVIDOR.md).
Tipo: medición. Sin gates de decisión.

## La pregunta

El producto promete un «paquete estructural reproducible». Esa promesa apoya en
un supuesto que nunca se midió: que Vina, con la misma entrada y la misma
semilla, produce la misma salida.

El supuesto era dudoso por construcción. `core/config.py:108` declara
`vina_cpu = 0` —auto-detección de núcleos— y `vina_service.py:576` lo pasa tal
cual a `--cpu`. `ENSEMBLE_REVIEW.md` lo dejó explícitamente sin medir:

> «Con la misma entrada, semilla y caja cabría esperarlo, pero `vina_cpu` vale 0
> por defecto y la búsqueda paralela de Vina no garantiza reproducibilidad bit a
> bit. No se comprobó, y por tanto no se afirma.»

## El resultado

Sesenta corridas: exhaustividad ∈ {8, 32} × `--cpu` ∈ {0, 1, 12}, diez
repeticiones por celda, semilla 42, misma caja, mismo receptor y mismo ligando
ya preparados. Cero fallos.

| celda | hashes distintos | idéntico byte a byte | rango top-1 | mediana |
|---|---:|---|---:|---:|
| `exh=8`  `cpu=0` (auto) | 1 | sí | 0.0 | 11.25 s |
| `exh=8`  `cpu=1` | 1 | sí | 0.0 | 57.30 s |
| `exh=8`  `cpu=12` | 1 | sí | 0.0 | 11.23 s |
| **`exh=32` `cpu=0`** (el producto) | **1** | **sí** | **0.0** | 33.54 s |
| `exh=32` `cpu=1` | 1 | sí | 0.0 | 200.05 s |
| `exh=32` `cpu=12` | 1 | sí | 0.0 | 33.66 s |

**Las sesenta salidas se reducen a DOS contenidos distintos**, uno por
exhaustividad:

    exh=8    7b1bcce8d5498d71f9ebe5f28f313e9948c23341df1ef792f01128b05d0e5cd5
    exh=32   321fb277d295a08099d65e7dced48967db0e9da071e2cceb907d117874445f48

El número de hilos **no aparece en el resultado**. Las tres condiciones de
`--cpu` producen el mismo archivo, byte a byte, dentro de cada exhaustividad.
Lo único que cambia es el tiempo: 200 s con un hilo frente a 33 s con doce, sin
una sola diferencia en las nueve afinidades ni en una sola coordenada.

## Lo que esto permite afirmar, y lo que no

**Permite** decir que la promesa de paquete reproducible **no necesita una
condición sobre el número de hilos**, que era la sospecha razonable. No hay que
escribir «reproducible sólo con `cpu=1`», como sí hubo que escribir la condición
de reconstrucción de hidrógenos en `MF-33-H-COR`.

**No permite** generalizar. Un ligando (E6C), un receptor (5TUN), una máquina
(Windows 11, 12 hilos), un binario (`AutoDock Vina v1.2.7`,
`e0c4b2715e0c1a74…`). Determinismo en otro binario, en otra plataforma o con
otro número de núcleos **sigue sin medirse**, y es justo la repetición que
tiene valor hacer en el servidor: otra arquitectura y otro recuento de núcleos.

**Tampoco dice** que las poses sean buenas. Dos salidas idénticas no son dos
salidas correctas.

## Condiciones de la corrida

Las celdas se ejecutaron en serie sobre la estación de trabajo. Durante la celda
`exh=32 cpu=1` corrió además, declarado, la batería de pruebas del backend y un
piloto de tres conformaciones con un solo hilo. Afectó al tiempo de pared, no al
resultado: los diez hashes de esa celda coinciden entre sí y con los de las
demás. Una medida de determinismo que sobrevive a la contención es una medida
más fuerte, no más débil.

## Contenido

    entorno.json        binario, hashes de entrada, máquina y parámetros
    per_complex.jsonl   una línea por corrida: hash, afinidades, tiempo
    metrics.json        el resumen por celda
    _work/              receptor y ligando de entrada, y UN representante por
                        hash distinto

Los 58 archivos restantes se eliminaron **después** de comprobar que eran
idénticos byte a byte a su representante; `per_complex.jsonl` conserva el
SHA-256 de las sesenta corridas, así que no se perdió ninguna evidencia.

## Reproducir

    python scripts/run_vinadet01_determinismo.py --salida <directorio-nuevo>

Un directorio nuevo, nunca el de salida de otra corrida.
