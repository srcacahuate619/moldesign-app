# AGENTS.md

Orientación para agentes de código que trabajen en este repositorio o lo
evalúen desde fuera. Este archivo describe **lo que MolDesign es hoy, medido**,
no lo que aspira a ser. La distinción es el producto: MolDesign existe para
decir cuándo *no* confiar en un número, así que su propia documentación no puede
permitirse exagerar.

Si eres un humano, empieza por [`README.md`](README.md). Este archivo asume que
vas a leer o modificar código.

---

## Qué es MolDesign hoy

Una **aplicación de escritorio** (Windows, Tauri v2 + Next.js + FastAPI + Python
embebido) para producir, organizar y comunicar **evidencia computacional
estructural** en etapas tempranas de investigación farmacológica.

No responde «¿esta molécula será un buen fármaco?». Su contrato es más estrecho
y más honesto:

> ¿Qué evidencia produjo esta corrida, con qué estructura y configuración, qué
> controles superó, qué incertidumbre permanece y qué sería justificable hacer
> después?

## Identidad de producto: confianza y transferencia estructural

MolDesign ocupa el espacio entre una estructura inicial y un cálculo científico
costoso. Su trabajo no es acumular motores ni prometer *drug discovery*
end-to-end, sino convertir decisiones estructurales que suelen quedar implícitas
en un objeto auditable, transferible y capaz de abstenerse.

```text
estructura + ligandos + contexto experimental
                    ↓
      MolDesign: readiness y procedencia
      - detecta bloqueantes y ambigüedades
      - registra decisiones y alternativas
      - conserva hashes, versiones y condiciones
                    ↓
        paquete estructural reproducible
                    ↓
      FEP+, OpenFE u otro cálculo externo
```

La arquitectura conceptual tiene cuatro capas:

| Capa | Responsabilidad |
|---|---|
| **Identidad permanente** | Confianza, procedencia y transferencia entre una hipótesis estructural y un cálculo posterior. |
| **Primer caso de uso de alto valor** | Auditar y preparar sistemas para flujos de energía libre sin ejecutar FEP. |
| **Implementación actual** | Producir y conservar evidencia de docking con Vina; ESMFold sólo aporta estructuras de péptidos que después acopla Vina. |
| **Destinos externos** | FEP+, OpenFE u otros protocolos; cada adaptador debe demostrar por separado qué puede reconstruir. |

Estas reglas forman parte del contrato del producto:

1. **FEP-ready es el primer flujo, no toda la identidad.** La misma capa podría
   preceder MD, ABFE o QM/MM, pero sólo después de medir y documentar la
   compatibilidad correspondiente.
2. **La unidad de valor no es un score aislado.** Es el sistema transferible:
   receptor, serie de ligandos, estados químicos, poses, correspondencias
   atómicas, referencias experimentales, decisiones y procedencia.
3. **«Preparado» no significa «el parser lo acepta».** Cadenas y unidad
   biológica, huecos, protonación, tautomería, estereoquímica, aguas, metales,
   cofactores y pose inicial deben resolverse o quedar declarados como
   incertidumbre.
4. **La abstención es una salida válida.** Un paquete puede quedar
   `BLOCKED`, `REVIEW` o `READY`; ocultar una ambigüedad para producir un
   archivo sería un defecto.
5. **La transferencia se prueba fuera de la sesión.** Un tercero debe poder
   reconstruir el paquete con sus archivos, manifiesto, hashes, versiones y
   decisiones registradas.
6. **«FEP+ ready» no equivale a certificación de Schrödinger.** Es una meta de
   preparación estructural independiente del proveedor hasta que una prueba de
   integración demuestre compatibilidad con una versión concreta.

Los primeros usuarios plausibles son equipos que sufren una frontera de
responsabilidad: CRO ↔ cliente, colaborador estructural ↔ equipo de simulación,
core facility ↔ laboratorio, biotech pequeña ↔ proveedor de FEP, o un grupo que
mantiene pipelines propios con OpenFE. La validación de producto debe medir si
reduce iteraciones, rechazos tardíos, decisiones perdidas y tiempo de preparación;
no sólo cuántas funciones ofrece.

Funciona **sin red**. Los pesos de los modelos se descargan una vez, a petición
explícita del investigador, y a partir de ahí la aplicación es autónoma. Esto no
es un detalle de implementación: es un requisito verificado por una guardia del
build (`frontend/scripts/check-no-remote-assets.js`).

### Lo que ejecuta de verdad

**Dos motores, y sólo dos.**

| Motor | Estado |
|---|---|
| **AutoDock Vina 1.2.7** | Empaquetado en el instalador. Es el motor de docking. |
| **ESMFold** | Descargable bajo demanda (8,4 GB). Pliega péptidos; el acoplamiento lo hace después Vina. |

El backend declara siete motores en `GET /evaluation/engines`, cada uno con lo
que puede ejecutar *esta* instalación y, si no, por qué. Desde el 2026-10-07
(decisión del propietario) el menú «Parámetros de la evaluación» sólo lista los
que se pueden elegir: Vina y ESMFold, que se elige aunque esté apagado porque la
corrida lo enciende al empezar (`frontend/lib/motores.ts`). Los otros cinco
—QuickVina 2, DiffDock, ColabFold, ESMFold Pro, RFdiffusion— ya no aparecen;
antes salían como «Próximamente». Hay además una plaza «Vía API» para un motor
externo, que dice «Sin conectar» y no envía datos a ningún servicio.

**No los añadas ni los actives sin evidencia.** Hay tres guardianes que fallan a
propósito si alguien vuelve a ofrecer un motor que la build no ejecuta:
`ENG-001` (`backend/tests/test_motores_declarados_son_los_que_existen.py`: el
inventario declara los siete con su motivo y sólo Vina está disponible de
fábrica), `ENG-003` (`test_diffpepdock_no_se_hace_pasar_por_esmfold.py`) y el
sucesor de `ENG-004` (`frontend/lib/__tests__/motores.test.ts`: el menú no lista
los cinco, ni como «Próximamente»). Esas pruebas existen porque ya pasó:
`diffpepdock` estaba en el contrato de la API, despachaba a ESMFold, y
etiquetaba la corrida con su propio nombre — una mentira de procedencia en el
dossier.

### Por qué DiffDock y ColabFold no están

No es falta de tiempo. Está medido en esta misma máquina:

- **DiffDock** (vía NVIDIA NIM, 19 complejos publicados *después* de su corte de
  entrenamiento): 84% de RMSD < 2 Å pero **21% de poses físicamente válidas**
  (PoseBusters). Y su `position_confidence` está **anticorrelacionado** con la
  validez: filtrar por «alta confianza» empeora el resultado al 14%. Para un
  producto cuya propuesta es saber cuándo no confiar, un motor sin señal de
  confianza utilizable no aporta nada.
- **ColabFold** necesita bases de datos de MSA de ~2 TB o un servicio remoto, y
  los parámetros de AlphaFold2 son CC BY-NC.

Referencia externa que lo enmarca: PoseBusters 2024 (Buttenschoen, Morris &
Deane, *Chem. Sci.* 15, 3130) da Vina 58% y DiffDock 12% con validez física
exigida.

### Visión molecular: el dibujo levantado a 3D

El editor y Moldex levantan el dibujo 2D de Ketcher a una geometría 3D que se le parezca
(`backend/chem/elevacion.py`, `POST /chem/elevacion`; integrado el 2026-10-25 desde
`codex/audit-producto-1.0.4`). Se abstiene cuando ningún candidato lo hace sin mover átomos
más de un enlace, y declara la energía MMFF94 del conformador que enseña. Es una vista: no
cambia ninguna corrida ni ningún score. **`VISION-MOLECULAR-01` (NO_GO, sellado al cerrar;
paper `docs/papers/VISION-MOLECULAR-01.md`)** reúne seis alternativas medidas con registro
previo para las moléculas grandes (37 de 35 a 51 átomos pesados, en las que se abstiene en 8):
ninguna lo mejora sin pagar en otra cosa, porque parecerse al dibujo y ser estable son
objetivos opuestos en una molécula flexible. Con xTB-ALPB, la energía declarada baja a 0,69
veces la de MMFF, pero no invierte el problema.

### Lo que MolDesign NO es

- **No corre dinámica molecular ni FEP.** Ver la sección siguiente.
- **No predice actividad biológica.** Las capas ADMET son experimentales y se
  presentan como tales.
- **No sustituye validación experimental**, y la interfaz lo dice en cada
  informe.
- **No es un servicio en la nube.** Todo el cómputo es local.

### El catálogo de receptores: Verificados, Tus receptores y Demostración

Medido el 2026-10-08/09: **ninguno de los 381 receptores del catálogo está
calibrado**. Hay un único intento medido contra datos experimentales, el de 8HFI, y
no superó el protocolo (ver `CAL-8HFI-01` más abajo). Además, muchos tienen
problemas de preparación que la pestaña Preparación bloquea con razón (huecos
junto al sitio, metales retirados, cadenas truncadas). Decisión del propietario
para 1.0.2: nada se oculta ni se bloquea, y el catálogo se presenta en tres
secciones.

