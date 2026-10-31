"""English translations for request-facing backend messages.

Generated from concrete response/error call sites and reviewed with the MolDesign
domain glossary. Spanish remains the source language and default locale.
"""

from __future__ import annotations

ENGLISH_MESSAGES: dict[str, str] = {
    "La corrida no conserva su receptor con un hash verificable.": "The run does not retain its receptor with a verifiable hash.",
    "El límite CPU del render debe dejar al menos un 25% para otras aplicaciones.": "The render CPU limit must leave at least 25% for other applications.",
    "No se pudo iniciar la medición de VRAM.": "VRAM monitoring could not be initialized.",
    "No podemos vigilar la VRAM de la tarjeta utilizada por Blender. Elige CPU.": "We cannot monitor VRAM on the card used by Blender. Choose CPU.",
    "Se perdió la medición de VRAM. Molcy detuvo el render; elige CPU o vuelve a comprobar la GPU.": "VRAM monitoring was lost. Molcy stopped rendering; choose CPU or check the GPU again.",
    "Molcy detuvo el render porque se superó el presupuesto de VRAM o cayó el margen libre. Cierra aplicaciones, ajusta el presupuesto o elige CPU.": "Molcy stopped rendering because the VRAM budget was exceeded or free headroom fell too low. Close applications, adjust the budget or choose CPU.",















































































 '<b>Decisiones humanas:</b> NO EVALUADO — nadie ha revisado ni reconocido controles de esta corrida.': '<b>Human '
                                                                                                        'decisions: '
                                                                                                        '</b> NOT '
                                                                                                        'EVALUATED — '
                                                                                                        'no one has '
                                                                                                        'checked or '
                                                                                                        'acknowledged '
                                                                                                        'controls of '
                                                                                                        'this run.',
 '<b>Filtros PAINS:</b> no se detectaron subestructuras de la biblioteca usada. La ausencia de coincidencias no descarta otros mecanismos de interferencia.': (
     '<b>PAINS filters:</b> No substructures from the library were detected. No matches do not rule out other interference mechanisms.'
 ),
 '<b>Mapeo de Contactos de Sitio Activo (Residuo-Ligando)</b>': '<b>Active Site Contact Map (Residue-Ligand)</b>',



 '<i>El panel de selectividad se ejecuto pero no se encontraron resultados. Verifica que los anti-targets seleccionados tengan estructuras PDB validas.</i>': '<i>The '
                                                                                                                                                              'selectivity '
                                                                                                                                                              'panel '
                                                                                                                                                              'was '
                                                                                                                                                              'executed '
                                                                                                                                                              'but '
                                                                                                                                                              'no '
                                                                                                                                                              'results '
                                                                                                                                                              'were '
                                                                                                                                                              'found. '
                                                                                                                                                              'Check '
                                                                                                                                                              'that '
                                                                                                                                                              'the '
                                                                                                                                                              'selected '
                                                                                                                                                              'anti-targets '
                                                                                                                                                              'have '
                                                                                                                                                              'valid '
                                                                                                                                                              'PDB '
                                                                                                                                                              'structures.</i>',

 '<i>Lectura relativa a un umbral del protocolo; no demuestra seguridad ni selectividad experimental.</i>': '<i>Reading '
                                                                                                            'relating '
                                                                                                            'to a '
                                                                                                            'protocol '
                                                                                                            'threshold; '
                                                                                                            'does not '
                                                                                                            'demonstrate '
                                                                                                            'safety or '
                                                                                                            'experimental '
                                                                                                            'selectivity.</i>',



 'ADMET-AI no esta disponible en esta instalacion, asi que no hay perfil que calcular. No se devuelve un perfil vacio como si lo fuera.': 'ADMET-AI '
                                                                                                                                          'is '
                                                                                                                                          'not '
                                                                                                                                          'available '
                                                                                                                                          'in '
                                                                                                                                          'this '
                                                                                                                                          'installation, '
                                                                                                                                          'so '
                                                                                                                                          'there '
                                                                                                                                          'is '
                                                                                                                                          'no '
                                                                                                                                          'profile '
                                                                                                                                          'to '
                                                                                                                                          'calculate. '
                                                                                                                                          'An '
                                                                                                                                          'empty '
                                                                                                                                          'profile '
                                                                                                                                          'is '
                                                                                                                                          'not '
                                                                                                                                          'returned '
                                                                                                                                          'as '
                                                                                                                                          'if '
                                                                                                                                          'it '
                                                                                                                                          'were.',



 

 'Acoplar contra la unidad asimétrica cuando el sitio se forma entre cadenas produce un sitio incompleto. El dato no existe todavía en el modelo.': 'Docking against the asymmetric unit when the site is formed between chains produces an incomplete site. The data does not yet exist in the model.',
 'Advertencias científicas registradas antes de ejecutar.': 'Scientific warnings recorded before execution.',
 'Advertencias de la comprobación previa': 'Pre-check warnings',
 'Afinidad calculada con campo de fuerzas AD4 y cargas GFN2-xTB.': 'Affinity calculated with force field AD4 and '
                                                                   'GFN2-xTB charges.',



 'Afinidad tiene el peso más alto como métrica principal de interacción. ADME y drug-likeness son filtros heurísticos complementarios.': 'Affinity '
                                                                                                                                         'has '
                                                                                                                                         'the '
                                                                                                                                         'highest '
                                                                                                                                         'weight '
                                                                                                                                         'as '
                                                                                                                                         'the '
                                                                                                                                         'main '
                                                                                                                                         'metric '
                                                                                                                                         'of '
                                                                                                                                         'interaction. '
                                                                                                                                         'ADME '
                                                                                                                                         'and '
                                                                                                                                         'drug-likeness '
                                                                                                                                         'are '
                                                                                                                                         'complementary '
                                                                                                                                         'heuristic '
                                                                                                                                         'filters.',
 'Afinidades peores que -4 indican interacción no específica con GPCRs.': 'Worse affinities than -4 indicate '
                                                                          'non-specific interaction with GPCRs.',
 'Alertas Científicas del Pipeline': 'Pipeline Scientific Alerts',
 'Alternativa válida': 'Valid alternative',
 'Alternativas físicamente válidas': 'Physically Valid Alternatives',
 'Ambas se conservan y ambas se declaran. La pose principal del producto sigue siendo la de Vina; la del selector es una recomendación.': 'Both '
                                                                                                                                          'are '
                                                                                                                                          'preserved '
                                                                                                                                          'and '
                                                                                                                                          'both '
                                                                                                                                          'declared. '
                                                                                                                                          'The '
                                                                                                                                          'main '
                                                                                                                                          'pose '
                                                                                                                                          'of '
                                                                                                                                          'the '
                                                                                                                                          'product '
                                                                                                                                          'remains '
                                                                                                                                          'that '
                                                                                                                                          'of '
                                                                                                                                          'Vina; '
                                                                                                                                          'that '
                                                                                                                                          'of '
                                                                                                                                          'the '
                                                                                                                                          'selector '
                                                                                                                                          'is '
                                                                                                                                          'a '
                                                                                                                                          'recommendation.',

 'Apéndice técnico: salidas heredadas': 'Technical Appendix: Inherited Outflows',

 'Audio vacío': 'Empty audio',
 'Aumentar TPSA > 140 Å² perjudicaría permeabilidad': 'Increasing TPSA > 140 Å² would harm permeability',
 'Aumentar área polar': 'Increase Polar Area',
 'AutoDock 4 no generó el archivo de salida (steric clash severo o fallo interno).': 'AutoDock 4 did not generate the '
                                                                                     'output file (severe steric clash '
                                                                                     'or internal failure).',
 'AutoDock Vina excedió el timeout de 600 segundos. La molécula puede ser demasiado grande o compleja para este setup.': 'AutoDock '
                                                                                                                         'Vina '
                                                                                                                         'exceeded '
                                                                                                                         'the '
                                                                                                                         'timeout '
                                                                                                                         'of '
                                                                                                                         '600 '
                                                                                                                         'seconds. '
                                                                                                                         'The '
                                                                                                                         'molecule '
                                                                                                                         'may '
                                                                                                                         'be '
                                                                                                                         'too '
                                                                                                                         'large '
                                                                                                                         'or '
                                                                                                                         'complex '
                                                                                                                         'for '
                                                                                                                         'this '
                                                                                                                         'setup.',

 'Basado en el rango típico de Vina para GPCRs. Los mejores ligandos conocidos de 5-HT1A suelen dar -8 a -10 kcal/mol.': 'Based '
                                                                                                                         'on '
                                                                                                                         'the '
                                                                                                                         'typical '
                                                                                                                         'Vina '
                                                                                                                         'range '
                                                                                                                         'for '
                                                                                                                         'GPCRs. '
                                                                                                                         'The '
                                                                                                                         'best '
                                                                                                                         'known '
                                                                                                                         '5-HT1A '
                                                                                                                         'ligands '
                                                                                                                         'usually '
                                                                                                                         'give '
                                                                                                                         '-8 '
                                                                                                                         'to '
                                                                                                                         '-10 '
                                                                                                                         'kcal/mol.',
 "Binario 'xtb' no encontrado en el sistema.": "Binario 'xtb' not found in the system.",
 'Bloqueantes declarados en la comprobación previa': 'Blockers declared in the previous check',
 'CPU de 2 cores sin GPU: las evaluaciones PRO completas pueden tomar >15 min.': '2-Cores CPU without GPU: Complete '
                                                                                 'PRO evaluations can take >15 min.',

 'Cadena R (auth) es el receptor 5-HT1A en 7E2Y.': 'Chain R (auth) is the 5-HT1A receptor in 7E2Y.',
 'Cadena del receptor': 'Receptor chain',
 'Caja (tamaño)': 'Box (size)',
 'Caja de búsqueda': 'Search box',
 'Centroide de SRO calculado con scripts/extract_grid_from_ligand.py': 'SRO centroid calculated with '
                                                                       'scripts/extract_grid_from_ligand.py',

 'Circuit breaker abierto: ESMFold falló demasiadas veces. Se reintenta tras cooldown.': 'Circuit breaker open: '
                                                                                         'ESMFold failed too many '
                                                                                         'times. Retry after cooldown.',
 'ColabFold no configurado. Define COLABFOLD_API_URL en el entorno.': 'ColabFold not configured. Define '
                                                                      'COLABFOLD_API_URL in the environment.',
 'ColabFold no está configurado': 'ColabFold is not configured',
 'ColabFold no está configurado.': 'ColabFold is not configured.',
 'ColabFold no está disponible': 'ColabFold not available',
 'ColabFold no retornó ningún resultado': 'ColabFold did not return any results',
 'Comparación computacional relativa al protocolo; no demuestra selectividad experimental.': 'Computational comparison '
                                                                                             'relating to the '
                                                                                             'protocol; it does not '
                                                                                             'demonstrate experimental '
                                                                                             'selectivity.',
 'Comparación entre la estructura PDB de origen y la entrada preparada para la corrida.': 'Comparison between the '
                                                                                          'original PDB structure and '
                                                                                          'the entrance prepared for '
                                                                                          'the run.',
 'Complejidad de fragmentos alta': 'High Fragment Complexity',
 'Comprobar choques, valencias, geometría, strain y consistencia del complejo antes de MM-GBSA, dinámica molecular o priorización experimental.': (
     'Check clashes, valences, geometry, strain, and complex consistency before MM-GBSA, molecular dynamics, or experimental prioritization.'
 ),

 'Con poses': 'With poses',
 'Conclusión operativa de la corrida': 'Operational conclusion of the run',


 'Conexión rechazada: ¿Sidecar ESMFold-Pro corriendo en :8300? Requiere GPU.': 'Connection rejected: Sidecar '
                                                                               'ESMFold-Pro running at :8300? Requires '
                                                                               'GPU.',
 
 'Contrato de ejecución': 'Implementation contract',
 'Contrato de evidencia': 'Evidence contract',
 'Contrato de fingerprint': 'Fingerprint contract',
 'Contrato de preflight': 'Preflight contract',
 'Controles sin evaluar en la comprobación previa': 'Unassessed checks in the previous check',
 

 'Credenciales inválidas': 'Invalid credentials',
 'Cryo-EM 3.0 Å del complejo 5-HT1A–Gi con serotonina. Reemplaza 3RZY (FABP4, target incorrecto).': 'Cryo-EM 3.0 Å of '
                                                                                                    'the 5-HT1A–Gi '
                                                                                                    'complex with '
                                                                                                    'serotonin. '
                                                                                                    'Replaces 3RZY '
                                                                                                    '(FABP4, incorrect '
                                                                                                    'target).',

 'DOSSIER DE EVIDENCIA COMPUTACIONAL': 'DOSSIER OF COMPUTATION EVIDENCE',


 'Default de Vina 1.2.x. Apropiado para uso interactivo del MVP.': 'Default of Vina 1.2.x. Suitable for interactive '
                                                                   'use of MVP.',

 'Describen el sitio de la estructura que efectivamente se acopla.': 'They describe the site of the structure that is actually docked.',
 'Descriptores, reglas y filtros heurísticos': 'Descriptors, rules and heuristic filters',

 'Detalles de la Molécula': 'Details of the Molecule',
 'DiffDock API URL no configurada. El sistema usa solo AutoDock Vina para docking.': 'DiffDock API URL not configured. '
                                                                                     'The system only uses AutoDock '
                                                                                     'Vina for docking.',
 'DiffDock API no devolvió resultados': 'DiffDock API did not return results',

 'DiffDock no configurado. Define DIFFDOCK_API_URL en el entorno.': 'DiffDock not configured. Define DIFFDOCK_API_URL '
                                                                    'in the environment.',
 'DiffDock no está configurado': 'DiffDock is not configured',
 'DiffDock no está configurado en este servidor. Solo se usó AutoDock Vina para el docking. Configure DIFFDOCK_API_URL para habilitar validación cruzada.': 'DiffDock '
                                                                                                                                                            'is '
                                                                                                                                                            'not '
                                                                                                                                                            'configured '
                                                                                                                                                            'on '
                                                                                                                                                            'this '
                                                                                                                                                            'server. '
                                                                                                                                                            'AutoDock '
                                                                                                                                                            'Vina '
                                                                                                                                                            'was '
                                                                                                                                                            'only '
                                                                                                                                                            'used '
                                                                                                                                                            'for '
                                                                                                                                                            'docking. '
                                                                                                                                                            'Configure '
                                                                                                                                                            'DIFFDOCK_API_URL '
                                                                                                                                                            'to '
                                                                                                                                                            'enable '
                                                                                                                                                            'cross '
                                                                                                                                                            'validation.',
 'DiffDock no está disponible actualmente': 'DiffDock is not currently available',
 'DiffDock no pudo generar poses para esta molécula.': 'DiffDock could not generate poses for this molecule.',
 'Discordancia entre la sugerida y Vina top-1': 'Discordance between suggested and Vina top-1',
 'Documentar las reservas de preparación, dominio o reproducibilidad antes de comparar esta corrida con otras.': 'Document '
                                                                                                                 'the '
                                                                                                                 'reservations '
                                                                                                                 'of '
                                                                                                                 'preparation, '
                                                                                                                 'domain '
                                                                                                                 'or '
                                                                                                                 'reproducibility '
                                                                                                                 'before '
                                                                                                                 'comparing '
                                                                                                                 'this '
                                                                                                                 'run '
                                                                                                                 'with '
                                                                                                                 'others.',


 'ESMFold no está configurado': 'ESMFold is not configured',
 'ESMFold no está configurado en las variables de entorno (ESMFOLD_API_URL).': 'ESMFold is not configured in the '
                                                                               'environment variables '
                                                                               '(ESMFOLD_API_URL).',

 'ESMFold-Pro (RFdiffusion) no está configurado. Requiere GPU NVIDIA >=8 GB.': 'ESMFold-Pro (RFdiffusion) is not '
                                                                               'configured. It requires GPU NVIDIA >=8 '
                                                                               'GB.',

 'Ejecutar con un informe de otra ruta atribuiría controles que no se realizaron al motor seleccionado.': 'Running '
                                                                                                          'with a '
                                                                                                          'report from '
                                                                                                          'another '
                                                                                                          'path would '
                                                                                                          'attribute '
                                                                                                          'controls '
                                                                                                          'that were '
                                                                                                          'not '
                                                                                                          'performed '
                                                                                                          'to the '
                                                                                                          'selected '
                                                                                                          'engine.',


 'El SDF de poses está vacío o es inválido.': 'The pose SDF is either empty or invalid.',

 'El SMILES no se pudo interpretar.': 'The SMILES could not be interpreted.',

 'El archivo o el estudio no son los que produjeron la comprobación previa que aceptaste. No se congela una cohorte distinta de la que se te enseñó: vuelve a comprobarla.': 'The '
                                                                                                                                                                             'file '
                                                                                                                                                                             'or '
                                                                                                                                                                             'the '
                                                                                                                                                                             'study '
                                                                                                                                                                             'are '
                                                                                                                                                                             'not '
                                                                                                                                                                             'the '
                                                                                                                                                                             'ones '
                                                                                                                                                                             'that '
                                                                                                                                                                             'produced '
                                                                                                                                                                             'the '
                                                                                                                                                                             'previous '
                                                                                                                                                                             'check '
                                                                                                                                                                             'that '
                                                                                                                                                                             'you '
                                                                                                                                                                             'accepted. '
                                                                                                                                                                             'A '
                                                                                                                                                                             'cohort '
                                                                                                                                                                             'other '
                                                                                                                                                                             'than '
                                                                                                                                                                             'the '
                                                                                                                                                                             'one '
                                                                                                                                                                             'you '
                                                                                                                                                                             'were '
                                                                                                                                                                             'taught '
                                                                                                                                                                             'is '
                                                                                                                                                                             'not '
                                                                                                                                                                             'frozen: '
                                                                                                                                                                             'check '
                                                                                                                                                                             'it '
                                                                                                                                                                             'again.',

 'El artefacto no estaba disponible al construir el paquete.': 'The artifact was not available when building the '
                                                               'package.',

 'El caso pide la corrida solicitada y el resultado almacenado pertenece a otra. No se empaqueta un resultado que no corresponde a la corrida del caso.': 'The '
                                                                                                                                                          'case '
                                                                                                                                                          'asks '
                                                                                                                                                          'for '
                                                                                                                                                          'the '
                                                                                                                                                          'requested '
                                                                                                                                                          'run '
                                                                                                                                                          'and '
                                                                                                                                                          'the '
                                                                                                                                                          'stored '
                                                                                                                                                          'result '
                                                                                                                                                          'belongs '
                                                                                                                                                          'to '
                                                                                                                                                          'another. '
                                                                                                                                                          'A '
                                                                                                                                                          'result '
                                                                                                                                                          'that '
                                                                                                                                                          'does '
                                                                                                                                                          'not '
                                                                                                                                                          'correspond '
                                                                                                                                                          'to '
                                                                                                                                                          'the '
                                                                                                                                                          'running '
                                                                                                                                                          'of '
                                                                                                                                                          'the '
                                                                                                                                                          'case '
                                                                                                                                                          'is '
                                                                                                                                                          'not '
                                                                                                                                                          'packaged.',

 'El catálogo declara esta diana como metaloenzima y no se observó ningún ion metálico en la estructura preparada. O el metal se perdió en la preparación —no estaba en `cofactors_whitelist`— o la etiqueta del catálogo no corresponde a esta estructura.': 'The catalog lists this target as a metalloenzyme, but no metal ion was '
                                                                                                                                                                                                                                                                         'observed in the prepared structure. Either the metal was lost during '
                                                                                                                                                                                                                                                                         'preparation—it was not listed in `cofactors_whitelist`—or the catalog label '
                                                                                                                                                                                                                                                                         'does not match this structure.',


 'El centro enviado es (0, 0, 0) y no se pudo derivar una caja reproducible del PDB filtrado.': 'The sent center is '
                                                                                                '(0, 0, 0) and could '
                                                                                                'not derive a '
                                                                                                'reproducible box from '
                                                                                                'the filtered PDB.',


 'El dominio de aplicabilidad del modelo no fue informado.': 'The applicability domain of the model was not reported.',
 'El ensemble no se pudo generar: el confórmero base no se pudo releer. La corrida sigue con una sola conformación.': 'The '
                                                                                                                      'assembly '
                                                                                                                      'could '
                                                                                                                      'not '
                                                                                                                      'be '
                                                                                                                      'generated: '
                                                                                                                      'the '
                                                                                                                      'base '
                                                                                                                      'conformer '
                                                                                                                      'could '
                                                                                                                      'not '
                                                                                                                      'be '
                                                                                                                      'reread. '
                                                                                                                      'The '
                                                                                                                      'run '
                                                                                                                      'continues '
                                                                                                                      'with '
                                                                                                                      'a '
                                                                                                                      'single '
                                                                                                                      'conformation.',
 'El generador de sugerencias falló. Esto no afecta la evaluación principal.': 'The suggestion generator failed. This '
                                                                               'does not affect the main evaluation.',
 'El hash del receptor preparado sólo puede calcularse sobre un archivo que exista. Prepararlo aquí convertiría la comprobación previa en trabajo de corrida.': 'The prepared receptor can only be hashed if the file exists. Preparing it here '
                                                                                                                                                                    'would turn the preflight check into work done during the run.',
 'El inventario no permite confirmar todos los requisitos de preparación.': 'The inventory does not allow confirmation '
                                                                            'of all preparation requirements.',
 'El inventario registra receptor preparado, grid y referencias estructurales.': 'The inventory records the prepared '
                                                                                 'receptor, grid, and structural '
                                                                                 'references.',
 'El modelo de plegamiento produjo una estructura, y la conversión de esa estructura a un ligando acoplable no se completó, así que Vina no llegó a ejecutarse y NO hay afinidad. No se sustituye por un valor derivado de la confianza del plegado: la confianza describe la estructura, no la unión. Ver docs/76_DECISION_TRANSFERENCIA_ESMFOLD_A_LIGANDO_V1.md.': 'The folding model produced a structure, and the conversion of that structure to a dockable ligand was not completed, so Vina never ran and there is NO affinity. It is not replaced by a value derived from the folding confidence: confidence describes the structure, not the binding. See docs/76_DECISION_TRANSFERENCIA_ESMFOLD_A_LIGANDO_V1.md.',

 'El motor que corrió no es el que se pidió. La pose no es comparable con la que habría producido el motor solicitado.': 'The '
                                                                                                                         'engine '
                                                                                                                         'that '
                                                                                                                         'ran '
                                                                                                                         'is '
                                                                                                                         'not '
                                                                                                                         'the '
                                                                                                                         'one '
                                                                                                                         'that '
                                                                                                                         'was '
                                                                                                                         'ordered. '
                                                                                                                         'The '
                                                                                                                         'pose '
                                                                                                                         'is '
                                                                                                                         'not '
                                                                                                                         'comparable '
                                                                                                                         'to '
                                                                                                                         'the '
                                                                                                                         'one '
                                                                                                                         'that '
                                                                                                                         'would '
                                                                                                                         'have '
                                                                                                                         'produced '
                                                                                                                         'the '
                                                                                                                         'requested '
                                                                                                                         'engine.',

 'El preflight no pudo ejecutar estos controles. No se evaluaron: eso no equivale a que los pasaran.': 'The preflight '
                                                                                                       'could not '
                                                                                                       'execute these '
                                                                                                       'controls. They '
                                                                                                       'were not '
                                                                                                       'evaluated: '
                                                                                                       'that does not '
                                                                                                       'mean they '
                                                                                                       'passed them.',


 'No hay una medida de calibración con n, intervalo y protocolo para este receptor: el ranking no está respaldado aquí.': 'There is no calibration measurement with n, interval and protocol for this receptor: the ranking is not supported here.',
 'El receptor no declara residuos de referencia y no has seleccionado ninguno.': 'The receptor declares no reference '
                                                                                 'residues and none were selected.',
 'El receptor preparado se congeló por su contenido. Dos corridas con el mismo SHA-256 usaron el mismo receptor; con hashes distintos, no, por mucho que la ruta coincida.': 'The '
                                                                                                                                                                             'prepared '
                                                                                                                                                                             'receptor '
                                                                                                                                                                             'was '
                                                                                                                                                                             'frozen '
                                                                                                                                                                             'by '
                                                                                                                                                                             'content. '
                                                                                                                                                                             'Two '
                                                                                                                                                                             'runs '
                                                                                                                                                                             'with '
                                                                                                                                                                             'the '
                                                                                                                                                                             'same '
                                                                                                                                                                             'SHA-256 '
                                                                                                                                                                             'used '
                                                                                                                                                                             'the '
                                                                                                                                                                             'same '
                                                                                                                                                                             'receptor; '
                                                                                                                                                                             'different '
                                                                                                                                                                             'hashes '
                                                                                                                                                                             'mean '
                                                                                                                                                                             'they '
                                                                                                                                                                             'did '
                                                                                                                                                                             'not, '
                                                                                                                                                                             'even '
                                                                                                                                                                             'if '
                                                                                                                                                                             'the '
                                                                                                                                                                             'path '
                                                                                                                                                                             'matches.',

 'El recuento sale de comparar archivos reales, no de una lista teórica.': 'The count comes from comparing real files, '
                                                                           'not from a theoretical list.',
 'El rescoring de ML no produjo regresión para esta corrida. En evaluaciones anteriores al 2026-09-04 este campo está vacío porque el valor se perdía al sobrescribir la afinidad de Vina.': 'The '
                                                                                                                                                                                             'rescoring '
                                                                                                                                                                                             'of '
                                                                                                                                                                                             'ML '
                                                                                                                                                                                             'did '
                                                                                                                                                                                             'not '
                                                                                                                                                                                             'produce '
                                                                                                                                                                                             'regression '
                                                                                                                                                                                             'for '
                                                                                                                                                                                             'this '
                                                                                                                                                                                             'run. '
                                                                                                                                                                                             'In '
                                                                                                                                                                                             'evaluations '
                                                                                                                                                                                             'prior '
                                                                                                                                                                                             'to '
                                                                                                                                                                                             '2026-09-04 '
                                                                                                                                                                                             'this '
                                                                                                                                                                                             'field '
                                                                                                                                                                                             'is '
                                                                                                                                                                                             'empty '
                                                                                                                                                                                             'because '
                                                                                                                                                                                             'the '
                                                                                                                                                                                             'value '
                                                                                                                                                                                             'was '
                                                                                                                                                                                             'lost '
                                                                                                                                                                                             'by '
                                                                                                                                                                                             'overwriting '
                                                                                                                                                                                             'the '
                                                                                                                                                                                             'affinity '
                                                                                                                                                                                             'of '
                                                                                                                                                                                             'Vina.',
 'El score total de la corrida no es un número interpretable y no puede sellarse.': "The run's total score is not an "
                                                                                    'interpretable number and cannot '
                                                                                    'be sealed.',
 'El selector de pose falló, así que no hay recomendación que leer.': 'The pose selector failed, so there is no recommendation to interpret.',
 'El selector de pose no se ejecutó en esta corrida; la referencia es Vina top-1.': 'The pose selector was not '
                                                                                    'executed in this run; the '
                                                                                    'reference is Vina top-1.',
 'El selector de pose se abstuvo: no recomendó ninguna pose. La referencia es Vina top-1 como fallback, no como acierto del selector.': 'The '
                                                                                                                                        'pose '
                                                                                                                                        'selector '
                                                                                                                                        'abstained: '
                                                                                                                                        'it '
                                                                                                                                        'did '
                                                                                                                                        'not '
                                                                                                                                        'recommend '
                                                                                                                                        'a '
                                                                                                                                        'pose. '
                                                                                                                                        'The '
                                                                                                                                        'fallback '
                                                                                                                                        'reference '
                                                                                                                                        'is '
                                                                                                                                        'Vina '
                                                                                                                                        'top-1, '
                                                                                                                                        'not '
                                                                                                                                        'a '
                                                                                                                                        'successful '
                                                                                                                                        'selector '
                                                                                                                                        'prediction.',
 'El selector falló; no hay recomendación que leer.': 'The selector failed; there is no recommendation to read.',
 'El selector no llegó a cargar su modelo, así que no hay artefacto que sellar.': 'The selector did not load its '
                                                                                  'model, so there is no artifact to '
                                                                                  'seal.',

 'El servicio DiffDock no respondió. Solo se usó AutoDock Vina para esta evaluación.': 'The DiffDock service did not '
                                                                                       'respond. AutoDock Vina was '
                                                                                       'only used for this evaluation.',
 'El servicio de evaluación no está disponible en este momento. El dispatcher local no está disponible; revisa backend.latest.log.': 'The '
                                                                                                                                     'evaluation '
                                                                                                                                     'service '
                                                                                                                                     'is '
                                                                                                                                     'not '
                                                                                                                                     'available '
                                                                                                                                     'at '
                                                                                                                                     'this '
                                                                                                                                     'time. '
                                                                                                                                     'The '
                                                                                                                                     'local '
                                                                                                                                     'dispatcher '
                                                                                                                                     'is '
                                                                                                                                     'not '
                                                                                                                                     'available; '
                                                                                                                                     'check '
                                                                                                                                     'backend.latest.log.',
 'El servicio de generación de reportes no está disponible': 'Report generation service not available',
 'El sitio que describen esos residuos no existe en la estructura contra la que se va a acoplar. Puede que la cadena elegida no sea la del sitio de unión.': 'The site that these residues describe does not exist in the structure it will be docked against. The chosen chain may not be the one that holds the binding site.',

 'El snapshot persistido de la corrida no se pudo serializar.': 'The persisted run snapshot could not be serialized.',

 'El token de acceso ha expirado': 'The access token has expired',
 'El token no contiene un correo electrónico': 'The token does not contain an email',
 'El validador de producción lo señaló sin impedir la ejecución.': 'The production validator pointed it out without '
                                                                   'impeding execution.',


 'Eliminar fragmentos puede reducir afinidad': 'Removing fragments can reduce affinity',
 'Email o contraseña incorrectos': 'Incorrect email or password',
 'En una metaloenzima el metal suele ser parte del sitio catalítico. Sólo se conservan los metales declarados explícitamente para este receptor.': 'In a metalloenzyme, the metal is usually part of the catalytic site. Only '
                                                                                                                                                      'metals explicitly declared for this receptor are retained.',
 
 
 


 'Error de validación. Por favor verifica el archivo y los parámetros.': 'Validation error. Please check the file and '
                                                                         'parameters.',


 'Error interno al generar el reporte IA. Por favor intenta más tarde.': 'Internal error when generating AI report. '
                                                                         'Please try later.',

 'Error interno al procesar el target.': 'Internal error processing target.',
 'Error interno al procesar la solicitud de evaluación. Por favor intenta más tarde.': 'Internal error processing '
                                                                                       'evaluation request. Please try '
                                                                                       'later.',
 'Es el archivo exacto que leerá la preparación de la corrida.': 'It is the exact file that will read the preparation '
                                                                 'of the run.',
 'Es la cadena que se acoplará; el resto de la estructura no entra.': 'It is the chain that will be docked; the rest of the structure is excluded.',
 'Es la caja exacta que recibirá el acoplamiento.': 'It is the exact box that will receive the docking.',
 'Escalón': 'Step',
 'Ese nombre de usuario ya está en uso': 'That username is already in use',
 'Especies retiradas de la estructura': 'Species removed from structure',
 'Esta cohorte se congeló con una versión del contrato de comprobación previa que este build ya no sabe leer. No se devuelve a medias.': 'This '
                                                                                                                                         'cohort '
                                                                                                                                         'was '
                                                                                                                                         'froze '
                                                                                                                                         'with '
                                                                                                                                         'a '
                                                                                                                                         'version '
                                                                                                                                         'of '
                                                                                                                                         'the '
                                                                                                                                         'previous '
                                                                                                                                         'verification '
                                                                                                                                         'contract '
                                                                                                                                         'that '
                                                                                                                                         'this '
                                                                                                                                         'build '
                                                                                                                                         'can '
                                                                                                                                         'no '
                                                                                                                                         'longer '
                                                                                                                                         'read. '
                                                                                                                                         'It '
                                                                                                                                         'is '
                                                                                                                                         'not '
                                                                                                                                         'half-returned.',
 'Esta cohorte ya tiene una corrida en marcha. Dos corridas simultáneas competirían por el mismo motor local y ninguna de las dos sería reproducible.': 'This '
                                                                                                                                                        'cohort '
                                                                                                                                                        'already '
                                                                                                                                                        'has '
                                                                                                                                                        'a '
                                                                                                                                                        'running '
                                                                                                                                                        'run. '
                                                                                                                                                        'Two '
                                                                                                                                                        'simultaneous '
                                                                                                                                                        'runs '
                                                                                                                                                        'would '
                                                                                                                                                        'compete '
                                                                                                                                                        'for '
                                                                                                                                                        'the '
                                                                                                                                                        'same '
                                                                                                                                                        'local '
                                                                                                                                                        'engine '
                                                                                                                                                        'and '
                                                                                                                                                        'neither '
                                                                                                                                                        'would '
                                                                                                                                                        'be '
                                                                                                                                                        'reproducible.',
 'Esta corrida es anterior a la etapa de selección de pose. La referencia sigue siendo Vina top-1, declarada como fallback.': 'This '
                                                                                                                              'run '
                                                                                                                              'predates '
                                                                                                                              'the '
                                                                                                                              'pose '
                                                                                                                              'selection '
                                                                                                                              'stage. '
                                                                                                                              'The '
                                                                                                                              'reference '
                                                                                                                              'is '
                                                                                                                              'still '
                                                                                                                              'Vina '
                                                                                                                              'top-1, '
                                                                                                                              'declared '
                                                                                                                              'as '
                                                                                                                              'fallback.',
 'Esta corrida es anterior a la etapa de validación física, o la etapa no llegó a emitir veredicto. Que no se midiera no dice nada sobre las poses.': 'This '
                                                                                                                                                      'run '
                                                                                                                                                      'predates '
                                                                                                                                                      'the '
                                                                                                                                                      'stage '
                                                                                                                                                      'of '
                                                                                                                                                      'physical '
                                                                                                                                                      'validation, '
                                                                                                                                                      'or '
                                                                                                                                                      'the '
                                                                                                                                                      'stage '
                                                                                                                                                      'did '
                                                                                                                                                      'not '
                                                                                                                                                      'reach '
                                                                                                                                                      'a '
                                                                                                                                                      'verdict. '
                                                                                                                                                      'That '
                                                                                                                                                      'it '
                                                                                                                                                      'was '
                                                                                                                                                      'not '
                                                                                                                                                      'measured '
                                                                                                                                                      'says '
                                                                                                                                                      'nothing '
                                                                                                                                                      'about '
                                                                                                                                                      'the '
                                                                                                                                                      'poses.',
 'Esta corrida es anterior a la etapa de validación física: no se ejecutó. Que no se midiera no dice nada sobre las poses.': (
     'This run predates the physical-validation step, so it was not run. Not having been evaluated says nothing about the poses.'
 ),
 'Esta corrida es anterior al congelado del receptor y no conserva sus bytes. No se sustituye por el archivo del catálogo: podría haberse repreparado.': 'This '
                                                                                                                                                         'run '
                                                                                                                                                         'predates '
                                                                                                                                                         'the '
                                                                                                                                                         'frozen '
                                                                                                                                                         'receptor '
                                                                                                                                                         'and '
                                                                                                                                                         'does '
                                                                                                                                                         'not '
                                                                                                                                                         'retain '
                                                                                                                                                         'its '
                                                                                                                                                         'bytes. '
                                                                                                                                                         'It '
                                                                                                                                                         'is '
                                                                                                                                                         'not '
                                                                                                                                                         'replaced '
                                                                                                                                                         'by '
                                                                                                                                                         'the '
                                                                                                                                                         'catalog '
                                                                                                                                                         'file: '
                                                                                                                                                         'it '
                                                                                                                                                         'could '
                                                                                                                                                         'have '
                                                                                                                                                         'been '
                                                                                                                                                         'repaired.',
 'Esta corrida no serializó ningún índice heredado.': 'This run did not serialize any inherited index.',

 'Esta versión experimental sólo permite Solana devnet.': 'This experimental version only allows Solana Devnet.',
 'Estado de la corrida': 'Status of the run',
 'Estado del acoplamiento': 'Docking status',
 'Este documento describe qué evidencia produjo una corrida, qué partes son reproducibles y qué quedó sin evaluar. No califica la molécula ni afirma que sea un fármaco, un candidato clínico ni un compuesto seguro.': 'This '
                                                                                                                                                                                                                        'document '
                                                                                                                                                                                                                        'describes '
                                                                                                                                                                                                                        'what '
                                                                                                                                                                                                                        'evidence '
                                                                                                                                                                                                                        'produced '
                                                                                                                                                                                                                        'a '
                                                                                                                                                                                                                        'run, '
                                                                                                                                                                                                                        'what '
                                                                                                                                                                                                                        'parts '
                                                                                                                                                                                                                        'are '
                                                                                                                                                                                                                        'reproducible '
                                                                                                                                                                                                                        'and '
                                                                                                                                                                                                                        'what '
                                                                                                                                                                                                                        'remained '
                                                                                                                                                                                                                        'unevaluated. '
                                                                                                                                                                                                                        'It '
                                                                                                                                                                                                                        'does '
                                                                                                                                                                                                                        'not '
                                                                                                                                                                                                                        'qualify '
                                                                                                                                                                                                                        'the '
                                                                                                                                                                                                                        'molecule '
                                                                                                                                                                                                                        'or '
                                                                                                                                                                                                                        'claim '
                                                                                                                                                                                                                        'to '
                                                                                                                                                                                                                        'be '
                                                                                                                                                                                                                        'a '
                                                                                                                                                                                                                        'drug, '
                                                                                                                                                                                                                        'a '
                                                                                                                                                                                                                        'clinical '
                                                                                                                                                                                                                        'candidate '
                                                                                                                                                                                                                        'or '
                                                                                                                                                                                                                        'a '
                                                                                                                                                                                                                        'safe '
                                                                                                                                                                                                                        'compound.',
 'Este documento responde qué evidencia computacional produjo la corrida, qué partes son reproducibles, qué supuestos hizo, qué controles superó, qué incertidumbres permanecen y qué sería justificable hacer después. No responde si la molécula es un buen fármaco.': 'This '
                                                                                                                                                                                                                                                                         'document '
                                                                                                                                                                                                                                                                         'states '
                                                                                                                                                                                                                                                                         'what '
                                                                                                                                                                                                                                                                         'computational '
                                                                                                                                                                                                                                                                         'evidence '
                                                                                                                                                                                                                                                                         'the '
                                                                                                                                                                                                                                                                         'run '
                                                                                                                                                                                                                                                                         'produced, '
                                                                                                                                                                                                                                                                         'which '
                                                                                                                                                                                                                                                                         'parts '
                                                                                                                                                                                                                                                                         'are '
                                                                                                                                                                                                                                                                         'reproducible, '
                                                                                                                                                                                                                                                                         'what '
                                                                                                                                                                                                                                                                         'assumptions '
                                                                                                                                                                                                                                                                         'it '
                                                                                                                                                                                                                                                                         'made, '
                                                                                                                                                                                                                                                                         'which '
                                                                                                                                                                                                                                                                         'checks '
                                                                                                                                                                                                                                                                         'passed, '
                                                                                                                                                                                                                                                                         'what '
                                                                                                                                                                                                                                                                         'uncertainties '
                                                                                                                                                                                                                                                                         'remain, '
                                                                                                                                                                                                                                                                         'and '
                                                                                                                                                                                                                                                                         'what '
                                                                                                                                                                                                                                                                         'action '
                                                                                                                                                                                                                                                                         'would '
                                                                                                                                                                                                                                                                         'be '
                                                                                                                                                                                                                                                                         'justified '
                                                                                                                                                                                                                                                                         'next. '
                                                                                                                                                                                                                                                                         'It '
                                                                                                                                                                                                                                                                         'does '
                                                                                                                                                                                                                                                                         'not '
                                                                                                                                                                                                                                                                         'determine '
                                                                                                                                                                                                                                                                         'whether '
                                                                                                                                                                                                                                                                         'the '
                                                                                                                                                                                                                                                                         'molecule '
                                                                                                                                                                                                                                                                         'is '
                                                                                                                                                                                                                                                                         'a '
                                                                                                                                                                                                                                                                         'good '
                                                                                                                                                                                                                                                                         'drug.',
 'Este documento responde una pregunta computacional y sólo una: qué entró en esta cohorte, qué se pudo acoplar bajo una configuración común, y qué quedó sin evaluar. NO responde si alguna de estas moléculas es un fármaco.': 'This '
                                                                                                                                                                                                                                 'document '
                                                                                                                                                                                                                                 'answers '
                                                                                                                                                                                                                                 'a '
                                                                                                                                                                                                                                 'computational '
                                                                                                                                                                                                                                 'question '
                                                                                                                                                                                                                                 'and '
                                                                                                                                                                                                                                 'only '
                                                                                                                                                                                                                                 'one: '
                                                                                                                                                                                                                                 'what '
                                                                                                                                                                                                                                 'entered '
                                                                                                                                                                                                                                 'this '
                                                                                                                                                                                                                                 'cohort, '
                                                                                                                                                                                                                                 'what '
                                                                                                                                                                                                                                 'could '
                                                                                                                                                                                                                                 'be '
                                                                                                                                                                                                                                 'coupled '
                                                                                                                                                                                                                                 'under '
                                                                                                                                                                                                                                 'a '
                                                                                                                                                                                                                                 'common '
                                                                                                                                                                                                                                 'configuration, '
                                                                                                                                                                                                                                 'and '
                                                                                                                                                                                                                                 'what '
                                                                                                                                                                                                                                 'remained '
                                                                                                                                                                                                                                 'unevaluated. '
                                                                                                                                                                                                                                 'It '
                                                                                                                                                                                                                                 'does '
                                                                                                                                                                                                                                 'NOT '
                                                                                                                                                                                                                                 'answer '
                                                                                                                                                                                                                                 'if '
                                                                                                                                                                                                                                 'any '
                                                                                                                                                                                                                                 'of '
                                                                                                                                                                                                                                 'these '
                                                                                                                                                                                                                                 'molecules '
                                                                                                                                                                                                                                 'is '
                                                                                                                                                                                                                                 'a '
                                                                                                                                                                                                                                 'drug.',


 'Este receptor sólo conserva un PDBQT preparado y no tiene una fuente PDB que pueda volver a prepararse. Sube otra preparación PDBQT o parte de un PDB.': 'This '
                                                                                                                                                           'receptor '
                                                                                                                                                           'only '
                                                                                                                                                           'retains '
                                                                                                                                                           'a '
                                                                                                                                                           'prepared '
                                                                                                                                                           'PDBQT '
                                                                                                                                                           'and '
                                                                                                                                                           'does '
                                                                                                                                                           'not '
                                                                                                                                                           'have '
                                                                                                                                                           'a '
                                                                                                                                                           'PDB '
                                                                                                                                                           'source '
                                                                                                                                                           'that '
                                                                                                                                                           'can '
                                                                                                                                                           'be '
                                                                                                                                                           'reprepared. '
                                                                                                                                                           'Upload '
                                                                                                                                                           'another '
                                                                                                                                                           'PDBQT '
                                                                                                                                                           'preparation '
                                                                                                                                                           'or '
                                                                                                                                                           'part '
                                                                                                                                                           'of '
                                                                                                                                                           'a '
                                                                                                                                                           'PDB.',





 'Estructura peptídica generada; docking no evaluado': 'peptide structure generated; docking not evaluated',
 'Etapa no habilitada en la configuración': 'Stage not enabled in configuration',

 'Explicabilidad Científica e IA de Caja Transparente': 'Scientific Explanation and Transparent Box AI',
 'FUERA del dominio de aplicabilidad del modelo: la molécula no se parece a las del conjunto de entrenamiento. Se muestra como referencia, no como predicción. La afinidad del caso es la de Vina.': 'OUTSIDE '
                                                                                                                                                                                                     'the '
                                                                                                                                                                                                     'applicability '
                                                                                                                                                                                                     'domain '
                                                                                                                                                                                                     'of '
                                                                                                                                                                                                     'the '
                                                                                                                                                                                                     'model: '
                                                                                                                                                                                                     'the '
                                                                                                                                                                                                     'molecule '
                                                                                                                                                                                                     'does '
                                                                                                                                                                                                     'not '
                                                                                                                                                                                                     'resemble '
                                                                                                                                                                                                     'those '
                                                                                                                                                                                                     'of '
                                                                                                                                                                                                     'the '
                                                                                                                                                                                                     'training '
                                                                                                                                                                                                     'set. '
                                                                                                                                                                                                     'It '
                                                                                                                                                                                                     'is '
                                                                                                                                                                                                     'shown '
                                                                                                                                                                                                     'as '
                                                                                                                                                                                                     'a '
                                                                                                                                                                                                     'reference, '
                                                                                                                                                                                                     'not '
                                                                                                                                                                                                     'as '
                                                                                                                                                                                                     'a '
                                                                                                                                                                                                     'prediction. '
                                                                                                                                                                                                     'The '
                                                                                                                                                                                                     'affinity '
                                                                                                                                                                                                     'of '
                                                                                                                                                                                                     'the '
                                                                                                                                                                                                     'case '
                                                                                                                                                                                                     'is '
                                                                                                                                                                                                     'that '
                                                                                                                                                                                                     'of '
                                                                                                                                                                                                     'Vina.',
 'Fallo al construir RDKit Mol tras protonación.': 'Failed to build RDKit Mol after protonation.',

 'Fallo en el plegamiento de ColabFold.': "ColabFold's fold failed.",
 'Fallo en la ingesta científica. Por favor verifica el PDB ID y vuelve a intentarlo.': 'Scientific intake failed. '
                                                                                        'Please check the PDB ID and '
                                                                                        'try again.',
 'Filas en el archivo': 'Rows in the file',

 'Firma inválida o no encontrada en la blockchain': 'Invalid signature or not found in blockchain',
 'Forma química del ligando': 'Chemical form of ligand',
 'Formato de Entrada': 'Input Format',
 'Formato de token inválido. Usa: Bearer <token>': 'Invalid token format. Use: Bearer <token>',
 'Fracaso de Farmacóforo: La molécula no interactúa con ningún residuo crítico definido para este target.': 'Pharmacophorus '
                                                                                                            'failure: '
                                                                                                            'The '
                                                                                                            'molecule '
                                                                                                            'does not '
                                                                                                            'interact '
                                                                                                            'with any '
                                                                                                            'critical '
                                                                                                            'residue '
                                                                                                            'defined '
                                                                                                            'for this '
                                                                                                            'target.',
 'Fuente del receptor': 'Receptor source',
 'Físicamente evaluadas': 'Physically assessed',

 'Huella de cohorte': 'Cohort fingerprint',
 'Huella de corrida': 'Run fingerprint',
 'Incertidumbre de Pose: Hay múltiples modos de enlace con energías casi idénticas. El modo 1 podría no ser el único biológicamente relevante.': 'Pose '
                                                                                                                                                 'uncertainty: '
                                                                                                                                                 'There '
                                                                                                                                                 'are '
                                                                                                                                                 'multiple '
                                                                                                                                                 'modes '
                                                                                                                                                 'of '
                                                                                                                                                 'bonding '
                                                                                                                                                 'with '
                                                                                                                                                 'almost '
                                                                                                                                                 'identical '
                                                                                                                                                 'energies. '
                                                                                                                                                 'Mode '
                                                                                                                                                 '1 '
                                                                                                                                                 'may '
                                                                                                                                                 'not '
                                                                                                                                                 'be '
                                                                                                                                                 'the '
                                                                                                                                                 'only '
                                                                                                                                                 'biologically '
                                                                                                                                                 'relevant.',


 'Interacción Molecular y Docking (AutoDock Vina)': 'Molecular Interaction and Docking (AutoDock Vina)',

 'Interpretación · regresión XGBoost (pKi)': 'Interpretation · regression XGBoost (pKi)',


 'La cadena del receptor ya no coincide con la configuración registrada. Vuelve a seleccionar el receptor y comprobar la preparación.': 'The receptor chain no longer matches the recorded settings. Re-select the receptor and check the preparation.',

 'La caja no está definida y no pudo derivarse del receptor filtrado. La corrida se detiene antes de enviar un centro (0,0,0) a Vina.': 'The '
                                                                                                                                        'box '
                                                                                                                                        'is '
                                                                                                                                        'undefined '
                                                                                                                                        'and '
                                                                                                                                        'could '
                                                                                                                                        'not '
                                                                                                                                        'be '
                                                                                                                                        'derived '
                                                                                                                                        'from '
                                                                                                                                        'the '
                                                                                                                                        'filtered '
                                                                                                                                        'receptor. '
                                                                                                                                        'The '
                                                                                                                                        'run '
                                                                                                                                        'stops '
                                                                                                                                        'before '
                                                                                                                                        'sending '
                                                                                                                                        'a '
                                                                                                                                        '(0,0,0) '
                                                                                                                                        'center '
                                                                                                                                        'to '
                                                                                                                                        'Vina.',

 'La cohorte congelada no tiene ninguna fila elegible que ejecutar.': 'The frozen cohort has no eligible row to run.',

 'La cohorte está bloqueada y no se guarda: no es una entrada ejecutable. Corrige los bloqueantes y vuelve a comprobarla.': 'The '
                                                                                                                            'cohort '
                                                                                                                            'is '
                                                                                                                            'locked '
                                                                                                                            'and '
                                                                                                                            'not '
                                                                                                                            'saved: '
                                                                                                                            'it '
                                                                                                                            'is '
                                                                                                                            'not '
                                                                                                                            'an '
                                                                                                                            'executable '
                                                                                                                            'input. '
                                                                                                                            'Correct '
                                                                                                                            'the '
                                                                                                                            'blockers '
                                                                                                                            'and '
                                                                                                                            'check '
                                                                                                                            'it '
                                                                                                                            'again.',

 'La cohorte no conserva el archivo original.': 'The cohort does not retain the original file.',
 'La comprobación exige el archivo real.': 'The check requires the actual file.',
 'La comprobación previa no descarga nada: importa o prepara el receptor y repite el control para calcular su hash y lo que la preparación retirará.': 'The '
                                                                                                                                                       'previous '
                                                                                                                                                       'check '
                                                                                                                                                       'does '
                                                                                                                                                       'not '
                                                                                                                                                       'download '
                                                                                                                                                       'anything: '
                                                                                                                                                       'it '
                                                                                                                                                       'imports '
                                                                                                                                                       'or '
                                                                                                                                                       'prepares '
                                                                                                                                                       'the '
                                                                                                                                                       'receptor '
                                                                                                                                                       'and '
                                                                                                                                                       'repeats '
                                                                                                                                                       'the '
                                                                                                                                                       'control '
                                                                                                                                                       'to '
                                                                                                                                                       'calculate '
                                                                                                                                                       'its '
                                                                                                                                                       'hash '
                                                                                                                                                       'and '
                                                                                                                                                       'what '
                                                                                                                                                       'the '
                                                                                                                                                       'preparation '
                                                                                                                                                       'will '
                                                                                                                                                       'withdraw.',
 'La comprobación previa registró bloqueantes técnicos.': 'The previous check recorded technical blockers.',


 'La corrida ejecutaría este mismo filtro y fallaría en la preparación. Revisa el identificador de cadena del receptor.': 'The run would apply this same filter and fail during preparation. Check the receptor chain identifier.',

 'La corrida lo reutilizará tal cual; la huella identifica la fuente y la receta.': 'The run will reuse it unchanged; the fingerprint identifies the source and the preparation recipe.',


 'La corrida no conservó el bloque PDBQT exacto de esta pose.': 'The run did not preserve the exact PDBQT block of '
                                                                'this pose.',
 'La corrida no lo reutilizará: el preparador verifica la cadena y lo regenerará desde la fuente antes de ejecutar Vina.': 'The '
                                                                                                                           'run '
                                                                                                                           'will '
                                                                                                                           'not '
                                                                                                                           'reuse '
                                                                                                                           'it: '
                                                                                                                           'the '
                                                                                                                           'preparer '
                                                                                                                           'checks '
                                                                                                                           'the '
                                                                                                                           'chain '
                                                                                                                           'and '
                                                                                                                           'regenerates '
                                                                                                                           'it '
                                                                                                                           'from '
                                                                                                                           'the '
                                                                                                                           'source '
                                                                                                                           'before '
                                                                                                                           'running '
                                                                                                                           'Vina.',
 'La corrida no produjo afinidad de acoplamiento.': 'The run did not produce a docking affinity.',
 'La corrida no produjo afinidad y no declara el motivo.': 'The run did not produce affinity and does not declare the '
                                                           'motive.',
 'La corrida no registro los pesos efectivos.': 'The run did not register the effective weights.',
 'La corrida no registró a qué pH se protonó el ligando.': "The run didn't record what pH the ligand protonated to.",
 'La corrida no registró advertencias ni errores.': 'The run did not record any warnings or errors.',
 'La corrida no registró con qué criterio se eligió el microestado.': 'The run did not record what criterion the '
                                                                      'microstate was chosen.',
 'La corrida no registró qué modelo de rescoring se usó.': 'The run did not record which model of recovery was used.',
 'La corrida no registró qué motor se ejecutó.': "The run didn't record which engine was run.",
 'La corrida no registró si la predicción cayó dentro del dominio de aplicabilidad, así que no se puede afirmar que lo hiciera.': 'The '
                                                                                                                                  'run '
                                                                                                                                  'did '
                                                                                                                                  'not '
                                                                                                                                  'register '
                                                                                                                                  'if '
                                                                                                                                  'the '
                                                                                                                                  'prediction '
                                                                                                                                  'fell '
                                                                                                                                  'within '
                                                                                                                                  'the '
                                                                                                                                  'domain '
                                                                                                                                  'of '
                                                                                                                                  'applicability, '
                                                                                                                                  'so '
                                                                                                                                  'it '
                                                                                                                                  'cannot '
                                                                                                                                  'be '
                                                                                                                                  'claimed '
                                                                                                                                  'to '
                                                                                                                                  'do '
                                                                                                                                  'so.',
 'La corrida no registró un panel de anti-targets.': "The run didn't record an anti-target panel.",
 'La corrida no serializó poses ni contratos estructurales.': 'The run did not serialize poses or structural '
                                                              'contracts.',
 'La corrida no tiene un score total calculado, y un certificado es irreversible: sellar un valor ausente lo convertiría en una medida que nadie hizo. Vuelve a evaluar la molécula antes de certificarla.': 'The '
                                                                                                                                                                                                             'run '
                                                                                                                                                                                                             'does '
                                                                                                                                                                                                             'not '
                                                                                                                                                                                                             'have '
                                                                                                                                                                                                             'a '
                                                                                                                                                                                                             'calculated '
                                                                                                                                                                                                             'total '
                                                                                                                                                                                                             'score, '
                                                                                                                                                                                                             'and '
                                                                                                                                                                                                             'a '
                                                                                                                                                                                                             'certificate '
                                                                                                                                                                                                             'is '
                                                                                                                                                                                                             'irreversible: '
                                                                                                                                                                                                             'sealing '
                                                                                                                                                                                                             'an '
                                                                                                                                                                                                             'absent '
                                                                                                                                                                                                             'value '
                                                                                                                                                                                                             'would '
                                                                                                                                                                                                             'make '
                                                                                                                                                                                                             'it '
                                                                                                                                                                                                             'a '
                                                                                                                                                                                                             'measure '
                                                                                                                                                                                                             'that '
                                                                                                                                                                                                             'no '
                                                                                                                                                                                                             'one '
                                                                                                                                                                                                             'did. '
                                                                                                                                                                                                             'Re-evaluate '
                                                                                                                                                                                                             'the '
                                                                                                                                                                                                             'molecule '
                                                                                                                                                                                                             'before '
                                                                                                                                                                                                             'certifying '
                                                                                                                                                                                                             'it.',
 'La corrida reutiliza el receptor preparado sólo cuando la cadena coincide; si debe regenerarlo, exige Meeko en vez de inventar la preparación.': 'The '
                                                                                                                                                   'run '
                                                                                                                                                   'reuses '
                                                                                                                                                   'the '
                                                                                                                                                   'prepared '
                                                                                                                                                   'receptor '
                                                                                                                                                   'only '
                                                                                                                                                   'when '
                                                                                                                                                   'the '
                                                                                                                                                   'chain '
                                                                                                                                                   'matches; '
                                                                                                                                                   'if '
                                                                                                                                                   'regeneration '
                                                                                                                                                   'is '
                                                                                                                                                   'required, '
                                                                                                                                                   'it '
                                                                                                                                                   'requires '
                                                                                                                                                   'Meeko '
                                                                                                                                                   'instead '
                                                                                                                                                   'of '
                                                                                                                                                   'inventing '
                                                                                                                                                   'a '
                                                                                                                                                   'preparation.',
 'La corrida se ejecuta sobre el SMILES canónico, no sobre el texto introducido.': 'The run runs on the canonical '
                                                                                   'SMILES, not on the entered text.',
 'La corrida solicitada no produjo un resultado válido.': 'The requested run did not produce a valid result.',
 'La corrida tampoco debe continuar con coordenadas cero: hay que disponer de la estructura o declarar una caja explícita.': 'The '
                                                                                                                             'run '
                                                                                                                             'must '
                                                                                                                             'not '
                                                                                                                             'continue '
                                                                                                                             'with '
                                                                                                                             'zero '
                                                                                                                             'coordinates '
                                                                                                                             'either: '
                                                                                                                             'the '
                                                                                                                             'structure '
                                                                                                                             'must '
                                                                                                                             'be '
                                                                                                                             'available '
                                                                                                                             'or '
                                                                                                                             'an '
                                                                                                                             'explicit '
                                                                                                                             'box '
                                                                                                                             'must '
                                                                                                                             'be '
                                                                                                                             'declared.',
 'La cuenta invitada no puede recibir un traspaso: el traspaso existe para salir de ella. Regístrate y repite desde tu cuenta.': 'The '
                                                                                                                                 'guest '
                                                                                                                                 'account '
                                                                                                                                 'cannot '
                                                                                                                                 'receive '
                                                                                                                                 'a '
                                                                                                                                 'transfer: '
                                                                                                                                 'the '
                                                                                                                                 'transfer '
                                                                                                                                 'exists '
                                                                                                                                 'to '
                                                                                                                                 'exit '
                                                                                                                                 'it. '
                                                                                                                                 'Sign '
                                                                                                                                 'up '
                                                                                                                                 'and '
                                                                                                                                 'repeat '
                                                                                                                                 'from '
                                                                                                                                 'your '
                                                                                                                                 'account.',
 'La direccion de wallet de Solana no es valida': 'Solana Wallet address is not valid',
 'La disposición final no está vinculada a la huella de la corrida documentada. Se conserva como declaración, pero no se considera aplicable a esta evidencia.': 'The '
                                                                                                                                                                 'final '
                                                                                                                                                                 'provision '
                                                                                                                                                                 'is '
                                                                                                                                                                 'not '
                                                                                                                                                                 'linked '
                                                                                                                                                                 'to '
                                                                                                                                                                 'the '
                                                                                                                                                                 'track '
                                                                                                                                                                 'of '
                                                                                                                                                                 'the '
                                                                                                                                                                 'documented '
                                                                                                                                                                 'run. '
                                                                                                                                                                 'It '
                                                                                                                                                                 'is '
                                                                                                                                                                 'preserved '
                                                                                                                                                                 'as '
                                                                                                                                                                 'a '
                                                                                                                                                                 'statement, '
                                                                                                                                                                 'but '
                                                                                                                                                                 'is '
                                                                                                                                                                 'not '
                                                                                                                                                                 'considered '
                                                                                                                                                                 'applicable '
                                                                                                                                                                 'to '
                                                                                                                                                                 'this '
                                                                                                                                                                 'evidence.',

 'La estructura puede descargarse manualmente desde AlphaFold DB.': 'The structure can be downloaded manually from '
                                                                    'AlphaFold DB.',

 'La evaluacion termino con SUCCESS, pero no fue posible recuperar el resultado: falta molecule_id y no existe un enlace durable al resultado persistido.': 'The '
                                                                                                                                                            'evaluation '
                                                                                                                                                            'ended '
                                                                                                                                                            'with '
                                                                                                                                                            'SUCCESS, '
                                                                                                                                                            'but '
                                                                                                                                                            'it '
                                                                                                                                                            'was '
                                                                                                                                                            'not '
                                                                                                                                                            'possible '
                                                                                                                                                            'to '
                                                                                                                                                            'recover '
                                                                                                                                                            'the '
                                                                                                                                                            'result: '
                                                                                                                                                            'molecule_id '
                                                                                                                                                            'is '
                                                                                                                                                            'missing '
                                                                                                                                                            'and '
                                                                                                                                                            'there '
                                                                                                                                                            'is '
                                                                                                                                                            'no '
                                                                                                                                                            'durable '
                                                                                                                                                            'link '
                                                                                                                                                            'to '
                                                                                                                                                            'the '
                                                                                                                                                            'persistent '
                                                                                                                                                            'result.',

 'La evaluación base no conserva un receptor verificable; no se puede construir una tabla SAR comparable.': 'The '
                                                                                                            'baseline '
                                                                                                            'assessment '
                                                                                                            'does not '
                                                                                                            'retain a '
                                                                                                            'verifiable '
                                                                                                            'receptor; '
                                                                                                            'a '
                                                                                                            'comparable '
                                                                                                            'SAR table '
                                                                                                            'cannot be '
                                                                                                            'constructed.',
 'La evaluación falló (recuperado desde DB).': 'The evaluation failed (recovered from DB).',
 'La evaluación falló.': 'The evaluation failed.',
 'La evaluación no existe o ya no está disponible.': 'Evaluation does not exist or is no longer available.',
 'La evaluación ya no está disponible.': 'The evaluation is no longer available.',
 'La evidencia disponible permite continuar dentro del mismo protocolo, conservando las limitaciones documentadas.': 'The available evidence supports continuing within the same protocol, subject to the documented limitations.',

 'La exportación de Meeko (mk_export) excedió el timeout de 60 segundos.': 'The export of Meeko (mk_export) exceeded '
                                                                           'the 60-second timeout.',

 'La firma institucional fue retirada. Usa el flujo experimental de wallet o la identidad efímera de Solana devnet.': 'Institutional '
                                                                                                                      'signing '
                                                                                                                      'was '
                                                                                                                      'removed. '
                                                                                                                      'Use '
                                                                                                                      'the '
                                                                                                                      'experimental '
                                                                                                                      'wallet '
                                                                                                                      'workflow '
                                                                                                                      'or '
                                                                                                                      'the '
                                                                                                                      'ephemeral '
                                                                                                                      'Solana '
                                                                                                                      'devnet '
                                                                                                                      'identity.',
 'La firma institucional fue retirada. Usa el registro experimental de Solana devnet desde la ventana de certificación.': 'Institutional '
                                                                                                                          'signing '
                                                                                                                          'was '
                                                                                                                          'removed. '
                                                                                                                          'Use '
                                                                                                                          'the '
                                                                                                                          'experimental '
                                                                                                                          'Solana '
                                                                                                                          'devnet '
                                                                                                                          'registration '
                                                                                                                          'from '
                                                                                                                          'the '
                                                                                                                          'certification '
                                                                                                                          'window.',
 'La forma protonada y el tautómero los fija la etapa de conformación durante la corrida. Anticiparlos aquí sería inventar una decisión que todavía no se ha tomado.': 'The '
                                                                                                                                                                       'protonated '
                                                                                                                                                                       'form '
                                                                                                                                                                       'and '
                                                                                                                                                                       'the '
                                                                                                                                                                       'tautomer '
                                                                                                                                                                       'fix '
                                                                                                                                                                       'them '
                                                                                                                                                                       'the '
                                                                                                                                                                       'stage '
                                                                                                                                                                       'of '
                                                                                                                                                                       'conformation '
                                                                                                                                                                       'during '
                                                                                                                                                                       'the '
                                                                                                                                                                       'run. '
                                                                                                                                                                       'To '
                                                                                                                                                                       'anticipate '
                                                                                                                                                                       'them '
                                                                                                                                                                       'here '
                                                                                                                                                                       'would '
                                                                                                                                                                       'be '
                                                                                                                                                                       'to '
                                                                                                                                                                       'invent '
                                                                                                                                                                       'a '
                                                                                                                                                                       'decision '
                                                                                                                                                                       'that '
                                                                                                                                                                       'has '
                                                                                                                                                                       'not '
                                                                                                                                                                       'yet '
                                                                                                                                                                       'been '
                                                                                                                                                                       'made.',
 'La huella de la comprobación previa no coincide con la calculada ahora. Vuelve a comprobar antes de ejecutar.': 'The previous check fingerprint does not match the one calculated now. Check again before running.',
 'La mejor afinidad es débil (> -3.0 kcal/mol); interpretar como baja evidencia de unión en este setup de docking.': 'The '
                                                                                                                     'best '
                                                                                                                     'affinity '
                                                                                                                     'is '
                                                                                                                     'weak '
                                                                                                                     '(> '
                                                                                                                     '-3.0 '
                                                                                                                     'kcal/mol); '
                                                                                                                     'interpret '
                                                                                                                     'as '
                                                                                                                     'low '
                                                                                                                     'evidence '
                                                                                                                     'of '
                                                                                                                     'binding '
                                                                                                                     'in '
                                                                                                                     'this '
                                                                                                                     'setup '
                                                                                                                     'of '
                                                                                                                     'docking.',
 'La misma para todas las filas. Se resolvió una vez, al abrir la corrida.': 'The same for every row. It was resolved '
                                                                             'once when the run was opened.',
 'La molécula no ha sido evaluada': 'The molecule has not been evaluated',

 'La molécula no tiene un resultado de evaluación que documentar.': 'The molecule has no evaluation result to '
                                                                    'document.',
 'La pose no conservó su bloque PDBQT; no hay coordenadas que validar.': 'The pose did not retain its PDBQT block; '
                                                                         'there are no coordinates to validate.',
 'La pose recomendada no está confirmada como físicamente válida. No se elige otra en su lugar: escoger la siguiente que pase sería una decisión que nadie tomó y para la que el modelo no fue entrenado.': 'The recommended pose is not confirmed as physically valid. No other pose is chosen in its place: choosing the next one that passes would be a decision that no one made and for which the model was not trained.',

 'La pose sugerida no está confirmada como físicamente válida, y NO se sustituye por otra: elegir «la siguiente que pase» sería una decisión que nadie tomó.': 'The '
                                                                                                                                                               'suggested '
                                                                                                                                                               'pose '
                                                                                                                                                               'is '
                                                                                                                                                               'not '
                                                                                                                                                               'confirmed '
                                                                                                                                                               'as '
                                                                                                                                                               'physically '
                                                                                                                                                               'valid, '
                                                                                                                                                               'and '
                                                                                                                                                               'is '
                                                                                                                                                               'NOT '
                                                                                                                                                               'replaced '
                                                                                                                                                               'by '
                                                                                                                                                               'another: '
                                                                                                                                                               'choosing '
                                                                                                                                                               '‘the '
                                                                                                                                                               'next '
                                                                                                                                                               'one '
                                                                                                                                                               'to '
                                                                                                                                                               'pass’ '
                                                                                                                                                               'would '
                                                                                                                                                               'be '
                                                                                                                                                               'a '
                                                                                                                                                               'decision '
                                                                                                                                                               'that '
                                                                                                                                                               'no '
                                                                                                                                                               'one '
                                                                                                                                                               'took.',
 'La preparación no retira ningún heteroátomo de esta estructura.': 'The preparation does not remove any heteroatom '
                                                                    'from this structure.',

 'La preparación terminó sin generar el archivo receptor .pdbqt esperado.': 'The preparation ended without generating '
                                                                            'the expected .pdbqt receptor file.',
 'La preparación ya no permite ejecutar esta corrida. Vuelve a comprobarla y revisa los bloqueantes.': 'The '
                                                                                                       'preparation no '
                                                                                                       'longer allows '
                                                                                                       'running this '
                                                                                                       'run. Check it '
                                                                                                       'again and '
                                                                                                       'check the '
                                                                                                       'blockers.',

 'La salida derivada está fuera del dominio de aplicabilidad declarado.': 'The derived output is outside the declared applicability domain.',
 'La semilla reportada por Vina difiere de la semilla configurada; revisar reproducibilidad del entorno.': 'The seed '
                                                                                                           'reported '
                                                                                                           'by Vina '
                                                                                                           'differs '
                                                                                                           'from the '
                                                                                                           'configured '
                                                                                                           'seed; '
                                                                                                           'review '
                                                                                                           'reproducibility '
                                                                                                           'of the '
                                                                                                           'environment.',
 'La separación entre poses es una señal descriptiva no calibrada; no debe interpretarse como confianza estadística.': 'The '
                                                                                                                       'separation '
                                                                                                                       'between '
                                                                                                                       'poses '
                                                                                                                       'is '
                                                                                                                       'an '
                                                                                                                       'uncalibrated '
                                                                                                                       'descriptive '
                                                                                                                       'signal; '
                                                                                                                       'it '
                                                                                                                       'should '
                                                                                                                       'not '
                                                                                                                       'be '
                                                                                                                       'interpreted '
                                                                                                                       'as '
                                                                                                                       'statistical '
                                                                                                                       'confidence.',

 'La tarea ya no existe en el proceso local y no se encontro un resultado persistido. Puedes volver a ejecutar la evaluacion.': 'The '
                                                                                                                                'task '
                                                                                                                                'no '
                                                                                                                                'longer '
                                                                                                                                'exists '
                                                                                                                                'in '
                                                                                                                                'the '
                                                                                                                                'local '
                                                                                                                                'process '
                                                                                                                                'and '
                                                                                                                                'no '
                                                                                                                                'persistent '
                                                                                                                                'result '
                                                                                                                                'was '
                                                                                                                                'found. '
                                                                                                                                'You '
                                                                                                                                'can '
                                                                                                                                're-run '
                                                                                                                                'the '
                                                                                                                                'evaluation.',
 'La transacción no corresponde a esta molécula': 'The transaction does not correspond to this molecule',
 'La transacción no corresponde a la corrida y target actuales': 'The transaction does not correspond to the current '
                                                                 'run and target',
 'La transferencia no se completó; no se generó un ligando acoplable.': 'The transfer was not completed; no dockable ligand was generated.',
 'La traza de reproducibilidad está incompleta.': 'The trace of reproducibility is incomplete.',

 'Las filas NO elegibles nunca entraron: el preflight las declaró inválidas antes de ejecutar. No desaparecen del recuento porque el denominador tiene que seguir siendo el del archivo que se subió.': 'The '
                                                                                                                                                                                                        'non-eligible '
                                                                                                                                                                                                        'rows '
                                                                                                                                                                                                        'never '
                                                                                                                                                                                                        'entered: '
                                                                                                                                                                                                        'the '
                                                                                                                                                                                                        'preflight '
                                                                                                                                                                                                        'declared '
                                                                                                                                                                                                        'them '
                                                                                                                                                                                                        'invalid '
                                                                                                                                                                                                        'before '
                                                                                                                                                                                                        'executing. '
                                                                                                                                                                                                        'They '
                                                                                                                                                                                                        'do '
                                                                                                                                                                                                        'not '
                                                                                                                                                                                                        'disappear '
                                                                                                                                                                                                        'from '
                                                                                                                                                                                                        'counting '
                                                                                                                                                                                                        'because '
                                                                                                                                                                                                        'the '
                                                                                                                                                                                                        'denominator '
                                                                                                                                                                                                        'has '
                                                                                                                                                                                                        'to '
                                                                                                                                                                                                        'remain '
                                                                                                                                                                                                        'the '
                                                                                                                                                                                                        'one '
                                                                                                                                                                                                        'in '
                                                                                                                                                                                                        'the '
                                                                                                                                                                                                        'file '
                                                                                                                                                                                                        'that '
                                                                                                                                                                                                        'was '
                                                                                                                                                                                                        'uploaded.',
 'LogP > 5 puede indicar pobre solubilidad acuosa': 'LogP > 5 may indicate poor aqueous solubility',
 'Los controles físicos no corrieron enteros sobre todas las poses, o una pose alternativa falla; «revisión necesaria» no equivale a pose aprobada.': 'Either the physical checks did not run across all poses or an alternative pose fails; “review required” does not mean a pose is approved.',
 'Al menos la pose principal falla los controles de química o geometría: la afinidad de esta corrida no sostiene una priorización del ligando.': 'At least the primary pose fails the chemistry or geometry checks: this run’s affinity does not support prioritizing the ligand.',

 'Los controles se reportan aparte y NO entran en la población de las métricas: un control positivo dentro de la población sube el enriquecimiento sin decir nada sobre la cohorte.': 'Controls are reported separately and are NOT included in the metrics population: a positive control inside the population raises enrichment without saying anything about the cohort.',
 'Los hotspots no restringen el acoplamiento; se usan para describir el sitio y para el análisis posterior.': 'Hotspots '
                                                                                                              'do not '
                                                                                                              'restrict '
                                                                                                              'the '
                                                                                                              'docking; '
                                                                                                              'they '
                                                                                                              'are '
                                                                                                              'used to '
                                                                                                              'describe '
                                                                                                              'the '
                                                                                                              'site '
                                                                                                              'and for '
                                                                                                              'subsequent '
                                                                                                              'analysis.',

 'Los scores de confianza de DiffDock NO son comparables con las afinidades (kcal/mol) de AutoDock Vina.': 'DiffDock '
                                                                                                           'confidence '
                                                                                                           'scores are '
                                                                                                           'NOT '
                                                                                                           'comparable '
                                                                                                           'with '
                                                                                                           'AutoDock '
                                                                                                           'Vina '
                                                                                                           'affinities '
                                                                                                           '(kcal/mol).',



 'MM-GBSA no convergió — energía virtualmente sin cambio': 'MM-GBSA did not converge — energy virtually unchanged',

 'MM-GBSA y otros métodos pueden aplicar políticas distintas. Un resultado no se puede comparar con otro sin declarar la política de cada ruta.': 'MM-GBSA '
                                                                                                                                                  'and '
                                                                                                                                                  'other '
                                                                                                                                                  'methods '
                                                                                                                                                  'can '
                                                                                                                                                  'apply '
                                                                                                                                                  'different '
                                                                                                                                                  'policies. '
                                                                                                                                                  'One '
                                                                                                                                                  'result '
                                                                                                                                                  'cannot '
                                                                                                                                                  'be '
                                                                                                                                                  'compared '
                                                                                                                                                  'to '
                                                                                                                                                  'another '
                                                                                                                                                  'without '
                                                                                                                                                  'declaring '
                                                                                                                                                  'the '
                                                                                                                                                  'policy '
                                                                                                                                                  'of '
                                                                                                                                                  'each '
                                                                                                                                                  'route.',

 'MW > 500 Da viola la regla de Lipinski': 'MW > 500 Da violates Lipinski rule',
 'Matriz de evidencia por dimensión': 'Evidence matrix by dimension',


 'Metales del receptor': 'Receptor metals',
 'Metodología observada y procedencia': 'Observed methodology and provenance',
 'Modelo de rescoring y familia estructural': 'Rescoring model and structural family',

 'MolPocket no detectó cavidades en la estructura APO.': 'MolPocket did not detect cavities in the APO structure.',


 'Molécula no encontrada': 'Molecule not found',
 'Molécula no evaluada': 'Molecule not evaluated',
 'Moléculas únicas acopladas': 'Single molecules coupled',
 'Motor de docking': 'Docking engine',
 'NINGÚN control declarado. No se ha inferido ninguno a partir de nombres, etiquetas ni posiciones. Sin control, el resultado de esta cohorte no tiene contra qué contrastarse.': 'NO '
                                                                                                                                                                                  'declared '
                                                                                                                                                                                  'control. '
                                                                                                                                                                                  'None '
                                                                                                                                                                                  'has '
                                                                                                                                                                                  'been '
                                                                                                                                                                                  'inferred '
                                                                                                                                                                                  'from '
                                                                                                                                                                                  'names, '
                                                                                                                                                                                  'labels '
                                                                                                                                                                                  'or '
                                                                                                                                                                                  'positions. '
                                                                                                                                                                                  'Without '
                                                                                                                                                                                  'control, '
                                                                                                                                                                                  'the '
                                                                                                                                                                                  'result '
                                                                                                                                                                                  'of '
                                                                                                                                                                                  'this '
                                                                                                                                                                                  'cohort '
                                                                                                                                                                                  'has '
                                                                                                                                                                                  'nothing '
                                                                                                                                                                                  'to '
                                                                                                                                                                                  'contrast '
                                                                                                                                                                                  'with.',
 'NO SE SUSTITUYE. Se declara revisión': 'NOT SUBSTITUATE.',
 'NO puede concluirse:': 'It cannot be concluded:',
 'Nada que decidir: no hay especies en disputa.': 'Nothing to decide: there are no species in dispute.',
 'Ningun SMILES valido en el archivo': 'No valid SMILES in the file',
 'Ninguna de estas salidas es una probabilidad de unión, eficacia, seguridad o éxito experimental. Para decidir el siguiente paso debe usarse la matriz de evidencia y sus flags de abstención.': 'None '
                                                                                                                                                                                                  'of '
                                                                                                                                                                                                  'these '
                                                                                                                                                                                                  'outputs '
                                                                                                                                                                                                  'is '
                                                                                                                                                                                                  'a '
                                                                                                                                                                                                  'probability '
                                                                                                                                                                                                  'of '
                                                                                                                                                                                                  'binding, '
                                                                                                                                                                                                  'efficacy, '
                                                                                                                                                                                                  'safety '
                                                                                                                                                                                                  'or '
                                                                                                                                                                                                  'experimental '
                                                                                                                                                                                                  'success. '
                                                                                                                                                                                                  'To '
                                                                                                                                                                                                  'decide '
                                                                                                                                                                                                  'the '
                                                                                                                                                                                                  'next '
                                                                                                                                                                                                  'step, '
                                                                                                                                                                                                  'the '
                                                                                                                                                                                                  'evidence '
                                                                                                                                                                                                  'matrix '
                                                                                                                                                                                                  'and '
                                                                                                                                                                                                  'its '
                                                                                                                                                                                                  'abstention '
                                                                                                                                                                                                  'flags '
                                                                                                                                                                                                  'should '
                                                                                                                                                                                                  'be '
                                                                                                                                                                                                  'used.',
 'Ninguno de estos pasos recomienda un fármaco, un candidato clínico ni un compuesto seguro. Describen qué trabajo computacional queda justificado.': 'None '
                                                                                                                                                      'of '
                                                                                                                                                      'these '
                                                                                                                                                      'steps '
                                                                                                                                                      'recommend '
                                                                                                                                                      'a '
                                                                                                                                                      'drug, '
                                                                                                                                                      'a '
                                                                                                                                                      'clinical '
                                                                                                                                                      'candidate, '
                                                                                                                                                      'or '
                                                                                                                                                      'a '
                                                                                                                                                      'safe '
                                                                                                                                                      'compound. '
                                                                                                                                                      'Describe '
                                                                                                                                                      'what '
                                                                                                                                                      'computational '
                                                                                                                                                      'work '
                                                                                                                                                      'is '
                                                                                                                                                      'justified.',
 'No evaluado: el SMILES no se pudo interpretar.': 'Not evaluated: SMILES could not be interpreted.',
 'No evaluado: sin la fuente en disco no hay nada que comparar.': 'Not evaluated: without the source on disk there is '
                                                                  'nothing to compare.',

 'No existe el PDB fuente necesario para derivar la caja de docking.': 'There is no PDB source needed to derive the '
                                                                       'docking box.',
 'No existe el receptor solicitado.': 'The requested receptor does not exist.',
 'No existe la cohorte de esta corrida.': 'There is no cohort of this run.',
 'No existe la cohorte solicitada.': 'There is no cohort requested.',
 'No existe la corrida solicitada.': 'The requested run does not exist.',
 'No existe la molécula solicitada.': 'There is no requested molecule.',




 'No existe una corrida para la cohorte solicitada.': 'No run exists for the requested cohort.',

 'No hace falta regenerar el receptor: existe un PDBQT compatible y sellado en la huella.': 'The receptor does not '
                                                                                            'need regeneration: a '
                                                                                            'compatible PDBQT is '
                                                                                            'sealed in the '
                                                                                            'fingerprint.',
 'No hay cuenta invitada en esta máquina: no hay nada que traspasar.': 'There is no guest account in this machine: '
                                                                       'there is nothing to pass through.',

 'No priorizar el ligando ni iniciar cálculos posteriores hasta recuperar poses y resolver los controles fallidos.': 'Do '
                                                                                                                     'not '
                                                                                                                     'prioritize '
                                                                                                                     'ligand '
                                                                                                                     'or '
                                                                                                                     'start '
                                                                                                                     'later '
                                                                                                                     'calculations '
                                                                                                                     'until '
                                                                                                                     'you '
                                                                                                                     'recover '
                                                                                                                     'poses '
                                                                                                                     'and '
                                                                                                                     'resolve '
                                                                                                                     'failed '
                                                                                                                     'controls.',
 'No queda ninguna fila pendiente ni interrumpida. Las que fallaron no se reintentan en silencio: eso convertiría un fallo declarado en un resultado nuevo sin que nadie lo pidiera.': 'There '
                                                                                                                                                                                       'is '
                                                                                                                                                                                       'no '
                                                                                                                                                                                       'line '
                                                                                                                                                                                       'left '
                                                                                                                                                                                       'pending '
                                                                                                                                                                                       'or '
                                                                                                                                                                                       'interrupted. '
                                                                                                                                                                                       'Those '
                                                                                                                                                                                       'who '
                                                                                                                                                                                       'failed '
                                                                                                                                                                                       'do '
                                                                                                                                                                                       'not '
                                                                                                                                                                                       'retry '
                                                                                                                                                                                       'in '
                                                                                                                                                                                       'silence: '
                                                                                                                                                                                       'that '
                                                                                                                                                                                       'would '
                                                                                                                                                                                       'make '
                                                                                                                                                                                       'a '
                                                                                                                                                                                       'judgment '
                                                                                                                                                                                       'declared '
                                                                                                                                                                                       'in '
                                                                                                                                                                                       'a '
                                                                                                                                                                                       'new '
                                                                                                                                                                                       'result '
                                                                                                                                                                                       'without '
                                                                                                                                                                                       'anyone '
                                                                                                                                                                                       'asking.',

 'No se detectaron interacciones con los residuos críticos (hotspots) del receptor.': 'Interactions with critical '
                                                                                      'residues (hotspots) of the '
                                                                                      'receptor were not detected.',
 'No se detectó GPU. MM-GBSA y GNN rescoring correrán en CPU (más lento).': 'No GPU detected. MM-GBSA and GNN '
                                                                            'recorring will run in CPU (slower).',
 'No se detectó voz en el audio.': 'No voice was detected in the audio.',
 'No se encontraron SMILES validos en el archivo': 'No valid SMILES found in file',

 'No se encontraron ligandos drug-like. Los HETATM detectados son cofactores (ATP/NAD/HEM). El grid box se centro en el cofactor mas grande.': 'No '
                                                                                                                                               'drug-like '
                                                                                                                                               'ligands '
                                                                                                                                               'were '
                                                                                                                                               'found. '
                                                                                                                                               'The '
                                                                                                                                               'HETATM '
                                                                                                                                               'detected '
                                                                                                                                               'are '
                                                                                                                                               'cofactors '
                                                                                                                                               '(ATP/NAD/HEM). '
                                                                                                                                               'The '
                                                                                                                                               'grid '
                                                                                                                                               'box '
                                                                                                                                               'is '
                                                                                                                                               'centered '
                                                                                                                                               'in '
                                                                                                                                               'the '
                                                                                                                                               'largest '
                                                                                                                                               'cofactor.',
 'No se encontraron ligandos validos en el PDB. La deteccion APO por MolPocket tampoco encontro cavidades. Estructuras apo (sin ligando) requieren coordenadas manuales del grid box.': 'No '
                                                                                                                                                                                        'valid '
                                                                                                                                                                                        'ligands '
                                                                                                                                                                                        'were '
                                                                                                                                                                                        'found '
                                                                                                                                                                                        'in '
                                                                                                                                                                                        'the '
                                                                                                                                                                                        'PDB. '
                                                                                                                                                                                        'APO '
                                                                                                                                                                                        'detection '
                                                                                                                                                                                        'by '
                                                                                                                                                                                        'MolPocket '
                                                                                                                                                                                        'also '
                                                                                                                                                                                        'did '
                                                                                                                                                                                        'not '
                                                                                                                                                                                        'find '
                                                                                                                                                                                        'cavities. '
                                                                                                                                                                                        'Apo '
                                                                                                                                                                                        'structures '
                                                                                                                                                                                        '(without '
                                                                                                                                                                                        'ligands) '
                                                                                                                                                                                        'require '
                                                                                                                                                                                        'manual '
                                                                                                                                                                                        'grid '
                                                                                                                                                                                        'box '
                                                                                                                                                                                        'coordinates.',
 'No se encontraron sugerencias automáticas para esta molécula. Considerar análisis manual de la pose de docking.': 'No '
                                                                                                                    'automatic '
                                                                                                                    'suggestions '
                                                                                                                    'were '
                                                                                                                    'found '
                                                                                                                    'for '
                                                                                                                    'this '
                                                                                                                    'molecule. '
                                                                                                                    'Consider '
                                                                                                                    'manual '
                                                                                                                    'analysis '
                                                                                                                    'of '
                                                                                                                    'Docking '
                                                                                                                    'pose.',
 'No se encontro la licencia de Steam para esta aplicacion.': 'Steam license for this application was not found.',
 "No se encontró 'mk_export.py'. La exportación a SDF es necesaria para conservar conectividad y órdenes de enlace de forma defendible.": 'No '
                                                                                                                                          "'mk_export.py' "
                                                                                                                                          'was '
                                                                                                                                          'found. '
                                                                                                                                          'Export '
                                                                                                                                          'to '
                                                                                                                                          'SDF '
                                                                                                                                          'is '
                                                                                                                                          'necessary '
                                                                                                                                          'to '
                                                                                                                                          'maintain '
                                                                                                                                          'connectivity '
                                                                                                                                          'and '
                                                                                                                                          'link '
                                                                                                                                          'orders '
                                                                                                                                          'in '
                                                                                                                                          'a '
                                                                                                                                          'defensible '
                                                                                                                                          'manner.',
 "No se encontró 'mk_prepare_receptor'. El receptor no se puede preparar.": "'mk_prepare_receptor' was not found. The "
                                                                            'receptor cannot be prepared.',
 "No se encontró 'mk_prepare_receptor.py'. Instala Meeko o provee la ruta correcta en MEEKO_PREPARE_RECEPTOR_PATH. Sin esta herramienta no es científicamente defendible preparar el receptor para Vina.": 'No '
                                                                                                                                                                                                           "'mk_prepare_receptor.py' "
                                                                                                                                                                                                           'found. '
                                                                                                                                                                                                           'Install '
                                                                                                                                                                                                           'Meeko '
                                                                                                                                                                                                           'or '
                                                                                                                                                                                                           'provide '
                                                                                                                                                                                                           'the '
                                                                                                                                                                                                           'correct '
                                                                                                                                                                                                           'path '
                                                                                                                                                                                                           'in '
                                                                                                                                                                                                           'MEEKO_PREPARE_RECEPTOR_PATH. '
                                                                                                                                                                                                           'Without '
                                                                                                                                                                                                           'this '
                                                                                                                                                                                                           'tool '
                                                                                                                                                                                                           'it '
                                                                                                                                                                                                           'is '
                                                                                                                                                                                                           'not '
                                                                                                                                                                                                           'scientifically '
                                                                                                                                                                                                           'defensible '
                                                                                                                                                                                                           'to '
                                                                                                                                                                                                           'prepare '
                                                                                                                                                                                                           'the '
                                                                                                                                                                                                           'receptor '
                                                                                                                                                                                                           'for '
                                                                                                                                                                                                           'Vina.',

 'No se encontró el target asociado a esta evaluación.': 'The target associated with this evaluation was not found.',

 





 'No se pudo conectar con Solana devnet.': 'Could not connect to Solana Devnet.',



 'No se pudo extraer secuencia del péptido.': 'Sequence of the peptide could not be extracted.',
 'No se pudo extraer una secuencia de aminoácidos del SMILES.': 'A sequence of amino acids from SMILES could not be '
                                                                'removed.',
 'No se pudo fusionar el PDB del receptor con el ligando docked.': "The receptor's PDB could not be merged with the "
                                                                   'docked ligand.',








 'No se registraron incertidumbres adicionales. Esto no significa que no existan.': 'There were no additional '
                                                                                    'uncertainties, which does not '
                                                                                    'mean that they do not exist.',
 'No tienes permiso para acceder a este resultado anónimo.': "You don't have permission to access this anonymous "
                                                             'result.',
 'No tienes permiso para acceder a este resultado.': "You don't have permission to access this result.",
 'No tienes permiso para operar esta evaluación anónima.': "You don't have permission to operate this anonymous "
                                                           'evaluation.',
 'No tienes permiso para operar esta evaluación.': "You don't have permission to operate this evaluation.",
 'Observación · afinidad AutoDock Vina': 'Observation · AutoDock Vina affinity',
 'Ocurrió un error interno no controlado': 'An uncontrolled internal error occurred',

 'Origen de la caja': 'Origin of the box',

 'PDB del receptor inválido (no contiene ATOM records)': 'Invalid receptor PDB (does not contain ATOM records)',


 "PREPARACIÓN DEL LIGANDO (Meeko), antes de ejecutar Vina: no se encontró 'mk_prepare_ligand.py'. Instala Meeko o configura MEEKO_PREPARE_LIGAND_PATH correctamente.": 'LIGAND '
                                                                                                                                                                       'PREPARATION '
                                                                                                                                                                       '(Meeko), '
                                                                                                                                                                       'before '
                                                                                                                                                                       'running '
                                                                                                                                                                       'Vina: '
                                                                                                                                                                       'no '
                                                                                                                                                                       "'mk_prepare_ligand.py' "
                                                                                                                                                                       'was '
                                                                                                                                                                       'found. '
                                                                                                                                                                       'Install '
                                                                                                                                                                       'Meeko '
                                                                                                                                                                       'or '
                                                                                                                                                                       'configure '
                                                                                                                                                                       'MEEKO_PREPARE_LIGAND_PATH '
                                                                                                                                                                       'correctly.',
 'PUEDE concluirse:': 'It may be concluded:',
 'Panel de Selectividad Farmacologica': 'Pharmaceutical Selectivity Panel',
 'Parámetro': 'Parameter',
 'Perfil Fisicoquímico (ADME)': 'Physicochemical Profile (ADME)',
 'Perfiles de Energía por Pose': 'Energy Profiles by Pose',
 'Pesos efectivos del stacking M4': 'Effective M4 stacking weights',

 'Pocket detectado por MolPocket (sin ligando)': 'Pocket detected by MolPocket (without ligand)',
 'Preparación del ligando y análisis': 'Preparation of ligand and analysis',
 'Preparación en condición desolvatada: se retiraron las aguas cristalográficas del receptor. No se pudo leer la estructura depositada para contar cuántas había en el sitio.': 'Desolvated '
                                                                                                                                                                                'preparation: '
                                                                                                                                                                                'crystallographic '
                                                                                                                                                                                'waters '
                                                                                                                                                                                'were '
                                                                                                                                                                                'removed '
                                                                                                                                                                                'from '
                                                                                                                                                                                'the '
                                                                                                                                                                                'receptor. '
                                                                                                                                                                                'The '
                                                                                                                                                                                'deposited '
                                                                                                                                                                                'structure '
                                                                                                                                                                                'could '
                                                                                                                                                                                'not '
                                                                                                                                                                                'be '
                                                                                                                                                                                'read '
                                                                                                                                                                                'to '
                                                                                                                                                                                'count '
                                                                                                                                                                                'how '
                                                                                                                                                                                'many '
                                                                                                                                                                                'were '
                                                                                                                                                                                'in '
                                                                                                                                                                                'the '
                                                                                                                                                                                'site.',
 'Preparador del receptor': 'Receptor preparation tool',



 'RAM < 8 GB: algunas funciones pueden usar swap. Cerrá otras apps.': 'RAM < 8 GB: Some features can use swap. It '
                                                                      'closes other apps.',
 'RDKit no disponible para generación de sugerencias': 'RDKit not available for suggestion generation',
 'RDKit no pudo reconstruir la molécula desde el SMILES canónico': 'RDKit could not reconstruct the molecule from the '
                                                                   'canonical SMILES',
 'Rango conservador que incluye fragmentos (100+) hasta moléculas drug-like complejas (800). Excluye péptidos grandes.': 'Conservative '
                                                                                                                         'range '
                                                                                                                         'that '
                                                                                                                         'includes '
                                                                                                                         'fragments '
                                                                                                                         '(100+) '
                                                                                                                         'to '
                                                                                                                         'complex '
                                                                                                                         'drug-like '
                                                                                                                         'molecules '
                                                                                                                         '(800). '
                                                                                                                         'It '
                                                                                                                         'excludes '
                                                                                                                         'large '
                                                                                                                         'peptides.',

 'Recuento (sobre el archivo)': 'Count (on file)',
 'Reducir LogP puede afectar la afinidad por el target': 'Reducing LogP can affect target affinity',
 'Reducir polaridad puede disminuir solubilidad': 'Reducing polarity can decrease solubility',
 'Reducir área polar': 'Reduce Polar Area',


 'Regla de 5 original de Lipinski.': "Lipinski's original Rule of Five.",


 'Reglas de Veber para biodisponibilidad oral.': 'Veber rules for oral bioavailability.',
 'Relación de la corrida con los inputs actuales': 'Relationship of the run with current inputs',
 'Residuos de referencia': 'Reference residues',
 'Resolución reportada en el header de 7E2Y.': 'Resolution reported in the 7E2Y header.',
 'Resultado STUB: no usar para investigación.': 'STUB result: not used for research.',
 'Revisión química del ligando': 'Chemical review of ligand',

 'SHA-256 del preparado': 'SHA-256 from the preparation',

 'SMILES del péptido vacío o demasiado corto': 'SMILES of empty peptide or too short',
 'SMILES inválido': 'SMILES invalid',

 'Se declaran una a una. Una molécula que no llegó al final no desaparece del informe: un recuento que sólo hablara de lo que salió bien no sería una cobertura.': 'They '
                                                                                                                                                                   'declare '
                                                                                                                                                                   'themselves '
                                                                                                                                                                   'one '
                                                                                                                                                                   'by '
                                                                                                                                                                   'one. '
                                                                                                                                                                   'A '
                                                                                                                                                                   'molecule '
                                                                                                                                                                   'that '
                                                                                                                                                                   'did '
                                                                                                                                                                   'not '
                                                                                                                                                                   'come '
                                                                                                                                                                   'to '
                                                                                                                                                                   'the '
                                                                                                                                                                   'end '
                                                                                                                                                                   'does '
                                                                                                                                                                   'not '
                                                                                                                                                                   'disappear '
                                                                                                                                                                   'from '
                                                                                                                                                                   'the '
                                                                                                                                                                   'report: '
                                                                                                                                                                   'a '
                                                                                                                                                                   'recount '
                                                                                                                                                                   'that '
                                                                                                                                                                   'only '
                                                                                                                                                                   'spoke '
                                                                                                                                                                   'of '
                                                                                                                                                                   'what '
                                                                                                                                                                   'went '
                                                                                                                                                                   'well '
                                                                                                                                                                   'would '
                                                                                                                                                                   'not '
                                                                                                                                                                   'be '
                                                                                                                                                                   'a '
                                                                                                                                                                   'coverage.',



 'Se informa JUNTO a la afinidad de Vina, no en su lugar: son dos cantidades con distinto error y distinto dominio de validez.': 'It '
                                                                                                                                 'is '
                                                                                                                                 'reported '
                                                                                                                                 'TOGETHER '
                                                                                                                                 'the '
                                                                                                                                 'affinity '
                                                                                                                                 'of '
                                                                                                                                 'Vina, '
                                                                                                                                 'not '
                                                                                                                                 'in '
                                                                                                                                 'its '
                                                                                                                                 'place: '
                                                                                                                                 'they '
                                                                                                                                 'are '
                                                                                                                                 'two '
                                                                                                                                 'quantities '
                                                                                                                                 'with '
                                                                                                                                 'different '
                                                                                                                                 'error '
                                                                                                                                 'and '
                                                                                                                                 'different '
                                                                                                                                 'domain '
                                                                                                                                 'of '
                                                                                                                                 'validity.',
 'Se listan para comparar. NINGUNA se selecciona automáticamente.': 'They are listed for comparison. NO ONE is '
                                                                    'selected automatically.',



 'Se reportan valores y reglas por separado; no se convierten en una calificación global.': 'Values and rules are '
                                                                                            'reported separately; they '
                                                                                            'do not become a global '
                                                                                            'rating.',
 'Secuencia del receptor corta o no detectable. El plegamiento del complejo puede ser menos preciso.': 'Short or '
                                                                                                       'undetectable '
                                                                                                       'receptor '
                                                                                                       'sequence. The '
                                                                                                       'folding of the '
                                                                                                       'complex may be '
                                                                                                       'less accurate.',
 'Selectividad omitida: sin poses de docking disponibles': 'Missing Selectivity: No Docking Possessions Available',
 'Selector: falló': 'Selector: Failed',
 'Selector: recomendó': 'Selector: recommended',
 'Selector: se abstuvo': 'Selector: abstained',
 'Semilla Estocástica': 'Stochastic seed',
 'Semilla fija para reproducibilidad determinística.': 'Fixed seed for deterministic reproducibility.',
 'Servicio ColabFold no configurado. Se usó AutoDock Vina.': 'Unconfigured ColabFold service. AutoDock Vina was used.',
 'Servicio ESMFold no configurado (ESMFOLD_API_URL ausente). Se usó AutoDock Vina como fallback.': 'Unconfigured '
                                                                                                   'ESMFold service '
                                                                                                   '(ESMFOLD_API_URL '
                                                                                                   'absent). AutoDock '
                                                                                                   'Vina was used as '
                                                                                                   'fallback.',
 'Servicio cerrándose': 'Service closing',
 'Servicio de ColabFold fuera de línea. Se usó AutoDock Vina.': 'ColabFold service off-line. AutoDock Vina was used.',
 'Si alguna de esas especies pertenece al sitio de unión, la corrida acopla contra un sitio distinto del cristalográfico. La decisión es tuya; el sistema no la toma ni la corrige.': 'If any of these species belong to the binding site, the run docks against a site other than the crystallographic one. The decision is yours; the system neither makes nor corrects it.',

 'Sin el ejecutable solicitado no se puede afirmar que la corrida corresponde al motor inspeccionado. El fallback silencioso no forma parte del contrato del caso.': 'Without '
                                                                                                                                                                     'the '
                                                                                                                                                                     'requested '
                                                                                                                                                                     'executable '
                                                                                                                                                                     'it '
                                                                                                                                                                     'cannot '
                                                                                                                                                                     'be '
                                                                                                                                                                     'said '
                                                                                                                                                                     'that '
                                                                                                                                                                     'the '
                                                                                                                                                                     'run '
                                                                                                                                                                     'corresponds '
                                                                                                                                                                     'to '
                                                                                                                                                                     'the '
                                                                                                                                                                     'inspected '
                                                                                                                                                                     'engine. '
                                                                                                                                                                     'The '
                                                                                                                                                                     'silent '
                                                                                                                                                                     'fallback '
                                                                                                                                                                     'is '
                                                                                                                                                                     'not '
                                                                                                                                                                     'part '
                                                                                                                                                                     'of '
                                                                                                                                                                     'the '
                                                                                                                                                                     'contract '
                                                                                                                                                                     'of '
                                                                                                                                                                     'the '
                                                                                                                                                                     'case.',
 'Sin este dato no se puede saber si el ranking del motor está respaldado para este receptor.': 'Without this data it '
                                                                                                'is not possible to '
                                                                                                'know if the engine '
                                                                                                'ranking is supported '
                                                                                                'for this receptor.',
 'Sin fórmula ni versión publicadas: no es interpretable como probabilidad, confianza ni calidad. No decisional.': 'Without '
                                                                                                                   'formula '
                                                                                                                   'or '
                                                                                                                   'published '
                                                                                                                   'version: '
                                                                                                                   'it '
                                                                                                                   'is '
                                                                                                                   'not '
                                                                                                                   'interpretable '
                                                                                                                   'as '
                                                                                                                   'probability, '
                                                                                                                   'confidence '
                                                                                                                   'or '
                                                                                                                   'quality.',
 'Sin la cadena en el nombre no hay forma de saber si están en el receptor.': 'Without the chain in the name, there is '
                                                                              'no way to know whether they are in the '
                                                                              'receptor.',
 'Sin leer la fuente no se puede afirmar nada sobre lo que entra en la corrida.': 'Without reading the source, nothing can be said about what enters the run.',
 'Sin molécula no hay átomos que comprobar.': 'No molecule, no atoms to check.',

 'Sin plantilla química ni SMILES declarados. La química no se deduce de los tipos AutoDock.': 'No chemical template '
                                                                                               'or declared SMILES. '
                                                                                               'Chemistry is not '
                                                                                               'deduced from AutoDock '
                                                                                               'types.',


 'Sin una molécula interpretable no hay nada que acoplar: la corrida fallaría igual, más tarde.': 'Without an interpretable molecule there is nothing to dock: the run would fail all the same, later.',
 'Solana devnet respondió sin estado saludable.': 'Solana Devnet responded without a healthy state.',
 'Sustitución automática': 'Automatic replacement',

 'Sólo un CONTROL SUPERADO explícito autoriza llamar válida a una pose. REVISIÓN describe una batería que no corrió entera, y NO EVALUADO un validador que no corrió: las dos describen lo que le pasó a la comprobación, nunca a la molécula, y ninguna de las dos es evidencia negativa sobre el compuesto.': 'Only '
                                                                                                                                                                                                                                                                                                                'an '
                                                                                                                                                                                                                                                                                                                'explicit '
                                                                                                                                                                                                                                                                                                                'SUPERITED '
                                                                                                                                                                                                                                                                                                                'CONTROL '
                                                                                                                                                                                                                                                                                                                'authorizes '
                                                                                                                                                                                                                                                                                                                'calling '
                                                                                                                                                                                                                                                                                                                'a '
                                                                                                                                                                                                                                                                                                                'pose '
                                                                                                                                                                                                                                                                                                                'valid. '
                                                                                                                                                                                                                                                                                                                'REVISION '
                                                                                                                                                                                                                                                                                                                'describes '
                                                                                                                                                                                                                                                                                                                'a '
                                                                                                                                                                                                                                                                                                                'battery '
                                                                                                                                                                                                                                                                                                                'that '
                                                                                                                                                                                                                                                                                                                'did '
                                                                                                                                                                                                                                                                                                                'not '
                                                                                                                                                                                                                                                                                                                'run '
                                                                                                                                                                                                                                                                                                                'whole, '
                                                                                                                                                                                                                                                                                                                'and '
                                                                                                                                                                                                                                                                                                                'NOT '
                                                                                                                                                                                                                                                                                                                'EVALUATED '
                                                                                                                                                                                                                                                                                                                'a '
                                                                                                                                                                                                                                                                                                                'validator '
                                                                                                                                                                                                                                                                                                                'that '
                                                                                                                                                                                                                                                                                                                'did '
                                                                                                                                                                                                                                                                                                                'not '
                                                                                                                                                                                                                                                                                                                'run: '
                                                                                                                                                                                                                                                                                                                'the '
                                                                                                                                                                                                                                                                                                                'two '
                                                                                                                                                                                                                                                                                                                'describe '
                                                                                                                                                                                                                                                                                                                'what '
                                                                                                                                                                                                                                                                                                                'happened '
                                                                                                                                                                                                                                                                                                                'to '
                                                                                                                                                                                                                                                                                                                'the '
                                                                                                                                                                                                                                                                                                                'test, '
                                                                                                                                                                                                                                                                                                                'never '
                                                                                                                                                                                                                                                                                                                'to '
                                                                                                                                                                                                                                                                                                                'the '
                                                                                                                                                                                                                                                                                                                'molecule, '
                                                                                                                                                                                                                                                                                                                'and '
                                                                                                                                                                                                                                                                                                                'neither '
                                                                                                                                                                                                                                                                                                                'is '
                                                                                                                                                                                                                                                                                                                'negative '
                                                                                                                                                                                                                                                                                                                'evidence '
                                                                                                                                                                                                                                                                                                                'about '
                                                                                                                                                                                                                                                                                                                'the '
                                                                                                                                                                                                                                                                                                                'compound.',
 'TPSA < 20 Å² puede indicar baja solubilidad': 'TPSA < 20 Å² may indicate low solubility',
 'TPSA > 140 Å² compromete permeabilidad de membrana': 'TPSA > 140 Å² compromises membrane permeability',
 'Tamaño (bytes)': 'Size (bytes)',




 'Todavía no existe: la corrida lo generará con Meeko.': "It doesn't exist yet: the run will generate it with Meeko.",
 'Todos los elementos tienen parámetros en el campo de fuerza de Vina.': 'All elements have parameters in the force '
                                                                         'field of Vina.',


 'Token de refresco inválido': 'Invalid soda token',
 'Token de refresco inválido o expirado': 'Token of invalid or expired soda',
 'Token inválido': 'Token invalid',
 "Token inválido: falta claim 'sub'": "Invalid Token: missing claim 'sub'",
 'Token inválido: subject no es un UUID válido': 'Invalid Token: subject is not a valid UUID',
 'Transferencia química ESMFold → ligando': 'Chemical transfer ESMFold → ligand',
 'Trazas técnicas registradas': 'Recorded technical traces',

 'Un elemento sin parámetros produce una energía que no se puede comparar con las demás.': 'An element without '
                                                                                           'parameters produces an '
                                                                                           'energy that cannot be '
                                                                                           'compared to the others.',
 'Un hueco junto al sitio cambia la forma del bolsillo. Requiere un análisis que esta comprobación previa todavía no hace.': 'A '
                                                                                                                             'hole '
                                                                                                                             'next '
                                                                                                                             'to '
                                                                                                                             'the '
                                                                                                                             'site '
                                                                                                                             'changes '
                                                                                                                             'the '
                                                                                                                             'shape '
                                                                                                                             'of '
                                                                                                                             'the '
                                                                                                                             'pocket. '
                                                                                                                             'It '
                                                                                                                             'requires '
                                                                                                                             'an '
                                                                                                                             'analysis '
                                                                                                                             'that '
                                                                                                                             'this '
                                                                                                                             'previous '
                                                                                                                             'check '
                                                                                                                             'does '
                                                                                                                             'not '
                                                                                                                             'yet '
                                                                                                                             'do.',

 'Una métrica calculada sin cumplir sus condiciones no es una métrica aproximada: es un número que parece un resultado.': 'A '
                                                                                                                          'metric '
                                                                                                                          'calculated '
                                                                                                                          'without '
                                                                                                                          'meeting '
                                                                                                                          'its '
                                                                                                                          'conditions '
                                                                                                                          'is '
                                                                                                                          'not '
                                                                                                                          'an '
                                                                                                                          'approximate '
                                                                                                                          'metric: '
                                                                                                                          'it '
                                                                                                                          'is '
                                                                                                                          'a '
                                                                                                                          'number '
                                                                                                                          'that '
                                                                                                                          'looks '
                                                                                                                          'like '
                                                                                                                          'a '
                                                                                                                          'result.',
 'Upgrade de 20³ a 25³ Å. Grid de 20 Å penaliza moléculas drug-like típicas (MW 300-500) que son 2-3x más grandes que serotonina.': 'Upgrade '
                                                                                                                                    'from '
                                                                                                                                    '203 '
                                                                                                                                    'to '
                                                                                                                                    '253 '
                                                                                                                                    'Å. '
                                                                                                                                    'Grid '
                                                                                                                                    'of '
                                                                                                                                    '20 '
                                                                                                                                    'Å '
                                                                                                                                    'penalizes '
                                                                                                                                    'typical '
                                                                                                                                    'drug-like '
                                                                                                                                    'molecules '
                                                                                                                                    '(MW '
                                                                                                                                    '300-500) '
                                                                                                                                    'that '
                                                                                                                                    'are '
                                                                                                                                    '2-3x '
                                                                                                                                    'larger '
                                                                                                                                    'than '
                                                                                                                                    'serotonin.',
 'Validación, propiedades, confórmeros y rescoring.': 'Validation, properties, conformers and recorring.',
 'Verifica que Vina esté instalado y que VINA_EXECUTABLE_PATH en .env sea correcto. En Docker, el Dockerfile debe instalar Vina.': 'Check '
                                                                                                                                   'that '
                                                                                                                                   'Vina '
                                                                                                                                   'is '
                                                                                                                                   'installed '
                                                                                                                                   'and '
                                                                                                                                   'that '
                                                                                                                                   'VINA_EXECUTABLE_PATH '
                                                                                                                                   'in '
                                                                                                                                   '.env '
                                                                                                                                   'is '
                                                                                                                                   'correct. '
                                                                                                                                   'In '
                                                                                                                                   'Docker, '
                                                                                                                                   'the '
                                                                                                                                   'Dockerfile '
                                                                                                                                   'must '
                                                                                                                                   'install '
                                                                                                                                   'Vina.',
 'Verifica que el PDB ID sea valido (4 caracteres alfanumericos). Usa GET /targets/ para ver los 19+ targets pre-cargados, o POST /targets/upload para agregar un receptor personalizado. Si el target existe en RCSB (https://www.rcsb.org), el sistema lo descargara automaticamente en el primer uso.': 'Check '
                                                                                                                                                                                                                                                                                                           'that '
                                                                                                                                                                                                                                                                                                           'the '
                                                                                                                                                                                                                                                                                                           'PDB '
                                                                                                                                                                                                                                                                                                           'ID '
                                                                                                                                                                                                                                                                                                           'is '
                                                                                                                                                                                                                                                                                                           'valid '
                                                                                                                                                                                                                                                                                                           '(4 '
                                                                                                                                                                                                                                                                                                           'Alphanumeric '
                                                                                                                                                                                                                                                                                                           'characters). '
                                                                                                                                                                                                                                                                                                           'Use '
                                                                                                                                                                                                                                                                                                           'GET '
                                                                                                                                                                                                                                                                                                           '/targets/ '
                                                                                                                                                                                                                                                                                                           'to '
                                                                                                                                                                                                                                                                                                           'view '
                                                                                                                                                                                                                                                                                                           'the '
                                                                                                                                                                                                                                                                                                           '19+ '
                                                                                                                                                                                                                                                                                                           'pre-loaded '
                                                                                                                                                                                                                                                                                                           'targets, '
                                                                                                                                                                                                                                                                                                           'or '
                                                                                                                                                                                                                                                                                                           'POST '
                                                                                                                                                                                                                                                                                                           '/targets/upload '
                                                                                                                                                                                                                                                                                                           'to '
                                                                                                                                                                                                                                                                                                           'add '
                                                                                                                                                                                                                                                                                                           'a '
                                                                                                                                                                                                                                                                                                           'custom '
                                                                                                                                                                                                                                                                                                           'receptor. '
                                                                                                                                                                                                                                                                                                           'If '
                                                                                                                                                                                                                                                                                                           'the '
                                                                                                                                                                                                                                                                                                           'target '
                                                                                                                                                                                                                                                                                                           'exists '
                                                                                                                                                                                                                                                                                                           'in '
                                                                                                                                                                                                                                                                                                           'RCSB '
                                                                                                                                                                                                                                                                                                           '(https://www.rcsb.org), '
                                                                                                                                                                                                                                                                                                           'the '
                                                                                                                                                                                                                                                                                                           'system '
                                                                                                                                                                                                                                                                                                           'will '
                                                                                                                                                                                                                                                                                                           'automatically '
                                                                                                                                                                                                                                                                                                           'download '
                                                                                                                                                                                                                                                                                                           'it '
                                                                                                                                                                                                                                                                                                           'in '
                                                                                                                                                                                                                                                                                                           'first '
                                                                                                                                                                                                                                                                                                           'use.',
 'Versión de MolDesign': 'MolDesign version',
 'Versión de RDKit': 'RDKit version',
 'Versión del Motor de Docking': 'Version of the Docking Engine',
 'Versión del motor': 'Engine version',
 'Vina no encontrado. Devolviendo estructura plegada sin docking.': 'Wine not found, returning folded structure '
                                                                    'without docking.',

 'Vina no tiene parámetros para esos elementos; la energía que devuelva no es comparable.': 'Vina has no parameters '
                                                                                            'for those elements; the '
                                                                                            'energy returned is not '
                                                                                            'comparable.',

 'Válidas (elegibles)': 'Valides (eligible)',
 'Ya existe una cuenta con ese email': "There's already an account with that email.",






 '`expected_fingerprint` tiene que ser el `cohort_fingerprint` que devolvió la comprobación previa, con la forma `sha256:<64 hexadecimales>`.': '`expected_fingerprint` '
                                                                                                                                                'must '
                                                                                                                                                'be '
                                                                                                                                                'the '
                                                                                                                                                '`cohort_fingerprint` '
                                                                                                                                                'returned '
                                                                                                                                                'by '
                                                                                                                                                'preflight, '
                                                                                                                                                'in '
                                                                                                                                                'the '
                                                                                                                                                'form '
                                                                                                                                                '`sha256:<64 '
                                                                                                                                                'hexadecimal '
                                                                                                                                                'characters>`.',


 'almacenamiento local (data/targets, biblioteca y caché)': 'local storage (data/targets, library and cache)',
 'almacenamiento local de targets preparados': 'local storage of prepared targets',
 


 'chem.validator.validate_smiles (mismo validador que /evaluation/submit)': 'chem.validator.validate_smiles (same '
                                                                            'validator as /evaluation/submit)',
 





















 












 'exhaustiveness=32 reduce la varianza del score significativamente. ~4x más lento que 8, pero necesario para calibración confiable.': 'exhaustiveness=32 '
                                                                                                                                       'reduces '
                                                                                                                                       'score '
                                                                                                                                       'variance '
                                                                                                                                       'significantly. '
                                                                                                                                       '~4x '
                                                                                                                                       'slower '
                                                                                                                                       'than '
                                                                                                                                       '8, '
                                                                                                                                       'but '
                                                                                                                                       'necessary '
                                                                                                                                       'for '
                                                                                                                                       'reliable '
                                                                                                                                       'calibration.',


 'faster-whisper no está instalado. Ejecutá: pip install faster-whisper': 'faster-whisper is not installed. It will '
                                                                          'run: pip install faster-whisper',


 'firma exacta de recalibración incompatible': 'exact signature of incompatible recalibration',



 'httpx no instalado en el backend.': 'httpx not installed in the backend.',








 'lectura local del PDB de origen': 'local PDB home reading',

 
 'mk_export.py no generó el SDF esperado': 'mk_export.py did not generate the expected SDF',


 'no está en el panel ni en el catálogo de este equipo': 'is not on the panel or in the catalog of this equipment',





 'openpyxl no instalado. Instalar con: pip install openpyxl': 'openpyxl not installed. Install with: pip install '
                                                              'openpyxl',

 'pH de protonación del ligando': 'ligand protonation pH',



 'preparer.filter_pdb_content (la función que ejecuta la corrida)': 'preparer.filter_pdb_content (the function that the run executes)',
 'preparer.filter_pdb_content sobre el PDB de origen': 'preparer.filter_pdb_content on the source PDB',















 'task_id es requerido para cancelar': 'task_id is required to cancel',


 

 'xTB no está configurado o instalado.': 'xTB is not configured or installed.',
 'xtb falló al procesar la molécula': 'xtb failed to process the molecule',
 'xtb no generó el archivo de cargas': 'xtb did not generate load file',





 '«Fallida» y «no evaluada» describen lo que le pasó al MOTOR, no a la molécula. Ninguna de las dos es evidencia negativa.': '«Fallid» '
                                                                                                                             'and '
                                                                                                                             '«not '
                                                                                                                             'evaluated» '
                                                                                                                             'describe '
                                                                                                                             'what '
                                                                                                                             'happened '
                                                                                                                             'to '
                                                                                                                             'the '
                                                                                                                             'MOTOR, '
                                                                                                                             'not '
                                                                                                                             'to '
                                                                                                                             'the '
                                                                                                                             'molecule. '
                                                                                                                             'Neither '
                                                                                                                             'is '
                                                                                                                             'negative '
                                                                                                                             'evidence.',
 'Átomos soportados por el campo de fuerza': 'Atoms supported by the force field',

















}

