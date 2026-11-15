# Respuesta al seguimiento de la réplica

15 de noviembre de 2026. Autor: Claude, la sesión de implementación. Responde a
[SEGUIMIENTO-REPLICA-2026-11-15.md](investigacion-1.0.4/SEGUIMIENTO-REPLICA-2026-11-15.md). Vive fuera de
`investigacion-1.0.4/` porque su `manifiesto.py --comprobar` hashea todos los ficheros de esa carpeta: un archivo nuevo
dentro lo rompería, y la carpeta queda como la dejó el investigador.

## D-01: el contraejemplo es correcto y está arreglado

Reproduje el contraejemplo: cambiar en memoria la primera fila de `_ma_qa_metric_local` de 91,387 a 51 dejaba la fuente
`chai1` con `lectura: calfa`, y Preparación seguía diciendo que el valor era el del Cα. El rótulo afirmaba algo del
archivo que sólo estaba comprobado para Chai-1 0.6.1.

Arreglo, en el commit siguiente a este archivo:

- `prediccion._plddt_modelcif` calcula `local_es_el_calfa`, que dice si en el propio archivo el valor local de cada
  residuo es el factor B de su Cα (a 0,01 o menos).
- `lectura: calfa` y la referencia del acta se ponen sólo si hay firma **y** el archivo lo cumple. Con la firma sola, la
  fuente sigue siendo `chai1`, porque eso es lo que el archivo declara de sí mismo. La lectura queda sin rótulo y
  Preparación usa la frase genérica «convención de esta fuente sin verificar».
- La frase del Cα ahora dice lo que se comprobó en ese archivo: «en este archivo coincide con el factor B del Cα de cada
  residuo, que no es la media del residuo que da el modelo (así lo escribe Chai-1 0.6.1; el archivo no declara su
  versión)». Tiene su inglés.
- Prueba nueva con el mismo contraejemplo: `test_con_la_firma_pero_un_valor_que_no_es_el_calfa_no_se_dice_que_es_el_calfa`.
  Con el arreglo, `comprobar_seguimiento_replica.py --producto` da `lectura: null` para el archivo modificado.
- No cambia lo que se lee ni el estado: la regla del 70 sigue usando el valor local.

## En qué me equivoqué yo

- **Punto 6, el README.** Lo leí antes de su versión de las 09:46, que ya recogía los 21 complejos de aguas, las 243
  corridas de 8HFI, las 44 filas y los 14 experimentos. La réplica comparó las fichas con un README que ya no era el
  vigente.
- **Punto 7, `__pycache__`.** Está ignorado por Git (`git status --ignored` lo da como `!!`), así que no había riesgo de
  commitearlo. Lo de los SMARTS de `PROTOCOLO.md` tampoco era un problema: `check_docs_links.py --check` pasa.

## Lo demás

- **D-09.** Acepto la procedencia: cuatro sesiones de `gpt-6.1-sol`, sin cegamiento verificable ni diversidad de modelo.
  D-09.md ya lo dice en la sección del panel completo. En la sección del piloto quedan «Los dos revisores coincidieron» y
  «La verificación independiente regeneró…»: convendría alinearlas, o aclarar que la segunda frase se refiere a la
  geometría.
- **D-08.** La recomendación corregida, una nota de cobertura para los aniones del piloto, cuesta un texto y su prueba.
  La puedo implementar si el propietario lo pide.
- **D-03, D-04, D-05 y D-06.** Las correcciones cuadran con lo que medí. Las medianas de 8HFI sólo con padres (35,9, 53,7,
  54,4 y 72,7 s) son las que obtuve yo.
- **Commits.** La carpeta entró en `af756a97`, con `.gitattributes` marcándola `-text` para que un checkout no cambie los
  bytes que hashea el manifiesto. Los sellos DEC-104 entraron en `d6ff43c9`.
