# MM-GBSA: validación numérica del candidato, no validación de afinidad

Estado: **EXPERIMENTAL_NOT_ENABLED**. La autorización del usuario permite reparar
el protocolo y descargar referencias en un entorno aislado en E:. No se hizo
build, no se instaló nada en python-embed y no se añadieron motores al producto.

## Resultado medido

Ocho ligandos diagnósticos, tres condiciones cada uno: vacío, GBn2 sin término
no polar y GBn2+LCPO. AmberTools 24.8 (sander) y OpenMM 8.5.2 reciben exactamente
el mismo prmtop y las mismas coordenadas. Son geometrías de prueba generadas con
semilla 20260917, **no poses experimentales ni resultados de docking**.

**23/24 comparaciones pasan** los criterios declarados. El clorobenceno con
LCPO no pasa y sigue como bloqueo explícito de activación. Los archivos raw de
las seis iteraciones permanecen separados en E:/MolDesign-science/2026-09-17;
no se borraron los experimentos fallidos.

| Ligando | Átomos con H | Ángulos | Vacío | GBn2 | GBn2+LCPO |
|---|---:|---:|---|---|---|
| ethanol | 9 | 13 | Sí | Sí | Sí |
| benzene | 12 | 18 | Sí | Sí | Sí |
| aspirin | 21 | 32 | Sí | Sí | Sí |
| chlorobenzene | 12 | 18 | Sí | Sí | No |
| acetate | 7 | 9 | Sí | Sí | Sí |
| methylammonium | 8 | 12 | Sí | Sí | Sí |
| dimethylphosphate | 13 | 20 | Sí | Sí | Sí |
| imidazole | 9 | 13 | Sí | Sí | Sí |

## Qué se corrigió y cómo se comprobó

1. **Tipado legacy incompleto.** GAFF2/AM1-BCC produce todos los ángulos de los
   ocho grafos. Etanol pasa de 10/13 a 13/13 y benceno de 6/18 a 18/18 en el
   candidato. Se verifica número de átomos, elementos, conectividad y una
   correspondencia biyectiva por coordenadas (máximo 0.001 Å de conversión).
2. **Cargas.** Se conserva ligand.raw.mol2. Se aplica el desplazamiento uniforme
   para conservar carga formal que usa el wrapper AmberTools de OpenFF por
   defecto, acotado por el redondeo de salida de sqm. Se registra el déficit y
   la corrección, no se confunde con una nueva predicción de cargas.
3. **GBn2 y fósforo.** OpenMM 8.5.2 usa valores por defecto para P fuera de
   residuos nucleicos; Amber asigna sus valores específicos de P también allí.
   El candidato cambia sólo alpha/beta/gamma de esos átomos mediante un
   adaptador explícito con comprobación de esquema. No modifica paquetes
   instalados ni usa un parche global. El error observado de ~50.924 kcal/mol
   desaparece al compararlo con sander; las cargas, radios y screening no cambian.
4. **LCPO y tipos GAFF.** Amber convierte el nombre del tipo a mayúsculas antes
   de buscar parámetros. OpenMM 8.5.2 compara O/N3/SH distinguiendo mayúsculas.
   El adaptador limita esa normalización a la búsqueda LCPO, conservando los
   tipos bonded originales. Resuelve las diferencias de aspirina, acetato y
   dimetilfosfato.
5. **Cloro, todavía abierto.** Amber avisa `Using carbon SA parms for atom typeCL`.
   OpenMM incluye parámetros específicos Cl de la publicación LCPO. No se copió
   el fallback carbono para conseguir paridad. La discrepancia residual es
   ~0.162782 kcal/mol y ~0.045100 kcal/mol/Å en fuerza. Hace falta una referencia
   independiente apropiada y una decisión de dominio, no ampliar tolerancias.

