# Evaluación: visores sin GPU, coste en reposo y a dónde va el tiempo de una corrida (medido el 2026-11-09)

Pregunta del propietario: la pestaña Evaluación es la que más riesgo tiene de fallar, ¿tarda demasiado en evaluar o en
cargar los visores?, ¿y qué pasa con Mol* cuando el equipo no tiene con qué dibujar en 3D, como en una máquina virtual?

Todo se midió en el **export estático** servido por una cápsula de QA (agente 4, backend real con `python-embed`, Vina real
con 4 núcleos, exhaustividad 8, 9 poses, semilla 42, receptor 8HFI), con Edge 157.0.4341.42 —el mismo Chromium que el
WebView2 instalado en esta máquina— en modo sin ventana, 1440×900. Máquina: Ryzen 5 5500 (6 núcleos, 12 hilos), GTX 1660
SUPER. Producto antes: `600c5642`; después: el commit de este documento. Los guiones son
`frontend/scripts/medir-evaluacion.mjs` y `frontend/scripts/verificar-visores.mjs`.

**Lo que esto no es.** Es Edge, no la ventana de Tauri, y `--disable-gpu` aproxima un equipo sin GPU: no se midió en una
máquina virtual ni con el instalador. El procesador es el de los procesos del navegador, en % de **un** núcleo.

## 1. Qué da el equipo según cómo arranca el motor

| Arranque | WebGL 2 | Quién dibuja | Lienzo 2D |
|---|---|---|---|
| con GPU | sí | ANGLE (NVIDIA … D3D11) | sí |
| `--disable-gpu` | sí | SwiftShader (procesador) | sí |
| `--disable-gpu --enable-unsafe-swiftshader` (lo que añade la aplicación) | sí | SwiftShader | sí |
| `--disable-gpu --disable-software-rasterizer` | **no** | — | sí |
| lo anterior más la bandera de la aplicación | **no** | — | sí |

- En Edge 157, sin GPU sigue habiendo WebGL por software aunque no se pase la bandera: hoy la bandera de
  `permitir_webgl_por_software` no cambia el resultado. Se deja, porque Chromium anunció que retirará ese repliegue.
- Sin rasterizador por software no hay WebGL de ninguna manera y la bandera no lo arregla. Es el estado en que queda
  Chromium cuando el proceso de GPU se cae varias veces o una política lo veta. **El lienzo 2D existe en todos los casos.**

## 2. Lo que veía el usuario, y lo que ve ahora

| Situación | Antes | Ahora |
|---|---|---|
| Sin ningún WebGL | Un recuadro negro con un aviso; no se podía mirar la pose | **Vista simplificada** en lienzo 2D: pose, residuos a 4,5 Å o menos y esqueleto; se gira y se acerca |
| La sonda consigue contexto y Mol* no | El mensaje crudo de Mol* en inglés («WebGL does not seem to be available…») sobre un recuadro blanco, y una excepción sin capturar | Se abre el visor ligero; si tampoco puede, la vista simplificada |
| Mol* no arranca | Aviso que mandaba «al botón del visor», tapado por el propio aviso | Se abre el visor ligero y se dice por qué |
| El equipo retira el contexto con el visor abierto | Lienzo en negro, sin mensaje | Se esperan 4 s a que vuelva; si no, visor ligero → vista simplificada, con «Reintentar 3D» |
| three.js no consigue contexto | Lienzo vacío sin mensaje (R3F crea el renderizador en una promesa y el fallo no llega a ninguna frontera) | Vista simplificada; el resto de la pestaña sigue en pie |

El segundo caso se reprodujo en el export negando el contexto a quien lo pide con `powerPreference` (Mol* y three) y
dándoselo a la sonda, que lo pide sin atributos. La guarda anterior miraba el texto del contenedor una sola vez, al
resolver `Viewer.create`; Mol* pinta su mensaje un render después. Ahora se mira `plugin.canvas3d`, que sí está decidido
en ese momento.

`node scripts/verificar-visores.mjs todos` repite los cinco casos y termina con código 1 si alguno no acaba en un visor
que dibuja (24 comprobaciones, todas en verde sobre el export del 2026-11-09 20:18).

El giro se comprueba sobre los píxeles del lienzo, no sobre una captura. La primera versión del guion arrastraba desde
el centro de la caja del lienzo, que con la página desplazada quedaba bajo la cabecera fija del caso: el arrastre
seleccionaba texto, la captura cambiaba por el resaltado y el guion daba el giro por bueno sin que el lienzo recibiera
nada. Ahora pregunta al navegador qué hay en el punto antes de arrastrar y lleva un control (arrastrar fuera del lienzo
no cambia el dibujo). Medido así: arrastrar sobre el lienzo 2D lo gira, recoge la explicación y no selecciona texto; en
Web3D el mismo gesto produce 336 llamadas de dibujo y, pasada la inercia, 0 en 3 s.

## 3. Procesador en reposo, con el visor abierto y sin tocar nada (10 s)

| Visor | Equipo | Antes | Ahora |
|---|---|---|---|
| Mol* | con GPU | 4,2 % (página 3,0 + GPU 1,2) | sin cambio |
| Mol* | sin GPU | 3,5 % (2,8 + 0,7) | sin cambio |
| Web3D | con GPU | **45–48 %** (página 32–33 + GPU 14) | **4,7 %** (4,6 + 0,1) |
| Web3D | sin GPU | **950–1160 %**: entre 9 y 11 núcleos enteros (GPU 915–1127 + página 32–37) | **4,6 %** (4,6 + 0) |

