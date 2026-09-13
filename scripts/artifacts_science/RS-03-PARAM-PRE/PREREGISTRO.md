# RS-03-PARAM-PRE — Preregistro formal: parametrización de ligando validada (OpenFF Sage + NAGL congelado)

**Fecha:** 2026-08-16
**Rama:** `experimentos/ruta-c-molflex`
**Estado:** PREREGISTRO (nada ejecutado; sin seal, sin finish)
**Tipo:** prerregistro del experimento SEPARADO **RS-03-PARAM** (política del laboratorio: prerregistro y ejecución son experimentos distintos; NO se usa `maintain` para incorporar resultados a un prerregistro sellado).
**Referencias selladas (lectura):** `CAMPANA-2-PLAN` sellado (`41b7f09`) IT1 **QA-2(e)** y §3.4 — RS-03-PARAM como PRERREQUISITO OBLIGATORIO de RS-03: reemplazar el tipado heurístico de `molchamb_v2.py:65` (aproxima éteres como hidroxilos) por una parametrización de ligando validada; objetivo desktop: OpenFF Sage + modelo NAGL congelado por versión y SHA-256; referencia de validación AM1-BCC en subconjunto estratificado. `RS-08` sellado (`fa9cf70`, NO_GO) — consecuencias para el futuro RS-03 (ver §7).

---

## 1. Hipótesis

La parametrización OpenFF Sage + NAGL (cargas) sobre los **116 ligandos train** produce una base física correcta (cobertura, determinismo, conservación de carga, cero fallback silencioso) reemplazando el tipado heurístico de `molchamb_v2.py:65`.

Hasta completar RS-03-PARAM, la implementación de MM/GBSA-like se llama **"rescoring MM/GBSA-like de pose única"** (nomenclatura del maintainer, IT1/QA-2e); NO se usa el término "MM-GBSA validado" en Campaña 2.

---

## 2. Dominio químico (estratos OBLIGATORIOS)

Cobertura **≥ 90% en cada uno** de los seis estratos declarados sobre los 116 ligandos train:

1. **Neutros / ionizados** (resultados separados; la carga formal nunca se presupone cero).
2. **Halogenados** (no se excluyen por nombre: decide la cobertura real del parámetro).
3. **Azufre / fósforo**.
4. **Rangos de MW** (rangos declarados de masa molecular).
5. **Flexibilidad — rotatable bonds** (rangos declarados de enlaces rotables).
6. **Fragmentos, drug-like y extremos fuera de dominio** (pequeños fragmentos, compuestos drug-like y los extremos fuera del dominio modelable; su cobertura se reporta por separado, nunca se oculta).

---

## 3. Versiones (pin del entorno y artefactos)

Pin exacto al materializar el entorno de ejecución:

| Componente | Pin | Nota |
|---|---|---|
| `openff-toolkit` | 0.16.x | pin exacto a confirmar en el lock de ejecución |
| `openff-nagl` | pin de la versión del toolkit | pin exacto a confirmar en el lock de ejecución |
| `openff-nagl-models` | 0.1.x | modelo NAGL congelado; pin exacto a confirmar en el lock de ejecución |
| `openff-interchange` | pin compatible con el toolkit | pin exacto a confirmar en el lock de ejecución |
| Referencia Sage (offxml) | Sage 2.3.1 (o la 2.x más reciente razonable) | pin a confirmar en el lock de ejecución |

Los **SHA-256** del offxml de Sage, de los pesos NAGL y del modelo congelado se fijan en **RS-03-PARAM** al materializar los artefactos y son **GATE de ejecución** (ver §4): **nunca se acepta un artefacto cuyo SHA no quede registrado en el manifest de ejecución.**

---

## 4. Gate de RS-03-PARAM (copiado exacto del maintainer)

### Cohorte

Exclusivamente los **116 ligandos train**; **cero** val40, test o D-RC-CONFIRM.

### Requisitos primarios

