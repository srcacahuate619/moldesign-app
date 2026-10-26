---
titulo: "INCONCLUSIVE: con la regla de metales en dos niveles, Preparación bloquea por error 1 de 18 sistemas, antes 3"
entradilla: "Frente al mismo panel ciego de revisores LLM, Preparación sigue sin autorizar ningún sistema que el panel detiene, y los falsos bloqueos bajan de 3 a 1 (4JVB). Los dos que desaparecen son los que MET-02-R1 predijo. Con 18 negativos no hay potencia para concluir."
---

**INCONCLUSIVE.** Repite `ABS-TR-01-VALIDEZ` con el producto de 1.0.4, que mide los metales desde el ligando del cristal y en
dos niveles (`14fd5e4d`). No es una medida ciega: MET-02-R1 ya había predicho qué cambiaría.

## Qué se midió

Los mismos 29 depósitos reales de ABS-TR-01, evaluados por la API como un usuario con un receptor del catálogo (ligando del
cristal, Vina 1.2.7, exhaustividad 8, 9 poses, semilla 42, 4 CPU) y después auditados por Preparación. La decisión de
Preparación (detenerse, avisar, seguir) se compara con la del panel de cinco revisores LLM, que **no se relanzó**: los revisores
juzgaron los depósitos, no la salida del producto, y su referencia se copió byte a byte de la sellada. La regla de decisión es la
misma: GO exige un límite superior unilateral 95 % del falso bloqueo ≤ 10 % y ninguna falsa autorización.

## Qué pasó

| Medida (mayoría de 5) | VALIDEZ | VALIDEZ-R1 |
|---|---:|---:|
| Falsas autorizaciones (el panel detiene, Preparación dice seguir) | 0 de 10 | 0 de 10 |
| Falsos bloqueos (el panel no detiene, Preparación se detiene) | 3 de 18 | **1 de 18** |
| Límite superior unilateral 95 % del falso bloqueo | 37,7 % | 23,8 % |
| Pasan con aviso aunque el panel los detiene | 4 | 4 |

- **1RKP y 6KE5** dejan de abstenerse y pasan a revisión: su ion retirado está a 6 Å o menos, pero el ligando del cristal no lo
  coordina. Es el cambio que predijo MET-02-R1; no apareció ningún otro.
- **4JVB** sigue bloqueado por un hueco del esqueleto a 6,09 Å: no lo toca la regla de metales.
- **4NY4, 6SXC, 6HW5 y 3G0E** siguen pasando con aviso aunque el panel los detiene. 4NY4 pide ahora revisión también por la
  protonación del receptor y por metales y cofactores (la Cys y el ligando junto al Fe del hemo); sigue siendo revisión, no
  abstención.
- 8WTW no se prepara (Meeko) y 1DIY se detiene en la comprobación previa, como antes. Las conclusiones con la mayoría unánime y
  con la ronda 2 sin Opus son las mismas: un solo falso bloqueo, ninguna falsa autorización.

## Qué significa y qué no

La regla nueva quita dos bloqueos sin motivo y no abre ninguna autorización falsa. Pero con 18 negativos el límite superior no
puede bajar del 15,3 % ni con cero errores, así que **este diseño no puede dar GO**: hacen falta más sistemas que el panel
considere aptos. Los revisores son LLM, no expertos, y dos son de la misma familia.

Sello `scripts/artifacts_science/ABS-TR-01-VALIDEZ-R1/`; arnés `scripts/abs_tr_01_r1/`, que importa sin editar el de VALIDEZ.