- **Verificados**: pose del cristal reproducida y calibración medida, cada uno
  con sus cifras. Vacía hasta 1.0.3; **desde 1.0.4 tiene uno, 8T69 (VMAT2)**, por
  `CAL-D-01-R4-2-VMAT2-8T69` (GO, ver más abajo). Un receptor entra sólo si su entrada en
  `backend/data/receptores_verificados.json` supera
  `services/targets/seccion_catalogo.py::supera_el_protocolo`: hash del receptor,
  receta vigente, protocolo y condiciones declarados, al menos 3 de 5 semillas a
  RMSD ≤ 2 Å, pose válida en PoseBusters y límite inferior del IC 95 % de la ρ
  mayor que 0. **No se promociona un receptor a mano**: el guardián de
  `tests/test_seccion_catalogo.py` exige que cada verificado repita las cifras de un
  intento GO de `intentos_de_verificacion.json`, y `tests/test_intentos_de_verificacion.py`
  comprueba ese intento contra su experimento sellado; los dos tienen controles negativos. Un sello sólo
  describe una corrida que declara el mismo receptor preparado y los mismos
  parámetros. Lo que la corrida no declara no cuenta como coincidencia:
  `catalogo_de_la_corrida` lo devuelve en `sin_declarar`, aparte de `difiere_en`.
- **Tus receptores**: los que sube el usuario, el camino para decisiones reales.
- **Demostración**: los 381 del catálogo. La etiqueta viaja a la portada del
  dossier y a su PDF (en los dos idiomas), a Preparación (pide revisión, no
  bloquea) y a las vistas de resultados, Moldex, lotes y Molcy. La certificación
  la cubre porque certifica el dossier. **El vídeo de Molcy la muestra desde
  `40e02f0` del motor** (rótulo en el título, en castellano o inglés según el
  idioma del cierre): el cambio entró en `main` del motor con el PR #2 (`854bada`).
  Desde 2026-10-25 el producto vendoriza `a3d0d10`, que lo junta con los controles de
  presentación (título propio, colores, receptor visible u oculto): un título propio
  sustituye al nombre, pero no quita la etiqueta. Su aspecto en pantalla todavía no está
  verificado.

El primer intento se publica pase o no: **`CAL-8HFI-01` (8HFI, NET), NO_GO.** La
pose pasa en el límite (3 de 5 semillas) y la calibración no: ρ = 0,13, IC 95 %
[−0,16; 0,41], n = 57 Ki del panel CHEMBL853189, con la configuración por defecto
de un caso (exhaustividad 8, 9 poses, semilla 42). El IC cruza el cero: **no se
demostró** que Vina ordene esa serie de análogos mejor que el azar, lo que no
equivale a demostrar que no lo haga (con n = 57, una ρ verdadera de 0,3 sólo se
detectaría el 62 % de las veces). El intento vive en
`backend/data/intentos_de_verificacion.json`, y
`tests/test_intentos_de_verificacion.py` comprueba cada cifra contra el
experimento sellado, con un control negativo: mejorar un número a mano falla. Su
paper, para la pestaña Ciencia, es `docs/papers/CAL-8HFI-01.md`.

**Segundo intento publicado: `CAL-D-01-R4-VMAT2-8T69` (8T69, VMAT2), NO_GO formal, y su reanálisis `CAL-D-01-R4B-VMAT2-8T69`, INCONCLUSIVE.** La pose de la tetrabenazina se reproduce en 5 de 5 semillas (RMSD 0,67–0,71 Å) y el top-1 de Vina correlaciona con 88 Ki publicados de la patente US11718618B2: ρ = 0,39 (IC 95 % 0,22–0,54) y ρ de peor caso sobre las asignaciones binarias de lote (F = 1015/703) = 0,32 (IC 95 % 0,14–0,47). El NO_GO es formal: el registro exigía cero fallos persistentes y el producto no completa el compuesto 4-67 (biciclo[1.1.1]pentano; corte a 1200 s). R4B lo reanaliza sin 4-67 con una enmienda escrita después de ver los scores: cumple el criterio y por eso mismo no es confirmatorio ni promociona. Papers `docs/papers/CAL-D-01-R4*.md`; código en `scripts/cal_d01r4/`. Lo que bloqueaba a 4-67 era el `energy_ratio` de PoseBusters, cuyo embebido ETKDG no termina con el biciclopentano; corría en un hilo y seguía gastando CPU tras el `Timeout`. Desde `48b22820` (2026-10-24) la validación física corre en un proceso hijo con plazo de 300 s que se mata al vencer o al cancelar: 4-67 contra 8T69 completa en 393 s con la etapa «no evaluada» (`VALIDADOR_EXCEDIO_EL_PLAZO`). R4 sigue sellado NO_GO. **Su repetición, `CAL-D-01-R4-2-VMAT2-8T69` (2026-10-24), dio GO** con la regla de R4 sin cambios (paper `docs/papers/CAL-D-01-R4-2-VMAT2-8T69.md`): 89 de 89 padres, 4-67 incluido (335 s), cero fallos persistentes, ρ = 0,39 (IC 95 % 0,22–0,54) y ρ_peor = 0,32 (0,14–0,47). Una validación física `not_evaluated` con score se declaró antes de medir como evaluada; 4-67 es el único caso, y sin él la ρ no cambia. No es ciego: los 88 scores comunes con R4 se repiten exactos. **8T69 está en Verificados desde el 2026-10-24** (decisión del propietario): el sello describe corridas con su receptor
preparado `8fc027ca…`, exhaustividad 8, 9 poses y semilla 42, y las condiciones serie congenérica, ensayo [3H]DTBZ en plaquetas y Kd
por lote no adjudicado. Ordena esta serie mejor que el azar; no predice el Ki de una molécula.

Los avisos medidos del catálogo están en `backend/data/avisos_catalogo.json`. Hoy
son 16 receptores cuyas cadenas del sitio no están todas en la unidad biológica
del depósito, así que el sitio podría ser un contacto del cristal.

**Curación de receptores, integrada el 2026-10-11** (`bc988534` a `2d29e294`; lo
medido, lo que no entró y por qué están en
`docs/auditorias/receptores-curacion-integracion-2026-10-11.md`):
- la comprobación previa decide los cofactores con la misma regla que
  `prepare_target`, con la caja efectiva de la corrida. Antes bloqueaba sin motivo
  18 de los 381 (hemo, FMN, ADP, fosforresiduos) y la corrida respondía 409; ahora
  son 0;
- 14 entradas declaraban como «ligando del cristal» un cofactor (hemo, NADP, FMN) y
  tenían la caja centrada en él, desplazada de 11,3 a 20,3 Å de su inhibidor (en las
  COX, del sitio peroxidasa al canal de la ciclooxigenasa). Se recentran en el
  inhibidor con `scripts/corregir_referencias_cofactor.py`; 3N8Y entra porque su
  serina acetilada sólo está en la cadena B. Versión del catálogo
  `referencias-del-sitio-3n8y-2026-10-11`;
- 3KK6 y 6S1Z se preparan. Sus depósitos traen hidrógenos del refinamiento que
  contradicen su propia estructura (His con H y ninguno en el anillo; HG en Cys de
  puentes disulfuro) y `preparer` los retira antes de Meeko, sólo en esos residuos.
  Barrido de Meeko 0.7.1 sobre las 381 entradas con la receta 7: **13 no
  disponibles** (antes 15; ninguna otra entrada cambia), y los cinco receptores de
  `scripts/invariancia_catalogo_receptores.py` siguen dando el mismo hash;
- los huecos del esqueleto siguen el orden del archivo (134 cortes inventados menos).
  Preparación los mide frente a todas las poses guardadas, y avisa cuando una His
  coordina un metal con el hidrógeno en el nitrógeno que lo coordina (la His388
  proximal de 8 COX; la plantilla de Meeko, HIE, no mira el metal);
- no entraron la receta 8, el ensamblaje por `REMARK 350`, el rescoring sobre el
  receptor de la corrida ni los expedientes del worktree de curación: viven en la
  rama `codex/receptores-curacion-20261008-wip` (`affbc92e`).

