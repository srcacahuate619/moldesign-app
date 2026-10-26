"""Monta la secuencia de PNG en un MP4 usando el secuenciador de Blender.

No hay ffmpeg en el PATH de esta maquina; Blender trae las suyas.

    blender -b --python codificar.py -- <carpeta_png> <salida.mp4> [fps] [ancho] [alto] [carpeta_overlay] [--sobrescribir] [--cierre <carpeta>]

`--cierre` pega al final la firma de marca rendida por `marca/cierre.py`, tras
un fundido a negro de 8 fotogramas del video. Esa carpeta es cache compartida
entre videos y la limpieza de abajo nunca la toca.

La resolucion se toma del PRIMER PNG si no se pasa: fijarla a 1920x1080 rompia
`previsualizacion` (720x720) y `social_vertical` (9:16), que salian estirados.

`carpeta_overlay` es la pasada aislada del titulo —PNG con alfa— y se compone
en un canal superior con ALPHA_OVER. Se alinea por el numero de fotograma del
primer PNG: f_0060.png entra en el fotograma 60. Asi el titulo nunca queda
tapado por el receptor.

Si la carpeta trae `montaje.json` (lo escribe el maestro), el video sigue su
mapa `fuentes`: el fotograma de salida i es el fotograma fuente `fuentes[i]`. Una
pausa de lectura repite un fotograma —no se rinde dos veces la misma imagen— y
los mapas `escena` y `capa` dicen que PNG ya rendido se ve en su lugar cuando su
estado es identico al de otro (`salida/firmas.py`), cada pasada por separado.

Un video existente NUNCA se pisa por accidente: si <salida.mp4> ya existe hay
que pedirlo explicito con --sobrescribir.

Al terminar un encode completo, los PNG de entrada se borran: el MP4 es el
artefacto y los intermedios son ~1.3 GB por pieza.
"""
import bpy
import json
import os
import shutil
import sys
import glob

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
if len(argv) < 2:
    raise SystemExit('uso: -- <carpeta_png> <salida.mp4> [fps]')
SOBRE = False
if '--sobrescribir' in argv:
    SOBRE = True
    argv = [a for a in argv if a != '--sobrescribir']
# --cierre <carpeta>: la firma de marca (`marca/cierre.py`) que se pega al
# final, despues de un fundido a negro del video.
CIERRE = ''
if '--cierre' in argv:
    i = argv.index('--cierre')
    CIERRE = argv[i + 1] if i + 1 < len(argv) else ''
    argv = argv[:i] + argv[i + 2:]
if not CIERRE:
    # El cierre de MolDesign es obligatorio en todo video: sin el no se codifica nada.
    raise SystemExit('SIN_CIERRE: el cierre de MolDesign es obligatorio en todo video (--cierre <carpeta>)')
#: Fotogramas del fundido a negro del video antes del cierre, que a su vez
#: nace del negro: el empalme es un «dip to black», no un corte.
FUNDIDO = 8
CARPETA, SALIDA = argv[0], argv[1]
if os.path.exists(SALIDA) and not SOBRE:
    raise SystemExit('NO_SOBREESCRIBO: ya existe %s '
                     '(pasa --sobrescribir si es lo que quieres)' % SALIDA)
FPS = int(argv[2]) if len(argv) > 2 and argv[2].isdigit() else 30
ANCHO = int(argv[3]) if len(argv) > 3 and argv[3].isdigit() else 0
ALTO = int(argv[4]) if len(argv) > 4 and argv[4].isdigit() else 0
OVER = argv[5] if len(argv) > 5 and argv[5] else ''

pngs = sorted(os.path.basename(p) for p in glob.glob(os.path.join(CARPETA, '*.png')))
if not pngs:
    raise SystemExit('no hay PNG en ' + CARPETA)
