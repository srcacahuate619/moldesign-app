# Fase 4 — bitácora de corrección local

Fecha: 2026-09-24/25 (America/Mexico_City). Auditoría base: `ae4db6a7aef0f4c14af7b74da350578abbd80074`.

## Rama y alcance

- Rama `codex/audit-phase-4`; worktree `D:\moldesign-build\.worktrees\audit-phase-4`.
- Padre local de fase 3: `33204b062313c2aa8ae40e70eff0e3b5dba4c0fe`.
- Commit local de fase 4: `2d0233cc7cb376ff5bc54973eca84cb0dba4a86b`. Árbol limpio al cerrar. No hubo `push` ni integración a `main`.
- Se usó el Python embebido y Vina 1.2.7 de `D:\moldesign-build`; los temporales y cachés se dirigieron al worktree de D mediante `TEMP`, `TMP`, `TMPDIR`, `XDG_CACHE_HOME` y `MPLCONFIGDIR`. No se generaron temporales deliberados en C. La prueba E2E fue en Windows, la plataforma que se distribuye; no hizo falta recurrir al servidor Ubuntu.

## Cambios, evidencia y razones

### 4.1 — PROV-010: procedencia de la ejecución

`docking_protocol/v2` conserva en el snapshot la caja **efectiva**, CPU solicitadas, versión de aplicación, versiones de Vina/Meeko/RDKit/dimorphite, SHA-256 del conformero SDF, PDBQT de entrada, poses SDF, log y receptor preparado, y la receta de preparación disponible (hash, cadenas, whitelist y detalles del informe Meeko). Se registran también las rutas lógicas de los archivos de entrada y del log para transferir sus bytes. Cuando una corrida antigua o una preparación no proporciona un dato, se deja ausente; no se reconstruye desde la petición del cliente. `git_commit` sólo se declara si lo proporciona un build de forma explícita o el árbol Git está limpio; un HEAD con cambios sin commitear sería una atribución falsa.

El dossier toma la caja y esos parámetros del snapshot. El ZIP incorpora SDF/PDBQT de entrada, receptor, poses y log únicamente si los bytes conservados coinciden con el SHA declarado; un archivo mutable alterado queda `NO_DISPONIBLE`. La primera ejecución E2E detectó una discrepancia real: el log se hasheaba antes de escribirlo con `write_text`, que modificaba sus bytes. Se cambió el hash para medir el objeto persistido y se repitió el gate con éxito. El golden E2E `backend/tests/goldens/e2e_vina_3f75.json` tiene SHA-256 `10bea1636805240759d2b2e24045363c513c72e1a03eefe0f0ddfeb762b610d2`.

### 4.2 — PROV-007/008/009: evidencia posterior y sellos

El esquema SQLite sube de 26 a 27 con `evaluation_run_addenda`. Cada addendum se enlaza a `molecule_id` y `task_id`, se codifica en JSON canónico y guarda SHA-256. La lectura verifica ese hash y aplica una copia al snapshot original, que permanece inmutable. Selectividad, informe IA y certificado escriben addenda; un escritor tardío sólo actualiza la proyección si todavía pertenece a su `task_id`. Los upserts parciales distinguen campo omitido de limpieza explícita: un informe IA ya no borra `is_control` ni `error_message` ni mueve `evaluated_at`.

Al iniciar una reevaluación se conservan `blockchain_tx_id`, `blockchain_hash`, `certified_task_id` y `certified_total_score`; el sello puede seguir visible como perteneciente a la corrida anterior. Las pruebas cubren la materialización después de otra corrida, la idempotencia del informe, un hash de addendum alterado, el sello preservado y la advertencia `MMGBSA_TIMEOUT` sin fabricar score.

**Límite actual:** MM-GBSA sigue rechazado en el ejecutor activo por la parametrización científica inconsistente establecida en fases anteriores. No se afirma que haya una ruta MM-GBSA operativa ni que el timeout se haya provocado experimentalmente. El formato de addendum y el aviso quedan definidos para evidencia tardía de esa clase.

### 4.3 — PROV-011: péptidos

Las dos rutas peptídicas escriben poses bajo un nombre nuevo por ejecución, con digest del `task_id` y UUID. Dos corridas y un reintento no reutilizan ni sobrescriben el SDF. La procedencia guarda el SHA de poses cuando existe. Las corridas anteriores no se reescriben.

### 4.4 — PROV-019/020: verificador y contrato

El verificador exige `sha256` hexadecimal y tamaño entero no negativo para **todo** artefacto `REGISTRADO`; compara ambos con los bytes del ZIP. Una prueba modifica metadatos del manifiesto y actualiza `checksums.sha256`: el paquete sigue siendo rechazado por la incongruencia interna. Se actualizaron `docs/56_DOSSIER_REPRODUCIBLE_CONTRACT.md` y la receta del ZIP para describir evidencia estructural, conformeros, entradas exactas, log y estados realmente persistidos.

### 4.5 — PROV-004: caminos normal y PRO