Fuentes primarias consultadas:
- [Amber, asignación GBn2 y LCPO](https://github.com/Amber-MD/AmberClassic/blob/main/src/msander/mdread.F90).
- [OpenMM, parámetros GB](https://github.com/openmm/openmm/blob/8.5.2/wrappers/python/openmm/app/internal/customgbforces.py).
- [OpenMM, parámetros LCPO](https://github.com/openmm/openmm/blob/8.5.2/wrappers/python/openmm/app/internal/lcpo.py).
- [OpenFF, wrapper AmberTools y normalización](https://github.com/openforcefield/openff-toolkit/blob/main/openff/toolkit/utils/ambertools_wrapper.py).

Los hashes de las fuentes consultadas están registrados; la fuente upstream
AmberClassic no se identifica como el código exacto del binario 24.8. La prueba
independiente se ejecutó contra ese binario, cuya versión/build se conserva.

## Tolerancias y diferencias de constantes

Criterios: residual energético <0.001 kcal/mol y diferencia máxima de fuerza
<0.001 kcal/mol/Å. OpenMM y Amber usan constantes electrostáticas distintas.
Se conserva la diferencia bruta y, por separado, se convierte analíticamente
con 18.2223² (Amber), 138.93545764438198 y 138.935485 kJ·nm/mol (OpenMM NB y GB).
La conversión usa las contribuciones electrostáticas de sander; no se ajustó
ningún coeficiente a estos ocho ligandos. Los pequeños errores brutos de varias
milésimas de kcal/mol no se ocultaron ni se declararon igualdad byte a byte.

OpenMM emite avisos `Non-optimal GB parameters` para aspirina y acetato. Se
conservan: el experimento usa los mismos radios prmtop mbondi3 que Amber para
comparar implementaciones. Eso **no demuestra que esos radios sean óptimos
para predecir afinidades**.

## Efecto en producción actual

`validate_ligand_system` se ejecuta ANTES de minimizar en las dos entradas del
motor legacy. Rechaza enlaces/ángulos sin término ni restricción aplicable,
cargas GB/electrostática incoherentes y excepciones de carga vacías cuando no
corresponde. Devuelve un error explícito; no fabrica una energía.

Esto puede hacer que MM-GBSA legacy se abstenga con frecuencia mientras se
valida el reemplazo. Es una limitación real y transitoria, no disponibilidad
restaurada. La guardia es necesaria pero no suficiente: no demuestra tipado
correcto, cobertura completa de torsiones ni validez predictiva.

Se retiró la afirmación del contrato backend de que el motor legacy sirve para
ordenar poses porque sus errores se cancelan: no había una medida que lo probara.
Los resultados históricos no fueron recalculados ni reescritos.

## Reproducibilidad y pruebas

- Referencias compactas: `backend/audits/amber_reference/`, con prmtop, inpcrd,
  SDF, energías/fuerzas independientes, hashes y manifiesto.
- Entorno y archivos grandes: `E:/MolDesign-science/2026-09-17` y distribución
  WSL `MolDesign-Science-20260917`, almacenada allí.
- Lock de 259 paquetes con URLs/builds/MD5; versiones, hashes de origen y licencias
  declaradas de las dependencias principales en reference-packages.json.
  Es un entorno de investigación, no una aprobación de redistribución comercial.
- OpenMM 8.5.2 del runtime Windows reproduce offline las 23 condiciones aceptadas.
  Un test separado mantiene el desacuerdo del cloro como bloqueo de activación.
- **64 pruebas focalizadas aprobadas**, con 6 avisos GB conservados.
  Log: backend/hardening-mmgbsa-science-gates.log.

Para repetir el experimento en un directorio NUEVO:

```text
python backend/audits/amber_openmm_reference.py --output <directorio-nuevo>
```

Se requiere el entorno de referencia; no se descarga nada desde este script.
Sale con código 1 mientras quede una condición no concordante, aunque los tests
operativos pasen. La regresión Windows no requiere AmberTools ni Internet.

## Puertas que siguen pendientes antes de activar el reemplazo

1. Resolver la referencia LCPO para halógenos; ampliar elementos y estados de carga.
   **Referencia contestada para F, Cl, Br e I el 2026-09-23** (ver la sección
   final): queda decidir qué hacer con Br e I, que el candidato no soporta.
2. Comprobar estereoquímica, orden de enlace y correspondencia atómica en poses
   reales, con permutaciones y tautomería/protonación explícitas.
3. Validar sistemas receptor-ligando completos y sus tres subsistemas, retención
   de aguas/metales/cofactores, decisiones de preparación, hashes y minimización.
4. Definir qué energía se reporta, condiciones dieléctricas, entropía y alcance.
   La concordancia de energías potenciales no las convierte en ΔG experimental.
5. Evaluar poses y series con referencias experimentales independientes,
   incertidumbre y dominio; no entrenar ni seleccionar parámetros con el test.
6. Empaquetado Windows, dependencia opcional offline y licencias del reemplazo.
   No convertir WSL en un requisito del producto por accidente.

**No se acredita equivalencia con Schrödinger ni se cierra MolDesign 1.0.1.**


Regresión completa posterior a la guardia y referencias: **2416 passed,
10 skipped, 1 failed**, 14 warnings, 337.09 s. El fallo es el guardián preexistente
de texto frontend, fuera del alcance. Log: hardening-science-verified-full.log.
Esto verifica regresiones de software; no convierte las 23/24 comparaciones
numéricas en validación de actividad biológica ni de energía libre de unión.


Protección de transporte Git: las referencias usan `.gitattributes` con `-text`
para conservar bytes exactos; las rutas del manifiesto usan `/` en ambos sistemas.
Se verificaron los SHA-256 de los **30 artefactos directamente desde el índice de
Git**, no sólo del working tree. Regresión posterior: 25 passed (referencias y
bloqueo de cloro); log hardening-reference-git.log. No cambió ningún parámetro.


## El desacuerdo del cloro, atribuido por completo (2026-09-17, tarde)

La puerta 1 decía: «Resolver la referencia LCPO para halógenos». Faltaba un paso
previo que sí se podía dar sin referencia nueva y sin AmberTools: averiguar **qué**
exactamente produce los 0.162782 kcal/mol, para poder afirmar que detrás de ellos
no hay un segundo error de implementación escondido.

Amber avisa `Using carbon SA parms for atom type CL` y no dice cuáles. Se midió:
sustituyendo sólo los cinco valores LCPO del cloro por cada entrada de carbono de
la tabla, con la geometría y el prmtop de referencia, y comparando contra sander.

| parámetros aplicados al Cl | residual (kcal/mol) | fuerza máx. (kcal/mol/Å) |
|---|---:|---:|
| **`C_sp2_2` completa (radio 1.7 Å)** | **1.3e-08** | **6.5e-05** |
| `C_sp3_2` con radio 1.7 | 0.0131 | 0.0043 |
| `C_sp2_2` con radio 1.8 | 0.0130 | 0.0010 |
| `C_sp3_1` con radio 1.7 | 0.0906 | 0.0204 |
| `C_sp3_3` con radio 1.7 | −0.1089 | 0.0191 |
| Cl publicado (Weiser, radio 1.8) | 0.162782 | 0.045100 |
| `C_sp2_3` con radio 1.7 | −0.1714 | 0.0303 |

Hay una única coincidencia, y es exacta: la entrada `C_sp2_2` completa, radio
incluido. Con ella el clorobenceno GBn2+LCPO concuerda con sander en 1.3e-08
kcal/mol de energía y 6.5e-05 kcal/mol/Å de fuerza, **dentro de los criterios ya
declarados, que no se han tocado**. El caso sin término no polar ya concordaba
con residual 7.1e-09, así que la divergencia está confinada al término de
superficie y no a la parametrización ni al GB.

Conclusión, con su límite: el residual **está completamente atribuido** a una
divergencia de parámetros conocida y ahora identificada numéricamente. No queda
error sin explicar. Lo que sigue abierto es distinto y más pequeño: **cuál de los
dos conjuntos es el correcto**, que es una decisión de dominio.

Y por eso el bloqueo se mantiene. Adoptar el respaldo de carbono daría paridad
perfecta, y eso es precisamente una razón para no hacerlo sin una decisión
explícita: sería elegir el parámetro por el resultado de la comparación. Además,
la evidencia disponible apunta a que el candidato es el que usa los valores
publicados: OpenMM 8.5.2 lo documenta en su propio código —«Cl is the only
element in the LCPO paper not implemented in Amber»— y los parámetros Cl de la
tabla son los del artículo de Weiser, Shenkin y Still (1999). Es decir, la
referencia sería aquí la que aproxima, no el candidato. Afirmar eso como cierto
exige una referencia independiente para el área superficial de halógenos, que es
lo que la puerta 1 sigue pidiendo.

Dos pruebas nuevas lo sostienen, sin AmberTools y sin red:

- `test_el_desacuerdo_del_cloro_esta_completamente_atribuido` reproduce la
  atribución sobre el artefacto de referencia y comprueba que toda la diferencia
  entre las dos lecturas ES el residual publicado.
- `test_produccion_no_copia_el_respaldo_de_carbono_para_el_cloro` falla si el
  adaptador empieza a manipular la tabla LCPO. Sin ella, alguien podría hacer
  pasar la comparación sustituyendo el cloro y el bloqueo científico desaparecería
  sin que nadie lo hubiera decidido.

La atribución se verificó por unicidad: cambiar la entrada de carbono asumida a
`C_sp3_1`, `C_sp3_2` o al propio Cl publicado hace caer la prueba. Ninguna otra
combinación de la tabla reproduce a sander.

**Lo que esto NO cierra.** La puerta 1 sigue abierta en su parte de dominio y en
la ampliación a más halógenos y estados de carga; sólo hay un caso con cloro y
ninguno con flúor, bromo o yodo. Las puertas 2 a 6 no se han tocado. El estado
del protocolo sigue siendo `EXPERIMENTAL_NOT_ENABLED` y 23/24 sigue siendo 23/24:
esta sección no convierte el caso fallido en aprobado, porque para eso habría que
cambiar los parámetros de producción.

## Un prerrequisito de la puerta 2, resuelto aparte

La puerta 2 pide comprobar «estereoquímica, orden de enlace y correspondencia
atómica en poses reales». Antes de eso hacía falta algo más básico que no estaba
garantizado: **que la pose que llega al motor sea la pose acoplada**. Un resultado
de ensemble no conserva un archivo único de poses, y el endpoint sólo podía
abstenerse.

`services/docking/pose_recovery.py` cierra esa mitad —ver ENS-04 en
[la revisión del ensamble](ENSEMBLE_REVIEW.md)—: recupera el registro exacto tras
comprobar el hash del artefacto, el hash de la conformación de entrada, la
correspondencia de átomos pesados y cada coordenada del bloque PDBQT entregado,
y se abstiene con el motivo cuando algo no cuadra. Nunca reconstruye desde SMILES.

Eso es identidad de la entrada, no la puerta 2: sigue faltando comprobar
estereoquímica, órdenes de enlace, permutaciones y estados de tautomería y
protonación del sistema parametrizado. Y no activa nada: la guardia
`validate_ligand_system` sigue rechazando sistemas incompletos antes de minimizar.

## Verificación de esta continuación

27 pruebas de paridad Amber, incluidas las dos nuevas del cloro, sin AmberTools y
sin red. Suite completa con el Python embebido sobre el código final: **2495
passed, 10 skipped, 1 failed**, 14 warnings, 336.21 s, de 2505 recolectadas; el
fallo es el guardián preexistente de texto del frontend, fuera de alcance. Log:
`hardening-ensemble-identidad-full.log`. Los seis avisos `Non-optimal GB
parameters` se conservan.

No se cambió ningún parámetro de producción, ningún criterio de tolerancia y
ningún archivo de `amber_reference/`. Esto verifica software; no convierte
23/24 en 24/24 ni las comparaciones numéricas en validación de energía libre.

## El cloro, adjudicado contra la geometría (2026-09-19)

La puerta 1 pedía «resolver la referencia LCPO para halógenos». La entrada
anterior dejó el residual **completamente atribuido** —es la entrada `C_sp2_2`
que Amber usa como respaldo de carbono— y una pregunta abierta que se declaró
como decisión de dominio: **cuál de los dos conjuntos es el correcto**. La única
evidencia entonces era un comentario en el fuente de OpenMM.

Esa pregunta sí tiene forma medible, y no hacía falta AmberTools, ni red, ni una
referencia experimental nueva. LCPO **es una aproximación analítica de la SASA**:
ése es todo su trabajo. Así que:

> ¿Cuál de las dos parametrizaciones aproxima mejor la SASA numéricamente
> exacta del mismo átomo, en la misma geometría, con su propio radio?

No se compara contra Amber ni contra OpenMM. Se compara contra la geometría.

### Antes de usar la regla, se calibra

Una diferencia en Å² no dice nada sin saber cuánto se equivoca LCPO cuando **sí**
está bien parametrizado. Sobre los 46 átomos con superficie de los
ocho ligandos de referencia cuyo tipo Amber y OpenMM asignan de acuerdo,
|LCPO − SASA exacta| por átomo vale:

| mediana | media | p90 | máximo |
|---:|---:|---:|---:|
| 2.286 Å² | 2.9439 Å² | 6.1776 Å² | 9.1928 Å² |

Ése es el error normal de LCPO. El cloro se lee contra él, no contra cero.

### La medida

| parámetros aplicados al Cl | radio | SASA exacta | LCPO | error | en energía |
|---|---:|---:|---:|---:|---:|
| **Cl publicado (Weiser 1999)** | 1.8 Å | 75.7891 Å² | 73.5012 Å² | **-2.2878 Å²** | -0.011439 kcal/mol |
| Respaldo de carbono de Amber (`C_sp2_2`) | 1.7 Å | 69.22 Å² | 40.0975 Å² | **-29.1226 Å²** | -0.145613 kcal/mol |
| *Diagnóstico*: carbono terminal (`C_sp3_1`) | 1.7 Å | 69.22 Å² | 58.2154 Å² | -11.0047 Å² | -0.055023 kcal/mol |

El cloro publicado se equivoca en 2.2878 Å²: la mediana
del error de fondo es 2.286 Å². El respaldo de carbono se equivoca en
29.1226 Å², que es **3.2 veces el peor error de fondo**
observado y 13 veces la mediana.

La tercera fila no la propone nadie: separa dos causas que de otro modo se
confundirían. `C_sp2_2` está fijado para un carbono sp2 con **dos** vecinos
pesados, y este cloro tiene **uno**. Con la única entrada de carbono terminal de
la tabla —mismo radio 1.7 Å— el error baja de 29.1226 a
11.0047 Å²: la mayor parte del fallo del respaldo es la
**clase de conectividad**, no el radio. Pero ni siquiera el mejor carbono llega
al error normal: 11.0047 Å² sigue por encima del máximo
de fondo (9.1928 Å²).

### El ancla

La diferencia entre las dos parametrizaciones es
32.5565 Å² de superficie
LCPO. Multiplicada por la tensión superficial de Amber (0.005 kcal/mol/Å²) da
**0.162782 kcal/mol**: exactamente el residual que `report.json` declara para el
clorobenceno con GBn2+LCPO. No es un experimento paralelo, es el mismo hecho
medido por otra vía.

### Lo que sostiene la medida

Dos guardianes, porque un detector tiene que demostrar que ve:

1. **La implementación propia de LCPO reproduce la de producción.** La suma de
   las áreas por átomo, multiplicada por la tensión superficial, reproduce la
   energía de `LCPOForce` construida por `add_gaff_lcpo_force` en los ocho
   ligandos, con desvío ≤ 5.7e-14 Å². Un desglose por átomo que no suma el total
   sería un desglose inventado.
2. **La SASA numérica declara su convergencia.** Shrake-Rupley con dos mallas
   independientes y cuatro densidades. Sobre el clorobenceno, a 200.000 puntos
   por átomo las dos mallas concuerdan en 0.0045 Å²
   para la molécula entera (a 2.000 puntos, 0.3979 Å²).
   El efecto que se mide son ~27 Å²: cuatro órdenes de magnitud por encima del
   ruido de discretización.

Código: [`lcpo_vs_sasa_exacta.py`](lcpo_vs_sasa_exacta.py); datos:
[`lcpo_vs_sasa_exacta.json`](lcpo_vs_sasa_exacta.json); pruebas:
`backend/tests/test_lcpo_aproxima_la_sasa_exacta.py` (12, con el runtime
embebido y sin red).

### Qué cambia y qué no

**Cambia** el estado epistémico de la puerta 1. Antes: «la evidencia disponible
apunta a que el candidato usa los valores publicados, pero afirmarlo exige una
referencia independiente». Ahora hay una referencia independiente —la geometría—
y dice que **el candidato es el que aproxima bien la superficie y la referencia
de Amber es la que aproxima mal**. En este caso concreto, la implementación de
referencia es la aproximación, no el patrón.

**No cambia** el estado del protocolo. Sigue `EXPERIMENTAL_NOT_ENABLED` y el
guardián `test_produccion_no_copia_el_respaldo_de_carbono_para_el_cloro` sigue
impidiendo que la paridad con Amber se consiga copiando el respaldo. Adoptar el
respaldo daría 24/24 y sería elegir el parámetro por el resultado de la
comparación.

**No demuestra**, y conviene decirlo entero:

- Un cloro, en una geometría. **F, Br e I siguen sin medir**, y la ampliación a
  ~50 ligandos con halógenos, azufre, estados de carga y tautómeros sigue
  pendiente: el cuello es curar el conjunto y generar los prmtop, que pide
  AmberTools, no calcular.
- La SASA numérica es una referencia **geométrica**, no experimental. Que LCPO
  reproduzca el área no dice que el área sea el término no polar correcto, ni
  que estos radios predigan afinidades.
- Las comparaciones siguen siendo de energía potencial entre dos
  implementaciones. Nada de esto es ΔG experimental.

## F, Cl, Br e I en 55 ligandos cristalográficos (2026-09-23)

La ampliación que la sección anterior dejaba pendiente, hecha con curación
automática y en el servidor (contenedor `moldesign-science`, AmberTools y
pysander, 3 procesos, límite de 6 GB). Mismo método y mismas funciones que la
adjudicación del cloro; lo único nuevo es el universo.

**Curación, declarada antes de medir** (commit `7b81bc9`): ligandos de PDBBind
que RDKit lee, sólo H/C/N/O/S/P/F/Cl/Br/I, 8-35 átomos pesados, |carga| ≤ 1,
un ligando por diana, estratos arilo/alifático; 12 por halógeno más los 7
fluorados de galectina-3. 55 de 763 candidatos. Tipos GAFF2 y radios mbondi3;
cargas Gasteiger, porque el área no depende de ellas. 55/55 parametrizados.

### Qué hace Amber con cada halógeno, medido con sander

Se sustituyeron los parámetros LCPO del halógeno por cada entrada de la tabla
hasta reproducir el término de superficie de sander, como en la atribución del
cloro. Una sola entrada coincide en cada ligando (residuo ~1e-8 kcal/mol; la
segunda, a 1e-2 o más):

| halógeno | ligandos | entrada que usa Amber |
|---|---:|---|
| F | 18 | `F` (la misma que OpenMM) |
| Cl | 11 | `C_sp2_2` (control positivo: reproduce la atribución del 17/09) |
| Br | 10 | `C_sp2_2` |
| I | 12 | `C_sp2_2` |

sander lo dice él mismo en su salida —`Using carbon SA parms for atom type BR`—
pero no dice cuáles; ahora está medido.

### Cuánto se equivoca cada uno frente a la SASA exacta

Error de fondo, 784 átomos pesados no halógenos de los mismos ligandos:
mediana |error| 2.81 Å², p90 7.25 Å². Incertidumbre de malla por átomo de
halógeno: mediana 0.012 Å², máximo 0.064 Å². LCPO propio contra OpenMM:
desvío máximo 9e-13 Å².

| halógeno (átomos) | parametrización | mediana \|error\| Å² | p90 | lectura |
|---|---|---:|---:|---|
| F (41) | `F`, Amber y OpenMM | 1.82 | 5.29 | dentro del fondo |
| Cl (18) | publicado, Weiser 1999 (el candidato) | 1.84 | 3.79 | dentro del fondo |
| Cl (18) | respaldo de Amber `C_sp2_2` | 25.86 | 28.68 | **fuera** |
| Br (19) | respaldo de Amber `C_sp2_2` | 24.64 | 30.68 | **fuera** |
| Br (19) | diagnóstico: coeficientes del Cl publicado | 3.33 | 6.74 | dentro del fondo |
| I (16) | respaldo de Amber `C_sp2_2` | 28.80 | 31.65 | **fuera** |
| I (16) | diagnóstico: coeficientes del Cl publicado | 1.87 | 4.31 | dentro del fondo |

El diagnóstico `C_sp3_1` (mismo radio 1.7 que el respaldo, pero carbono
terminal) da 8-12 Å²: como con el cloro, la mayor parte del error del respaldo
es la **clase de conectividad**, no el radio.

### Lectura

1. **F: resuelto.** La entrada que Amber y OpenMM comparten, que el artículo de
   LCPO nunca publicó, aproxima la superficie tan bien como un átomo bien
   parametrizado.
2. **Cl: la adjudicación del 19/09 se sostiene** sobre 18 átomos en geometrías
   reales: el candidato acierta y la referencia de Amber no.
3. **Br e I: la referencia de Amber está mal, y el candidato no existe.** El
   OpenMM 8.5.2 que viaja con el producto no tiene parámetros LCPO para Br ni
   I y lanza excepción: el MM-GBSA candidato hoy no puede puntuar un ligando
   bromado o yodado. Que los coeficientes del cloro caigan dentro del fondo con
   radio 1.8 **no** autoriza a usarlos: dice que la forma funcional de un
   halógeno terminal sirve, no qué radio es el físico para Br (≈1.85) o I
   (≈1.98). Eso es una decisión de dominio.

**Qué cambia en la puerta 1.** La parte de referencia queda contestada para los
cuatro halógenos: para Cl, Br e I, la implementación de referencia es la que
aproxima mal. Lo que queda abierto es una decisión: para Br e I, o se mantiene
la abstención (rechazar el ligando con un mensaje que nombre la causa) o se
define y valida una parametrización propia. **No se ha cambiado nada de
producción**: el protocolo sigue `EXPERIMENTAL_NOT_ENABLED` y el guardián que
impide copiar el respaldo sigue en pie.

**No demuestra:** lo mismo que la sección anterior —la SASA numérica es una
referencia geométrica, no experimental— y además que 12 ligandos por halógeno
cubren su química: los yodados incluyen tres análogos (`6g34`, `6g39`, `6g3a`),
porque las entradas de PDBBind sin proteína no tienen grupo de diana.

Una primera medida falló en 51 de 55 ligandos por un defecto del script, no de
la química (pysander con NumPy 2 exige un array, no una lista); se conserva
como `resultado_INVALIDO_numpy2_lista.json`.

Código: [`lcpo_halogenos.py`](lcpo_halogenos.py); datos:
[`halogenos_lcpo/`](halogenos_lcpo/) (selección, parametrización, resultado y
registros). Las topologías y coordenadas derivadas de PDBBind quedaron en el
servidor, fuera del repositorio.
