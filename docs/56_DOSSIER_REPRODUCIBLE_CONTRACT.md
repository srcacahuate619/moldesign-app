# 56 — Contrato del dossier y del paquete reproducible

**Estado:** 🟢 Vigente desde Sprint 4A. Motor backend implementado; la
integración con la interfaz de Informe llega en Sprint 4B.

---

## 1. Propósito

El dossier responde una pregunta y sólo una:

> ¿Qué evidencia computacional produjo esta corrida, qué partes son
> reproducibles, qué supuestos hizo, qué controles superó, qué incertidumbres
> permanecen y qué sería justificable hacer después?

**No** responde «¿es esta molécula un buen fármaco?». Esa pregunta no la puede
contestar un acoplamiento, y presentarla contestada es la autoridad indebida que
`docs/53 §6.7` manda retirar.

Hay dos salidas y ninguna sustituye a la otra:

| Salida | Qué es | Para quién |
|---|---|---|
| `dossier.pdf` | la lectura humana del caso | quien decide |
| paquete `.zip` | la contraparte verificable | quien audita o reproduce |

---

## 2. Límites científicos

- **No hay score soberano.** Los índices 0-100 no aparecen en portada, resumen
  ni jerarquía principal. Viven en el *Apéndice A · Outputs heredados*, marcados
  como no decisionales, con la advertencia de que no son probabilidad, confianza
  ni calidad. No existe ningún «GLOBAL SCORE».
- **Las afinidades son señales de ranking dentro del protocolo**, no mediciones
  de energía libre experimental.
- **La pose top-1 no es verdad estructural.** Sin un control geométrico
  superado, el orden de energía no demuestra nada.
- **La ausencia de alertas no es validez.** Un control que no se ejecutó sale
  `NO EVALUADO` y no autoriza ninguna conclusión.
- **Ninguna «siguiente acción» recomienda un fármaco, un candidato clínico ni un
  compuesto seguro.** Describen qué trabajo computacional queda justificado.
- **Sin narrativa generada.** El documento es determinista y sale exclusivamente
  de datos registrados. No se llama a PubChem, Ollama ni a ningún proveedor.

### Corrección de hidrógenos

El control de validez física declara su protocolo: la pose se reconstruye desde
PDBQT con plantilla del SMILES, y **los hidrógenos se añaden en esa
reconstrucción** — la representación validada no es la del cristal. Es la
corrección documentada en `docs/53`. Las cifras históricas 8,62 % / 15,52 % **no
se citan** como justificación en ninguna parte del dossier, y el proxy de
energía no se presenta como fallo físico soberano.

Hoy `eval_result.pose_validation` **no es una columna del ORM**: el validador de
`services/chemistry/pose_physical_validity.py` existe pero no está cableado al
pipeline (`docs/53 §12`, punto 6). En consecuencia el control sale siempre
`NO EVALUADO`, que es lo correcto y está cubierto por pruebas.

---

## 3. Taxonomía de estados

Un solo vocabulario para el PDF, el manifiesto y el README.

| Estado | Significado |
|---|---|
| `NO_DEFINIDO` | El caso no declaró este contexto. |
| `NO_EVALUADO` | El control no se ejecutó en esta corrida. |
| `NO_DISPONIBLE` | El resultado o artefacto esperado no está disponible. |
| `NO_APLICA` | El control no corresponde a este caso. |
| `REVISAR` | Hay evidencia, pero no autoriza una conclusión por sí sola. |
| `ABSTENCION` | Falta evidencia indispensable o existe un bloqueo declarado. |
| `REGISTRADO` | El dato existe y quedó serializado por la corrida. |
| `PASA` | El control se ejecutó y lo superó. |

**Regla que no se negocia:** ni `None`, ni un campo ausente, ni un error de
lectura se convierten nunca en `PASA` o `REGISTRADO`.

