# RS-03-PARAM-A-PRE — Sub-prerregistro A: Sage + NAGL nativo (cargas) sobre los 116 ligandos train

**Fecha:** 2026-08-16
**Rama:** `experimentos/ruta-c-molflex`
**Estado:** PREREGISTRO (nada ejecutado bajo este registro; sin seal, sin finish)
**Tipo:** sub-prerregistro del experimento **RS-03-PARAM-A** (política del laboratorio: prerregistro y ejecución son experimentos distintos; NO se usa `maintain` para incorporar resultados a un prerregistro sellado).
**Referencia sellada (contrato general):** `RS-03-PARAM-PRE` sellado (`7dfa3b8`) — PRE maestro de la familia RS-03-PARAM. Este sub-prerregistro lo referencia y lo refina para el alcance A; **no lo modifica ni lo des-sella** (nada sellado se toca).

---

## 1. Relación con el PRE maestro

El PRE maestro `RS-03-PARAM-PRE` (sellado en `7dfa3b8`, decisión GO procedimental) congela el contrato general de la parametrización de ligando validada: hipótesis, 6 estratos químicos obligatorios, 11 requisitos primarios, regla AM1-BCC estratificada y política de prerregistro separado.

La familia RS-03-PARAM se divide en:

- **RS-03-PARAM-A** (este sub-prerregistro): parametrización OpenFF **Sage + NAGL nativo** (cargas) sobre los 116 ligandos train.
- **RS-03-PARAM-B** (sub-prerregistro separado `RS-03-PARAM-B-PRE`): referencia **AM1-BCC** estratificada (caracterización, no selector).
- **RS-03-PARAM**: agregación final de A y B contra el contrato del PRE maestro.

Los sub-prerregistros referencian el PRE maestro; no lo reemplazan ni lo modifican.

---

## 2. Alcance

- Parametrización con **OpenFF Sage 2.2.1** (tipos de átomo, enlaces, ángulos, torsiones, vdW) + **cargas NAGL nativas** del modelo de producción `openff-gnn-am1bcc-1.0.0.pt` sobre los **116 ligandos train**.
- Serialización del sistema (interchange) y chequeos por ligando (energía finita, conservación de carga, mapeo biyectivo).
- **NO es AM1-BCC**: la referencia `antechamber`+`sqm` es el alcance de B (`RS-03-PARAM-B-PRE`); aquí no se ejecuta.
- **NO es el RS-03 físico**: ningún resultado de este experimento se usa como mejora de scoring ni se evalúa contra val40/test/D-RC-CONFIRM.

---

## 3. Entorno real (pin exacto)

Contenedor Ubuntu `moldesign-science:latest` en el servidor `192.168.1.64` (Micromamba 1.5.10, canal conda-forge, Python 3.11):

| Componente | Versión / pin | Nota |
|---|---|---|
| `openff-toolkit` | 0.18.0 | toolkit OpenFF |
| `openff-nagl` | 0.5.5 | cargas GNN nativas |
| `openff-nagl-models` | 2025.9.0 | paquete de modelos NAGL |
| `openff-interchange` | 0.5.2 | serialización del sistema |
| RDKit | 2026.03.1 | sanitización y lectura SDF |
| OpenMM | 8.5.2 | evaluación de energía |
| XGBoost | 3.2.0 | dependencia del entorno |
| AmberTools | `antechamber` + `sqm` funcionales | se usan SOLO en B, no en A |
| Sage (offxml) | `openff-2.2.1.offxml` (primario), `openff-2.2.0.offxml` | force field |
| Modelo NAGL | `openff-gnn-am1bcc-1.0.0.pt` (**producción, NO RC**) | SHA-256 `7981e7f5b0b1e424c9e10a40d9e7606d96dcd3dd2b095cb4eeff6829f92238ee` |

Test de humo de aspirina ya ejecutado en el entorno: `|Σq| = 3.33×10⁻¹⁶ e ≤ 1×10⁻⁴ e` ✓ (conservación de carga del pipeline).

Los SHA-256 del offxml de Sage y del modelo NAGL se registran en el manifest de la ejecución (RS-03-PARAM-A): **nunca se acepta un artefacto cuyo SHA no quede registrado** (PRE maestro §3).

---

## 4. Topología aprobada

- Cliente `scripts/moldesign_client.py` (paramiko) desde **Windows** contra el servidor `192.168.1.64`.
- Contenedor **efímero** por corrida:
  `docker run --rm -v /home/srcacahuate619/moldesign-env:/workspace -w /workspace moldesign-science:latest python /workspace/scripts/run_rs03_param_a.py`
- Los **116 SDF** se suben al workspace remoto (rsync/scp); los resultados se descargan con `download_artifacts`.
- Transferencia **binaria, sin normalización EOL**: los SHA-256 son reproducibles Windows/Ubuntu byte a byte.
- `scripts/experiment_manifest.py` sella **en Windows** (los hashes del sello se computan sobre los archivos ya descargados).
- El túnel 8001 **NO se usa**.

---

## 5. Gate de A — los 11 requisitos del PRE maestro §4 aplicados a NAGL nativo

Gate de aceptación de A (sin AM1-BCC: la referencia AM1-BCC es B y no forma parte del gate de A):

1. **Versión + SHA registrados**: `openff-2.2.1.offxml` (versión y SHA-256) y `openff-gnn-am1bcc-1.0.0.pt` (SHA-256 `7981e7f5…`, producción) registrados en el manifest de ejecución.
2. **Cero descargas de modelos durante la ejecución** (todo materializado y verificado previamente en la imagen).
3. Carga formal derivada del **ligando sanitizado** (nunca inferida de PDBQT; nunca presupuesta cero).
4. `|Σq − formal_charge| ≤ 1×10⁻⁴ e` por ligando.
5. Mapeo atómico **biyectivo** y `atom_order_hash` registrado.
6. **Cero fallback silencioso** (si el modelo falla, el resultado primario es `missing/failed`; cargas alternativas solo como sensibilidad secundaria explícita, jamás sustituto silencioso).
7. Cobertura global **≥ 95%** de los 116 ligandos train.
8. Cobertura **≥ 90% en cada uno de los 6 estratos** del PRE maestro §2 (neutros/ionizados, halogenados, azufre/fósforo, rangos de MW, rotatable bonds, fragmentos/drug-like/extremos fuera de dominio).
9. **Energía finita** y sistema **serializable** para el **100%** de los ligandos parametrizados.
10. Cargas **deterministas**: diferencia máxima **≤ 1×10⁻⁶ e** entre dos ejecuciones.
11. Fallos **clasificados por química** y **NUNCA convertidos en energía cero**.

---

## 6. Cohorte

Exclusivamente los **116 ligandos train**; **cero** val40, test o D-RC-CONFIRM.

---

## 7. Sin claim de mejora

Este experimento **NO reclama mejora** de scoring ni de recuperación de hits. Su único propósito es demostrar que la parametrización Sage 2.2.1 + NAGL nativo es una **base física correcta** (cobertura, determinismo, conservación de carga, cero fallback silencioso) que reemplaza el tipado heurístico de `molchamb_v2.py:65`, como exige el PRE maestro. La comparación descriptiva contra AM1-BCC corresponde a B y la agregación final a RS-03-PARAM.
