# REC-01 — Auditoría reproducible de grids y hotspots sobre los 387 targets del catálogo

**Estado:** preregistrado, **sin ejecutar**.
**Fecha de preregistro:** 2026-08-17.
**Nivel de madurez (doc. 49 §3):** E1 — smoke/contrato determinista sobre cohorte completa. No puede afectar producción.
**Protocolo padre:** [`docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md`](../../../docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md) §7, fila REC-01.

---

## 1. Por qué este experimento y por qué ahora

El doc. 49 §19.1 (regla de futilidad, añadida 2026-08-17) bloquea RS-11/12/13 y
reasigna la prioridad a la **cartera B**. La justificación es la descomposición
de §9: el Top-1 global es `cobertura del oráculo × precisión condicional`, y la
evidencia sellada indica que el selector v0.6 es estable (~76% de precisión
condicional en val y test) mientras la cobertura varía 20 puntos entre splits.
El margen está en el generador, y el generador depende del receptor y del grid.

El entregable 8 (`D-MF-HARD-EXH4`) apunta en la misma dirección: en el estrato
hard, `vina_exh4` alcanzó la cobertura de la unión completa con 119 poses en vez
de 802. Antes de gastar más presupuesto en muestreo conformacional conviene
saber **cuántos targets del catálogo están apuntando al sitio equivocado**,
porque ningún generador puede cubrir un bolsillo que la caja no contiene.

`5TUN` (doc. 35) es el caso testigo conocido: grid desalineado ~7 Å en Z, con
`TYR89` y `GLU84` fuera de la caja. REC-01 responde si es una anomalía aislada
o la punta de un patrón.

## 2. Hipótesis

Los grids del catálogo de 387 targets contienen un subconjunto **acotado y
reproducible** de casos desalineados respecto al sitio de unión real. Auditarlos
separando HOLO de APO produce una lista de excepciones accionable **sin
re-docking**.

Hipótesis falsable en dos direcciones:

- si la fracción desalineada es grande, la prioridad del programa cambia (el
  catálogo es un pasivo científico, no un activo);
- si es pequeña y concentrada en APO, `5TUN` es representativo de una clase
  estrecha y el fix de REC-07 se generaliza a esa clase.

## 3. Alcance y prohibiciones

**Dentro de alcance:**

- los **387 targets** de `curated_targets.json`;
- los PDB locales de `data/target_library/` y `data/targets/` (verificado
  2026-08-17: cobertura 387/387, 100%);
- geometría: centro de grid declarado, tamaño de caja, hotspots declarados.

**Fuera de alcance y expresamente prohibido:**

- **cero docking**: este experimento no ejecuta Vina ni genera poses;
- **cero escrituras** en `curated_targets.json`, `curated_targets.csv`, en
  ninguna base de datos, ni en `rescoring/`. La auditoría es de sólo lectura;
  la corrección de cualquier target es un experimento posterior (REC-07 para
  `5TUN`, REC-03 para política de tamaño);
- **cero acceso** a `poses_val.jsonl`, `poses_test.jsonl` ni a `D-RC-CONFIRM`;
- ninguna decisión sobre el selector ni sobre Top-1.

## 4. Definiciones congeladas antes de ejecutar

### 4.1. Clasificación HOLO / APO

Determinista, derivada del PDB (el catálogo no tiene campo APO/HOLO):

- se recorren los `HETATM` del PDB y se descarta la lista `SKIP_ARTIFACT`
  de `backend/scripts/audit_grid_hotspots.py` (aguas, iones, crioprotectores,
  detergentes, azúcares, residuos modificados);
- los `COFACTORS` del mismo módulo se cuentan pero se **anotan por separado**:
  un cofactor no es un ligando drug-like y su centroide no es necesariamente el
  sitio de unión de interés;
- **HOLO** = existe al menos un heteroátomo no-artefacto con `>= 6` átomos
  pesados. El mayor por número de átomos pesados define el **ligando nativo**;
- **APO** = no existe ninguno;
- **HOLO_COFACTOR_ONLY** = sólo hay cofactores. Se reporta como estrato propio,
  no se mezcla con HOLO ni con APO.

El umbral de 6 átomos pesados se fija ahora y no se ajusta después de ver los
resultados.

### 4.2. Ground truth por estrato

- **HOLO**: centroide de los átomos pesados del ligando nativo. Es el ground
  truth fuerte.
- **APO / HOLO_COFACTOR_ONLY**: no hay ground truth de ligando. Se usa el
  **centroide de los CA de los hotspots declarados** como referencia débil, y
  todo resultado de este estrato se marca `ground_truth=debil` y es
  **descriptivo**, sin inferencia fuerte. Esta es exactamente la situación de
  `5TUN`.