`NO_DEFINIDO` y `NO_DISPONIBLE` se distinguen a propósito: el primero es un
hueco del usuario, el segundo del pipeline. Confundirlos culparía a uno de lo
que hizo el otro.

---

## 4. Esquema de entrada

`POST` recibe una **proyección del caso** (`services/dossier/schemas.py`,
`projection_version: 1`). El caso vive en el cliente; el backend toma sólo lo
necesario para redactar y recupera todo lo científico de sus propias fuentes.

```jsonc
{
  "projection_version": 1,
  "case_id": "caso-serie-a-001",
  "case_schema_version": 3,
  "name": "Serie A · exploración del bolsillo ortostérico",
  "created_at": "2026-08-20T08:00:00+00:00",
  "context": {
    "study_kind": "explore-hypothesis",
    "question": "…", "decision": "…", "system_rationale": "…",
    "controls": "…", "assumptions": "…", "uncertainties": "…", "notes": "…"
  },
  "inputs": {
    "receptor": { "pdb_id": "7E2Y", "chain": "R", "origin": "curado",
                  "name": "…", "target_id": "…" },
    "ligand":   { "input_smiles": "…", "canonical_smiles": "…", "name": "…" },
    "config":   { "grid_center": [x,y,z], "grid_size": [x,y,z],
                  "custom_hotspots": ["R:TYR390"], "docking_engine": "vina",
                  "exhaustiveness": 8, "num_poses": 9, "seed": 42 }
  },
  "preflight": { "fingerprint": "sha256:…", "generated_at": "…",
                 "execution_route": "docking_vina",
                 "blockers": [], "warnings": [], "not_evaluated": [] },
  "run": { "task_id": "…", "input_fingerprint": "sha256:…",
           "execution_state": "completed", "started_at": "…" },
  "decisions": [ { "control_code": "…", "fingerprint": "sha256:…",
                   "decision": "reconocida", "at": "…", "note": "…" } ],
  "run_inputs_relation": "corresponde"
}
```

### Lo que se rechaza (HTTP 422)

- **rutas locales** en cualquier texto: `C:\…`, `/home/…`, UNC `\\…`, `../`;
- **`storage.path`** y cualquier campo desconocido (`extra="forbid"`);
- **resultados científicos** suministrados por el cliente (afinidades, poses,
  scores): el backend no los acepta, los recupera;
- secretos, tokens o configuración de proveedores.

Las rutas se rechazan **en la entrada**, no se filtran al imprimir: un filtro de
salida hay que recordar aplicarlo en cada sitio, y basta olvidarlo una vez para
publicar el nombre de usuario de alguien dentro de un PDF que circula.

### Lo que el backend recupera por su cuenta

`MoleculeORM`, `EvaluationResultORM`, `TargetORM`, poses, receptor preparado y
logs de la corrida. Autorización: `require_owned_molecule`, la misma que el
resto de `/evaluation`.

### Coherencia de la corrida

Si `EvaluationResult.celery_task_id` existe y **no coincide** con el `task_id`
de la proyección, el endpoint responde **409**. No se empaqueta en silencio un
resultado que pertenece a otra corrida.

Si la huella de la corrida no coincide con la del preflight, el modelo lo
declara —`REVISAR` en «relación de la corrida con los inputs actuales»—, escribe
un **aviso de integridad** en el PDF y fuerza `ABSTENCIÓN` en la siguiente
acción. El backend confía en lo que puede comprobar, no en lo que el cliente
declare.

---

## 5. Estructura del ZIP

```
moldesign_case_<case-id>_run_<task-short>/
├── README.md                    qué es, cómo verificar, qué falta
├── dossier.pdf                  lectura humana
├── manifest.json                rol, tamaño, SHA-256 y estado por archivo
├── checksums.sha256             índice ordenado de hashes
├── case/
│   ├── case_snapshot.json       la proyección validada, tal cual entró
│   └── dossier_model.json       el modelo canónico completo
├── run/
│   ├── protocol.json            parámetros, entradas y procedencia
│   └── reproduce.md             receta de reproducción
├── inputs/                      ligando y receptor preparado, si existen
├── outputs/                     poses serializadas, si existen
├── evidence/
│   └── evidence_summary.json    controles, dimensiones, decisiones
└── logs/                        advertencias y errores de ESTA corrida
```

