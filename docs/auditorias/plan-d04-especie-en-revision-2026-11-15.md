# Plan de D-04: ampliar «especie en revisión» en 1.0.4

| Campo | Registro |
|---|---|
| Fecha | 2026-11-15 |
| Código de referencia | `ffddd7e9`, rama `codex/release-hygiene`, sin empujar |
| Decisión del propietario | Se hace en 1.0.4 (antes estaba aplazada a 1.0.5), opción A de D-04: **declarar, sin tocar la tabla de pKa** |
| Investigación delegada | [`docs/encargos/ENCARGO_D04_ESPECIE_EN_REVISION_20261115.md`](../encargos/ENCARGO_D04_ESPECIE_EN_REVISION_20261115.md) |
| Evidencia de partida | [D04.md](investigacion-1.0.4/D04.md) · [segunda opinión, §D-04](segunda-opinion-gemini-1.0.4-2026-11-15.md) · AMINA-PKA-01 (`git show 665a473b:docs/auditorias/AMINA-PKA-01.md`) |

## Qué se hace y qué no

**Se hace.** `backend/chem/especie_en_revision.py` reconoce hoy cuatro motivos de revisión. Se añaden como máximo cuatro más, uno por entorno que la
investigación acepte: α-aminoéster/α-aminocetona, N-alquilmorfolina, propargilamina y β-sulfona. Cada uno mueve la «Especie acoplada» de
*registrada* a *revisar*, con un motivo que cita un ejemplo de la literatura y dice que no es la molécula de la persona.

**No se hace.** No se cambia el 9,8 de `amina_alifatica`, ni lo que se acopla, ni LogD, ni CNS-MPO, ni ningún score. La razón está medida: sustituir 9,8 por
8,3 deja el estado de carga a pH 7,4 igual (139/193 con las dos cifras). Cambiar la tabla pide un experimento sellado y un protocolo propio; declarar, no.

## Por qué hay que esperar a la investigación

Los cuatro entornos y sus SMARTS salen de una segunda opinión cuyas citas web **no se han verificado**, y los pKa de las cuatro clases no están medidos en este
repositorio (el único caso con cifra propia es el del nitrilo, ya cubierto). Implementar ahora sería convertir una hipótesis en una regla visible para quien
use el producto. Por eso el trabajo se parte en cuatro fases con una puerta entre la 1 y la 2.

## Fases

| Fase | Quién | Qué | Puerta para pasar a la siguiente |
|---|---|---|---|
| **0 · Hecha** | Esta sesión | Evidencia reunida, encargo escrito, consumidores y riesgos medidos (abajo) | El propietario envía el encargo |
| **1 · Investigación** | Modelo dedicado | Responde P1–P7 del encargo en `docs/auditorias/investigacion-d04-2026-11-15/` | Se repiten 3 cifras al azar, se comprueba el 10 % de las citas, los SMARTS recorren los controles del repositorio y **ninguna** de las 17 `CORRECTAS_VERIFICADAS` se marca |
| **2 · Decisión** | Propietario | Qué clases entran, si la morfolina NH y la α-aminoamida entran y con qué texto | Decisión escrita en el registro de decisiones del acta |
| **3 · Implementación** | Esta sesión | Código, pruebas, textos en inglés y registro (abajo) | Pruebas verdes y los dos controles de blast radius de la fase 4 |
| **4 · Efecto medido** | Esta sesión | Cuántas moléculas de MolFlex (203) y de 8T69 (89) cambian de estado, y que las ocho corridas doradas y la instantánea del dossier no se muevan sin explicación | Cifras en `docs/versions/1.0.4_cambios.md` |
| **5 · Lotes** | Esta sesión, si el propietario lo decide | Que las cohortes declaren la especie por fila con el mismo `motivos_de_revision`, para heredar las clases nuevas sin código aparte. Hoy la cohorte no dice qué especie acopló ([medido](lotes-frente-a-evaluacion-2026-11-15.md), punto 2) | Cambia el contenido de los paquetes de cohorte nuevos; las cohortes guardadas no se reescriben |

## Fase 3, en detalle

