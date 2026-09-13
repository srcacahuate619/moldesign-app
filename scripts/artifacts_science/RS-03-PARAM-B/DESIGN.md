# RS-03-PARAM-B — Referencia AM1-BCC estratificada (método y procedencia)

> Este documento describe **cómo** se produjo B. Los resultados y su lectura van
> en `LECTURA.md`; las cifras agregadas, en `metrics.json`.

## Contexto

- **Prerregistro**: `RS-03-PARAM-B-PRE` sellado GO (`147abb1`), que refina el PRE maestro `RS-03-PARAM-PRE` (`7dfa3b8`).
- **Entrada**: `RS-03-PARAM-A` sellado GO (`93541c9`) — 116/116 ligandos train parametrizados con Sage 2.2.1 + NAGL `openff-gnn-am1bcc-1.0.0`, determinismo 2.78e−17.
- **Naturaleza de B**: caracterización **descriptiva**. AM1-BCC es referencia estratificada, **no verdad absoluta**. El PRE maestro §4 prohíbe seleccionar NAGL mirando RMSD o Top-1, y B no acepta ni rechaza NAGL.

## Incidencia del 2026-08-17 y por qué B se recalculó completo

La primera ejecución de B produjo 102 PASS y 14 timeouts a 300 s. La re-ejecución parcial de esos 14 con `--timeout 1200` escribió **en el mismo directorio de salida** que la corrida principal, sobrescribiendo `per_complex.jsonl`, `metrics.json` y `failures.jsonl` tanto en el servidor como en la copia local. **Los 102 resultados originales se perdieron sin copia recuperable.**

Consecuencias, todas asumidas explícitamente:

1. B se **recalcula completo** (116/116), no se reconstruye a partir de fragmentos.
2. El runner gana `--out-name`: cada corrida escribe en su propio directorio y **la sobrescritura entre corridas deja de ser posible**. Los shards son disjuntos por construcción y el script de fusión aborta si detecta un `pid` duplicado o si la cohorte no cierra en los 116 PASS de A.
3. El recálculo se aprovechó para **cerrar dos requisitos del prerregistro que el runner anterior no cumplía** (§5.5 y §5.6, abajo). Un merge de resultados viejos y nuevos habría mezclado dos esquemas distintos; el recálculo completo garantiza un único esquema uniforme.

## Cobertura del prerregistro

| PRE-B | Requisito | Implementación |
|---|---|---|
| §5.1 | Cohorte = los 116 train que A parametrizó | `a_rows` filtrado por `status == PASS` de `RS-03-PARAM-A/per_complex.jsonl` |
| §5.2 | AM1-BCC con conservación de carga reportada | `antechamber -c bcc -nc <carga formal del ligando sanitizado>`; se registra `delta_q_am1bcc_vs_formal_e` |
| §5.3 | Comparación por átomo sobre el mapeo biyectivo | **Verificado**, no asumido: elemento a elemento contra el mol sanitizado **y** por coordenadas (`max|Δr| ≤ 5e−3 Å`). Si no casa, el ligando es FAIL, nunca comparación silenciosa |
| §5.4 | Carga molecular en ambos métodos | `sum_q_nagl`, `sum_q_am1bcc`, `delta_mol_charge_e` |
| §5.5 | Dipolo si está disponible | Dipolo de cargas puntuales sobre la geometría del SDF, para NAGL y AM1-BCC, con origen en el centro geométrico (declarado: para especies ionizadas el dipolo depende del origen) |
| §5.6 | Estabilidad de energías | Energía de punto único en vacío con Sage 2.2.1 + OpenMM, plataforma **Reference** (determinista, monohilo), para ambos juegos de cargas; se reporta `energy_finite` |
| §5.7 | Todo estratificado por los 6 estratos del PRE maestro | `strata_stats` por `is_ionized`, `has_halogens`, `has_sulfur_phosphorus`, `mw_stratum`, `rot_stratum`, `drug_likeness` |
| §5.8 | Sin gate de aceptación/rechazo de NAGL | `metrics.json` lleva `nota_selector`; ninguna métrica de B decide sobre NAGL |

El runner anterior emitía `dipolo_debye: null` siempre y no calculaba energías: §5.5 y §5.6 estaban **sin cubrir** antes de este recálculo.

## Ejecución

- **Entorno**: contenedor Ubuntu `moldesign-science:latest` en `192.168.1.64` (Micromamba, Python 3.11), con AmberTools (`antechamber` + `sqm`), openff-toolkit 0.18.0, OpenMM 8.5.2, RDKit 2026.03.1.
- **Shards**: 3 contenedores Docker independientes y simultáneos (`RS-03-PARAM-B-S1..S3`), 116 pids repartidos sin solapamiento. Los 14 ligandos que habían agotado el timeout de 300 s se repartieron entre los tres shards para equilibrar el coste. `--timeout 1200` en todos.
- **Aislamiento**: cada ligando se procesa en su propio `TemporaryDirectory` dentro de su contenedor, de modo que la paralelización no altera la química por ligando.
- **Fusión**: `scripts/merge_rs03_param_b.py` — unión por `pid` con aborto ante duplicados o cohorte incompleta; `metrics.json` se recalcula sobre la unión, nunca se copia el de un shard.

## Archivos

- `metrics.json` — agregados, estratos, procedencia de shards y notas de gobernanza.
- `per_complex.jsonl` — una línea por ligando: cargas AM1-BCC, `|Δq|` por átomo (media y máximo), cargas moleculares, dipolos, energías con ambos juegos de cargas, verificación de orden atómico y estratos.
- `failures.jsonl` — una línea por ligando fallido, clasificado por causa química.
- `LECTURA.md` — lectura de los resultados.
- `scripts/run_rs03_param_b.py`, `scripts/merge_rs03_param_b.py` — runner y fusión.
