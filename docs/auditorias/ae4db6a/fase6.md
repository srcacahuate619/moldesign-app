# Fase 6 — bitácora de corrección y validación científica

Fecha: 2026-09-25. Rama local: codex/audit-phase-6. Padre: c3aa4689c57087f20afd92bef0df678d4eff7cfb (fase 5). Commits de esta fase: 183a57d (preregistro), 3f626c3 (arnés de reproducción) y d570797 (contenciones científicas). No se hizo push ni se alteró main. El trabajo se realizó en D:\moldesign-build\.worktrees\audit-phase-6. Los temporales quedaron en su directorio .tmp de D; se reutilizó el runtime Python y las dependencias frontend de fase 5 mediante junctions, sin instalar nada en C.

## Decisión general

La fase 6 pedía evidencia nueva, no sólo que un test pasara. Allí donde faltan poses de Vina o controles negativos verificables, dejé la afirmación retirada y el sistema en el comportamiento conservador. Los cambios no deben interpretarse como validación de eficacia predictiva. La fase 7 puede partir de d570797; las puertas científicas pendientes quedan identificadas abajo para que el auditor decida cuándo reabrirlas.

## SCORE-007: reproducción del clasificador congelado

Se preregistró el protocolo antes del cálculo en docs/89_FASE6_PREREG_CLASIFICADOR.md. El script scripts/phase6_classifier_holdout.py reconstruyó la matriz original Fase A de PDBBind v2020: 865 complejos, 537 de pool y 328 de holdout; cero exclusiones por falta de entradas. Se verificaron SHA-256 de índice, split, grupos de proteína, metadata, modelo y archivos consumidos. Se usaron los 160 descriptores congelados y poses cristalográficas originales, sin reentrenar ni recalibrar con holdout. La matriz compacta tiene SHA-256 9ee1917995ff6a3b38ebf0f21b076f75b5bee6d6acb2c26a574a70a2f6501851 y el modelo b83a936564036b196b53919c707250c441d49fbd1b9427b15f7ebe48850ea636.

La preparación se hizo con Python embebido 3.11.9 y NumPy 2.4.4. El cálculo de probabilidades se hizo en el contenedor existente moldesign_rescoring del servidor Ubuntu autorizado, con Python 3.10.20, NumPy 1.26.4 y XGBoost 3.2.0. Se transfirieron sólo matriz, script y modelo compactos; los hashes se contrastaron antes de ejecutar. No hubo descarga web ni experimento simultáneo pesado en los dos equipos. Se ejecutaron 2000 bootstrap por clúster proteico, semilla 42.

| Estrato | N | AUC ROC | IC 95 % de AUC | Brier | ECE, 10 intervalos |
|---|---:|---:|---:|---:|---:|
| Holdout completo | 328 | 0.8818 | 0.8292–0.9270 | 0.1370 | 0.0649 |
| Clúster visto en pool | 233 | 0.8852 | 0.8214–0.9388 | 0.1386 | 0.1009 |
| Clúster ausente del pool | 95 | 0.8544 | 0.7408–0.9373 | 0.1332 | 0.1079 |

El AUC completo reproduce el 0.8818 del metadata con diferencia absoluta de 0.0000049. El estrato de 95 complejos sí es disjunto por clúster respecto del pool, pero el holdout global de 328 no lo es. La prevalencia de positivos del holdout es 151/328 = 46.04 %, distinta de un cribado real. Estas métricas **no** validan poses generadas por Vina, EF, prevalencia de uso ni beneficio incremental del clasificador sobre Vina. Para cerrar SCORE-007 faltan esa evaluación externa y la calibración de probabilidades bajo el uso previsto.

Evidencia: corrigendum\evidencia_fase6\score007_native\. metrics.json SHA-256 D3716F3FEBCD2AE4C65473B76084F5034E90EEE787DAE02D636CBBE31533FD87; predictions.jsonl SHA-256 6ACDF82A803728A106ECFA4FA507964B186200470ECA4CEA4B76252036D069E6. El manifiesto registra hashes por entrada; el script tiene SHA-256 8ff8289663d1b349bf6e71f1c6af4dcf73af13e26c0d937a7f2e7f1c4a6c4e2e.

