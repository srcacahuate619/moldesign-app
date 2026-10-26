# Glosario español → inglés de la interfaz

Criterio de redacción del inglés de MolDesign. **No es exhaustivo**: recoge lo decidido y lo que ya está en
los diccionarios (`frontend/context/traducciones/*.ts` y `LanguageContext.tsx`). Cuando se decida un término
nuevo, se añade aquí en el mismo commit que lo usa.

Decidido por el propietario el 2026-10-04: el inglés es **americano**, y la única traducción del inglés es la de
Claude, sin revisión externa; por eso este glosario y las guardias que lo vigilan existen.

## Ortografía

Americana: *center, color, catalog, license, analyze, minimize, optimization, canceled, labeled, judgment,
toward, artifact, sulfur, hemato-*. Lo vigila `frontend/lib/__tests__/inglesAmericano.test.ts`, que también
rechaza caracteres propios del español en un texto inglés. «Cancellation» conserva la doble «l» en inglés
americano.

## Términos

| Español | Inglés | Nota |
|---|---|---|
| Caja de búsqueda | Search box | Nunca «grid box», «docking box» ni «working box». La caja de búsqueda efectiva es la que se ejecutó. |
| Comprobación previa (preflight) | Preflight check | Revisión anterior a ejecutar el motor. |
| Metaloenzima | Metalloenzyme | En inglés lleva doble «l». |
| Motivo del fallback | Fallback reason | Explica por qué se usó el modelo universal cuando no había uno de familia validado. |
| Parámetros de la evaluación | Evaluation parameters | Diálogo del motor, la caja de búsqueda y los recursos de una evaluación. «Opciones» / «Options» es sólo el menú de la cabecera. |
| Parámetros avanzados | Advanced parameters | Sección del diálogo anterior. |
| Motor externo (API) | External engine (API) | Motor de docking de un tercero, conectado por API. En esta versión sólo hay plaza: no se conecta ni envía datos. Ver `docs/96_DISENO_MOTOR_EXTERNO_VIA_API.md`. |
| Vía API | Via API | Nombre de la plaza del motor externo en el menú de docking. |
| Exhaustividad | Exhaustiveness | Parámetro de Vina. |
| Semilla | Seed | |
| hotspots | hotspots | Una sola palabra en ambos idiomas; singular hotspot. |
| Pose | Pose | Singular «pose», plural «poses»; en español «1 pose», «9 poses». |
| Acoplamiento (docking) | Docking | Sin traducir; es el término del campo. |
| Receptor, ligando | Receptor, ligand | |
| Corrida | Run | |
| Cohorte | Cohort | |
| Caso | Case | Unidad de procedencia y de transferencia. |
| Disposición científica | Scientific disposition | Decide qué se puede afirmar a partir de una corrida. |
| Aceptar evidencia | Accept the evidence | Acción de disposición. |
| Aceptar con límites | Accept with limits | Acción de disposición que conserva sus salvedades. |
| Abstenerse | Abstain | No se formula una conclusión a partir de la corrida. |
| Evaluación / Informe | Evaluation / Report | Las dos vistas disponibles de un caso. |
| Cancelada | Canceled | |
| Completada | Completed | |
| Duplicado reutilizado | Reused duplicate | |
| No evaluada | Not evaluated | No es evidencia negativa sobre la molécula. |
| Referencia / Positivo / Negativo | Reference / Positive / Negative | Roles de control de una cohorte. |
| Afinidad Vina observada | Observed Vina affinity | Es una señal de ranking dentro de un protocolo, no energía libre. |

## Lo que no se traduce

Nombres de motores y programas (AutoDock Vina, ESMFold, Open Babel, RDKit, Meeko), siglas (PDB, SMILES, ADMET)
y la palabra «MolDesign» (el producto se llama así a secas, sin «AI»).