# QA2-004: motivo de abstención del motor externo Molcy, sin alterar rutas ni datos.
ENGLISH_MESSAGES.update({
    "Esta versión de Molcy no admite paquetes de corrida.":
        "This version of Molcy does not support run packages.",
})

ENGLISH_MESSAGES.update({
    "No hay fuente en disco que comparar. Se calculará cuando la corrida la descargue.": "No on-disk source is available for comparison. Its checksum will be calculated when the run downloads it.",
    "El filtrado de la cadena falló, así que no hay preparado con el que comparar.": "Chain filtering failed, so there is no prepared receptor to compare.",
    "Son las cadenas que se acoplarán juntas; el resto de la estructura no entra.": "These are the chains that will be docked together; the rest of the structure is excluded.",
    "Plantilla local de cofactor": "Local cofactor template",
    "La preparación se abstiene antes de consultar CCD por red o retirar el cofactor.": "Preparation abstains before querying the CCD over the network or removing the cofactor.",
    "preparer.cofactores_sin_plantilla · caja efectiva de la corrida, la misma regla que prepare_target": "preparer.cofactores_sin_plantilla · effective box of the run, the same rule as prepare_target",
    "Cofactores sin plantilla fuera del margen": "Cofactors without a template outside the margin",
    "Quedan fuera del margen geométrico de preparación; esa distancia no demuestra irrelevancia química.": "They lie outside the geometric preparation margin; that distance does not show that they are chemically irrelevant.",
    "El template elegido está registrado; el microestado experimental no está validado.": "The selected template is recorded; the experimental microstate has not been validated.",
    "informe Meeko del receptor preparado": "Meeko report for the prepared receptor",
    "El receptor preparado carece del resumen de plantillas de Meeko.": "The prepared receptor has no Meeko template summary.",
    "No se puede atribuir una protonación concreta a un PDBQT sin este registro.": "A specific protonation state cannot be assigned to a PDBQT without this record.",
    "Meeko aún no ha preparado el receptor; la plantilla elegida no se conoce.": "Meeko has not prepared the receptor yet; the selected template is unknown.",
    "El preflight no ejecuta Meeko ni adivina HIE/HID/HIP desde un PDB sin hidrógenos.": "Preflight does not run Meeko or guess HIE/HID/HIP from a PDB without hydrogens.",
    "Meeko 0.7.1 · selección de plantillas": "Meeko 0.7.1 · template selection",
    "Respaldo científico del receptor": "Scientific evidence for the receptor",
    "No se pudo determinar el estado de calibración.": "The calibration status could not be determined.",
    "AutoDock Vina no tiene parámetros": "AutoDock Vina has no parameters",
    "Átomos no soportados": "Unsupported atoms",
    "Política de heteroátomos de esta ruta": "Heteroatom policy for this path",
    "preparer.filter_pdb_content + sitio de llamada en vina_service.run_docking": "preparer.filter_pdb_content + call site in vina_service.run_docking",
    "Ruta de docking comprobable": "Docking path that can be checked",
    "Open Babel viaja como programa independiente (GPL-2.0-only) y se conserva para operaciones y artefactos históricos. La ruta de docking actual exige el SDF exportado por Meeko: si falla, se abstiene sin reconstruir química desde el PDBQT de Vina. La inspección de este control no busca ejecutables en PATH.": "Open Babel ships as a standalone program (GPL-2.0-only) and is retained for operations and historical artifacts. The current docking path requires the SDF exported by Meeko; if that step fails, it abstains instead of reconstructing chemistry from Vina's PDBQT. This check does not search PATH for executables.",
    "Si sólo se halló el centroide proteico, la corrida se abstiene. Una caja derivada de un heteroátomo tampoco es una hipótesis de sitio validada experimentalmente.": "If only the protein centroid was found, the run abstains. A box derived from a heteroatom is also not an experimentally validated site hypothesis.",
    "catálogo del receptor": "receptor catalog",
    "elegido por ti": "selected by you",
    "No hay estructura del receptor disponible para comparar la caja.": "No receptor structure is available for comparison with the box.",
    "Sin el PDB de la ruta no se puede medir la relación geométrica entre la caja y el receptor; no se inventa.": "Without the PDB used by this path, the geometric relationship between the box and receptor cannot be measured; no value is inferred.",
    "PDB filtrado de la ruta real": "Filtered PDB from the actual path",
    "Una caja sin intersección con el receptor acopla contra espacio vacío: el score que salga no describirá ningún bolsillo. La decisión de explorar fuera es del investigador; lo que no puede ser invisible.": "A box that does not intersect the receptor docks against empty space: any resulting score will describe no binding pocket. The researcher decides whether to explore outside the receptor; that choice must remain visible.",
    "PDB filtrado de la ruta real · geometría de la caja de búsqueda efectiva": "Filtered PDB from the actual path · geometry of the effective search box",
    "La búsqueda tiene estructura delante; la pertinencia del sitio se lee en los residuos de referencia.": "The search region contains structure; assess site relevance from the reference residues.",
    "Volumen de búsqueda amplio": "Large search volume",
    "El umbral de 27 000 Å³ y el escalón 32 son una política conservadora pendiente de benchmark de convergencia; no garantizan una pose correcta.": "The 27,000 Å³ threshold and increment of 32 are a conservative policy awaiting a convergence benchmark; they do not guarantee a correct pose.",
    "services.docking.search_policy · tamaño efectivo de caja": "services.docking.search_policy · effective box size",
    "0 residuos por decisión del investigador: esta corrida no usa residuos de referencia; el análisis de contactos viajará sin lista.": "Zero residues by researcher choice: this run uses no reference residues, so the contact analysis will contain no list.",
    "El protocolo que puede ejecutarse viaja en pipeline_config: las puertas de ejecución no llevan esos campos de nivel superior. Declararlos como efectivos firmaría una corrida que no ocurriría; para cambiar el protocolo hay que declararlo en stage_params.": "The executable protocol is carried in pipeline_config; execution gates do not use those top-level fields. Declaring them as effective would attest to a run that would not occur. To change the protocol, declare it in stage_params.",
    "Política de preparación aplicada a la estructura de esta corrida.": "Preparation policy applied to this run's structure.",
    "Cadena de los residuos de referencia": "Reference-residue chain",
    "Los residuos declarados no indican cadena, así que no se puede comprobar.": "The declared residues do not specify a chain, so they cannot be checked.",
    "hotspots del catálogo · cadenas del receptor filtrado": "Catalog hotspots · filtered receptor chains",
    "Protonación y tautómero del ligando": "Ligand protonation and tautomer",
    "No evaluado antes de ejecutar.": "Not evaluated before the run.",
    "Unidad asimétrica frente a assembly biológica": "Asymmetric unit versus biological assembly",
    "No evaluado: el catálogo no registra qué assembly representa el archivo.": "Not evaluated: the catalog does not record which assembly the file represents.",
    "Residuos faltantes cerca del sitio": "Missing residues near the site",
    "No evaluado: la ruta no conserva un mapa de huecos del receptor preparado.": "Not evaluated: this path does not retain a gap map for the prepared receptor.",
    "Cancelado por el usuario": "Canceled by the user",
    "MM-GBSA no disponible (MMGBSA_CONDICION): parametrización legacy inconsistente.": "MM-GBSA unavailable (MMGBSA_CONDICION): inconsistent legacy parameterization.",
    "El motor se declara en docking_engine, no en stage_params.docking.engine": "The engine is specified in docking_engine, not in stage_params.docking.engine.",
    "No se pudieron calcular los grupos quelantes; la ausencia de señal no es negativa.": "Chelating groups could not be calculated; absence of a signal is not a negative result.",
    "Se detectó una secuencia peptídica lineal compatible con ESMFold; se respeta el motor Vina solicitado. La ruta ESMFold es exploratoria y no valida precisión de poses.": "A linear peptide sequence compatible with ESMFold was detected; the requested Vina engine is retained. The ESMFold path is exploratory and does not validate pose accuracy.",
    "Fallo al inspeccionar tipo de molécula": "Failed to inspect molecule type",
    "No se pudo preparar PDB temporal del target para Nivel 3": "Could not prepare a temporary PDB for the target at Level 3",
    "Predicción de Nivel 3 completada con éxito": "Level 3 prediction completed successfully",
    "Se solicitó refinamiento peptídico, pero la ruta OpenMM/Amber no está validada. Se conserva la pose original de Vina sin marcarla como refinada.": "Peptide refinement was requested, but the OpenMM/Amber path is not validated. The original Vina pose is retained without marking it as refined.",
    "confianza estructural no reportada": "structural confidence not reported",
    "el modelo plegó la estructura pero ninguna pose pasó por acoplamiento": "the model folded the structure, but no pose went through docking",
    "Sin respuesta del servicio": "No response from the service",
    "Fallo en Nivel 3, cayendo a Vina estándar": "Level 3 failed; falling back to standard Vina",
    "conformer listo para docking": "conformer ready for docking",
    "grupo reconocido sin pKa verificado: menor carga formal, en revisión": "recognized group without a verified pKa: lowest formal charge, under review",
    "sin centros reconocidos: selección alfabética reproducible, sin población estimada": "no recognized centers: reproducible alphabetical selection, with no population estimated",
    "no sustituye a affinity_kcal": "does not replace affinity_kcal",
    "Índice cuántico no evaluado: faltan descriptores xTB verificables.": "Quantum index not evaluated: verifiable xTB descriptors are missing.",
    "El subproceso excedió 300 segundos": "The subprocess exceeded 300 seconds",
    "pipeline de evaluación falló": "evaluation pipeline failed",
    "no se pudo persistir estado FAILED en DB": "could not persist FAILED status to the database",
    "Evaluación cancelada o interrumpida": "Evaluation canceled or interrupted",
    "Evaluación interrumpida o cancelada": "Evaluation interrupted or canceled",
    "Error en tarea DESKTOP": "Error in DESKTOP task",
    "La evaluación excedió el plazo de ejecución.": "The evaluation exceeded its execution time limit.",
    "La etapa openmm está retirada: sobrescribía poses y no ejecutaba OpenMM.": "The openmm stage is retired: it overwrote poses and did not run OpenMM.",
    "⚠️ Se detectó una secuencia peptídica lineal compatible con ESMFold. Si se trata de un péptido o peptidomimético, considera usar la ruta ESMFold exploratoria; no hay benchmark de precisión de poses.": "⚠️ A linear peptide sequence compatible with ESMFold was detected. If this is a peptide or peptidomimetic, consider the exploratory ESMFold path; pose accuracy has not been benchmarked.",
    "Selectividad no evaluada: falta afinidad principal finita": "Selectivity not evaluated: finite primary affinity is missing",
    "Error en stage": "Error in stage",
    "Índice cuántico y UMS histórico no evaluados: faltan descriptores xTB verificables.": "Quantum index and historical UMS not evaluated: verifiable xTB descriptors are missing.",
    "El pipeline finalizó pero no generó docking o propiedades.": "The pipeline finished but produced no docking result or properties.",
})

