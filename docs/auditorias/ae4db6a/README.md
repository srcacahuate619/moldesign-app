# Corrigendum de la auditoría `ae4db6a`

Respuesta a la *Auditoría científica y de backend de MolDesign AI* sobre el
commit `ae4db6a` (2026-09-24): 131 hallazgos en 8 áreas. Este directorio
contiene lo que se hizo con cada hallazgo, en qué commit, con qué evidencia y
qué queda abierto. El informe del auditor no se reproduce aquí.

## Commits

Todos van encima de `27c4b79`, que es el `main` público auditado, en línea y
sin fusiones. Las fases siguen el orden del plan del auditor
(`03_PLAN_DE_CORRECCION.md` §3).

| Commit | Contenido | Bitácora |
|---|---|---|
| `fb3b315` | Fase 0: dejar de afirmar lo que no ocurrió | [fase0.md](fase0.md) |
| `2cb93e1` | Fase 1: el receptor que se acopla es el que se declara | [fase1.md](fase1.md) |
| `65a9db3` | Fase 2: especie química reproducible y declarada | [fase2.md](fase2.md) |
| `33204b0` | Fase 3: el número que ordena es el que se dice | [fase3.md](fase3.md) |
| `2d0233c` | Fase 4: procedencia reproducible | [fase4.md](fase4.md) |
| `c3aa468` | Fase 5: seguridad del backend local | [fase5.md](fase5.md) |
| `183a57d`, `3f626c3`, `d570797` | Fase 6: preregistro, arnés y contenciones científicas | [fase6.md](fase6.md) |
| `06d27b6` | Fase 7: calidad y eficiencia | [fase7.md](fase7.md) |
| `3fcf35f` | Regresiones halladas al verificar las fases | [verificacion_2026-09-26.md](verificacion_2026-09-26.md) |
| `d3c0e0b` | Puertas de CI que las fases dejaron en rojo | [verificacion_2026-09-26.md](verificacion_2026-09-26.md) |
| `30a9eb5` | Cofactores con margen de sitio, disponibilidad del catálogo medida, DOCK-012, panel de selectividad y MolChat | [verificacion_2026-09-26.md](verificacion_2026-09-26.md), segunda parte |

Otros documentos de este directorio:

- [Inventario_regresiones.md](Inventario_regresiones.md): capacidades
  retiradas, cobertura reducida y resultados históricos que dejan de ser
  comparables. Es la lectura recomendada para saber qué cambia para quien usa
  la aplicación.
- [validacion_informe_PR-LIG-04.md](validacion_informe_PR-LIG-04.md): contraste
  de las fuentes de pKa usadas en LIG-003, con dos atribuciones erróneas
  detectadas en el informe externo.
- `evidencia_fase6/score007_native/`: manifiesto, hashes de entrada y métricas
  de SCORE-007.

## Cómo leer las bitácoras

- Son las notas de trabajo de cada fase, copiadas **literalmente**, con una
  excepción: en `fase3.md` se omitieron la dirección y la ruta de un servidor
  propio.
- Describen el estado al cerrar cada fase. Lo que se encontró después está en
  `verificacion_2026-09-26.md`, no en ellas. Por ejemplo, `fase0.md` dice que
  los cambios seguían sin commit; después se commitearon como `fb3b315`.
- Las rutas `D:\moldesign-build\.worktrees\...` son los directorios de trabajo
  locales donde se hizo cada fase.
- **Material no publicado:**
  - la matriz `matrix_native_faseA.npz` y `predictions.jsonl` de SCORE-007:
    derivan de estructuras y afinidades de PDBBind v2020, cuya licencia no
    permite redistribuirlas (ver `scripts/sellos_no_distribuidos.json`); sus
    hashes figuran en `matrix_manifest.json` y en `fase6.md`;
  - `prepare_stderr.log`;
  - los encargos de investigación externa que citan algunas bitácoras;
  - la evidencia bruta del diagnóstico de la verificación: descargas de ChEMBL
    e inventario de datos privados.