**Metales junto al sitio (medido el 2026-10-11 sobre los depósitos; sin corregir).**
Ninguna entrada del catálogo declara `cofactors_whitelist`, así que la preparación
elimina todo ion metálico y Preparación se abstiene cuando estaba junto al ligando.
En 41 de las 381 hay un ion a 6 Å o menos del ligando del cristal (52 iones: 28 de
Zn, 16 de Mg, 5 de Ca y 3 de K), y el propio ligando coordina 43 de ellos (un N, O o
S suyo a 2,8 Å o menos): 25 de Zn, 13 de Mg, 4 de Ca y 1 de K. El Zn es el de la
anhidrasa carbónica II, las HDAC y las enzimas convertidoras de angiotensina; el Mg,
el de los nucleótidos y sus análogos. En 35 entradas, pues, el metal forma parte de
la unión; en las otras 6 ningún átomo del ligando llega al ion (a 3,7–5,8 Å: las dos PDE,
con su par Zn–Mg, y cuatro iones sueltos). Es una medida geométrica sobre el cristal, no una
energía.
`scripts/medir_metales_del_sitio.py` la reproduce y la evidencia está en
`docs/auditorias/metales_junto_al_sitio_2026-10-11.json`.
**Vina no tiene un término de coordinación geométrica** (AutoDock4Zn, que sí, no está en
el producto), así que conservar el ion no basta por sí solo. Cuál es la decisión (declarar
`cofactors_whitelist` por entrada, o ampliar M5) la mide mejor un redocking del ligando del
cristal con y sin el ion. **MET-01 lo intentó el 2026-10-11 y no llegó a medirlo**
(INCONCLUSIVE; paper `docs/papers/MET-01-ION-DEL-SITIO.md` y tabla de las 41 entradas en
`docs/auditorias/metales-con-y-sin-ion-2026-10-11.md`): la evaluación descartaba la lista, y
el brazo con ion acoplaba el receptor sin él (arreglado en `a27ded64`, ver más abajo).
**MET-01-R1 lo repitió el 2026-10-21 sobre `9ce8b104` y dio NO_GO** (paper
`docs/papers/MET-01-R1-ION-DEL-SITIO.md`, tabla en `docs/auditorias/metales-con-y-sin-ion-R1-2026-10-21.md`):
380 corridas, 28 entradas pareadas de 35, discordancias 0 a favor de conservar el ion y 3 a favor de
retirarlo (p bilateral exacta 0,25), 4 controles evaluables de 6 sin pérdida. Con el Vina del producto,
conservar el ion no mejora la reproducción de la pose del cristal; tampoco se demuestra daño ni
equivalencia. Se mantiene la retirada y la abstención, y el brazo con ion queda como línea base para
M5. MET-01 dejó otros dos límites, que siguen: PoseBusters no mira los iones que
Meeko escribe como `ATOM` (quedan fuera de la máscara inorgánica y de la de proteína, así que un
PASA no valida su coordinación), y la variante de 8UBR conservaba dos ATP de más porque
`POST /targets/{id}/variants` no pasaba `site_ligand` al preparar (arreglado en `eea5b9f5`: la variante hereda el ligando
del cristal del padre).
**M5-Zn no cubre hoy esos casos.** Es una receta de puntuación para tres PDB exactos
(3DC3, 1GKC y 1O86), ninguno está en el catálogo, y no cambia lo que Vina acopla. Ningún
perfil devuelve VALIDATED: el de CA2 necesita GNN-D, que no tiene productor
(`gnn_d_prob=None` en el ejecutor), y los benchmarks de MMP9 y ACE están en revisión
(`docs/77_CORRIGENDUM_SITIO_DEL_BENCHMARK_M5_ZN.md`; en ACE, ninguna pose top-1 de 47 coloca
un átomo donante a 4 Å o menos del zinc). Dirección del propietario (2026-10-11): M5 es la
solución propia para el zinc y puede ampliarse a más metales; aún no se ha hecho.
**Regla en dos niveles, integrada el 2026-10-23** (`14fd5e4d`; papers `docs/papers/MET-02-SEMILLA.md` y
`MET-02-R1-SEMILLA.md`). Preparación mide metales y cofactores desde el **ligando del cristal**, no desde el mínimo con la pose:
un metal retirado que el ligando del cristal coordina (un N, O o S suyo a 2,8 Å o menos), o un cofactor sin metal a 4 Å o menos,
sigue absteniendo; uno sólo cercano (≤ 6 Å) pide **revisión**; un metal conservado que el ligando coordina (el Fe del hemo de 4NY4)
pide revisión, porque Vina no modela la coordinación; sin ligando del cristal no se sabe y se abstiene. MET-02-R1 (GO, 41 entradas
× 5 semillas): ningún estado cambia con la semilla, 39 de 39 coinciden con el inventario geométrico y la pose top-1 es la misma que
con la regla anterior. Cambian 7 decisiones: 4PHL, 4QGE, 5A2R, 6KE5 y 8WGR pasan a revisión, 1RKP deja de abstenerse y 4NY4
pide revisión. MET-02 (INCONCLUSIVE) destapó que el lector de coordenadas tomaba la carga de la columna 79 como parte del elemento
(«MG2», «ZN0», «H0»: 45 de 446 depósitos); arreglado en `f7c46736`. `ABS-TR-01-VALIDEZ-R1` (2026-10-24, INCONCLUSIVE; paper `docs/papers/ABS-TR-01-VALIDEZ-R1.md`) lo repitió
con la regla nueva contra la misma referencia congelada: falso bloqueo 1/18 (sólo 4JVB; antes 3/18), ninguna falsa autorización, y sólo
cambiaron 1RKP y 6KE5, como se predijo.

**Subida de receptores propios, arreglada el 2026-10-09** (rama
`claude/receptores-propios`, integrada en `6eef2ce9`; nota en
`ENTREGA_RECEPTORES_PROPIOS.md`). Tres caminos, medidos con Vina real por la API
sobre un corpus de 36 casos (antes 1 de 4):
- **A**, estructura cruda: PDB, `.ent` y mmCIF, con cadenas de varias letras y
  códigos CCD largos con correspondencia explícita, y estructuras predichas;
- **B**, estructura ya preparada por el equipo: se respetan su protonación,
  aguas, metales y cofactores; la protonación se declara «por el usuario», nunca
  se valida; PQR de PDB2PQR con AMBER o PARSE;
- **C**, PDBQT listo para Vina: se evalúa tal cual; con la estructura de origen,
  Preparación audita lo que se retiró.

Los rechazos dicen qué falló y qué hacer. De una estructura predicha sólo se lee
el pLDDT con la convención verificada de **AlphaFold DB**; Boltz, Chai-1 y
AlphaFold 3 salen «no disponible», porque no hay un archivo real con el que
comprobarla. Un pLDDT < 70 junto al sitio pide revisión y no bloquea. El modo vive
en `targets/USR_*/perfil.json`: **el catálogo nunca tiene perfil**, así que su
preparación no puede cambiar (los cinco receptores de
`scripts/invariancia_catalogo_receptores.py` dan el mismo `receptor_sha256`).
Ocho códigos de aviso nuevos de la subida (`DECODIFICADO_LATIN1`, `MMCIF_*`,
`PDBQT_*`) están en `CODIGOS_DE_AVISO`; la interfaz muestra el código tal cual y no
necesita un espejo. En modo automático, los nombres de CHARMM (`HSD`/`HSE`/`HSP`,
`WAT`) pasan a `HIS`/`HOH` antes de preparar, y queda declarado (antes la receta
borraba esas histidinas). No verificado: el bundle instalado y los campos de
fuerzas TYL06, PEOEPB y SWANSON.

**Preparación y Evaluación con receptores propios, arregladas el 2026-10-11**
(`f0e64086` y `ee2d6c78`; medido con Vina real por la API sobre cdk2 y pde2 de OpenFF, por
los caminos A, B y C con y sin origen: `docs/auditorias/evaluacion-caminos-propios-2026-10-11.md`).
Las dos pestañas daban por hecha la receta del catálogo, que retira todas las aguas, todos
los metales y los cierres ACE/NME:
- Preparación no reconocía el origen de los caminos B y C (P01 de FEP-09) y lo medía todo
  desde la caja. Ahora recalcula la receta del camino que registró la corrida; el camino C
  con origen se verificó por primera vez con Vina real;
- en Evaluación, el aviso de aguas decía «se retiraron N aguas» de receptores que las
  conservaban (ahora `AGUAS_DEL_SITIO_CONSERVADAS`, medido sobre el receptor acoplado), el
  supuesto del dossier decía «se eliminaron todas las aguas» de cualquier corrida, el
  receptor y el complejo de un PDBQT sin origen daban 404, y las interacciones de **toda**
  corrida B o C caían al análisis por distancias (Zn y Mg escritos «Z» y «M»; el ACE A:-1
  rompía ProLIF, que guarda el número de residuo sin signo);
- la evaluación individual descartaba los cofactores y metales declarados en la subida o en
  una variante (`cofactors_whitelist`) desde al menos el 2026-08-13, y volvía a preparar el
  receptor sin ellos; el PDF del dossier los daba por conservados. Lotes sí la respetaba. Lo
  encontró MET-01; arreglado en `a27ded64` y comprobado con Vina real sobre 1BN1: la variante
  con Zn acopla ahora su propio receptor (`e23dabe7…`).

Sigue abierto: la coordinación con metales no aparece en las interacciones (la huella de
ProLIF del producto no la incluye). El supuesto del dossier de cohorte ya conoce el modo de preparación de un
receptor propio (`3ea8bb97`).

---

## Primer caso de uso: preparación **FEP-ready**

Ésta es la confusión más probable de un agente, así que va explícita:

> **MolDesign no ejecutará FEP.** Ser «FEP-ready» significa preparar y auditar
> el sistema estructural que consumirá un cálculo externo, conservar las
> decisiones que lo definen y permitir que un tercero reconstruya el paquete.