## SCORE-004 y SCORE-010: contrato M4 provisional

El ranking de release usa pesos Vina 1.0, XGBoost 0.0, GNN legacy 0.0 y CL-GNN 0.0 para las ocho familias del registro. Se creó versión 2 en backend/artifacts/sci_config_registry.json y se actualizó el espejo rescoring/artifacts/stacking_weights.json, el fallback del motor y los siete DOT de la interfaz. El config_hash v2 es 2df4f25f5a7b1f55da3d0e6055c5cc7fb41e3fa77c8d8633e0876f4e645f15e8. La versión v1 histórica permanece para trazabilidad. XGB puede calcularse como señal exploratoria, pero no modifica total_score. M5-Zn es un protocolo aparte. La fórmula exacta y sus límites están en docs/90_FASE6_DECISION_M4.md. Se verificaron casos numéricos congelados y la igualdad entre interfaz, registro y motor. Se escogió esta contención porque la métrica con pose cristalográfica no permite calibrar pesos de producción.

## SCORE-008: cifras históricas retiradas; benchmark pendiente

docs/19_LIMITATIONS.md y docs/22_ABLATION_MOLCHAMB_CDK2.md ahora declaran que 33.37x era una media histórica de cinco dianas, no de 80; que 0.919 era la AUC media de esa tabla, y que la diana llamada CDK2 usaba el receptor 3PP0 de HER2 con activos CDK2. No existe un artefacto reproducible que justifique usar aquellas cifras en un paper o para el ranking actual. Se corrigió 3PP0 a HER2/ERBB2 en la fuente de alias y el catálogo, sin tocar los artefactos científicos sellados. El benchmark histórico ahora acepta p=0 como probabilidad válida y no salta discontinuamente a Vina cuando p≤0.01; EF ya utiliza el desempate fraccional compartido.

Al intentar regenerar backend/data/target_aliases.json se descubrió que este worktree carece de la biblioteca completa de estructuras: el generador producía cero dianas con estructura y un catálogo truncado. Se restauró el artefacto versionado, se aplicó sólo el cambio verificable de 3PP0 y se añadió una guardia que aborta sin sobrescribirlo cuando no hay estructuras. La prueba manual observó exit code 1 y SHA-256 del catálogo intacto. El origen CSV/JSON sí identifica 3PP0 como HER2.

No se repitió EF/AUC: ni en el worktree ni en la búsqueda local del servidor aparecieron los archivos multitarget históricos ni un conjunto controlado de activos y negativos. Tampoco es adecuado fabricar señuelos a partir de ChEMBL y llamarlos inactivos. Se dejó el encargo exacto en corrigendum\prompt_SCORE-008_fase6.md. Hasta contar con datos primarios, hashes y licencia, SCORE-008 sólo queda **contenido**, no validado.

## PROV-012 y PROV-016

Se rectificaron AGENTS.md y docs/50_ROADMAP.md: FEP-02 83/203 es un criterio preliminar aplicado a los archivos PDBbind _protein.pdb, no un paquete FEP listo; entre esos 83, 20 contienen metales y 75 aguas, sólo 8 no contienen ninguno de los dos. Los saltos de numeración son candidatos de hueco, no decisiones de modelado. FEP-03 91 parejas/18 dianas es cota de pares; nueve son perturbación nula. FEP-01 distingue 142 que necesitan multestado de 141 que pasan la puerta tras excluir un bloqueo estereoquímico. docs/51_POLITICA_DE_AGUAS.md diferencia el programa experimental con aguas de la preparación real de producto, que retira HOH/WAT/DOD y avisa SITIO_DESOLVATADO. Se contrastaron estas cifras con los JSONL/métricas sellados sin modificar sus bytes.

## ENG-A05, ENG-A07 y ENG-A08