Web3D repintaba 60 veces por segundo una escena quieta, porque informaba la cámara desde el bucle de dibujo. El
rasterizador por software usa todos los núcleos que hay, que son los que necesita Vina. Ahora dibuja a demanda y, pasada
la inercia del último gesto, hace 0 llamadas de dibujo en 3 s.

## 4. La pantalla «evaluando» (12 s con una corrida de Vina en marcha)

| Equipo | Animaciones | Procesador |
|---|---|---|
| sin GPU | fluidas, 60 fotogramas por segundo (antes) | 56,6 % (GPU 40,9 + página 15,5) |
| sin GPU | por pasos, `steps(8)` (ensayo) | 23,0 % |
| sin GPU | ninguna (ensayo) | 15,1 % |
| sin GPU | **por pasos, `steps(12)` (ahora, automático)** | **27,0 %** (GPU 11,8 + página 14,9) |
| con GPU | fluidas (sin cambio) | 38,0–38,6 % |

Sin tarjeta gráfica cada fotograma lo compone el procesador. `lib/webgl.ts` deja dicho en `<html data-dibujo>` cómo
dibuja el equipo y `globals.css` da entonces las animaciones por pasos. Con tarjeta gráfica no se toca nada: la decisión
del 2026-10-10 sobre el orbe sigue vigente.

## 5. Carga de la pestaña y memoria

| Qué | Con GPU | Sin GPU | Sin WebGL |
|---|---|---|---|
| Pestaña lista (botón «Crear un caso») | 0,32–0,39 s | 0,32–0,42 s | 0,33 s |
| Editor 2D listo tras crear el caso | 0,7–1,1 s | 0,8–1,2 s | 0,9 s |
| Visor con el receptor tras elegirlo | 1,1–1,8 s | 1,2–1,7 s | no medido |
| JavaScript cargado (descomprimido) | 37,1 MB | 37,1 MB | 32,4 MB (no se carga Mol*) |
| Memoria privada de la página, con Mol* y el editor | 540–580 MB | 570–620 MB | no medido |
| La misma, con un resultado abierto | 590–690 MB | 590–680 MB | no medido |

Son de cuatro pasadas con GPU, tres sin GPU y una sin WebGL, en una máquina rápida con disco local: valen como orden de
magnitud, no como lo que tardará un equipo modesto.

- Los trozos mayores: uno de 20,2 MB, otro de 3,6 MB y `molstar.js` de 4,65 MB. No se identificó qué contiene cada
  trozo de Next.
- Alternar entre Mol* y Web3D 24 veces (48 visores creados): la página pasó de 538 a 798 MB con altibajos (736, 688, 815,
  798) y Mol* seguía dibujando. No crece de forma monótona en esa prueba; no se midió más allá.
- El backend, con torch y los modelos cargados tras una docena de evaluaciones: 1 592 MB privados.
- `GET /targets/` (381 receptores) tardó 3,4 s en frío y 0,7 s en caliente; se pide en cada carga de la pestaña.

## 6. A dónde va el tiempo de una evaluación (8HFI, un ligando de 20 átomos pesados)

| Tramo | Primera corrida tras arrancar | Corrida siguiente, otra molécula | Misma molécula otra vez |
|---|---|---|---|
| Total visto por el usuario | 65,2 s | 30,8–33,6 s | 8,6–8,8 s |
| Preparar el receptor (Meeko) | 6,8 s | en caché | en caché |
| Vina | 19,5 s | 17,5 s | en caché (0,2 s) |
| XGBoost | 5,7 s (carga de modelos) | 0,14 s | 0,07 s |
| CL-GNN | 18,0 s (carga de torch) | 0,03 s | 0,01 s |
| **Después de la última etapa** | 8,6 s | **8,3–9,5 s** | **7,5–7,7 s** |

Una pasada por columna, salvo la del medio y la última (dos cada una).

- Lo que ocurre después de la última etapa es sobre todo la validación física de las poses: un proceso hijo de Python
  por evaluación que vivió 7,8 s (medido por su tiempo de vida). No emite ningún evento, así que la línea de etapas
  enseña todo terminado mientras faltan unos 8 s. En una corrida ya acoplada es casi todo el tiempo.
- Importar el módulo del hijo cuesta 0,9 s; el resto es trabajo de la validación. **No se midió** cuánto de ese trabajo
  es arranque de PoseBusters y cuánto es cálculo, ni se cambió nada: toca el camino sellado de la evidencia estructural.
- La etapa de acoplamiento tardó 21,0 s en la pasada sin GPU y 20,1 s en la de con GPU, pero eran moléculas distintas:
  no es una comparación. En esta máquina, además, sobran núcleos (Vina usa 4 de 12). **No se midió** cuánto frena a Vina
  el navegador en un equipo de 2 a 4 núcleos; lo medido es cuánto procesador pide el navegador (secciones 3 y 4).

## Sin verificar

- La ventana de Tauri y el instalador: los cambios están probados en el export con Edge, no en el binario.
- Una máquina virtual real sin GPU virtualizada.
- Los demás visores de la aplicación (Moldex, comparador de poses, levantamiento a 3D): sólo se tocó la columna 3D de
  Evaluación. Siguen enseñando su aviso cuando no hay WebGL.
- La fluidez de Mol* al girar una escena grande por software: se midió el reposo, no el arrastre.