El cálculo de energía libre lo hará otro (Schrödinger FEP+, OpenFE u otro
protocolo). El hueco que MolDesign ocupa está *antes*: preparación, control y
transferencia de los supuestos estructurales que esos métodos dan por hechos.

**Ésta es una dirección de producto, no el estado actual.** Hasta superar
`FEP-05` y `FEP-06`, la formulación correcta es «auditor de readiness para FEP
en desarrollo», no «sistema compatible con FEP+».

**Pre-prueba de transferencia `FEP-06-PRE` (2026-10-22/24, GO estrecho; acta en
`scripts/artifacts_science/FEP-06-PRE/RESULTADOS.md`, paper `docs/papers/FEP-06-PRE.md`).** Seis revisores LLM recibieron
a ciegas los diez paquetes que exporta el producto `861f6a0e` (siete estructuras con trampas plantadas y los caminos A, B y C).
- Ninguna pérdida silenciosa llegó a tres revisores en P04–P09, ningún paquete se declaró transferible y no hubo falsas alarmas en
  los controles. Ningún revisor dio un paquete por **listo para preparar**.
- Un revisor vio una alteración real sin declarar: la Cys442 de 4NY4, que coordina el Fe del hemo, quedó como tiol.
- También destapó mensajes contradictorios del filtro de poses de Model A y del censo de aguas en 4 de los 10 paquetes, y huecos
  de procedencia: el ensamblaje por simetría, la identidad original de los residuos retirados y la caja en `protocol.json`.
- No es FEP-06: ningún tercero reconstruyó ni ejecutó un cálculo.

Los defectos están corregidos en 1.0.4 (`a9da9e0f` a `8951aa88`), cada uno con su prueba:
- Preparación avisa de la Cys que coordina un metal como tiol.
- Model A, MM-GBSA y el censo de aguas leen en desarrollo el mismo receptor que en el instalador.
- La procedencia lleva la caja ejecutada.
- Se declaran las cadenas generadas por simetría, la identidad original de lo truncado y retirado, y la regla de los altlocs.
- Preparación lee las cabeceras del depósito: ligando del cristal incompleto (REMARK 610), constructo (SEQADV/999) y ocupación
  cero (475/480).

**`FEP-06-PRE-2` (2026-10-25, GO; acta `scripts/artifacts_science/FEP-06-PRE-2/RESULTADOS.md`, paper `docs/papers/FEP-06-PRE-2.md`)**
repite el diseño con el producto arreglado (`1886794d`). Con cuatro revisores admitidos:
- ninguna pérdida candidata, ningún paquete transferible y ninguna falsa alarma;
- nadie vuelve a señalar la Cys del hemo ni la cadena por simetría, y se citan 49 de 52 hechos de la clave.
- No cuentan deepseek4.1flash, que empezó antes de la firma sin carpeta anotada, ni flint40bfree, que leyó la revisión anterior
  (se vio después del primer sello `8bb8b5c1`, que lo admitía; corregido con mantenimiento del sello). GO también con 3, 5 y 6 revisores.
- Un revisor admitido (y flint40bfree) vio una pérdida real, por debajo del umbral: en 6SXC, una segunda copia del ligando (OHT A:307, a 3,32 Å) se
  retiraba sin declarar, porque `preflight.py` trataba como «el ligando» todo residuo con su código CCD (14 de 381 entradas con
  otra copia a 6 Å o menos). **Arreglado en 1.0.4:** sólo la copia más cercana al centro de la caja es el ligando del sitio; las
  demás se declaran con su distancia al ligando del cristal (no a la pose) y, a 6 Å o menos, «Otras especies junto al sitio» pide
  revisión y las nombra. Medido con Vina real sobre las 14: 13 lo piden y nombran la copia; 1VKG no se prepara (Meeko). El estado
  global no cambia en ninguna.

Estado auditado hoy, sobre 203 complejos:

| Auditoría | Listos | Cuello |
|---|---:|---|
| `FEP-01` integridad del ligando (línea base, 2026-08-18) | **19%** (39/203) | 164 con tautómero ambiguo, ninguno declarado entonces |
| `FEP-01-DECL` (después de declarar tautómeros) | **19%** resueltos (39/203); 180/203 *declarados* | 142 en MULTIESTADO_REQUERIDO y 22 por encima del tope de 32: declarado no es resuelto (ver el punto 1 de abajo) |
| `FEP-02` cribado preliminar del receptor | **83/203 (41%) cumplen sólo el criterio de numeración y cadena**, no readiness FEP | Sobre `_protein.pdb` de PDBbind ya limpiado: 86 con saltos de numeración candidatos a hueco físico, 43 con el sitio entre cadenas, 52 con metales; mediana de 10 aguas. Entre los 83, hay 20 con metales en el sitio y 75 con aguas a ≤6 Å; sólo 8 no tienen ninguno de esos dos factores. Aguas, metales, cofactores y preparación del producto no forman parte del criterio de 83. |
| `FEP-03` series congenéricas | 91 parejas / 18 dianas, **cota superior** | 9 parejas tienen perturbación de grafo pesado cero; la cohorte se armó para diversidad y no demuestra una red FEP utilizable. |

**Sensibilidad de la pestaña Preparación** (`FEP-09` y `FEP-09-R1`, 2026-10-11; papers en
`docs/papers/`). Con defectos plantados en 15 dianas del benchmark de OpenFF, por el camino B y
con Vina real, R1 mide sobre el producto con P01 arreglado: detecta los huecos del sitio (15 de
15) y la estereoquímica sin asignar (21 de 21 en 7 dianas), las dos GO, con falsa alarma 0 de
585. No detecta el agua puente retirada (0 de 9) ni la protonación del sitio (0 de 5): son
límites de lo que mira, iguales caso a caso que en FEP-09, no efectos de P01. El tautómero
minoritario y la especie del ligando no tienen casos, así que la decisión global es
INCONCLUSIVE. FEP-09 (Sol) se había medido con P01 dentro: sus 127 auditorías medían desde la
caja.

**Validez de la decisión de Preparación** (`ABS-TR-01-VALIDEZ`, 2026-10-22, INCONCLUSIVE; papel en
`docs/100`). Sobre 28 de los 29 sistemas reales de ABS-TR-01 (8WTW no se prepara: Meeko), contra la
decisión de cinco revisores LLM —no expertos, y dos de la misma familia— que detienen un sistema si
≥ 3 dan NO_APTO: **ninguna falsa autorización** (0/10; Preparación no dijo «seguir» en ningún
sistema), **falso bloqueo 3/18** (16,7 %, límite unilateral 95 % 4,7–37,7 %: 1RKP y 6KE5 por un ion
retirado a ≤ 6 Å que el ligando no coordina; 4JVB por un hueco a 6,09 Å) y **4/10 que el panel
detiene pasan con aviso** (4NY4: el ligando coordina el Fe de un hemo conservado y Preparación no lo
ve; 6SXC: sitio completado por simetría; 6HW5: covalente, sólo revisión; 3G0E: ligando del
depósito incompleto). La distancia de un metal se medía contra el mínimo entre la pose top-1 y el
ligando del cristal (1RKP: el Zn está a 6,52 Å del cristal y se informó a 5,17 Å); desde el 2026-10-23 se mide desde el cristal
y en dos niveles (ver «Metales junto al sitio»), con lo que 1RKP y 6KE5 dejan de abstenerse y 4NY4 pide revisión. Con 18 negativos el límite superior no baja del 15,3 % ni con cero
errores: no concluye. Salió de paso un falso positivo del detector de ojivas (el 3-ilidenoxindol del
sunitinib contaba como acrilamida), ya corregido.

Orden de trabajo declarado (`docs/50_ROADMAP.md` §3):

1. **Declarar tautómeros** — **hecho** (`56e8733`, tres estados) y medido en
   `FEP-01-DECL` (GO): 180/203 (88,7%) quedan *declarados*, pero sólo **39 (19%)
   resueltos**; 142 tienen estado MULTIESTADO_REQUERIDO (141 cumplen el criterio declarado; uno queda bloqueado por estereoquímica) y 22 superan el tope de 32. Declarado
   no es resuelto: la cifra que describe el estado real es la del 19%. Para
   docking con Vina apenas importa; para FEP+ es determinante, porque el
   tautómero define qué átomos donan y cuáles aceptan puentes de hidrógeno.
   Siguiente: un modelo energético validado para descartar candidatos.
2. **Documentar receptores** — huecos, cadenas múltiples, metales, aguas
   estructurales frente a desplazables.
3. **Reconstruir la cohorte congenérica** desde PDBBind: pocas dianas con muchos
   análogos.
4. **`FEP-05`** export reproducible: SDF/PDB/JSON con hashes, versiones, caja,
   semillas y advertencias.
5. **`FEP-06`** dry-run de transferencia — un tercero reconstruye el paquete sin
   conocer la sesión.