ENGLISH_MESSAGES.update({
    "Evaluación científica": "Scientific evaluation",
    "No se encontró el ejecutable de AutoDock Vina que el instalador empaqueta. Sin él no se puede ejecutar ninguna corrida.": "The AutoDock Vina executable packaged by the installer was not found. No run can be performed without it.",
    "QuickVina 2 no está habilitado para evaluaciones en esta versión. El backend rechaza la selección antes de encolar la corrida.": "QuickVina 2 is not enabled for evaluations in this version. The backend rejects the selection before enqueueing the run.",
    "Qué motores de docking puede ejecutar esta instalación": "Docking engines this installation can run",
    "Encender un motor descargable que ya está instalado": "Start a downloadable engine that is already installed",
    "Motor de docking ejecutable en esta versión": "Docking engine that can run in this version",
    "stage_params.docking debe ser un objeto": "stage_params.docking must be an object",
    "El motor se declara en docking_engine": "Declare the engine in docking_engine",
    "Hay una etapa desconocida o no ejecutable": "An unknown or non-executable stage is present",
    "La caja debe contener sólo números finitos": "The box must contain only finite numbers",
    "El centro debe estar entre -10000 y 10000 Å": "The center must be between -10000 and 10000 Å",
    "Cada dimensión de la caja debe estar entre 5 y 80 Å": "Each box dimension must be between 5 and 80 Å",
    "pH solicitado para el microestado del ligando": "Requested pH for the ligand microstate",
    "Cadena del receptor que fue aceptada en el preflight. Debe coincidir con la cadena registrada del target.": "Receptor chain accepted during preflight. It must match the chain recorded for the target.",
    "Si es True, se ignora el score químico (ADME/Drug-likeness) al calcular el score total.": "If True, the chemistry score (ADME/drug-likeness) is ignored when calculating the total score.",
    "Centro de la Grid Box override (X, Y, Z)": "Grid box center override (X, Y, Z)",
    "Tamaño de la Grid Box override (dX, dY, dZ)": "Grid box size override (dX, dY, dZ)",
    "Lista de hotspots seleccionados por el usuario": "List of user-selected hotspots",
    "Datos clínicos y genómicos del paciente (Capa 0)": "Patient clinical and genomic data (Layer 0)",
    "Ruta peptídica disponible tras descargar ESMFold; ausente usa Vina.": "Peptide path available after downloading ESMFold; if absent, Vina is used.",
    "El perfil supera 64 KiB": "Profile exceeds 64 KiB",
    "Configuración manual del pipeline de ejecución (Modo PRO)": "Manual configuration for the execution pipeline (PRO mode)",
    "peptide_docking_engine debe coincidir con pipeline_config.peptide_docking_engine": "peptide_docking_engine must match pipeline_config.peptide_docking_engine",
    "ph debe coincidir con pipeline_config.stage_params.conformer.ph": "ph must match pipeline_config.stage_params.conformer.ph",
    "Huella de la comprobación previa aceptada por el usuario. Si se envía, el backend la recalcula antes de registrar la corrida.": "Fingerprint for the preflight accepted by the user. If provided, the backend recalculates it before recording the run.",
    "Evaluacion sincrona con SSE progress": "Synchronous evaluation with SSE progress",
    "La evaluación no produjo un resultado persistido.": "The evaluation did not produce a persisted result.",
    "La evaluación falló; consulta el estado de la tarea para más detalles.": "The evaluation failed; check the task status for more details.",
    "Cancelar una evaluación desktop por task_id": "Cancel a desktop evaluation by task_id",
    "Enviar evaluación molecular asíncrona": "Submit an asynchronous molecular evaluation",
    "Suscribirse al flujo de eventos del pipeline (SSE)": "Subscribe to the pipeline event stream (SSE)",
    "Consultar estado de un job de evaluación": "Check the status of an evaluation job",
    "Leer resultado persistido de una molécula": "Read a molecule's persisted result",
    "Leer SVG de atención GNN on-demand (UI-7, fuera del polling)": "Read a GNN attention SVG on demand (UI-7, outside polling)",
    "No tienes permiso para acceder a esta atención.": "You do not have permission to access this attention map.",
    "No existe molécula": "Molecule does not exist",
    "Cadena a acoplar. Por defecto, la que declare el receptor.": "Chain to dock. Defaults to the chain declared by the receptor.",
    "Comprobación previa factual de una corrida (no ejecuta docking)": "Factual preflight for a run (does not perform docking)",
    "Abrir una corrida sobre una cohorte congelada": "Open a run for a frozen cohort",
    "Paralelismo. Operacional: NO entra en el `run_fingerprint`.": "Parallelism. Operational only: it is NOT part of the `run_fingerprint`.",
    "Última corrida durable de una cohorte": "Most recent durable run for a cohort",
    "Estado, progreso, configuración efectiva, procedencia y filas": "Status, progress, effective configuration, provenance, and rows",
    "Reanudar una corrida interrumpida o con excepciones": "Resume an interrupted run or one with exceptions",
    "Pedir la cancelación de una corrida": "Request cancellation of a run",
    "Resumen científico de la corrida (cobertura, evidencia y métricas)": "Scientific summary of the run (coverage, evidence, and metrics)",
    "Único orden ofrecido: `afinidad_vina_observada`. Es un ORDEN, no un veredicto: no significa «mejores fármacos» ni probabilidad de éxito.": "Only sort order offered: `afinidad_vina_observada`. This is an ORDER, not a verdict: it does not mean “better drugs” or indicate a probability of success.",
    "Dossier de cohorte en PDF (inline)": "Cohort dossier in PDF (inline)",
    "Paquete verificable de la cohorte (ZIP con manifiesto y hashes)": "Verifiable cohort package (ZIP with manifest and hashes)",
    "Comprobación previa de una cohorte (no ejecuta docking ni la persiste)": "Preflight a cohort (does not run docking or persist it)",
    "CSV, Excel, SDF o SMILES/TXT con las moléculas.": "CSV, Excel, SDF, or SMILES/TXT file containing the molecules.",
    "Congelar una cohorte comprobada (no ejecuta nada)": "Freeze a checked cohort (does not run anything)",
    "El MISMO archivo que se comprobó.": "The SAME file that was checked.",
    "El MISMO `CohortStudy` v1 que se comprobó.": "The SAME `CohortStudy` v1 that was checked.",
    "El `cohort_fingerprint` que devolvió la comprobación previa.": "The `cohort_fingerprint` returned by preflight.",
    "Cohortes congeladas (resumen: sin filas y sin archivo)": "Frozen cohorts (summary: no rows and no file)",
    "Una cohorte congelada: definición, snapshot, resumen y filas": "A frozen cohort: definition, snapshot, summary, and rows",
    "Dossier de caso": "Case dossier",
    "No tienes permiso para exportar el dossier de esta molécula.": "You do not have permission to export this molecule's dossier.",
    "La corrida no conserva poses inmutables con SHA-256 verificable.": "The run does not retain immutable poses with verifiable SHA-256 hashes.",
    "La corrida no conserva este archivo con SHA-256 verificable.": "The run does not retain this file with a verifiable SHA-256 hash.",
    "La corrida no conserva receptor inmutable con SHA-256 verificable.": "The run does not retain an immutable receptor with a verifiable SHA-256 hash.",
    "La corrida no conservó esta especie del ligando.": "The run did not retain this ligand species.",
    "Índice de referencia. Cada pose apunta a su bloque PDBQT exacto; `outputs/poses.sdf` se declara además cuando la corrida produjo un archivo único que representa la colección.": "Reference index. Each pose points to its exact PDBQT block; `outputs/poses.sdf` is also declared when the run produced one file representing the collection.",
    "Dossier del caso en PDF (inline)": "Case dossier in PDF (inline)",
    "Auditoría de preparación de la corrida (readiness FEP en desarrollo)": "Run preparation audit (FEP readiness under development)",
    "Paquete reproducible del caso (ZIP con manifiesto y hashes)": "Reproducible case package (ZIP with manifest and hashes)",
    "No tienes permiso para acceder a este receptor.": "You do not have permission to access this receptor.",
    "Descargar SDF de poses de docking": "Download the docking poses as SDF",
    "No tienes permiso para acceder a estos archivos.": "You do not have permission to access these files.",
    "Complejo proteína-ligando fusionado (un único PDB para visualización 3D correcta)": "Merged protein-ligand complex (one PDB for correct 3D visualization)",
    "No tienes permiso para acceder al complejo fusionado.": "You do not have permission to access the merged complex.",
    "No existe resultado": "No result exists",
    "Error generando reporte. Por favor intenta de nuevo.": "Error generating the report. Please try again.",
    "Generar reporte IA bajo demanda para una molécula evaluada": "Generate an AI report on demand for an evaluated molecule",
    "No tienes permiso para acceder a este reporte.": "You do not have permission to access this report.",
    "El SMILES no puede estar vacío": "SMILES cannot be empty",
    "No se puede kekulizar la molécula. El sistema aromático definido no es válido.": "The molecule cannot be kekulized. The specified aromatic system is invalid.",
    "Se detectaron electrones radicales; el pipeline actual no acepta radicales por baja defendibilidad en docking estándar.": "Radical electrons were detected; the current pipeline does not accept radicals because they are difficult to justify in standard docking.",
    "Error en SaltRemover, continuando con la molécula original": "SaltRemover error; continuing with the original molecule",
    "La molécula contiene contraiones/sales que fueron removidos automáticamente (desalinización).": "The molecule contains counterions/salts that were removed automatically (desalting).",
    "iniciando validación de SMILES": "starting SMILES validation",
})

