# La fuga del cambio de caso, un Mol* para toda la sesión y una prueba de resistencia (2026-11-10)

Continúa `evaluacion-visores-y-rendimiento-2026-11-09.md`. Ese día, alternando dos casos en Evaluación (8HFI y 1RKP), la
página pasó de 675 a 1 567 MB en 24 cambios y, tras forzar la recogida de basura, se quedaba con unos 21 MB retenidos por
cambio (3,5 MB sin Mol*). El código llamaba a `viewer.dispose()`, así que algo retenía cada visor.

Todo se midió en el **export estático** servido por una cápsula de QA (agente 4, backend real con `python-embed`), con Edge
157 —el Chromium del WebView2 de esta máquina— sin ventana, a 1440×900, con GPU. Producto antes: `b2b5c09c`.

## 1. Qué retenía cada cambio de caso

No era `dispose()`. Una instantánea del montón tras seis cambios mostró **siete copias de la pantalla del caso** —editor,
paneles de configuración, el visor— desprendidas del documento y vivas. Un subárbol desprendido se conserva entero mientras
quede vivo uno de sus nodos, y cuatro cosas, todas de Ketcher 3.18.0, alcanzaban uno:

| # | Retenedor | Por qué no se suelta |
|---|---|---|
| 1 | `window.resize` (de `initResize`) y `document.mousemove`, `mouseup` y `mouseleave` (de `domEventSetup`) | Ketcher los registra con funciones anónimas y su limpieza no los retira: no guarda la referencia. |
| 2 | `RotationView.rotationCenterSubscribers` y `rotationHandleSubscribers` | Son conjuntos **estáticos**. La herramienta de selección de cada «editor central» (`CoreEditor`) se suscribe al crearse y sólo se da de baja cuando se cambia por otra herramienta, nunca al destruir el editor. |
| 3 | `settings:changed` del servicio de ajustes | El servicio es uno para toda la página; el constructor de cada `Ketcher` se suscribe y descarta la función para darse de baja. |
| 4 | Nuestros cierres | La caja del editor quedaba capturada en el cierre del efecto (el minificador mete `vigilarKetcher` dentro del efecto). |

Cada uno tapaba al siguiente: arreglado el 1, el guardián seguía viendo +1 221 nodos y +484 oyentes por cambio; con el 2,
+582 y +82; con el 3 y el 4, cero. Además, `Viewer.create` monta la interfaz de Mol* en una raíz de React propia que
`dispose()` no desmonta: quien conserve el elemento donde se montó conserva el plugin entero.

**Una trampa de método.** Las instantáneas de V8 enseñan las entradas de un `WeakMap` como retenedoras aunque la clave sólo
esté viva a través de su propio valor. Un recorrido que las sigue como aristas fuertes señala culpables falsos (el primer
diagnóstico de esta sesión culpaba a un `WeakMap` de campos privados de Ketcher). Una entrada sólo retiene su valor si la
clave se alcanza por otro camino.

## 2. Qué se cambió

- `frontend/lib/ketcherOyentes.ts`: vigila lo que registra cada editor mientras arranca y lo retira al desmontarlo. Cada
  oyente se reconoce por algo que sólo hace Ketcher (el `resize` que sigue al teclado en su raíz; la firma
  `isPolymerEditorTurnedOn`; los `settings:changed` que aparecen mientras arranca un solo editor). Con dos editores
  arrancando a la vez no se atribuye nada: retirar un oyente ajeno rompería a su dueño.
- `frontend/lib/molstarResidente.ts`: **un solo Mol\* para toda la sesión**. Se crea una vez en un elemento propio que no
  pertenece a ningún caso; se cuelga de quien lo pide y se descuelga al devolverlo. Para que un caso nunca vea la
  estructura de otro: al devolverlo se oculta y sale del documento en el acto, todo va por una cola (el vaciado del
  anterior termina antes de la carga del siguiente, y una carga que ya no es la vigente no añade nada) y no vuelve a verse
  hasta que Mol\* ha dibujado un fotograma vacío. Ketcher sigue remontándose con cada caso, a propósito: el dibujo y el
  historial de deshacer son del caso.

## 3. Medido después

Tras recoger la basura dos veces, cada dos cambios (pasada corta de `scripts/resistencia.mjs`, 12 cambios, sin
evaluaciones):

