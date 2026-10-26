---
titulo: "GO de alcance: el comparador de cobertura cambió, sin evaluar un modelo generativo"
entradilla: "El GO de alcance mantiene MF-30 como benchmark externo opcional. El registro contrapone 3 y 26 casos cubiertos sobre 33 bajo protocolos distintos; no midió rendimiento, compatibilidad ni necesidad de GPU de un candidato generativo."
---

**GO de registro de alcance.** MF-30 deja de ser una dirección prioritaria de producto y queda como benchmark externo opcional. No se cancela su ID ni se incorpora un motor.

## Por qué se hizo

La propuesta de evaluar un generador preentrenado conservaba una referencia de cobertura del conjunto rígido anterior. El programa ya disponía de un brazo flexible con mayor cobertura observada. Superar aquella referencia histórica no bastaría para demostrar una mejora sobre el comparador activo.

## Qué se midió

Se recopilaron agregados anteriores. No se ejecutó un generador ni una comparación nueva de docking. La cobertura es de oráculo: existe una pose con RMSD de bolsillo de 2 Å o menos. No evalúa qué pose selecciona el producto.

## Qué pasó

Los conteos siguientes se refieren al estrato COLOCACION conservado, con 33 miembros:

| Referencia | Protocolo | Cubiertos |
|---|---|---:|
| Gate histórico de MF-09 | Conjunto v2, fuente rígida | 3 |
| MF-33, brazo C | Ensemble rígido del protocolo comparado | 1 |
| MF-33, brazo A | Conformero fijo flexible | 12 |
| MF-33, brazo B | Ensemble flexible | 26 |

El cociente entre el comparador flexible y el gate histórico es 8,67. Es una descripción de coberturas entre protocolos diferentes. No identifica la causa de la diferencia ni el efecto aislado de una intervención.

El registro cita además un benchmark externo de PoseBusters. No comprobado por mí: la publicación externa original y sus cifras. Aquí no se reproducen sus porcentajes ni se convierten en una medición del programa. El parcial de MF-33-A3 archivado tampoco se presenta como su resultado final.

## Qué dice y qué no dice

La decisión conserva el trabajo como comparación externa opcional. Reabrirlo requiere un candidato compatible con el runtime o un uso de laboratorio que produzca un entregable compatible, un comparador activo y control del solapamiento de entrenamiento. La restricción documentada se refiere al runtime CPU distribuido de aquella instalación. Este registro no demuestra una limitación universal de los modelos generativos ni mide sus tiempos o memoria.

## Correcciones

**Vigentes al 2026-10-22.**

- **SCI-B-124:** la revisión posterior verifica igualdad de miembros entre los grupos comparados. El productor original sólo contrastaba agregados. Se conserva el cociente descriptivo y se retira cualquier lectura causal de un cambio único.
- **SCI-B-125:** no se evaluó un candidato generativo. Compatibilidad, tiempo y memoria deben medirse por separado; la supuesta necesidad universal de GPU no está demostrada aquí.

Detalle: `docs/102_FASE_1B_CORRECCIONES.md`; estado en `docs/100_CORRECCIONES_AUDITORIA_CIENCIA_20261015.md`. Las entradas propias y agregados están identificados en el manifiesto; la decisión no constituye una prueba de superioridad frente a una familia de métodos no evaluada.