## Cómo comprobarlo

Desde un clon, con el entorno de `backend/requirements-embed.lock.txt`, las
mismas órdenes que ejecuta `.github/workflows/ci.yml`:

```bash
cd backend
python -m pytest tests -ra -p no:cacheprovider          # desde backend/, no desde la raíz
python ../scripts/report_test_counts.py --check
python ../scripts/generate_openapi_contract.py --check
python ../scripts/generate_runtime_inventory.py --check
python ../scripts/validar_sellos.py --check
cd ..
python rescoring/scripts/generate_model_manifest.py --check
python -m pytest rescoring/tests -ra -p no:cacheprovider
```

Para ver que una prueba de aceptación detecta su defecto, basta ejecutarla
contra `27c4b79`: su `backend/` y su `rescoring/` son idénticos a los de
`ae4db6a`.

## Estado por hallazgo

Significado de cada estado:

- **Corregido:** el defecto se corrigió y una prueba lo cubre.
- **Retirado:** la capacidad producía un resultado falso y se quitó del
  producto.
- **Contenido:** la afirmación o el peso se retiraron hasta tener evidencia
  nueva.
- **Parcial:** se corrigió una parte; la nota dice qué falta.
- **Pendiente:** no se corrigió.

| Estado | Hallazgos |
|---|---:|
| Corregido | 107 |
| Retirado | 10 |
| Contenido | 6 |
| Parcial | 4 |
| Pendiente | 4 |
| **Total** | **131** |

### Fase 0

| ID | Sev. | Estado | Nota |
|---|---|---|---|
| API-001 | CRÍTICA | Corregido |  |
| ENG-A01 | CRÍTICA | Corregido |  |
| ENG-A02 | CRÍTICA | Corregido |  |
| ENG-A03 | CRÍTICA | Corregido |  |
| PROV-001 | CRÍTICA | Corregido |  |
| PROV-002 | CRÍTICA | Retirado | etapa `openmm` (era UFF de RDKit) rechazada antes de ejecutar |
| SCORE-003 | CRÍTICA | Retirado | la «atención GNN» heurística ya no se presenta, ni en registros antiguos |
| DOCK-017 | ALTA | Corregido |  |
| ENG-A04 | ALTA | Retirado | rama DiffDock que persistía afinidad 0.0 eliminada |
| ENG-A06 | ALTA | Corregido |  |
| LIG-008 | ALTA | Corregido |  |
| ORQ-001 | ALTA | Corregido | testosterona y los 8 fármacos en cuarentena vuelven con SMILES isomérico de PubChem, InChIKey y CIP verificados |
| ORQ-003 | ALTA | Corregido |  |
| PHYS-002 | ALTA | Retirado | valores históricos sin versión de motor ya no se muestran como kcal/mol |
| PHYS-006 | ALTA | Corregido |  |
| PHYS-009 | ALTA¹ | Retirado | ver PROV-002 |
| PROV-010 | ALTA | Corregido | para docking; el export FEP-05 sigue siendo trabajo aparte |
| SCORE-006 | ALTA | Corregido | más la caché de features por contenido del receptor (3fcf35f) |
| API-008 | MEDIA | Retirado | `POST /rescore` retirado (404); el rescoring del pipeline sigue |
| DOCK-018 | MEDIA | Corregido |  |
| ENG-A12 | MEDIA | Corregido |  |
| ENG-A16 | MEDIA | Corregido |  |
| PHYS-001 | MEDIA | Retirado | MM-GBSA fuera del producto: 422 antes de ejecutar |
| PHYS-010 | MEDIA¹ | Retirado | sin cálculo nuevo, no hay abstención sin rastro |
| PROV-005 | MEDIA | Corregido |  |
| SCORE-011 | MEDIA | Corregido |  |
| SCORE-015 | MEDIA | Corregido |  |

### Fase 1

