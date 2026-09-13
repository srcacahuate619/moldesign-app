---
titulo: "El testigo comparaba un ligando sin torsiones contra uno con seis"
entradilla: "Vina divide la afinidad por (1 + w_rot · N_rot). El salto de escala vale 1.055 kcal/mol medianos y el déficit que se estaba leyendo como fallo de búsqueda valía 0.491. Noventa y ocho segundos de cómputo retiraron un instrumento."
---

`MF-29-EMP` se quedó `INCONCLUSIVE` porque sus dos instrumentos preregistrados apuntaban en
direcciones opuestas. La cantidad primaria decía que subir el presupuesto no compra nada
—3 de 48—. El testigo decía que la búsqueda fallaba en el 70.8% de los complejos.

Cuando dos instrumentos válidos se contradicen, no se elige el que gusta. Se mide si alguno
de los dos es válido.

## El defecto, en una línea

`MF-13` escribía el `rigid_str` de `molflex.escribir_pdbqt` —`ROOT / átomos / ENDROOT /
TORSDOF 0`— y `MF-29-EMP` dockeaba `conf0.flex.pdbqt`, con hasta seis torsiones activas.

Vina divide la afinidad por `(1 + w_rot · N_rot)`.

> **Un ligando sin torsiones no paga esa penalización y uno con seis sí, para la misma
> pose.**

Los dos números nunca estuvieron en la misma escala. El «déficit» del cristal contra el
brazo masivo mezclaba física con contabilidad de torsiones.

## El diseño: cambiar una sola cosa

Se repitió `MF-13` con **un único cambio** —el `flex_str` en vez del `rigid_str`— y todo lo
demás idéntico: mismo tipado de Meeko, mismo receptor, misma caja de 25 Å, misma semilla 42,
mismo binario en el mismo contenedor.

Los umbrales se sellaron en `MF-29-EMP-COR-PRE`, **antes de correr**, con el hash del script:
**≤0.30 → ARTEFACTO DE ESCALA**, **≥0.70 → EL TESTIGO SOBREVIVE**, intermedio → **MIXTO**.

Y antes del primario, dos gates de validez, porque una preparación distinta podría no ser
comparable:

| Gate | Criterio | Resultado |
|---|---|---|
| **G1** | TORSDOF del cristal flexible == el de `conf0.flex.pdbqt` en ≥95% | **48/48 = 1.0** |
| **G2** | deriva mediana del `--local_only` ≤ 2.0 Å | **0.3425 Å** |

Los 0.3425 Å son casi idénticos a los 0.322 Å que derivó el rígido en `MF-13`: la relajación
local mueve el cristal lo mismo en las dos preparaciones.

## Qué salió

| Cantidad | Valor |
|---|---:|
| **Salto de escala** (mismo cristal, flexible − rígido) | **+1.055** medianos · máx +3.895 · mín −0.293 |
| Déficit que el testigo leía | +0.491 |
| **Déficit corregido**, a igual escala | **−0.406** |
| Complejos donde el masivo puntúa mejor por >0.10 | **36 de 48** |
| Complejos donde el cristal aún gana | **4 de 48** → `f` = 0.0833 |

`f` = 0.0833 está por debajo de 0.30: **ARTEFACTO DE ESCALA**.

El artefacto solo —1.055— cubre de sobra el déficit que se estaba leyendo como fallo de
búsqueda —0.491—. Corregido, el signo se invierte: lo que la búsqueda encuentra iguala o
supera el valor del cristal relajado a igual escala.

Los cuatro que sobreviven, con su deriva local, que en todos es menor de 0.35 Å:

| Complejo | Estrato | Cristal flex | Masivo | Déficit | Deriva |
|---|---|---:|---:|---:|---:|
| `1k9s` | RESTO | −9.507 | −8.496 | +1.011 | 0.237 Å |
| `1add` | CONTROL | −8.916 | −8.366 | +0.550 | 0.229 Å |
| `1ax0` | RESTO | −6.513 | −5.976 | +0.537 | 0.350 Å |
| `1flr` | CONTROL | −12.257 | −11.977 | +0.280 | 0.221 Å |

## El modelo lo anticipaba, y por eso no bastaba

Con `w_rot = 0.05846` y el TORSDOF real de cada complejo, la penalización **sola** predecía
un déficit artefactual de **1.367** medianos, contra los 0.491 observados. Es decir: el
artefacto por sí solo predecía *más* déficit del que había.

Eso motivó el experimento y no lo sustituye. Una decisión de gate no se cambia con un modelo
algebraico de la fórmula del motor cuando medirlo cuesta **98 segundos**.

## Lo que pareció destapar, y no era — corregido el mismo día

Al cerrar este corrigendum se registró la sospecha de que `MF-13` arrastraba el mismo
desajuste, acompañada de una indicación exploratoria alarmante: sobre los 48 complejos del
solapamiento, la fracción «el cristal gana al mejor dock» caía de 0.396 a 0.021.

**Esa indicación era inválida y la sospecha se retiró.** `MF-13-ESCALA` lo midió:

| | |
|---|---:|
| Complejos donde el top-1 de `MF-13` viene de `molflex` —que dockea rígido— | **102 de 116** |
| Gate G2 de COLOCACION, como se midió | 23/33 = **0.6970** |
| El mismo gate restringido a poses de fuente **rígida** | 23/33 = **0.6970** |
| Complejos que cambian de veredicto | **0** |

`MF-13` comparaba rígido contra rígido: escala homogénea. El error estuvo en **suponer** que
las poses del conjunto v2 eran flexibles en vez de comprobarlo —`RC-F0-V2-EXT` ya había
medido que el 93.9% viene del protocolo rígido—. Y aquel 0.396 → 0.021 comparaba un cristal
**flexible** contra poses **rígidas**: el desajuste inverso, tan inválido como el que este
corrigendum retiró.

El `MIXTO` de `MF-13` se sostiene tal como está sellado.

Nada de esto toca lo que se midió aquí. El desajuste que este corrigendum retiró era real
—cristal rígido de `MF-13` contra el brazo masivo, que sí dockea flexible— y su magnitud
está medida.

## Hallazgo lateral, exploratorio

`1ew8` puntúa **+1.714** preparado flexible: positivo. `MF-13` ya lo había señalado —junto a
`1fkh`— como sistema probablemente mal montado, por su −2.181 rígido, y planteó que faltara
un cofactor, un metal o una agua estructural, o que la protonación estuviese mal. Verlo
cruzar a positivo **refuerza** esa hipótesis; no la establece.

## Límites declarados

1. **No reabre la cantidad primaria de `MF-29-EMP`** —masivo contra producción—, que ningún
   resultado de aquí puede tocar.
2. **No certifica optimalidad global.** `MF-29` sigue abierto.
3. Cohorte de 48 y no 50: el brazo masivo de `1mmr` y `1nm6` expiró, y eso lo recupera
   `MF-29-EMP-EXT`.
