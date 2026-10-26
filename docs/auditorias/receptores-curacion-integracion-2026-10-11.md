# Curación de receptores: qué entra en 1.0.2 y qué no (2026-10-11)

El worktree de curación de receptores (rama `codex/receptores-curacion-20261008`, `7b16531e`, y 83 entradas sin
commitear) se verificó contra desarrollo el 2026-10-10 y se integró por partes el 2026-10-11. Criterio del
propietario: integrar en 1.0.2 sólo lo útil y sin regresiones. Este documento dice qué entró, qué no y por qué,
con la medida que lo decide.

## Dónde vive todo lo demás

- **Código y documentos del worktree**, congelados byte a byte: rama `codex/receptores-curacion-20261008-wip`,
  commit `affbc92e` (26 ficheros modificados y 110 nuevos sobre `7b16531e`; commit con `core.autocrlf=false`
  porque los manifiestos de la evidencia hashean los bytes con CRLF; para recuperarlos, checkout con
  `core.autocrlf=false`). No se empuja al repositorio público.
- **Cápsulas de medida** (`output/` del worktree, ignorado por git): copiadas a
  `F:\Backups\moldesign-evidencia\2026-10-11-receptores-20261008-output`, 5 879 ficheros y 3 076 477 316 bytes,
  comparados fichero a fichero por SHA-256 (0 distintos). Las 182 junctions de pytest no se copian (`/XJ`).

## Lo que entra en 1.0.2

| Paso | Qué | Medida |
|---|---|---|
| 1 | La comprobación previa decide los cofactores con la regla de `prepare_target` (`cofactores_sin_plantilla`, caja efectiva). | 18 de 381 receptores bloqueados sin motivo (hemo, FMN, ADP, fosforresiduos, MET de MSE), con 409 al ejecutar → 0. Ninguna otra entrada cambia. |
| 2 | Trece entradas con un cofactor como «ligando del cristal» se recentran en su inhibidor (`scripts/corregir_referencias_cofactor.py`). | Cajas desplazadas 11–20 Å (en las COX, del sitio peroxidasa al canal de la ciclooxigenasa); el cofactor se conserva; inventario de disponibilidad medido otra vez con Meeko. |
| 3 | El detector de huecos sigue el orden del archivo. | Entradas con algún hueco junto al sitio: 137 → 126; 28 pierden cortes inventados y aparece uno real que no se veía (6CM4, C–N 4,56 Å, lejos del sitio). |
| 3 | El visor 3D identifica cada hotspot por cadena, residuo y código de inserción. | Antes `A:LYS60A` se leía `LYS60` y, en un homodímero, la importancia salía de la otra cadena. |

Las cifras exactas, los comandos y los controles negativos están en `docs/versions/1.0.2_cambios.md`.

## Lo que no entra, y por qué

| Pieza del worktree | Por qué no en 1.0.2 | Qué haría falta |
|---|---|---|
| Receta del receptor 8 y catálogo reanotado (364 de 381 entradas: `assembly_id`, ancla, instancia del ligando, `receptor_context_chains`, 201 conjuntos de hotspots) | Cambia la preparación de todo el catálogo. Choca con `scripts/invariancia_catalogo_receptores.py` («la receta 7 del catálogo no puede moverse»), con `seccion_catalogo.py` (receta vigente) y con CAL-8HFI-01, medido en receta 7. El propio worktree dice que no hay un barrido válido de las 381 bajo su estado (se invalidó a las 119). Con el WIP, la suite del backend daba 12 fallos propios. | Decisión del propietario sobre la receta; barrido completo válido; regenerar goldens con Vina real; repetir CAL-8HFI-01 si cambia la receta. |
| Selección de ensamblaje por `REMARK 350` con alcance por cadena | Cambia los registros de 75 entradas y deja 11 en abstención (1KLI, 1ZZ1, 2GH6, 2P4E, 3P88, 3P89, 4FK3, 4JP9, 4NY4, 4QGE, 5CQG) hasta una decisión registrada: 4NY4 volvería a no poder ejecutarse. La consecuencia visible ya está declarada: las 16 entradas con cadenas del sitio fuera de la unidad biológica son exactamente las 16 de `backend/data/avisos_catalogo.json`. | Decidir las 11 ambigüedades; integrarlo con la receta 8. |
| Rescoring sobre el receptor de la corrida (`rescoring_receptor.py`, `receptor_chemistry.py`) | Depende de campos del informe de Meeko de la receta 8 (`meeko_parameterized_json_sha256`, exportación química). Desarrollo ya escribe el PDB de rescoring desde el ensamblaje al preparar. | Integrarlo con la receta 8 y con pruebas sobre corridas reales. |
| Contrato de evidencia de calibración (`calibracion_evidencia.py`) | Es un segundo mecanismo de «calibrado» junto a `receptores_verificados.json` y `supera_el_protocolo`; dejaría como «sin evidencia» una calibración local del usuario. | Unificarlo con la sección Verificados. |
| Expedientes de Luna y Gemini, triaje de 381, sustitutos (1KT7, 7L01, 1Q4G…) | Son investigación, no producto. Ningún sustituto está aprobado. | Consultarlos en la rama `-wip`; adoptar un sustituto exige preparar, redocking y calibración. |

