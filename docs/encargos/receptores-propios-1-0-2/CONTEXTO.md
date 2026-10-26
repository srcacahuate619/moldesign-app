# Contexto: receptores propios para MolDesign 1.0.2

Fecha: 2026-10-09. Preparado por Claude (sesión anterior) para la sesión que implementa
este encargo. Todo lo que dice «medido» se midió el 2026-10-09 en esta máquina, sobre
`codex/release-hygiene` = `e9b032ae`.

---

## 1. Por qué ahora

1.0.2 sale con el catálogo partido en tres secciones (decisión del propietario,
2026-10-08/09):

- **Verificados**: vacía en 1.0.2. El único candidato medido, 8HFI, no superó la
  calibración (`CAL-8HFI-01`, NO_GO, sellado).
- **Tus receptores**: el camino para decisiones reales. Texto de la interfaz: «Para
  decisiones reales, usa un receptor preparado y revisado por tu equipo. MolDesign lo
  auditará en Preparación.»
- **Demostración**: los 381 receptores del catálogo.

Es decir, 1.0.2 **promociona** la subida de receptores propios, y esa subida tiene
defectos medidos (sección 2). La orden del propietario es **arreglar, no quitar**, y
que entre en 1.0.2.

---

## 2. Estado medido de la subida (2026-10-09, por la API)

Arnés: `qa_subida_receptores.py` (en esta carpeta). Levanta un backend con datos
desechables, igual que la puerta `check:evaluation-runtime`, sube por
`POST /targets/upload` y evalúa la desipramina con `/evaluation/preflight` +
`/evaluation/submit`. Resultado en `informe_20261009.json`.

| Archivo | Modo | HTTP | Evaluación |
|---|---|---|---|
| `8hfi_crudo.pdb` | automático | 201 | **SUCCESS** en 53 s, con `species_diff` (Preparación puede auditar) |
| `8hfi_curado.pdbqt` | manual (`is_curated=true`) | **201 «subido exitosamente»** | **No se puede evaluar**: el preflight bloquea con `RECEPTOR_FUENTE_DISPONIBLE` |
| `8HFI_CRUDO.PDB` | automático | 400 | mensaje genérico «Error de validación…»: el motivo real (extensión en mayúsculas) se pierde |
| `8hfi.cif` | automático | 400 | «Only PDB (.pdb), PDBQT (.pdbqt, modo manual) or SDF (.sdf)»; SDF tampoco sirve para receptores |

Además, por lectura de código:

- **El modo automático descarta la preparación del usuario.** `prepare_target` vuelve
  a preparar con plantillas de Meeko; `_filter_pdb_content` quita **todas** las aguas y
  todo HETATM que no esté en `cofactors_whitelist`. Un receptor que su equipo protonó y
  en el que decidió qué aguas y metales conservar sale distinto de como entró.
- **Por qué falla el PDBQT manual.** La ingesta guarda el PDBQT en
  `StoragePath.target_prepared(pdb_id)`, sin crudo y sin informe de Meeko. Al evaluar,
  `prepare_target(USR_xxxx)` busca `StoragePath.target_raw`, no lo encuentra y cae a
  `download_pdb_from_rcsb("USR_XXXX")`. El preflight lo detecta antes y bloquea.
  `vina_service` exige además el informe de Meeko con `protonation_templates`
  (`DockingFailed` si falta).

---

## 3. Mapa del código

### Backend

