# FEP-09-SENSIBILIDAD — prerregistro, 2026-10-11

Se fija y commitea antes de la primera evaluación. Producto bajo medida:
`f183e0af`. La rama del experimento puede avanzar; el diff de backend,
frontend, rescoring y tools respecto a ese commit debe permanecer vacío.

## Hipótesis y unidades

La auditoría por API de una corrida reacciona a defectos dentro de su cobertura
declarada. Un caso es una diana, el primer registro legible de ligands.sdf y
una intervención única. No se afirma sensibilidad a problemas reales de
preparación. Se conserva la salida completa de cada requisito, no sólo el
veredicto global. Fuentes independientes: geometría de PDB/SDF y RDKit
2025.09.6 (sin importar las reglas del producto).

## Población y ejecución

`inventory.json` fija nombres, archivos, hashes, selección y parámetros exactos.
PLB: commit `fd88824f9114244f95a14b485e6d6c96c1de716d`, clon en
`E:\MolDesign-science\openff-plb`, datos CC BY 4.0, código MIT.
De los 21 nombres de targets.yml, 15 tienen ambos archivos. Se excluyen
bace, bace_hunt, bace_p2, galectin, jnk1 y pde10 por falta de archivos prescritos.
No se sustituye ninguna diana por su resultado.

Camino B, `modo_preparacion=respetar`, pues son receptores preparados para
RBFE. Cada caso se sube de nuevo, incluidas las tres líneas base: así se
mide preparación independiente y no sólo releer la misma caché. Sin fuente
PDB alternativa ni cambios de estado de protonación impuestos al receptor
base. Las variantes temporales viven en tmp de cada cápsula y no se versionan.
El upload usa los bytes de un archivo absoluto. La API recibe una cadena
primaria determinada por el mayor número de átomos a ≤6 Å de la referencia
(desempate alfabético); las otras cadenas siguen dentro del archivo base.

Caja de 20×20×20 Å, centroide pesado del primer ligando, fija por diana para
todos los brazos. Pipeline normal explícito con sus etapas por defecto:
validation, properties, sa_filter, conformer, docking, xgb, clgnn. Vina 1.2.7,
exhaustividad 8, 9 poses, semilla 42; pH 7,4. Tautómero en modo por defecto
canónico. No se cambia a conservar entrada para facilitar detección.
`preflight → submit → status → result → preparacion`, projection construida
según accept_evaluation_runtime.py y con input_smiles específico del caso.
Se guarda y contrasta la configuración efectiva, hashes y versión del motor.

Backend: python-embed 3.11.9 desde el producto congelado, cápsulas QA de
agentes 1–3 (son instancias, no delegación a agentes), VINA_CPU=4 cada una.
Frontend externo ya construido y --no-build; no se ejerce su UI. Piloto:
cdk2 completa. Datos del piloto se guardan aparte y **no** entran en la
medición confirmatoria. No se cambian gate ni selección según el piloto.
Correcciones técnicas del arnés se anotan antes de la fase completa.

## Catálogo y mínimos fijados

| Categoría | n inventariado | Requisito | Mínimo / expectativa | Cobertura para gate |
|---|---:|---|---|---|
| hueco_en_el_sitio | 15 | receptor.huecos | ABSTENCION, riesgo mayor que base | Declarada |
| estereo_sin_asignar | 3 | ligando.estereoquimica | REVISAR o ABSTENCION, riesgo mayor que base | Declarada, n insuficiente |
| cadena_del_sitio_ausente | 1 | receptor.cadenas_excluidas | REVISAR o ABSTENCION, riesgo mayor que base | No declara reconstruir cadena borrada antes de upload B; límite |
| metal_o_cofactor_retirado | 1 | entorno.metales_cofactores | ABSTENCION, riesgo mayor que base | No declara origen previo al upload B; límite |
| agua_puente_retirada | 9 | entorno.aguas | REVISAR o ABSTENCION, riesgo mayor que base | No declara agua borrada antes de upload B; límite |
| protonacion_del_sitio | 5 | receptor.protonacion | REVISAR del caso, cambio respecto a base | No valida protonación del usuario en B; límite |
| tautomero_minoritario | 0 verificados | ligando.tautomero | REVISAR o ABSTENCION, riesgo mayor que base | Declarada; sin población independiente, INCONCLUSIVE |
| especie_del_ligando con pKa individual y distancia >3 | 0 verificados | ligando.especie | REVISAR o ABSTENCION, riesgo mayor que base | Declarada; sin pKa individual independiente, INCONCLUSIVE |
| tautomero_alternativo_proxy | 13 | ligando.tautomero | REVISAR o ABSTENCION, riesgo mayor que base | Diagnóstico; no prueba minoría |
| especie_opuesta_proxy | 7 | ligando.especie | REVISAR o ABSTENCION, riesgo mayor que base | Diagnóstico; no prueba distancia de pKa >3 |
| hueco_lejano | 10 | receptor.huecos | Puede pasar a REVISAR, nunca bloquea por el corte sembrado | Control espacial |
| seriales_renumerados | 15 | Todos | Estados y flags de riesgo sin cambios | Control inocuo estricto |

El corte elimina tres residuos consecutivos observados, de una sola cadena
principal, cuyos enlaces C–N originales son continuos. Se exige una distancia
de ≤6 Å del ligando tanto del corte como de al menos un extremo superviviente,
y C–N nuevo >2 Å. No se usan funciones del producto para generar o seleccionar.
En el hueco lejano, residuos y extremos quedan a >15 Å de la superficie de
la caja. Cambiar a REVISAR es una consecuencia legítima de extremos nuevos,
declarada antes de medir: se excluye sólo este cambio de su falsa alarma.

