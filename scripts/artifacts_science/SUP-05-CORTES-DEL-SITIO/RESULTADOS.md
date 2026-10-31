# SUP-05-CORTES-DEL-SITIO — acta de cierre

**Decisión: INCONCLUSIVE.** Sólo 272 de las 381 entradas son medibles, por debajo del mínimo de 300 que fijó el registro
previo (`9d470adf`). Las otras 109 no declaran `site_ligand` en `curated_targets.json`, así que no hay ligando del cristal desde el
que medir. Ninguna falla por error del script. El mínimo se fijó sin conocer ese recuento. Es un error de planificación,
no de la medida, y la regla se aplica tal como se escribió.

## Lo medido (se publica; no decide)

| Corte del hueco | 6 Å | 7 Å | **8 Å (vigente)** | 9 Å | 10 Å |
|---|---:|---:|---:|---:|---:|
| Entradas que abstienen por un hueco | 15 | 22 | **27** | 30 | 36 |
| Entradas con una cadena lateral truncada | 18 | 30 | **42** | 48 | 57 |

| Corte de la especie | 5 Å | **6 Å (vigente)** | 7 Å | 8 Å |
|---|---:|---:|---:|---:|
| Alguna especie retirada (sin contar los metales coordinados) | 51 | **57** | 69 | 80 |
| · metal | 9 | 10 | 20 | 30 |
| · otra copia del ligando | 14 | 15 | 15 | 18 |
| · otra orgánica | 31 | 35 | 40 | 45 |

- **Primaria 1 (hueco, de 7 a 9 Å):** cambian 8 de 272 entradas, el 2,9 %, por debajo del 5 % del criterio.
- **Primaria 2 (especie, de 5 a 7 Å):** cambian 18 de 272, el 6,6 %, por encima del 5 %. Casi todo el salto está en los
  metales: 10 a 6 Å y 20 a 7 Å.
- **Metal coordinado por el ligando del cristal** (abstiene con cualquier corte): 36 entradas. Concuerda con las 35 del inventario
  geométrico de 2026-10-11 (`docs/auditorias/metales_junto_al_sitio_2026-10-11.json`).
- **Control:** el hueco más cercano de 4JVB está aquí a 6,12 Å; ABS-TR-01-VALIDEZ-R1 publicó 6,09 Å. La diferencia es esperable,
  porque aquí se mide desde el cristal y Preparación toma el mínimo con la pose.
- **Falsos bloqueos por hueco en los 28 sistemas de ABS-TR-01-VALIDEZ-R1** (abstiene y el panel no lo detiene): ninguno a 6 Å,
  4JVB a 7 y 8 Å, y 4JVB, 6GUE y 6HL1 a 9 y 10 Å.
- Distancia del hueco más cercano: 15 entradas a menos de 6 Å, 12 entre 6 y 8 Å, 9 entre 8 y 10 Å; 187 sin hueco o con el más
  cercano a 20 Å o más.

## Qué significa

- Con las entradas que sí se pueden medir, **el corte de 8 Å de los huecos no es un filo**: un ångström arriba o abajo cambia el
  estado en menos del 3 % del catálogo. El de **6 Å de las especies sí lo parece**, sobre todo para los metales, cuyo número se
  duplica de 6 a 7 Å. Ninguna de las dos lecturas es una decisión: el experimento no alcanzó su denominador.
- Una repetición con el denominador corregido no sería ciega: estas cifras ya se conocen. La medida que de verdad fijaría el corte
  de las especies es un redocking con y sin el metal a 6–8 Å, como MET-01-R1 a ≤ 6 Å.

## Límites

- Mide desde el ligando del cristal, no desde el mínimo con la pose top-1 que usa Preparación.
- Las especies salen del ensamblaje, no del `species_diff` de una preparación con Meeko: es una reproducción geométrica de la
  regla. Las 15 entradas que Meeko no prepara aquí sí se miden.
- Mide si la decisión depende del corte, no si el corte es correcto.
