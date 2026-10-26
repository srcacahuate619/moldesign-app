---
titulo: "8HFI reproduce la pose; el orden de su serie no supera el protocolo"
entradilla: "El primer intento de verificar un receptor del catálogo: el transportador de noradrenalina reproduce la desipramina del cristal en 3 de 5 semillas, pero no se demostró que Vina ordene las 57 moléculas del panel mejor que el azar (ρ = 0,13; IC 95 % de −0,16 a 0,41). 8HFI sigue en Demostración, con el resultado publicado en la aplicación."
---

Ninguno de los 381 receptores del catálogo tenía una calibración medida frente a
datos experimentales. Para 1.0.2 se buscaba un primer receptor «verificado», y
8HFI (el transportador de noradrenalina humano, con desipramina en el sitio) era
el candidato con el panel más completo: CHEMBL853189, 57 compuestos padre con Ki
medido en un mismo ensayo.

La hipótesis, fijada antes de acoplar nada, tenía dos partes. Con la receta de
receptor que publica el producto (la 7) y la configuración por defecto de un caso
(exhaustividad 8, 9 poses, semilla 42):

1. **Pose:** el top-1 reproduce la desipramina del cristal (RMSD ≤ 2 Å, sin
   alinear) en al menos 3 de 5 semillas, y es físicamente válido en PoseBusters.
2. **Calibración:** el top-1 de Vina ordena el panel con una ρ de Spearman cuyo
   IC 95 % bootstrap tiene el límite inferior por encima de 0.

## Qué se midió

Todo pasó por la API del producto, no por un script aparte: la misma preparación,
la misma especie química y los mismos parámetros que obtendría un usuario. Los
microestados (conectividad y carga de cada padre) se congelaron antes de acoplar y
no hubo ninguna desviación del protocolo. El panel no asigna la configuración del
nitrógeno de la amina terciaria protonada, así que las coordenadas acopladas fijan
una que el panel no declara. Hubo un solo receptor preparado (un único SHA-256) y
cero fallos en las 57 moléculas.

## Qué salió

**NO_GO.** La pose pasa, justo en el límite. La calibración, no.

| | Resultado | Exigido |
|---|---|---|
| Semillas con RMSD ≤ 2 Å | 3 de 5 (0,52; 0,56; 0,64 Å) | ≥ 3 |
| Semillas que fallan | 3,68 y 4,12 Å | — |
| Top-1 válidos en PoseBusters, con la reconstrucción de hidrógenos de MF-33-H-COR | 5 de 5 | todos |
| ρ de Spearman (−E de Vina frente a pKi) | 0,13 | — |
| IC 95 % bootstrap (10 000 remuestreos) | [−0,16; 0,41] | límite inferior > 0 |
| IC 95 % de Fisher | [−0,14; 0,38] | — |

Con este receptor y esta configuración, **no se demostró** que el orden que da Vina
en esta serie sea mejor que el azar: el IC cruza el cero. Eso no demuestra que no
haya asociación. Con n = 57, una ρ verdadera de 0,3 sólo se detectaría alrededor del
62 % de las veces. El panel cubre unas 2,9 unidades de pKi (de 5,97 a 8,85), y las
fuentes no permiten aislar por qué la ρ observada es baja: ruido del ensayo, falta de
potencia o la propia función de puntuación.

La validez en PoseBusters se midió con el protocolo de reconstrucción de hidrógenos de
MF-33-H-COR, el mismo que usa el producto: los hidrógenos se regeneran desde la geometría
acoplada. Sin esa condición la cifra no es comparable; con las mismas poses y otra
reconstrucción de hidrógenos, MF-33-H-COR midió 2,64 % de poses válidas donde con esta
mide 99,48 %. No es la neutralización que se usa para el RMSD (ver «Dos condiciones
declaradas»).

## Qué no dice

- **No dice que Vina no sepa acoplar en NET.** La pose del cristal se reproduce
  con precisión cuando sale (0,5–0,6 Å). Lo que falla es el orden entre análogos.
- **No vale para ligandos de estructura diversa.** El panel es casi entero una
  serie: 53 de los 57 comparten el mismo andamio de Murcko. La ρ describe cómo
  ordena compuestos de esa serie.
- **No es una afirmación sobre el ensayo.** Es un ensayo de desplazamiento de
  [3H]nisoxetina en NET (descripción de ChEMBL archivada en la entrada del
  experimento). El pH, la temperatura y la concentración del radioligando no constan
  en las fuentes consultadas, y la correlación es dentro de un único ensayo.

## Dos condiciones declaradas

- **Sin iones.** La preparación del producto retira el cloruro del depósito. Vina
  no tiene término electrostático y su corte es de 8 Å: el top-1 más cercano
  queda a 7,9 Å de donde estaba el cloruro, y sólo uno de los 57 top-1 queda a
  menos de 8 Å. La estructura no modela sodio.
- **Dos correcciones técnicas del análisis**, hechas y declaradas antes de calcular
  ninguna cifra: neutralizar después de quitar los hidrógenos explícitos (con ellos,
  la amina protonada no casaba con el ligando neutro del cristal) y excluir los
  pseudoátomos con que Meeko abre el anillo de siete de la desipramina al contrastar
  el SDF con el PDBQT.

## Lo que apareció por el camino

El producto acoplaba los 57 padres con carga +2, con las dos aminas protonadas,
también cuando una de ellas lleva un grupo atractor cerca del nitrógeno y su pKa
real queda cerca o por debajo de 7,4. No decide este resultado (no hay forma de saber si otra especie
ordenaría mejor sin medirlo), pero era un defecto de química: desde 1.0.2, la
«Especie acoplada» de esas aminas pide revisión, con su motivo.

## Consecuencia

8HFI sigue en **Demostración**, y la sección «Verificados» sale vacía en 1.0.2.
El intento se publica igualmente: el selector de receptores y los resultados con
8HFI muestran estas cifras, sus condiciones y este experimento. Un receptor sólo
entra en Verificados si supera el protocolo; publicar también los intentos que no
lo superan es lo que da sentido a esa sección.

## Correcciones

**2026-10-20**, a raíz de la auditoría científica del producto (SCI-A-017, 018, 044,
045 y 052). La versión anterior de este texto decía que el orden de Vina «no se
distingue del azar» y que «el rango de afinidades no es el problema», como si eso
estuviera demostrado. También daba el radioligando por desconocido, aunque figura en
la entrada archivada, y publicaba el 5 de 5 de PoseBusters sin su protocolo de
hidrógenos. Ninguna cifra cambia: no se repitió ningún cálculo ni se tocó el
experimento sellado.