### 4.3. Métricas por target

1. `d_centro` — distancia euclídea entre el grid center declarado y el ground
   truth del estrato.
2. `contencion_ligando` — fracción de átomos pesados del ligando nativo dentro
   de la caja declarada (sólo HOLO).
3. `contencion_hotspots` — fracción de CA de hotspots declarados dentro de la
   caja.
4. `hotspots_validos` — fracción de hotspots declarados que existen realmente
   como residuo en el PDB (cadena + numeración).
5. `margen_min` — distancia mínima desde cualquier átomo del ligando/hotspot al
   borde de la caja; negativa si está fuera.

Convención de caja: caja axis-aligned centrada en `(grid_center_x/y/z)` con
semilados `grid_size_*/2`. Sin rotación. Coordenadas en Å.

### 4.4. Criterio de excepción (preregistrado)

Un target entra en la **lista de excepciones** si cumple al menos uno:

| Código | Condición | Estrato aplicable |
|---|---|---|
| `E1_CENTRO_LEJOS` | `d_centro > 6.0 Å` | HOLO (fuerte) |
| `E2_LIGANDO_RECORTADO` | `contencion_ligando < 1.0` | HOLO |
| `E3_HOTSPOTS_FUERA` | `contencion_hotspots < 0.80` | todos |
| `E4_HOTSPOTS_INVALIDOS` | `hotspots_validos < 0.80` | todos |
| `E5_HOTSPOTS_AUSENTES` | menos de 5 hotspots declarados | todos |
| `E6_SIN_PDB` | no se localiza PDB local | todos |
| `E7_PDB_NO_PARSEABLE` | el PDB existe pero no parsea | todos |

El umbral de 6.0 Å para `E1` procede del propio `audit_grid_hotspots.py`, que
ya reporta bandas 4/6/10/15 Å; se elige 6.0 Å porque `5TUN` (~7 Å) debe quedar
capturado y porque una caja típica de 22–30 Å tolera desalineamientos menores
sin perder el ligando. No se ajustará tras ver la distribución.

Sondeo previo declarado (no consume el gate): de los 387 targets, **380
declaran >=5 hotspots, 4 declaran entre 1 y 4, y 3 declaran 0**. Esos 7 son
candidatos conocidos a `E5` antes de ejecutar.

## 5. Gates de decisión

| ID | Gate | Criterio |
|---|---|---|
| G1 | **Cobertura total** | los 387 targets aparecen en `per_complex.jsonl` con veredicto explícito; 0 omisiones silenciosas. Un target que falla se registra en `failures.jsonl` con su causa, no se descarta |
| G2 | **Clasificación determinista** | cada target recibe exactamente un estrato de `{HOLO, APO, HOLO_COFACTOR_ONLY}` mediante la regla §4.1, sin intervención manual |
| G3 | **Excepciones con criterio numérico** | toda excepción cita el código `E1…E7` y el valor que lo dispara; ninguna se añade por juicio |
| G4 | **Determinismo** | dos corridas independientes producen `per_complex.jsonl` byte-idéntico (excluyendo timestamps del manifest) |
| G5 | **Sólo lectura** | verificación explícita de que catálogo, DB y `rescoring/` conservan su SHA-256 tras la corrida |

**GO** = los cinco gates pasan. El resultado GO significa «la auditoría es
válida y su lista de excepciones es reproducible», **no** que el catálogo esté
sano. La fracción de excepciones es el resultado, no el gate.

**NO_GO** = falla cualquier gate. Un NO_GO aquí es un defecto del instrumento de
auditoría, y se corrige antes de leer conclusiones científicas.

## 6. Lo que este experimento NO decide

- No corrige ningún grid. `5TUN` y cualquier otro caso quedan documentados para
  REC-07 / REC-03.
- No afirma que un target excepcional produzca peor docking: eso exige el
  experimento pareado de REC-03, con docking, y no está autorizado aquí.
- No mide cobertura de oráculo ni Top-1.
- No toca la política de tamaño de caja (REC-03) ni la de assembly (REC-08).

## 7. Artefactos

```text
scripts/artifacts_science/REC-01/
  PREREGISTRO.md      (este archivo)
  manifest.json
  metrics.json        agregados por estrato y por familia
  per_complex.jsonl   un registro por target, los 387
  failures.jsonl      targets no auditables con su causa
  README.md
```

Ejecutor: `scripts/run_rec01_grid_audit.py` (nuevo; no modifica
`backend/scripts/audit_grid_hotspots.py`, que queda como activo original y se
reutiliza por composición según la política del doc. 49 §17).

Semilla preregistrada: 42. El experimento es determinista y no usa aleatoriedad;
la semilla se registra por contrato del manifest.
