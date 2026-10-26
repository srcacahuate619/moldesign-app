# ABS-TR-01, validez de la decisión de Preparación — registro previo

Escrito el 2026-10-22, **antes de generar ninguna salida del producto sobre estos 29 sistemas.** Los veredictos de
los revisores ya se conocen (están en `D:\moldesign-audits\ABS_TR_01\analisis\RESULTADOS_PRELIMINARES_CIERRE.md`);
lo que no se conoce es lo que dirá Preparación. Hubo una auditoría del catálogo entero con Preparación el
2026-10-08, con otro producto; no se consultó para escribir esto.

## Qué se pregunta

Si la pestaña Preparación, en el uso normal de un receptor del catálogo, toma sobre los 29 sistemas reales de
ABS-TR-01 la misma decisión que un panel ciego de revisores: **detenerse**, **avisar y seguir** o **seguir**.
Es el endpoint de decisión del diseño de la Fase D (`abstencion_y_falso_bloqueo.md`): falso bloqueo, falsa
autorización y aviso, con su denominador.

## Sistemas

Los 29 «sistema» del mapa privado de la ronda 2 (`mapa_privado_r2.json`), que son los mismos depósitos de la
ronda 1 con otro identificador. Cada depósito del catálogo (`data/targets/{PDB}.pdb.gz`) se comprueba contra el
SHA-256 que registró el mapa. Ninguna exclusión.

## Lo que hace el producto (una corrida por sistema)

- Receptor del catálogo (sección Demostración), su cadena y su caja; ruta normal de la aplicación.
- Ligando: el del cristal (`site_ligand`), con el SMILES canónico de su definición en el CCD del wwPDB (OpenEye
  si existe), archivado con URL, fecha y SHA-256. Si el depósito trae el ligando incompleto, se acopla la molécula
  completa del CCD y se anota.
- Microestado del producto (pH 7,4), congelado en dos procesos; una corrida con otro microestado es deriva y
  detiene la campaña.
- Vina 1.2.7, configuración de un caso (exhaustividad 8, nueve poses, un conformador), semilla 42, 4 CPU.
- `POST /evaluation/preflight` → `submit` → `result` → `POST /evaluation/dossier/{id}/preparacion` con la
  proyección del caso (origen «catalog»). Por la API, en una cápsula con perfil y datos aislados (la de MET-01-R1).
- Un reintento técnico idéntico. Tope de 30 CPU-core-h.

**Decisión del producto:** DETENER si el preflight devuelve bloqueos técnicos o Preparación dice BLOQUEADO;
SEGUIR si Preparación dice REVISION sólo por revisiones rutinarias (o TRANSFERIBLE); AVISAR en el resto de
REVISION.

## La referencia

Cinco revisores: **Astra 6, Sol 6.1, GLM 5.3 y step5preview** (ronda 2, cuatro estados) y **Opus 5.5** con su
**ronda 1** (tres estados, sin REVISAR), por decisión del propietario (2026-10-22): Opus no entregó la ronda 2.

Un revisor **detiene** un sistema si su veredicto es NO_APTO (algún control CRITICO).

- **Primaria:** DETENER si lo detienen 3 o más de los 5; NO_DETENER si 2 o menos.
- **Sensibilidad 1, unánime:** DETENER si 5 de 5, NO_DETENER si 0 de 5; el resto, DISPUTADO (fuera del cálculo).
- **Sensibilidad 2, ronda 2 sin Opus:** DETENER si 3 o 4 de 4, NO_DETENER si 0 o 1; 2 de 4, DISPUTADO.

Límites de la referencia que se aceptan de antemano: son modelos de lenguaje, no expertos; Astra y Sol se
parecen mucho entre sí (92 % de celdas iguales); Opus juzgó con otra escala; nadie adjudicó los 29 con
información externa (artículos, informes de validación).

## Endpoints

- **Falso bloqueo** = producto DETENER en un sistema de referencia NO_DETENER. Denominador: los NO_DETENER.
- **Falsa autorización** = producto SEGUIR en un sistema de referencia DETENER. Denominador: los DETENER.
- **Aviso sin bloqueo** = producto AVISAR en un sistema de referencia DETENER (no es un error de autorización:
  el programa avisa y sigue; se informa aparte).
- Límites unilaterales al 95 % de Clopper-Pearson. Objetivo del diseño: falso bloqueo con límite superior ≤ 10 %.

## Decisión

- **NO_GO** si hay una falsa autorización en un sistema que detienen los cinco revisores, o si el límite
  inferior del falso bloqueo supera el 10 % (con la referencia primaria).
- **GO** si el límite superior del falso bloqueo es ≤ 10 % y no hay ninguna falsa autorización. **Con menos de
  29 negativos no es alcanzable aunque no haya errores** (0 de 18 da un límite superior del 15,3 %); se dice de
  antemano.
- **INCONCLUSIVE** en el resto, o si más de 3 sistemas quedan sin auditoría por fallos de infraestructura.

## Secundario (no decide)

- Por control: el estado de los requisitos de Preparación que miran lo mismo que cada control (tabla
  `CORRESPONDENCIA` del arnés) frente a la mayoría de los revisores. Preparación sólo registra la caja y las
  cadenas, y no compara el ligando del cristal con su definición: esos controles no tienen equivalente real.
- Los motivos de cada bloqueo y de cada aviso, para separar los errores por causa.

## Qué no dirá

Nada sobre la química de estos sistemas más allá del juicio de los revisores, nada sobre receptores propios del
usuario (caminos A, B y C) ni sobre otros 352 receptores del catálogo, y nada sobre la validez de las poses.