FUENTES = None
if os.path.isfile(os.path.join(CARPETA, 'montaje.json')):
    with open(os.path.join(CARPETA, 'montaje.json'), encoding='utf-8') as fh:
        MONTAJE = json.load(fh)
    FUENTES = [int(f) for f in MONTAJE['fuentes']]
    ESCENA = {int(k): int(v) for k, v in (MONTAJE.get('escena') or {}).items()}
    CAPA = {int(k): int(v) for k, v in (MONTAJE.get('capa') or {}).items()}
    pngs = ['f_%04d.png' % ESCENA.get(f, f) for f in FUENTES]
    faltan = sorted({n for n in pngs if not os.path.isfile(os.path.join(CARPETA, n))})
    if not FUENTES or faltan:
        raise SystemExit('MONTAJE_INCOMPLETO: faltan %d fotogramas fuente (%s)'
                         % (len(faltan), ', '.join(faltan[:5])))
    print('ENCODE_MONTAJE: %d fotogramas de video con %d PNG distintos'
          % (len(pngs), len(set(pngs))))
print('ENCODE_ENTRADA: %d fotogramas desde %s' % (len(pngs), CARPETA))
libre = shutil.disk_usage(os.path.dirname(SALIDA) or '.').free
if libre < 1024 ** 3:
    raise SystemExit('ESPACIO_INSUFICIENTE: se conserva 1 GiB antes de codificar el MP4')

sc = bpy.context.scene
sc.render.fps = FPS
sc.render.fps_base = 1.0
if not (ANCHO and ALTO):
    img = bpy.data.images.load(os.path.join(CARPETA, pngs[0]))
    ANCHO, ALTO = img.size[0], img.size[1]
    bpy.data.images.remove(img)
sc.render.resolution_x, sc.render.resolution_y = ANCHO, ALTO
print(f'ENCODE_RESOLUCION: {ANCHO}x{ALTO} @ {FPS}fps')
sc.render.resolution_percentage = 100
sc.frame_start, sc.frame_end = 1, len(pngs)

if sc.sequence_editor:
    sc.sequence_editor_clear()
se = sc.sequence_editor_create()
# renombrado en Blender 5.x. Ojo: un colector vacio es falsy, asi que
# `getattr(...) or se.sequences` se iba a la rama vieja y reventaba.
tiras = se.strips if hasattr(se, 'strips') else se.sequences

tira = tiras.new_image(name='cine', filepath=os.path.join(CARPETA, pngs[0]),
                       channel=1, frame_start=1)
for nombre in pngs[1:]:
    tira.elements.append(nombre)

# Capa superior del titulo, si la pasada existe. Se alinea por el numero de
# fotograma impreso en el nombre del primer PNG (f_0060.png -> fotograma 60).
if OVER and os.path.isdir(OVER):
    ovs = sorted(glob.glob(os.path.join(OVER, '*.png')))
    if ovs:
        try:
            inicio = int(os.path.splitext(os.path.basename(ovs[0]))[0].split('_')[-1])
        except ValueError:
            inicio = 1
        if FUENTES is not None:
            # Una capa por fotograma de SALIDA: la de su PNG fuente, o una vacia
            # donde ningun texto existe (esos no se rindieron).
            vacio = os.path.join(OVER, 'vacio.png')
            imagen = bpy.data.images.new('capa_vacia', width=ANCHO, height=ALTO, alpha=True)
            imagen.generated_color = (0.0, 0.0, 0.0, 0.0)
            imagen.filepath_raw = vacio
            imagen.file_format = 'PNG'
            imagen.save()
            bpy.data.images.remove(imagen)
            hay = {os.path.basename(r) for r in ovs}
            capas = ['f_%04d.png' % CAPA.get(f, f) for f in FUENTES]
            ovs = [os.path.join(OVER, n if n in hay else 'vacio.png') for n in capas]
            inicio = 1
        capa = tiras.new_image(name='titulo', filepath=ovs[0], channel=2,
                               frame_start=inicio)
        for ruta in ovs[1:]:
            capa.elements.append(os.path.basename(ruta))
        capa.blend_type = 'ALPHA_OVER'
        print('ENCODE_CAPA: %d fotogramas de titulo desde %d'
              % (len(ovs), inicio))
    else:
        print('ENCODE_CAPA_VACIA: %s' % OVER)