| ID | Sev. | Estado | Nota |
|---|---|---|---|
| DOCK-001 | CRÍTICA | Corregido |  |
| DOCK-004 | CRÍTICA | Corregido |  |
| DOCK-005 | CRÍTICA | Corregido |  |
| PROV-003 | CRÍTICA | Corregido |  |
| DOCK-002 | ALTA | Corregido | ya no se borran en silencio; medido: 119/380 dianas quedan no disponibles por residuos del sitio que Meeko elimina |
| DOCK-003 | ALTA | Contenido | cofactor sin plantilla a ≤ 6 Å de la caja ⇒ abstención (10/380 dianas); más lejos se retira o se devuelve a su aminoácido, declarado |
| DOCK-006 | ALTA | Corregido |  |
| DOCK-007 | ALTA | Corregido |  |
| DOCK-008 | ALTA | Corregido |  |
| DOCK-010 | ALTA | Corregido |  |
| DOCK-016 | ALTA | Corregido |  |
| SCORE-008 | ALTA | Contenido | cifras 33.37x / 0.919 retiradas; benchmark nuevo pendiente de datos primarios |
| DOCK-009 | MEDIA | Corregido |  |
| DOCK-011 | MEDIA | Corregido |  |
| DOCK-013 | MEDIA | Corregido |  |
| DOCK-014 | MEDIA | Corregido | aviso y exhaustividad ≥32; la política no tiene benchmark de convergencia |
| DOCK-019 | MEDIA | Corregido |  |
| DOCK-020 | MEDIA | Corregido |  |
| DOCK-015 | BAJA | Corregido |  |

### Fase 2

| ID | Sev. | Estado | Nota |
|---|---|---|---|
| LIG-001 | CRÍTICA | Corregido |  |
| LIG-002 | ALTA | Corregido |  |
| LIG-003 | ALTA | Parcial | clases añadidas; metformina, imidas y N-cianoguanidinas quedan en REVIEW |
| LIG-004 | ALTA | Corregido |  |
| LIG-005 | ALTA | Corregido |  |
| LIG-007 | ALTA | Corregido |  |
| PROV-006 | ALTA | Corregido |  |
| LIG-006 | MEDIA | Corregido |  |
| LIG-009 | MEDIA | Corregido |  |
| LIG-010 | MEDIA | Corregido |  |
| LIG-012 | MEDIA | Corregido |  |
| LIG-013 | BAJA | Corregido |  |
| LIG-014 | BAJA | Corregido |  |

### Fase 3

| ID | Sev. | Estado | Nota |
|---|---|---|---|
| ENG-A09 | ALTA | Corregido |  |
| ENG-A10 | ALTA | Corregido |  |
| ORQ-002 | ALTA | Corregido |  |
| SCORE-001 | ALTA | Corregido |  |
| SCORE-002 | ALTA | Contenido | latente: MM-GBSA ya no entra en `total_score` |
| SCORE-005 | ALTA | Corregido |  |
| ENG-A11 | MEDIA | Corregido |  |
| SCORE-009 | MEDIA | Corregido |  |
| SCORE-012 | MEDIA | Corregido |  |
| SCORE-013 | MEDIA | Corregido |  |
| SCORE-014 | MEDIA | Corregido |  |
| SCORE-016 | MEDIA | Corregido |  |
| SCORE-017 | MEDIA | Corregido |  |
| SCORE-019 | MEDIA | Corregido |  |

### Fase 4

| ID | Sev. | Estado | Nota |
|---|---|---|---|
| PROV-004 | ALTA | Corregido |  |
| PROV-007 | ALTA | Corregido |  |
| PROV-008 | MEDIA | Corregido |  |
| PROV-009 | MEDIA | Corregido |  |
| PROV-011 | MEDIA | Corregido |  |
| PROV-013 | MEDIA | Corregido |  |
| PROV-015 | MEDIA | Corregido |  |
| PROV-014 | BAJA | Corregido |  |
| PROV-019 | BAJA | Corregido |  |
| PROV-020 | BAJA | Corregido |  |

### Fase 5