| Qué | Antes (`b2b5c09c`) | Después |
|---|---|---|
| Memoria privada retenida por cambio | ~21 MB | 0,01 MB |
| Nodos del DOM retenidos por cambio | (no medido) | 0 (3 341 constantes) |
| Oyentes de eventos retenidos por cambio | +4 globales de Ketcher | 0 (1 966 constantes) |
| Visores de Mol\* creados en 12 cambios | 12 | 0 (uno en toda la sesión) |
| Contextos WebGL creados en 12 cambios | 12 | 0 |

**Sin tocar, para decidir:** en reposo, con nada que dibujar (cero llamadas de dibujo medidas), el bucle
`requestAnimationFrame` de Mol\* cuesta 4–6 % de un núcleo de la página y 1,6 % de la GPU; con el bucle parado, 0,1 %. Es
el diseño de Mol\*, no una regresión, y pararlo cuando nadie toca el visor es posible pero toca cómo responde a la
interacción.

## 4. La prueba de resistencia

Los tres fallos graves de la interfaz (el sondeo a Ketcher que tumbó la VM a la hora, Web3D gastando 9–11 núcleos en reposo
y esta retención) fueron de comportamiento en el tiempo, y los encontró alguien midiendo a mano con todas las pruebas en
verde. `frontend/scripts/resistencia.mjs` lo mide: crea dos casos, evalúa tres ligandos, cambia de caso 30 veces, alterna
Mol\* y el visor ligero seis veces y deja la aplicación quieta 10 minutos (4 con Mol\* y un resultado, 3 con el visor
ligero, 3 en otra pestaña con Evaluación oculta). Termina con código 1 si algo se pasa del presupuesto.

**Conduce la ventana real.** WebView2 admite depuración remota: el guion lanza el binario con
`WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=…` y `MOLDESIGN_PERFIL_DE_PRUEBA` (una carpeta temporal:
datos, casos, logs y perfil de WebView2 fuera de los del usuario, sin instancia única), se conecta con Playwright y, al
terminar, cierra la ventana como un usuario para que Tauri apague su backend. Probado aquí con el binario de depuración
con el export incrustado (`cargo build --features tauri/custom-protocol`): la ventana de WebView2 con la interfaz de
producción, sin instalador. **No con el binario de release**, que no se construye hasta cerrar 1.0.4 (decisión del
propietario).

| Presupuesto | Valor | Por qué ese valor |
|---|---:|---|
| Nodos del DOM retenidos por cambio | ≤ 150 | Medido: 0. Un caso entero son miles: la fuga original eran ~1 200 sólo de Ketcher. |
| Oyentes retenidos por cambio | ≤ 1 | Medido: 0,01. Con la fuga: 4 globales y ~480 de elemento. |
| Montón de JavaScript retenido por cambio | ≤ 2 MB | Medido: 0,11–0,35. |
| Memoria privada retenida por cambio | ≤ 4 MB | Oscila ±25 MB entre muestras y el propio Playwright le suma ~1,4 (§6); la fuga original eran 21 y la del worker, 5–8. |
| Enviado a los workers por cambio | ≤ 1 MB | Medido: 0,02–0,04. Con la fuga del worker de Indigo: 5,2–6,6 (§6). Es determinista. |
| Visores de Mol\* creados al cambiar de caso | 0 | Antes, uno por cambio. |
| Procesador en reposo (página + GPU + navegador) | ≤ 12 % de un núcleo | Medido: 6,7–10,8 con Mol\*, 0,1–0,8 con el visor ligero. Web3D gastaba 950–1 160 sin GPU. |
| Crecimiento de la memoria en reposo | ≤ 3 MB/min | Entre los dos extremos del reposo, tras recoger la basura; sólo en reposos de 2 min o más. El sondeo a Ketcher: ~200. Sin recoger, la curva con Mol\* sube ~12 MB/min y cae de golpe: es basura de su bucle de dibujo. |

**La primera pasada larga sobre la ventana real** (binario de depuración con el export incrustado, GPU, 2026-11-10, antes
del arreglo del worker de §6): dentro del presupuesto de entonces, pero con la memoria creciendo 6,4 MB por cambio.