Horizonte declarado: 12–18 meses para el conjunto; ~3 meses para el 80% del
valor (los tres primeros puntos).

---

## El ejecutable

El instalador se distribuye por **GitHub Releases** y, según el propietario
(2026-10-04), la **versión 1.0.1 está en producción en la Microsoft Store**. No
vive en el árbol (`frontend/src-tauri/target/` está en `.gitignore`). El código
declara hoy **1.0.4** (`backend/core/version.py`, `package.json`, `tauri.conf.json` y
`Cargo.toml`; Store 1.0.4.0, sin construir todavía; registro en `docs/versions/1.0.4_cambios.md`). La 1.0.3, un HOT FIX
acotado al render de Molcy, está publicada en la Store desde `bef67706` (`docs/versions/1.0.3_cambios.md`).
Lo que sigue describe los paquetes de **1.0.2** (Store 1.0.2.0, `467330cd`). Se
reconstruyeron el 2026-10-12 desde `dd09e229`, con el árbol limpio y las 16 puertas en
verde: el instalador NSIS (`MolDesign_1.0.2_x64-setup.exe`, 531 409 182 bytes,
SHA-256 `a9c3e5a9…7551e`) y el MSIX 1.0.2.0 sin firmar para la Store y firmado con el
certificado de desarrollo para la VM. Viven en `E:\rel\v1.0.2.0\` (que apunta a
`F:\Releases_Historicos\`), con hashes y procedencia en `paquetes-entregados.json`.
El primer build, de `40b58b4b`, está apartado en
`E:\rel\historico-v1.0.2.0-20261012-40b58b4b-fuga-ketcher\`: la VM encontró en él la fuga
de memoria del editor de moléculas y Molecular Nodes sin el runtime de Visual C++. Los
paquetes nuevos todavía no se han validado: ni WACK, ni la VM, ni Partner Center.

```
MolDesign_<versión>_x64-setup.exe
```

El producto se llama **MolDesign** (`productName` y título de ventana en
`tauri.conf.json`). El instalador de 1.0.0, archivado en `dist/installers-anteriores/` (ahora en F:\Backups\moldesign-evidencia\2026-10-10-limpieza-D\dist\installers-anteriores),
todavía se llamaba «MolDesign AI_1.0.0_x64-setup.exe» y pesaba 572,8 MiB; esa cifra
no es la de 1.0.1, que no está medida aquí.

### NO ESTÁ FIRMADO

El `.exe` de GitHub no lleva firma **Authenticode** (el paquete de la Store lo
firma Microsoft al publicarlo). Consecuencias que conviene decir sin adornos:

- Windows mostrará el aviso de SmartScreen «aplicación no reconocida».
- **El SHA-256 es la única prueba de integridad que existe.** Verifícalo antes
  de ejecutarlo:

  ```powershell
  Get-FileHash ".\MolDesign_<versión>_x64-setup.exe" -Algorithm SHA256
  ```

  y contrástalo con el `.sha256` y el `release-manifest.json` que acompañan a
  cada release.

La falta de firma es por falta de presupuesto para el certificado, no por
descuido. Está declarada en `release-manifest.json` como
`"firmado_authenticode": false`.

El manifiesto también trae `"arbol_limpio"`: si es `false`, ese instalador se
construyó desde un árbol con cambios sin commitear y **no es reproducible desde
el repositorio**. Compruébalo antes de asumir que el binario corresponde al
código que estás leyendo.

---

## Mapa del repositorio

```
backend/          FastAPI + pipeline científico (Python).
  api/            routers y main
  chem/           propiedades, conformers, validación
  services/       docking, pipeline, motores, IA, blockchain
  scoring/        rescoring y calibración
frontend/         Next.js 16 (export estático) + Tauri v2.
  src-tauri/      contenedor Rust: supervisa el backend, ventana, descargas
  scripts/        guardias del build (ver abajo)
rescoring/        modelos de rescoring y selector de pose
scripts/          herramientas de empaquetado y ciencia
  bundle_helper.py        arma el runtime que viaja en el instalador
  stage_openbabel_tool.py materializa Open Babel como herramienta externa
  check_openbabel_boundary.py  guarda de la frontera GPL (ver doc 79)
  artifacts_science/      artefactos SELLADOS de experimentos (no editar)
  qa_sandbox/             cápsulas de QA por agente: backend + export + datos propios (ver su README)
tools/            programas de terceros invocados por subproceso
  vina/ xtb/ llama/       binarios (no versionados); vina/ trae también vina_trace.exe,
                          la traza de la búsqueda que usa Molcy (manifiesto versionado)
  openbabel/              Open Babel GPL-2.0-only + manifiesto y licencia
  molcy/                  motor de vídeo (obra propia, GPL-3.0-or-later): scripts que corren DENTRO de Blender; se vendoriza desde un
                          commit con stage_molcy_motor.py, no se edita a mano (ver doc 95)
  vc-runtime/             cinco DLL MSVC x64 firmadas + manifiesto y hashes