ENGLISH_MESSAGES.update({
    "La corrida no registró qué modelo de rescoring se usó.": "This run did not record which rescoring model was used.",
    "Advertencias de la comprobación previa": "Preflight warnings",
    "Validación, propiedades, confórmeros y rescoring.": "Validation, properties, conformers, and rescoring.",
    "Receptor preparado": "Prepared receptor",
})

ENGLISH_MESSAGES.update({
    "NO DECLARADO": "NOT DECLARED",
    "NO DECLARADA": "NOT DECLARED",
    "Cadena": "Chain",
    "Tamaño (bytes)": "Size (bytes)",
    "Objeto": "Object",
    "Parámetro": "Parameter",
    "Caja (centro)": "Box (center)",
    "Caja (tamaño)": "Box (size)",
    "Origen de la caja": "Box source",
    "Motor": "Engine",
    "Semilla": "Seed",
    "Cohorte": "Cohort",
    "Huella de cohorte": "Cohort fingerprint",
    "Huella de corrida": "Run fingerprint",
    "SHA-256 del preparado": "Prepared SHA-256",
    "Recuento": "Count",
    "Filas elegibles": "Eligible rows",
    "Filas NO elegibles": "Ineligible rows",
    "Completadas": "Completed",
    "Duplicados reutilizados": "Reused duplicates",
    "Fallidas": "Failed",
    "No evaluadas": "Not evaluated",
    "Interrumpidas": "Interrupted",
    "Canceladas": "Canceled",
    "Escalón": "Stage",
    "Entradas totales": "Total inputs",
    "Válidas (elegibles)": "Valid (eligible)",
    "Ejecutadas": "Executed",
    "Con poses": "With poses",
    "Seleccionables (≥2 poses)": "Selectable (≥2 poses)",
    "Físicamente evaluadas": "Physically evaluated",
    "· controles superados": "· checks passed",
    "· controles fallidos": "· checks failed",
    "Selector: recomendó": "Selector: recommended",
    "Selector: se abstuvo": "Selector: abstained",
    "Selector: falló": "Selector: failed",
    "Causa": "Cause",
    "Filas": "Rows",
    "TOTAL EXCLUIDAS": "TOTAL EXCLUDED",
    "Nombre": "Name",
    "Estado": "Status",
    "Afinidad Vina obs. (kcal/mol)": "Observed Vina affinity (kcal/mol)",
    "Etiq.": "Label",
    "Papel": "Role",
    "Etiqueta": "Label",
    "Métrica": "Metric",
    "Contrato de preflight": "Preflight contract",
    "Contrato de fingerprint": "Fingerprint contract",
    "Contrato de ejecución": "Execution contract",
    "Contrato de evidencia": "Evidence contract",
    "Etapas ejecutadas": "Stages run",
})

