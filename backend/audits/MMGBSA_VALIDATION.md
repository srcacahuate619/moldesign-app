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