| Qué | Resultado |
|---|---|
| Tres evaluaciones (8HFI) | 45,3 s, 32,0 s y 29,9 s |
| 30 cambios de caso | nodos 4 625 y oyentes 2 250 constantes; montón +0,11 MB/cambio; un solo Mol\* |
| Memoria privada en los cambios | 707 → 948 MB: +6,4 MB/cambio (era el worker de Indigo, §6) |
| Seis veces Mol\* ↔ visor ligero | seis contextos WebGL nuevos (uno por visor ligero, que sí se crea y destruye) |
| Reposo con Mol\* y un resultado, 4 min | 6,7 % de un núcleo (página 4,9 + GPU 1,7); memoria −0,9 MB/min |
| Reposo con el visor ligero, 3 min | 0,1 %; memoria plana |
| Reposo en otra pestaña, 3 min | 0,4 %; la memoria de la página baja de 975 a 165 MB |

**El guardián demuestra que ve** (`--autotest`, restricción 2 del AGENTS.md): una pasada corta limpia pasa; la misma con
una fuga plantada (~16 MB por clic), 2 MB por clic enviados a un worker y un bucle que gasta media CPU en reposo falla por
los tres motivos (montón +15,6 MB/cambio; 1,93 MB/cambio al worker; procesador 57–65 %). Si los contadores de visores no llegan a la página, falla: «0 visores creados» sin
haberlos visto no vale (le pasó a la primera versión, que los inyectaba por CDP y no se aplicaban).

## 5. Lo que queda abierto

- **El bucle `requestAnimationFrame` de Mol\* gasta 4–6 % de un núcleo en reposo sin dibujar** (parado: 0,1 %). Es su
  diseño; pararlo cuando nadie toca el visor es posible.
- **El editor de macromoléculas de Ketcher** no es otra raíz de React: se pinta dentro de la nuestra. Lo que hay que
  soltar de él es su `CoreEditor`, y el vigía lo hace, también en desarrollo (§7). No se probó cambiar de caso con el
  modo de macromoléculas activo.
- **Los objetos de embind del worker de Indigo siguen sin liberarse.** En `indigoWorker.ts` de ketcher-standalone 3.18.0,
  `handle()` crea un `MapStringString` por mensaje y no lo libera, y Calculate y Clean hacen lo mismo con un `VectorInt`.
  Medido el 2026-11-11 llamando a indigo-ketcher 1.46.0 desde Node con 17 opciones como las de Ketcher (las 15 capturadas
  en la página, más el formato de entrada y el de salida): entre
  1,0 y 1,6 KB de memoria de WebAssembly por mensaje, y 0 con `.delete()` (no «unos cientos de bytes», como decía esta
  línea). Son unos 6 mensajes por cambio de caso: ~8 KB. Sigue igual en `master` y en `v3.21.0-rc.2` de epam/ketcher, y no
  encontramos incidencia. No se puede parchear aquí: el paquete por defecto lleva el worker en base64 dentro de un archivo
  de 20 MB. La variante `dist/binaryWasm` lo trae en un archivo aparte y lo admitiría, cambiando el empaquetado.
- **Una retención acotada, que no crece.** Ketcher guarda el estado de su último almacén en una variable global
  (`global.currentState`) y su `highlightFG`, un antirrebote de módulo, conserva el último `dispatch` que recibió. Entre
  los dos mantienen alcanzable una instancia muerta, siempre la última. Visto en la instantánea de desarrollo; no se midió
  aparte en el export, donde los nodos son constantes.

## 6. El worker de Indigo perdía lo que se le enviaba (arreglado)

Arreglada la pantalla retenida (§1–§3), la memoria seguía subiendo 5–8 MB por cambio de caso, fuera de JavaScript: el
montón (+0,35 MB/cambio), los búferes de `ArrayBuffer` y los objetos de Blink no se movían.

**Prueba causal.** Tras 16 cambios, cerrar el worker de Indigo liberaba **325 MB** (con un caso evaluado) o **216 MB**
(sin él); vaciar Mol\*, 8. En esos cambios la página le había enviado 234 MB, 203 de ellos de biblioteca de monómeros.

**La causa, en el código del worker** (embebido en `ketcher-standalone/dist/main.js`, 3.18.0). Por cada mensaje crea un
mapa de opciones de C++, `new indigo.MapStringString()`, y no lo libera nunca con `.delete()`: los objetos de embind viven
en la memoria de WebAssembly y el recolector de basura no los ve. Y en las opciones de cada conversión Ketcher mete
`JSON.stringify(...monomersLibraryParsedJson)`, la biblioteca de monómeros del editor central entera (~1,3 MB). Cada
`getSmiles` o `getMolfile` dejaba ~1,3 MB atrapados. Un cambio de caso hace unas tres conversiones; una evaluación, decenas.

