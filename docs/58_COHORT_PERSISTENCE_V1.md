# 58 — Cohortes congeladas: persistencia durable e inmutable

**Estado:** 🟢 Vigente desde Sprint 5B. La cohorte se guarda y sobrevive al
reinicio. La ejecución llegó en Sprint 5C — ver
[59 — Ejecución durable](59_COHORT_EXECUTION_V1.md). Sigue sin haber dossier de
cohorte, ranking, PDF ni ZIP.

**Superficie:** `POST /evaluation/cohorts` · `GET /evaluation/cohorts` ·
`GET /evaluation/cohorts/{cohort_id}`

**Prerrequisito:** [57 — Comprobación previa de cohortes](57_COHORT_PREFLIGHT_V1.md).

---

## 1. Preflight y cohorte no son lo mismo

Es la distinción entera de este sprint:

| | Comprobación previa (57) | Cohorte persistida (58) |
|---|---|---|
| Qué es | un **dictamen** | un **registro** |
| Vive | en la respuesta HTTP | en SQLite, con su archivo |
| Se puede repetir | sí, da lo mismo | no se repite: se creó una vez |
| Sobrevive al reinicio | no | **sí** |
| Se puede editar | no aplica | **no, nunca** |

El dictamen es una función pura del archivo y del estudio: vuelve a pedirlo
mañana y sale idéntico —mientras no cambie la versión del validador—. El
registro tiene que seguir diciendo lo mismo **aunque esa versión cambie**,
porque es lo que una persona aceptó.

De ahí la decisión central: al congelar se guarda el **veredicto entero**, no
la receta para recalcularlo.

---

## 2. Qué queda congelado

```
cohorts
├── id, schema_version, name, status = "ready"
├── cohort_fingerprint            identidad científica (ver 57 §5)
├── source_filename               nombre BASE saneado, nunca una ruta
├── source_content_type
├── source_sha256                 del archivo tal como llegó
├── source_bytes                  el archivo entero, BLOB
├── source_size_bytes
├── normalized_study_json         la definición normalizada
├── preflight_snapshot_json       el CohortPreflightResult COMPLETO
├── provenance_json               con qué se congeló
├── user_id                       propietario
└── created_at
```

**El archivo y el veredicto, los dos.** Si sólo guardáramos las filas ya
interpretadas, dentro de seis meses nadie podría comprobar que la
interpretación fue fiel al archivo. Si sólo guardáramos el archivo, la
ejecución tendría que reinterpretarlo con las reglas de ese día — y una
molécula que hoy es `eligible` podría dejar de serlo mañana sin que nadie
tocara nada.

**El snapshot lleva TODAS las filas**, incluidas las inválidas y las
duplicadas, con su `row_index`, sus razones y sus avisos. El denominador de la
cobertura tiene que seguir siendo el del archivo que se subió.

### 2.1 Por qué BLOB en SQLite y no un archivo en disco

El límite de ingesta son 8 MB. Un archivo aparte introduce exactamente el
estado que este producto no quiere: una fila que dice tener un archivo que ya
no está, o un archivo huérfano que sobrevive a la fila que lo describía. Con el
BLOB, **la cohorte se guarda entera o no se guarda**: un `INSERT`, una tabla,
una transacción.

No hay tabla por fila. Las filas no tienen estado propio todavía; cuando lo
tengan —que es lo que introduce la ejecución— tendrán su tabla. Partirlas ahora
sólo añadiría una forma de que la mitad se guarde.

---

## 3. Flujo de creación

`POST /evaluation/cohorts` — `multipart/form-data` con `file`, `study` y
`expected_fingerprint`.

1. **Se valida la forma de `expected_fingerprint`** (`sha256:<64 hex>`). Es lo
   más barato y una huella con otra forma no puede coincidir con ninguna que
   este producto emita.
2. Se valida `study` (mismo contrato que 57: `extra="forbid"`, sin `ALL`, sin
   no finitos).