Se añaden entradas a [`especie_en_revision.py`](../../backend/chem/especie_en_revision.py), con el mismo patrón que `_AMINA_CON_ATRACTOR`:
`MotivoDeRevision(código, texto)`, SMARTS **sobre la especie acoplada** (N protonado), y una línea en `revisiones_en_mol` que devuelve el motivo con los átomos
que lo provocan. Se conserva en `TEXTOS_ANTERIORES_DE_MOTIVOS` cualquier texto que se reescriba, para que las corridas antiguas sigan traduciéndose.

| Archivo | Cambio |
|---|---|
| `backend/chem/especie_en_revision.py` | Motivos y SMARTS nuevos; cabecera con la evidencia de cada clase |
| `backend/tests/test_especie_en_revision.py` | Los controles de `controles.json` (positivos y negativos) como pruebas; se mantiene `CORRECTAS_VERIFICADAS == []` |
| `backend/core/i18n_catalog.py` | Texto en inglés de cada motivo (sin ortografía británica: lo exige `test_catalogo_ingles_sin_defectos`) |
| `backend/tests/test_especie_en_ingles.py`, `test_elevacion_detectores.py` | Un caso por motivo nuevo |
| `frontend/context/traducciones/elevacion.ts` | Clave `el_det_<código>` en castellano y en inglés (hoy hay tres: sulfonil-piperazina, ácido enólico, amina con atractor) |
| `docs/versions/1.0.4_cambios.md`, `AGENTS.md` | Fila del registro; cifras del efecto medido |
| `docs/api/test-counts.json` | Se regenera con `scripts/report_test_counts.py --write` y python-embed |

Los motivos no bloquean ni mueven ningún score. El dossier, Preparación y el panel de elevación 3D los leen de la misma función
(`backend/services/dossier/model.py:660`, `backend/chem/elevacion.py:385`), así que no hace falta tocar sus rutas.

## Riesgos y cómo se miden

1. **Falsas alarmas.** Un SMARTS demasiado ancho marca moléculas que no lo merecen (el de la morfolina, tal como lo propuso la segunda opinión, casa con la
   morfolina sin sustituir). Se acota con los controles negativos de la investigación, y la puerta de la fase 1 exige cero marcas en las 17 correctas verificadas.
2. **Corridas doradas e instantánea del dossier.** Si una molécula de las ocho corridas doradas o de la instantánea cae en una clase nueva, su estado de
   «especie» cambia y el hash del dossier se mueve. Antes de implementar se pasa cada SMILES de `check:goldens` y del test de instantánea por los patrones
   propuestos. Si alguno casa, se decide caso a caso si se regenera la instantánea (siempre con python-embed y reportlab 4.2.0, que el escritor de instantáneas ya exige).
3. **Alarma que no se puede ignorar.** «Revisar» ya está en el vocabulario de Preparación y no bloquea. Si la investigación concluye que una clase afecta a buena parte
   de una serie típica, se propone como informativa y no como revisión (el umbral lo fija el registro previo de la investigación, no este plan).
4. **Doble conteo.** Un α-nitrilo ya lo marca `amina_con_atractor`. Una molécula con dos motivos recibe dos, como pasa hoy con las bases próximas más la
   sulfonil-piperazina; no se deduplica.
5. **Texto.** Cada motivo debe decir «ejemplo de la literatura, no esta molécula», con la cifra y la cita que entregue la investigación. Sin cita verificada no hay texto.

## Preguntas que deciden el propietario (después de la fase 1)

1. ¿Entra la morfolina NH (pKa ≈ 8,4, a 0,5 de la banda de 8,9)?
2. ¿Entra la α-aminoamida (lidocaína, bupivacaína: catión mayoritario, 17–26 % de neutro) como revisión o como nota informativa?
3. Si una clase tiene menos de cinco compuestos con medida primaria, ¿entra como «sin evidencia suficiente», o se deja fuera?
4. ¿El criterio de entrada usa el mismo `UMBRAL_PKA = 1,5` de `preparacion.py`, o se fija otro?

## Qué entrega esta sesión antes de la investigación

Nada de código. Sólo este plan y el encargo; la implementación empieza cuando el propietario envíe el encargo y vuelva la entrega.