La petición sin `pipeline_config` construye explícitamente el perfil normal y entra al mismo `run_pipeline` que PRO. Conserva su presupuesto histórico de Vina (exhaustiveness 8, cinco poses) y usa las mismas etapas científicas y advertencias; PRO mantiene su perfil (nueve poses en el caso E2E). El rescoring recibe la familia estructural también en PRO. El antiguo cuerpo legacy permanece en el archivo como código inalcanzable tras el retorno delegado; retirarlo requeriría adaptar más guardianes estáticos y no cambia el ejecutor usado. La convergencia **de ejecución** se demostró con ambos contratos reales y persistidos.

### 4.6 — PROV-013/014/015: sellos y goldens

`validar_sellos.py` separa `MANTENIDO` y `MANTENIDO_EN_COPIA` de `VERIFICADO`, y verifica el SHA de PDB `.gz` **después de descomprimir**. La whitelist `NO_CONSERVADO` de `scripts/sellos_no_distribuidos.json` se redujo a los cuatro PDB realmente ausentes. Los 107 restantes pasan como `VERIFICADO_GZ`. Se regeneró el índice público del registro y se corrigió su texto: el hash mantenido no certifica el código productor original.

`PREP-01` selló una versión de `preparer.py` que cambió en fase 1. Se recuperaron los bytes exactos re-sellados del commit local `94c21b8` y se guardaron en `scripts/historical_sources/PREP-01/preparer.py` (52 721 bytes; SHA-256 `80e851dc6100dba305de1d0fa660dca5c821db717f2c1984d5eb3490729c5ae4`). Se declaró la divergencia en la tabla; no se editaron archivos de `scripts/artifacts_science/`. Los bytes **anteriores al mantenimiento** no se recuperaron y no se presentan como verificados. La copia histórica contiene una línea con espacio final: se conservó tal cual para no alterar su hash; el chequeo de whitespace del resto del commit pasa.

El golden M5 de replay ya no finge AUC reconstruidas cuando faltan tres checkpoints no redistribuidos: declara sus rutas, hashes y AUC de referencia con estado `NO_DISTRIBUIDO`. `generate_goldens.py --verify-m5-replay` ejecuta el replay real sólo con esos archivos y primero valida sus hashes. El gate E2E de Vina ahora compara el golden de PRO y normal, reinicia el backend, relee SQLite y comprueba los bytes exactos dentro del dossier. El replay M5 numérico opcional no se ejecutó en este worktree porque los checkpoints no estaban allí.

## Verificaciones realizadas

- Backend completo con Python embebido 3.11.9: **2647 pasadas, 50 omitidas** (261 s). Las pruebas añadidas durante esa ejecución se repitieron junto con dossier y sellos: **61 pasadas**. Los grupos dirigidos previos tuvieron **98 pasadas**, **29 pasadas**, y el ajuste de fixtures M5/informe IA **50 pasadas, 2 omitidas**; esos grupos se solapan y no se suman al total.
- Vina real 1.2.7, 3F75, semilla 42: perfiles PRO y normal en `tmp/evaluation-runtime-20260925T050811Z`, **PASS**. Afinidades −5.656 y −4.879 kcal/mol, respectivamente. Hash del receptor preparado `8b945aba2292c92ef32ff2c7a6ae3cdcf5ccd7a0d7041d4a5995bbd3d69189ff`. El gate comprobó dossier, seis denegaciones de otra cuenta y recuperación tras reinicio. Las afinidades son salidas de Vina bajo estas condiciones, no medidas experimentales.
- `generate_goldens.py --check`: **8** goldens verificados. `validar_sellos.py --check`: **167** experimentos sellados, **784** activos verificados originales, **21** mantenidos (32 eventos en 14 experimentos), **107** PDB verificados vía `.gz`, **5** copias de sellos originales, **1** copia de activo mantenido, **0** distintos y **0** ausentes sin declarar. De 731 no distribuidos, sólo 4 son `NO_CONSERVADO`; los demás corresponden a licencia, runtime o archivo no versionado.
- Frontend: `npm run typecheck` pasó; prueba específica del registro científico **7/7**. Se detuvo la suite frontend completa, que abrió muchos procesos, para no agravar el uso de memoria de esta máquina. El cambio visible fue el texto del estado de mantenimiento y el índice del registro.
- `git diff --cached --check` pasó al excluir únicamente la copia histórica cuyos bytes no se podían modificar. Árbol limpio tras el commit.

## Límites para la revisión del auditor

El paquete mejora la procedencia del docking, pero no equivale aún a un export FEP-05 aceptado por OpenFE/FEP+ ni al dry-run FEP-06. No se probó equivalencia bit a bit entre Windows y Ubuntu. La versión de la aplicación y las herramientas queda registrada; en un bundle sin `MOLDESIGN_BUILD_COMMIT` no se inventa un SHA de código. Los activos re-sellados siguen distinguidos porque su código productor anterior no está completamente recuperado. El auditor decide si integrar esta rama a `main`.
