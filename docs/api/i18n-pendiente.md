# I18N: texto que se conserva sin traducir

## Recorrido de QA

El 2026-10-04 se ejecutó la cápsula del agente 2 con `MOLDESIGN_I18N_REPORT=1` y `Accept-Language: en`. Se recorrieron evaluación, preflight Batch, catálogo de receptores, vista previa del dossier y exportación ZIP. El reporter no encontró mensajes humanos en español sin plantilla o entrada: `i18n_faltantes.jsonl` no se creó, lo que equivale a cero filas.

El dossier de la corrida `a67bfc96-b6c7-44fe-bbdd-89918e9cfb82` fue leído completo en inglés. El ZIP declara y contiene 28 archivos; el verificador no encontró errores ni avisos.

## Identificadores preservados

- El valor de modelo registrado `v0.6 XGBRanker rank:pairwise (selector oficial de Ruta C)` se conserva íntegro como identidad técnica del selector. Traducir un fragmento de ese valor produciría un identificador distinto del que guardó la corrida. La frase entre paréntesis es parte del valor serializado, no prosa generada para la interfaz.
- Nombres de casos, moléculas, cohortes y receptores; SMILES; IDs de PDB, cadenas y residuos; códigos de estado y razón; nombres de motores y modelos; versiones, hashes, rutas, fechas, semillas, cantidades y unidades permanecen exactamente como fueron registrados.

## Ruta no ejecutada

La ruta de péptidos con ESMFold no se ejecutó. La descarga de pesos requiere autorización explícita del propietario y no forma parte de esta verificación. No se presenta como una traducción pendiente: su texto visible se declara experimental y sus cautelas tienen traducción inglesa.