ENGLISH_MESSAGES.update({
    """Aceptar con límites""": """Accept with limits""",
    """Estado de ejecución (técnico)""": """Execution status (technical)""",
    """El caso no registró el estado de la corrida.""": """The case did not record the run status.""",
    """Disposición científica de la evidencia""": """Scientific disposition of the evidence""",
    """Revisión humana""": """Human review""",
    """Nadie ha revisado ni reconocido controles de esta corrida.""": """No one has reviewed or acknowledged this run's checks.""",
    """Disposición final del caso""": """Final case disposition""",
    """El caso aún no tiene una disposición científica final.""": """The case does not yet have a final scientific disposition.""",
    """El caso no declaró receptor.""": """The case did not declare a receptor.""",
    """Origen del receptor""": """Receptor source""",
    """El caso no declaró el origen del receptor.""": """The case did not declare the receptor source.""",
    """El caso no declaró ligando.""": """The case did not declare a ligand.""",
    """Ligando canónico (el que se acopla)""": """Canonical ligand (the one docked)""",
    """No se registró la forma canónica del ligando.""": """The canonical form of the ligand was not recorded.""",
    """La corrida no persistió la caja de búsqueda efectiva; la caja declarada por el caso no prueba la ejecutada.""": """This run did not persist the effective search box; the box declared by the case does not establish which box was used.""",
    """No se seleccionaron residuos de referencia.""": """No reference residues were selected.""",
    """Huella de los inputs (preflight)""": """Input fingerprint (preflight)""",
    """La huella de la disposición no coincide con la huella de la corrida.""": """The disposition fingerprint does not match the run fingerprint.""",
    """La corrida se ejecutó con los inputs que este dossier describe.""": """This run used the inputs described in this dossier.""",
    """No se puede confirmar que la corrida corresponda a los inputs actuales. La diferencia puede deberse a cambios en los inputs o en el cálculo de la huella.""": """It cannot be confirmed that the run matches the current inputs. The difference may result from changes to the inputs or to how the fingerprint was calculated.""",
    """La corrida no registró la huella de sus inputs; no se puede afirmar a qué hipótesis corresponde.""": """This run did not record its input fingerprint; it cannot be linked to a specific hypothesis.""",
    """Política de heteroátomos declarada""": """Declared heteroatom policy""",
    """Motor de acoplamiento""": """Docking engine""",
    """La corrida no registró el motor.""": """This run did not record the engine.""",
    """La corrida no registró la versión.""": """This run did not record the version.""",
    """Versión MolDesign""": """MolDesign version""",
    """La corrida no registró la versión de la aplicación.""": """This run did not record the application version.""",
    """La corrida no registró el argumento CPU de Vina.""": """This run did not record Vina's CPU argument.""",
    """SHA-256 ligando SDF de entrada""": """Input ligand SDF SHA-256""",
    """La corrida no registró el hash del conformero de entrada.""": """This run did not record the input conformer hash.""",
    """La corrida no registró el hash del PDBQT acoplado.""": """This run did not record the docked PDBQT hash.""",
    """La corrida no registró el hash del SDF de salida.""": """This run did not record the output SDF hash.""",
    """La corrida no registró el hash del log.""": """This run did not record the log hash.""",
    """Receta de receptor""": """Receptor preparation recipe""",
    """La corrida no registró el hash de receta del receptor.""": """This run did not record the receptor recipe hash.""",
    """Versiones de preparación""": """Preparation versions""",
    """La corrida no registró el parser.""": """This run did not record the parser.""",
    """Origen del parseo""": """Parser source""",
    """Modelo de rescoring""": """Rescoring model""",
    """La corrida no registró el modelo.""": """This run did not record the model.""",
    """Configuración PRO declarada""": """Declared PRO settings""",
    """El caso no declaró opciones PRO avanzadas; este campo no acredita su ejecución.""": """The case did not declare advanced PRO options; this field does not establish that they were used.""",
    """La corrida no registró la exhaustividad utilizada.""": """This run did not record the exhaustiveness used.""",
    """La corrida no registró el número de poses solicitado.""": """This run did not record the requested number of poses.""",
    """Motivo de fallback""": """Fallback reason""",
    """No se registró ningún fallback.""": """No fallback was recorded.""",
    """La corrida no registró errores.""": """This run did not record errors.""",
    """Exhaustividad declarada por el caso""": """Exhaustiveness declared by the case""",
    """Poses declaradas por el caso""": """Poses declared by the case""",
    """El valor declarado por el caso difiere del protocolo ejecutado.""": """The value declared by the case differs from the protocol that ran.""",
    """Valor declarado por el caso; la ejecución se documenta por separado.""": """Value declared by the case; execution is documented separately.""",
    """Caja declarada por el caso""": """Box declared by the case""",
    """La caja declarada difiere de la ejecutada.""": """The declared box differs from the box used.""",
    """Valor declarado por el caso; no sustituye la caja ejecutada.""": """Value declared by the case; it does not replace the box used.""",
    """La corrida no serializó poses; no hay evidencia estructural que revisar.""": """This run did not serialize poses; there is no structural evidence to review.""",
    """La corrida no serializó poses.""": """This run did not serialize poses.""",
    """La corrida no registró la semilla: no es repetible bit a bit.""": """This run did not record the seed; it cannot be reproduced bit for bit.""",
    """Motor y versión""": """Engine and version""",
    """La corrida no registró el motor ni su versión.""": """This run did not record the engine or its version.""",
    """La corrida no serializó afinidad.""": """This run did not serialize affinity.""",
    """Cobertura de validación física""": """Physical validation coverage""",
    """Ninguna pose recibió veredicto físico.""": """No pose received a physical verdict.""",
    """Estado de la etapa de selección""": """Selection stage status""",
    """El selector emitió una recomendación.""": """The selector made a recommendation.""",
    """El margen no llegó al umbral: el selector NO recomienda.""": """The margin did not reach the threshold: the selector does NOT recommend a pose.""",
    """El selector no se ejecutó en esta corrida.""": """The selector did not run in this run.""",
    """Pose principal del producto (Vina top-1)""": """Product primary pose (Vina top-1)""",
    """La corrida no permitió identificar la top-1 de Vina.""": """This run did not identify Vina top-1.""",
    """Pose recomendada por el selector""": """Pose recommended by the selector""",
    """El selector no recomendó ninguna pose.""": """The selector did not recommend a pose.""",
    """Pose que habría recomendado (abstención)""": """Pose the selector would have recommended (abstention)""",
    """No aplica: la etapa no se abstuvo con una candidata medida.""": """Not applicable: the stage did not abstain with a measured candidate.""",
    """Margen de confianza y umbral""": """Selector margin and threshold""",
    """El selector no dejó margen medido.""": """The selector left no measured margin.""",
    """Vina top-1 como FALLBACK: no es un acierto del selector""": """Vina top-1 as FALLBACK: this is not a selector hit""",
    """Recomendación del selector, junto a Vina top-1""": """Selector recommendation, alongside Vina top-1""",
    """Cuando no hay recomendación, la referencia es Vina top-1 por defecto.""": """When there is no recommendation, Vina top-1 is the default reference.""",
    """Razón de abstención""": """Abstention reason""",
    """La etapa no registró razón de abstención.""": """The stage did not record an abstention reason.""",
    """Modelo del selector""": """Selector model""",
    """No se registró el modelo del selector.""": """The selector model was not recorded.""",
    """SHA-256 del modelo""": """Model SHA-256""",
    """No se selló el modelo del selector.""": """The selector model was not sealed.""",
    """SHA-256 de la metadata del modelo""": """Model metadata SHA-256""",
    """No se selló la metadata del selector.""": """The selector metadata was not sealed.""",
    """Veredicto de la etapa""": """Stage verdict""",
    """Motor de validación""": """Validation engine""",
    """La etapa no declaró motor de validación.""": """The stage did not declare a validation engine.""",
    """Ninguna pose recibió veredicto.""": """No pose received a verdict.""",
    """Código de razón""": """Reason code""",
    """La etapa no registró código de razón.""": """The stage did not record a reason code.""",
    """Estado físico de la pose recomendada""": """Physical status of the recommended pose""",
    """No hay pose recomendada, o su estado físico no se midió.""": """There is no recommended pose, or its physical status was not measured.""",
    """Estado físico de la pose que habría recomendado""": """Physical status of the pose the selector would have recommended""",
    """No aplica: el selector no se abstuvo con una candidata medida.""": """Not applicable: the selector did not abstain with a measured candidate.""",
    """Validez física y geométrica de las poses""": """Physical and geometric validity of the poses""",
    """Reconstrucción de la pose desde PDBQT con plantilla del SMILES y validación geométrica. La representación con la que se valida NO es la del cristal: los hidrógenos se añaden en la reconstrucción.""": """Pose reconstruction from PDBQT using the SMILES template, followed by geometric validation. The representation used for validation is NOT the crystal structure: hydrogens are added during reconstruction.""",
    """Separación energética entre poses""": """Energy separation between poses""",
    """No se pudo describir la separación entre poses.""": """The separation between poses could not be described.""",
    """Diferencia de afinidad entre la pose 1 y la 2, y recuento a ≤1 kcal/mol.""": """Affinity difference between poses 1 and 2, and the count within ≤1 kcal/mol.""",
    """Traza de reproducibilidad técnica""": """Technical reproducibility trace""",
    """Presencia de los tres campos que permiten repetir la corrida.""": """Presence of the three fields needed to repeat the run.""",
    """Siguiente acción justificable""": """Next justified action""",
    """ABSTENCIÓN: CORRESPONDENCIA NO CONFIRMADA""": """ABSTENTION: MATCH NOT CONFIRMED""",
    """No se puede confirmar que esta corrida corresponda a los inputs actuales. Vuelve a comprobar la preparación y ejecuta con la hipótesis actual antes de decidir.""": """It cannot be confirmed that this run matches the current inputs. Check the preparation again and run with the current hypothesis before deciding.""",
    """Índice compuesto heredado (total_score)""": """Legacy composite index (total_score)""",
    """Índice de afinidad heredado""": """Legacy affinity index""",
    """Índice ADME heredado""": """Legacy ADME index""",
    """Índice de similitud a fármaco heredado""": """Legacy drug-likeness index""",
})

ENGLISH_MESSAGES.update({
    "No se detectó GPU. MM-GBSA y GNN rescoring correrán en CPU (más lento).": (
        "No GPU detected. MM-GBSA and GNN rescoring will run on the CPU (slower)."
    ),
})

ENGLISH_MESSAGES.update({
    """El caso no lo declaró.""": """The case did not declare it.""",
    """La corrida no registró las cadenas del receptor preparado; la cadena declarada por el caso no prueba contra cuáles se acopló.""": """This run did not record the chains in the prepared receptor; the chain declared by the case does not show which chains were docked against.""",
    """Validación del método peptídico""": """Peptide method validation""",
    """EXPERIMENTAL: la estructura la predice ESMFold y su calidad no está validada en MolDesign""": """EXPERIMENTAL: ESMFold predicts the structure, and MolDesign has not validated its quality""",
    """MolDesign ha comprobado que ESMFold carga y sirve estructuras, no que sean buenas. El acoplamiento lo hace después Vina sobre esa estructura predicha: su afinidad no hereda validez de la predicción.""": """MolDesign has verified that ESMFold loads and serves structures, not that the structures are good. Vina then performs docking against the predicted structure; its affinity does not inherit validity from the prediction.""",
    """RDKit de canonicalización""": """RDKit version for canonicalization""",
    """La corrida no registró la versión de RDKit usada para la identidad.""": """This run did not record the RDKit version used for identity.""",
    """SHA-256 de identidad v2""": """Identity v2 SHA-256""",
    """La corrida no registró un hash de identidad con versión de RDKit.""": """This run did not record an identity hash with an RDKit version.""",
    """La conectividad procede del SMILES y las coordenadas proceden de ESMFold.""": """Connectivity comes from the SMILES, and coordinates come from ESMFold.""",
    """El manifiesto no registró el recuento de coordenadas.""": """The manifest did not record the coordinate count.""",
    """Átomos transferidos / completados""": """Atoms transferred / completed""",
    """La transferencia no registró cómo completó los átomos ausentes.""": """The transfer did not record how missing atoms were completed.""",
    """Método de completado geométrico""": """Geometric completion method""",
    """Versión del mapeo""": """Mapping version""",
    """La transferencia no registró su versión de mapeo.""": """The transfer did not record its mapping version.""",
    """motivo no registrado""": """reason not recorded""",
    """Estereoquímica del ligando""": """Ligand stereochemistry""",
    """No se pudo asignar el isómero desde la geometría 3D guardada.""": """The isomer could not be assigned from the saved 3D geometry.""",
    """SMILES isomérico derivado del conformero 3D guardado.""": """Isomeric SMILES derived from the saved 3D conformer.""",
    """La corrida registra el pH, el microestado y el tautómero (ver el protocolo); la estereoquímica no se evaluó en esa corrida.""": """This run records pH, microstate, and tautomer (see the protocol); stereochemistry was not evaluated in that run.""",
    """Protonación, tautomería y estereoquímica""": """Protonation, tautomerism, and stereochemistry""",
    """El pipeline no registra la forma protonada ni el tautómero elegidos.""": """The pipeline does not record the selected protonation form or tautomer.""",
    """El diff registrado no declara el margen del sitio.""": """The recorded diff does not declare the site margin.""",
    """Eficiencia por átomo pesado""": """Efficiency per heavy atom""",
    """Sin afinidad o sin recuento de átomos: no se calcula.""": """No affinity or atom count: not calculated.""",
    """Eficiencia de ligando (LE)""": """Ligand efficiency (LE)""",
    """No calculable.""": """Not calculable.""",
    """Generación conformacional""": """Conformer generation""",
    """Esta corrida es anterior al sellado del protocolo de generación 3D. No se sustituye por la configuración del caso: sería atribuirle un ajuste que nadie guardó con ella.""": """This run predates sealing of the 3D generation protocol. The case configuration is not substituted: that would attribute settings to the run that no one saved with it.""",
    """El protocolo sellado no declara el número de conformaciones.""": """The sealed protocol does not declare the number of conformers.""",
    "método no registrado por la corrida": "method not recorded by the run",
    "Enumeración de microestados": "Microstate enumeration",
    "Contexto de ensayo": "Assay context",
    "pH del ensayo frente al de protonación": "Assay pH versus protonation pH",
    "Cadenas del constructo frente a las del receptor": "Construct chains versus receptor chains",
    "Cofactores del ensayo frente a los conservados": "Assay cofactors versus kept cofactors",
    "Coinciden.": "They match.",
    "Temperatura, magnitud medida, constructo y fuente se transmiten tal como los declaró el caso; la corrida no tiene con qué compararlos.": "Temperature, measured quantity, construct and source are carried as the case declared them; the run has nothing to compare them with.",
    "Vuelve a evaluar con el pH del ensayo, o registra una decisión que diga por qué la especie acoplada sirve igual.": "Evaluate again at the assay pH, or record a decision saying why the docked species still serves.",
    "Prepara el receptor con las cadenas del constructo, o registra una decisión que diga por qué las del receptor representan el ensayo.": "Prepare the receptor with the construct chains, or record a decision saying why the receptor chains represent the assay.",
    "Declara en el receptor los cofactores del ensayo y vuelve a evaluar, o registra una decisión que diga por qué su ausencia o su presencia no cambia la lectura.": "Declare the assay cofactors in the receptor and evaluate again, or record a decision saying why their absence or presence does not change the reading.",
    "La corrida no registró a qué pH se protonó el ligando: la comparación con el ensayo no se pudo hacer.": "The run did not record the pH at which the ligand was protonated: the comparison with the assay could not be made.",
    "La corrida no registró las cadenas del receptor acoplado: la comparación con el ensayo no se pudo hacer.": "The run did not record the chains of the docked receptor: the comparison with the assay could not be made.",
    "La corrida no registró qué cofactores conservó: la comparación con el ensayo no se pudo hacer.": "The run did not record which cofactors it kept: the comparison with the assay could not be made.",
    "dimorphite-dl devolvió su número máximo de microestados: el conjunto puede estar incompleto y la especie acoplada se eligió entre los que devolvió.": "dimorphite-dl returned its maximum number of microstates: the set may be incomplete and the docked species was chosen among those it returned.",
    "Faltan poses o afinidad serializada.": "Poses or serialized affinity are missing.",
    "EVIDENCIA DISPONIBLE": "EVIDENCE AVAILABLE",
    "EVIDENCIA INCOMPLETA": "INCOMPLETE EVIDENCE",
    "Sin datos suficientes": "Insufficient data",
    "MARGEN DE SCORE AMPLIO — la diana principal puntúa al menos 2.73 kcal/mol mejor que la peor anti-diana": "WIDE SCORE MARGIN — the main target scores at least 2.73 kcal/mol better than the worst anti-target",
    "MARGEN DE SCORE MODERADO — entre 1.36 y 2.73 kcal/mol a favor de la diana principal": "MODERATE SCORE MARGIN — between 1.36 and 2.73 kcal/mol in favor of the main target",
    "MARGEN DE SCORE ESTRECHO — menos de 1.36 kcal/mol, dentro de la dispersión del score de Vina": "NARROW SCORE MARGIN — less than 1.36 kcal/mol, within the dispersion of the Vina score",
    "SIN MARGEN DE SCORE — scores indistinguibles entre diana y anti-diana": "NO SCORE MARGIN — scores indistinguishable between target and anti-target",
    "MARGEN DE SCORE NEGATIVO — la molécula puntúa mejor contra una anti-diana que contra su diana": "NEGATIVE SCORE MARGIN — the molecule scores better against an anti-target than against its target",
    "sin clasificación": "unclassified",
    "El resultado almacenado no guarda identificador de corrida: la correspondencia con la corrida que declara el caso no se pudo comprobar.": "The stored result keeps no run identifier: its correspondence with the run declared by the case could not be verified.",
    "El caso no la declaró; es la del resultado almacenado.": "The case did not declare it; it is the stored result's run.",
    "el modelo plegó la estructura pero ninguna pose pasó por acoplamiento": "the model folded the structure but no pose went through docking",
    "el servicio respondió sin poses": "the service responded without poses",
    "El protocolo no informa si hubo ensemble; no se registraron réplicas.": "The protocol does not report whether there was an ensemble; no replicates were recorded.",
    "Confórmero único; no se registraron réplicas.": "Single conformer; no replicates were recorded.",
    "La geometría de entrada no se optimizó con MMFF94 hasta converger, o la corrida no registró cómo se optimizó: las poses de Vina parten de ella.": "The input geometry was not optimized with MMFF94 to convergence, or the run did not record how it was optimized: the Vina poses start from it.",
    """Esta corrida es anterior al sellado de los residuos de referencia. No se sustituyen por los del catálogo: podrían no ser los que se usaron.""": """This run predates sealing of the reference residues. They are not replaced with the catalog entries: those may differ from the residues used.""",
    """Ninguno: la persona decidió no usar residuos de referencia""": """None: the user chose not to use reference residues""",
    """Sin residuos de referencia la corrida no calcula qué residuos del sitio contactan las poses.""": """Without reference residues, the run does not calculate which site residues contact the poses.""",
    """Receptor no informado""": """Receptor not reported""",
    """El backend no resolvió la molécula.""": """The backend did not resolve the molecule.""",
    """Respaldo del receptor""": """Receptor support""",
    """El caso no registró identificador de corrida.""": """The case did not record a run identifier.""",
    """Fecha de la corrida""": """Run date""",
    """La corrida no serializó su fecha.""": """This run did not serialize its date.""",
    """Esquema del dossier""": """Dossier schema""",
    """Tipo de estudio""": """Study type""",
    """¿Qué intenta responder este caso?""": """What is this case trying to answer?""",
    """¿Qué decisión se pretende tomar?""": """What decision is intended?""",
    """¿Qué justifica la elección del sistema?""": """What supports the choice of system?""",
    """¿Qué controles o referencias existen?""": """What controls or references are available?""",
    """Notas del caso (contexto libre; no entra en ningún cálculo)""": """Case notes (free text; not used in any calculation)""",
})

ENGLISH_MESSAGES.update({
    """Filas NO elegibles""": """Ineligible rows""",
    """· requieren revisión""": """· require review""",
    """· no evaluadas""": """· not evaluated""",
    """Selector: no disponible""": """Selector: unavailable""",
    """activa""": """active""",
    """inactiva""": """inactive""",
    """NO DISPONIBLE""": """NOT AVAILABLE""",
    """La contraparte verificable de `dossier.pdf`. Permite comprobar que la lectura del PDF se hizo sobre estos archivos y no sobre otros.""": """The verifiable counterpart to `dossier.pdf`. It lets you check that the PDF was based on these files and not on others.""",
    """Es el MISMO verificador que valida los paquetes de caso: un solo protocolo de manifiesto y checksums para todo el producto.""": """This is the SAME verifier used for case packages: one manifest and checksum protocol for the whole product.""",
    """Si el resultado no es `VÁLIDO`, no uses el contenido: el paquete no describe lo que dice describir.""": """If the result is not `VALID`, do not use the contents: the package does not describe what it claims to describe.""",
    """el ZIP no se contiene a sí mismo;""": """the ZIP does not contain itself;""",
    """`checksums.sha256` no se hashea a sí mismo;""": """`checksums.sha256` does not include its own hash;""",
    """`manifest.json` no se declara a sí mismo dentro de `files` — su integridad la cubre `checksums.sha256`, que se calcula después.""": """`manifest.json` does not declare itself in `files`—its integrity is covered by `checksums.sha256`, which is calculated afterward.""",
    """`dossier.pdf` — la lectura humana.""": """`dossier.pdf` — the human-readable dossier.""",
    """`cohort.json` — la cohorte congelada (definición normalizada y procedencia).""": """`cohort.json` — the frozen cohort definition and provenance.""",
    """`preflight.json` — el veredicto de comprobación previa, con TODAS las filas.""": """`preflight.json` — the preflight verdict, including every row.""",
    """`run.json` — la corrida: configuración efectiva, receptor, estado, contadores.""": """`run.json` — the run record: effective configuration, receptor, status, and counts.""",
    """`evidence.json` — este resumen científico completo.""": """`evidence.json` — the complete scientific summary.""",
    """`rows.csv` — una línea por fila de trabajo.""": """`rows.csv` — one line per work row.""",
    """`inputs/` — el archivo original tal como se subió, y el receptor preparado.""": """`inputs/` — the original uploaded file and the prepared receptor.""",
    """Filas en el archivo""": """Rows in the file""",
    """Elegibles""": """Eligible""",
    """Moléculas únicas acopladas""": """Unique molecules docked""",
    """Completadas""": """Completed""",
    """fallidas""": """failed""",
    """no evaluadas""": """not evaluated""",
    """duplicados reutilizados""": """reused duplicates""",
    """No garantiza validez científica. Completar un acoplamiento no demuestra actividad.""": """Scientific validity is not guaranteed. Completing a docking run does not demonstrate activity.""",
    """No contiene ranking de candidatos ni puntuación agregada.""": """It contains no candidate ranking or aggregate score.""",
    """No garantiza reproducibilidad bit a bit: eso depende de la versión del motor y del hardware.""": """Bitwise reproducibility is not guaranteed; it depends on the engine version and hardware.""",
    """Tautómero del ligando""": """Ligand tautomer""",
    """structural_evidence (PoseBusters con hidrógenos reconstruidos desde el SMILES; condición MF-33-H-COR)""": """structural_evidence (PoseBusters with hydrogens reconstructed from SMILES; MF-33-H-COR condition)""",
})

ENGLISH_MESSAGES.update({
    """Se persistieron los pesos normalizados usados realmente en esta corrida.""": """The normalized weights actually used in this run were persisted.""",
    """Señal · warheads de zinc (UMS, SMARTS)""": """Zinc warhead signal (UMS, SMARTS)""",
    """No se calculó la señal de warheads.""": """The warhead signal was not calculated.""",
    """Sin un perfil de M5-Zn no hay fórmula que aplicar. Las señales individuales sí están disponibles y se muestran por separado.""": """There is no formula to apply without an M5-Zn profile. Individual signals are available and shown separately.""",
    """No se resolvió el perfil.""": """The profile could not be resolved.""",
    """Fórmula del perfil""": """Profile formula""",
    """El perfil no declara su fórmula.""": """The profile does not declare its formula.""",
    """El perfil no declara sus componentes.""": """The profile does not declare its components.""",
    """Normalización de Vina (congelada por perfil)""": """Vina normalization (fixed by profile)""",
    """El perfil no declara su normalizador.""": """The profile does not declare its normalizer.""",
    """No se pudo calcular.""": """Could not be calculated.""",
    """El protocolo se ejecutó y no produjo score compuesto.""": """The protocol ran but did not produce a composite score.""",
    """La corrida no registró ningún estado de M5-Zn: es anterior a SCHEMA 18, cuando el protocolo se conectó al pipeline. Hasta entonces estaba implementado y sin llamador, así que estos casos se puntuaron con M4 y los pesos por defecto del stacking. Las señales individuales de arriba sí son de esta corrida.""": """This run did not record an M5-Zn status: it predates SCHEMA 18, when the protocol was connected to the pipeline. Until then, it was implemented without a caller, so these cases were scored with M4 and the stacking defaults. The individual signals above do come from this run.""",
    """BENCHMARK EN REVISIÓN""": """BENCHMARK UNDER REVIEW""",
    """PROCEDENCIA SIN VERIFICAR""": """PROVENANCE NOT VERIFIED""",
    """TOP-1 SIN COORDINAR EL METAL""": """TOP-1 WITHOUT METAL COORDINATION""",
    """Faltó al menos un componente con peso distinto de cero en la fórmula del perfil. No se renormalizan pesos ni se sustituye un modelo por otro (§5). El caso de CA2/3DC3 es GNN-D: no existe productor de esa señal en producción —sólo aparece en los checkpoints de benchmark— y el §4.1 prohíbe sustituirla por CL-GNN.""": """At least one component with nonzero weight in the profile formula was missing. Weights are not renormalized, and one model is not substituted for another (§5). The CA2/3DC3 case uses GNN-D: no production component generates that signal—it appears only in benchmark checkpoints—and §4.1 prohibits substituting CL-GNN.""",
    """Es una metaloenzima de zinc, pero su PDB no es ninguno de los tres perfiles de M5-Zn. M5-Zn prepara el receptor, conserva el zinc, ejecuta Vina y calcula señales diagnósticas, y NO hereda los pesos de otra diana (§7.2).""": """This is a zinc metalloenzyme, but its PDB is not one of the three M5-Zn profiles. M5-Zn prepares the receptor, retains zinc, runs Vina, and calculates diagnostic signals; it does NOT inherit weights from another target (§7.2).""",
    """El PDB corresponde a un perfil de M5-Zn pero no se confirmó el zinc en la estructura. Un carboxilato, tiol o sulfonamida en el ligando es una feature del ligando, no un centro metálico (§8).""": """The PDB matches an M5-Zn profile, but zinc was not confirmed in the structure. A carboxylate, thiol, or sulfonamide in the ligand is a ligand feature, not a metal center (§8).""",
    """La diana es metálica y este producto no tiene protocolo validado para ese metal. Se declara en vez de degradarse a M4 en silencio (§6.1).""": """The target contains a metal, and this product has no validated protocol for that metal. This is declared instead of silently falling back to M4 (§6.1).""",
    """Auditor de readiness para FEP en desarrollo""": """FEP readiness auditor in development""",
    """Huecos del esqueleto""": """Backbone gaps""",
    """La corrida no midió los huecos del esqueleto: su receptor se preparó antes de registrarlos o se congeló antes. No se reconstruye con la receta de hoy.""": """This run did not measure backbone gaps: its receptor was prepared before they were recorded or was frozen earlier. They are not reconstructed from today's recipe.""",
    """Ninguno: el esqueleto de las cadenas del receptor es continuo (C–N ≤ 2 Å entre residuos consecutivos).""": """None: the receptor-chain backbones are continuous (C–N ≤ 2 Å between consecutive residues).""",
    """Lejos del sitio no cambian la cavidad, pero un cálculo con disolvente explícito necesita esos extremos capados o modelados.""": """Away from the site, they do not change the cavity, but an explicit-solvent calculation needs those termini capped or modeled.""",
    """Residuos retirados por la preparación""": """Residues removed during preparation""",
    """La corrida no registró qué residuos retiró la preparación del receptor.""": """This run did not record which residues receptor preparation removed.""",
    """Meeko no retiró residuos y no hubo cofactores sin plantilla fuera del sitio.""": """Meeko removed no residues, and there were no cofactors without templates outside the site.""",
    """Fuera del margen no impiden la corrida, pero el receptor que se entregaría no los contiene. Declarar si importan para el cálculo siguiente.""": """Outside the site margin, they do not block the run, but the receptor to be transferred does not contain them. Declare whether they matter for the next calculation.""",
    """La corrida no registró qué cadenas laterales incompletas del cristal se truncaron: su receta es anterior a la v7 o el receptor se congeló antes.""": """This run did not record which incomplete crystal side chains were truncated: its recipe predates v7 or the receptor was frozen earlier.""",
    """Ninguna: el cristal resolvía todas las cadenas laterales del receptor.""": """None: the crystal resolved all receptor side chains.""",
    """El cristal no resolvía esas cadenas laterales y se truncaron a ALA o GLY, conservando sólo átomos observados.""": """The crystal did not resolve those side chains, so they were truncated to ALA or GLY, retaining only observed atoms.""",
    """En el sitio, la cavidad pierde esos grupos: un cálculo posterior tendría que reconstruirlos, y declararlo, o partir de otra estructura.""": """At the site, the cavity lacks those groups: a later calculation would need to rebuild them and declare that choice, or start from another structure.""",
    """Fuera del sitio no cambian la cavidad, pero el receptor que se entregaría no los contiene.""": """Away from the site, they do not change the cavity, but the receptor to be transferred does not contain them.""",
    """La corrida no registró qué proteína quedó fuera del receptor junto a la caja.""": """This run did not record which protein was left outside the receptor near the box.""",
    """Puede ser un sitio entre cadenas o una caja que invade la cadena vecina: el ligando podría acoplarse contra el hueco que deja.""": """This may be a site between chains or a box that extends into a neighboring chain: the ligand could dock into the gap it leaves.""",
    """Protonación del receptor""": """Receptor protonation""",
    """Asignación por plantilla, sin pH experimental: el estado de histidinas, ácidos y bases del sitio no está validado.""": """Template-based assignment, without experimental pH: the state of site histidines, acids, and bases has not been validated.""",
    """La corrida no registró cómo se protonó el receptor.""": """This run did not record how the receptor was protonated.""",
    """La corrida no registró el hash del receptor preparado.""": """This run did not record the prepared receptor hash.""",
    """Cadenas del receptor""": """Receptor chains""",
    """La corrida no registró qué cadenas forman el receptor.""": """This run did not record which chains make up the receptor.""",
    """La corrida no persistió la caja de búsqueda efectiva.""": """This run did not persist the effective search box.""",
    """La corrida no registró la forma del ligando que se acopló.""": """This run did not record the form of the ligand that was docked.""",
    """La corrida no registró la protonación del ligando.""": """This run did not record ligand protonation.""",
    """La corrida es anterior a la declaración de tautómeros y no se reconstruye.""": """This run predates tautomer declaration, which is not reconstructed.""",
    """Validez física de la pose principal""": """Physical validity of the primary pose""",
    # Las dos frases fijas de la validez física en la metodología del informe
    # individual. La rama con veredicto lleva el estado interpolado y vive como
    # plantilla en `i18n_plantillas`; el límite del análisis externo es común a
    # las dos ramas (SCI-A-008).
    """<b>Validez física:</b> en esta corrida los controles de química y geometría no llegaron a emitir veredicto, y esa ausencia no habla de las poses.""": """<b>Physical validity:</b> in this run the chemistry and geometry checks did not issue a verdict, and that absence says nothing about the poses.""",
    """El análisis geométrico externo debe documentarse antes de cálculos posteriores o decisiones experimentales.""": """External geometric analysis should be documented before further calculations or experimental decisions.""",
    """La etapa de validación no dejó detalle.""": """The validation stage left no details.""",
    """No hay evidencia física de la pose principal.""": """There is no physical evidence for the primary pose.""",
    """Regla de selección de la pose""": """Pose selection rule""",
    """La corrida no permitió identificar la pose principal (top-1 de Vina).""": """This run did not identify the primary pose (Vina top-1).""",
    """Hay dos candidatas a pose de partida. Elegir una es una decisión que el cálculo siguiente hereda.""": """There are two candidates for the starting pose. Choosing one is a decision that the next calculation will inherit.""",
    """Poses de la corrida""": """Run poses""",
    """La corrida no conservó el archivo de poses con su hash.""": """This run did not retain the pose file and its hash.""",
    """Correspondencia atómica de la serie""": """Atomic mapping across the series""",
    """Requiere una serie de ligandos; esta auditoría cubre una corrida.""": """This requires a ligand series; this audit covers one run.""",
    """no aplica a una corrida""": """not applicable to a run""",
    """Política de heteroátomos""": """Heteroatom policy""",
    """La corrida no declaró la ruta de preparación aplicada.""": """This run did not declare the preparation route used.""",
    """La corrida usó un receptor congelado y su informe de preparación no viaja con ella.""": """This run used a frozen receptor, and its preparation report is not included.""",
    """La corrida no serializó qué retiró la preparación: su receptor se preparó antes de registrarlo. No se reconstruye con la receta de hoy.""": """This run did not serialize what preparation removed: its receptor was prepared before that was recorded. It is not reconstructed from today's recipe.""",
    """El receptor que se entregaría no contiene especies que estaban en el sitio. Hay que decidir sobre ellas antes de cualquier cálculo posterior.""": """The receptor to be transferred does not contain species that were in the site. Decide how to handle them before any later calculation.""",
    """La ruta de docking retira todas las aguas. No se ha decidido cuáles son estructurales y cuáles desplazables.""": """The docking route removes all waters. It has not determined which are structural and which are displaceable.""",
    """Pueden ser aditivos de cristalización o parte de la cavidad; la preparación no lo distingue.""": """They may be crystallization additives or part of the cavity; preparation does not distinguish between them.""",
    """Ninguna retirada aparte del ligando del cristal""": """No removal apart from the crystal ligand""",
    """Hashes de entrada y salida""": """Input and output hashes""",
    """La corrida no registró su procedencia de ejecución.""": """This run did not record its execution provenance.""",
    """Versiones de la corrida""": """Run versions""",
    """La corrida no registró la cadena de herramientas.""": """This run did not record the toolchain.""",
    """Semilla y parámetros""": """Seed and parameters""",
    """La corrida no registró la semilla.""": """This run did not record the seed.""",
    """Relación con los inputs del caso""": """Relationship to the case inputs""",
    """La corrida se ejecutó con los inputs actuales del caso.""": """This run used the case's current inputs.""",
    """La corrida no registró la huella de sus inputs.""": """This run did not record its input fingerprint.""",
    """La corrida no quedó atada a una comprobación previa.""": """This run was not linked to a preflight check.""",
    """La comprobación previa del caso no corresponde a los inputs de esta corrida.""": """The case preflight does not match this run's inputs.""",
    """Bloqueantes de la comprobación previa""": """Preflight blockers""",
    """Controles previos sin evaluar""": """Preflight checks not evaluated""",
    """Advertencias registradas antes de ejecutar.""": """Warnings recorded before execution.""",
    """No se evaluaron: eso no equivale a que los pasaran.""": """They were not evaluated; that does not mean they passed.""",
    """Commit de código""": """Code commit""",
    """La corrida no declaró un commit verificable (bundle o árbol modificado).""": """This run did not declare a verifiable commit (bundle or modified tree).""",
    """huellas de la corrida y del preflight""": """run and preflight fingerprints""",
    """Falta evidencia imprescindible o hay una abstención declarada.""": """Required evidence is missing or an abstention was declared.""",
    """Hay decisiones científicas abiertas que el cálculo siguiente heredaría.""": """Open scientific decisions would carry over to the next calculation.""",
    """Controles superados para el alcance declarado.""": """Checks passed for the declared scope.""",
    """Todos los requisitos tienen dato registrado, pero la transferencia a un cálculo FEP no está demostrada: FEP-06 sigue sin sellar.""": """All requirements have recorded data, but transfer to an FEP calculation has not been demonstrated: FEP-06 remains unsealed.""",
    """Paquete de la corrida""": """Run package""",
    """Es el paquete reproducible del dossier de esta corrida. No es un paquete FEP.""": """This is the reproducible package for this run's dossier. It is not an FEP package.""",
    """Filas NO elegibles""": """Ineligible rows""",
    """· requieren revisión""": """· require review""",
    """· no evaluadas""": """· not evaluated""",
    """Selector: no disponible""": """Selector: unavailable""",
    """Que estas moléculas se acoplaron contra este receptor con esta configuración.""": """That these molecules were docked against this receptor with this configuration.""",
    """Qué proporción de la cohorte llegó a producir un resultado, y qué quedó fuera.""": """What proportion of the cohort produced a result, and what was excluded.""",
    """Que dos corridas con la misma huella describen el mismo cálculo.""": """That two runs with the same fingerprint describe the same calculation.""",
    """Revisar geométricamente las poses de las moléculas con mejor afinidad observada antes de atribuirles cualquier significado.""": """Review the poses of molecules with the best observed affinity geometrically before assigning them any meaning.""",
    """Ejecutar un control de re-acoplamiento del ligando cristalográfico si el receptor lo tiene, para saber si el protocolo recupera una pose conocida.""": """If the receptor includes the crystallographic ligand, run a re-docking control to check whether the protocol recovers a known pose.""",
    """Repetir la cohorte con otra semilla y comparar el orden: si cambia, el orden no era estable.""": """Repeat the cohort with another seed and compare the ordering; if it changes, the ordering was not stable.""",
    """Ampliar los controles declarados. Una cohorte sin referencia no se puede interpretar aunque sus números sean buenos.""": """Expand the declared controls. A cohort without a reference cannot be interpreted, even if its numbers look good.""",
})
# QA2-010: los errores del recibo histórico conservan la condición de la corrida.
ENGLISH_MESSAGES.update({
    'Corrida no encontrada': 'Run not found',
    'Esta corrida no conserva un recibo': 'This run has no saved receipt',
})

