# ENS-PILOT-01 — la piscina del ensemble contiene diversidad real

Bloque 1 de [`backend/audits/VALIDACION_EN_SERVIDOR.md`](../../../backend/audits/VALIDACION_EN_SERVIDOR.md).
Corrida el **2026-09-19** en la estación del mantenedor, en dos tramos.

## Qué demuestra y qué no

**Demuestra** que cada conformación entra a Vina con SU geometría y que la pose
entregada puede probar de cuál vino. Nada más.

**No demuestra ninguna ventaja del ensemble.** Eso es `ENS-PROD-01`, con
prerregistro, cohorte y 248 complejos, y sigue sin ejecutarse. Tampoco es un
redocking: los diez ligandos no son los nativos de 5TUN, así que **ninguna
afinidad de este artefacto es interpretable**. Se registran sólo porque el orden
de la piscina se decide con ellas.

Este piloto existe porque hasta el 2026-09-17 el camino del producto acoplaba K
veces la MISMA geometría (`ENS-05`). Lo que se había demostrado al corregirlo era
que Meeko recibe el SDF correcto de cada conformación; faltaba demostrar que la
piscina *contiene* diversidad.

## Resultado

| Medida | Valor |
|---|---|
| Ligandos sin error | **10/10** |
| SHA-256 de entrada todos distintos | **sí** (30 por ligando, 300 en total) |
| Poses con SHA que coincide con su generador | **90/90** |
| Conformaciones distintas en el top-9 | **9** (mediana) |
| Poses recuperadas por las seis puertas | **72/90** |

Los 18 fallos son **exclusivamente los dos macrociclos**, 9/9 cada uno. Los ocho
ligandos restantes recuperan 9/9. La causa está abajo y no es del ensemble.

### RMSD intra-piscina, mediana por ligando (Å)

| ligando | mediana | lectura |
|---|---:|---|
| cafeina | 0.026 | **control negativo**: 30 conformaciones distintas colapsan a la misma pose. En un ligando sin rotores el ensemble no aporta nada, y el número lo dice sin ambigüedad. |
| naproxeno | 0.784 | |
| aspirina | 0.890 | |
| indometacina | 0.985 | |
| ibuprofeno | 1.244 | |
| paracetamol | 1.338 | |
| celecoxib | 1.571 | |
| exaltolida | 2.037 | macrociclo |
| muscona | 4.397 | macrociclo |
| warfarina | **15.896** | **atípico, y no es un defecto del arreglo.** Sus 30 entradas eran distintas y sus 9 poses trazan a su conformación; lo que dice el número es que las poses caen en sitios muy separados de la caja, con sólo 4 conformaciones en el top-9. No se promedia con las demás ni se lee como «más diversidad». |

## Dos defectos que este piloto destapó

Ninguno de los dos lo introdujo `ENS-05`; son anteriores y ortogonales al
ensemble. Aparecieron aquí porque el bloque 1 exigía incluir macrociclos.

1. **El SDF de Meeko no se parseaba nunca.** Un ancla `$` en el `re.match` de
   `parse_vina_output_sdf` descartaba la cabecera real de Meeko
   (`>  <meeko>  (1) `), así que las poses llegaban vacías y **el respaldo de
   Open Babel se usó en 171 de los 172 acoplamientos** —el 172 estaba en vuelo—.
   Cero por Meeko.
2. **En macrociclos ese respaldo entrega una molécula falsa.** Open Babel no
   reconoce los tipos de pegado de Meeko: escribe dos carbonos reales del anillo
   como pseudo-átomos `*` y deja el ciclo abierto (exaltólida: 17 átomos y 14
   enlaces donde corresponden 17 y 17). La puerta G5 de `pose_recovery` hizo
   exactamente lo que debía —se negó a certificar—, y por eso los macrociclos
   dan `recuperadas 0/9`.

**Este artefacto mide el estado ANTERIOR al arreglo.** Ambos defectos se
corrigieron el mismo día para 1.0.1; verificado con las fixtures reales de
`backend/tests/fixtures/meeko_export/`, con Meeko las dos puertas pasan y la
composición del macrociclo vuelve idéntica a la de su confórmero de entrada. La
medida posterior al arreglo, si se hace, va en **otro directorio**: reusar el de
salida ya destruyó 102 resultados de `RS-03-PARAM-B`.

## Procedencia

Todo lo verificable está en [`entorno.json`](entorno.json) y
[`metrics.json`](metrics.json); aquí sólo lo que hay que saber para leerlos.

- Intérprete: el **distribuido** (`python-embed`, 3.11.9), no el de desarrollo.
- Vina 1.2.7, SHA-256 `e0c4b271…3cce5`; `vina_cpu = 0`.
- Receptor 5TUN de `REC-07`, SHA-256 `eceefe6d…0665f`.
- K = 30, 9 poses, semilla 42, **exhaustividad 32** — la del producto, no la de
  `MF-33-B-RET-R2`, que corrió a 8.
- Datos en `_work/data/`, aislados de los del usuario mediante `LOCAL_DATA_DIR`.

**La corrida fue en dos tramos.** Se interrumpió tras el cuarto ligando y se
reanudó con `--reanudar`, que **reescribe `entorno.json`**: su `inicio_utc` dice
`2026-09-20T02:19:49Z`, que es la reanudación, no el arranque real
(`2026-09-19T17:21:40Z`). Todo lo demás del entorno es idéntico byte a byte
—mismo Vina, mismo receptor, misma semilla, misma caja—, así que las cuatro
filas del primer tramo y las seis del segundo son comparables.

## Reproducir

```
python-embed/python.exe scripts/run_enspilot01_diversidad.py --salida <directorio NUEVO>
```
