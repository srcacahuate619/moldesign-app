---
titulo: "GO: la paridad de implementación pasa con el filtro geométrico y la excepción de azufre"
entradilla: "Pasan 23 topologías Br/I evaluables y 1 queda indeterminada por geometría. La revisión conserva GO al conjugar ese resultado con las comparaciones Windows/Linux y la ausencia de fallos de ejecución. No demuestra calidad física de los parámetros."
---

**GO del gate conjunto conservado.** Se sostiene la paridad de implementación bajo las condiciones declaradas. No se activa MMGBSA ni se valida su precisión como energía de unión.

## Por qué se repitió

H5 había dejado NO_GO por la letra de su gate: una entrada con geometría degenerada fallaba ya en vacío. R1 declara un filtro geométrico antes de medir esta réplica. El diseño se hizo después de conocer aquel caso; no cambia retroactivamente el gate ni la decisión de H5.

## Qué se midió

Se conservaron 55 topologías, 24 con Br o I, y controles F/Cl. Se compararon OpenMM 8.5.2, plataforma Reference, y sander en vacío y GBn2 sin superficie, sobre la misma topología y coordenadas. Se convierten analíticamente las constantes de Coulomb; no se ajustan contra el resultado.

El gate exige residuo de energía menor que 0,001 kcal/mol y error de fuerza convertido menor que 0,001 kcal/mol/Å. Para los casos con S se admite la excepción declarada: vacío conforme y desacuerdo de GBn2 que desaparece al tratar S como elemento genérico en ambos programas.

El filtro marca geometría imposible si algún par está a menos de 0,5 Å o un ángulo de valencia es menor que 30 grados. Esos casos quedan indeterminados. El gate exige al menos 20 Br/I evaluables y paridad directa Windows/Linux con entradas iguales.

## Qué pasó

Clasificación de R1 con el filtro, no los agregados anteriores que el script base deja también en metrics:

| Grupo | Pasa R1 | Indeterminado por geometría | Condición |
|---|---:|---:|---|
| Br/I | 23 | 1 | 19 directamente y 4 con la excepción de S |
| Control F/Cl | 30 | 1 | Misma clasificación geométrica y excepción escrita |

5mlj y 6gnp son las entradas indeterminadas. Recolocar sus H y repetir la comparación fue un diagnóstico fuera del gate; no sustituye sus resultados sobre la geometría original.

| Comprobación directa entre plataformas | Resultado archivado |
|---|---:|
| Comparaciones presentes / esperadas | 110 / 110 |
| Entradas iguales según sus hashes registrados | 55 |
| Tolerancia | 1e-06 kcal/mol y kcal/mol/Å |
| Máxima diferencia de energía | 8,53e-14 kcal/mol |
| Máxima diferencia de fuerza | 1,63e-13 kcal/mol/Å |

La comparación entre plataformas usa sus diferencias directas. El flag de coincidencia de Windows contra sander responde otra pregunta. Los registros geométricos de failures no son fallos de ejecución; metrics conserva aparte la lista de fallos de ejecución vacía.

## Qué dice y qué no dice

Con entradas y geometrías iguales, estas implementaciones concuerdan bajo el tratamiento descrito. Eso no demuestra que los parámetros representen correctamente la solvatación ni la afinidad, y la excepción de S no es un parámetro físico recomendado. No se extiende la conclusión a otras versiones, topologías o protocolos.

## Correcciones

**Vigentes al 2026-10-22.**

- **SCI-B-139:** el booleano original de R1 sólo evaluaba el requisito Br/I. El GO requiere también ausencia de fallos de ejecución y paridad Windows/Linux con las mismas entradas y geometrías. La conjunción se cumple en los resultados conservados; no se le atribuye al booleano aislado esa comprobación completa.

El log compara primero con el gate antiguo de H5 y muestra NO PASA; la salida final de R1 es PASA. Ambas líneas quedan preservadas y no se elige la primera como decisión de R1.

Detalle: `docs/102_FASE_1B_CORRECCIONES.md`; estado en `docs/100_CORRECCIONES_AUDITORIA_CIENCIA_20261015.md`. Se comprobaron tablas, hashes declarados, logs y productores. No comprobado por mí: las energías y fuerzas originales por átomo ni las topologías crudas, que no están distribuidas en esta carpeta. Sus hashes y metadatos no sustituyen una reproducción física; aquí no se recalcularon.