**Sólo artefactos reales.** Si un archivo no existe: no se fabrica un marcador
que parezca el artefacto; se registra en `manifest.json` con estado
`NO_DISPONIBLE` o `NO_EVALUADO` y su razón, y la ausencia se explica en el
`README.md`.

### Nunca se incluye

`.env`, claves, tokens, la base de datos, rutas del perfil del usuario, carpetas
temporales, logs de otras corridas, archivos no relacionados, enlaces simbólicos
ni rutas absolutas o con `..`. No es un filtro de salida: sólo se escriben los
artefactos que `package.py` construye, con nombres saneados por lista blanca.

---

## 6. Reglas de integridad

`manifest.json` (v1) declara por archivo: `path` relativo normalizado con `/`,
`rol`, `media_type`, `tamano`, `sha256`, `fuente` y `estado`.

`checksums.sha256` está ordenado, usa `/` y cubre todos los archivos del paquete
salvo sí mismo.

### Las tres exclusiones deliberadas

1. **El ZIP no se contiene a sí mismo.** Incluirlo cambiaría su hash.
2. **`checksums.sha256` no se hashea a sí mismo**, por lo mismo.
3. **`manifest.json` no se declara a sí mismo** dentro de `files`, por lo mismo
   — pero **sí queda cubierto**: `checksums.sha256` se calcula después e
   incluye el manifiesto. El único archivo sin hash propio es
   `checksums.sha256`, que es la raíz de la cadena.

Las tres están escritas en el `README.md` del paquete y en el campo
`exclusiones` del manifiesto, para que un verificador ajeno pueda reproducir el
criterio en vez de reportarlas como archivos no declarados.

### Determinismo

Con los mismos inputs y el mismo `generated_at`, el ZIP es **byte a byte
idéntico**: orden estable de entradas, timestamps del ZIP congelados en
1980-01-01, JSON canónico (claves ordenadas) y compresión fija.

El PDF se genera con `invariant=1` de ReportLab. Sin eso, cada render escribía
`/CreationDate` con la hora real y un `/ID` aleatorio, y esa diferencia se
propagaba al hash del manifiesto: el paquete dejaba de ser reproducible y el
verificador no podía distinguir un cambio real de dos exportaciones.

---

## 7. Algoritmo de verificación

`scripts/verify_dossier_package.py <archivo.zip> [--json]`

**Nunca extrae ni ejecuta nada.** Lee la tabla del ZIP y hashea en memoria. Por
eso el orden empieza por las rutas, antes de tocar contenido: un verificador que
extrajera sería la vía de entrada obvia para un zip-slip.

