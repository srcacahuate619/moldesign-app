# RS-14

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Con el denominador corregido (conjunto v2, cobertura 79.3%), un selector bajo el protocolo congelado de v0.6 supera al baseline de vina_score en precision condicional, evaluado leave-one-complex-out

## Protocolo

Referencia: `RS-14-PRE sellado; datos RC-F0-V2 solo train; 233 features con la transformacion de v0.6; XGBRanker con hiperparametros congelados; LOCO 116x3 semillas; nulo por permutacion dentro de complejo`

## Gate

G1 validez, G2 condicional > baseline con CI95 pareado excluyendo cero, G3 condicional > percentil 95 del nulo

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `1dc3ba88df8c9d5b8c022307b8ac31d88293d1d8`, dirty=True

## Estado

- Creado: 2026-08-18T08:00:59.334830+00:00
- Status: finished
- Decisión: NO_GO
- Sellado: sí (2026-08-18T08:01:00.018755+00:00)
- Finalizado: 2026-08-18T08:01:29.624766+00:00
- Razón de la decisión: Falla G2: la precision condicional del selector es 0.4312 frente a 0.4783 del baseline de vina_score, con diferencia pareada -0.0471 y CI95 [-0.1522, +0.0617] sobre los 92 complejos cubiertos. TRES MATICES QUE EL NO_GO NO DEBE OCULTAR. (1) El selector SI aprende senal real: con 200 permutaciones que barajan etiquetas dentro de cada complejo, el nulo tiene media 0.104 y percentil 95 en 0.163, y el selector alcanza 0.431 con p empirico 0.0, casi tres veces por encima; en el regimen p>n que temiamos, el modelo no memoriza ruido. (2) El CI CRUZA EL CERO, asi que la lectura honesta no es que el selector pierda sino que empata dentro del ruido y el gate exigia superioridad demostrada, tal como se preregistro. (3) Lo que aprende no anade nada sobre el score de Vina. HALLAZGO OPERATIVO: con 92 complejos cubiertos la diferencia observada equivale a 4.3 complejos y el intervalo de mas menos 0.10 equivale a 9, de modo que este diseno NO PUEDE detectar diferencias menores a unos 10 puntos porcentuales, y mas semillas, features o arboles no lo arreglan porque la incertidumbre viene del numero de complejos. Confirma cuantitativamente lo que la seccion 19.1 afirmaba: la palanca es multiplicar complejos, no senales; harian falta unas 4 veces mas para resolver diferencias de 5 puntos. La variabilidad entre semillas (0.467, 0.380, 0.446) tiene un rango de 0.087, casi el doble de la diferencia con el baseline, que es otra manifestacion del mismo limite de potencia. Contraste con MF-09: el margen existe -8 de 15 complejos del control tienen la pose correcta disponible y el top-1 por score no la elige pero si esta entre las cinco primeras- y el selector no lo captura. La cartera D se reabrio con el denominador corregido, que era la condicion de la seccion 19.1, y el resultado es que el problema NO era el denominador: el espacio de features actual esta agotado frente a vina_score. No se tocaron val ni test: un NO_GO en train no consume el confirmatorio.
- Hashes de dataset: 2 archivo(s) con SHA-256
- Hashes de assets: 5 archivo(s) con SHA-256

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
