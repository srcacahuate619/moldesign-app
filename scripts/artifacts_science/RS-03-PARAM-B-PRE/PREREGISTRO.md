# RS-03-PARAM-B-PRE — Sub-prerregistro B: referencia AM1-BCC estratificada (caracterización, no selector)

**Fecha:** 2026-08-16
**Rama:** `experimentos/ruta-c-molflex`
**Estado:** PREREGISTRO (nada ejecutado bajo este registro; sin seal, sin finish)
**Tipo:** sub-prerregistro del experimento **RS-03-PARAM-B** (política del laboratorio: prerregistro y ejecución son experimentos distintos; NO se usa `maintain` para incorporar resultados a un prerregistro sellado).
**Referencia sellada (contrato general):** `RS-03-PARAM-PRE` sellado (`7dfa3b8`) — PRE maestro de la familia RS-03-PARAM. Este sub-prerregistro lo referencia y lo refina para el alcance B; **no lo modifica ni lo des-sella** (nada sellado se toca).

---

## 1. Relación con el PRE maestro

El PRE maestro `RS-03-PARAM-PRE` (sellado en `7dfa3b8`, decisión GO procedimental) congela el contrato general: AM1-BCC es **referencia de validación estratificada, NO "verdad absoluta"**, y queda **PROHIBIDO seleccionar NAGL mirando RMSD ni Top-1** (PRE maestro §4).

La familia RS-03-PARAM se divide en:

- **RS-03-PARAM-A** (sub-prerregistro `RS-03-PARAM-A-PRE`): parametrización OpenFF **Sage + NAGL nativo** sobre los 116 ligandos train.
- **RS-03-PARAM-B** (este sub-prerregistro): referencia **AM1-BCC** estratificada (`antechamber` + `sqm`).
- **RS-03-PARAM**: agregación final de A y B contra el contrato del PRE maestro.

Los sub-prerregistros referencian el PRE maestro; no lo reemplazan ni lo modifican.

---

## 2. Alcance

- Referencia **AM1-BCC estratificada** sobre los ligandos train parametrizados por A, vía `antechamber` + `sqm` (AmberTools) dentro del contenedor Ubuntu.
- Caracterización **descriptiva** de las cargas NAGL de A: comparación por átomo, por molécula y por estrato.
- **NO es selector**: B es referencia, no criterio. **PROHIBIDO seleccionar NAGL mirando RMSD ni Top-1**; ningún resultado de B acepta ni rechaza NAGL.
- **NO es el RS-03 físico**: ningún resultado de B se usa como mejora de scoring ni se evalúa contra val40/test/D-RC-CONFIRM.

---

## 3. Entorno

Mismo contenedor Ubuntu `moldesign-science:latest` del servidor `192.168.1.64` descrito en RS-03-PARAM-A-PRE §3 (Micromamba 1.5.10, conda-forge, Python 3.11), con:

- **AmberTools funcionales**: `antechamber` + `sqm` (generación de cargas AM1-BCC).
- **Sage `openff-2.2.1.offxml`** para la **serialización comparativa** de los sistemas cargados con AM1-BCC (mismo force field que A; difieren solo las cargas).
- RDKit 2026.03.1 (sanitización), OpenMM 8.5.2 (energías), openff-toolkit 0.18.0 / openff-interchange 0.5.2 (serialización).

---

## 4. Topología aprobada

Idéntica a A (RS-03-PARAM-A-PRE §4): cliente `scripts/moldesign_client.py` (paramiko) desde Windows contra `192.168.1.64`; contenedor **efímero** `docker run --rm -v /home/srcacahuate619/moldesign-env:/workspace -w /workspace moldesign-science:latest`; SDF ida/vuelta por transferencia **binaria sin normalización EOL** (SHA-256 reproducibles Windows/Ubuntu); `download_artifacts` para resultados; `scripts/experiment_manifest.py` sella **en Windows**; el túnel 8001 **NO se usa**.

---

## 5. Gate de B (referencia, no aceptación)

B es un experimento de **caracterización**: su gate es de **completitud del reporte**, NO de aceptación/rechazo de NAGL.

1. **Cohorte**: los 116 ligandos train que A parametrizó. **B espera si A no finalizó**: B solo corre sobre la cohorte efectivamente parametrizada por A; si A no alcanza el 100%, B corre sobre el subconjunto parametrizado y lo declara explícitamente.
2. AM1-BCC vía `antechamber` + `sqm` con **conservación de carga reportada** por ligando (`|Σq_AM1-BCC − formal_charge|` reportado; la carga formal es la del **ligando sanitizado**, la misma que usó A).
3. Reportar **|q_NAGL − q_AM1-BCC| por átomo** (sobre el mapeo biyectivo y `atom_order_hash` registrados por A).
4. Reportar **carga molecular** (Σq por ligando) en ambos métodos.
5. Reportar **dipolo si está disponible**.
6. Reportar **estabilidad de energías** (energía finita de los sistemas serializados con cargas AM1-BCC bajo Sage 2.2.1).
7. Todo lo anterior **estratificado por los 6 estratos** del PRE maestro §2 (neutros/ionizados, halogenados, azufre/fósforo, rangos de MW, rotatable bonds, fragmentos/drug-like/extremos fuera de dominio).
8. **Sin gate de aceptación/rechazo de NAGL**: prohibido concluir "NAGL aceptado" o "NAGL rechazado" desde B; **prohibido RMSD/Top-1** como criterio de selección.

---

## 6. Cohorte y cegamiento

Exclusivamente los **116 ligandos train** (los que A parametrizó); **cero** val40, test o D-RC-CONFIRM.

---

## 7. Sin claim científico

B **no produce claim científico** sobre la calidad de NAGL: es una **caracterización descriptiva** que alimenta la agregación final RS-03-PARAM, donde el contrato del PRE maestro (`7dfa3b8`) es el que decide.
