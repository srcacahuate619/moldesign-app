# Sitio público de MolDesign

Sitio estático bilingüe de varias páginas. Publicar **la carpeta `site/` completa**:
las páginas dependen de los estilos, scripts, fuente y capturas de `assets/`. No
necesita Next.js, un backend ni un servidor de aplicación.

La URL canónica es `https://moldesign.amezcua-dev.com/` (decisión del propietario,
2026-10-11), la misma que abre la app y que escribe el cierre de los vídeos de Molcy.
Vive en una sola constante, `DOMINIO`, de `scripts/build_sitio_publico.py`: de ahí
salen el `canonical` y el `og:url` de cada página, `sitemap.xml` y `robots.txt`. Todos los enlaces de privacidad apuntan a
`https://moldesign-privacidad.amezcua-dev.com/`; `privacy/` es esa página y sus
enlaces de vuelta llevan a la URL canónica, porque se sirve en otro subdominio.

## Páginas

| Ruta | Archivo | Contenido |
|---|---|---|
| `/` | `index.html` | Portada: descarga en Microsoft Store, repositorio en GitHub, recorrido por las pestañas en el orden de la aplicación (Preparación, Molcy, Batch, Evaluación, Moldex, Historial), novedades de 1.0.2 (Molcy como novedad estrella, con vídeo y tutorial; Preparación con lo que midió FEP-09-R1; el resto en tarjetas), flujo, preguntas. |
| `/ciencia/` | `ciencia/index.html` | El registro científico completo: cada experimento sellado, con su artículo o la ficha de su manifest. |
| `/catalogo/` | `catalogo/index.html` | El catálogo de receptores con su estado real y el explorador. |

No hay página de descargas: la descarga es el botón principal de la portada y lleva a
Microsoft Store. Los expedientes de `/ciencia/` no tienen página propia: cada uno es
un ancla, `/ciencia/#CAL-8HFI-01`, que abre ese expediente.

## Cómo se edita: `scripts/build_sitio_publico.py`

```bash
python scripts/build_sitio_publico.py          # regenera
python scripts/build_sitio_publico.py --check  # falla si algo no está al día o un enlace no resuelve
```

- **La cabecera y el pie se editan en la portada.** Viven entre
  `<!-- compartido:cabecera -->` y `<!-- /compartido:cabecera -->` (y `pie`). El
  script los copia a las demás páginas, corrige las rutas relativas para su carpeta
  y marca `aria-current` en el enlace con su `data-pagina`. Editarlos en otra página
  no sirve: se sobrescriben.
- **El registro de `/ciencia/` se genera** entre `<!-- generado:registro -->` y su
  cierre, desde `frontend/public/registro/`, el mismo JSON que usa la aplicación.
  Ese JSON lo emite `scripts/build_registro_cientifico.py` desde los manifests
  sellados de `scripts/artifacts_science/` y los artículos de `docs/papers/`. Para
  publicar un artículo nuevo: escribirlo, correr los dos scripts, en ese orden. Va
  como HTML y no como datos que pinte JavaScript, para que se lea sin JavaScript,
  lo indexen los buscadores y funcione el enlace directo.
- **El catálogo de `/catalogo/` se incrusta** desde `receptors.json`, entre
  `<!-- generado:receptores -->` y su cierre, para que el explorador no haga
  peticiones.
- **Las cifras no se escriben a mano.** Un elemento con `data-dato="registro-total"`
  recibe su valor de `datos()` en el script. Una clave que no existe falla. Las
  fechas y los valores bilingües van en un elemento que no sea `<span>` (`<time>`,
  `<b>`), porque traen sus dos idiomas en `<span>`. Las cifras de Preparación salen de
  las métricas selladas de FEP-09-R1, incluidas las que no detecta.
- **El tutorial de Molcy se copia de la aplicación**, entre
  `<!-- generado:tutorial-molcy -->` y su cierre: capturas (a
  `assets/tutorial/molcy/{es,en}/`), cajas y textos del Inicio. No se edita aquí: se
  regenera en la app (`frontend/scripts/capturas-tutorial-molcy.mjs`) y después se corre
  este script.

