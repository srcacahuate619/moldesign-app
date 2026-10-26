# SUP-03-VALIDADOR-LIGANDO — registro previo (2026-10-25)

Escrito y commiteado **antes** de pasar ninguna molécula por el validador. Sale del inventario SUPUESTOS-01: Sol 6.1 lo encontró
(C-276 a C-279) y la semilla de Claude no lo tenía.

## La pregunta

Antes de acoplar, `chem/validator.py::validate_smiles` **rechaza** (error, no aviso) una molécula si cumple alguna de estas reglas:

| Regla | Dónde | Valor |
|---|---|---|
| R1 · carga formal neta | `core/config.py::max_total_formal_charge_abs` | \|carga\| > 2 |
| R2 · carga formal de un átomo | `core/config.py::max_atom_formal_charge_abs` | \|carga\| > 2 |
| R3 · radicales | `chem/validator.py::_check_chemical_plausibility` | cualquier electrón radical |
| R4 · varios fragmentos tras quitar sales | `core/config.py::strict_single_fragment_only` (`True`) | más de un fragmento después de `SaltRemover` |

Ninguna tiene una medida detrás. La preferencia del propietario (2026-10-07) es que el producto avise y no bloquee, salvo que algo
de verdad no se pueda ejecutar. La pregunta es cuánta química con actividad medida cae en estas reglas.

## Datos (ya existen en el repositorio)

| Conjunto | Fuente | n | ¿Actividad medida? |
|---|---|---:|---|
| A · VMAT2 | SMILES de `CAL-D-01-R4-2-VMAT2-8T69/_work/panel/shard-*/panel-*.terminal.json` | 89 | sí (Ki, patente) |
| B · NET | `CAL-8HFI-01/entrada/panel_congelado.csv`, columna `smiles` | 57 | sí (Ki, ChEMBL) |
| C · 5-HT1A | `data/chembl_5ht1a_actives.txt` | 494 | sí (ChEMBL) |
| D · señuelos DUD-E de 5-HT1A | `data/dude_5ht1a_decoys.smi` | 3000 | no: control descriptivo |
| E · conjuntos de benchmark | `completed_smiles` de los diez `data/benchmark_checkpoint_<diana>.json` (sin `.bak` ni `.last`), sin duplicados | — | mezcla de activos y señuelos: descriptivo |

## Medida

Cada SMILES pasa por `validate_smiles` con la configuración por defecto del producto, sin cambiarla. Cada rechazo se asigna a su
regla por el texto del error (R1–R4) o, si no es ninguna de las cuatro, a «otra» (tamaño, masa, átomos, lectura), que se informa sin
decidir. Se guardan todos los rechazados, con su SMILES, su conjunto y su motivo.

## Regla de decisión, por regla (R1–R4)

- **GO**: rechaza 0 moléculas de A ∪ B ∪ C (640 con actividad medida).
- **NO_GO**: rechaza al menos una. La regla bloquea química con actividad medida. Se propondrá convertirla en aviso, salvo que una
  medida aparte demuestre que el pipeline no puede ejecutar esas moléculas. Eso no lo mide este experimento.

Decisión global: GO si las cuatro reglas son GO; NO_GO si alguna lo es.

## Límites declarados de antemano

- Los SMILES de entrada son los que el usuario escribiría (padres neutros en su mayoría). La protonación que viene después puede
  llevar a cargas mayores; este experimento no mira esa etapa.
- 640 moléculas de tres dianas no son el espacio de los fármacos: un GO dice que la regla no muerde aquí, no que nunca muerda.