| Pieza | Dónde |
|---|---|
| Endpoint de subida | `backend/api/routers/targets.py`, `upload_custom_target` (≈ líneas 120–210). Límite de 31 MiB; validación de «magic bytes» que busca `HEADER`/`ATOM`/`REMARK` o `$$$$`; convierte todo `ValueError` en un 400 genérico |
| Ingesta | `backend/services/targets/ingestion_manager.py::ingest_custom_target` (≈ 270–479). `is_curated=True` exige `.pdbqt` y centro de caja, y guarda tal cual. `False` exige `.pdb` (`endswith` distingue mayúsculas), descubre el bolsillo si no hay centro, anota el sitio (`anotar_sitio`) y llama a `prepare_target(force_reprepare=True)` |
| Metadatos | `extract_pdb_metadata` (organismo y resolución, sólo de cabeceras PDB) |
| Preparación | `backend/services/docking/preparer.py::prepare_target` (≈ 1251–1770): resuelve el origen (crudo, biblioteca, siembra o RCSB) → `receptor_recipe_hash` → atajo de caché → `generar_unidad_biologica` (BIOMT, lee REMARK 350 del texto PDB) → `cofactores_sin_plantilla` → `_filter_pdb_content` → truncado de cadenas laterales (receta v7) → huecos del esqueleto → `diff_de_especies_de_la_corrida` → Meeko → `_residuos_eliminados` → informe JSON (`species_diff`, `protonation_templates`, `removed_residues`, `truncated_sidechains`, `backbone_gaps`, `recipe_hash`, `receptor_sha256`…) |
| Filtro | `_filter_pdb_content` (≈ 184–355): elige altloc por ocupación, quita aguas siempre, HETATM salvo lista blanca o MSE→MET |
| Constantes | `RECEPTOR_RECIPE_VERSION = 7`, `MARGEN_SITIO_A = 6.0`, `_METAL_COFACTORS`, `_WATER_RESIDUES`, `ORGANIC_COFACTORS_KEPT` |
| Preflight | `backend/services/docking/preflight.py::build_preflight`; control `RECEPTOR_FUENTE_DISPONIBLE` (≈ 495–540) |
| Lo que copia la corrida | `backend/services/docking/vina_service.py`, bloque `execution_provenance` → `receptor_prep` (≈ 1326–1400); lectura del informe de Meeko (≈ 836–875) |
| Auditoría | `backend/services/dossier/preparacion.py` (requisitos y agregación; ver su docstring) y `backend/services/dossier/model.py` (dossier; ya incluye `campo_de_la_seccion` y `run.catalogo`, `d26c5f8a`) |
| Sección del catálogo | `backend/services/targets/seccion_catalogo.py`: privados y comunidad → `None` («Tus receptores») |
| mmCIF ya resuelto en otro sitio | `scripts/bowes44_validar_estructuras.py`: `descargar_pdb` (mmCIF → PDB con gemmi) y `het_de_codigo_largo` (códigos CCD de 5 caracteres) |
| AlphaFold DB ya integrado (añadido tras escribir el encargo) | `backend/services/alphafold/client.py` y las rutas `GET /targets/alphafold/lookup/{uniprot_id}` y `/targets/alphafold/search` (`targets.py` ≈ 437–520): baja el **PDB** `AF-<id>-F1-model_v4.pdb`, lee el pLDDT del B-factor (`_parse_plddt_from_pdb`) y avisa por el pLDDT **medio** (< 50 CRÍTICO, < 70 ADVERTENCIA). Lo nuevo es el pLDDT **del sitio** y los formatos mmCIF/ModelCIF y otras fuentes (AF3, Boltz, Chai): reutiliza este cliente y su convención para AFDB, y mantén coherentes los dos caminos (subida y búsqueda en AlphaFold DB) |

### Frontend

| Pieza | Dónde |
|---|---|
| Modal de subida | `frontend/components/interfaces/pro/CustomReceptorModal.tsx`: modos `auto`/`manual`; `accept=".pdb"` o `".pdbqt"`; prop `antiDiana` (subida de anti-dianas, Sol, `8821ba47`) |
| Selector | `frontend/components/interfaces/pro/TargetSelectorModal.tsx` (secciones Verificados / Tus receptores / Demostración) |
| Llamada | `frontend/lib/api.ts::uploadCustomTarget`; caché del catálogo en `frontend/lib/catalogoDeReceptores.ts` (`invalidarCatalogo`) |
| Textos | `frontend/context/traducciones/*.ts` (es/en, con guardián de textos sin traducir) |

**Sol (GPT) trabaja en paralelo** en `D:\moldesign-build\.worktrees\catalogo-demostracion`,
rama `sol/catalogo-sello`, sólo frontend (sello «Verificado», insignia compacta,
selector). Puede tocar `TargetSelectorModal.tsx`. No toques su worktree; los conflictos
los resuelve Claude al integrar.

---

## 4. Lo que hay en el runtime (python-embed 3.11.9)

- **gemmi 0.7.5**: lee mmCIF, ModelCIF y `.gz`, y genera ensamblajes
  (`make_assembly`). Basta para mmCIF sin dependencias nuevas.
- **meeko 0.7.1**. Plantillas presentes: HID, HIE, HIP, CYX, ASH, GLH, LYN, HOH, ZN,
  MG, CA (y las del producto en `backend/data/meeko_templates/`). **Ausentes:** HIS a
  secas (Meeko elige entre HIE/HID/HIP por los H presentes), los nombres de CHARMM
  HSD/HSE/HSP, CYM, WAT y NA.
- **Trampa del sodio**: en PDBQT, el tipo `NA` es un nitrógeno aceptor. Un Na⁺ no
  tiene representación en Vina; conservarlo sin más produciría un nitrógeno fantasma.
- **No están** pdb2pqr ni propka. Aceptar su **salida** (PQR) no exige instalarlos.
  Para generar casos de prueba, usa un entorno aparte, nunca el runtime.
- **Vina 1.2.7**: `D:\moldesign-build\tools\vina\vina.exe` (no versionado).

---

## 5. Casos reales para el corpus

