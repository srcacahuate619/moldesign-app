# Revision acotada del ensamble - 2026-09-17

Alcance: backend, sin build, sin activar MM-GBSA experimental, sin cambiar
pesos, energias, generacion de conformaciones ni seleccion de poses.
Se inspeccionaron implementaciones, contratos y registros experimentales locales;
NO se repitieron los benchmarks cientificos ni se verificaron todos sus hashes.

## Dos mecanismos diferentes

1. Ensemble conformacional: `chem/conformer_ensemble.py` genera conformaciones;
   `services/docking/ensemble.py` ejecuta Vina por conformacion, agrupa las poses
   y entrega las de menor energia observada. Conserva indice de conformacion.
   K=1 delega en el generador habitual. Esto NO es un ensemble de receptores.
2. Stacking M4: `scoring/engine.py`, `rescoring/artifacts/stacking_weights.json`
   y `artifacts/sci_config_registry.json`. El contrato de release declara
   Vina=0.25, XGB=0.75, GNN=0, CL-GNN=0; familias con pesos comunes.
   `services/targets/calibracion.py` declara vacio el conjunto de familias
   calibradas. No se deben presentar los pesos como calibracion por receptor.
   Si falta un componente, el engine renormaliza y declara degradacion/pesos
   efectivos; no se ha medido aqui la utilidad predictiva de esa degradacion.

## Evidencia existente y sus limites

Fuentes originales leidas, sin modificar archivos sellados:

- `scripts/artifacts_science/MF-33-A3/README.md`: en el estrato COLOCACION
  (33 complejos), cobertura del oraculo RMSD <=2 A: ensemble 26/33 frente a
  19/33 con reinicios de un conformero, igualando corridas y poses, CPU
  aproximada (A3/B=1.196). Discordancias 7 contra 0; p=0.0156.
  Es cobertura: el oraculo conoce la estructura experimental. No es un
  porcentaje de recomendaciones correctas ni valida el pipeline actual.
- `scripts/artifacts_science/MF-33-B-RET-R2/metrics.json`: 48 complejos;
  top-1 single 20/48, ensemble 24/48, McNemar p=0.34375; top-5 26/48 frente
  a 35/48, p=0.003906; oraculo 26/48 frente a 41/48. Configuracion:
  exhaustiveness=8, num_modes=9, seed=42, caja=25 A, cpu=1.
  El registro declara expresamente que R2 NO es confirmacion ciega.
  No demostrar mejora top-1 no demuestra equivalencia o ausencia de efecto.
- `scripts/artifacts_science/MF-33-H-COR/README.md`: 8181/8224 poses flexibles
  PB-valid, CONDICIONAL a reconstruccion canonica de hidrogenos conservando
  coordenadas pesadas. No demuestra exactitud de pose, union ni superioridad
  de un brazo. Sustituye cifras historicas contaminadas por reconstruccion.

La evidencia apoya diversidad/cobertura bajo esos protocolos. Queda demostrar
transferencia al generador, preparacion, binarios y parametros actuales, y
ventaja de la seleccion final en un conjunto externo no usado para ajustar.
No se audito exhaustivamente aqui el solapamiento con entrenamiento de XGB/GNN.

## Hallazgos y correccion

| ID | Severidad | Problema | Estado |
|---|---|---|---|
| ENS-01 | ALTO | El agrupador atribuia a todas las poses la procedencia de la primera corrida sin verificar receptor, version, semilla ni protocolo de las restantes. | Corregido: desacuerdos abortan con campo e indice identificados; no se silencian como fallo parcial. |
| ENS-02 | ALTO | Se perdian engine_efectivo, exhaustiveness_efectiva y num_poses_solicitadas al agrupar. El dossier podia recuperar lo pedido y ocultar una diferencia con lo ejecutado. | Corregido: se preservan tras comprobar homogeneidad. |
| ENS-03 | MEDIO | parsing_source queda con el valor de la ultima corrida y no se conserva conversor_estructural en el resultado agrupado. Puede ocultar conversiones mixtas. | Pendiente: procedencia por corrida/pose con contrato compatible, sin fingir una fuente unica. |
| ENS-04 | MEDIO | El agrupado no tiene SDF colectivo: poses_file_path=None es deliberado para no apuntar a coordenadas de una sola corrida. | Limitacion: comprobar recuperacion exacta de la pose para MM-GBSA; nunca generar desde SMILES como sustituto. |
| ENS-05 | ALTO, riesgo por verificar | Generacion RDKit adicional dentro de async, almacenamiento por hash/indice y dependencia de metadata sin identidad completa por corrida. | Pendiente prueba de bloqueo/concurrencia y trazabilidad de entradas; esta revision NO demuestra una colision en produccion. |