# Molcy (2026-10-04): configuración, instalación de Blender y de Molecular Nodes, y mensajes de trabajo.
# Sólo mensajes estáticos que el usuario ve; las comprobaciones de que no falte ninguno viven en test_molcy_mensajes.py.
ENGLISH_MESSAGES.update({
    "No se encontró Blender. Descárgalo desde la configuración de abajo o elige tu blender.exe.":
        "Blender was not found. Download it from the settings below or choose your blender.exe.",
    "No se encontró el motor Molcy. Elige su carpeta en la configuración de abajo.":
        "The Molcy engine was not found. Choose its folder in the settings below.",
    "La carpeta del motor Molcy está incompleta: faltan scripts/maestro.py, scripts/correr_caso.ps1 o la plantilla de arte.":
        "The Molcy engine folder is incomplete: scripts/maestro.py, scripts/correr_caso.ps1 or the art template is missing.",
    "El motor Molcy incluido en MolDesign está dañado o fue modificado. Reinstala MolDesign.":
        "The Molcy engine included with MolDesign is damaged or was modified. Reinstall MolDesign.",
    "El acta no acredita el cierre de MolDesign; el video no se entrega.":
        "The build record does not confirm the MolDesign outro; the video is not delivered.",
    "El video no dura lo que declara su acta: falta el cierre de MolDesign.":
        "The video is not as long as its build record says: the MolDesign outro is missing.",
    "MolDesign usa el motor Molcy incluido; elegir otro motor no está disponible.":
        "MolDesign uses the bundled Molcy engine; choosing another engine is not available.",
    "Molcy requiere Blender 5.2 o superior. Usa el Blender de MolDesign (recomendado) o actualiza el tuyo.":
        "Molcy requires Blender 5.2 or later. Use the MolDesign Blender (recommended) or update yours.",
    "Blender no pudo renderizar con Cycles en CPU.":
        "Blender could not render with Cycles on CPU.",
    "Blender devolvió una comprobación ilegible.":
        "Blender returned an unreadable check result.",
    "Falta Molecular Nodes en este Blender. Instálalo para generar vídeos.":
        "Molecular Nodes is missing from this Blender. Install it to generate videos.",
    "Blender no pudo cargar Molecular Nodes sin conexión.":
        "Blender could not load Molecular Nodes offline.",
    "El estado del trabajo está dañado o no se pudo leer.":
        "The job state is damaged or could not be read.",
    "Render interrumpido al cerrar MolDesign.":
        "Render interrupted when MolDesign was closed.",
    "Render cancelado por el usuario.":
        "Render canceled by the user.",
    "Molcy no produjo MP4 y acta final":
        "Molcy did not produce an MP4 and its final build record",
    "El acta no acredita el renderizador solicitado":
        "The build record does not confirm the requested renderer",
    "El SHA-256 del MP4 no coincide con el acta":
        "The MP4 SHA-256 does not match the build record",
    "Molcy ya tiene un render activo. Espera o cancélalo antes de generar otro vídeo.":
        "Molcy already has an active render. Wait for it or cancel it before generating another video.",
    "Cancela el render y espera a que termine antes de eliminarlo.":
        "Cancel the render and wait for it to finish before deleting it.",
    "La ruta del trabajo no pertenece al usuario.":
        "The job path does not belong to the user.",
    "Molcy detuvo el render porque el espacio libre cayó por debajo de la reserva de 1 GiB.":
        "Molcy stopped the render because free space fell below the 1 GiB reserve.",
    "Modo de Blender inválido":
        "Invalid Blender mode",
    "Descarga de Blender cancelada.":
        "Blender download canceled.",
    "Blender no coincide con el tamaño y SHA-256 oficiales; no se instalará.":
        "Blender does not match the official size and SHA-256; it will not be installed.",
    "El destino no pertenece a la instalación administrada de MolDesign.":
        "The destination does not belong to the MolDesign-managed installation.",
    "Blender no coincide con el SHA-256 oficial; no se instalará.":
        "Blender does not match the official SHA-256; it will not be installed.",
    "La instalación administrada ya existe.":
        "The managed installation already exists.",
    "Elige el blender.exe existente con su ruta absoluta.":
        "Choose the existing blender.exe with its absolute path.",
    "Elige la carpeta del motor Molcy, que contiene scripts/maestro.py.":
        "Choose the Molcy engine folder, which contains scripts/maestro.py.",
    "La instalación administrada ya existe; selecciona ese Blender o configura uno existente.":
        "The managed installation already exists; select that Blender or configure an existing one.",
    "Espacio insuficiente en la unidad de datos de MolDesign: se reservan 4,4 GiB.":
        "Not enough space on the MolDesign data drive: 4.4 GiB is reserved.",
    "La descarga se redirigió fuera del servidor oficial de Blender.":
        "The download was redirected away from the official Blender server.",
    "El ZIP no tiene la estructura o tamaño esperado de Blender.":
        "The ZIP does not have the expected Blender structure or size.",
    "El ZIP no contiene blender.exe.":
        "The ZIP does not contain blender.exe.",
    "Blender no se instaló. Comprueba el espacio libre y que ningún antivirus bloquee la carpeta de datos de MolDesign.":
        "Blender was not installed. Check the free space and that no antivirus is blocking the MolDesign data folder.",
    "Espacio insuficiente antes de instalar Blender.":
        "Not enough space before installing Blender.",
    "La instalación ya está aplicándose; espera a que termine.":
        "The installation is already being applied; wait for it to finish.",
    "El ZIP de Blender excede el tamaño oficial.":
        "The Blender ZIP exceeds the official size.",
    "Espacio insuficiente durante la descarga de Blender.":
        "Not enough space during the Blender download.",
    "El ZIP contiene una ruta fuera de la instalación de Blender.":
        "The ZIP contains a path outside the Blender installation.",
    "El ZIP contiene un enlace simbólico.":
        "The ZIP contains a symbolic link.",
    "La instalación sólo está disponible si falta Molecular Nodes.":
        "Installation is only available when Molecular Nodes is missing.",
    "No se encontró Blender en una ruta absoluta.":
        "Blender was not found at an absolute path.",
    "Blender no tiene configurado el repositorio oficial de extensiones.":
        "Blender does not have the official extensions repository configured.",
    "Blender no informó dónde instala sus extensiones.":
        "Blender did not report where it installs its extensions.",
    "Espacio insuficiente para descargar e instalar Molecular Nodes: se requiere 1 GiB libre en el perfil de Blender.":
        "Not enough space to download and install Molecular Nodes: 1 GiB free is required in the Blender profile.",
    "Espera a que termine la instalación de Blender o Molecular Nodes.":
        "Wait for the Blender or Molecular Nodes installation to finish.",
    "Esta corrida no conserva una búsqueda interna compatible con Molcy.":
        "This run has no saved internal search compatible with Molcy.",
    "La traza no pertenece al ligando de esta corrida.":
        "The trace does not belong to this run's ligand.",
    "La escena elegida no corresponde al origen seleccionado.":
        "The chosen scene does not match the selected source.",
    "Trabajo no encontrado.":
        "Job not found.",
    "Este trabajo no está renderizando.":
        "This job is not rendering.",
    "Vídeo no encontrado.":
        "Video not found.",
    "El vídeo ya no coincide con su SHA-256.":
        "The video no longer matches its SHA-256.",
    "Procedencia no encontrada.":
        "Provenance not found.",
    "Acceso al vídeo caducado.":
        "Video access expired.",
    "La corrida no conserva su caja de docking exacta.":
        "The run does not keep its exact search box.",
    "El motor Molcy instalado no trae la escena Ensamble; actualízalo.":
        "The installed Molcy engine does not include the Ensemble scene; update it.",
    "La corrida no es un ensamble de conformaciones.":
        "The run is not a conformer ensemble.",
    "La corrida no conserva la procedencia de cada conformación; las evaluaciones de ensamble nuevas la guardan automáticamente.":
        "The run does not keep each conformation's provenance; new ensemble evaluations save it automatically.",
    "Las poses entregadas no conservan de qué conformación salieron.":
        "The delivered poses do not keep which conformation they came from.",
    "Un SDF de la corrida no conserva una geometría 3D legible.":
        "A run SDF does not keep a readable 3D geometry.",
    "Una conformación no se corresponde átomo a átomo con las poses; no se alinea.":
        "A conformation does not match the poses atom by atom; it is not aligned.",
    "Evaluación no encontrada.":
        "Evaluation not found.",
    "Espera a que termine el render antes de instalar Molecular Nodes.":
        "Wait for the render to finish before installing Molecular Nodes.",
    "Espera a que termine la instalación de Blender.":
        "Wait for the Blender installation to finish.",
    "Espera a que termine el render antes de cambiar su instalación.":
        "Wait for the render to finish before changing its installation.",
    "Espera a que termine la instalación de Molecular Nodes.":
        "Wait for the Molecular Nodes installation to finish.",
    "Espera a que termine el render antes de instalar Blender.":
        "Wait for the render to finish before installing Blender.",
    "La procedencia del vídeo no se pudo leer.":
        "The video provenance could not be read.",
    "Actualiza el motor Molcy para poder elegir los hilos de CPU.":
        "Update the Molcy engine to be able to choose CPU threads.",
    "Evaluación no encontrada en Moldex.":
        "Evaluation not found in Moldex.",
    "Corrida terminada no encontrada.":
        "Finished run not found.",
    "La corrida no conserva receptor y poses con hashes verificables.":
        "The run does not keep a receptor and poses with verifiable hashes.",
    "Un archivo de la corrida ya no coincide con su SHA-256.":
        "A file from the run no longer matches its SHA-256.",
    "Falta la preparación registrada de este receptor.":
        "The registered preparation of this receptor is missing.",
    "El receptor ya no coincide con su SHA-256 registrado.":
        "The receptor no longer matches its registered SHA-256.",
    "Falta un archivo persistido de la corrida.":
        "A stored file of the run is missing.",
    "No hay estructura local; añade un PDB antes de renderizar.":
        "There is no local structure; add a PDB before rendering.",
    "No se encontró el PDBQT preparado de este receptor.":
        "The prepared PDBQT for this receptor was not found.",
    # VM-MOLCY-01 (2026-10-12): el Python auxiliar de Blender sin el runtime de Visual C++ x64.
    "El Python auxiliar de Blender no arranca: le falta una biblioteca de Microsoft Visual C++ x64 (0xC0000135, STATUS_DLL_NOT_FOUND), así que Blender no puede descargar el catálogo de extensiones.":
        "Blender's helper Python cannot start: a Microsoft Visual C++ x64 library is missing (0xC0000135, STATUS_DLL_NOT_FOUND), so Blender cannot download the extensions catalog.",
    "El runtime de Visual C++ que trae MolDesign está incompleto o alterado: reinstala MolDesign.":
        "The Visual C++ runtime that ships with MolDesign is incomplete or was altered: reinstall MolDesign.",
    "MolDesign no pudo colocar su runtime junto a ese Python; comprueba que ningún antivirus bloquee la carpeta de datos de MolDesign y vuelve a intentarlo.":
        "MolDesign could not place its runtime next to that Python; check that no antivirus is blocking the MolDesign data folder and try again.",
    "MolDesign no modifica tu Blender: usa el Blender de MolDesign (recomendado), que lo resuelve sin permisos de administrador.":
        "MolDesign does not modify your Blender: use MolDesign's Blender (recommended), which solves this without administrator permissions.",
    "El Python auxiliar de Blender no respondió en 60 s; Blender no puede instalar extensiones.":
        "Blender's helper Python did not respond within 60 s; Blender cannot install extensions.",
    "Blender no pudo descargar el catálogo oficial de extensiones (extensions.blender.org), así que no encontró Molecular Nodes.":
        "Blender could not download the official extensions catalog (extensions.blender.org), so it did not find Molecular Nodes.",
    "Comprueba la conexión a Internet y vuelve a intentarlo.":
        "Check the Internet connection and try again.",
    "Blender no pudo instalar Molecular Nodes.":
        "Blender could not install Molecular Nodes.",
})