| ID | Sev. | Estado | Nota |
|---|---|---|---|
| API-002 | ALTA | Corregido |  |
| API-003 | ALTA | Corregido |  |
| API-004 | ALTA | Corregido |  |
| API-006 | ALTA | Corregido |  |
| API-007 | ALTA | Corregido |  |
| API-005 | MEDIA | Corregido |  |
| API-009 | MEDIA | Corregido |  |
| API-010 | MEDIA | Corregido |  |
| API-011 | MEDIA | Corregido |  |
| API-012 | MEDIA | Corregido |  |
| API-013 | MEDIA | Corregido |  |
| API-014 | MEDIA | Corregido |  |
| API-015 | MEDIA | Parcial | 6 dependencias actualizadas; no se repitió pip-audit completo |
| API-016 | MEDIA | Parcial | corregidos los `except` de rutas científicas críticas, no los 248 |
| API-018 | BAJA | Corregido |  |
| API-020 | BAJA | Corregido |  |

### Fase 6

| ID | Sev. | Estado | Nota |
|---|---|---|---|
| ENG-A05 | ALTA | Corregido |  |
| ENG-A07 | ALTA | Corregido |  |
| PHYS-003 | ALTA¹ | Pendiente | sólo relevante si se reactiva MM-GBSA con un protocolo nuevo |
| SCORE-004 | ALTA | Contenido | M4 v2: Vina 1.0, XGBoost 0.0 hasta validar sobre poses Vina y dianas disjuntas |
| SCORE-007 | ALTA | Contenido | AUC 0.8818 reproducida sobre poses cristalográficas; falta evaluación sobre poses Vina |
| ENG-A08 | MEDIA | Corregido |  |
| ENG-A13 | MEDIA | Corregido |  |
| ENG-A14 | MEDIA | Corregido |  |
| LIG-011 | MEDIA | Retirado | TabPFN y la penalización `S_tox` retirados hasta tener procedencia de `control_toxics.csv` |
| PHYS-004 | MEDIA¹ | Pendiente | ídem |
| PHYS-005 | MEDIA | Corregido |  |
| PHYS-011 | MEDIA¹ | Pendiente | ídem |
| PHYS-013 | MEDIA¹ | Pendiente | ídem |
| PROV-012 | MEDIA | Corregido |  |
| PROV-016 | MEDIA | Corregido |  |
| SCORE-010 | MEDIA | Contenido | ver SCORE-004 |

### Fase 7

| ID | Sev. | Estado | Nota |
|---|---|---|---|
| API-017 | BAJA | Corregido |  |
| API-019 | BAJA | Corregido |  |
| ENG-A15 | BAJA | Corregido |  |
| ENG-A18 | BAJA | Corregido |  |
| ORQ-004 | BAJA | Corregido |  |
| ORQ-005 | BAJA | Corregido | suites verdes desde `backend/` tras 3fcf35f y d3c0e0b |
| ORQ-006 | BAJA | Corregido |  |
| PHYS-008 | BAJA¹ | Corregido |  |
| PHYS-012 | BAJA¹ | Retirado | refinamiento peptídico deshabilitado; se conserva la pose original |
| PROV-018 | BAJA | Corregido |  |
| SCORE-018 | BAJA | Parcial | se declara la pose que usa Model A; la paridad de features exige reentrenar |
| SCORE-020 | BAJA | Corregido |  |
| SCORE-021 | BAJA | Corregido |  |

### Sin fase en el plan del auditor

| ID | Sev. | Estado | Nota |
|---|---|---|---|
| DOCK-012 | MEDIA | Corregido | omitido por las fases 0-7; corregido en la verificación: diámetro del ligando, independiente de la orientación |
| ENG-A17 | MEDIA | Corregido | vía ENG-A03: el backend rechaza los motores que AGENTS.md declara no disponibles |
| PROV-017 | MEDIA | Corregido | vía LIG-005 (SA>7 ya no aborta) y ORQ-002 (denominador declarado); sin cambio propio |