1. **Rutas**: ninguna absoluta, con unidad de disco, con `\`, con `..` ni con
   componentes vacíos; ningún enlace simbólico.
2. **Duplicados**: ninguna entrada repetida (un lector ingenuo sólo ve la
   última).
3. **Raíz única**.
4. **Manifiesto**: existe, es JSON, y su `manifest_version` ≤ la soportada. Una
   versión futura **detiene** la verificación en vez de concluir.
5. **Archivos declarados**: los `REGISTRADO` existen; los declarados ausentes
   **no** están presentes (si aparecen, el paquete miente sobre sí mismo).
6. **Tamaño y SHA-256** de cada archivo declarado.
7. **Archivos no declarados**: ninguno, salvo las tres exclusiones.
8. **`checksums.sha256`**: ordenado, sin líneas mal formadas, coincide con el
   contenido real y no lista archivos que no están.

Resultado binario con motivos: **VÁLIDO** o **INVÁLIDO**. No hay «válido con
reservas»: quien lee «válido» no lee la letra pequeña.

Códigos de salida: `0` válido · `1` inválido · `2` no se pudo leer el archivo.
El `2` se distingue a propósito — «no pude comprobarlo» no es «lo comprobé y
está mal».

---

## 8. Endpoints

Bajo `/evaluation/dossier`, **no** bajo `/blockchain`. Razón: `/blockchain/
certificate` sella *cuándo* se emitió algo; el dossier describe *qué evidencia
produjo una corrida* y depende del CASO, que aquella ruta no conoce. Las rutas
antiguas se conservan intactas.

Son `POST` porque el caso vive en el cliente y no cabe en una URL.

| Método | Ruta | Devuelve |
|---|---|---|
| `POST` | `/evaluation/dossier/{molecule_id}/preview` | `application/pdf` inline |
| `POST` | `/evaluation/dossier/{molecule_id}/package` | `application/zip` adjunto |

Errores: **404** molécula inexistente o sin resultado · **403** no es del
usuario · **409** el `task_id` no corresponde · **422** proyección inválida.

`Content-Disposition` lleva el nombre saneado a `[A-Za-z0-9._-]`: un nombre de
caso con comillas o saltos de línea podría inyectar cabeceras.

### Ejemplo

```bash
curl -X POST http://127.0.0.1:8001/evaluation/dossier/$MOL_ID/package \
     -H "Content-Type: application/json" \
     --data @proyeccion.json -o paquete.zip

python scripts/verify_dossier_package.py paquete.zip
# VÁLIDO
#   raíz:        moldesign_case_caso-serie-a-001_run_task-complet
#   manifiesto:  v1
#   archivos:    9 presentes / 9 declarados
```

---

## 9. Deudas para Sprint 4B

Declaradas, no escondidas:

1. **Integración con la interfaz de Informe.** `CaseReportView` sigue usando
   `PDFReportViewer` y `/blockchain/certificate`. Cablearlo a
   `/evaluation/dossier` es 4B, y con ello la proyección del caso desde el
   cliente.
2. **Diff fuente→preparado dentro del paquete.** El preflight lo calcula pero no
   queda archivado con el resultado, así que la sección de preparación sale
   `NO_EVALUADO` para aguas, metales y cofactores. Requiere persistir el informe
   de preparación junto a la corrida.
3. **`pose_validation` sin cablear.** Mientras no sea columna del ORM, el
   control físico será siempre `NO_EVALUADO`.
4. **Protonación, tautomería y estereoquímica.** El pipeline no las registra;
   hasta que lo haga se declaran `NO_EVALUADO`.
5. **Receptor original.** El paquete incluye el receptor *preparado* cuando
   existe; el PDB de origen se referencia por hash pero no se empaqueta.
6. **Top-K, ensemble y dominio por pose.** Sólo se incluye lo que la corrida
   serializó; no hay selección de poses ni comparación entre semillas.
7. **Importación del paquete.** Este sprint exporta y verifica; reconstruir un
   caso desde un ZIP es Hito 3.
8. **Firma y cifrado.** Fuera de alcance por decisión explícita: el paquete es
   verificable, no autenticado.

---

## 10. Fuentes

- `docs/53_MAPA_ALINEACION_PRODUCTO.md` §§3, 4, 5, 6.5, 6.6, 6.7, 9, 13
- `docs/45_API_CONTRACT_CURRENT.md` (regenerado con el endpoint nuevo)
- `docs/46_RUNTIME_INVENTORY.md`
- `backend/services/dossier/` — taxonomía, esquemas, modelo, PDF, paquete y
  verificador
- `backend/tests/test_dossier_model.py`, `test_dossier_package.py`,
  `test_dossier_api.py`
- Artefactos de QA visual: `output/pdf/sprint4a/`, regenerables desde la
  suite de dossier. No se versionan: son salidas de ejecución, no fuentes.