La detección conservadora exige una cadena lineal de al menos tres residuos estándar; no clasifica como péptidos a lisinopril, enalapril ni ampicilina por coincidencias SMARTS sueltas. La detección sólo recomienda; el motor solicitado por el usuario decide el enrutado. El sidecar exige centro y tamaño de caja dados por el llamador y devuelve SIN_CAJA_DECLARADA si faltan; no inventa el sitio desde la geometría plegada. La ruta peptídica selecciona y persiste el microestado del ligando antes de ESMFold, y el respaldo Vina reutiliza el mismo SMILES canónico/hash. Se corrigió la lectura de N terminal protonado en los dos extractores de secuencia; una transferencia real de tri alanina zwitteriónica conservó grafo y carga. ESMFold sigue siendo exploratorio y sin benchmark de exactitud de pose.

## ENG-A13 y ENG-A14

La generación de análogos y las sustituciones bioisostéricas ahora operan sobre grafos RDKit con un sitio de unión explícito y único; si el mapeo es ambiguo se abstienen. El SA score es el de RDKit Contrib, no una fórmula local sin calibración. Se consultan catálogos estructurales PAINS A/B/C y BRENK y se rechazan nuevas alertas en análogos. Las sugerencias informan qué átomos de entrada cambiaron, muestran alertas heredadas, indican baja confianza y declaran que no fueron acopladas. Se retiró un intento de pre-score HTTP que no llegaba a ejecutarse. Estas reglas evitan proponer productos desconectados o cambiar silenciosamente otro sitio; no demuestran mejor actividad ni sintetizabilidad.

## PHYS-005 y LIG-011

MM-GBSA permanece retirado: la ruta pública responde MMGBSA_NO_DISPONIBLE y el campo histórico de respuesta siempre se invalida a null. Se corrigió el nombre físico a diferencia de energía potencial GBn2+ACE, ε_in=1 y sin entropía, que no es ΔG/ΔΔG; la documentación histórica se rotuló como retirada. El cálculo legacy, si se invoca fuera del producto, informa la plataforma real en sus resultados, incluso al abstenerse. Se regeneró OpenAPI desde FastAPI; no se editó el JSON manualmente. PHYS-003/004/011/013 son condicionales a reactivar ese motor con un protocolo nuevo y por eso siguen pendientes.

control_toxics.csv conserva 56 etiquetas sin fuentes primarias, endpoint ni licencia trazables. Se retiró su carga, entrenamiento TabPFN y penalización S_tox; el estado es no_evaluado y la UI no interpreta una lista vacía como seguridad. Las señales CYP se presentan como metabolismo estimado, no toxicidad clínica. backend/chem/CONTROL_TOXICS_PROVENANCE.md fija los requisitos para cualquier reactivación. Una prueba confirma que TPSA y SA altos no reducen S_tox como si fueran una predicción de toxicidad.

## Verificación

- Backend con Python embebido 3.11.9: 99 pruebas dirigidas pasaron; otras 16 de los guardianes históricos de componentes pasaron. Una advertencia de ProDy y advertencias de dependencias de ML no alteraron resultados.
- Frontend: TypeScript sin errores; suite completa Vitest 1067/1067 con dos workers para limitar memoria.
- Guardias: check_stacking_weights_ui, generate_openapi_contract --check y ocho goldens pasaron; git diff --check sin errores.
- No se ejecutó build de instalador ni smoke de producción: esta fase no alteró Tauri, CSP, empaquetado ni binarios. El auditor debe exigirlos antes de un release.
- No se modificó scripts/artifacts_science, no hubo push y no se escribieron temporales en C.

## Pendientes que no deben perderse al abrir fase 7

1. SCORE-007: poses Vina del pipeline de release con dianas/clústeres externos, intervalos y calibración bajo prevalencia de cribado. Mantener XGB=0 hasta superar esa puerta.
2. SCORE-008: recibir y verificar datos primarios de activos/negativos controlados, ejecutar primero el piloto de bajo costo y después un benchmark preregistrado con pesos congelados, hash del modelo, EF fraccional e IC bootstrap. No citar las métricas históricas como resultado del producto.
3. PHYS-003/004/011/013: sólo mediante un nuevo protocolo si se decide reactivar MM-GBSA. El legacy retirado no sirve como punto de partida validado.
4. Los recuentos FEP siguen siendo descriptivos; un paquete transferible requiere resolver aguas, metales, huecos, estados químicos y reconstrucción externa.