# El cierre de marca, despues de un fundido a negro del video. Va en la misma
# pista, justo detras. `FIT` lo ajusta si el video es un borrador a menor
# resolucion: el cierre se rinde una vez, a la resolucion del formato.
n_cierre = 0
if CIERRE:
    cps = sorted(glob.glob(os.path.join(CIERRE, 'f_*.png')))
    if not cps:
        raise SystemExit('CIERRE_VACIO: no hay fotogramas en %s' % CIERRE)
    fin = len(pngs)
    tira.color_multiply = 1.0
    tira.keyframe_insert('color_multiply', frame=max(1, fin - FUNDIDO))
    tira.color_multiply = 0.0
    tira.keyframe_insert('color_multiply', frame=fin)
    cierre = tiras.new_image(name='cierre', filepath=cps[0], channel=1,
                             frame_start=fin + 1, fit_method='FIT')
    for ruta in cps[1:]:
        cierre.elements.append(os.path.basename(ruta))
    n_cierre = len(cps)
    sc.frame_end = fin + n_cierre
    print('ENCODE_CIERRE: %d fotogramas desde %s, tras %d de fundido'
          % (n_cierre, CIERRE, FUNDIDO))
total = len(pngs) + n_cierre

# Blender 5.x separo el tipo de medio del formato: hay que declarar VIDEO
# antes de que 'FFMPEG' aparezca siquiera en el enum de file_format.
ajustes = sc.render.image_settings
if hasattr(ajustes, 'media_type'):
    ajustes.media_type = 'VIDEO'
ajustes.file_format = 'FFMPEG'
ff = sc.render.ffmpeg
ff.format = 'MPEG4'
ff.codec = 'H264'
ff.constant_rate_factor = 'PERC_LOSSLESS'
ff.ffmpeg_preset = 'GOOD'
ff.gopsize = FPS
ff.audio_codec = 'NONE'
sc.render.filepath = SALIDA

bpy.ops.render.render(animation=True)

final = SALIDA
if not os.path.exists(final):   # Blender anade el rango de fotogramas al nombre
    cand = glob.glob(os.path.splitext(SALIDA)[0] + '*.mp4')
    if cand:
        final = cand[0]
        destino = SALIDA
        if os.path.exists(destino):
            os.remove(destino)
        os.rename(final, destino)
        final = destino
print('ENCODE_LISTO: %s (%.1f MB, %.2f s)'
      % (final, os.path.getsize(final) / 1e6, total / FPS))

# Verificacion de duracion: un encode muerto deja un contenedor valido pero
# vacio (paso con v4b: 1 fotograma de 360) y sin esto lo dariamos por bueno
# y encima borrariamos los PNG. Solo con la duracion correcta se limpia.
try:
    prueba = bpy.data.movieclips.load(final)
    n_frames = prueba.frame_duration
    bpy.data.movieclips.remove(prueba)
except Exception as e:
    raise SystemExit('ENCODE_SIN_VERIFICAR: no se pudo leer %s (%s)'
                     % (final, e))
if n_frames != total:
    raise SystemExit('ENCODE_MAL: %s trae %d fotogramas y la tira tenia %d'
                     % (final, n_frames, total))
print('ENCODE_VERIFICADO: %d fotogramas' % n_frames)

# El MP4 es el artefacto: los PNG intermedios ya no hacen falta (en 1080p son
# ~1.3 GB por pieza). Se borran aqui, tras un encode completo, para que valga
# en cualquier corrida y no solo en la tanda de produccion.sh.
if os.path.exists(final):
    for carpeta in (CARPETA, OVER):
        if carpeta and os.path.isdir(carpeta):
            shutil.rmtree(carpeta, ignore_errors=True)
            print('ENCODE_LIMPIEZA: %s' % carpeta)