## Segunda pasada: 3N8Y, 3KK6 y 5TBO (2026-10-11)

Los tres receptores que la primera pasada dejó abiertos, medidos uno a uno.

- **3N8Y entra.** Se dejó fuera por la serina acetilada por la aspirina (OAS), que parecía pedir una preparación
  covalente. En el depósito la OAS sólo está en la cadena B, como microheterogeneidad y a 34,8 Å del diclofenaco
  A:701. La cadena A, que es la del catálogo, tiene la Ser530 sin modificar, y el carboxilato del diclofenaco le da
  un puente de hidrógeno (2,53 Å): es su modo de unión invertido, contra Tyr385 y Ser530. Se recentra con el mismo
  criterio que las otras trece (`corregir_referencias_cofactor.py --solo 3N8Y`); la caja se desplaza 18,08 Å y el
  ligando queda a 12 Å de cada cara. Versión del catálogo `referencias-del-sitio-3n8y-2026-10-11` (`21e807af…`).
  El guardián de cofactores declarados como ligando queda sin pendientes.
- **3KK6 se prepara.** No era el celecoxib ni la caja: el depósito trae los hidrógenos del refinamiento de PHENIX
  (con ocupación 0) y contradicen su propia estructura. Las 36 histidinas llevan hidrógenos, pero ninguno en el
  anillo, así que Meeko empata HIE y HID. Además, cinco cisteínas de puentes disulfuro llevan su HG, y Meeko lo lee
  como un segundo enlace S–S. `preparer` retira esos hidrógenos antes de Meeko, sólo en esos residuos. Sobre los
  depósitos de las 381 entradas, la regla sólo actúa en 3KK6 y 6S1Z (una His), las dos sin preparar por este
  motivo. El hash de la receta y el informe lo declaran sólo cuando actúa, así que ningún receptor que ya se
  preparaba cambia (guardián en `test_hidrogenos_depositados.py`, con Meeko real y su control negativo).
  Preparación lo dice en la protonación, que sigue en REVISAR. Las His quedan en HIE, como en cualquier depósito sin
  hidrógenos; la His388 queda a 3,9 Å del hierro en el receptor preparado, así que su H en NE2 no choca con él.
- **5TBO sigue en REVISIÓN, y ahora con la medida que faltaba.** El corte VAL343→GLU356 está a 20 Å del inhibidor
  pero a 1,59 Å de la caja: Vina busca junto a él. Preparación medía sólo la pose 1. Ahora mide todas las poses que
  guarda la corrida y dice cuáles caen a 8 Å o menos de un corte, o que ninguna lo hizo. En la corrida del paso 2
  (aspirina como sonda, exhaustividad 8, 9 poses, semilla 42), ninguna de las 9 quedó a menos de 16,9 Å del corte:
  seis cayeron sobre el sitio del inhibidor (0,2–0,4 Å) y tres a unos 6 Å, hacia el bolsillo del orotato (ORO,
  retirado y declarado a 10,2 Å).
- **De punta a punta con Vina real**, después de los dos commits: preflight, envío y Preparación, con aspirina como
  sonda, exhaustividad 8, 9 poses y semilla 42.
  - 3KK6: −6,515 kcal/mol; 3N8Y: −6,796. Las dos en REVISIÓN, con la pose 1 sobre el inhibidor del cristal (a 0,3 y
    0,5 Å, distancia del centroide de la pose al átomo más cercano).
  - 5TBO: −5,979, REVISIÓN, con la frase nueva sobre su corte.
  - 6S1Z: se ejecuta (−6,0), pero Preparación la BLOQUEA con razón: la preparación retira el Zn A:705, que está a
    2,18 Å del ligando, porque el catálogo no lo declara. Conservar el zinc de una metaloenzima es una decisión de
    política de metales, no de esta regla.
  - Barrido de Meeko sobre las 381 (receta 7): 13 no disponibles (antes 15); ninguna otra entrada cambia. La
    invariancia de la receta 7 se cumple en sus cinco receptores (8HFI, 1C3R, 3F75, 5VA1 y 1HSG).

## Lo que sigue sin poder prepararse, con su causa medida

