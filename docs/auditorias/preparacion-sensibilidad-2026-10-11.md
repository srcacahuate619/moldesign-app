# Preparación: sensibilidad medida el 2026-10-11

Producto `f183e0af`. Experimento FEP-09-SENSIBILIDAD, decisión
**INCONCLUSIVE**, preregistro `9cdd0eab826bbbbe10d9b2469c52fbd0a0cf1638`.
127 intentos confirmatorios, 127 auditorías,
0 rechazos anteriores y
0 fallos. Camino B respetar, receta
B versión 1, Meeko 0.7.1, Vina 1.2.7, 8/9/42, pH 7,4, tres cápsulas CPU=4.
No se cambió el producto; no hay parches en este expediente.

## FEP09-P01 — El comprobador de origen no reconoce la receta de modo B

**Cobertura declarada: sí. Severidad propuesta: P1.**
Preparación declara geometría respecto al ligando cuando el origen es
comprobable. El origen existe y su receta respetando coincide, pero la
comprobación usa receptor_recipe_hash de modo automático. Se pierde contexto
de distancias, puentes de agua, secuencia y otras medidas; se usa la caja.
Es una discrepancia de contratos de hash, no evidencia de manipulación del
archivo ni un fallo de docking.

Reproducción mínima: `cdk2__baseline__0`.
Task original: `b85d23a6-55f1-47ed-a4dc-dd82ff82edd4`.
Entrada: `4ac4621d1592644ec5ef81e5309ab90773e7f29335a86f204fceb358e86eb066`.
Raw normalizado: `15d1e509d7951ca45ea266d51a627d5f452dcf0bb5bd48751ae57eb29e28ab69`.
Receptor: `c359de55ebe3a134edcf1d2f75c989f7f86a0564bc48651abbca71ed3f09410c`.
Receta B registrada y recalculada: `c6fea531565d2ef11917c2338198f8b982225eb0efd69a502ac59fca007ee644`.
Receta automática sin marca de H contradictorios:
`60cdf37b8d15046c175e36fad693af6b58c0aaf851d24c15f73708ce31251041`.

Solicitud y respuestas exactas en
`scripts/artifacts_science/FEP-09-SENSIBILIDAD/_work/shard-0/evidence/cdk2__baseline__0/`:
upload_request.json, preflight_request.json, submit_request.json,
projection.json, result_metadata.json y preparacion.json.
La llamada final es `POST /evaluation/dossier/{molecule_id}/preparacion`,
con projection.json, después del status SUCCESS y result persistido.
Archivos originales se obtienen del clon PLB fijado; no se distribuyen aquí.

Esperado: `entorno.referencia` REGISTRADO tras reconocer la receta B.
Observado: `NO_EVALUADO`,
`El archivo de origen no es el que preparó el receptor de esta corrida (la receta no coincide): las distancias se miden desde la caja.`.
Contratos del producto leídos: preparer_respetando.py::receta_respetando y
contexto_estructural.py::origen_comprobado. La verificación stdlib conserva
los documentos canónicos y hashes relevantes en verification.json.

## Límites, sin presentarlos como defectos de contrato

| ID | Intervención y requisito | Cobertura declarada | Severidad |
|---|---|---|---|
| FEP09-L01 | Cadena borrada antes de upload, receptor.cadenas_excluidas | Registra exclusión hecha por el preparador, no reconstruye una cadena ausente del origen | Sin severidad de bug; limitación de alcance |
| FEP09-L02 | Metal/cofactor borrado antes de upload, entorno.metales_cofactores | Diff del origen recibido frente a preparación; no origen histórico no aportado | Sin severidad de bug |
| FEP09-L03 | Agua puente borrada antes de upload, entorno.aguas | No infiere agua ausente del archivo recibido ni su carácter estructural | Sin severidad de bug |
| FEP09-L04 | Protonación local de receptor B, receptor.protonacion | Conserva estado del usuario; expresamente no valida pH ni His/Asp/Glu del sitio | Sin severidad de bug |
| FEP09-L05 | Tautómero alternativo y especie opuesta | Proxies sin población y pKa individuales independientes; no prueban categorías estrictas | Déficit del experimento, no bug probado |
| FEP09-L06 | Identidad de la construcción experimental de TYK2 | El auditor no declara comparación con secuencia/constructo del ensayo | Sin severidad de bug; fuente pública no resuelta |

Para cada intervención ejecutada: archivos, hashes, task_id, requisito esperado,
estado base, estado observado y clasificación en per_complex.jsonl,
metrics.json::comparisons y evidence del shard correspondiente. Una revisión
genérica ya presente no se cuenta como detección. No se propone parche con
estas tasas ni se equipara no detección con error de los autores de PLB.

## Tabla y condiciones

| Categoría | n | Auditor | Detectado antes | IC 95 % ruta | Decisión / alcance |
|---|---:|---:|---:|---|---|
| agua_puente_retirada | 9 | 0 | 0 | [0,000; 0,336] | límite |
| cadena_del_sitio_ausente | 1 | 0 | 0 | [0,000; 0,975] | límite |
| especie_del_ligando | 0 | 0 | 0 | no estimable | INCONCLUSIVE |
| especie_opuesta_proxy | 7 | 1 | 0 | [0,004; 0,579] | proxy |
| estereo_sin_asignar | 3 | 3 | 0 | [0,292; 1,000] | INCONCLUSIVE |
| hueco_en_el_sitio | 15 | 15 | 0 | [0,782; 1,000] | GO |
| metal_o_cofactor_retirado | 1 | 0 | 0 | [0,000; 0,975] | límite |
| protonacion_del_sitio | 5 | 0 | 0 | [0,000; 0,522] | límite |
| tautomero_alternativo_proxy | 13 | 13 | 0 | [0,753; 1,000] | proxy |
| tautomero_minoritario | 0 | 0 | 0 | no estimable | INCONCLUSIVE |

Falsa alarma inocua: 4/555
(0,72 %); acuerdo de bases 99,55 %.
Cada número conserva su condición y n. El informe público detalla los
proxies, el brazo C, las exclusiones y la concordancia FEP-08.

## Reproducir sin modificar el experimento

Crear cápsula QA nueva (por ejemplo agente 4, puerto 18014) desde este
worktree; usar export externo con --out y --no-build, sin tauri:build.
Después, con el clon OpenFF verificado:

```powershell
node scripts/qa_sandbox/sandbox-up.mjs --agente 4 --capsula D:/moldesign-build/.worktrees/.sandbox/fep09-repro --out D:/moldesign-build/frontend/out --no-build --vina-cpu 4
python scripts/fep09_reproduce.py --case cdk2__baseline__0 --capsule D:/moldesign-build/.worktrees/.sandbox/fep09-repro
python scripts/fep09_reproduce.py --case cdk2__hueco_en_el_sitio__0 --capsule D:/moldesign-build/.worktrees/.sandbox/fep09-repro
```

Los resultados nuevos se escriben en tmp/fep09-reproductions, nunca en
artifacts_science. Usar Python 3.14 para el arnés; el backend de QA usa
python-embed 3.11.9. Las credenciales de la cápsula no se versionan ni se
imprimen. No se ha reproducido esta muestra una segunda vez: el comando
está preparado para la revisión independiente.