**El arreglo** (`frontend/lib/indigoSinFuga.ts`). La biblioteca sólo la necesitan las macromoléculas: el modo de
macromoléculas del editor, los formatos de secuencia (FASTA, HELM, IDT…) y los KET que contienen monómeros. Para todo lo
demás se quita del mensaje antes de enviarlo y el mapa que se pierde pasa a pesar unos cientos de bytes. Se envuelve
`Worker.prototype.postMessage` al cargar el editor: el worker es interno a ketcher-standalone y `ketcher.structService` es
un envoltorio sin `.worker` (la primera versión del arreglo lo buscaba ahí, no se instalaba y lo vio la medida, no las
pruebas). Sólo se toca un mensaje con la forma exacta de una conversión de Indigo.

**No cambia ningún resultado.** Cada conversión real de una sesión (siete moléculas con estereoquímica, cargas,
halógenos y el macrociclo de QA-030, «Ver 3D» y una evaluación completa) se reenvió a un segundo worker dos veces, con
la biblioteca y sin ella. La aplicación sólo hace dos tipos de conversión, a SMILES (159) y a molfile (51); se reenviaron
25 de cada uno y las respuestas fueron idénticas, byte a byte, sin errores.

| Medido en el export (Edge) | Antes | Después |
|---|---:|---:|
| Enviado al worker en 16 cambios | 103–234 MB | 0,4–1,1 MB |
| Lo que libera cerrar el worker al final | 216–325 MB | 116–123 MB (su tamaño de base) |
| Memoria de la página por cambio, sin caso evaluado | 5,1–5,3 MB | 0,3 MB |
| Memoria de la página por cambio, con caso evaluado (30 cambios) | 6,1–8,8 MB | 1,4 MB |

**El 1,4 MB que queda lo pone el instrumento.** Un volcado de memoria de Chromium (`memory-infra`) lo sitúa en
`partition_alloc` (+23 MB vivos en 20 cambios), y la diferencia entre dos instantáneas, en
`blink::NetworkResourcesData::ResourceData` (+1 837): es donde DevTools guarda el cuerpo de cada respuesta mientras el
dominio `Network` está activo, y Playwright lo activa siempre. Medido conduciendo Edge por CDP en crudo, 24 cambios con un
caso evaluado tras calentar: **−0,79 MB por cambio sin el dominio `Network`** y +0,28 con él.

## 7. En desarrollo (`next dev`) eran tres causas más (arreglado)

Con `next dev`, cada cambio de caso seguía reteniendo 1 308 nodos, 540 oyentes y 13,9 MB de montón (2026-11-11, Edge
contra el servidor de desarrollo; el día antes, en la ventana de Tauri, 1 336 y 542). El export nunca lo tuvo. Dos causas
son del modo estricto de React, que en desarrollo monta el editor dos veces, y la tercera de React Refresh.

**A. El aviso de Ketcher llega tarde.** Su `onInit` no sale cuando una instancia termina de arrancar: lo lanza un efecto
de su componente exterior (`Editor`) cuando también está listo el editor de macromoléculas. Con el doble montaje, el
aviso de la primera instancia, que Ketcher ya ha destruido, llega cuando la segunda ha registrado el teclado y todavía
no ha creado su editor. El vigía lo tomaba por el de la instancia que arrancaba y dejaba de mirar `document`; los tres
oyentes de la segunda (`mousemove`, `mouseup`, `mouseleave`) se registraban sin envolver y no se retiraban nunca, y el
aviso bueno, que llega después, se descartaba. Traza de un montaje, en milisegundos:

| ms | Qué pasa |
|---:|---|
| 16 761 | la primera instancia registra el teclado: empieza la vigilancia |
| 16 824 | su editor registra sus oyentes de `document`: envueltos |
| 16 875 | Ketcher destruye la primera instancia |
| 16 879 | la segunda registra el teclado |
| 16 952 | llega el aviso de la **primera** (su lienzo ya no está en el documento): el vigía cerraba aquí |
| 17 028 | el editor de la segunda registra sus oyentes de `document`: **sin envolver** |
| 17 117 | llega el aviso de la segunda: se descartaba |

En el primer montaje de la página no pasa: el editor de macromoléculas tarda en cargarse y sólo llega un aviso, el bueno.