3. Se lee el archivo, con los límites de tamaño (8 MB) y de filas (500)
   aplicados **antes** de canonicalizar nada.
4. **Se RECALCULA el preflight** desde el archivo y el estudio.
5. Si el fingerprint calculado ≠ `expected_fingerprint` → **409**, cero
   escrituras.
6. Si `decision != ready` → **422**, cero escrituras.
7. Se persiste, atómicamente, con su procedencia.
8. **201** con el registro creado.

En ningún punto se ejecuta docking, se llama a ML, se lanza una tarea de fondo
ni se produce un score.

### 3.1 El resultado nunca llega del cliente

El endpoint **no acepta** un `CohortPreflightResult`. Sólo archivo, estudio y
huella; el veredicto lo recalcula el servidor. Si aceptáramos el resultado del
cliente, cualquiera podría congelar una cohorte que declara 500 moléculas
elegibles a partir de un archivo vacío, y el registro dejaría de ser evidencia
de nada.

`expected_fingerprint` no es una credencial: es la forma de que el servidor
compruebe que **el archivo que se está congelando es el que se enseñó**. El caso
real que atrapa es mundano: comprobar un archivo, cambiarlo, y aceptar.

### 3.2 Códigos

| Código | Cuándo |
|---|---|
| `201` | Cohorte congelada |
| `409` | El fingerprint recalculado no es el que el cliente aceptó |
| `422` | `study` inválido, huella malformada, límites excedidos, o cohorte `blocked` |
| `404` | La cohorte no existe **o no es tuya** |

---

## 4. Inmutabilidad

**No hay `PATCH`, ni `PUT`, ni `DELETE`.** La inmutabilidad no se vigila con
comprobaciones: no se implementa el verbo que la rompería.

Una vez creada, no cambia el receptor, ni la configuración, ni las filas, ni el
fingerprint, ni el archivo. Cambiar cualquiera de esas cosas produce **otra
cohorte**, con su propia comprobación previa y su propio identificador. La
anterior sigue exactamente como estaba.

Un `PATCH` que cambiara el receptor dejaría una cohorte cuyo fingerprint ya no
describe su contenido — y el fingerprint es lo único que permite afirmar que lo
ejecutado es lo que se aceptó.

### 4.1 Duplicados: dos cohortes iguales coexisten

`cohort_fingerprint` está indexado pero **no es único**. Dos cohortes con la
misma huella pueden convivir, y el nombre descriptivo puede repetirse.

No se deduplica en silencio: alguien creó las dos a conciencia, y retirarle una
sería decidir por esa persona. La política de duplicados —si algún día la hay—
es una decisión posterior, no un efecto secundario de una restricción de la
base.

---

## 5. Procedencia

`provenance_json` guarda, **sólo si se puede leer de verdad**:

| Campo | Origen |
|---|---|
| `preflight_contract_version` | `COHORT_PREFLIGHT_SCHEMA_VERSION` |
| `fingerprint_contract` | `cohort_preflight/v1` |
| `moldesign_version` | `api.main.APP_VERSION` |
| `rdkit_version` | `rdkit.__version__` en el instante de congelar |
| `created_at` | ISO 8601 UTC |

**Lo ausente se omite, no se inventa.** Si no se puede leer la versión de RDKit,
el campo no viaja: un `"desconocida"` escrito a mano se leería después como si
fuera un dato, y la procedencia existe justamente para distinguir «esto es lo
que había» de «esto es lo que supusimos».

`rdkit_version` es el campo que más va a importar: el snapshot congela el
veredicto de elegibilidad, y esa versión es la que lo produjo.

---

## 6. Qué significa `ready` — y qué no

Lo mismo que en la comprobación previa, ni un gramo más:

> **`ready` significa «entrada ejecutable».** Estas filas se pueden leer y esta
> configuración se puede aplicar a todas por igual.

- **No hay ninguna evidencia de docking.** No se ha calculado ninguna energía,
  ninguna pose, ninguna interacción.
