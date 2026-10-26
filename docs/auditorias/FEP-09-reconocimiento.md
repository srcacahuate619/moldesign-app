# FEP-09: reconocimiento antes de medir

Producto congelado: `f183e0af`. Fecha: 2026-10-11. No se ha ejecutado una
corrida ni consultado Preparación para este experimento.

El contrato se leyó en `backend/services/dossier/preparacion.py` y sus
dependencias de contexto. La salida contiene claves estables por requisito,
`estado`, `imprescindible`, dato y razón. El veredicto global tiene techo
REVISIÓN. La unidad del ensayo es el requisito de una corrida.

| Requisitos | Qué declara | Defecto independiente que puede moverlo |
|---|---|---|
| receptor.identidad, receptor.cadenas, receptor.caja | Hash, cadenas y caja registrados, no identidad experimental | No confundir cambios de hash con detección |
| receptor.huecos | Cortes físicos C–N entre residuos consecutivos, proximidad al ligando y poses | Borrar tres residuos contiguos cerca; lejos pide revisión por extremos nuevos |
| receptor.cadenas_excluidas, receptor.recorte | Proteína del origen que la preparación excluye y recorte de bolsillo | Cadena eliminada antes de subir no está en el origen observado: límite |
| receptor.residuos_retirados, receptor.cadenas_truncadas | Cambios que hizo la preparación | Ninguna reconstrucción de lo eliminado antes de subir |
| receptor.protonacion | Declaración del usuario en B; no valida His, Asp/Glu ni pH del sitio | Cambio local de protonación: límite explícito de B, con respuesta descriptiva |
| receptor.disulfuros, receptor.altlocs | Geometría de S–S y alternativas observadas | No intervenidos en este catálogo |
| receptor.entrada, receptor.confianza_estructural, receptor.campo_de_fuerzas, receptor.seccion_catalogo | Procedencia del archivo, confianza disponible, elementos compatibles y sección | No intervenidos; benchmark no es catálogo del producto |
| ligando.identidad, ligando.ph, ligando.especie | Forma acoplada y criterio de selección de microestado | Forma opuesta a la del curador: diagnóstico; falta pKa individual independiente |
| ligando.tautomero | Ambigüedad, canonicalización y reglas de clases minoritarias | RDKit enumera un alternativo; puntuación no prueba minoría: diagnóstico separado |
| ligando.estereoquimica | Centros sin asignar y estereoquímica conservada | Quitar el primer centro asignado de RDKit |
| ligando.covalente, ligando.campo_de_fuerzas | Señales de enlace covalente y parámetros disponibles | No intervenidos |
| pose.origen, pose.* | Pose, controles físicos, selección y correspondencias serializadas | Se conservan las respuestas; los cambios colaterales no entran al gate |
| entorno.politica, entorno.referencia | Política y referencia declaradas en la corrida | No verifica que el usuario haya conservado el origen completo |
| entorno.metales_cofactores, entorno.aguas, entorno.otras_especies | Diff entre el origen subido y la preparación; proximidad al ligando | Especies borradas antes de subir B: límite de procedencia; no se declara inferir su ausencia |
| entorno.membrana | Segmentos compatibles con membrana, no validación de ensamblaje | No intervenido |
| procedencia.* | Hashes, versiones, semilla, preflight y relación con la corrida | Repeticiones registran reproducibilidad, no sólo el veredicto |

La tabla del encargo usa mínimos amplios para cadenas, agua y metales. En el
camino B, la cobertura declarada es el **diff producido por MolDesign**, no la
reconstrucción del origen anterior a la subida. Se medirán las variantes, pero
una ausencia de señal se clasificará como límite, evitando ampliar retrospectivamente
el contrato para fabricar un defecto. No se añade `source_file`: la API lo
admite para PDBQT (camino C), que este ensayo no usa.

Hay 21 nombres en targets.yml y 15 con ambos archivos prescritos. Las seis
exclusiones y sus motivos constan en inventory.json. Coinciden las 15 dianas
de FEP-08. Sólo se elige el primer registro SDF legible por diana, antes de
mirar resultados, para conservar una unidad estructural independiente por
diana y no inflar n repitiendo un mismo defecto del receptor.

No se ha encontrado una fuente independiente de población para cada tautómero
o pKa individual de los primeros ligandos. Se registran proxies por separado,
sin afirmar que una puntuación RDKit sea energía ni que el estado del curador
demuestre pKa. Las categorías estrictas de minoría y |pKa−pH|>3 tendrán n=0
verificado y serán INCONCLUSIVE. Esta limitación se fija antes de medir.