**B. React Refresh retiene las raíces que hacen un commit después de desmontarse.** Su `onCommitFiberRoot` apunta la raíz
en un mapa fuerte (`helpersByRoot`) en cada commit y sólo la borra en el commit que la desmonta. La raíz propia de Ketcher
hace un segundo commit dentro de su misma llamada a `unmount()` (medido: tras el primero queda trabajo síncrono
pendiente), vuelve al mapa y no sale. En desarrollo las fibras guardan la pila de dónde se creó cada elemento
(`_debugStack`), y por ahí se alcanza el editor de macromoléculas y su interfaz. Es la única causa con el modo estricto
apagado. Next 16.4.3 trae react-refresh 0.12.0; el código es el mismo en la rama principal de React.

**C. El editor central no sabe de quién es.** `new CoreEditor()` no recibe el identificador de su Ketcher y toma «el último
que se añadió». En modo estricto ése es la segunda instancia, que todavía no tiene editor, así que se queda con
`micromoleculesEditor = null`. El vigía lo reconocía comparando con el editor, no lo encontraba, y su herramienta de
selección seguía apuntada en `RotationView.rotationCenterSubscribers` (§1, tercer retenedor).

Cada una se confirmó neutralizándola por separado, sin tocar el código del producto salvo dos experimentos temporales en
el vigía:

| `next dev`, por cambio de caso | Nodos | Oyentes | Montón |
|---|---:|---:|---:|
| Como estaba (modo estricto encendido) | +1 308 | +540 | +13,9 MB |
| Modo estricto apagado | +985 | +470 | +10,3 MB |
| Modo estricto apagado y B neutralizada | 0 | 0 | +0,5 MB |
| Modo estricto encendido, A y B neutralizadas | +611 | +255 | +1,0 MB |
| Modo estricto encendido, A, B y C neutralizadas | 0 | 0 | +0,9 MB |

**El arreglo.**

- A: un aviso cuyo editor tiene el lienzo fuera de la raíz es de una instancia sustituida. No cierra la vigilancia, y a
  ese editor se le quitan sus manejadores en el momento (`lib/ketcherOyentes.ts`).
- C: el editor central se reconoce también por dónde está su raíz (`ketcherRootElement`), dentro de la pantalla de este
  Ketcher.
- B: `lib/reactRefreshSinFuga.ts` aparta de React Refresh los commits de una raíz que ya se vio desmontada, salvo los que
  traen error. Sólo se instala en desarrollo, y en el export no queda rastro (comprobado sobre `out/`).

**Medido después.** `next dev` con el modo estricto encendido, 8 cambios: 0 nodos y 0 oyentes por cambio desde el segundo, y
el montón quieto (246,6 → 247,2 → 246,8 MB). El export, 12 cambios con la prueba de resistencia: 0 y 0, dentro del
presupuesto. El editor carga moléculas y dibuja con el ratón en desarrollo igual que antes del arreglo.

**Cómo se midió.** Una cápsula de QA con su servidor de comandos movido al puerto 13094 y, en el 13014, un proxy que
sirve `next dev` (puerto 3000) con el Tauri simulado inyectado. Así la página de desarrollo conserva el origen que el
backend acepta. También lo mide la prueba de resistencia sobre la ventana real, con un binario de depuración que cargue
`http://localhost:3000` (`--binario`).

Una nota anterior de este documento decía que el modo estricto no era la causa. Aquella prueba cambió cómo trataba el
vigía los dos arranques; no apagó el modo estricto.

## Sin verificar

- La ventana de Tauri en desarrollo (`tauri dev`) con el arreglo de §7: se midió en Edge contra `next dev`.
- El arreglo de §7 con la extensión React DevTools instalada: los commits que se apartan tampoco le llegan a ella.
- En desarrollo, el primer clic de dibujo en el primer editor que se abre no añadió el enlace en la comprobación, con el
  código de antes y con el de ahora. No se investigó.
- El binario de release y el instalador: no se construyen hasta cerrar 1.0.4. Lo probado es el binario de depuración con
  el export incrustado, que es la misma ventana de WebView2 con la misma interfaz.
- Una máquina sin GPU ni una VM: la pasada larga fue con GPU.
- La pantalla completa del sistema dentro de WebView2: en Edge se concede; en la ventana de Tauri no se probó, y el visor
  tiene el respaldo de ocupar la ventana.
