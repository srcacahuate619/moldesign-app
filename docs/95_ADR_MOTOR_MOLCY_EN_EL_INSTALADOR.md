# ADR 95 — El motor Molcy viaja en el instalador, como programa independiente GPL-3.0-or-later

**Estado:** implementado en la rama `qa/molcy-blender`; pendiente de build de instalador, de `smoke:prod` y de una prueba en una máquina limpia.
**Fecha:** 2026-10-04 (cierre obligatorio y repositorio público el mismo día). **Sustituye** lo que el ADR 92 dejaba pendiente («la distribución del motor GPL independiente requiere preparar y verificar
su paquete complementario»).

## El problema, medido

Molcy tiene tres componentes: **Blender** (programa de 3D), **Molecular Nodes** (extensión de Blender) y el **motor** (los scripts que, ejecutados
dentro de Blender, construyen la escena y dibujan el vídeo). Los dos primeros se obtienen bajo demanda; el motor no se obtenía de ninguna parte.
La pantalla pedía una «Carpeta del motor Molcy» —ruta a un repositorio del propietario, sin licencia, que ningún investigador tiene—, de modo que
aunque la aplicación descargara Blender (404 MB) y Molecular Nodes (133 MB) **ningún usuario real podía generar un vídeo**.

## Decisión

El propietario decidió (2026-10-04): el motor va **dentro del instalador**, es **obra propia** y se publica bajo **GPL-3.0-or-later**.

### ¿Estamos obligados a hacerlo GPL?

Sí, en la práctica y por una razón concreta, no por «usar» Blender como herramienta: el motor es código que **se carga dentro de Blender**
(`blender -b --python maestro.py`), **importa `bpy`** (la API de Python de Blender) y activa **Molecular Nodes** para construir la escena.
Blender se publica bajo `GPL-3.0-or-later` (© Blender Foundation) y Molecular Nodes declara `SPDX:GPL-3.0-or-later` (© 2022 Brady Johnston). La lectura
habitual es que un programa que importa `bpy` y se ejecuta en el mismo proceso es una obra derivada y debe distribuirse bajo una licencia GPL
compatible (la plataforma oficial de extensiones de Blender, por ejemplo, sólo admite licencias compatibles con la GPL). `GPL-3.0-or-later` es la que coincide con la de Molecular Nodes (una GPL-2.0-only no
serviría con ella).

Lo que **no** cambia: el copyright sigue siendo del propietario, que puede además licenciar su propio código por otra vía a quien quiera
(doble licencia); y MolDesign **no** pasa a ser GPL: sigue bajo PolyForm Noncommercial. La razón es la frontera de abajo.

Lo que **sí** implica, y conviene saberlo antes de publicar: quien reciba el motor lo recibe bajo GPL, es decir, con derecho a usarlo,
modificarlo y redistribuirlo **también con fines comerciales**. La reserva comercial de PolyForm no se aplica a ese directorio.

> Esto es ingeniería y procedencia, **no asesoría jurídica**. Igual que el ADR 79 con Open Babel, una revisión legal externa sigue siendo
> recomendable antes de vender licencias comerciales.

### La frontera (mera agregación, como Open Babel)

- MolDesign **no importa** ningún módulo del motor y el motor **no importa** nada de MolDesign (`backend/tests/test_frontera_motor_molcy.py`).
- MolDesign lo ejecuta por **subproceso**, con la ruta **absoluta** de `correr_caso.ps1` y de Blender, y se comunican por ficheros (`scene.json`,
  geometría, acta y MP4). Nunca se resuelve nada por `PATH`.
- Viajar en el mismo instalador es agregación, no combinación en una sola obra.

## Qué viaja

`tools/molcy/` (51 ficheros, ~2,3 MB): `scripts/maestro.py`, `scripts/correr_caso.ps1` y los paquetes `formatos`, `guiones`, `marca`, `nucleo`,
`salida`, `sujetos` y `variables`; la plantilla de arte (`plantilla_arte.blend`); el emblema; `LICENSE` (texto íntegro de la GPL-3.0-or-later, el de la
distribución de Blender 5.2.2) y `NOTICE.md`; y `molcy-manifest.json` con el SHA-256 de cada fichero, el commit de origen y la licencia.