| Caso | Por qué | Fuente |
|---|---|---|
| 8HFI en PDB y en mmCIF | Paridad: el mismo receptor por las dos vías tiene que dar el mismo receptor preparado | `data/targets/8HFI.pdb.gz` (repo); `D:\moldesign-audits\verificacion-8hfi-20261008\fuentes\8HFI.cif` (con hash en su `manifest.json`) |
| 8XVK, 8ZP2, 8YUT | Códigos CCD de 5 caracteres: `A1D5J` (ambrisentán), `A1LX4` (atomoxetina); en 8YUT, `A1D67` y `A1D5J` se fundirían en «A1D» si se truncan | RCSB (sólo hay mmCIF); memoria `codigos-ccd-de-cinco-caracteres` |
| Modelo de AlphaFold DB | pLDDT por residuo; sin ligandos ni aguas | `https://alphafold.ebi.ac.uk/` (p. ej. NET humano, P23975) |
| Salida de Boltz/Chai/AF3 | Su convención de pLDDT **hay que verificarla con archivos reales**, no suponerla | Si no hay un archivo real disponible, decláralo y no lo afirmes |
| Receptor protonado con PDB2PQR/PROPKA | Modo «preparado por tu equipo» y PQR | Genéralo en un entorno aparte y registra versiones y comando |
| Nombres de CHARMM (HSD/HSE/HSP) | Mapeo a HID/HIE/HIP declarado | Renombrado sintético documentado |
| PDBQT con y sin estructura de origen | El modo roto de hoy | El PDBQT de 8HFI de la corrida `CAL-8HFI-01` (`D:\moldesign-audits\cal-8hfi-01\datos-01\targets\8HFI\prepared-*.pdbqt`) y su `raw.pdb` |
| Casos adversos | Un guardián tiene que demostrar que ve | RMN con varios MODEL, altlocs, CRLF, sin columna de elemento, sólo ADN, un `.gz` que se infla por encima del límite, extensión que no casa con el contenido, 5 caracteres de CCD, más de 99 999 átomos o cadenas de varias letras |

---

## 6. Invariantes (romperlos es un defecto)

1. **El catálogo no cambia.** Los receptores del catálogo (receta 7) tienen que salir
   **byte a byte iguales**. Mídelo: el mismo `receptor_sha256` antes y después para
   8HFI, 1C3R, 3F75 (sitio A+P), 5VA1 (hERG, cuatro cadenas) y 1HSG. Hay puertas que
   dependen de ello: `generate_goldens.py --check`,
   `generate_catalog_availability.py --check`, `check:dossier-embebido` y
   `check:evaluation-runtime`.
2. **El contrato de Preparación no se relaja.** «Imprescindible sin dato o en
   ABSTENCIÓN → BLOQUEADO» se mantiene. Lo que cambia es que la ausencia se **explica**
   («sin estructura de origen no se puede saber qué se retiró: súbela para auditar»),
   no que desaparezca. `TRANSFERENCIA_FEP_DEMOSTRADA` sigue en `False`.
3. **Sin red al evaluar.** Un receptor `USR_*` nunca debe acabar en
   `download_pdb_from_rcsb`.
4. **Frontera GPL.** Nada de `import openbabel`/`pybel`; Open Babel sólo por
   `backend/services/external_tools/open_babel.py`.
5. **Lo que se verifica es lo que se entrega.** Las pruebas unitarias no bastan: cada
   formato y cada modo pasan por la API con Vina real (el arnés de esta carpeta).
6. **Nada se trunca ni se renombra en silencio.** Una cadena de varias letras, un código
   de 5 caracteres o un residuo renombrado (HSD→HID, WAT→HOH) se registran con su
   correspondencia en el informe de preparación y llegan al dossier. Si algo no se puede
   representar, se abstiene con un motivo, no se adivina.
7. **Los mensajes de error son útiles y seguros.** Dicen qué falló y qué hacer, en los
   dos idiomas, sin rutas del disco.

---

## 7. Material relacionado (sólo lectura)

- Worktree de Codex `D:\moldesign-build\.worktrees\receptores-20261008` (rama
  `codex/receptores-curacion-20261008`, **sin commitear, receta 8, para 1.0.3**). Rediseña
  el ensamblaje (`ensamblaje_biologico.py`, `referencia_estructural.py`) y la selección
  de unidades. **No lo fusiones ni copies su receta**; puedes leerlo como referencia.
- Memoria del proyecto (se carga sola): `subida-de-receptores-propios-estado`,
  `codigos-ccd-de-cinco-caracteres`, `catalogo-demostracion-y-verificados`,
  `preparacion-fep-siguiente-paso`, `frontera-open-babel-programa-independiente`,
  `heredoc-de-bash-colapsa-barras`, `arnes-debe-replicar-el-entorno-de-tauri`,
  `reglas-de-metodo-probar-antes-de-sellar`, `registro-de-cambios-1-0-2`.