## La demostración en vídeo de Molcy

```bash
python scripts/preparar_demo_molcy.py --video "<carpeta salida de Molcy>/<vídeo>.mp4"
python scripts/build_sitio_publico.py
```

El primero recomprime un vídeo real de Molcy (H.264 a 720 px de ancho, sin audio) y
escribe `assets/molcy-demo.mp4`, su fotograma de reposo `molcy-demo.webp` y
`molcy-demo.json`, con el SHA-256 del original (comprobado contra su `.sha256`) y lo
que Molcy declaró de él: corrida, receptor, escena, poses, pasos. El pie del vídeo en la
portada sale de ese JSON, y el generador se niega a publicar si el vídeo no es el que
describe. No es un GIF: medido el 2026-10-11 sobre el vídeo de 4FK3, un GIF de 360 px a
15 fps pesaba 18,6 MB y el MP4 de 720 px a 30 fps, 2,7 MB. En la página se comporta
como un GIF (en bucle, sin sonido, sin controles), sólo se reproduce mientras se ve y
tiene un botón para pararlo; con «reducir movimiento» no arranca solo.

La demo actual es la escena Búsqueda de la corrida `381491c8` sobre 4FK3 (elegida por el
propietario). Se renderizó el 2026-10-07, así que su cierre escribe el dominio de
entonces, `molecule-design.amezcua-dev.com`, en letra muy pequeña.

`backend/tests/test_sitio_publico.py` comprueba que `site/` está al día, que ningún
enlace interno está roto y que cada experimento sellado tiene su expediente, y
demuestra con controles negativos que cada guarda detecta su fallo.

## Contenido y estado de publicación

Las novedades resumen `docs/versions/1.0.2_cambios.md`, sección 1, y las
restricciones de producto de `AGENTS.md`, con corte al **11 de octubre de 2026**.
**La web da por hecho que 1.0.2 es la versión actual en Microsoft Store** (decisión del
propietario, 2026-10-11): la descarga, la etiqueta «Versión actual» de las novedades, la
pregunta «¿Qué versión es la actual?» y las descripciones para buscadores y redes. El
11 de octubre la Store todavía tenía la 1.0.1 y el instalador de 1.0.2 no se había
construido: **no publicar esta web antes de que 1.0.2 esté en la Store**, o dirá algo
falso.

La banda bajo el recorrido desfila con diez mensajes (dos copias de la lista, la segunda
oculta a los lectores de pantalla), se para al pasar el ratón o con su botón y, con
«reducir movimiento», se queda quieta y se muestra entera.

- Molcy: Beta, vídeo con GPU y fotos con CPU o GPU; herramientas bajo demanda.
- Preparación: auditor de readiness para FEP en desarrollo, sin ejecutar FEP
  ni certificar compatibilidad con FEP+.
- Paquete de la evaluación: dossier, estructuras, protocolo, receta, auditoría
  y hashes; no se declara paquete FEP.
- Receptores propios: tres caminos de preparación, decisiones conservadas y
  límites de protonación y coordinación metálica declarados.
- Moldex, Lotes, anti-dianas, idioma y MolChat: cambios de la versión.

`/ciencia/` publica **los 171 experimentos sellados** al 11 de octubre de 2026, 77
con artículo; lo último sellado va primero. Separa hallazgos y refutaciones del
resto de poblaciones (mediciones, prerregistros, correcciones, inconclusos) porque
el cociente crudo de decisiones del manifest mezcla prerregistros, sellados GO por
convención, con experimentos que tenían un umbral real. Los textos científicos se
publican en español, su idioma original; la interfaz está en los dos idiomas. Los
enlaces de un artículo a otro pasan a ser anclas de la página; los enlaces a
documentos del repositorio que la web no publica quedan como texto.

