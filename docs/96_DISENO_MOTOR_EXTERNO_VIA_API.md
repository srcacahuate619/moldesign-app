# 96 — Diseño del motor externo «Vía API»

**Estado:** diseño. Sólo existe la plaza visible en el menú; no hay conexión, configuración,
red ni cambios en el backend. Fecha: 2026-10-07. Autor de la decisión de producto: el propietario.

**Objetivo.** Que el menú de docking pueda alojar, algún día, un motor propio o de terceros
sin reescribir la rama de Vina ni la de ESMFold. Este documento fija **dónde** encaja y **cómo**,
para que la implementación (frontend primero, luego backend) no invente la forma por el camino.

---

## 1. Dónde encaja en el menú

Un grupo propio, **«Motor externo (API)»**, debajo de «Péptidos» y no dentro de él.

Motivo: un motor externo declara qué moléculas acepta. Puede ser de moléculas pequeñas, de
péptidos o de ambas. Meterlo dentro de «Péptidos» obligaría a que cada motor externo heredara esa
rama, y un docking de moléculas pequeñas por API no cabría.

- **Hoy:** una plaza «Vía API · Sin conectar», visible, no elegible.
- **Tras conectar:** una tarjeta por conexión **verificada**. Una conexión configurada pero no
  verificada no aparece como elegible.
- **Alternativa descartada:** dentro de «Péptidos», tal como aparecía en la lista original.
  Si el propietario la prefiere, es mover una entrada; el resto del diseño no cambia.

## 2. Qué es una conexión

Una conexión describe un servicio, no un motor. Sus campos, sin valores reales:

| Campo | Qué guarda | Quién lo declara |
|---|---|---|
| `id` | Identificador local estable | La app al crearla |
| `nombre` | Nombre visible | La persona |
| `url_base` | Dirección del servicio | La persona |
| `autenticacion` | `ninguna` o `cabecera` con clave | La persona |
| `aplica_a` | `pequenas`, `peptidos` o `ambas` | **La conexión**, no la molécula |
| `identidad` | Nombre y versión que responde el servicio | El servicio, al verificar |
| `estado` | `sin_conectar` · `configurada` · `verificada` · `error` | La app |

Sólo `verificada` es elegible. `configurada` significa que hay datos, no que el servicio responda.

## 3. Modelo de selección (frontend)

Hoy el estado es `DockingEngineConfig { engine: "vina"; peptideEngine: "esmfold" | null; gnnPrecision }`.

**No se añaden motores externos a `peptideEngine`.** Mezclar identificadores en ese campo ya
produjo una mentira de procedencia: `diffpepdock` estaba en el contrato, despachaba a ESMFold y
etiquetaba la corrida con su propio nombre (ENG-003, `services/docking/protocolo.py`).

Propuesta: un tipo que separe el origen:

```ts
type MotorElegido =
  | { tipo: "local"; motor: "vina" | "esmfold" }
  | { tipo: "api"; conexionId: string };
```

Y una función que traduzca la elección al payload que ya existe (`docking_engine`,
`peptide_docking_engine`), para no tocar el contrato de las corridas locales. Para `tipo: "api"`
no se produce payload hasta que exista el backend. La precisión GNN sólo aplica con
`tipo: "local"` y `motor: "vina"`.

## 4. Contrato con el backend (no implementar todavía)

- `GET /evaluation/engines` añade `externos: [...]`. Las conexiones no verificadas aparecen con su
  estado y su motivo, pero no son elegibles.
- La corrida recibe un campo nuevo, `motor_externo: { conexion_id }`. `docking_engine` se queda en
  `vina`, que es el motor local que se ejecuta.
- `validar_motor_solicitado` admite un id externo sólo si la conexión está verificada. Es la misma
  regla que ENG-001, extendida: lo que la interfaz ofrece tiene que estar verificado.
- La procedencia registra `origen: "api"`, el nombre y la versión que **reporta el servicio**, un
  hash del endpoint (sin credenciales ni URL en claro) y un hash de la respuesta. Nunca se etiqueta
  una corrida con un nombre que no produjo la respuesta.

## 5. Reglas que no se negocian

1. **Ningún motor externo sustituye a Vina en silencio.** Si la conexión falla, la corrida se
   abstiene o falla. No cae a Vina. Hoy la ruta ESMFold sí cae a Vina con exhaustividad 4
   (`services/docking/peptide_docking.py`, cerca de «Fallo en Nivel 3»). No copiar ese patrón.
2. **Sin red por defecto.** Una conexión externa envía moléculas y receptor fuera del equipo. La
   interfaz lo declara antes de ejecutar («esta corrida envía datos a <host>»). Que el producto
   deje de ser «sin red» sólo en esa corrida es una decisión del propietario (§7b).
3. **Secretos fuera de la interfaz.** Ninguna clave en `localStorage`, en la URL, en el estado del
   modal ni en el expediente. La interfaz sólo ve «clave guardada: sí / no».
4. **Nada no verificado es elegible.** «Probar conexión» es la única transición de `configurada`
   a `verificada`.

## 6. Qué queda hecho en esta versión

- La plaza `plaza-motor-api`, visible y no elegible, con sus textos `op_api_*` en español e inglés.
- Una prueba que comprueba que la plaza existe y que no hay un radio elegible con su nombre.
- Nada más: sin configuración, sin red, sin cambios en el backend ni en el payload.

## 7. Decisiones pendientes del propietario

a. ¿Grupo propio (propuesta) o dentro de «Péptidos» (lista original)?
b. ¿Se permite enviar moléculas y receptor a servicios externos? Cambia la promesa «funciona sin red».
c. ¿Dónde viven las claves: en el backend, o en el almacén de credenciales del sistema?
d. **ESMFold Pro.** Se retiró del menú como motor local sin ejecutar. Su servicio estaba previsto en
   `localhost:8300` (`esmfold_pro_api_url` en `backend/api/routers/evaluation.py`), que es exactamente
   el caso de una conexión API. Si se quiere conservar, es la primera conexión de esta plaza, no una
   entrada fija del menú.

> **Actualización 2026-10-07.** El plan por fases, con lo que los motores reales (DiffDock, Boltz-2) obligan a
> cambiar de este diseño —capacidades por conexión, la caja con «No aplica», la superposición al receptor—
> está en [`docs/97_PLAN_MOTOR_EXTERNO_VIA_API.md`](97_PLAN_MOTOR_EXTERNO_VIA_API.md). Donde §4 y §8 difieran, manda ese plan.

## 8. Para la implementación (frontend, antes que el backend)

1. Tipo `MotorElegido` (§3) y su traducción al payload actual.
2. Alta de conexión, «Probar conexión» y estados (§2).
3. Una tarjeta por conexión verificada en el grupo de §1.
4. Pruebas guardianas: (i) ninguna tarjeta elegible sin verificar; (ii) ninguna clave en
   `localStorage`, en la URL ni en el payload.

Archivos que toca: `components/interfaces/pro/ProOptionsModal.tsx` (la plaza, en el bloque
«Motor externo (API)»), `lib/motores.ts` (`puedeElegirse` se extiende a conexiones) y
`components/interfaces/pro/ProEvaluation.tsx` (`handleSubmit` y el payload).

`components/interfaces/pro/DockingEnginePanel.tsx` no lo usa nada y aún lleva los motores retirados.
Conviene borrarlo antes de empezar, para no duplicar la lista de motores.