docs/             programa experimental, gates de release, auditorías
```

---

## Construir

```bash
cd frontend
npm run test:run      # 2105 pruebas en 229 archivos (2026-10-22)
npm run tauri:build   # instalador completo
```

`tauri:build` encadena dieciséis puertas en `beforeBuildCommand`, más `cargo`/NSIS y
el sellado. Todas bloquean el build si fallan. La lista sale de
`frontend/src-tauri/tauri.conf.json`, no de la memoria de nadie (esta tabla
decía catorce y le faltaba la primera; la auditoría externa 001 lo midió el
2026-09-22; el 2026-10-04 se añadió `check:molcy-motor`):

| # | Puerta | Qué comprueba |
|---:|---|---|
| 1 | `check:runtime-arbol` | el runtime que las demás dan por hecho existe (`python-embed/` y compañía), con el Python del sistema |
| 2 | `check:csp` | la CSP de producción trae lo que la app necesita |
| 3 | `check:rescoring-manifest` | los pesos declarados son los que hay |
| 4 | `check:m5-manifest` | el manifiesto de M5-Zn |
| 5 | `check:goldens` | las ocho corridas doradas, byte a byte |
| 6 | `check:pesos-stacking` | la interfaz y el backend resuelven los mismos pesos |
| 7 | `check:openbabel-fuente` | `tools/openbabel/` coincide con su manifiesto y **convierte una molécula de verdad** |
| 8 | `check:molcy-motor` | `tools/molcy/` (el motor de vídeo, GPL-3.0-or-later) es íntegro frente a su manifiesto, es la GPL y no lleva **ninguna ruta de una máquina** (`E:\blender.exe`) |
| 9 | `stage:desktop` | copia el runtime y precompila el bytecode del arranque |
| 10 | `check:openbabel` | la frontera con Open Babel **sobre el bundle staged** (ver abajo) |
| 11 | `verify:desktop-runtime` | imports, Vina, Open Babel, el motor Molcy **y** `/health` con el Python embebido |
| 12 | `check:evaluation-runtime` | una evaluación real con Vina termina, persiste y reaparece desde el bundle |
| 13 | `check:dossier-embebido` | el dossier del runtime embebido coincide con el de desarrollo |
| 14 | `build:desktop` | export estático de Next |
| 15 | `check:exported-api-url` | ningún puerto de backend horneado |
| 16 | `check:no-remote-assets` | ningún recurso remoto |
| — | `cargo` + NSIS | el instalador |
| — | `seal:installer` | SHA-256 y manifiesto de release |

**El orden de 9 y 10 no es casual.** `check:openbabel` mira el ARTEFACTO —sin
bindings de Open Babel en `site-packages`, sin resolución por `PATH`, hash y
versión correctos, conversión PDBQT→SDF real— así que sólo puede correr después
de `stage:desktop`. Comprobar el repositorio no habría detectado nada: las
pruebas del *código* estaban verdes mientras la aplicación instalada fallaba,
que es la restricción 1 de más abajo. Ver
`docs/79_ADR_FRONTERA_OPEN_BABEL.md`.

Además: `npm run smoke:prod` levanta el backend con el Python empaquetado y el
entorno exacto de `src-tauri/src/backend.rs`, sirve el export real con la CSP de
producción e inyecta un `window.__TAURI__`. **Ejecútalo antes de dar por buena
cualquier corrección que toque empaquetado, CSP o estilos.**

---

## Restricciones que no debes romper

Cada una viene de un fallo real que costó al menos un instalador.

1. **Lo que se verifica tiene que ser lo que se entrega.** Las 688 pruebas de
   frontend estaban verdes mientras la app instalada tenía cinco fallos
   simultáneos. Todas corrían sobre el *código*; los fallos vivían en el
   *artefacto*. Si añades una prueba para un problema de empaquetado, que mire
   `out/` o el binario, no el `.tsx`.

2. **Un guardián tiene que demostrar que ve.** Un detector nuestro quedó con un
   carácter `0x08` dentro de su expresión regular, recorrió 167 archivos y
   anunció «limpio» sobre un export sucio. Los guardianes de `frontend/scripts/`
   llevan autotest con muestras que deben detectar y muestras que no. Mantenlo.

3. **No adivines el puerto del backend.** Rust elige el primero libre de
   8000-8019 y lo entrega por `ensure_backend`. Caer a `:8000` te pone a hablar
   con el proceso ajeno que lo ocupe. `lib/config.ts` es el único dueño de esa
   dirección.

4. **Tauri reescribe la CSP.** Inyecta nonces, y un nonce **anula
   `'unsafe-inline'`** por especificación — con él se caen todos los
   `style={{...}}` de React. Por eso `tauri.conf.json` lleva
   `dangerousDisableAssetCspModification: ["style-src"]`. En `tauri dev` no
   ocurre, así que **desarrollo no prueba esto**.

5. **No edites `scripts/artifacts_science/`.** Son artefactos sellados con
   hashes. Cambiarles los bytes invalida el sellado.

6. **Los números científicos se citan con su condición.** Ejemplo vivo: la
   validez física de PoseBusters sólo es comparable bajo el protocolo de
   reconstrucción de hidrógenos documentado en `MF-33-H-COR`. Un número sin su
   condición es un número falso.

7. **Trabajo caro fuera del camino crítico.** El arranque pasó de ~57 s a ~6 s
   quitando dos cosas que nadie necesitaba para abrir la aplicación: un import
   de sondeo que arrastraba torch, y un precalentamiento de modelos que
   bloqueaba la ventana. Antes de añadir algo al arranque, mide con
   `python -X importtime`.
   **Y fuera del bucle de eventos.** Aquel import no desapareció: pasó a la
   primera evaluación, ejecutado por código síncrono dentro de funciones
   `async`, y congelaba el backend hasta 23 s (`/health` sin contestar, y la
   interfaz decía «El motor se desconectó»). Desde `async`, lo caro va en un
   hilo (`await asyncio.to_thread(...)`); `tests/test_bucle_de_eventos_libre.py`
   mide el latido del bucle y su guardián falla si `detect_hardware`,
   `predict_clgnn`, `predict_rescore`, `list_providers`, `analyze_complex` y
   compañía se llaman a pelo. Un hilo no basta si la llamada retiene el GIL
   (RDKit en C++): ahí hay que quitar la causa.
   **Y nada que se repita solo en la interfaz sin medir su memoria nativa.** Las
   pestañas no se desmontan: un temporizador sigue corriendo con la pestaña
   oculta y la app quieta. El editor de moléculas preguntaba `getSmiles()` a
   Ketcher cada 500 ms; cada llamada lleva al worker de Indigo 1,57 MB, que se
   quedan en el proceso de la página, **fuera** del heap de JS (que se veía
   plano). +200 MB/min en reposo, y en la VM de 10 GiB «Out of Memory» a la hora
   (`4fee8572`; ahora escucha `editor.subscribe("change")`). Si algo se repite,
   mide la memoria privada del proceso renderer, no `usedJSHeapSize`. Si aun así
   la página muere, `src-tauri/src/vigia_webview.rs` la recarga y escribe el
   motivo en `desktop-bootstrap.log` (comprobado matando el renderer de la app real).

8. **La rama de desarrollo no se empuja al repositorio público.** Su historial
   contiene manuscritos sin enviar, el deck y registros internos
   (`scripts/retenidos_del_publico.txt`) y una contraseña antigua del servidor.
   Se publica replicando commits sobre la rama `publico` en un worktree. El
   2026-09-21 alguien empujó `codex/release-hygiene` y el tag `v1.0.1` y las 56
   rutas quedaron públicas; el 2026-09-22 se borró el repositorio y se recreó
   desde `publico`, porque borrar la rama no quitaba los commits de la caché
   de GitHub (seguían descargándose por SHA). Desde entonces
   `scripts/check_push_publico.py` es un hook `pre-push` que rechaza cualquier
   ref cuyo historial las toque o que añada una credencial. Si el hook no
   está, instálalo con `--instalar` antes de empujar nada.

---

## Licencia

**PolyForm Noncommercial 1.0.0** ([`LICENSE`](LICENSE)). Permite usar,
estudiar, modificar y redistribuir MolDesign para fines no comerciales. Los
modelos propios ligeros incluidos se rigen por los mismos límites, explicitados
en [`LICENSE-MODELS`](LICENSE-MODELS).

MolDesign es **source-available**, no software de código abierto según la
definición OSI, porque el uso comercial está reservado. Cualquier uso comercial
requiere una licencia escrita separada; ver
[`COMMERCIAL-LICENSE.md`](COMMERCIAL-LICENSE.md). La tarifa, regalía o comisión
se negocia caso por caso: el repositorio no concede una tasa automática.

Las versiones ya publicadas bajo AGPL conservan irrevocablemente esa licencia.
La licencia actual sólo gobierna esta versión y las posteriores que se publiquen
bajo ella. Las contribuciones requieren firmar el [CLA](CLA.md) para mantener
consolidado el derecho de relicenciamiento.

La integración Solana es exclusivamente un **POC en devnet**. La firma ocurre
en el frontend con `@solana/web3.js`; el backend sólo prepara y verifica memos
por JSON-RPC estándar. No reintroduzcas `solana-py`, `solders`, `jsonalias` ni
una clave institucional. El modo escritorio usa una identidad efímera y SOL de
prueba; ninguna salida constituye certificación ni validez científica. Ver
`docs/83_ADR_SOLANA_DEVNET_POC.md`.
El runtime incluye además cinco DLL x64 de Microsoft Visual C++ 14.50.35719
como despliegue app-local; no están cubiertas por la licencia de MolDesign y su procedencia y hashes viven en
`tools/vc-runtime/`, que viaja también entero en el bundle. **El Blender que se descarga después también las
necesita** (VM-MOLCY-01, 2026-10-12): su `python.exe` auxiliar, el que lanza el gestor de extensiones, no hereda
el `blender.crt` de `blender.exe` y moría con 0xC0000135 en un Windows sin el redistribuible, así que Molecular
Nodes no se instalaba. `services/molcy/runtime_vc.py` las copia, verificadas contra el manifiesto, junto a ese
Python en el Blender administrado (sin pisar ninguna DLL que traiga Blender), antepone la carpeta al PATH de todo
subproceso de Blender (sin tocar el Blender del usuario) y la instalación prueba ese Python antes de pedirle nada
a Blender. Medido aquí: con las copias al lado, el Python de Blender 5.2.2 carga las de MolDesign y no las de
System32. **No medido:** un Windows limpio sin el redistribuible (esta máquina y la VM reparada lo tienen).

Dependencias con copyleft en el runtime distribuido: cinco paquetes LGPL
(`rpc-websockets`, `GridDataFormats`, `meeko`, `paramiko` y `MDAnalysis`, que el SBOM
no clasificaba hasta el 2026-10-11 porque su metadata abre con una fila de «=»), tres
paquetes Python y cinco crates de Rust bajo MPL-2.0 (`gemmi`, `certifi`, `tqdm`; `cssparser`,
`cssparser-macros`, `dtoa-short`, `option-ext`, `selectors`), un binario LGPL (xTB
6.7.1, `LGPL-3.0-or-later`, en `tools/xtb/`) **y dos programas GPL:
Open Babel 3.1.1.23, `GPL-2.0-only`**, que viaja en `tools/openbabel/`, **y el motor
Molcy, `GPL-3.0-or-later`, obra propia del producto** (scripts que se ejecutan dentro de
Blender; viaja en `tools/molcy/`, ver `docs/95_ADR_MOTOR_MOLCY_EN_EL_INSTALADOR.md`).
Blender y Molecular Nodes, también GPL-3.0-or-later, **no** viajan: el usuario los
descarga a petición. El inventario npm del SBOM lista además `@img/sharp-*`
(libvips, LGPL-3.0-or-later), que `next` arrastra para optimizar imágenes en un
servidor; el export estático no lo usa y el instalador sólo empaqueta `out/` y
`resources/` (medido el 2026-10-10: ningún fichero de libvips en `out/`). Ningún
componente que inventaría el SBOM (`docs/api/sbom.json`: paquetes Python y npm,
crates Rust del binario de Windows y binarios de terceros) **declara** AGPL ni
SSPL, y `generate_sbom.py --check` falla mientras algún componente quede sin
licencia —antes las crates Rust salían todas en blanco y la afirmación no se
sostenía—. «Declara» no es «contiene»: `padelpy` declaraba MIT y empaquetaba
AGPL, y por eso `check_copyleft_en_runtime.py` lee los textos de licencia (sólo
en Python). En Rust se midieron una vez, el 2026-10-03, sin automatizar: ver
`docs/86_CORRECCIONES_AUDITORIA_LUNA_20261002.md`. Las restricciones no
comerciales propias se declaran arriba.

Este párrafo ha estado mal dos veces, y las dos correcciones valen como aviso.

Decía «no hay GPL» y era falso: el detector de `scripts/generate_sbom.py` buscaba
la subcadena `GPL`, y Open Babel declara su licencia como `GNU GENERAL PUBLIC
LICENSE` —donde esa subcadena no aparece—, así que el gate quedaba verde con un
componente GPL dentro. El detector normaliza el nombre largo desde entonces.

Después decía que Open Babel «se invoca como biblioteca Python, no como
subproceso», y eso también era falso en el único punto de uso vivo: `vina_service`
ya lo invocaba por subproceso. Lo cierto era peor y más aburrido: los *bindings*
viajaban en `site-packages`, dos módulos de `rescoring/` los importaban, y el
binario se resolvía dentro del paquete Python con un respaldo a `"obabel"` a
secas que el `PATH` podía resolver a cualquier cosa.

**Resuelto el 2026-09-05.** Open Babel sigue en el instalador, pero como
**programa independiente**: fuera del entorno Python importable, con manifiesto,
hash, licencia y procedencia propios, invocado por un único adaptador
(`backend/services/external_tools/open_babel.py`) que verifica el hash antes de
ejecutar y **nunca** resuelve por `PATH`. Nueve guardas
(`scripts/check_openbabel_boundary.py`) bloquean el build si eso deja de ser
cierto. La decisión completa, con lo que queda prohibido y lo que sigue abierto
—incluida la recomendación de una revisión jurídica externa antes de vender
licencias comerciales—, está en `docs/79_ADR_FRONTERA_OPEN_BABEL.md`.

**No importes `openbabel`, `pybel` ni `_openbabel` desde `backend/` o
`rescoring/`.** No es una preferencia de estilo: los bindings GPL-2.0-only no pueden redistribuirse como una sola obra bajo PolyForm Noncommercial; un import destruiría la frontera de programa independiente.

La regla vale para **todo** el árbol de esos dos directorios —también `tests/`,
`scripts/` y `data/`—, y la guarda G1 la comprueba con AST sobre todos los `.py`,
incluidos los imports dinámicos con nombre constante; un archivo que no puede
analizar es un fallo, no un «limpio». Sólo admite **cuatro excepciones**, nombradas
una a una con su motivo en `EXCEPCIONES_DEV_ONLY`
(`scripts/check_openbabel_boundary.py`): scripts de desarrollo que **no viajan en el
instalador** —`bundle_helper` los excluye, y G2 y G1 sobre el bundle lo comprueban
sin ninguna exención—:

- `rescoring/generate_gpu_dataset.py`
- `rescoring/RTMScore/feats/extract_pocket_prody.py`
- `rescoring/scripts/redock_pdbbind.py`
- `rescoring/scripts/test_crystal_vs_docked.py`

`redock_pdbbind.py` no se reescribe porque respalda la procedencia sellada de cinco
artefactos (1414 registros declaran el receptor «openbabel_pdb2pdbqt_rigido»; en
FND-06, 470 lo citan como el código de preparación) y reescribirlo cambiaría lo
medido; los otros tres son generadores y experimentos de desarrollo que ningún
módulo del producto importa. **Una quinta excepción es decisión del propietario, no
un parche de la guarda.** Decisión y medidas en
`docs/86_CORRECCIONES_AUDITORIA_LUNA_20261002.md` (LUNA-01).

**Lo mismo con el motor Molcy, que es GPL-3.0-or-later.** No importes `bpy`, `bl_ext` ni
módulos del motor (`maestro`, `nucleo`, `correr_caso`) desde `backend/` o `rescoring/`, y que
nada de `tools/molcy/` importe `backend`, `services` ni `api`: el motor se ejecuta sólo por
subproceso (`backend/services/molcy/renderer.py`) y se comunica por ficheros; el backend verifica
su manifiesto antes de ejecutarlo (`backend/services/molcy/motor.py`). Nunca se edita
`tools/molcy/` a mano: se vendoriza desde un commit del repositorio del motor con
`scripts/stage_molcy_motor.py`, y la puerta `check:molcy-motor` falla si un fichero difiere de su
manifiesto o si el código lleva una ruta de una máquina. Lo guarda
`backend/tests/test_frontera_motor_molcy.py`. El repositorio del motor es público
(<https://github.com/srcacahuate619/moldesign-molcy>) y es la oferta de código fuente que pide la
GPL: el `fuente.commit` del manifiesto debe existir ahí. Ver `docs/95_ADR_MOTOR_MOLCY_EN_EL_INSTALADOR.md`.

**El cierre de MolDesign es obligatorio en todo vídeo (decisión del propietario, estrategia de
marketing).** No añadas ningún ajuste, formato, argumento ni campo de la interfaz que lo omita o
lo acorte, ni ninguna ruta para elegir otro motor desde la aplicación: el backend sólo ejecuta el
motor incluido y rechaza `motor` en la configuración; un motor propio exige
`MOLCY_PERMITIR_MOTOR_PROPIO=1` (desarrollo). El backend no da por completo un vídeo cuyo acta no
acredite el cierre o cuyo MP4 dure menos de lo esperado (`backend/services/molcy/cierre.py`). Un
vídeo sin cierre es un defecto, no una variante. Los límites honestos (la GPL permite modificar la
copia propia) están en el ADR 95.

**El vídeo es sólo con GPU; la CPU toma fotos, y toda foto lleva la marca de MolDesign (decisión del
propietario, 2026-10-08).** No vuelvas a ofrecer vídeo por CPU desde la aplicación: medido, tres segundos
no enseñaban nada y costaban minutos. Las fotos se rinden siempre con Cycles (CPU o GPU), de 720p a 4K,
y el backend les pone el emblema, sutil, en una esquina libre de rótulos y borra el PNG sin marca
(`backend/services/molcy/marca_foto.py`, `fotos.py`). No añadas ningún ajuste que quite la marca ni una
ruta que sirva una foto sin ella. Ver la sección «Fotos» del ADR 95.

**El tutorial de Molcy del Inicio se genera, no se retoca.** «Del caso al vídeo, en seis pasos»
(`frontend/components/inicio/TutorialMolcy.tsx`) enseña capturas reales de la aplicación en castellano
o en inglés, con el control de cada paso señalado por un recuadro y una flecha que van encima de la
imagen. Las capturas (`frontend/public/tutorial/molcy/{es,en}/`) y la caja de cada control
(`frontend/lib/tutorial/molcy-marcas.json`) las escribe `frontend/scripts/capturas-tutorial-molcy.mjs`
contra una cápsula de QA nueva por idioma, con Vina real. Si cambia Evaluación o Molcy, se regeneran;
no se editan a mano ni se mueve una caja para que «cuadre».

Además, **6 paquetes Python y 5 npm** no declaran licencia en su metadata y se
resolvieron leyendo el archivo de licencia que viaja dentro del propio paquete
—entre ellos `tabpfn`, cuyas condiciones no son las de sus dependencias, y
`MDAnalysis` y `kiwisolver`, que copian el texto entero en la metadata—. El SBOM
los lista en `licencias_resueltas_por_evidencia`, **no** en
`sin_licencia_declarada`: esa sección lleva una lista por ecosistema (Python,
npm, Rust y binarios) y debe estar vacía para release.
`backend/tests/test_sbom_inventario.py` comprueba los dos conteos de este
párrafo contra el SBOM. Ver `docs/69_GATE_DE_RELEASE.md`.

---

## Estado y honestidad

- Backend: **5413** pruebas recolectadas con el intérprete que se distribuye
  (`python-embed`, 3.11.9; `docs/api/test-counts.json` cuenta 5411 con su propio criterio), medidas el 2026-10-24 al cerrar 1.0.4
  sin construir: **5385 pasan, 26 saltadas, 2 xfail y 0 fallos** (9,6 min). Además `scripts/tests` 262, `rescoring/tests` 321,
  frontend 2105 en 229 archivos, `tsc` limpio, `cargo check --locked` limpio y todos los `--check` de `ci.yml` en verde (más
  `build_sitio_publico --check` y `generate_catalog_availability --check`). Antes, el 2026-10-23 sobre `14fd5e4d`: 5371 pasan de
  5397. Antes, el 2026-10-22 sobre la consolidación de `claude/fase-1b`: 5333
  pasan de 5372, `scripts/tests` 262 y `rescoring/tests` 318. Antes, el
  mismo día sobre `5727bda4`: 5302 pasan, con tres errores por `WinError 10055` (búferes de socket
  de Windows) que pasan aislados; `scripts/tests` 165.
  Antes: 4878 el 2026-10-12 sobre `0659a7ce`. Con el intérprete de
  desarrollo (3.14.3) se recolectaban **4900** el 2026-10-11 sobre `a27ded64`, con 4850 en
  python-embed: las 50 de diferencia son `importorskip`
  cuya dependencia no viaja en el bundle, y por eso el número que vale es el
  del runtime embebido. Ejemplo: `pypdf` no está en el runtime, así que las
  pruebas que extraen texto del PDF se saltan con python-embed y sólo corren con
  el de desarrollo. Ejecutada entera con python-embed el 2026-10-11 en el árbol
  principal, con el backend de `f183e0af`: **4766 pasan, 22 saltadas, 2 xfail y 0
  fallos** (9,5 min). De las 22 saltadas, 18 son por `pypdf` y las otras 4 son sueltas
  (sin ADMET-AI para medir latidos, un parámetro vacío, un comportamiento fuera de
  Windows y un microestado único). En un worktree limpio, con el mismo intérprete, pasan
  4718 y se saltan 63 (la diferencia no se investigó). Repetida en un worktree con la
  integración de MET-01 y el arreglo de la lista de cofactores, antes de su cambio del PDF:
  **4783 pasan, 63 saltadas, 2 xfail y 0 fallos** (9 min). Antes del primer build de
  1.0.2, en un worktree limpio sobre `0659a7ce`: **4843 pasan, 35 saltadas, 2 xfail y 0
  fallos** (10,6 min, con la máquina ocupada en el stage). La última, antes del segundo
  build, en el worktree del build sobre `dd09e229`: **4868 pasan, 35 saltadas, 2 xfail y
  0 fallos** (10,7 min).
  Frontend: **2105** en 229 archivos, todas en verde (medido el 2026-10-24 al cerrar 1.0.4; antes, el 2026-10-22 sobre la rama de
  integración; antes, 2047 el 2026-10-12 sobre `96d18d9a`). `tsc` y `check:csp` limpios. Con la máquina cargada, una prueba de
  Preparación (`tautomeroMinoritario.test.tsx`) llegó a agotar su tiempo; aislada y con
  la suite repetida en reposo, pasa.
  **Las instantáneas y los conteos se escriben con python-embed.** El manifiesto
  de la instantánea española del dossier lleva el hash del PDF, y el PDF depende
  de la versión de reportlab: 4.2.0 en el runtime y en la CI, 4.5.1 en el Python
  de desarrollo. Escrita con la 4.5.1, la prueba falló del 2026-10-06 al 10-09.
  Ahora `tests/dossier_snapshot.py --write` se niega con otro reportlab, y la
  prueba salta sólo el manifiesto, diciendo por qué.
  El conteo del backend lo mantiene `scripts/report_test_counts.py`, que
  escribe `docs/api/test-counts.json`: esa es la fuente, no este párrafo.
  Este párrafo ya envejeció tres veces —decía 2117 y 889, luego 2518 cuando
  el registro ya daba 2542, y luego 2571 cuando daba 2792— mientras el registro
  estaba al día; si vuelven a discrepar, manda el registro. (El 2026-10-10 el
  propio registro se había quedado atrás: daba 4423 con 4441 recolectadas.)
  Cuidado con `report_test_counts.py --check`: sólo falla si una suite **dejó**
  de recolectar, que es la guardia contra un `importorskip` perdido. Un conteo
  que creció lo deja pasar, así que después de añadir pruebas hay que ejecutar
  `--write`.
- Smoke de producción: **63/63** (2026-10-12, sobre `dd09e229` en el worktree del segundo
  build, con `test:e2e` 13/13 y `test:ux` 12/12; antes, igual sobre `0659a7ce` en un worktree limpio;
  export y runtime staged, CSP de producción y datos temporales; incluye la API de
  Molcy, su raíz instalada, el catálogo de Molcy, el selector de lotes y 12 rutas de la
  API en cada idioma). Se montó en un worktree para que el export no arrastre trabajo sin
  commitear de otra sesión: junctions a `python-embed`, `tools\xtb`,
  `tools\openbabel\bin` y `frontend\node_modules`, y enlaces duros a los binarios
  ignorados de `tools\vina` y `tools\llama`. En ese mismo worktree pasan las 16 puertas
  del build (incluida la 12, con dos corridas reales de Vina desde el bundle), Playwright
  (`test:e2e` 13/13 y `test:ux` 12/12, con `CI=1` para no reutilizar un servidor ajeno en
  :3100) y todos los `--check` de `ci.yml` con python-embed. `cargo fmt --check`,
  `clippy -D warnings` y `cargo test` (103) los pasó sobre `bb88bf0f` (el vigía de WebView2)
  la sesión que lo escribió; el Rust no cambió después. **Cubre el export y el
  runtime, no el instalador:** WebView2, NSIS y una
  máquina limpia siguen sin probarse aquí. El anterior era de 18/18 (2026-10-03); repítelo
  si cambia el frontend, el CSP o el empaquetado.
- Sellos: **187** experimentos sellados (`python scripts/validar_sellos.py --check`,
  paso de la CI; 172 con MET-01-R1, 2 más con CAL-D-01 R4 y R4B, 1 con ABS-TR-01-VALIDEZ y 3 de la fase 1b: REC-07-R1, RS-03-PARAM-A-R1 y MF-33-EXT-MOD-R1, integrados el 2026-10-22; MET-02-SEMILLA y MET-02-R1-SEMILLA el 2026-10-23; y FEP-06-PRE, sellado al cerrar, ABS-TR-01-VALIDEZ-R1 y CAL-D-01-R4-2-VMAT2-8T69, el 2026-10-24; FEP-06-PRE-2, VISION-MOLECULAR-01, SUP-02-TOTAL-SCORE y SUP-03-VALIDADOR-LIGANDO, el 2026-10-25). **Un clon del repositorio público
  valida 185**, no 187: FEP-06-PRE y FEP-06-PRE-2 están en `scripts/retenidos_del_publico.txt` mientras la
  ronda FEP-06-HUM pueda reutilizar sus paquetes, y el registro y la web públicos se regeneran sin ellos
  (medido el 2026-10-25 sobre `b361d730` en un clon limpio: 6684 ficheros verificados, cero ausentes y cero
  distintos). El 2026-10-23, 7035 ficheros verificados, cero ausentes y cero distintos. El 2026-10-21, con MET-01-R1 integrado en `claude/auditoria-ciencia-arreglos`:
  5304 ficheros verificados, cero ausentes y cero distintos (723 no distribuidos, todos
  declarados). El 2026-10-11, con FEP-09, FEP-09-R1 y MET-01 integrados, validaban con
  python-embed desde un worktree sin archivos ignorados en `scripts/artifacts_science/`:
  4263 ficheros verificados, cero ausentes y cero distintos (738 no distribuidos, todos
  declarados); la CI lo repite desde un clon limpio. Lo que no viaja (PDBBind, runtime) está declarado en
  `scripts/sellos_no_distribuidos.json`. El 2026-09-23 un clon limpio validaba 12.
  Ojo: `scripts/artifacts_science/*/_work/` está en `.gitignore`. Si un sello
  incluye archivos de `_work/`, hay que versionarlos a la fuerza (`git add -f`): un
  `validate` verde en un worktree no prueba que git los tenga (`CAL-8HFI-01` dio 63
  AUSENTES desde el árbol principal hasta `e9b032ae`).
- CI: instala `backend/requirements-embed.lock.txt`, la lista exacta del
  intérprete distribuido, no `requirements-desktop.txt`. El 2026-10-09 cuatro
  pasos del backend llevaban días en rojo sin que nadie lo viera: el contrato
  OpenAPI, el inventario del runtime, la instantánea del dossier y tres pruebas
  de la traza de Vina que daban error sin los binarios. El 2026-10-10 volvió a
  pasar con el contrato OpenAPI: la versión 1.0.2 y los campos nuevos de la subida
  de receptores (`modo_preparacion`, `source_file`) no estaban regenerados. Ese
  día, con el contrato regenerado, todos los `--check` de `ci.yml` pasan con
  python-embed (sellos, inventario, SBOM con 168 paquetes Python, 1267 npm, 331
  Rust y 5 binarios, lockfile, frontera de Open Babel, pesos del stacking,
  manifiesto de modelos y enlaces). **Antes de integrar en la rama de una
  versión, pasa con python-embed todos los `--check` de `ci.yml`**, no sólo
  pytest.
- **Inventario de supuestos `SUPUESTOS-01` (2026-10-25).** Lo que el producto da por hecho sin medida, en dos barridos
  independientes: 50 entradas de Claude y 303 de Sol 6.1 (validadas cita por cita contra el commit; 14 de 15 correctas en una
  muestra a mano). La entrega está en `E:\SUPUESTOS-01\`. Se miden por coste, con registro previo:
  - **`SUP-02-TOTAL-SCORE` (NO_GO):** el `total_score` de 0 a 100 que SAR, Comunidad y Moldex enseñan como calidad no ordena
    mejor que Vina (8T69: ρ 0,397 frente a 0,392; 8HFI: 0,03 frente a 0,13).
  - **`SUP-03-VALIDADOR-LIGANDO` (GO):** las cuatro reglas bloqueantes del validador no rechazan ninguna de 640 moléculas con
    actividad medida.
  - Pendiente de decidir: las 5 poses por defecto de la API frente a las 9 de la interfaz.
- Arranque medido en entorno de producción: **~6 s**.
- **Cero usuarios externos** todavía. El propio roadmap identifica esto como el
  riesgo de muerte real del proyecto, por encima del científico.
- La ciencia de ESMFold **no está validada**: está probado que carga y sirve
  poses, no que las poses sean buenas.

Si encuentras una afirmación en este repositorio que no puedas rastrear hasta
una medida, trátala como un defecto y dilo.