# I18N-DOSSIER-03: rótulos iniciales para exportar dossier, PDF y paquete.
ENGLISH_MESSAGES.update({
    "DOSSIER DE EVIDENCIA COMPUTACIONAL": "COMPUTATIONAL EVIDENCE DOSSIER",
    "Este documento describe qué evidencia produjo una corrida, qué partes son reproducibles y qué quedó sin evaluar. No califica la molécula ni afirma que sea un fármaco, un candidato clínico ni un compuesto seguro.": (
        "This document describes what evidence a run produced, which parts are reproducible, "
        "and what remained unevaluated. It does not rate the molecule or claim that it is "
        "a drug, clinical candidate, or safe compound."
    ),
    "MolDesign · dossier de evidencia computacional · no es una recomendación clínica": (
        "MolDesign · computational evidence dossier · not a clinical recommendation"
    ),
    "Campo": "Field",
    "Contenido": "Content",
    "Estado": "Status",
    "Valor": "Value",
    "Observación y protocolo": "Observation and protocol",
    "Afinidad Vina (kcal/mol)": "Vina affinity (kcal/mol)",
    "Controles físicos": "Physical checks",
    "Papel": "Role",
    "Controles que fallan": "Failed checks",
    "Rango": "Rank",
    "Afinidad (kcal/mol)": "Affinity (kcal/mol)",
    "RMSD l.b.": "RMSD lower bound",
    "RMSD u.b.": "RMSD upper bound",
    "Decisión": "Decision",
    "Aplica a los inputs actuales": "Applies to current inputs",
    "Sí": "Yes",
    "NO DEFINIDO": "NOT DEFINED",
    "NO EVALUADO": "NOT EVALUATED",
    "NO DISPONIBLE": "NOT AVAILABLE",
    "NO APLICA": "NOT APPLICABLE",
    "REVISAR": "REVIEW",
    "ABSTENCIÓN": "ABSTENTION",
    "REGISTRADO": "RECORDED",
    "PASA": "PASSED",
    "Control": "Check",
    "Significado": "Meaning",
    "Veredicto por pose": "Verdict by pose",
    "manifiesto": "manifest",
    "evaluadas": "evaluated",
    "NO EVALUADAS": "NOT EVALUATED",
    "El caso no declaró este contexto.": "The case did not declare this context.",
    "El control no se ejecutó en esta corrida.": "The control was not evaluated in this run.",
    "El resultado o artefacto esperado no está disponible.": "The expected result or artifact is unavailable.",
    "El control no corresponde a este caso.": "The control does not apply to this case.",
    "Hay evidencia, pero no autoriza una conclusión por sí sola.": "Evidence is available, but it does not support a conclusion on its own.",
    "Falta evidencia indispensable o existe un bloqueo declarado.": "Required evidence is missing or a declared blocker exists.",
    "El dato existe y quedó serializado por la corrida.": "The data exists and was serialized by the run.",
    "El control se ejecutó y lo superó.": "The control ran and passed.",
    "Dossier reproducible": "Reproducible dossier",
    "Paquete": "Package",
    "Caso": "Case",
    "Corrida": "Run",
    "Generado": "Generated",
    "Modelo del dossier": "Dossier model",
    "Qué es esto": "What this is",
    "Qué NO es": "What this is NOT",
    "Estructura": "Contents",
    "Integridad": "Integrity",
    "Para verificar": "To verify",
    "Tres exclusiones deliberadas": "Three deliberate exclusions",
    "Qué demuestra un checksum, y qué no": "What a checksum proves, and what it does not",
    "Artefactos ausentes": "Missing artifacts",
    "Glosario de estados": "Status glossary",
    "Cómo verificarlo": "How to verify it",
    "Los tres ciclos de hash": "The three hash cycles",
    "Qué hay dentro": "What's inside",
    "Cobertura": "Coverage",
    "Qué NO garantiza": "What this does NOT guarantee",
    "4 · Cobertura y excepciones": "4 · Coverage and exclusions",
    "7 · Métricas etiquetadas": "7 · Labeled metrics",
    "8 · Qué puede y qué NO puede concluirse": "8 · What can and cannot be concluded",
    "9 · Próximos pasos justificables": "9 · Justified next steps",
    "10 · Procedencia": "10 · Provenance",
    "1. Pregunta y propósito del caso": "1. Case question and purpose",
    "2. Resumen de lo ejecutado": "2. Summary of what ran",
    "3. Entradas y procedencia": "3. Inputs and provenance",
    "4. Preparación del sistema y supuestos": "4. System preparation and assumptions",
    "5. Protocolo y entorno de ejecución": "5. Protocol and run environment",
    "6. Evidencia estructural y acoplamiento": "6. Structural evidence and docking",
    "7. Generación de poses": "7. Pose generation",
    "8. Selección de pose": "8. Pose selection",
    "9. Validación geométrica y física": "9. Geometric and physical validation",
    "10. Controles físicos y geométricos": "10. Physical and geometric checks",
    "11. Evidencia por dimensión": "11. Evidence by dimension",
    "12. Supuestos declarados": "12. Declared assumptions",
    "13. Incertidumbres y limitaciones": "13. Uncertainties and limitations",
    "14. Interpretación justificable y próximos pasos": "14. Supported interpretation and next steps",
    "15. Procedencia e instrucciones de verificación": "15. Provenance and verification instructions",
    "16. Glosario de estados": "16. Status glossary",
    "Apéndice A. Resultados heredados (no decisionales)": "Appendix A. Legacy outputs (not for decisions)",
    "Dossier de cohorte": "Cohort dossier",
    "Evidencia computacional de una cohorte": "Computational evidence for a cohort",
    "Huella de cohorte": "Cohort fingerprint",
    "Huella de corrida": "Run fingerprint",
    "3 · Configuración efectiva": "3 · Effective configuration",
    "4 · Cobertura y excepciones": "4 · Coverage and exceptions",
    "5 · Evidencia por molécula": "5 · Evidence by molecule",
    "6 · Controles declarados": "6 · Declared controls",
    "Este documento responde una pregunta computacional y sólo una: qué entró en esta cohorte, qué se pudo acoplar bajo una configuración común, y qué quedó sin evaluar. NO responde si alguna de estas moléculas es un fármaco.": (
        "This dossier answers exactly one computational question: what entered this cohort, "
        "what could be docked under a shared configuration, and what remained unevaluated. "
        "It does NOT answer whether any of these molecules is a drug."
    ),
    "Cómo reproducir esta corrida": "How to reproduce this run",
    "1. Qué se ejecutó": "1. What ran",
    "2. Comprobar primero la integridad": "2. Check integrity first",
    "3. Repetir el acoplamiento": "3. Repeat the docking run",
    "3.1. La evidencia estructural, en crudo": "3.1. Raw structural evidence",
    "4. Qué NO garantiza este paquete": "4. What this package does NOT guarantee",
    "Molécula": "Molecule",
    "sin identificador": "no identifier",
    "no resuelta": "unresolved",
    "sin razón registrada": "no reason recorded",
    "Los parámetros exactos están en `run/protocol.json`, campo `parametros`. Cada uno lleva su estado: los que digan `NO_DISPONIBLE` no fueron serializados por la corrida y **no se pueden reproducir a ciegas**.": (
        "The exact parameters are in `run/protocol.json`, under `parametros`. Each has a status: "
        "those marked `NO_DISPONIBLE` were not serialized by the run and **cannot be reproduced blindly**."
    ),
    "Si el resultado no es `VÁLIDO`, no reproduzcas nada: el paquete no describe lo que dice describir.": (
        "If the result is not `VALID`, do not reproduce anything: the package does not describe what it claims to describe."
    ),
    "Con MolDesign: abre el caso, restaura los inputs de `case/case_snapshot.json`, ejecuta la comprobación previa y compara la huella resultante con `input_fingerprint`. Si coincide, la corrida nueva parte de la misma hipótesis.": (
        "With MolDesign: open the case, restore the inputs from `case/case_snapshot.json`, run the preflight check, "
        "and compare the resulting fingerprint with `input_fingerprint`. If they match, the new run starts from the same hypothesis."
    ),
    "Fuera de MolDesign: consulta el estado de cada campo en `run/protocol.json`. Sólo los valores `REGISTRADO` proceden de la corrida; los `NO_DISPONIBLE` impiden afirmar que el cálculo puede reconstruirse. Usa `inputs/ligand_docked.smi` para la especie acoplada y `inputs/ligand.smi` para la entrada original, cuando ambos archivos estén registrados. Comprueba también el receptor preparado y la caja de búsqueda efectiva antes de repetir Vina. Los archivos `inputs/ligand_input.sdf`, `inputs/ligand_input.pdbqt` y `logs/vina.log` llevan los bytes archivados cuando sus SHA-256 coincidieron con la procedencia de la corrida; su ausencia queda declarada en el manifiesto.": (
        "Outside MolDesign: check the status of each field in `run/protocol.json`. Only `REGISTRADO` values come from the run; "
        "`NO_DISPONIBLE` values prevent you from claiming that the calculation can be reconstructed. Use `inputs/ligand_docked.smi` "
        "for the docked species and `inputs/ligand.smi` for the original input when both files are recorded. Also check the prepared "
        "receptor and effective search box before repeating Vina. The files `inputs/ligand_input.sdf`, `inputs/ligand_input.pdbqt`, "
        "and `logs/vina.log` contain the archived bytes when their SHA-256 hashes matched the run's provenance; their absence is stated in the manifest."
    ),
    (
        "El score está calculado y es reproducible, y NO se ha demostrado que el "
        "sitio sea incorrecto: en ACE/1O86 el zinc está dentro de la caja —es su "
        "centro exacto— y las poses también. Lo que no se puede verificar es la "
        "procedencia: falta el complejo cristalográfico para comprobar el "
        "bolsillo del inhibidor, ningún artefacto registra la caja de búsqueda efectiva, y "
        "el checkpoint tiene 44 registros sin pose y 21 sin features. El "
        "componente que depende de la pose pesa 0.60. «No se puede comprobar que "
        "esté bien» no es «está mal», y tampoco es «está validado». Ver "
        "docs/77_CORRIGENDUM_SITIO_DEL_BENCHMARK_M5_ZN.md §1.2 y §7."
    ): (
        "The score is computed and reproducible, and the site has not been shown "
        "to be incorrect: at ACE/1O86, zinc is inside the box—at its exact center—"
        "and so are the poses. Provenance cannot be verified: the crystal complex "
        "needed to check the inhibitor pocket is missing, no artifact records the "
        "effective search box, and the checkpoint has 44 records without a pose "
        "and 21 without features. The pose-dependent component has a weight of "
        "0.60. “Cannot verify that it is correct” does not mean “it is wrong,” "
        "and it does not mean “it is validated.” See "
        "docs/77_CORRIGENDUM_SITIO_DEL_BENCHMARK_M5_ZN.md §1.2 and §7."
    ),
    "- `evidencia/structural_evidence.json` — veredicto físico POR POSE tal y como lo persistió el backend: motor, cobertura, controles que fallan y su razón.": (
        "- `evidencia/structural_evidence.json` — the per-pose physical verdict as persisted by the backend: engine, coverage, failed checks, and their reasons."
    ),
    "- `evidencia/pose_selection.json` — la recomendación del selector: Vina top-1, pose sugerida, margen, umbral, abstención y alternativas.": (
        "- `evidencia/pose_selection.json` — the selector's recommendation: Vina top-1, suggested pose, margin, threshold, abstention, and alternatives."
    ),
    "- `evidencia/pose_index.json` — qué pose es cuál y a qué bloque PDBQT exacto apunta. `outputs/poses.sdf` aparece además sólo cuando representa de verdad la colección; en un ensemble no se finge que el SDF de una conformación sea la piscina completa.": (
        "- `evidencia/pose_index.json` — which pose is which and the exact PDBQT block it points to. `outputs/poses.sdf` is included only "
        "when it truly represents the collection; for an ensemble, a single-conformation SDF is not presented as the full set."
    ),
    "- `evidencia/pose_selector_model.json` — modelo, versión y SHA-256 del selector.": (
        "- `evidencia/pose_selector_model.json` — selector model, version, and SHA-256."
    ),
    "La configuración de la corrida NO se repite aquí: vive en `run/protocol.json`, donde cada parámetro lleva además su estado. Un segundo archivo con los mismos valores en plano crearía dos sitios donde mirar y ninguna comprobación nueva.": (
        "The run configuration is NOT repeated here: it lives in `run/protocol.json`, where each parameter also has a status. "
        "A second file with the same plain values would create two places to look and no new check."
    ),
    "El protocolo registra conformeros solicitados y generados cuando la etapa los informó. No registra una serie completa de restarts; ningún campo ausente se rellena desde la configuración declarada por el caso.": (
        "The protocol records requested and generated conformers when the stage reported them. It does not record a complete series of restarts; "
        "no missing field is filled from the configuration declared by the case."
    ),
    "El PDF es una lectura de estos archivos. Están en crudo para que se pueda comprobar que el documento no añadió, quitó ni suavizó nada.": (
        "The PDF is a readable view of these files. They are provided raw so you can check that the document did not add, remove, or soften anything."
    ),
    "Dos cosas que estos archivos NO dicen: `review` no significa pose aprobada —la batería no corrió entera—, y `not_evaluated` describe lo que le pasó al validador, nunca a la molécula. Ninguna de las dos es evidencia negativa sobre el compuesto.": (
        "These files do NOT say two things: `review` does not mean the pose was approved—the full check suite did not run—and `not_evaluated` "
        "describes what happened to the validator, never to the molecule. Neither is negative evidence about the compound."
    ),
    "- No garantiza que el resultado sea reproducible bit a bit: eso depende de la versión del motor y del hardware.": (
        "- It does not guarantee bit-for-bit reproducibility; that depends on the engine version and hardware."
    ),
    "- No garantiza validez científica. Los estados del dossier dicen qué se comprobó y qué no.": (
        "- It does not guarantee scientific validity. The dossier statuses say what was checked and what was not."
    ),
    "- **Un checksum correcto demuestra integridad, no validez.** Prueba que los archivos coinciden con el manifiesto y los checksums que trae el propio paquete; que no cambiaron desde la exportación sólo se comprueba contra una huella guardada aparte. No prueba que el método fuera adecuado, que la preparación fuera correcta ni que la conclusión sea cierta. Que el paquete sea `VÁLIDO` es una afirmación sobre los archivos, no sobre la ciencia.": (
        "- **A correct checksum demonstrates integrity, not validity.** It proves that the files match the manifest and checksums the package itself carries; "
        "that they have not changed since export can only be checked against a fingerprint kept separately. "
        "It does not prove that the method was suitable, the preparation was correct, or the conclusion is true. `VALID` means the files passed verification, not that the science is valid."
    ),
    "- No afirma que el compuesto sea activo, eficaz, seguro ni un candidato a fármaco. Nada en este paquete sostiene esa clase de conclusión.": (
        "- It does not claim that the compound is active, effective, safe, or a drug candidate. Nothing in this package supports that kind of conclusion."
    ),
    "La contraparte verificable de `dossier.pdf`. El PDF es la lectura humana del caso; este paquete permite comprobar que esa lectura se hizo sobre los archivos que declara, y detectar si alguno falta o cambió.": (
        "The verifiable counterpart to `dossier.pdf`. The PDF is the human-readable view of the case; this package lets you check that the view was based on the files it declares and detect whether any are missing or changed."
    ),
    "**Ninguno sustituye al otro.**": "**Neither replaces the other.**",
    "No es una recomendación. No afirma que la molécula sea un fármaco, un candidato clínico ni un compuesto seguro. Los índices 0-100 que aparecen en el apéndice del PDF no son probabilidad, confianza ni calidad, y no son decisionales.": (
        "This is not a recommendation. It does not claim that the molecule is a drug, clinical candidate, or safe compound. The 0–100 indices in the PDF appendix are not probability, confidence, or quality measures, and they are not decision criteria."
    ),
    "este archivo": "this file",
    "lectura humana del caso": "human-readable view of the case",
    "rol, tamaño, SHA-256 y estado de cada archivo": "role, size, SHA-256, and status of each file",
    "índice ordenado de hashes": "sorted hash index",
    "proyección del caso y modelo canónico": "case projection and canonical model",
    "protocolo y receta de reproducción": "protocol and reproduction instructions",
    "receptor y ligando, cuando existen": "receptor and ligand, when available",
    "poses y resultados serializados": "serialized poses and results",
    "evidencia estructural, selección y controles": "structural evidence, selection, and checks",
    "advertencias y errores de ESTA corrida": "warnings and errors for THIS run",
    "El verificador comprueba, sin extraer ni ejecutar nada: que ninguna entrada escape del directorio raíz, que el manifiesto sea de una versión compatible, que todos los archivos declarados existan, que sus SHA-256 y tamaños coincidan, que no haya duplicados y que no haya archivos no declarados.": (
        "Without extracting or running anything, the verifier checks that no entry escapes the root directory, the manifest version is supported, "
        "all declared files exist, their SHA-256 hashes and sizes match, and there are no duplicates or undeclared files."
    ),
    "1. **El ZIP no se contiene a sí mismo.** Un paquete que llevara su propia copia no podría cerrarse: su hash cambiaría al incluirlo.": (
        "1. **The ZIP does not contain itself.** A package containing its own copy could not be finalized: its hash would change when included."
    ),
    "2. **`checksums.sha256` no se hashea a sí mismo.** Escribir su hash dentro de sí mismo es imposible por la misma razón.": (
        "2. **`checksums.sha256` does not include its own hash.** Writing its hash into the file is impossible for the same reason."
    ),
    "3. **`manifest.json` no se declara a sí mismo** dentro de `files`, por lo mismo. Su integridad **sí** queda cubierta: `checksums.sha256` se calcula después e incluye el manifiesto, así que una modificación del manifiesto se detecta.": (
        "3. **`manifest.json` does not declare itself** in `files`, for the same reason. Its integrity **is** covered: `checksums.sha256` is calculated afterward and includes the manifest, so any change to the manifest is detected."
    ),
    "El verificador conoce las tres y no las reporta como archivos no declarados.": "The verifier knows about all three and does not report them as undeclared files.",
    "Un checksum correcto demuestra **integridad, no validez**: prueba que los archivos coinciden con el manifiesto y los checksums que trae el propio paquete; que no cambiaron desde la exportación sólo se comprueba contra una huella guardada aparte. No prueba que el método fuera adecuado, que la preparación fuera correcta, que las poses sean físicamente razonables ni que la conclusión sea cierta. Que el verificador diga `VÁLIDO` es una afirmación sobre los ARCHIVOS, nunca sobre la ciencia — y nada en este paquete afirma que el compuesto sea activo, eficaz o seguro.": (
        "A correct checksum demonstrates **integrity, not validity**: the files match the manifest and checksums the package itself carries; that they have not changed since export "
        "can only be checked against a fingerprint kept separately. It does not prove that the method was suitable, "
        "the preparation was correct, the poses are physically reasonable, or the conclusion is true. `VALID` is a statement about the FILES, never the science, and this package does not claim that the compound is active, effective, or safe."
    ),
    "Un archivo ausente se declara; no se sustituye por un marcador que parezca el artefacto.": "A missing file is declared; it is not replaced with a marker that looks like the artifact.",
    "Ninguno: todos los artefactos declarados están presentes.": "None: all declared artifacts are present.",
    "Este documento describe qué evidencia produjo una corrida, qué partes son reproducibles y qué quedó sin evaluar. No califica la molécula ni afirma que sea un fármaco, un candidato clínico ni un compuesto seguro.": (
        "This document describes the evidence produced by a run, what can be reproduced, and what was not evaluated. It does not rate the molecule or claim that it is a drug, clinical candidate, or safe compound."
    ),
    "El estado técnico, la disposición científica y la revisión humana son tres cosas distintas. Que un proceso termine no valida su resultado, y que no haya alertas no significa que alguien lo haya revisado.": (
        "Technical status, scientific disposition, and human review are three separate things. A process finishing does not validate its result, and the absence of alerts does not mean anyone reviewed it."
    ),
    "Hash del ligando (SMILES)": "Ligand hash (SMILES)",
    "Referencia del receptor": "Receptor reference",
    "Hash de la configuración": "Configuration hash",
    "Hash de las poses": "Pose hash",
    "La corrida no selló el ligando.": "The run did not seal the ligand.",
    "Sin referencia de receptor.": "No receptor reference.",
    "Sin configuración sellada.": "No sealed configuration.",
    "La corrida no serializó bloques de pose que sellar.": "The run did not serialize pose blocks to seal.",
    "Decisiones humanas registradas": "Recorded human decisions",
    "Sugerida": "Suggested",
    "Alternativa válida": "Valid alternative",
    "Las afinidades son señales de ranking dentro de este protocolo, no mediciones de energía libre. La pose de mejor energía no es, por serlo, la pose correcta: sin un control geométrico superado no hay evidencia estructural.": (
        "Affinities are ranking signals within this protocol, not measurements of free energy. The pose with the best energy is not necessarily the correct pose: without a passed geometric check, there is no structural evidence."
    ),
    "Los parámetros que la corrida no persistió aparecen como NO EVALUADO con su razón. No se sustituyen por los de la configuración del caso: describirían un ajuste que nadie guardó con este resultado.": (
        "Parameters that the run did not persist appear as NOT EVALUATED with a reason. They are not replaced with values from the case configuration: that would describe settings no one saved with this result."
    ),
    "El selector RECOMIENDA; no sustituye. La pose principal del producto sigue siendo la top-1 de Vina, que se conserva y se declara siempre. Cuando el selector se abstiene, falta o falla, la referencia es Vina top-1 en calidad de FALLBACK — no como un acierto del selector. El margen de confianza es la distancia entre la primera y la segunda pose según el modelo: no es una probabilidad ni una nota.": (
        "The selector RECOMMENDS; it does not replace. The product's primary pose remains Vina top-1, which is always retained and declared. If the selector abstains, is missing, or fails, the reference is Vina top-1 as a FALLBACK—not as a selector success. The confidence margin is the distance between the first and second pose according to the model; it is not a probability or a score."
    ),
    "Sólo un CONTROL SUPERADO explícito autoriza llamar válida a una pose. REVISIÓN describe una batería que no corrió entera, y NO EVALUADO un validador que no corrió: las dos describen lo que le pasó a la comprobación, nunca a la molécula, y ninguna de las dos es evidencia negativa sobre el compuesto.": (
        "Only an explicit PASSED CHECK allows a pose to be called valid. REVIEW describes a check suite that did not run in full, and NOT EVALUATED describes a validator that did not run: both describe what happened to the check, never to the molecule, and neither is negative evidence about the compound."
    ),
    "La ausencia de alertas no equivale a validez: un control que no se ejecutó aparece como NO EVALUADO y no autoriza ninguna conclusión.": (
        "The absence of alerts does not establish validity: a check that did not run appears as NOT EVALUATED and supports no conclusion."
    ),
    "No se registraron incertidumbres adicionales. Esto no significa que no existan.": "No additional uncertainties were recorded. This does not mean none exist.",
    "Ninguna acción de esta lista afirma que el compuesto sea un fármaco, un candidato clínico ni un compuesto seguro. Describen qué trabajo computacional queda justificado por la evidencia de esta corrida.": (
        "None of these actions claims that the compound is a drug, clinical candidate, or safe compound. They describe what computational work is justified by the evidence from this run."
    ),
    "El paquete reproducible que acompaña a este dossier lleva un `manifest.json` con rol, tamaño y SHA-256 de cada archivo, y un `checksums.sha256` ordenado que permite detectar archivos ausentes, modificados o añadidos.": (
        "The reproducible package accompanying this dossier includes a `manifest.json` with the role, size, and SHA-256 of each file, and a sorted `checksums.sha256` file that detects missing, modified, or added files."
    ),
    "<b>Cómo verificar el paquete, sin ejecutar nada:</b> (1) abrir el ZIP y leer `manifest.json`, que declara rol, tamaño y SHA-256 de cada archivo, incluidos los ausentes con su razón; (2) recalcular el SHA-256 de cada archivo y compararlo con `checksums.sha256`; (3) comprobar que no sobra ni falta ningún archivo respecto al manifiesto. El propio ZIP, `checksums.sha256` y la entrada de `manifest.json` dentro de `files` quedan fuera por construcción —un archivo no puede contener su propio hash—, y el README del paquete lo declara.": (
        "<b>How to verify the package without running anything:</b> (1) open the ZIP and read `manifest.json`, which declares each file's role, size, and SHA-256, "
        "including missing files and their reason; (2) recalculate each file's SHA-256 and compare it with `checksums.sha256`; (3) check that no file is missing or extra relative to the manifest. "
        "The ZIP itself, `checksums.sha256`, and the `manifest.json` entry inside `files` are excluded by design—a file cannot contain its own hash—and the package README explains this."
    ),
    "Un checksum correcto demuestra INTEGRIDAD: que los archivos coinciden con el manifiesto y los checksums que trae el propio paquete; que no cambiaron desde la exportación sólo se comprueba contra una huella guardada aparte. No demuestra que el método sea adecuado, que la preparación fuera correcta ni que la conclusión sea cierta. Integridad no es validez científica, y este dossier no las presenta como lo mismo.": (
        "A correct checksum demonstrates INTEGRITY: the files match the manifest and checksums the package itself carries; that they have not changed since export can only be checked against a fingerprint kept separately. It does not show that the method is suitable, the preparation was correct, or the conclusion is true. Integrity is not scientific validity, and this dossier does not present them as the same."
    ),
    "Los índices siguientes los calcula el pipeline por compatibilidad con lecturas anteriores. <b>No son decisionales.</b> No son probabilidad, ni confianza, ni calidad, y no deben usarse para comparar moléculas ni para priorizar trabajo experimental.": (
        "The following indices are calculated by the pipeline for compatibility with earlier reports. <b>They are not decision criteria.</b> They are not probability, confidence, or quality measures, and should not be used to compare molecules or prioritize experimental work."
    ),
    "Esta corrida no serializó ningún índice heredado.": "This run did not serialize any legacy indices.",
    "Dossier de evidencia computacional": "Computational evidence dossier",
    "VÁLIDO": "VALID",
    "INVÁLIDO": "INVALID",
    "ruta absoluta": "absolute path",
    "ruta con unidad de disco": "path with a drive letter",
    "separador de Windows en la entrada del ZIP": "Windows path separator in ZIP entry",
    "componente `..` (escape de directorio)": "`..` component (directory traversal)",
    "componente vacío o `.`": "empty or `.` component",
    "El paquete está vacío.": "The package is empty.",
    "Falta `manifest.json`.": "`manifest.json` is missing.",
    "(no determinada)": "(undetermined)",
    "`manifest.json` no declara `manifest_version` entera.": "`manifest.json` does not declare an integer `manifest_version`.",
    "`manifest.json` no declara una lista `files`.": "`manifest.json` does not declare a `files` list.",
    "Una entrada del manifiesto no es un objeto JSON.": "A manifest entry is not a JSON object.",
    "Una entrada del manifiesto no tiene `path`.": "A manifest entry has no `path`.",
    "No se declara a sí mismo: su hash cambiaría al escribirlo. Su integridad la cubre `checksums.sha256`, que se calcula después.": (
        "It does not declare itself: its hash would change when written. Its integrity is covered by `checksums.sha256`, which is calculated afterward."
    ),
    "No se hashea a sí mismo: su hash cambiaría al escribirlo.": "It does not include its own hash; its contents would change if that hash were written inside it.",
    "El paquete no se contiene a sí mismo.": "The package does not contain itself.",
    "cliente (proyección validada)": "client (validated projection)",
    "El artefacto no estaba disponible al construir el paquete.": "The artifact was unavailable when the package was built.",
    "Revisa la especie antes de un cálculo de energía libre.": "Review the species before a free-energy calculation.",
    "Ninguno de estos pasos recomienda un fármaco, un candidato clínico ni un compuesto seguro. Describen qué trabajo computacional queda justificado.": (
        "None of these steps recommends a drug, clinical candidate, or safe compound. They describe what computational work is justified."
    ),
    "Se listan para comparar. NINGUNA se selecciona automáticamente.": (
        "They are listed for comparison. NONE is selected automatically."
    ),
    "La disposición final no está vinculada a la huella de la corrida documentada. Se conserva como declaración, pero no se considera aplicable a esta evidencia.": (
        "The final disposition is not linked to the fingerprint of the documented run. It is preserved as a statement, but is not considered applicable to this evidence."
    ),
    "La corrida no registró qué motor se ejecutó.": "This run did not record which engine ran.",
    "La corrida no registró a qué pH se protonó el ligando.": (
        "This run did not record the pH used to protonate the ligand."
    ),
    "Una métrica calculada sin cumplir sus condiciones no es una métrica aproximada: es un número que parece un resultado.": (
        "A metric calculated without meeting its conditions is not an approximate measure; it is a number that looks like a result."
    ),
    "<b>Decisiones humanas:</b> NO EVALUADO — nadie ha revisado ni reconocido controles de esta corrida.": (
        "<b>Human decisions:</b> NOT EVALUATED — no one has reviewed or acknowledged this run's checks."
    ),
    "Estos hashes permiten a un tercero comprobar que las conclusiones de este dossier se calcularon sobre las entradas que declara. El registro en devnet, si existe, guarda en su memo el hash del SMILES, el score redondeado, el PDB, una fecha declarada por quien firma y la wallet: no identifica la revisión de este documento, no acredita su fecha de emisión ni certifica sobre qué se calculó. Ninguno de los dos sustituye al otro.": (
        "These hashes let a third party verify that this dossier's conclusions were calculated from the inputs it declares. The devnet record, if there is one, stores in its memo the SMILES hash, the rounded score, the PDB, a date declared by the signer and the wallet: it does not identify this document's revision, does not attest to its issue date and does not certify what it was calculated from. Neither replaces the other."
    ),
    "protocolo de búsqueda": "search protocol",
    "hash del receptor": "receptor hash",
    "hashes de entrada del ligando": "ligand input hashes",
    "hashes de salida (poses y registro)": "output hashes (poses and log)",
    "preparación del ligando": "ligand preparation",
    "versión de la aplicación": "application version",
    "REVISIÓN NECESARIA": "REVIEW REQUIRED",
    "Al menos la pose principal falla los controles de química o geometría.": "At least the primary pose fails the chemistry or geometry checks.",
    "La batería no corrió entera sobre todas las poses, o la pose principal pasa y alguna alternativa falla. «Revisión necesaria» describe una comprobación que hay que mirar, NO una pose aprobada.": (
        "Either the full check suite did not run on every pose, or the primary pose passes while an alternative fails. ‘Review required’ describes a check that must be inspected, NOT an approved pose."
    ),
    "sin código de razón": "no reason code",
    "RECOMENDACIÓN EMITIDA": "RECOMMENDATION ISSUED",
    "SELECTOR NO DISPONIBLE": "SELECTOR UNAVAILABLE",
    "La corrida conserva poses, procedencia y los elementos registrados para intentar reconstruirla; la reconstrucción por un tercero no está demostrada.": (
        "The run retains poses, provenance, and the recorded items needed to attempt reconstruction; reconstruction by a third party has not been demonstrated."
    ),
    "La corrida produjo evidencia útil, pero contiene reservas que deben revisarse antes de continuar.": (
        "The run produced useful evidence, but it contains caveats that should be reviewed before proceeding."
    ),
    "Faltan afinidad o poses; esta corrida no debe usarse para priorizar el ligando.": (
        "Affinity or poses are missing; this run should not be used to prioritize the ligand."
    ),
    "No hay poses para describir la separación interna.": "There are no poses from which to describe the internal separation.",
    "Solo hay una pose; no puede describirse separación interna.": "There is only one pose; internal separation cannot be described.",
    "modelo de familia": "family model",
    "modelo no informado": "model not reported",
    "motor no informado": "engine not reported",
    "Preparación del sistema": "System preparation",
    "Señal de docking": "Docking signal",
    "Muestreo de poses": "Pose sampling",
    "Reproducibilidad técnica": "Technical reproducibility",
    "Validez física de poses": "Physical validity of poses",
    "Dominio del modelo": "Model applicability domain",
    "DENTRO DEL DOMINIO DECLARADO": "WITHIN DECLARED DOMAIN",
    "FUERA DEL DOMINIO": "OUTSIDE DOMAIN",
    "Descriptores fisicoquímicos": "Physicochemical descriptors",
    "Evidencia de selectividad": "Selectivity evidence",
    "EJECUCIÓN SIN RESULTADOS": "RUN WITH NO RESULTS",
    "Las afinidades se interpretan como señales de ranking dentro del protocolo, no como mediciones de energía libre experimental.": (
        "Affinities are interpreted as ranking signals within the protocol, not as experimental free-energy measurements."
    ),
    "La mejor pose cruda se identifica por el orden de afinidad serializado; ese orden no demuestra validez geométrica.": (
        "The best raw pose is identified by serialized affinity order; that order does not demonstrate geometric validity."
    ),
    "No se atribuyen operaciones de preparación, protonación o minimización que la corrida no haya registrado.": (
        "No preparation, protonation, or minimization steps are attributed to the run unless it recorded them."
    ),
    "Preparación en condición desolvatada: se eliminaron todas las aguas cristalográficas del receptor. Si esta diana requiere aguas puente conservadas para el reconocimiento molecular, los contactos y las afinidades de esta corrida no las incluyen.": (
        "Desolvated preparation: all crystallographic waters were removed from the receptor. If this target requires conserved bridging waters for molecular recognition, this run's contacts and affinities do not include them."
    ),
    # Un receptor propio (camino B o C) trae las aguas de su archivo (FEP-09, 2026-10-11).
    "Las aguas del receptor son las del archivo que se subió: MolDesign no las retiró ni decidió cuáles conservar, y Vina trata las que haya como parte rígida del receptor. Si esta diana requiere aguas puente, la corrida sólo las incluye si las traía ese archivo.": (
        "The receptor's waters are those of the uploaded file: MolDesign did not remove them or decide which to keep, and Vina treats any present as a rigid part of the receptor. If this target requires bridging waters, the run includes them only if that file contained them."
    ),
    "Preparación en condición desolvatada: el receptor acoplado no trae aguas cristalográficas dentro de la caja de acoplamiento. Se subió sin su estructura de origen, así que no se sabe si las tenía.": (
        "Desolvated preparation: the docked receptor has no crystallographic waters inside the docking box. It was uploaded without its source structure, so it is unknown whether it had any."
    ),
    "no registrados": "not recorded",
    "ABSTENCIÓN: COMPLETAR LA CORRIDA": "ABSTENTION: COMPLETE THE RUN",
    "VALIDAR GEOMETRÍA ANTES DE CONTINUAR": "VALIDATE GEOMETRY BEFORE PROCEEDING",
    "RESOLVER RESERVAS ANTES DE COMPARAR": "RESOLVE CAVEATS BEFORE COMPARING",
    "APTA PARA ANÁLISIS POSTERIOR": "SUITABLE FOR FURTHER ANALYSIS",
    "RTMScore, deprecada. Conserva peso en algunas familias del artefacto vigente.": (
        "RTMScore is deprecated. It retains weight in some families in the current artifact."
    ),
    "Un valor nulo significa que la etapa no se ejecuto o no serializo su salida. No se sustituye por cero ni por un neutro: eso convertiria una ausencia en una prediccion.": (
        "A null value means the step did not run or did not serialize an output. It is not replaced with zero or a neutral value: that would turn a missing result into a prediction."
    ),
    "Informe de evaluación de una corrida (no es el dossier del caso)": "Evaluation report for one run (not the case dossier)",
    "INFORME DE EVALUACIÓN": "EVALUATION REPORT",
    "Nombre": "Name",
    "<b>Nombre Asignado:</b>": "<b>Assigned name:</b>",
    "<b>Estructura SMILES:</b>": "<b>SMILES string:</b>",
    "<font color='#d97706'><b>[SISTEMA: ARCHIVO DE USUARIO]</b> La estructura fue aportada por el usuario. No se infieren operaciones de protonación o minimización que no estén registradas.</font>": (
        "<font color='#d97706'><b>[SYSTEM: USER-PROVIDED FILE]</b> The structure was provided by the user. Protonation or minimization steps are not inferred unless they were recorded.</font>"
    ),
    "<font color='#16a34a'><b>[SISTEMA: LISTO PARA EVALUAR]</b> El receptor está preparado y dispone de grid y referencias estructurales. Esto no implica validación experimental.</font>": (
        "<font color='#16a34a'><b>[SYSTEM: READY FOR EVALUATION]</b> The receptor is prepared and has a grid and structural references. This does not imply experimental validation.</font>"
    ),
    "<font color='#d97706'><b>[SISTEMA: REVISAR PREPARACIÓN]</b> El inventario del receptor no permite afirmar que preparación, grid y hotspots estén completos.</font>": (
        "<font color='#d97706'><b>[SYSTEM: REVIEW PREPARATION]</b> The receptor inventory does not support a claim that preparation, grid, and hotspots are complete.</font>"
    ),
    "<b>Nombre Común (PubChem):</b>": "<b>Common name (PubChem):</b>",
    "<b>Nombre Sistemático (IUPAC):</b>": "<b>Systematic name (IUPAC):</b>",
    "<b>ID de Sistema:</b>": "<b>System ID:</b>",
    "<b>Firma de Transacción:</b>": "<b>Transaction signature:</b>",
    "<b>Hash del Registro:</b>": "<b>Record hash:</b>",
    "<b>Enlace de Verificación:</b>": "<b>Verification link:</b>",
    "<i>La huella de este informe todavía no está registrada en Solana. El registro acredita integridad y fecha, no descubrimiento ni validez científica.</i>": (
        "<i>This report's fingerprint has not yet been recorded on Solana. The record supports integrity and timestamp, not discovery or scientific validity.</i>"
    ),
    "dentro del dominio declarado": "within the declared domain",
    "fuera del dominio declarado": "outside the declared domain",
    "dominio no informado": "domain not reported",
    "motor y modelo no informados": "engine and model not reported",
    "CONTROLES SUPERADOS": "CHECKS PASSED",
    "CONTROLES FALLIDOS": "CHECKS FAILED",
    "NO EVALUADA": "NOT EVALUATED",
    "Evidencia, reproducibilidad, supuestos, controles e incertidumbres": "Evidence, reproducibility, assumptions, checks, and uncertainties",
    "Supuestos e incertidumbres abiertas": "Open assumptions and uncertainties",
    "Supuestos registrados | Incertidumbres abiertas": "Recorded assumptions | Open uncertainties",
    "Dimensión": "Dimension",
    "Valor observado": "Observed value",
    "Valor calculado": "Calculated value",
    "Propiedad": "Property",
    "Salida": "Output",
    "Solubilidad Acuosa (LogS)": "Aqueous solubility (LogS)",
    "Peso Molecular (MW)": "Molecular weight (MW)",
    "Donadores H-Bond (HBD)": "H-bond donors (HBD)",
    "Aceptores H-Bond (HBA)": "H-bond acceptors (HBA)",
    "Enlaces Rotables": "Rotatable bonds",
    "Mejor pose Vina cruda": "Best raw Vina pose",
    "Poses serializadas": "Serialized poses",
    "Metabolismo CYP (P450)": "CYP metabolism (P450)",
    "Propiedad modelada (ADMET-AI)": "Modeled property (ADMET-AI)",
    "Integridad y registro temporal (Solana)": "Integrity and timestamp record (Solana)",
    "pose SDF": "SDF pose",
    "Caja de búsqueda efectiva": "Effective search box",
    "caja de búsqueda efectiva": "effective search box",
    "hashes de salida (poses y registro)": "output hashes (poses and record)",
    "no registrado": "not recorded",
    "no informado": "not reported",
    "modelo no informado": "model not reported",
    "motor no informado": "engine not reported",
    "INSUFICIENTE": "INSUFFICIENT",
    "DISPONIBLE": "AVAILABLE",
    "AMBIGUO": "AMBIGUOUS",
    "PARCIAL": "PARTIAL",
    "NO INFORMADO": "NOT REPORTED",
    "SIN DATOS": "NO DATA",
    "CUMPLE": "PASS",
    "NO CUMPLE": "FAIL",
    "NO EVALUADO": "NOT EVALUATED",
    "EJECUCIÓN SIN RESULTADOS": "RUN WITH NO RESULTS",
    "NO COMPARABLE": "NOT COMPARABLE",
    "DESCRIPTIVO": "DESCRIPTIVE",
    "SIN EVIDENCIA": "NO EVIDENCE",
    "NOTA": "NOTE",
    "CRÍTICA": "CRITICAL",
    "PRECAUCIÓN": "CAUTION",
    "POSITIVA": "POSITIVE",
    "DOCUMENTADA": "DOCUMENTED",
    "CRUZA UMBRAL": "CROSSES THRESHOLD",
    "PDB INVALIDO": "INVALID PDB",
    "FALLO": "FAILED",
    "Umbral operativo": "Operating threshold",
    "Lectura": "Interpretation",
    "Afinidad": "Affinity",
    "Especificidad": "Specificity",
    "Regla de Egan": "Egan rule",
    "Señal / Valor serializado": "Signal / Serialized value",
    "QED quedó por debajo de 0.5; se conserva como descriptor heurístico, no como veredicto.": "QED fell below 0.5; it remains a heuristic descriptor, not a verdict.",
    "Propósito del informe": "Report purpose",
    "Evidencia o límite observado": "Evidence or observed limitation",
    "No se registraron incertidumbres adicionales a las limitaciones generales del protocolo.": (
        "No additional uncertainties were recorded beyond the protocol's general limitations."
    ),
    "Receptor Biológico (Target)": "Biological target",
    "Señal computacional": "Computational signal",
    "Afinidad reportada por el pipeline": "Affinity reported by the pipeline",
    "Separación entre poses 1 y 2": "Separation between poses 1 and 2",
    "Eficiencia de Ligando (LE)": "Ligand efficiency (LE)",
    "Eficiencia Lipofílica (LLE)": "Lipophilic ligand efficiency (LLE)",
    "Parámetro de Reproducibilidad": "Reproducibility parameter",
    "estructura PDB del receptor": "receptor PDB structure",
    "Tipo de Interacción": "Interaction type",
    "Distancia Mínima": "Minimum distance",
    "Panel computacional de anti-targets": "Computational anti-target panel",
    "sin clasificación": "not classified",
    "Margen computacional no evaluado: faltan afinidades comparables.": "Computational margin not evaluated: comparable affinities are missing.",
    "NO CRUZA UMBRAL": "BELOW THRESHOLD",
    "SIN ESTRUCTURA": "NO STRUCTURE",
    "Regla de referencia": "Reference rule",
    "Coef. Partición (LogP)": "Partition coefficient (LogP)",
    "Área Sup. Polar (TPSA)": "Topological polar surface area (TPSA)",
    "Conteo de Anillos": "Ring count",
    "Alcance de la señal": "Signal scope",
    "Salida individual del modelo; se interpreta por separado de otros descriptores.": (
        "Individual model output; interpreted separately from other descriptors."
    ),
    "La corrida no serializo absorcion intestinal. No se evaluo: eso no dice nada sobre la molecula.": (
        "The run did not serialize intestinal absorption. It was not evaluated; this says nothing about the molecule."
    ),
    "No permeable (SNC-)": "Not permeable (CNS−)",
    "El target requiere acceso al SNC; la salida sigue siendo una predicción binaria.": "The target requires CNS access; the output is still a binary prediction.",
    "Predicción binaria; no determina exposición ni seguridad central.": "Binary prediction; it does not determine central exposure or safety.",
    "Salida no serializada.": "Output not serialized.",
    "Sin alertas CYP serializadas": "No CYP alerts were serialized",
    "Estimación del modelo; no sustituye una medición de solubilidad.": "Model estimate; it does not replace a solubility measurement.",
    "Unión a Proteínas (PPB)": "Plasma protein binding (PPB)",
    "Categoría predicha de unión a proteínas plasmáticas.": "Predicted plasma protein binding category.",
    "Absorción Intestinal (HIA)": "Human intestinal absorption (HIA)",
    "Barrera Hematoencefálica (BBB)": "Blood-brain barrier (BBB)",
    "Solo resume alertas CYP presentes; ausencia de alertas no demuestra ausencia de interacción.": (
        "Summarizes only CYP alerts that are present; no alerts does not demonstrate an absence of interactions."
    ),
    "No se registraron infracciones frente a estas reglas": "No violations of these rules were recorded",
    "Regla de Lipinski (Ro5)": "Lipinski's rule of five (Ro5)",
    "QED (heurístico)": "QED (heuristic)",
    "Regla de Veber": "Veber rule",
    "Regla de Ghose": "Ghose filter",
    "Regla de Muegge": "Muegge rule",
    "SA (heurístico)": "SA (heuristic)",
    "Nota: las afinidades por pose corresponden a la salida cruda de AutoDock Vina. La señal affinity_kcal puede diferir porque la serializa otra etapa del pipeline. Ninguna de las dos equivale por sí sola a una energía libre experimental.": (
        "Note: per-pose affinities are raw AutoDock Vina output. The affinity_kcal signal may differ because another pipeline step serializes it. Neither is, by itself, an experimental free-energy measurement."
    ),
    "Área Superficial Polar (TPSA)": "Topological polar surface area (TPSA)",
    "Donadores de H-Bond": "Hydrogen-bond donors",
    "Aceptores de H-Bond": "Hydrogen-bond acceptors",
    "Conteo de Átomos Pesados": "Heavy atom count",
    "Accesibilidad Sintética (SA)": "Synthetic accessibility (SA)",
    "Regla de Lipinski": "Lipinski's rule of five",
    "SHAP del regresor Model A (residuo de pKi sobre Vina)": "SHAP for Model A regressor (pKi residual over Vina)",
    "SHAP histórico: modelo/objetivo no sellados": "Historical SHAP: model/target not sealed",
    "No se puede atribuir esta explicación a un modelo exacto.": "This explanation cannot be attributed to an exact model.",
    "Contribución (SHAP)": "Contribution (SHAP)",
    "Contexto Fisiológico:": "Physiological context:",
    "Contexto fisiológico no disponible: el receptor no tiene una anotación funcional curada.": "Physiological context unavailable: the receptor has no curated functional annotation.",
    "Contribución a Afinidad (SHAP Value)": "Affinity contribution (SHAP value)",
    "Estas contribuciones no explican el total_score ni la probabilidad del clasificador que entra al ranking.": "These contributions do not explain total_score or the classifier probability used in ranking.",
    "Afinidad normalizada heredada": "Legacy normalized affinity",
    "Salida CL-GNN": "CL-GNN output",
    "Salida XGBoost": "XGBoost output",
    "Familia estructural": "Structural family",
    "Dirección en la salida": "Output direction",
    "Contribución negativa a la salida": "Negative contribution to output",
    "Contribución positiva a la salida": "Positive contribution to output",
    "Esta tabla existe únicamente para compatibilidad y auditoría de registros anteriores. Sus escalas no son comparables entre sí y no alimentan la conclusión operativa de este informe.": (
        "This table exists only for compatibility and to audit earlier records. Its scales are not comparable and do not inform this report's operational conclusion."
    ),
    " (escala histórica 0-100)": " (historical 0–100 scale)",
    "Índice compuesto heredado": "Legacy composite index",
    "Índice de reglas heredado": "Legacy rules index",
    "Índice MPO heredado": "Legacy MPO index",
    "Salida GNN geométrica": "Geometric GNN output",
    "Salida cuántica": "Quantum output",
    "ninguno conservado (la corrida registró una lista vacía)": "none kept (the run recorded an empty list)",
    "la corrida no registró la lista de cofactores": "the run did not record the cofactor list",
    "Limitaciones Cientificas del Analisis Computacional": "Scientific limitations of computational analysis",
    "<font color='#94a3b8' size='7'><i>Generado localmente por MolDesign. Uso no comercial bajo PolyForm Noncommercial 1.0.0; uso comercial sujeto a licencia separada.<br/>Código y plataforma: https://github.com/srcacahuate619/moldesign-app</i></font>": (
        "<font color='#94a3b8' size='7'><i>Generated locally by MolDesign. Noncommercial use under PolyForm Noncommercial 1.0.0; commercial use requires a separate license.<br/>Code and platform: https://github.com/srcacahuate619/moldesign-app</i></font>"
    ),
    "Exendin-P5 (Péptido)": "Exendin-P5 (peptide)",
    "Inhibidor Alostérico 11a": "Allosteric inhibitor 11a",
    "Péptido MYPPPY (B7-1)": "MYPPPY peptide (B7-1)",
    "Inhibidor Alostérico VIII": "Allosteric inhibitor VIII",
    "Ácido Mefenámico": "Mefenamic acid",
    "· <b>Naturaleza computacional:</b> Todas las predicciones presentadas en este documento provienen de modelos computacionales (AutoDock Vina, XGBoost, RDKit). NO constituyen evidencia experimental y DEBEN ser validadas mediante ensayos in vitro e in vivo.": (
        "· <b>Computational nature:</b> All predictions in this document come from computational models (AutoDock Vina, XGBoost, RDKit). They are NOT experimental evidence and MUST be validated with in vitro and in vivo assays."
    ),
    "· <b>Alcance del docking:</b> Las afinidades son valores de una funcion de scoring y sirven para ranking dentro de un protocolo. No constituyen mediciones de energia libre. Las poses son hipotesis estructurales y no representan la flexibilidad completa del receptor ni el solvente explicito.": (
        "· <b>Docking scope:</b> Affinities are values from a scoring function and support ranking within a protocol. They are not free-energy measurements. Poses are structural hypotheses and do not represent the receptor's full flexibility or explicit solvent."
    ),
    "· <b>Limitaciones ADMET:</b> Las predicciones de toxicidad y farmacocinetica provienen de modelos QSAR entrenados en datos historicos. Pueden no generalizar a quimiotipos novedosos. Los falsos negativos en cardiotoxicidad (hERG) y hepatotoxicidad son posibles.": (
        "· <b>ADMET limitations:</b> Toxicity and pharmacokinetic predictions come from QSAR models trained on historical data. They may not generalize to novel chemotypes. False negatives for cardiotoxicity (hERG) and hepatotoxicity are possible."
    ),
    "· <b>PAINS y falsos positivos:</b> Los filtros PAINS cubren ~480 subestructuras conocidas pero no son exhaustivos. Pueden existir otros mecanismos de interferencia en ensayos no cubiertos por estos filtros.": (
        "· <b>PAINS and false positives:</b> PAINS filters cover ~480 known substructures but are not exhaustive. Other interference mechanisms in assays may not be covered by these filters."
    ),
    "· <b>Selectividad:</b> El margen frente a anti-targets no se pudo evaluar. Los scores de Vina entre receptores distintos no son energias libres experimentales comparables. La selectividad in vivo puede diferir debido a metabolitos activos, union a proteinas plasmaticas y efectos de dosis.": (
        "· <b>Selectivity:</b> The margin against anti-targets could not be evaluated. Vina scores from different receptors are not comparable experimental free energies. In vivo selectivity may differ because of active metabolites, plasma protein binding, and dose effects."
    ),
    "· <b>Sintesis:</b> El SA Score es una estimacion heuristica de la dificultad sintetica. No reemplaza el analisis de un quimico medicinal experimentado ni un estudio de retrosintesis completo.": (
        "· <b>Synthesis:</b> The SA Score is a heuristic estimate of synthetic difficulty. It does not replace analysis by an experienced medicinal chemist or a complete retrosynthesis study."
    ),
    "· <b>Reproducibilidad:</b> Este informe registra version del motor, semilla y parser, y los elementos de reconstruccion (caja de búsqueda efectiva, hashes de receptor, entradas y salidas, preparacion del ligando) cuando la corrida los midio. Los campos ausentes quedan marcados y deben completarse antes de comparar corridas. Que un tercero reconstruya la corrida con estos datos no esta demostrado.": (
        "· <b>Reproducibility:</b> This report records the engine version, seed, parser, and reconstruction items (effective search box, receptor hashes, inputs and outputs, ligand preparation) when the run measured them. Missing fields are marked and should be completed before runs are compared. Reconstruction of the run by a third party from these data has not been demonstrated."
    ),
    "<b>Este reporte es una herramienta de apoyo a la investigacion. Las decisiones sobre desarrollo de farmacos deben basarse en evidencia experimental y criterio cientifico profesional.</b>": (
        "<b>This report is a research-support tool. Decisions about drug development should be based on experimental evidence and professional scientific judgment.</b>"
    ),
})

ENGLISH_MESSAGES.update({
    "Sin modelo de poblaciones validado: no se descarta ningún candidato. El canónico de RDKit es una representación reproducible, no el estado dominante.": (
        "No validated population model is available, so no candidate is excluded. The RDKit canonical form is a reproducible representation, not the dominant state."
    ),
    "Meeko 0.7.1; asignación por plantilla, sin pH experimental declarado": (
        "Meeko 0.7.1; template-based assignment, with no experimental pH declared"
    ),
    "más de 15 enlaces rotables": "more than 15 rotatable bonds",
    "MW fuera de 200-600": "MW outside 200-600",
    
    
    
    
    
    "Curado estructuralmente; sin calibrar y sin pipeline de familia": (
        "Structurally curated; calibration and a family pipeline are missing"
    ),
    "faltan Spearman ρ del receptor y stacking calibrado para su familia": (
        "the receptor's Spearman ρ and calibrated stacking for its family are missing"
    ),
    "Acoplamiento": "Docking",
    "Preparación del ligando y análisis": "Ligand preparation and analysis",
    "Preparar el receptor": "Prepare receptor",
    "Validación, propiedades, confórmeros y rescoring.": (
        "Validation, properties, conformers, and rescoring."
    ),
    "Este receptor aún no está preparado en este equipo. Se hace una sola vez: las siguientes corridas contra él se lo saltan.": (
        "This receptor has not been prepared on this computer yet. This happens once: later runs against it skip it."
    ),
})

ENGLISH_MESSAGES.update({
    "NO DEFINIDO": "NOT DEFINED",
    "NO EVALUADO": "NOT EVALUATED",
    "NO DISPONIBLE": "NOT AVAILABLE",
    "NO APLICA": "NOT APPLICABLE",
    "REVISAR": "REVIEW",
    "ABSTENCIÓN": "ABSTENTION",
    "REGISTRADO": "RECORDED",
    "PASA": "PASSED",
    "Receptor declarado": "Declared receptor",
    "Receptor acoplado (unidad preparada)": "Docked receptor (prepared unit)",
    "Ligando introducido": "Input ligand",
    "Poses producidas": "Poses generated",
    "Poses solicitadas": "Poses requested",
    "Poses solicitadas al motor": "Poses requested from the engine",
    "Mejor afinidad Vina observada": "Best observed Vina affinity",
    "Especie acoplada": "Docked species",
    "Exhaustividad": "Exhaustiveness",
    "Semilla aleatoria": "Random seed",
    "Motor ejecutado": "Engine used",
    "CPU solicitadas a Vina": "CPUs requested for Vina",
    "SHA-256 receptor preparado": "Prepared receptor SHA-256",
    "SHA-256 ligando PDBQT": "PDBQT ligand SHA-256",
    "SHA-256 poses SDF": "Pose SDF SHA-256",
    "SHA-256 log": "Log SHA-256",
    "Error declarado": "Declared error",
    "Referencia declarada": "Declared reference",
    "curado": "curated",
    # Los otros cuatro orígenes del receptor (RECEPTOR_ORIGINS en el frontend).
    "privado": "private",
    "comunidad": "community",
    "subido": "uploaded",
    "desconocido": "unknown",
    # Evidencia de un lote: límites y motivos de abstención de las métricas.
    "Completar un acoplamiento no demuestra actividad ni afinidad experimental.":
        "Completing a docking run does not demonstrate activity or experimental affinity.",
    # SCI-A-004: el límite de validez física describe lo que midió la corrida
    # (`cohort/evidence.py::limite_de_validez_fisica`), así que la frase fija que
    # había aquí se retiró con ella: era la que negaba, debajo de su propio
    # recuento de «controles superados», que alguna pose los hubiera superado.
    "Ninguna pose de esta cohorte recibió un veredicto geométrico/físico automático; una afinidad sólo es interpretable después de revisar la pose.":
        "No pose in this cohort received an automatic geometric/physical verdict; an affinity is only interpretable after the pose has been reviewed.",
    "Las poses evaluadas de esta cohorte superaron los controles geométricos y químicos de esta batería; superarlos no demuestra actividad ni afinidad experimental.":
        "The evaluated poses in this cohort passed this suite's geometric and chemical checks; passing them does not demonstrate activity or experimental affinity.",
    "Parte de esta cohorte no superó los controles geométricos/físicos automáticos: el desglose por veredicto está arriba, y una afinidad sólo es interpretable después de revisar la pose.":
        "Part of this cohort did not pass the automatic geometric/physical checks: the breakdown by verdict is above, and an affinity is only interpretable after the pose has been reviewed.",
    "«Requiere revisión» significa que la batería no corrió entera, o que la pose principal pasa y alguna alternativa falla: NO es una pose aprobada. Sólo «controles superados» autoriza llamar válida a una pose.":
        "‘Requires review’ means either the full validation battery did not run or the primary pose passes while an alternative fails: it is NOT an approved pose. Only ‘checks passed’ allows calling a pose valid.",
    "La afinidad Vina observada es una señal de ranking dentro de este protocolo, no una medida de energía libre.":
        "The observed Vina affinity is a ranking signal within this protocol, not a free-energy measurement.",
    "No hay puntuación agregada ni ranking de candidatos: este resumen no ordena moléculas por mérito farmacológico.":
        "There is no aggregate score or candidate ranking: this summary does not order molecules by pharmacological merit.",
    "Las filas `failed` y `not_evaluated` no son evidencia negativa sobre sus moléculas: describen lo que le pasó al motor.":
        "Rows marked `failed` and `not_evaluated` are not negative evidence about their molecules: they describe what happened to the engine.",
    "La corrida todavía no ha terminado. Una métrica sobre una corrida a medias mediría el orden de despacho, no el acoplamiento.":
        "The run has not finished yet. A metric on a half-finished run would measure dispatch order, not docking.",
    "La cohorte no declara etiquetas `active`. Sin etiquetas no hay nada contra lo que medir enriquecimiento.":
        "The cohort declares no `active` labels. Without labels there is nothing to measure enrichment against.",
    "Las únicas moléculas con etiqueta `active` son controles, y los controles no entran en la métrica: no queda población etiquetada contra la que medir enriquecimiento.":
        "The only molecules with an `active` label are controls, and controls are excluded from the metric: no labeled population is left to measure enrichment against.",
    "Ninguna molécula etiquetada tiene afinidad Vina observada.": "No labeled molecule has an observed Vina affinity.",
    "No hay ninguna molécula etiquetada como activa.": "No molecule is labeled as active.",
    "No hay ninguna molécula etiquetada como inactiva.": "No molecule is labeled as inactive.",
    # Rótulos de cada control en el PDF.
    "Protocolo": "Protocol",
    "Procedencia": "Provenance",
    "modelo universal": "universal model",
    "Fit Quality (proxy sobre Vina)": "Fit Quality (Vina proxy)",
})

