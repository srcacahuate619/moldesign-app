# Evaluación con receptores propios (caminos B y C): medido el 2026-10-11

P01 de FEP-09 era Preparación dando por hecha la receta del catálogo. La misma suposición
vivía en la pestaña Evaluación. Se midió con Vina real por la API, en una cápsula de QA
(agente 6, Vina con 4 núcleos, exhaustividad 8, 9 poses, semilla 42, pH 7,4), sobre dos
dianas del benchmark de OpenFF (commit `fd88824f`):

- **cdk2**, con el agua puente HOH A:2117 y el cierre ACE A:-1;
- **pde2**, con Zn D:1001 y Mg D:1923 junto al sitio.

Cada una pasó por el camino A (estructura cruda), B (`respetar`) y C (el PDBQT que dio el
camino B, con y sin la estructura de origen). Producto antes: `f0e64086`; después: el
commit de este documento.

## Antes

| Qué | A | B | C con origen | C sin origen |
|---|---|---|---|---|
| Aviso de aguas | «se retiraron 1/3 aguas» (cierto) | «se retiraron 1/3 aguas» con el receptor conservándolas (falso) | igual que B (falso) | «se retiraron las aguas… no se pudo leer la estructura depositada» con el PDBQT trayéndolas (falso) |
| Supuesto del dossier y la certificación | «se eliminaron todas las aguas» (cierto) | igual (falso) | igual (falso) | igual (falso) |
| Interacciones | ProLIF | análisis por distancias, sin química | por distancias | por distancias |
| Receptor y complejo (`/evaluation/files/…`) | 200 | 200 | 200 | **404**: «Descargar complejo» fallaba |

Las interacciones de las corridas B y C caían al análisis de respaldo por dos causas que el
catálogo nunca enseña, porque su receta retira metales y cierres:

1. `interactions._pdbqt_receptor_a_pdb` tomaba la primera letra de cualquier tipo
   AutoDock que no fuera de proteína: Zn → «Z», Mg → «M», y el calcio habría sido
   carbono. RDKit rechazaba el receptor de pde2.
2. ProLIF guarda el número de residuo como entero sin signo (`ResidueGroup`, uint32): el
   ACE A:-1 de cdk2 lanzaba `OverflowError`.

Con el respaldo, cdk2 B daba 38 «interacciones» (33 hidrófobas por distancia); con ProLIF
son 4 puentes de hidrógeno (Glu81, Leu83 y el agua HOH 2117).

## Después

| Qué | A | B | C con origen | C sin origen |
|---|---|---|---|---|
| Aviso de aguas | sin cambios, byte a byte | `AGUAS_DEL_SITIO_CONSERVADAS`: «conserva las 1/3 aguas que su estructura de origen tiene dentro de la caja» | igual que B | «conserva 1/3 aguas… sin la estructura de origen no se sabe si se retiró alguna» |
| Supuesto | sin cambios | «Las aguas del receptor son las del archivo que se subió…» | igual | igual |
| Interacciones | ProLIF (sin cambios) | ProLIF: cdk2 4 puentes de H; pde2 1 puente y 1 hidrófoba | igual que B | igual que B |
| Receptor y complejo | 200 | 200 | 200 | 200, con la copia en PDB del PDBQT que guarda la subida |

Preparación no cambia: `entorno.referencia` REGISTRADO en A, B y C con origen (el camino C
se verifica aquí por primera vez con Vina real) y NO_EVALUADO en C sin origen, que es lo
correcto.

## Lo que no cubre

- **La coordinación con metales no aparece en las interacciones.** La huella de ProLIF que
  usa el producto no incluye `MetalDonor`/`MetalAcceptor`, así que un ligando que coordina
  el Zn no lo enseña como interacción. Antes tampoco: el receptor ni se leía.
- **Batch**, por lectura del código y sin medir: usa los bytes congelados del receptor, así
  que el aviso de aguas mide esos bytes y queda bien; pero su corrida no registra el modo de
  preparación, y el supuesto del dossier de cohorte conserva la frase de la receta del
  catálogo aunque el receptor sea propio.
- No se probó la interfaz (WebView2) ni el instalador: la verificación es por la API.

Pruebas: `backend/tests/test_evaluacion_caminos_propios.py` (17). Cada arreglo se deshizo
por separado y su prueba falló: aviso de aguas 4, supuesto 6, archivos del visor 2,
elementos de los metales 1, numeración negativa 1.