**No viaja:** la interfaz Flask del propietario, las pruebas, las herramientas de desarrollo (con rutas de su máquina), `preparar_emblema.py` (herramienta de una
sola vez) y los 73 MB de casos y vídeos ya generados. **Blender y Molecular Nodes tampoco viajan**: se descargan a petición y MolDesign no los distribuye.

### De dónde sale

El motor tiene su propio repositorio. Se vendoriza desde un **commit** con `scripts/stage_molcy_motor.py --fuente <repo> --write`, leyendo los *blobs* de git
(no el árbol de trabajo, cuyos saltos de línea dependen de `core.autocrlf`) y exigiendo que el árbol esté limpio en lo que se copia. El manifiesto
registra rama y commit. El repositorio de MolDesign marca `tools/molcy/**` como `-text` para que git no toque sus bytes.

**Desde el 2026-10-04 la fuente es un repositorio público propio del motor:** <https://github.com/srcacahuate619/moldesign-molcy> (rama `main`). Es la
oferta de código fuente que pide la GPL: cada instalador lleva un `molcy-manifest.json` cuyo `fuente.commit` es el commit exacto de ese repositorio del que
sale la copia incluida (`fuente.repositorio` es la URL, sin credenciales; `stage_molcy_motor.py` la lee del remoto `origin` y la omite si el remoto es ssh o local).
Para actualizar el motor: se cambia **allí**, se commitea, y aquí se ejecuta `stage_molcy_motor.py --fuente ..\moldesign-molcy --write`. Nunca al revés ni a mano.
Antes sólo existía la rama `molcy/integracion` del repositorio privado del propietario (`E:\proyect3d`, que no trae los cambios de CPU/GPU).

## Qué se corrigió en el motor antes de distribuirlo

La guarda de rutas de máquina (que forma parte de `check:molcy-motor`) encontró en el motor:

| Dónde | Qué | Arreglo |
|---|---|---|
| `nucleo/rutas.py` | `ESCENAS = D:\moldesign-build\dist\scenes`, `CASOS = E:\proyect3d\moldesign\cases`, `BLENDER = E:\blender.exe` por defecto | salen de `MOLCY_SCENES_DIR`, `MOLCY_CASES_DIR`, `MOLCY_BLENDER` o de carpetas junto al proyecto |
| `correr_caso.ps1` | `-Blender` valía `E:\blender.exe` por defecto | toma `MOLCY_BLENDER`; sin ninguno, `SIN_BLENDER` |
| `marca/cierre.py` | `C:\Windows\Fonts\seguisb.ttf` y `...\CascadiaMono.ttf` por ruta fija: Cascadia Mono no está en todo Windows 10 y una fuente ausente hacía fallar el cierre de **todos** los vídeos | `_fuente_del_sistema()` busca en `%SystemRoot%\Fonts` con alternativas (Segoe UI → Arial; Cascadia Mono → Consolas → Courier) y, sin ninguna, Blender usa la suya |
| `marca/preparar_emblema.py` | `D:\moldesign-build\msix\assets\...` | no se distribuye (herramienta de una sola vez) |

Quien use la interfaz Flask del propietario en su máquina debe fijar ahora `MOLCY_SCENES_DIR` (antes tomaba `D:\moldesign-build\dist\scenes`) y, si Blender no
está en el PATH, `MOLCY_BLENDER`.

## Cómo lo usa el backend

`backend/services/molcy/motor.py` (sólo biblioteca estándar): localiza el motor incluido (`MOLDESIGN_MOLCY_DIR`, que pasa Rust; si no, la carpeta hermana de
Open Babel; en desarrollo, `tools/molcy`) y verifica su integridad contra el manifiesto. `renderer.motor_elegido()` usa **siempre el incluido** y lo verifica.
Con el incluido alterado, el detector se abstiene (`motivo_codigo: motor_alterado`, «Reinstala MolDesign») **sin lanzar Blender**. La procedencia
(origen, commit y licencia del motor) queda en el estado de cada trabajo.

Un motor propio (el de `MOLCY_ENGINE_DIR` o el que guarda la configuración) **sólo se acepta con `MOLCY_PERMITIR_MOTOR_PROPIO=1`** en el entorno del proceso:
es el interruptor de quien desarrolla el motor y no tiene ningún camino desde la aplicación (ver «El cierre es obligatorio»). La pantalla dice que el motor viene
incluido y **no ofrece elegir otro**; si falta, avisa de que hay que reinstalar.

## Escenas y presupuesto de recursos (2026-10-05)

