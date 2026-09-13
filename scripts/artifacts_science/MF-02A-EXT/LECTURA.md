# MF-02A-EXT — El techo conformacional generaliza, y el conjunto de train es más difícil que PDBBind

**Tipo: medición** (declarada en `MF-02-PRE` §4, sellado antes de ejecutar). Sin gates de aceptación: mide, no decide.

## Qué se midió

El mismo techo conformacional de `MF-02A` —RMSD mínimo **alineado** (`GetBestRMS`) entre cualquier confórmero del ensemble ETKDG y el ligando cristalográfico— sobre **5,316 complejos de PDBBind** en vez de los 116 de train. 6.9 h en el contenedor.

Aquí alinear es **correcto a propósito**: la pregunta es sobre la conformación interna del ligando, no sobre su colocación. Es la decisión contraria a la del resto de la línea, y así quedó declarado antes de ejecutar.

## La curva sobre 4,636 complejos

| `n_conf` | Mediana | ≤1.0 Å | ≤2.0 Å |
|---:|---:|---:|---:|
| 5 | 1.175 Å | 43.0% | 75.2% |
| 15 | 0.943 Å | 52.1% | 81.2% |
| **30** (protocolo) | 0.871 Å | 56.0% | **83.9%** |
| 60 | 0.806 Å | 59.3% | 86.2% |
| 90 | 0.781 Å | 60.9% | 87.2% |
| 150 | 0.761 Å | 62.5% | **88.1%** |

## Dos lecturas, y una corrige a MF-02A

**1. El techo generaliza: ~12% de PDBBind no tiene la conformación bioactiva** en el ensemble ETKDG ni con 150 confórmeros. Es una propiedad del método de embebido, no de la cohorte de 116.

**2. La saturación es más blanda a escala de la que vi en los 116.** Sobre train la curva se aplanaba en 80.2% desde K60 (K60 = K90 = K150); sobre 4,636 sigue subiendo: 86.2 → 87.2 → **88.1%**. Son ~1 punto por duplicación más allá de K60, pequeño pero real y sostenido.

Es decir: la saturación que declaré en `MF-02A` era en parte un artefacto del tamaño de muestra. Con n=116 el plateau aparente era ruido; con n=4,636 se ve que hay una pendiente residual. **La conclusión cualitativa se mantiene** —el eje conformacional da rendimientos decrecientes y pasar de 30 a 150 cuesta 5× para ganar 4.2 puntos— pero «satura» era demasiado fuerte.

**3. El conjunto de train es más difícil que PDBBind en general.** A `n_conf=30`, la disponibilidad conformacional es **83.9% en PDBBind frente a 77.6% en los 116 de train**. Los 116 no son una muestra representativa: son más duros. Eso es coherente con el gradiente `train < val < test` que `RC-F0-V2` encontró en la cobertura del oráculo, y sugiere que el sesgo viene de cómo se armó la cohorte, no del generador.

## Fallos

**680 de 5,316 complejos (12.8%)** no se pudieron medir: 677 por fallo de embebido de RDKit (`EmbedMultipleConfs` no produjo confórmeros) y 3 sin confórmeros tras el pruning. Son ligandos que el propio generador no puede procesar — un límite que conviene tener presente antes de plantear cualquier ampliación de cohorte: **el 13% de PDBBind no pasa ni la primera fase**.

## Relación con MF-09

`MF-09` concluyó que en 30 de 33 complejos difíciles no existe pose a ≤2 Å entre ~751 candidatas, y que por tanto el fallo es de muestreo. Esta medición lo acota por el otro lado: **la conformación sí suele estar disponible** (83.9% a K30 en PDBBind). Las dos juntas dicen que el material conformacional existe y el docking no lo coloca — el cuello está en la búsqueda de posición y orientación, no en la generación de formas.

## Prohibición heredada

La disponibilidad conformacional medida aquí **no puede usarse como filtro** para construir cohortes futuras sin declararlo: sería seleccionar complejos por una propiedad correlacionada con el éxito del docking (`MF-02-PRE` §4).

## Archivos

- `metrics.json` — curva global, fracciones por umbral y configuración.
- `per_complex.jsonl` (4,636) — por complejo: curva acumulada de RMSD mínimo, confórmeros conservados, átomos pesados.
- `failures.jsonl` (680) — clasificados por causa.
- `scripts/run_mf02a_conf_ceiling.py` (con `--all-pdbbind`).