Trece entradas siguen en `no_disponibles`. Las nueve en las que falla Meeko se reparten en dos familias. Ninguna se
toca en 1.0.2, porque arreglarlas mueve la receta 7 de receptores que hoy se preparan:

- **El recorte multicadena parte un puente disulfuro** (1UZJ, 1VKG, 1XWD, 3HH2, 5I3T, 8WTW). El recorte al radio
  del sitio deja una cisteína del puente sola o en el extremo de un fragmento, y Meeko no puede rellenar el enlace
  S–S. En 1VKG, la Cys A244 (puente con la A287) se convierte en extremo C porque la Glu245 queda fuera del radio;
  como el depósito trae hidrógenos, Meeko empata CYX con CYX-. Haría falta que el recorte conservara los residuos
  vecinos de un puente, o nombrar CYX las cisteínas de un puente como hace pdb4amber.
- **Contactos de ~1,4 Å entre cadenas laterales de residuos no consecutivos** (1FEM ASN50–HIS52, 6NTW GLN485–ASN491,
  7D42 PHE329–PHE443). Meeko los lee como un enlace que su plantilla no tiene. Hay que mirar en cada depósito si son
  conformaciones alternativas mal resueltas o un entrecruzamiento real antes de decidir nada.

## Metales del sitio: dos medidas para decidir

- **La His que coordina el hierro del hemo lleva el H en el nitrógeno que lo coordina.** En los 368 receptores que
  preparó el barrido, 9 His tienen un N del anillo a 2,6 Å o menos de un metal conservado, y en 8 la plantilla de
  Meeko (HIE) le puso el H justo en ese NE2. Son todas la His388 proximal de las COX: 1Q4G, 2OYE, 2OYU, 3N8W, 3N8X,
  3N8Y, 4O1Z y 5WBE (Fe–N entre 1,87 y 2,57 Å). Sólo 1CX2 está bien (HID), porque su depósito traía el H en ND1.
  Ese estado no existe. En el docking pesa poco: la His388 está en la cara proximal del hemo, lejos del canal de
  la ciclooxigenasa, y Vina no puntúa los hidrógenos. Para un cálculo con dinámica sí es un error. Corregir la
  plantilla movería la receta 7 de esas ocho entradas, así que en 1.0.2 Preparación lo mide sobre el PDBQT de la
  corrida y lo dice como revisión del caso, con su acción (`contexto_estructural.his_al_metal`). Para 1.0.3:
  asignar HID/HIE según el N que coordina.
- **41 entradas del catálogo tienen un ion metálico no declarado a 6 Å o menos de su ligando del cristal** (52
  iones: 28 de Zn, 16 de Mg, 5 de Ca y 3 de K), y el propio ligando coordina 43 de ellos (un N, O o S suyo a 2,8 Å o
  menos): 25 de Zn, 13 de Mg, 4 de Ca y 1 de K. El Zn es el de la anhidrasa carbónica II (3 entradas), las HDAC (14) y
  las enzimas convertidoras de angiotensina (8, y una novena a 4,4 Å del ligando, que ya no lo toca); en las dos PDE
  el ligando queda a 5,5–5,8 Å del Zn y a 4,4–5,7 Å del Mg de su sitio bimetálico.
  El Mg es el de los nucleótidos y sus análogos. La preparación lo retira y Preparación se abstiene, como en 6S1Z.
  Conservarlo es una decisión por entrada (`cofactors_whitelist`) o una ampliación de M5, y Vina no tiene un término de
  coordinación geométrica: el ajuste a la química del zinc (AutoDock4Zn) no está en el producto. Lo que decidiría es un
  redocking del ligando del cristal con y sin el ion, que no se ha hecho. Medida y lista de iones:
  `scripts/medir_metales_del_sitio.py` y `docs/auditorias/metales_junto_al_sitio_2026-10-11.json`.
  **M5-Zn no cubre hoy esos casos:** son tres PDB exactos (3DC3, 1GKC y 1O86), ninguno en el catálogo, y ningún perfil
  devuelve VALIDATED (GNN-D no tiene productor; los benchmarks de MMP9 y ACE están en revisión, docs/77).

## Lo que sigue abierto aunque haya entrado

- **5TBO** conserva el hueco VAL343→GLU356 (C–N 8,5 Å, 12 ausentes en REMARK 465). Corrida real con aspirina como
  sonda, exhaustividad 8, 9 poses, semilla 42: REVISIÓN, FMN conservado a 4,34 Å.
- Conservar el hemo no valida su física con la función de Vina por defecto: Preparación lo registra, no lo aprueba.
- Las cajas recentradas cambian el receptor preparado de esas trece entradas; la resincronización del catálogo lo
  invalida en las instalaciones existentes y se vuelve a preparar en la siguiente corrida.
