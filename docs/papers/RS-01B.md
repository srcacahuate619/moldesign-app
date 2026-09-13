---
titulo: "Quitar poses duplicadas no mejoró nada, y eso también es un resultado"
entradilla: "La deduplicación dejó el RMSD pareado exactamente en 0.000 Å y bajó los aciertos de 47 a 43. Ni mejora ni degrada de forma demostrable: simplemente no es la palanca."
---

Cuando un pipeline genera candidatas desde tres fuentes distintas, muchas son la misma
pose contada varias veces. Eso desperdicia presupuesto y, peor, distorsiona la densidad
del espacio: una región muestreada por casualidad tres veces parece más importante de lo
que es, y un selector entrenado sobre esa distribución aprende un sesgo que no está en la
física.

La hipótesis era que limpiar los duplicados mejoraría la selección sin perder calidad de
pose.

## Qué pasó

| | Aciertos Top-1 fuera de muestra |
|---|---:|
| Conjunto original | 47/116 |
| **Deduplicado** | **43/116** |
| Exigido por el gate | ≥ +3 |

Delta de **−4**. El gate no se cumple.

Los dos criterios de no-degradación sí se cumplen, y con holgura:

- **mediana pareada del cambio de RMSD: 0.000 Å**, con un límite de 0.1 Å. La
  deduplicación no perdió ni una pose buena;
- el intervalo de confianza por componentes, [−8.80, +4.00], y el test de McNemar
  (p = 0.481) **no establecen superioridad ni degradación**.

## Cómo hay que leer esto

Es tentador leer «bajó de 47 a 43» como que la deduplicación hace daño. La estadística no
lo soporta: el intervalo contiene el cero con margen a ambos lados. Con n=116 y una
diferencia de 4 complejos, esto es indistinguible del ruido.

La lectura correcta es la aburrida: **la deduplicación es neutra**. No mejora la selección
y no estropea las poses.

Que la mediana del cambio de RMSD sea **exactamente 0.000 Å** es el dato más informativo
del experimento y el que justifica conservar la herramienta. Significa que el umbral
elegido agrupaba poses genuinamente equivalentes: al quedarse con una representante de
cada grupo, no se perdió ninguna pose que importara. Es un filtro que hace lo que dice.

## Por qué el artefacto se conserva aunque no se adopte

El resultado es un **NO_GO operacional**: la deduplicación no se adopta como entrada por
defecto del selector, porque no hay evidencia de que mejore nada y la regla del laboratorio
es no cambiar producción sin ella.

Pero el artefacto queda disponible como opción, y esa decisión resultó acertada por una
razón que en su momento no se veía. Cuando el conjunto se reconstruyó y pasó a ser **6.9
veces más denso**, la deduplicación dejó de ser cosmética: con ~169 candidatas por complejo
en vez de ~9, reducir un tercio del volumen sin perder cobertura es una diferencia real de
coste.

El umbral hubo que volver a derivarlo —el de 1.5 Å se había elegido sobre la unión escasa,
y sobre la densa sale 2.0 Å— pero la herramienta ya existía y estaba validada.

Un negativo que deja detrás una pieza reutilizable vale más que uno que sólo deja una
conclusión.
