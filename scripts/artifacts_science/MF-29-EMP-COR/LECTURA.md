# MF-29-EMP-COR — El testigo comparaba un ligando sin torsiones contra uno con seis

## Diagnóstico: `ARTEFACTO DE ESCALA` — decisión `GO`

| Gate | Criterio preregistrado | Resultado |
|---|---|---|
| **G1** validez | TORSDOF del cristal flexible == el de `conf0.flex.pdbqt` en ≥95% | **PASS — 48/48 = 1.0** |
| **G2** validez | deriva mediana del `--local_only` ≤ 2.0 Å | **PASS — 0.3425 Å** |
| **Primario** | `f` = fracción donde el cristal flexible aún gana por >0.10 | **4/48 = 0.0833** → `ARTEFACTO DE ESCALA` |

Umbrales preregistrados en `MF-29-EMP-COR-PRE`, sellado **antes** de correr con el hash del
script: **≤0.30 → ARTEFACTO**, **≥0.70 → EL TESTIGO SOBREVIVE**, intermedio → **MIXTO**.

98 segundos de cómputo, 48 complejos, 4 workers.

## El defecto, en una línea

`MF-13` escribía el `rigid_str` de `molflex.escribir_pdbqt` —`ROOT / átomos / ENDROOT /
TORSDOF 0`— y `MF-29-EMP` dockeaba `conf0.flex.pdbqt`, con hasta 6 torsiones activas. Vina
divide la afinidad por `(1 + w_rot · N_rot)`. **Un ligando sin torsiones no paga esa
penalización y uno con seis sí, para la misma pose.**

## Los números

Cambiando **una sola cosa** —el `flex_str` en vez del `rigid_str`, mismo tipado de Meeko,
mismo receptor, misma caja de 25 Å, misma semilla 42, mismo binario en el mismo contenedor:

| Cantidad | Valor |
|---|---:|
| **Salto de escala** (mismo cristal, flexible − rígido) | **+1.055** medianos · máx **+3.895** · mín −0.293 |
| Déficit que el testigo de `MF-29-EMP` leía | +0.491 |
| **Déficit corregido**, a igual escala | **−0.406** |
| Complejos donde el masivo puntúa mejor por >0.10 | **36 de 48** |
| Complejos donde el cristal aún gana | **4 de 48** |

El artefacto solo —1.055— cubre de sobra el déficit que se estaba leyendo como fallo de
búsqueda —0.491—. Corregido, el signo se invierte.

Los cuatro que sobreviven, con su deriva local, que en todos es menor de 0.35 Å:

| Complejo | Estrato | Cristal flex | Masivo | Déficit | Deriva |
|---|---|---:|---:|---:|---:|
| `1k9s` | RESTO | −9.507 | −8.496 | +1.011 | 0.237 Å |
| `1add` | CONTROL | −8.916 | −8.366 | +0.550 | 0.229 Å |
| `1ax0` | RESTO | −6.513 | −5.976 | +0.537 | 0.350 Å |
| `1flr` | CONTROL | −12.257 | −11.977 | +0.280 | 0.221 Å |

### El modelo lo había anticipado, y la medición no depende de él

Con `w_rot = 0.05846` y el TORSDOF real de cada complejo, la penalización sola predecía un
déficit artefactual de **1.367** medianos contra **0.491** observado: el artefacto por sí
solo predecía *más* déficit del que había. Eso motivó el experimento y no lo sustituye —una
decisión de gate no se cambia con un modelo de la fórmula cuando medirlo cuesta minutos—.

## Consecuencia registrada en MF-29-EMP

Su testigo deja de ser instrumento válido y se retira. La cantidad primaria
—masivo vs producción, 3 de 48— queda sola, su lectura preregistrada `OBJETIVO` se sostiene
y **su decisión pasa de `INCONCLUSIVE` a `GO`**. No se movió ningún umbral ni se eligió
instrumento después de ver el resultado: se midió que uno de los dos no medía lo que decía
medir.

También queda **anulado el confusor del confórmero** que `MF-29-EMP` había declarado como
siguiente paso obligado. No hace falta: el déficit que se le iba a atribuir no existe.

## Lo que pareció destapar, y no era — corregido el mismo día

Al cerrar este corrigendum se registró la sospecha de que `MF-13` arrastraba el mismo
desajuste, porque comparó ese cristal **rígido** contra `score_top1_dock`, del conjunto v2.
La acompañaba una indicación exploratoria alarmante: sobre los 48 complejos del solapamiento
la fracción «el cristal gana al mejor dock» caía de 0.396 a 0.021.

**Esa indicación era inválida y la sospecha se retiró.** `MF-13-ESCALA` lo midió:

| | |
|---|---:|
| Complejos donde el top-1 de `MF-13` viene de `molflex` —que docka `conf{cid}.rigid.pdbqt`— | **102 de 116** |
| Gate G2 de COLOCACION, como se midió | 23/33 = **0.6970** |
| Gate G2 restringido a poses de fuente **rígida** | 23/33 = **0.6970** |
| Complejos que cambian de veredicto | **0** |

`MF-13` comparaba **rígido contra rígido**: escala homogénea. El error estuvo en suponer que
las poses del conjunto v2 eran flexibles en vez de comprobarlo —`RC-F0-V2-EXT` ya había
medido que el 93.9% viene del protocolo rígido—. Y aquel 0.396 → 0.021 comparaba un cristal
**flexible** contra poses **rígidas**: el desajuste inverso, tan inválido como el que este
corrigendum retiró.

El `MIXTO` de `MF-13` se sostiene tal como está sellado, y con él el «~70% de fallo de
búsqueda» que usan el §8 y la justificación de la cartera C.

**Nada de esto toca lo que se midió aquí.** El desajuste que este corrigendum retiró era
real —cristal rígido de `MF-13` contra el brazo masivo de `MF-29-EMP`, que sí dockea
`conf0.flex.pdbqt`— y su magnitud, 1.055 kcal/mol, está medida.

## Hallazgo lateral, exploratorio

`1ew8` puntúa **+1.714** preparado flexible: positivo. `MF-13` ya lo había señalado —junto a
`1fkh`— como sistema probablemente mal montado, por su −2.181 rígido, y planteó que faltara
un cofactor, un metal o una agua estructural, o que la protonación estuviese mal. Verlo
cruzar a positivo **refuerza** esa hipótesis; no la establece.

## Límites declarados

1. **No reabre la cantidad primaria de `MF-29-EMP`** —masivo vs producción—, que ningún
   resultado de aquí puede tocar.
2. **No certifica optimalidad global.** `MF-29` sigue **ABIERTO**.
3. Cohorte de 48 y no 50: el brazo masivo de `1mmr` y `1nm6` expiró.