Una corrida de Moldex conserva el receptor preparado y su hash: puede producir tanto
«Resultado» (si también conserva las poses) como «Receptor», usando los bytes de esa
corrida, sin sustituirlos por una preparación posterior. «Búsqueda» permanece
deshabilitada: Vina no conserva su traza interna; caja, semilla y poses finales no
permiten representar honestamente los pasos recorridos. «Ensamble» sigue pendiente
de un guion que represente el conjunto de poses conservadas.

`GET /molcy/recursos` consulta CPU y memoria GPU sin iniciar Blender. La pantalla
actualiza la medición cada cinco segundos antes del render. El máximo de hilos
reserva el 25% de los procesadores lógicos disponibles y se reduce según la carga
actual. El backend vuelve a comprobarlo antes de iniciar. En Windows, el proceso
principal y sus descendientes reciben prioridad inferior a la normal y un límite
nativo de consumo CPU mediante Job Objects, nunca superior al 75% de la máquina.
Estos límites incluyen procesos auxiliares y el cierre, también en modo GPU.

Desde el 2026-10-05, Blender gestiona automáticamente la VRAM. La pantalla no
ofrece una cuota de memoria: el antiguo presupuesto vigilaba el consumo adicional
de toda la tarjeta y podía detener el render, pero no limitaba sus asignaciones.
GPU se habilita cuando el sondeo de Blender confirma que puede renderizar con
ella, aunque NVML no esté disponible. Se mantienen los límites CPU también en GPU.
La gestión automática no garantiza que el equipo permanezca fluido ni reserva RAM.

La API conserva el campo obsoleto `gpu_vram_mib` para clientes anteriores. Si lo
envían explícitamente, su presupuesto sigue requiriendo telemetría y la vigilancia
original; la aplicación actual lo omite y no ejecuta esa vigilancia.

Las pruebas de escenas, telemetría simulada, parada de un proceso real y límite
CPU nativo están en `backend/tests/test_molcy_escenas_y_limites.py`. El motor GPL
incluido conserva sus bytes y el cierre obligatorio.

## El cierre de MolDesign es obligatorio en todo vídeo (decisión del propietario, 2026-10-04)

El cierre (la firma animada del final, de ~3,6 s) forma parte de la estrategia de marketing: **todo vídeo que genere un usuario termina con él y la aplicación
no ofrece ningún modo de quitarlo.** Lo hacen cumplir cuatro capas, de dentro afuera:

1. **El motor** (repositorio `moldesign-molcy`): no existe `Interruptor("cierre")`; `Formato.cierre_s` no puede bajar de 3,0 s (ni con `dataclasses.replace`);
   los tres formatos lo traen (la prueba también, 3,6 s); `controles.validar` rechaza un `cierre` que llegue por cualquier lado; `codificar.py`, `sellar_mp4.py` y
   `correr_caso.ps1` fallan (`SIN_CIERRE`) si no reciben las imágenes y el manifiesto del cierre; la vista previa en CPU sigue llevándolo (la escena se acorta a
   3 s, el cierre no). Las pruebas del motor lo comprueban. Desde el 2026-10-08 la aplicación ya no ofrece vídeo por CPU (ver «Fotos»); el motor conserva ese
   camino para uso manual.
2. **El backend verifica el resultado, no la intención** (`backend/services/molcy/cierre.py`): un trabajo sólo pasa a «completo» si el acta acredita
   `formato.cierre_s ≥ 3`, `cierre{segundos, fotogramas, huella}` coherentes y `video.segundos ≈ duracion_s + cierre_s`, **y** la duración que declara el propio
   MP4 (se lee el átomo `mvhd`; sin ffprobe) no es menor que lo esperado. Un vídeo que dura sólo lo de la escena se rechaza aunque el acta lo jure.
3. **No hay camino desde la aplicación** hacia otro motor: `PUT /molcy/configuracion` rechaza `motor`, la pantalla no tiene el campo, el motor incluido se
   verifica contra su manifiesto antes de cada ejecución y el instalador lo trae junto al backend.
4. **Presupuesto de disco** con los fotogramas del cierre de cada formato (`disk.BRAND_FRAMES`).