El catálogo se deriva de `curated_targets.json`: 381 registros. `receptors.json`
conserva su SHA-256, fecha, campos y estados. La disponibilidad procede de
`backend/data/disponibilidad_catalogo.json` y los avisos de ensamblaje de
`backend/data/avisos_catalogo.json`. Son 13 preparaciones no disponibles con receta
7/Meeko 0.7.1. Todas las entradas son Demostración; Verificados tiene cero entradas.
Ningún script del repositorio regenera `receptors.json` (comprobado el 2026-10-11):
si cambia el catálogo, hay que rehacerlo y después correr `build_sitio_publico.py`.

## Diseño y recursos

Inspiración pública: [Deska](https://deska.dev/). Se estudiaron su HTML y CSS:
tipografía Geist, fondos oscuros, separación mediante bordes, demostraciones
del producto y explicaciones por tarea. La adaptación conserva el violeta de
MolDesign, su identidad y contenido propios. No reutiliza imágenes ni código
de Deska.

Las imágenes son copias sin modificación de las capturas reales del desarrollo:

- Moldex y Preparación: `docs/verificacion/cierre-1-0-2/capturas/`, es/en,
  oscuro, 1440 px. La vista de Preparación se recorta visualmente con CSS; las
  demás capturas del recorrido van enteras, con su proporción.
- Molcy (vídeo terminado), Batch, Evaluación e Historial del recorrido:
  `molcy-video-es.png`, `batch-es.png`, `evaluacion-es.png` e `historial-es.png`,
  capturas del desarrollo 1.0.2 que dio el propietario el 2026-10-11. Sólo existen
  en español: en inglés se ven igual y su pie lo dice («Spanish interface»).
- Tutorial de Molcy: `assets/tutorial/molcy/{es,en}/`, copia de
  `frontend/public/tutorial/molcy/` que hace el generador.
- Favicon: `frontend/public/logo.png`.
- Geist Latin: fuente local distribuida con Next.js; su licencia SIL OFL 1.1
  se incluye en `assets/OFL-Geist.txt`. La fuente sólo se aplica al sitio público.

Ninguna página carga fuentes, imágenes, analítica ni librerías remotas.
`assets/site.js` es común (menú, pestañas, idioma); `assets/molcy.js` (vídeo y
tutorial de la portada), `assets/ciencia.js` y `assets/catalogo.js` son de su página. El idioma elegido se recuerda en el navegador
y vale para todas las páginas. Sin JavaScript se leen todas las páginas y todos los
expedientes; el explorador del catálogo es lo único que lo necesita.

## Previsualizar

Abriendo `index.html` con `file:///` funciona: `site.js` reescribe los enlaces a
carpetas (`ciencia/`) para que apunten a su `index.html`, cosa que publicado no hace
falta. Para ver las URLs reales:

```bash
python -m http.server 8765 --directory site
```

## Validación

Verificado el 11 de octubre de 2026 en el navegador integrado del escritorio, sobre
un servidor local: las tres páginas a 1440 y 360 px sin desplazamiento horizontal;
`aria-current` en la página activa; búsqueda, filtros, enlace directo a un expediente
(también con filtros puestos), aviso de cifras reemplazadas, cambio de idioma, el
explorador del catálogo y las seis pestañas del recorrido, cada una con su captura y
su pie en los dos idiomas. La novedad estrella: el vídeo arranca al verse y se para al
salir de la vista o con su botón; los seis pasos del tutorial cargan su captura, y el
recuadro cae sobre el botón en los dos idiomas; a 360 px el vídeo va justo después de
la entradilla. No se repitió aquí la batería anterior de 14 combinaciones
de idioma y ancho ni la de contraste WCAG, y la página de ciencia (1,4 MiB; unos
290 KiB con gzip) no se midió en un móvil real.

Las capturas ilustran el estado del desarrollo y no sustituyen una verificación
del instalador ni del sitio desplegado. Para publicar cambios, cargar la carpeta
completa y comprobar su URL; no empujar la rama de desarrollo al repositorio
público.