- **No predice unión ni calidad farmacológica.**
- **No es un ranking.** No hay `total_score` ni ningún score 0-100.
- Una cohorte congelada es una **hipótesis lista para ejecutarse**, no un
  resultado.

---

## 7. La ejecución futura consume el snapshot

Cuando 5C ejecute una cohorte, tomará las filas `eligible` **del snapshot
persistido**. No volverá a leer el archivo con las reglas de ese día ni a
recalcular la elegibilidad con otra versión de RDKit.

Si lo hiciera, se ejecutaría una cohorte distinta de la que la persona aceptó
—posiblemente con más filas, posiblemente con menos— y el `cohort_fingerprint`
dejaría de identificar lo que de verdad corrió.

El archivo original sigue guardado para lo que de verdad sirve: poder auditar,
mucho después, que la interpretación fue fiel. Se lee por
`services/cohort/repository.py::load_cohort_source`, que **no tiene endpoint**:
el detalle publica el `sha256` para cotejar, y entregar el contenido es otra
operación, no un efecto secundario de mirar una cohorte.

---

## 8. Propiedad y fugas

- Sin sesión autenticada, el dueño es el usuario `demo`, como en el resto del
  escritorio (`api/routers/evaluation_access.py`).
- `GET` valida propiedad. Una cohorte ajena y una inexistente devuelven **lo
  mismo: 404**. Es deliberadamente distinto del `403` de
  `require_owned_molecule`: un 403 confirma que ese identificador existe en esta
  máquina.
- El listado **nunca carga el BLOB**: selecciona columnas explícitas y el
  archivo no está entre ellas.
- Los logs registran identidad —`cohort_id`, fingerprint, `source_sha256`,
  recuentos— y **nunca contenido molecular**. Un log con 500 SMILES es una copia
  del archivo en un sitio que nadie audita.
- `source_filename` se reduce a su nombre base con lista blanca: un navegador
  puede mandar `C:\Users\ana\cohorte.csv`, y guardar eso publicaría el nombre de
  usuario de Ana en cada respuesta.

---

## 9. Esquema de base de datos

`SCHEMA_VERSION` pasa de **3 a 4**. El cambio es **puramente aditivo**: una
tabla nueva, `cohorts`. Ninguna tabla existente cambia, y una base v3 recibe la
tabla por `create_all` al arrancar sin tocar nada de lo que ya guardaba.

---

## 10. El Batch histórico sigue intacto

`POST /evaluation/batch`, `GET /evaluation/batch/{id}`, `/export` y `/csv` no se
han tocado y **se ejercitan** en `backend/tests/test_batch_legacy_contract.py`:
se sube un archivo, se acepta el trabajo, se consulta el estado y se exporta.

Su estado sigue viviendo en un `dict` de módulo y se pierde al reiniciar. Es una
de las razones por las que existen las cohortes; este sprint le da durabilidad a
la superficie **nueva** y deja la vieja como está.

---

## 11. Dónde vive

```
backend/core/models.py                      CohortORM
backend/core/database.py                    SCHEMA_VERSION = 4
backend/services/cohort/schemas.py          CohortRecord · CohortListItem · CohortProvenance
backend/services/cohort/repository.py       persistencia, propiedad y saneado
backend/api/routers/evaluation_cohorts.py   las tres rutas nuevas
```

---

## 12. Reservado para 5C / 5D

- ~~Ejecución durable, tabla por fila y reanudación tras reinicio~~ — hechas en
  5C, ver [doc 59](59_COHORT_EXECUTION_V1.md).
- Métricas de cribado (EF, ROC-AUC) **después** de ejecutar, nunca antes.
- Dossier de cohorte y su paquete reproducible.
- Política de duplicados en las métricas.
- Verificación del receptor contra el catálogo (hoy sólo se valida la forma del
  `pdb_id`).
- Entrega del archivo original por HTTP, si algún flujo la necesita.