ENS-01 era reproducible inyectando dos DockingResult con receptores o protocolos
distintos. La ruta normal intenta compartir parametros; la guardia protege el
limite del agrupador ante cambios, regresiones o evidencia incompleta. No se
ha demostrado que usuarios hayan sufrido esta mezcla.

La guardia compara receptor_sha256, vina_version, vina_random_seed,
engine_efectivo, exhaustiveness_efectiva y num_poses_solicitadas. Un dato conocido
no puede cubrir el desconocido de otra corrida. Si todas carecen de un campo,
se conserva None por compatibilidad; eso NO certifica su identidad. Distintas
rutas con el mismo hash se admiten. Los errores ordinarios de una conformacion
siguen permitiendo cobertura parcial y la cancelacion se propaga.

## Verificacion

- Antes del cambio: 9 fallos reproducibles y 28 pruebas correctas en la suite
  conformacional ampliada.
- Despues: 113 passed, 1 skipped en ocho archivos (ensemble, protocolo,
  piscina/dossier, stacking, no-fabricacion, calibracion, avisos y dossier).
- Se prueban incompatibilidades, ausencia asimetrica de huella, conservacion
  de parametros, rutas diferentes con mismos bytes y cancelacion. Las pruebas
  existentes conservan energias, ranking estable, K=1 y degradacion parcial.
- Regresion global: 2427 passed, 10 skipped, 1 failed (H15 frontend
  preexistente), 14 warnings, 243.06 s. Log: hardening-ensemble-full.log.
  Ruff F de desarrollo, compileall focalizado y git diff --check correctos.

## Proximo experimento propuesto: ENS-PROD-01

Estado: BORRADOR, no prerregistrado ni ejecutado. Antes de ejecutarlo hay que
cerrar cohorte, tamano/potencia, presupuesto y umbral de relevancia practica.
No mirar el conjunto final para decidir esos valores.

1. Objetivo: comprobar transferencia del beneficio de cobertura al pipeline
   actual y si llega a las poses entregadas. No evaluar actividad biologica
   con etiquetas de RMSD. Priorizar ligandos pequenos no covalentes con
   estructuras experimentales; metales/cofactores como estratos declarados.
2. Datos: cohorte publica independiente de MF-33 y de ajustes previos; documentar
   solapamiento de diana, ligando/serie y entrenamiento de modelos. Hashes,
   licencias, decisiones de preparacion y exclusion registrados antes de correr.
3. Brazos: pipeline actual K=1; K=30; y reinicios desde un conformero con
   presupuesto comparable. Fijar binario, receptor, caja, protonacion, poses
   conservadas y politica de semillas. Registrar CPU y tiempo; no confundir
   beneficio de presupuesto con diversidad.
4. Primario propuesto: acierto top-1 con RMSD pesado corregido por simetria <=2 A
   Y validez fisica bajo reconstruccion de H explicita. Secundarios: top-5,
   cobertura del oraculo, fallos, abstenciones, coste y fraccion evaluable.
   Referencia cristalina accesible SOLO al evaluador, nunca al selector.
5. Analisis: comparaciones pareadas por complejo, intervalos de confianza y
   desglose por diana; contemplar dependencia entre complejos relacionados.
   Todos los casos preincluidos permanecen en el denominador. Predefinir
   tratamiento de fallos y multiplicidad si se prueba mas de una hipotesis.
6. Gate: limite inferior del intervalo para la diferencia primaria superior a
   cero y ganancia practica predefinida, dentro del presupuesto acordado. Si
   solo mejora cobertura, declarar solo cobertura; no promocionar top-1.
