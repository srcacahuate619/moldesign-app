---
titulo: "GO de medición: las políticas retienen inventarios distintos, sin medir su calidad"
entradilla: "PREP-01 compara tres rutas sobre 116 estructuras y conserva GO descriptivo. Sus conteos de sitio son proxies por especie; no identifican qué copia local desapareció ni validan una política de preparación."
---

**GO de medición, sin gate de calidad.** Se documentan diferencias entre políticas históricas. No se cambia el producto ni se certifica preparación para un cálculo posterior.

## Por qué se hizo

El dataset sobre el que se evaluaba la ciencia y las rutas del producto no aplicaban la misma política de heteroátomos. Además, una conservación medida contra PDBBind ya limpiado no responde qué se retiró de la estructura depositada.

## Qué se midió

La fuente común fue el depósito RCSB de cada miembro de MF-13. Se usó la cadena mayoritaria y el vocabulario de especies 1.0.0. Se compararon el receptor del dataset, el filtro histórico de docking aplicado sin Meeko y una aproximación de la ruta MMGBSA que conserva registros ATOM.

Se descartó el propio ligando cristalográfico mediante solapamiento dentro de 0,5 Å: retirarlo del receptor no es una pérdida de cofactor. No se calcularon docking, cobertura ni energías. Las estructuras originales no están disponibles en este worktree para repetir el conteo.

## Qué pasó

Número de complejos marcados por el contador, sobre los mismos 116 miembros:

| Ruta histórica | Disminuye algún metal global | Disminuye algún cofactor conocido global | Proxy de especie del sitio disminuida |
|---|---:|---:|---:|
| Dataset experimental | 11 | 8 | 22 |
| Filtro de docking histórico | 55 | 5 | 41 |
| Modelo de retirada de HETATM para MMGBSA | 55 | 8 | 41 |

En la clasificación de aguas, el dataset marca conservación en 115 complejos y el filtro de docking marca retirada total en 115. Son observaciones de esas rutas y fuentes históricas, no un censo del catálogo vigente.

## Qué dice y qué no dice

El proxy de sitio combina dos hechos: la especie disminuye en el inventario global y alguna copia estaba cerca del ligando. No demuestra que la copia retirada fuera la próxima. Una retirada remota de la misma especie puede activar el aviso. No se midió cuánto sobrecuenta este proxy.

La retención tampoco prueba función: un cofactor, un aditivo y una copia desplazable requieren decisiones distintas. Menos retiradas observadas no equivale a mejor preparación. La elección de cadena y las políticas de un catálogo o receptor propio pueden diferir de este barrido.

## Correcciones

**Vigentes al 2026-10-22.**

- **SCI-B-140:** se retira la lectura del proxy como número exacto de pérdidas locales funcionales. Las filas resumidas no permiten emparejar las copias.
- **SCI-B-141:** la copia conservada del filtro coincide con el hash posterior al mantenimiento, no con el productor original atribuido a los resultados. Se conserva la trazabilidad declarada de ese cambio, sin afirmar recuperación del filtro original ni recalcular con el módulo vivo. No comprobado por mí: los bytes del módulo de reporte original que la corrección describe como conservados por separado.
- **SCI-B-142:** se retiran «mejor preparación» y la atribución causal a una lista positiva. El análisis sólo describe retención bajo las políticas comparadas.

Detalle: `docs/102_FASE_1B_CORRECCIONES.md`; estado en `docs/100_CORRECCIONES_AUDITORIA_CIENCIA_20261015.md`. No comprobado por mí: reproducción del barrido desde los depósitos y el filtro original. Los conteos publicados son los archivados, con estos límites.