La cadena ausente es la primera cadena secundaria que contribuye a ≤6 Å.
La especie eliminada es el metal/cofactor más próximo a ≤6 Å. El agua es la
primera por distancia que tiene O a ≤3,5 Å de N/O del ligando y proteína y
distancia ligando >1,8 Å. El estado de protonación se cambia en una His
con exactamente un H de anillo o Asp/Glu con O a ≤3,5 Å; se declara geometría
del H agregado y nombre de residuo cambiado. No se afirma carácter catalítico
sin fuente. El centro estereogénico eliminado es el primero asignado de RDKit.

El alternativo tautomérico es el primero por (ScoreTautomer, SMILES), distinto
de la entrada. Es un proxy de representación y ambigüedad; **una puntuación
RDKit no es una población**. La especie proxy neutraliza el primer carboxilato
o amonio alifático del archivo; no se le atribuye pKa individual. Ambas
limitaciones están cerradas antes de correr y no se resolverán con reglas
del propio producto. Se publican respuestas, pero no pasan por categorías
estrictas que requieren evidencia externa ausente.

## Brazo C

Fuentes abiertas el 2026-10-11: incidencias
[OpenFF #101](https://github.com/openforcefield/protein-ligand-benchmark/issues/101)
y [#112](https://github.com/openforcefield/protein-ligand-benchmark/issues/112).
El inventory guarda cuatro preocupaciones (tnks2, eg5, thrombin, tyk2), sus
paráfrasis y registros encontrados en el commit. Si una no tiene archivo
correspondiente, no se ejecuta y se declara. Son observaciones públicas y
preguntas pendientes, no errores establecidos. No se transfieren afirmaciones
de otra versión del benchmark al commit fijado. Con menos de cinco casos
verificables, brazo C **INCONCLUSIVE**; no se calculan tasas con n<10.
El artículo [Hahn et al., 2022](https://doi.org/10.33011/livecoms.4.1.1497)
se abrió en PDF y sirve de contexto y atribución, no de etiqueta de defecto.

## Análisis y gate inmutables

Riesgo: REGISTRADO/PASA/NO_APLICA=0, REVISAR=1,
ABSTENCION=2. NO_EVALUADO/NO_DISPONIBLE y otros estados de ausencia no
son detecciones de un defecto sembrado. Riesgo por bloquea=2,
revision no rutinaria=1. Detección confirmatoria exige requisito esperado
presente, mínimo alcanzado y riesgo **estrictamente mayor** que su base 0.
Una alerta genérica ya presente no cuenta. Se conserva la saturación de base
en su propia columna; no se quita del denominador para mejorar sensibilidad.
Rechazo antes del auditor cuenta como `detectado_antes` separado, si es
un rechazo explícito de la entrada (HTTP 400/409/422 con cuerpo registrado),
no una caída, timeout, 401, 404, 500 o tarea FAILURE. Sensibilidad principal
del auditor y sensibilidad de la ruta (incluye rechazos) se muestran separadas;
el gate aplica a la ruta completa, evitando penalizar protección anterior.

Sensibilidad por categoría y Clopper–Pearson exacto bilateral 95 %. Se informa
el n nominal, evaluable, rechazado antes, fallo de infraestructura y saturado.
El denominador para el gate es todo caso aplicable confirmatorio; fallos de
infraestructura no se imputan como ausencia de sensibilidad, y su existencia
hace la categoría INCONCLUSIVE salvo NO_GO ya demostrado con todos ellos
como detectados. Para categorías declaradas con n≥8: GO si límite inferior
≥0,5 y falsa alarma de controles inocuos ≤0,10; NO_GO si falla. Categorías
declaradas con n<8 son INCONCLUSIVE. Global NO_GO si alguna falla; GO sólo
si todas las categorías declaradas pasan; de otro modo INCONCLUSIVE.

Falsa alarma = requisitos de riesgo cuyo estado o flag bloquea/revisión del
caso cambian respecto a base sin intervención pertinente / requisitos
comparables. No se cuentan diferencias de texto con UUID, timestamp, hash,
número de corrida o etiquetas de entrada. Se publican también estado solo
y los cambios colaterales de las variantes. Ruido: acuerdos por requisito
entre base 0–1 y 0–2; se declaran estados, flags, hashes de receptor y
microestados. No se atribuye una discrepancia a un motor sin probarlo.

Unión ordenada por case_id, sin sobrescribir shards. Cada shard lleva su
directorio propio `_work/shard-N/`; piloto `_work/pilot/`. Reanudar omite
case_id ya terminal, nunca reescribe evidencia. Analizador determinista con
autotest positivo/negativo, rechazo, ruido, casos saturados y límites del IC.
Concordancia FEP-08 descriptiva: cdk2/thrombin numeración frente a corte físico,
tnks2 sitio entre cadenas; no es gate.

Parada: si >30 % de intentos fallan por infraestructura, se para y se publica
INCONCLUSIVE, con fallos incluidos. Se evalúa el umbral por corrida del piloto
y de cada shard; tras alcanzar el primer fallo se detiene si rebasa el umbral,
sin esperar una cohorte favorable. Timeout de tarea 3600 s. Si el piloto
estima >4 días, se fija antes de la fase completa una reducción determinista
de dianas o se para; no se toca el gate. No hay presupuesto artificial de
tokens o tiempo que sustituya el trabajo autorizado.