7. Stacking se evalua APARTE sobre actividad experimental compatible: Vina,
   XGB ligand-only y combinacion actual, datos separados por serie/diana/fecha,
   precision entre primeros candidatos y cobertura, incluida degradacion.
   No modificar pesos ni entrenar con el conjunto final.
8. Entrega: manifiesto, resultados por complejo, fallos completos y comando
   reproducible offline en entorno limpio. Cambios cientificos posteriores
   requieren decision explicita y nuevo examen independiente.

Orden sugerido de continuacion: resolver procedencia mixta/pose exacta,
congelar ENS-PROD-01 y ejecutar piloto tecnico fuera del holdout; despues ensayo
final. Continuar MM-GBSA en paralelo solo como candidato experimental, con sus
gates de parametrizacion, complejos completos y utilidad aun abiertos.


## Continuacion: identidad de registros y conversiones (2026-09-17)

ENS-03 queda corregido para NUEVOS ensembles: cada pose conserva
`source_provenance` con rank original, ruta SDF de su corrida, parsing_source
y metadata del conversor. La renumeracion de la piscina no altera esos datos.
Un agrupado con distintos parsers declara `mixed`; el conversor global solo
se conserva cuando todas las corridas coinciden. No se recupera metadata de
corridas historicas que nunca la guardaron.

Justificacion del contrato aditivo: `DockingPose.source_provenance` es metadata
opcional, persistida dentro del JSON existente, sin migracion SQL. Los registros
historicos cargan con None. `DockingResult.parsing_source` admite `mixed` para
no atribuir toda la piscina al ultimo parser. No cambian scores, algoritmos,
parametros cientificos ni coordenadas. La UI no se modifico; el backend expone
los nuevos datos para su futura presentacion.

ENS-06 (ALTO, corregido): el parser SDF omitía registros sin afinidad y
renumeraba los siguientes. Vina asocia la lista resultante por posicion con los
bloques PDBQT: un primer registro sin afinidad podia asignar la energia del
segundo a la geometria del primero. La correccion rechaza el conjunto parcial
de scores SDF y permite seguir los respaldos existentes hacia conversion o
PDBQT. Un archivo completo conserva exactamente sus valores y orden. No se
reconstruye una afinidad ausente ni se cambia una formula.

ENS-04 sigue abierto: source_provenance NO certifica por si sola correspondencia
atomica ni integridad de bytes. Todavia no se utiliza para activar MM-GBSA.
Antes de recuperar SDF por rank de origen se exige comprobar hash del artefacto,
identidad quimica y correspondencia geometrica con el bloque PDBQT entregado,
sin conversion desde SMILES ni herencia de la pose de otra conformacion.
No se ha cerrado tampoco la validacion externa ENS-PROD-01: sigue como borrador.

Pruebas: seis fallos reproducidos antes del cambio y una prueba positiva; luego
129 passed, 1 skipped en ocho suites, incluidos SQLite real, contratos de
respuesta/PDF, Open Babel y MM-GBSA. Se cubren huecos de metadata al principio,
en medio y al final, y propiedades truncadas sin valor; parsers mixtos/homogeneos; rank original tras ordenar y
compatibilidad de registros antiguos. Resultado global en HARDENING_1.0.1.md.
Ruff F detecto un F841 preexistente en test_sqlite_roundtrip.py:194, fuera del
cambio (variable mol). No se corrigio ni se oculto en esta revision.

El separador $$$$ se procesa antes de cualquier propiedad pendiente: un valor
ausente no puede absorber el fin del registro ni mezclar metadata entre poses.
Dos pruebas adicionales reprodujeron esa variante antes de corregirla.

Verificacion global de esta continuacion: 2434 passed, 10 skipped, 1 failed
(H15 frontend preexistente), 14 warnings, 239.96 s. Esa corrida comenzo antes
del ultimo ajuste de delimitadores; despues de ese ajuste se verificaron las
129 pruebas focalizadas indicadas arriba. No se afirma una suite global nueva
sobre ese ultimo ajuste. Detalle en HARDENING_1.0.1.md.