# Revisión del 2026-10-04: el dossier en inglés dejaba en español el respaldo del receptor (tres de sus cuatro niveles), la cola del veredicto físico
# y el estado «reconocida» de una decisión. Textos exactos de services/targets/calibracion.py y de services/dossier/schemas.py.
ENGLISH_MESSAGES.update({
    'Calibrado para este receptor (Spearman ρ medido)':
        'Calibrated for this receptor (measured Spearman ρ)',
    'Pipeline calibrado por familia; este receptor no está calibrado individualmente':
        'Family-calibrated pipeline; this receptor is not individually calibrated',
    'Sin curar: sin familia estructural conocida':
        'Not curated: no known structural family',
    'falta calibrar Spearman ρ contra afinidades medidas de este receptor':
        'Spearman ρ has not been calibrated against measured affinities for this receptor',
    'faltan Spearman ρ del receptor y stacking calibrado para su familia':
        "the receptor's Spearman ρ and calibrated stacking for its family are missing",
    'falta curar el receptor: familia estructural, preparación y Spearman ρ':
        'the receptor still needs curation: structural family, preparation, and Spearman ρ',
    'Este receptor no tiene Spearman ρ medido: no se ha comprobado que el ranking del motor correlacione con afinidad real para él. El stacking sí está calibrado para su familia estructural, lo que respalda el método pero no este receptor en concreto. Usa el score para ordenar candidatos, no como una predicción de afinidad.':
        "This receptor has no measured Spearman ρ: it has not been checked that the engine's ranking correlates with real affinity for it. Stacking is calibrated for its structural family, which supports the method but not this specific receptor. Use the score to rank candidates, not as an affinity prediction.",
    'Este receptor no está curado: no se le conoce familia estructural ni preparación verificada, y no tiene Spearman ρ. El pipeline corre con el contrato alpha conservador común y sin family-gating. Cualquier score de esta corrida es orientativo; no lo cites como evidencia de afinidad.':
        'This receptor is not curated: its structural family and a verified preparation are unknown, and it has no Spearman ρ. The pipeline runs with the common conservative alpha contract and without family gating. Any score from this run is indicative only; do not cite it as evidence of affinity.',
    'reconocida':
        'acknowledged',
})

# QA-S04: declaración de la semilla congelada por fila.
ENGLISH_MESSAGES.update({'La semilla de esta cohorte histórica no se puede reconstruir. Crea y comprueba una nueva cohorte con semilla positiva.': 'The seed of this historical cohort cannot be reconstructed. Create and check a new cohort with a positive seed.', 'Paquete de evidencia auditada de cohorte': 'Audited cohort evidence package', 'Semilla efectiva por fila': 'Effective seed per row', 'Semilla efectiva': 'Effective seed', 'Origen de la semilla': 'Seed origin', 'semilla no reconstruible': 'seed cannot be reconstructed', 'predeterminada': 'default', 'elegida por el usuario': 'chosen by the user', 'registrada': 'recorded', 'La semilla identifica el protocolo; no garantiza reproducción bit a bit. Todas las filas constan en rows.csv.': 'The seed identifies the protocol; it does not guarantee bitwise reproduction. All rows are included in rows.csv.'})

ENGLISH_MESSAGES.update({"Semilla observada": "Observed seed"})

ENGLISH_MESSAGES.update({"Fila": "Row"})

# Preparación: sólo el corte físico junto al sitio bloquea.
ENGLISH_MESSAGES.update({'Un corte del esqueleto junto al sitio deja una cavidad incompleta o incompatible con el receptor. Un cálculo posterior heredaría el bucle ausente o inventado; reparar o cambiar la estructura es imprescindible.': 'A backbone break near the site leaves an incomplete cavity or one incompatible with the receptor. A later calculation would inherit the missing or invented loop; repairing or changing the structure is essential.', 'Modela o repara el esqueleto en el sitio, o usa otra estructura del mismo receptor. Después vuelve a preparar y evaluar. Revisa también las cadenas laterales ausentes.': 'Model or repair the backbone at the site, or use another structure of the same receptor. Then prepare and evaluate again. Also review missing side chains.', 'Hueco del esqueleto junto al sitio: el sistema está bloqueado hasta reparar o cambiar la estructura.': 'Backbone gap near the site: the system is blocked until the structure is repaired or replaced.'})

ENGLISH_MESSAGES.update({"REMARK 465 no declara los residuos ausentes": "REMARK 465 does not declare missing residues"})

ENGLISH_MESSAGES.update({"tautomero debe ser canonico o entrada": "tautomero must be canonico or entrada"})

ENGLISH_MESSAGES.update({"Un solo tautómero enumerable": "One enumerable tautomer", "Se acopló el tautómero del usuario; la protonación sigue el pH declarado.": "The user's tautomer was docked; protonation follows the declared pH.", "Se acopló el tautómero canónico de RDKit; la protonación sigue el pH declarado.": "The RDKit canonical tautomer was docked; protonation follows the declared pH."})

ENGLISH_MESSAGES.update({"El acta no acredita el cierre de MolDesign en el idioma pedido con un lema válido.": "The record does not confirm the MolDesign outro in the requested language with a valid motto."})

# Moldex guarda evaluaciones (corridas), no moléculas.
ENGLISH_MESSAGES.update({
    "Sólo puede guardarse una evaluación terminada con éxito": "Only an evaluation that finished successfully can be saved",
})

# Carpeta de salida opcional de Molcy y mensajes de vídeo/espacio que habían quedado sin traducción.
ENGLISH_MESSAGES.update({
    "El trabajo no conserva un nombre de vídeo válido.":
        "The job does not keep a valid video name.",
    "El vídeo de este trabajo ya no está en su carpeta de salida.":
        "This job's video is no longer in its output folder.",
    "Molcy detuvo el render porque la unidad del caso o del cierre tiene menos de 1 GiB libre.":
        "Molcy stopped the render because the drive of the case or of the closing sequence has less than 1 GiB free.",
    "La carpeta de salida elegida no es válida.":
        "The chosen output folder is not valid.",
    "La carpeta de salida ya no está autorizada. Elígela de nuevo en Molcy.":
        "The output folder is no longer authorized. Choose it again in Molcy.",
    "La carpeta de salida no es una carpeta ordinaria. Elige otra.":
        "The output folder is not an ordinary folder. Choose another one.",
    "No se pudo leer el registro de carpetas de salida. Elígela de nuevo.":
        "The output folder registry could not be read. Choose the folder again.",
    "El registro de carpetas de salida tiene un formato desconocido.":
        "The output folder registry has an unknown format.",
    "La carpeta de salida de Molcy fue redirigida.":
        "The Molcy output folder was redirected.",
})

# Fotos de Molcy (2026-10-08): la CPU toma fotos y el vídeo es sólo con GPU; sesiones, tomas, marca y procedencia.
ENGLISH_MESSAGES.update({
    "El vídeo se genera sólo con GPU. Con la CPU puedes tomar fotos de la escena.":
        "Video is rendered only on a GPU. With the CPU you can take photos of the scene.",
    "EEVEE no funciona en este equipo y este motor Molcy no sabe tomar fotos: actualiza MolDesign.":
        "EEVEE does not work on this computer and this Molcy engine cannot take photos: update MolDesign.",
    "El vídeo necesita una GPU que funcione con EEVEE. Con la CPU puedes tomar fotos de la escena.":
        "Video needs a GPU that works with EEVEE. With the CPU you can take photos of the scene.",
    "Este motor Molcy no sabe tomar fotos: actualiza MolDesign.":
        "This Molcy engine cannot take photos: update MolDesign.",
    "Cycles no encontró una GPU compatible (CUDA, OptiX, HIP u oneAPI): las fotos se harán con la CPU.":
        "Cycles found no compatible GPU (CUDA, OptiX, HIP or oneAPI): photos will be rendered on the CPU.",
    "La foto se interrumpió al cerrar MolDesign.":
        "The photo was interrupted when MolDesign closed.",
    "Foto cancelada por el usuario.":
        "Photo canceled by the user.",
    "La foto de este trabajo ya no está en su carpeta de salida.":
        "This job's photo is no longer in its output folder.",
    "El acta de la escena no es de este receptor.":
        "The scene record is not for this receptor.",
    "El acta de las tomas no es de esta escena.":
        "The shots record is not for this scene.",
    "El acta nombra un fichero fuera de su carpeta.":
        "The record names a file outside its folder.",
    "El motor no dejó el acta de las tomas.":
        "The engine did not leave the shots record.",
    "La escena no tiene momentos que fotografiar.":
        "The scene has no moments to photograph.",
    "La foto del motor no coincide con su SHA-256.":
        "The engine's photo does not match its SHA-256.",
    "La foto ya no coincide con su SHA-256.":
        "The photo no longer matches its SHA-256.",
    "La imagen ya no coincide con su SHA-256.":
        "The image no longer matches its SHA-256.",
    "Molcy detuvo la foto porque la unidad del caso tiene menos de 1 GiB libre.":
        "Molcy stopped the photo because the case drive has less than 1 GiB free.",
    "Nombre de foto inválido.":
        "Invalid photo name.",
    "Operación de fotos desconocida.":
        "Unknown photo operation.",
    "Resolución u orientación desconocida.":
        "Unknown resolution or orientation.",
    "Sesión de fotos mal pedida.":
        "Malformed photo session request.",
    "Una miniatura no coincide con su SHA-256.":
        "A thumbnail does not match its SHA-256.",
    "pedir() necesita la reserva del trabajo.":
        "The photo request needs the job reservation.",
    "Este trabajo es un vídeo, no una sesión de fotos.":
        "This job is a video, not a photo session.",
    "La escena de esta sesión todavía no está preparada.":
        "This session's scene is not ready yet.",
    "Cycles no encontró una GPU en este equipo.":
        "Cycles found no GPU on this computer.",
    "Sesión de fotos no encontrada.":
        "Photo session not found.",
    "Toma no encontrada.":
        "Shot not found.",
    "Imagen no encontrada.":
        "Image not found.",
    "Clase desconocida.":
        "Unknown class.",
    "Esta sesión todavía no tiene fotos.":
        "This session has no photos yet.",
    "El control de calidad del motor no deja encuadrar esta escena; el acta del caso dice por qué.":
        "The engine's quality control cannot frame this scene; the case record says why.",
    "Cycles no encontró la GPU de este equipo. Toma la foto con la CPU o vuelve a comprobar el renderizador.":
        "Cycles did not find this computer's GPU. Take the photo with the CPU or check the renderer again.",
    "Molcy detuvo la foto porque el espacio libre cayó por debajo de la reserva de 1 GiB.":
        "Molcy stopped the photo because free space fell below the 1 GiB reserve.",
    "La escena preparada cambió desde que se preparó; prepara la escena otra vez.":
        "The prepared scene changed after it was prepared; prepare the scene again.",
    "No se encontró Blender; vuelve a comprobar el renderizador.":
        "Blender was not found; check the renderer again.",
    "La cantidad de hilos sólo se configura con la CPU.":
        "The thread count can only be set for the CPU.",
    "Molcy no puede tomar fotos.":
        "Molcy cannot take photos.",
    "La procedencia de las fotos no se pudo leer.":
        "The photos' provenance could not be read.",
    "El acta de la escena ya no coincide con su SHA-256.":
        "The scene record no longer matches its SHA-256.",
})

# Sección del catálogo (Verificados / Demostración) en el dossier y en Preparación.
ENGLISH_MESSAGES.update({
    'Sección del catálogo': 'Catalog section',
    'Demostración': 'Demo',
    'Receptor preparado automáticamente desde el PDB, sin verificación de pose ni calibración. Sirve para explorar la aplicación, no para decidir qué sintetizar.': 'Receptor prepared automatically from the PDB, without pose verification or calibration. It serves to explore the application, not to decide what to synthesize.',
    'Receptor del usuario: fuera del catálogo incluido; MolDesign no lo ha verificado ni calibrado.': 'User receptor: outside the included catalog; MolDesign has not verified or calibrated it.',
    'La corrida no resolvió el receptor.': 'The run did not resolve the receptor.',
    'Verificado; el sello no describe esta corrida': 'Verified; the seal does not describe this run',
    'El receptor se acopló sin los iones del depósito (la preparación los retira); Vina no tiene término electrostático y la calibración se midió en esas condiciones.': 'The receptor was docked without the deposited ions (preparation removes them); Vina has no electrostatic term and the calibration was measured under these conditions.',
    'El panel es casi entero una serie de análogos: la ρ describe cómo ordena compuestos de esa serie, no ligandos de estructura diversa.': 'The panel is almost entirely one analogue series: ρ describes how it ranks compounds of that series, not structurally diverse ligands.',
    'Ensayo de desplazamiento de [3H]nisoxetina; el pH, la temperatura y la concentración del radioligando no constan en las fuentes consultadas, y la correlación es dentro de un único ensayo.': '[3H]nisoxetine displacement assay; pH, temperature and radioligand concentration are not documented in the sources consulted, and the correlation is within a single assay.',
    'Las cadenas del sitio anotado no están todas en la unidad biológica del depósito: el sitio podría ser un contacto del cristal. Pendiente de reanotar.': 'The chains of the annotated site are not all in the deposited biological assembly: the site could be a crystal contact. Pending re-annotation.',
})

# Especie acoplada: frases completas, también en revisión (2026-10-09).
ENGLISH_MESSAGES.update({
    'En revisión por dos centros básicos a 3 enlaces o menos (piperazina o diamina): la tabla da a cada uno el pKa de su clase por separado, pero protonar uno baja el del otro (cetirizina, pKa 7,98, es zwitterión neutro y se acoplaba como catión).': "Under review because of two basic centers 3 bonds apart or fewer (piperazine or diamine): the table gives each one its class pKa separately, but protonating one lowers the other's (cetirizine, pKa 7.98, is a neutral zwitterion and was docked as a cation).",
    'En revisión por N-sulfonil-piperazina: el sulfonilo baja el pKa del N distal muy por debajo del 9,8 de una amina alifática (sildenafilo 6,78: neutro a pH 7,4, se acoplaba como catión).': 'Under review because of N-sulfonyl piperazine: the sulfonyl group lowers the pKa of the distal N far below the 9.8 of an aliphatic amine (sildenafil 6.78: neutral at pH 7.4, was docked as a cation).',
    'En revisión por ácido enólico vinílogo (oxicam o 4-hidroxicumarina): la tabla de pKa no tiene esta clase y la especie a pH 7,4 no está establecida (piroxicam, pKa ácido ≈5,3, con fuentes que discrepan).': 'Under review because of vinylogous enolic acid (oxicam or 4-hydroxycoumarin): the pKa table lacks this class and the species at pH 7.4 is not established (piroxicam, acidic pKa ≈5.3, with conflicting sources).',
    'En revisión por amina protonada con un grupo atractor a uno o dos enlaces del N (CF3 o CHF2 en β, nitrilo en α o β): el grupo baja varias unidades el pKa que la tabla da a la clase (9,8); la 2,2,2-trifluoroetilamina tiene pKa ≈5,7 y el 3-aminopropionitrilo ≈7,8, así que la carga a pH 7,4 es una decisión abierta.': 'Under review because of protonated amine with an electron-withdrawing group one or two bonds from the N (CF3 or CHF2 at β, nitrile at α or β): the group lowers the class pKa the table assigns (9.8) by several units; 2,2,2-trifluoroethylamine has pKa ≈5.7 and 3-aminopropionitrile ≈7.8, so the charge at pH 7.4 is an open decision.',
    'La selección es reproducible, pero la población de esta clase no la resuelve la tabla de pKa por clases.': 'The selection is reproducible, but the class-based pKa table does not resolve the population of this class.',
    'La selección es reproducible, pero la población del microestado no quedó establecida por una constante química verificada.': 'The selection is reproducible, but the microstate population was not established by a verified chemical constant.',
})
# Preparación: cofactor declarado ligando del cristal y tautómero cambiado (2026-10-10).
ENGLISH_MESSAGES.update({
    'El receptor que se entregaría no contiene especies que estaban en el sitio. Hay que decidir sobre ellas antes de cualquier cálculo posterior. El ligando se une junto a ese cofactor y no lo desplaza: el sitio acoplado quedó sin él.': 'The receptor to be transferred does not contain species that were in the site. Decide how to handle them before any later calculation. The ligand binds next to that cofactor and does not displace it: the docked site lost it.',
    'Usa otra estructura del mismo receptor en la que el cofactor no sea el ligando del cristal, o súbela como receptor propio ya preparado, con el cofactor dentro. Después vuelve a evaluar.': 'Use another structure of the same receptor in which the cofactor is not the crystal ligand, or upload it as your own already-prepared receptor with the cofactor included. Then evaluate again.',
    'El ligando del cristal no toca ninguno (ni un N, O o S a 2,8 Å de un metal ni un átomo a 4 Å de un cofactor).': 'The crystal ligand touches none of them (no N, O or S within 2.8 Å of a metal and no atom within 4 Å of a cofactor).',
    'Sin ligando del cristal no se puede ver si el ligando los toca.': 'Without a crystal ligand, it cannot be seen whether the ligand touches them.',
    'El receptor no contiene especies que estaban cerca del sitio, pero el ligando del cristal no las toca. Si sólo ocupan la segunda esfera, retirarlas puede ser aceptable; decide y justifícalo antes de un cálculo posterior.': 'The receptor lacks species that were near the site, but the crystal ligand does not touch them. If they only occupy the second shell, removing them may be acceptable; decide and justify it before any downstream calculation.',
    'Si la especie es estructural o catalítica para este ligando, vuelve a evaluar con ella en la lista de cofactores del receptor; si no, registra por qué se retira.': 'If the species is structural or catalytic for this ligand, re-run the evaluation with it in the receptor cofactor list; otherwise, record why it is removed.',
    'El ligando del cristal coordina un metal que el receptor conserva. Vina no tiene término de coordinación: la pose no la reproduce y un cálculo posterior necesita parámetros para ese enlace.': 'The crystal ligand coordinates a metal that the receptor keeps. Vina has no coordination term: the pose does not reproduce it, and a downstream calculation needs parameters for that bond.',
    'Retirarlo es correcto si el ligando compite con él por el sitio, como un inhibidor competitivo con ATP, SAM o NAD. Si el ligando se une a su lado, el sitio acoplado quedó incompleto.': 'Removing it is correct if the ligand competes with it for the site, as an ATP-, SAM- or NAD-competitive inhibitor does. If the ligand binds next to it, the docked site is incomplete.',
    'Se acopló el tautómero canónico de RDKit, que no es el de la entrada.': 'The RDKit canonical tautomer was docked, and it is not the input tautomer.',
    'El canónico es una representación reproducible, no una predicción del tautómero dominante.': 'The canonical tautomer is a reproducible representation, not a prediction of the dominant tautomer.',
    'Si el tautómero que escribiste es el correcto, vuelve a evaluar con «Tautómero del ligando: Por defecto (conservar el tautómero que escribí)» en las opciones avanzadas.': 'If the tautomer you entered is the correct one, evaluate again with “Ligand tautomer: Default (keep the tautomer I entered)” in the advanced options.',
})
# Preparación: tautómeros con población despreciable (2026-10-10).
ENGLISH_MESSAGES.update({
    'amida o hidroxamato como ácido imídico (iminol)': 'amide or hydroxamate as an imidic acid (iminol)',
    'enol de un carbonilo sin conjugar': 'enol of an unconjugated carbonyl',
    'hidroxiazina en vez de su forma oxo': 'hydroxyazine instead of its oxo form',
    'imina exocíclica en vez de la amina aromática': 'exocyclic imine instead of the aromatic amine',
    'nitroso en vez de oxima o hidroxamato': 'nitroso instead of oxime or hydroxamate',
    'pierde aromaticidad': 'loses aromaticity',
    'El tautómero acoplado tiene una población despreciable en agua: un cálculo de energía libre partiría de una especie que casi no existe.': 'The docked tautomer has a negligible population in water: a free-energy calculation would start from a species that barely exists.',
    'Vuelve a evaluar con «Tautómero del ligando: Por defecto (conservar el tautómero que escribí)»: el tautómero que escribiste es la forma mayoritaria.': 'Evaluate again with “Ligand tautomer: Default (keep the tautomer I entered)”: the tautomer you entered is the major form.',
})
# Preparación medida desde el ligando (2026-10-10).
ENGLISH_MESSAGES.update({
    'Recorte del receptor': 'Receptor crop',
    'Puentes disulfuro': 'Disulfide bridges',
    'Conformaciones alternativas': 'Alternate conformations',
    'Referencia de las distancias': 'Distance reference',
    # Las filas de especies del sitio del PDF son las de la auditoría de Preparación (2026-10-22).
    'Metales y cofactores junto al sitio': 'Metals and cofactors near the site',
    'Aguas junto al sitio': 'Waters near the site',
    'Otras especies junto al sitio': 'Other species near the site',
    'Registros HETATM retirados del ensamblaje': 'HETATM records removed from the assembly',
    'Especies conservadas como otro residuo (Å a la caja)': 'Species kept as another residue (Å to the box)',
    'Pose top-1': 'Top-1 pose',
    'Ninguno en las cadenas del receptor': 'None in the receptor chains',
    'El recorte sirve para Vina, pero el receptor que se entregaría no es la proteína: un cálculo con disolvente explícito tiene que partir de las cadenas enteras de la estructura de origen.': 'The crop works for Vina, but the receptor to be transferred is not the protein: an explicit-solvent calculation must start from the full chains of the source structure.',
    'Meeko aplicó la plantilla de tiol libre (CYS) a una cisteína del puente porque su pareja quedó fuera del receptor: el receptor tiene un SH donde la estructura tiene un enlace S–S.': 'Meeko applied the free-thiol template (CYS) to a bridge cysteine because its partner was left outside the receptor: the receptor has an SH where the structure has an S–S bond.',
    'La preparación no registró la plantilla de una o de las dos cisteínas del puente, así que no se puede saber si el receptor conserva el enlace S–S o tiene un tiol libre.': 'The preparation did not record the template of one or both bridge cysteines, so it cannot be known whether the receptor keeps the S–S bond or has a free thiol.',
    'La preparación usó en cada residuo la conformación de mayor ocupación sumada y, si empatan, la primera por letra (A antes que B), sin mirar el ligando; la otra puede cambiar el contacto con el ligando.': 'For each residue, preparation used the conformation with the highest summed occupancy and, on a tie, the first by letter (A before B), without looking at the ligand; the other may change the contact with the ligand.',
    'La tabla de pKa por clases elige una forma, pero las dos están pobladas: un cálculo de energía libre tiene que considerar las dos o fijar una con evidencia.': 'The class-based pKa table picks one form, but both are populated: a free-energy calculation has to consider both or fix one with evidence.',
    'La corrida no conserva la pose principal: las distancias se miden desde la caja.': 'The run does not keep the primary pose: distances are measured from the box.',
    'No se pudieron medir las distancias al ligando: las distancias se miden desde la caja.': 'Distances to the ligand could not be measured: distances are measured from the box.',
    'El escrito en el archivo': 'The one written in the file',
    'Canónico de RDKit': 'RDKit canonical',
    # Preparación: por qué no se puede usar el archivo depositado (contexto_estructural.origen_comprobado).
    'La corrida no registró la receta del receptor o la caja': 'The run did not record the receptor recipe or the box',
    'No se encontró el archivo de origen del receptor': 'The receptor source file was not found',
    'El archivo de origen no es el que preparó el receptor de esta corrida (la receta no coincide)': 'The source file is not the one that prepared this run\'s receptor (the recipe does not match)',
    'No se pudo comprobar la estructura de origen del receptor': 'The receptor source structure could not be verified',
    'No se encontró el perfil del receptor propio con el que se preparó esta corrida': 'The profile of the uploaded receptor this run was prepared with was not found',
    'La estructura de origen ya no corresponde al PDBQT de esta corrida': 'The source structure no longer matches the PDBQT of this run',
    'auditoría de preparación: qué bloquea, qué revisar y qué se decidió': 'preparation audit: what blocks, what to review and what was decided',
    # Preparación: unión covalente, membrana y cobertura del campo de fuerzas.
    'Unión covalente': 'Covalent binding',
    'Cobertura del campo de fuerzas del ligando': 'Ligand force-field coverage',
    'Cobertura del campo de fuerzas del receptor': 'Receptor force-field coverage',
    'Proteína de membrana': 'Membrane protein',
    'acrilamida (aceptor de Michael)': 'acrylamide (Michael acceptor)',
    'acrilato (aceptor de Michael)': 'acrylate (Michael acceptor)',
    'alquinamida (aceptor de Michael)': 'alkynamide (Michael acceptor)',
    'vinilsulfona o vinilsulfonamida (aceptor de Michael)': 'vinyl sulfone or vinyl sulfonamide (Michael acceptor)',
    'haloacetamida': 'haloacetamide',
    'α-halocetona': 'α-haloketone',
    'epóxido': 'epoxide',
    'aziridina': 'aziridine',
    'aldehído': 'aldehyde',
    'ácido o éster borónico': 'boronic acid or ester',
    'α-aminonitrilo (ojiva reversible)': 'α-aminonitrile (reversible warhead)',
    'cianamida': 'cyanamide',
    'β-lactama': 'β-lactam',
    'β-lactona': 'β-lactone',
    'fluoruro de sulfonilo': 'sulfonyl fluoride',
    'fluorofosfonato': 'fluorophosphonate',
    'α-cetoamida (ojiva reversible)': 'α-ketoamide (reversible warhead)',
    'isotiocianato': 'isothiocyanate',
    'Vina acopla el complejo no covalente. Un cálculo de energía libre del inhibidor unido necesita el aducto, con parámetros para el enlace, o un protocolo covalente; el del complejo no covalente describe sólo el paso reversible.': 'Vina docks the non-covalent complex. A free-energy calculation of the bound inhibitor needs the adduct, with parameters for the bond, or a covalent protocol; one of the non-covalent complex describes only the reversible step.',
    'Declara qué estado describe el cálculo: el complejo no covalente previo o el aducto.': 'Declare which state the calculation describes: the preceding non-covalent complex or the adduct.',
    'Ninguna ojiva covalente conocida': 'No known covalent warhead',
    'El depósito no une el ligando del cristal a la proteína.': 'The deposition does not bond the crystal ligand to the protein.',
    'No se consultaron los enlaces del depósito.': 'The deposition links were not consulted.',
    'El ligando es un radical: los campos de fuerzas de uso común no tienen tipos de átomo para electrones desapareados.': 'The ligand is a radical: common force fields have no atom types for unpaired electrons.',
    'Declara qué campo de fuerzas cubre estos elementos o con qué parámetros propios se describen.': 'Declare which force field covers these elements or which custom parameters describe them.',
    'Es cobertura por elemento: tipos de átomo y cargas se asignan al parametrizar.': 'This is coverage by element: atom types and charges are assigned during parametrization.',
    'El receptor de la corrida no se pudo leer por su SHA-256.': 'The run receptor could not be read by its SHA-256.',
    'Sólo aminoácidos estándar': 'Standard amino acids only',
    'Los 20 aminoácidos y sus estados de protonación están en los campos de proteína de uso común (AMBER ff14SB y ff19SB, CHARMM36m, OPLS).': 'The 20 amino acids and their protonation states are in common protein force fields (AMBER ff14SB and ff19SB, CHARMM36m, OPLS).',
    'metal: necesita parámetros de ion o un modelo enlazado': 'metal: needs ion parameters or a bonded model',
    'cofactor: necesita parámetros propios': 'cofactor: needs custom parameters',
    'fosforresiduo: necesita parámetros adicionales': 'phosphorylated residue: needs additional parameters',
    'residuo no estándar: necesita parámetros propios': 'non-standard residue: needs custom parameters',
    'Un campo de proteína estándar no los cubre: el cálculo siguiente tiene que parametrizarlos aparte y declararlo.': 'A standard protein force field does not cover them: the next calculation has to parametrize them separately and declare it.',
    'Declara con qué parámetros se describe cada uno, o retíralo si no forma parte de la hipótesis.': 'Declare which parameters describe each one, or remove it if it is not part of the hypothesis.',
    'Sin el archivo depositado, comprobado por la receta del receptor, no se mide su secuencia.': 'Without the deposited file, verified by the receptor recipe, its sequence is not measured.',
    'El depósito la clasifica como «MEMBRANE PROTEIN».': 'The deposition classifies it as “MEMBRANE PROTEIN”.',
    'El receptor que se entrega no lleva bicapa: un cálculo con disolvente explícito tiene que insertarlo en una membrana y declarar su composición y orientación.': 'The receptor being transferred has no bilayer: an explicit-solvent calculation has to insert it into a membrane and declare its composition and orientation.',
    'Declara la membrana del sistema (composición y orientación) o por qué el cálculo no la necesita.': 'Declare the system membrane (composition and orientation) or why the calculation does not need one.',
    'Sin indicios de proteína de membrana multipaso': 'No evidence of a multi-pass membrane protein',
    'No detecta barriles β ni proteínas monotópicas o de un solo paso.': 'It does not detect β-barrels or monotopic or single-pass proteins.',
    'Todos los requisitos tienen dato registrado o una decisión justificada, pero la transferencia a un cálculo FEP no está demostrada: FEP-06 sigue sin sellar.': 'Every requirement has recorded data or a justified decision, but transfer to an FEP calculation has not been demonstrated: FEP-06 is still unsealed.',
    # Preparación: revisión rutinaria y revisión del caso (2026-10-11).
    'La pide toda corrida con un receptor que ya trae su protonación: la decisión es de quien lo preparó.': 'Every run with a receptor that already carries its protonation requests it: the decision belongs to whoever prepared it.',
    'La pide toda corrida con un receptor de varias cadenas: Vina recibe siempre un bolsillo recortado.': 'Every run with a multi-chain receptor requests it: Vina always receives a cropped pocket.',
    'La pide toda corrida contra un receptor del catálogo de demostración.': 'Every run against a Demo catalog receptor requests it.',
    'La pide toda corrida del instalador o de un árbol con cambios sin commitear, que no declaran commit. La versión de la aplicación queda en «Versiones de la corrida».': 'Every run from the installer, or from a tree with uncommitted changes, requests it: neither declares a commit. The app version is recorded under “Run versions”.',
    'Son advertencias de la ruta o que esta auditoría vuelve a medir junto al ligando: receptor sin calibrar, especies retiradas de la estructura y protonación del receptor.': 'These warnings come from the route, or this audit measures them again next to the ligand: uncalibrated receptor, species removed from the structure and receptor protonation.',
    'La comprobación previa deja estos controles sin evaluar en toda corrida, como deuda declarada, o antes de preparar el receptor por primera vez.': 'The pre-check leaves these controls unevaluated in every run, as a declared debt, or before the receptor is prepared for the first time.',
    'La plantilla eligió su estado sin mirar el sitio: HID, HIE o HIP cambian los puentes de hidrógeno que forma con el ligando.': 'The template chose its state without looking at the site: HID, HIE or HIP change the hydrogen bonds it forms with the ligand.',
    'Nada propio de este caso pide revisión: sólo quedan las revisiones que esta ruta pide en toda corrida. Aun resueltas, la transferencia a un cálculo FEP no está demostrada: FEP-06 sigue sin sellar.': 'Nothing specific to this case needs review: only the reviews this route requests for every run remain. Even once resolved, transfer to an FEP calculation has not been demonstrated: FEP-06 is still unsealed.',
})
ENGLISH_MESSAGES.update({
    "Ese estado no existe: el nitrógeno unido al metal no lleva hidrógeno, y la plantilla que corresponde lo "
    "pone en el otro nitrógeno del anillo.":
        "That state does not exist: the nitrogen bound to the metal carries no hydrogen, and the correct template "
        "puts it on the other ring nitrogen.",
    "Antes de un cálculo posterior, protona esa His con el hidrógeno en el otro nitrógeno del anillo (HID si "
    "coordina por NE2, HIE si coordina por ND1) y súbela como receptor ya preparado, o retira el metal si no "
    "forma parte de la hipótesis.":
        "Before a downstream calculation, protonate that His with the hydrogen on the other ring nitrogen (HID if "
        "it coordinates through NE2, HIE if through ND1) and upload it as an already prepared receptor, or remove "
        "the metal if it is not part of the hypothesis.",
    "Constructo cristalizado": "Crystallized construct",
    "Ocupación cero en el depósito": "Zero occupancy in the deposit",
    "Sin diferencias SEQADV fuera de etiquetas de expresión.": "No SEQADV differences beyond expression tags.",
    "Sin diferencias declaradas con la secuencia de referencia, aparte de etiquetas de expresión":
        "No declared differences from the reference sequence, apart from expression tags",
    "Ninguna en las cadenas del receptor": "None in the receptor chains",
    "Fuera del margen no impiden la corrida, pero el receptor que se entregaría no los contiene. Declarar si importan "
    "para el cálculo siguiente. «X→ALA» o «X→GLY»: el depósito no resolvía la cadena lateral de X, se truncó y después "
    "Meeko retiró el residuo.":
        "Outside the site margin, they do not block the run, but the receptor to be transferred does not contain them. "
        "Declare whether they matter for the next calculation. “X→ALA” or “X→GLY”: the deposit did not resolve the "
        "side chain of X, it was truncated and Meeko then removed the residue.",
    "Una cisteína que coordina un metal es un tiolato: la plantilla le puso el hidrógeno sin mirar el metal.":
        "A cysteine that coordinates a metal is a thiolate: the template added the hydrogen without looking at the "
        "metal.",
    "Antes de un cálculo posterior, desprotona esa Cys (tiolato, CYM) y parametriza su enlace con el metal, y "
    "súbela como receptor ya preparado, o retira el metal si no forma parte de la hipótesis.":
        "Before a downstream calculation, deprotonate that Cys (thiolate, CYM), parametrize its bond to the metal "
        "and upload it as an already prepared receptor, or remove the metal if it is not part of the hypothesis.",
})
# Molcy: recetas visuales y la ilustración fluida (escena Ensamble).
ENGLISH_MESSAGES.update({
    "El acta no acredita la receta visual solicitada.": "The record does not confirm the requested visual recipe.",
    "La escena preparada no acredita la receta visual solicitada.": "The prepared scene does not confirm the requested visual recipe.",
    "La ilustración fluida sólo corresponde a la escena Ensamble.": "The fluid illustration only applies to the Ensemble scene.",
    "La conformación elegida no conserva un rig torsional verificable con ejes elegibles.":
        "The chosen conformation does not keep a verifiable torsional rig with eligible axes.",
})
# Preparación: la «fuente» de cada requisito cuando no es un campo del código. Con la interfaz en inglés salían en
# castellano («source: secuencia del receptor · HEADER del depósito»); lo vio la grabación del vídeo (2026-10-25).
ENGLISH_MESSAGES.update({
    "receptor PDBQT de la corrida · services/docking/preparer_multichain.radio_para_caja":
        "the run's receptor PDBQT · services/docking/preparer_multichain.radio_para_caja",
    "estructura de origen · informe de la preparación (protonation_templates)":
        "source structure · preparation report (protonation_templates)",
    "estructura de origen (altloc y ocupación)": "source structure (altloc and occupancy)",
    "estructura de origen (SEQADV · REMARK 999)": "source structure (SEQADV · REMARK 999)",
    "estructura de origen (REMARK 475 · REMARK 480)": "source structure (REMARK 475 · REMARK 480)",
    "structural_evidence (PoseBusters con hidrógenos reconstruidos desde el SMILES; condición MF-33-H-COR)":
        "structural_evidence (PoseBusters with hydrogens rebuilt from the SMILES; condition MF-33-H-COR)",
    "no aplica a una corrida": "not applicable to a single run",
    "pose top-1 · estructura de origen comprobada por la receta del receptor":
        "top-1 pose · source structure checked against the receptor recipe",
    "huellas de la corrida y del preflight": "run and preflight fingerprints",
    "ligand_state.smiles_acoplado · LINK del depósito": "ligand_state.smiles_acoplado · LINK records of the deposit",
    "PDBQT del receptor (por su SHA-256)": "receptor PDBQT (by its SHA-256)",
    "secuencia del receptor · HEADER del depósito": "receptor sequence · HEADER of the deposit",
    "catálogo · services/targets/seccion_catalogo.py": "catalog · services/targets/seccion_catalogo.py",
    # encabezado de cada página del PDF del dossier (services/dossier/pdf.py): «caso · corrida <id>»
    "corrida": "run",
})
# Receptores propios: subida, modos de preparación y su auditoría.
from core.i18n_receptores_propios import MENSAJES as _MENSAJES_RECEPTORES_PROPIOS  # noqa: E402

ENGLISH_MESSAGES.update(_MENSAJES_RECEPTORES_PROPIOS)
