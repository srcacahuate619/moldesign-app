---
titulo: "El catálogo estaba casi cinco veces peor de lo que suponíamos"
entradilla: "Auditar los 387 objetivos encontró 57 con la caja de búsqueda desalineada, no los 12 que asumía el plan. En 23 de ellos la caja no contiene ni un solo átomo del sitio real."
---

Antes de este experimento, el plan del programa daba por hecho que había "unos 12 grids
problemáticos" en el catálogo de objetivos. Era una cifra heredada, nunca medida: alguien
la estimó en algún momento y se citó desde entonces.

Auditar 387 objetivos no es investigación, es higiene. Pero la higiene sin medir es fe.

## Lo que se auditó, y con qué cuidado

Un grid es la caja donde el docking busca. Si está mal colocada, **todo** lo que se
calcule sobre ese objetivo es inválido, y lo será silenciosamente: el programa devuelve
poses con puntuaciones de aspecto normal.

El problema metodológico es que sólo la mitad de los objetivos permite comprobarlo
directamente. Los **HOLO** tienen un ligando nativo en la estructura que sirve de verdad
de referencia. Los **APO** no tienen ninguno, y ahí la auditoría depende de señales
indirectas y es más débil. Se separaron los dos estratos desde el diseño, en vez de
mezclarlos y reportar un número único que habría sido más limpio y menos honesto.

Los cinco criterios del instrumento se declararon antes:

| Gate | Qué exige | Resultado |
|---|---|---|
| G1 | Cobertura de los 387, sin omisiones silenciosas | 387/387 |
| G2 | Clasificación HOLO/APO determinista | Determinista en todos |
| G3 | Toda excepción con código y valor disparador | E1–E7, con su número |
| G4 | Determinismo bit a bit entre corridas | Idéntico en tres, incluida una tras reconstruir el directorio |
| G5 | Cero escrituras en catálogo, base de datos o producción | SHA-256 intacto |

Ese G4 es el que más importa: la auditoría se repitió tras borrar y reconstruir su
directorio de trabajo, y salió byte-idéntica. Sin eso, una auditoría es una opinión con
tablas.

## Qué pasó

**57 de 387 objetivos con excepción — el 14.7%.** Aproximadamente **4.75 veces** lo que
asumía el plan.

Y el detalle es peor que el agregado:

- **25 objetivos** con el grid a más de 15 Å del ligando nativo;
- **23 objetivos** con contención de ligando **0.00** — la caja no contiene ni un solo
  átomo del sitio de unión real.

## Lo que este GO significa, y lo que no

Conviene ser preciso, porque es fácil leerlo al revés:

> El GO dice que **la auditoría es válida y reproducible**. No dice que el catálogo esté
> sano. Dice lo contrario.

## El hallazgo negativo que se declaró en vez de taparse

El caso testigo de todo esto —el objetivo `5TUN`, que llevaba documentado como grid roto
desde hacía tiempo— **no fue capturado por la auditoría**.

Su contención de hotspots dio 0.800, exactamente en la frontera del umbral, y su verdad
de referencia es débil por ser APO. Y sin embargo tiene un hotspot a 5.147 Å fuera de la
caja.

Aquí había una tentación evidente: mover un poco el umbral para que `5TUN` entrara. El
prerregistro lo prohibía, y el umbral **no se tocó**. La corrección pasó a un experimento
propio, con un código de excepción nuevo para hotspots fuera de caja.

El coste de esa disciplina se puede cuantificar, y es alto: ese criterio nuevo capturaría
**52 objetivos hoy invisibles**. El recuento pasaría de 57 a 109 — del 14.7% al **28.2%**.

Es decir: sabemos que la cifra de este experimento es una subestimación, y la publicamos
igual, porque ajustar el umbral después de ver qué caso queríamos capturar habría
convertido la auditoría en una profecía.

## Alcance

Sin docking, sin red, y cero escrituras fuera del directorio del experimento.
