"""FORMATO: vertical para Reels, TikTok y Shorts.

9:16, corto, y con rotulos de PANTALLA en vez de etiquetas ancladas: el gancho
tiene que existir en el primer segundo y sobrevivir al movimiento, y una
etiqueta anclada solo puede aparecer con la camara quieta.

El texto va al doble de tamano: esto se ve en un movil, no en un monitor.
"""
from variables.formato import Formato

FORMATO = Formato(
    nombre="social_vertical",
    descripcion="9:16 de 12 s de escena (mas las pausas de lectura) con rotulos de pantalla. ~10 min de render.",
    ancho=1080, alto=1920, fps=30, segundos=12.0,
    # 64 muestras y sombras a 0.5, medido en 016 (1EI1) sobre el mismo .blend:
    # 1550 -> 615 s por video. La diferencia con 96/1.0 es solo el patron del
    # ruido de dithering del fantasma, que ya existe a 96. En el plano general
    # el cambio no se distingue (PSNR 60 dB); el ahorro esta en el primer plano.
    muestras=64, escala_render=100, escala_sombras=0.5,
    bucle=False, etiquetas_3d=True, rotulos_pantalla=True,
    desenfoque_movimiento=True, profundidad_de_campo=True,
    # La firma va al final (cierre 3D de marca), no quemada arriba durante
    # todo el video: el sello de texto competia con el titulo y las etiquetas.
    sello_procedencia=False, cierre_s=3.6, escala_texto=2.0,
    # Ancladas grandes y fuera del sitio: el reparto (`rotulos.colocar`) no
    # acepta solapes ni cruces; si no caben, achica o rotula menos.
    escala_etiquetas_3d=3.2,
)