1. Versión exacta y SHA-256 de Sage, NAGL y pesos del modelo.
2. **Cero descargas de modelos durante la ejecución** (todo materializado y verificado previamente).
3. Carga formal derivada del **ligando sanitizado** (nunca inferida de PDBQT; nunca presupuesta cero).
4. `|Σq − formal_charge| ≤ 1×10⁻⁴ e` por ligando.
5. Mapeo atómico **biyectivo** y `atom_order_hash` registrado.
6. **Cero fallback silencioso** (cargas Gasteiger u otras solo como sensibilidad secundaria explícita, jamás sustituto silencioso; si el modelo falla, el resultado primario es `missing/failed`).
7. Cobertura global **≥ 95%** de los 116 ligandos train.
8. Cobertura **≥ 90% en cada estrato químico declarado** (§2).
9. **Energía finita** y sistema **serializable** para el **100%** de ligandos parametrizados.
10. Cargas **deterministas**: diferencia máxima **≤ 1×10⁻⁶ e** entre dos ejecuciones.
11. Fallos **clasificados por química** y **NUNCA convertidos en energía cero**.

### AM1-BCC (referencia de validación)

- Referencia **estratificada**, NO "verdad absoluta".
- Reportar: diferencias por átomo, carga molecular, dipolo si está disponible y estabilidad de energías.
- **PROHIBIDO seleccionar NAGL mirando RMSD ni Top-1.**

---

## 5. Protocolo (esquema)

```
inventario de ligandos (SDF sanitizado, carga formal, mapeo biyectivo, atom_order_hash)
        │
        ▼
parametrización OpenFF (tipos, cargas NAGL congelado, normalización a carga formal)
        │
        ▼
serialización (interchange/system)
        │
        ▼
chequeos por ligando (energía finita, Σq)
        │
        ▼
estratos (cobertura ≥90% por estrato declarado)
        │
        ▼
determinismo (2 corridas, diferencia ≤ 1×10⁻⁶ e)
        │
        ▼
AM1-BCC estratificado como referencia descriptiva
        │
        ▼
reporte
```

---

## 6. Forecast (tiempo/coste por etapa)

| Etapa | Estimación | Notas |
|---|---|---|
| Inventario de ligandos | bajo (minutos–1 h) | SDF sanitizado, carga formal, mapeo, `atom_order_hash` |
| Parametrización OpenFF | bajo (minutos) | 116 ligandos, tipos + cargas NAGL congelado |
| Serialización (interchange/system) | bajo (minutos) | chequeos por ligando incluidos |
| AM1-BCC estratificado | medio (horas) | **requiere AmberTools**; subconjunto estratificado, no los 116 completos |

**La instalación del entorno es autorización separada** (no se ejecuta en este entregable): `openff-toolkit`, `openff-nagl-models`, `AmberTools` y el modelo NAGL congelado.

---

## 7. Caveat RS-08 (contexto del futuro RS-03)

Consecuencias del NO_GO de RS-08 (`fa9cf70`) para el futuro RS-03:

- **RS-08 queda fuera del camino primario** de la cascada.
- **margin-only será el router primario** del futuro RS-03 (el rival principal de RS-08 lo superó en el gate).
- **Máximo teórico: 5 hits recuperables@2** (espacio de mejora acotado).
- Los **60 casos no recuperables** (`sampling_needed`) indican un **problema dominante de generación/posición de poses** — el rescoring no puede recuperar lo que no existe.
- **Caveat inner-CV**: las probabilidades del inner-CV de RS-08 **NO son generalización receptor-disjoint** — el componente gigante de 55 complejos se dividió por PID, NO es component-disjoint.

---

## 8. Política del laboratorio (prerregistro separado)

- **Prerregistro y ejecución son experimentos separados**: este prerregistro (RS-03-PARAM-PRE) y la ejecución (RS-03-PARAM) son experimentos distintos.
- El **prerregistro sellado no recibe resultados vía `maintain`**: NO se usa `maintain` para incorporar resultados a un prerregistro sellado.
- Los **resultados se sellan juntos al final de la ejecución** (flujo completo de la ejecución: init → ejecución → seal con TODOS los assets → finish).