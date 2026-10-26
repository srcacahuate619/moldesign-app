---
titulo: "GO de auditoría: hay candidatos a revisar la protonación, no errores confirmados"
entradilla: "Sobre 116 complejos, la heurística marca 64 ligandos neutros con grupos ionizables. El GO es descriptivo: no estima pKa, no valida protonación y los recuentos del sitio no son exhaustivos."
---

**GO de auditoría sin gate de eficacia.** Se dimensiona una necesidad de revisión de estados químicos. No se corrige la protonación ni se demuestra un efecto sobre docking o energía libre.

## Por qué se hizo

El pipeline experimental declaraba protonación del receptor heredada del PDB de entrada. Para transferir un sistema hace falta conocer sus estados, y la presencia de hidrógenos no prueba que sean apropiados para las condiciones de uso.

## Qué se midió

Se leyeron PDB y SDF de la partición de entrenamiento: presencia de H, carga formal y grupos reconocidos por SMARTS. El pH 7,4 motiva la revisión; no se ejecutó un predictor de pKa ni una enumeración validada de estados.

El archivo `metrics.json` está vacío. El agregado real está en `metrics_auditoria.json`, que conserva la etiqueta interna REC-04a. El ID de este experimento y de este paper sigue siendo REC-04.

## Qué pasó

Resultados archivados de la auditoría sobre 116 complejos:

| Indicador | Complejos | Alcance |
|---|---:|---|
| Registros de H presentes en el receptor | 116 | Presencia según el contador; no corrección del estado |
| Algún grupo ionizable reconocido | 87 | Heurística SMARTS |
| Ligando neutro con grupo que activa la revisión | 64 | Candidatos a revisión; no errores confirmados |

No se usa el conteo histórico de histidinas o titulables próximos como inventario completo del sitio. El instrumento examinaba el primer registro de cada residuo, y la ausencia de centro podía acabar como un cero geométrico.

## Qué dice y qué no dice

La auditoría conserva señales para revisar la decisión química. No demuestra que todos los candidatos deban ionizarse ni que el receptor esté bien protonado por contener H. Tampoco midió cuánto cambia el ranking, la calidad del sistema transferido o un cálculo de energía libre. La hipótesis narrativa de una causa principal de fallo no fue contrastada por esta auditoría.

## Correcciones

**Vigentes al 2026-10-22.**

- **SCI-B-152:** el primer registro por residuo no es la distancia mínima de todos sus átomos. La falta de centro tampoco es una ausencia demostrada de residuos próximos. Se retiran los conteos como medida exhaustiva y la conclusión de que el receptor estaba «mejor de lo temido» basada en ellos.

Detalle: `docs/102_FASE_1B_CORRECCIONES.md`; estado en `docs/100_CORRECCIONES_AUDITORIA_CIENCIA_20261015.md`. No comprobado por mí: un inventario corregido desde estructuras y centros originales, ausentes aquí. Recontarlo sería otra unidad de análisis, no una corrección silenciosa del sello.