**Límites, dichos sin adorno.** La GPL-3.0-or-later permite a cualquiera modificar su copia del motor, también para quitar el cierre; no es una condición de la
licencia (`NOTICE.md` lo dice) y añadirla como tal sería una restricción adicional que la GPL no permite. Lo que protege el cierre es: (a) que la aplicación
no ofrece quitarlo ni tiene un camino para ello, (b) que quien edite el motor incluido lo ve la verificación de integridad, y (c) que el nombre y el emblema son
marca de MolDesign y la licencia no los concede. Quien edite los ficheros instalados, fije `MOLCY_PERMITIR_MOTOR_PROPIO` o edite el vídeo a mano puede quitarlo:
eso no es un defecto que esta capa pueda cerrar. Los vídeos que ya estuvieran generados antes de este cambio no se vuelven a verificar.

## Fotos: la CPU toma fotos y el vídeo es sólo con GPU (decisión del propietario, 2026-10-08)

**Por qué.** Medido el 2026-10-07 con el motor `69fe2e7`: tres segundos de vídeo por CPU no enseñaban nada de lo que da valor al vídeo (Resultado sin
etiquetas legibles; Búsqueda con dos o tres fotogramas por pose) y Cycles en CPU costaba ~8–10 s por fotograma a 720 px, más el cierre (1079 s la primera
vez, 4 hilos). Una foto es un solo fotograma: viable en CPU. El propietario decidió: (1) el vídeo, sólo con GPU; (2) la CPU toma **fotos**, y con GPU también
se pueden pedir; (3) **Cycles en todas las fotos**, para que la foto no dependa del equipo; (4) resolución de **720p** (el piso) a **4K** (el techo, para
imprimir: 32,5 × 18,3 cm a 300 ppp); (5) primero las tomas sugeridas y, como segunda opción, cualquier fotograma; (6) toda foto lleva el emblema de
MolDesign, **sutil, en una esquina**.

**Cómo.** El motor (`moldesign-molcy`, rama `codex/fotos`) añade `maestro.py --fotos` (construye la escena entera, sin el recorte de la CPU, y guarda el
`.blend` horneado con `escena_fotos_*.json`), `variables/momentos.py` (las tomas sugeridas salen de la escena: cada pausa del montaje, el plano general con
el título y la mitad de cada beat de recorrido sin pausa propia), `foto.py` (dentro de Blender: abre el `.blend` y rinde fotogramas con Cycles en CPU o en
GPU —CUDA, OptiX, HIP, oneAPI o Metal—, OpenImageDenoise, semilla 0, sin desenfoque de movimiento; la capa de rótulos aparte, como el vídeo) y
`correr_foto.py` (Python con Pillow, fuera de Blender: `preparar` y `tomar`, con un acta por PNG). La frontera no cambia: MolDesign lanza
`correr_foto.py` por subproceso con su Python y lee ficheros; no importa nada del motor.

El backend (`services/molcy/fotos.py`) trata una **sesión de fotos** como un trabajo más (su carpeta, su `estado.json`, la misma cola de Blender):
preparar una vez, y después fotos (`POST /molcy/trabajos/{id}/fotos`) y vistas libres a tamaño de miniatura (`/vista`) sin reconstruir la escena. El acta de
cada foto tiene que acreditar lo pedido —fotograma, resolución, Cycles, dispositivo, muestras, hilos, el SHA-256 de la escena y del `.blend`— o la foto no se
entrega; un fallo o una cancelación no estropean la sesión. El sondeo del renderizador rinde 8×8 px con Cycles en la GPU antes de anunciarla
(`foto_gpu_disponible`): encontrar una GPU no basta. Medido en 4FK3 (Ryzen 5 5500 con 8 hilos / GTX 1660 SUPER, 128 muestras): preparar 38 s con CPU;
720×1280 en 81 s (CPU) y 24 s (GPU); 1080×1920 en 104 s y 25 s; 4K en 13,4 min y 90 s. La foto de CPU y la de GPU difieren 0,03/255 de media y 6/255
como máximo.

**La marca de las fotos** (`services/molcy/marca_foto.py`) la pone **MolDesign**, no el motor: el emblema de `backend/assets/logo.png` con su transparencia,
al 30 % de opacidad, del 7 % del lado corto, en la primera esquina libre de rótulos según el acta del motor (`esquinas`: lo que ocupa la capa de rótulos en
cada esquina). Así es la misma en CPU y en GPU y no depende de una copia del motor. Se hace cumplir como el cierre:

1. **No hay interruptor**: ni en la API ni en la pantalla.
2. **Lo que se entrega lleva la marca por construcción**: el backend compone la marca sobre el PNG del motor y **borra el PNG sin marca**, también cuando la
   foto falla después de rendirse; `GET /molcy/trabajos/{id}/fotos/{n}` sólo sirve la foto marcada y comprueba su SHA-256.
3. **La procedencia viaja dentro del PNG** (iTXt `MolDesign`): corrida, receptor y sus hashes, escena, fotograma, momento, resolución, ajustes de Cycles,
   versión de MolDesign y commit del motor. Sólo identificadores, hashes y versiones: ni rutas del equipo ni el nombre del caso.

**Límites, dichos sin adorno.** La sesión conserva en su carpeta el `.blend` y el acta de la escena (son su evidencia), las miniaturas de las tomas y las vistas
libres (480 px, sin marca): quien abra ese `.blend` con Blender puede rendir sin marca, y la GPL permite modificar el motor. Una marca en una esquina se
recorta; la procedencia embebida se puede borrar con cualquier editor. Lo que protege la marca es lo mismo que protege el cierre: la aplicación no ofrece
quitarla y el emblema es de MolDesign.

## Cómo se verifica en el build

| Qué | Dónde |
|---|---|
| `tools/molcy/` íntegro frente al manifiesto, GPL verdadera, sin rutas de máquina | puerta 8, `check:molcy-motor` (`stage_molcy_motor.py --check`) |
| la copia del **runtime staged** íntegra y localizada por el backend empaquetado, sin la variable de Rust | `verify:desktop-runtime` → `validate_molcy_motor` |
| el motor es herramienta **crítica** del empaquetado | `bundle_helper.HERRAMIENTAS_CRITICAS` |
| el motor figura en el SBOM con su licencia y su procedencia | `generate_sbom.py` (5 binarios) |
| el runtime empaquetado informa `motor_incluido` | `smoke:prod` |
| la frontera de importaciones | `backend/tests/test_frontera_motor_molcy.py` |

## Lo que queda abierto

- **Marca.** `moldesign/assets/marca/*.png` (nombre y emblema de MolDesign) viajan dentro de un directorio GPL. `NOTICE.md` dice que la GPL no concede derechos
  de marca. Decisión del propietario si quiere otra cosa. En el repositorio no consta que el nombre esté registrado como marca; si no lo está, esa protección es más débil de lo que suena.
- **Revisión jurídica** antes de vender licencias comerciales (ver arriba).
- **Fuente correspondiente.** La GPL exige ofrecer el código fuente del motor con cada publicación. El instalador **lleva** el código fuente (son scripts de
  Python) y la oferta está escrita en `THIRD_PARTY_NOTICES.md` y `tools/molcy/NOTICE.md` con la URL del repositorio público. Cada commit que viaje debe
  estar publicado antes de construir la release. El motor de Búsqueda `9e9c48f` se publicó con autorización del propietario el 2026-10-05; el encuadre y la
  capa del título de esa escena y las retiradas de `sitio_activo` se corrigieron después (`83c6ad4` y `3147090`, publicados el 2026-10-05 con autorización
  del propietario en la rama `codex/busqueda-interna-vina`) y el motor vendorizado viene ahora de `f836a05` (interacciones de Resultado y Búsqueda); los tres commits (`83c6ad4`, `3147090`, `f836a05`) están publicados en la rama `codex/busqueda-interna-vina` con autorización del propietario. Ver [la traza y sus verificaciones](TRAZA_BUSQUEDA_MOLCY.md).
- **Justificación de `runFullTrust` de la Store.** `docs/STORE_RUNFULLTRUST_JUSTIFICATION.md` enumera los procesos que MolDesign lanza; Molcy añade PowerShell y
  Blender. No se ha actualizado.
- **Sincronía con el repositorio del motor.** Los cambios del motor llegan aquí con `stage_molcy_motor.py` desde `moldesign-molcy`. La rama `molcy/integracion` del
  repositorio privado del propietario queda superada por ese repositorio; no se mantiene en dos sitios.
- **Verificado el 2026-10-05:** `stage:desktop`, `verify:desktop-runtime`, las dos evaluaciones reales del runtime y `smoke:prod` (22/22), además de un
  MP4 de Búsqueda en GPU con cierre acreditado. **Pendientes:** `tauri:build`, el MSIX y una máquina limpia.
