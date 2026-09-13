"""
Cuántas aguas se retiraron del sitio, y cuántas estaban bien coordinadas.

# Por qué existe

`services/docking/preparer.py` elimina TODAS las aguas cristalográficas (HOH,
WAT, DOD) antes de preparar el receptor. Es la práctica estándar en
acoplamiento generalista y **este módulo no la cambia**: sólo mide lo que se
tiró, para que el dossier pueda decirlo con números en vez de con una frase
genérica.

# Lo que la medición desaconseja

Una auditoría externa propuso conservar como «estructurales» las aguas con más
de tres puentes de hidrógeno al receptor. Se aplicó ese criterio a las 307
estructuras que viajan en el producto, contando sólo aguas dentro de la caja de
acoplamiento:

    receptores con estructura y caja      254
      con aguas dentro de la caja         254   (100 %)
      con al menos una de >=3 puentes     237   ( 93 %)

    aguas en la caja      mediana 30   máximo 122
    aguas de >=3 puentes  mediana  8   máximo  38

Un criterio que dispara en el 93 % de los receptores y selecciona una mediana
de ocho aguas por sitio no está identificando aguas estructurales: está
identificando aguas. Meter ocho moléculas en la caja de 4QA0 (38) o 5A2R (35)
no refina el acoplamiento — lo sustituye por otro protocolo, cambia toda
afinidad ya guardada e invalida la calibración por diana (`spearman_rho`,
`calibration_date`).

# El criterio que se pidió, medido

La conclusión anterior dejaba pendiente un criterio mejor: «enterramiento y
desplazabilidad por el ligando, no conteo de puentes». Se implementó
(`_medir_sitio`) y se aplicó a las 322 estructuras del catálogo que tienen aguas
dentro de su caja. Lo que dio:

                                          receptores    aguas por receptor
    criterio                              que disparan  mediana media  máx
    >=3 puentes (el de la auditoría)       303 (94 %)      8.0    9.8    38
    enterramiento >= 0.80                  317 (98 %)     15.0   19.5    94
    enterramiento >= 0.90                  301 (93 %)      8.0   13.0    69
    enterramiento >= 0.96                  288 (89 %)      7.0   10.6    50
    enterramiento >= 1.00 (encerrada)      272 (84 %)      5.0    7.3    37
    encerrada y >=3 puentes                253 (79 %)      3.0    4.3    19
    encerrada y >=4 puentes                230 (71 %)      2.0    2.3    12
    encerrada y >=5 puentes                159 (49 %)      0.0    0.9     6

**La desplazabilidad, tal como se propuso, no informa de nada.** Se midió como
la distancia del agua al átomo pesado más cercano del receptor: si cabe ahí un
carbono, el ligando puede ocupar el sitio. Sobre las 11 820 aguas de caja del
catálogo esa distancia se reparte así:

    percentil  1    2.22 Å        percentil 75    3.08 Å
    percentil 25    2.70 Å        percentil 95    3.81 Å
    percentil 50    2.83 Å        percentil 99    4.29 Å

El 80 % está por debajo de 3.2 Å — y no puede ser de otra forma: un agua
cristalográfica está, por definición, formando puentes a 2.7-3.0 Å. La medida
diría «no desplazable» de cuatro de cada cinco aguas, así que no separa nada. Un
carbono de ligando tampoco necesita el punto exacto del oxígeno: se acomoda
medio ángstrom más allá. La proximidad al receptor no es desplazabilidad.

**El enterramiento solo tampoco basta.** Ni exigiendo encierro total —ninguna de
las 26 direcciones abierta dentro de 8 Å— baja del 84 % de receptores, con
mediana de cinco aguas. Es el mismo problema que el conteo de puentes:
identifica aguas, no aguas estructurales.

**Lo único que llega a una escala defendible es el encierro con coordinación
fuerte**: encerrada y con cinco o más contactos deja 0,9 aguas de media, ninguna
en la mitad de los receptores y como mucho seis. Ese es el perfil que uno espera
de un agua estructural de verdad.

# Y aun así, esto sigue sin aplicarse

Que un criterio seleccione un conjunto creíble no demuestra que conservarlo
mejore el acoplamiento. Falta la medición contra redocking que ya se pedía, y
sigue en pie el coste: conservar aguas cambia toda afinidad ya guardada e
invalida la calibración por diana (`spearman_rho`, `calibration_date`).

Lo que este archivo hace es **medir y declarar**. `candidata_a_conservar`
implementa el corte que quedó en pie para que se pueda probar, y nada del
acoplamiento lo consulta.

# El criterio de coordinación

Un oxígeno de agua cuenta un puente por cada N u O del receptor a 3.5 Å o menos.
Es el corte geométrico habitual, sin ángulo: no hay hidrógenos explícitos en el
PDB depositado, y estimar el ángulo sin ellos es exactamente el error que ya se
corrigió en `services/interactions/analyzer.py`. Aquí se cuenta contacto
donador-aceptor, y se llama por su nombre.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: Distancia máxima O(agua)···N/O(receptor) para contar un puente, en Å.
CORTE_PUENTE_A: float = 3.5

#: A partir de cuántos puentes se considera un agua «bien coordinada». No es un
#: umbral de conservación: es el que usó la auditoría, y se conserva para que el
#: número que se declara sea comparable con el suyo.
PUENTES_BIEN_COORDINADA: int = 3


#: Radio en el que se busca el receptor para decidir si un agua está enterrada.
RADIO_ENTERRAMIENTO_A: float = 8.0

#: Semiángulo del cono que da por «tapada» una dirección. Con 26 direcciones y
#: 30°, los conos cubren la esfera con solape: una dirección tapada significa
#: que hay receptor por ahí, no que haya un átomo exactamente en esa recta.
SEMIANGULO_CONO_GRADOS: float = 30.0

#: Enterramiento a partir del cual el agua se considera encerrada: **todas** las
#: direcciones tapadas. El barrido del encabezado explica por qué no vale 0.80.
ENTERRAMIENTO_ENCERRADA: float = 1.00

#: Contactos exigidos, además del encierro, para llamar estructural a un agua.
#: Cinco, no tres: con tres el corte sigue disparando en el 84 % de los receptores.
PUENTES_ESTRUCTURAL: int = 5

#: Las 26 direcciones del cubo (caras, aristas y vértices). No es una
#: distribución equiespaciada de la esfera, pero es determinista, no necesita
#: dependencias y basta para separar «tapada por todos lados» de «abierta al
#: disolvente», que es la única distinción que se le pide.
_DIRECCIONES: tuple[tuple[float, float, float], ...] = tuple(
    (dx / (dx * dx + dy * dy + dz * dz) ** 0.5,
     dy / (dx * dx + dy * dy + dz * dz) ** 0.5,
     dz / (dx * dx + dy * dy + dz * dz) ** 0.5)
    for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1)
    if (dx, dy, dz) != (0, 0, 0)
)


@dataclass(frozen=True)
class AguaMedida:
    """Una molécula de agua de la caja, con lo que se midió de su sitio."""

    #: Coordenadas del oxígeno.
    posicion: tuple[float, float, float]
    #: Contactos donador-aceptor con el receptor, dentro de `CORTE_PUENTE_A`.
    puentes: int
    #: Fracción de las 26 direcciones tapadas por receptor. 1.0 = encerrada.
    enterramiento: float
    #: Distancia al átomo pesado más cercano del receptor, en Å.
    hueco_a: float

    @property
    def encerrada(self) -> bool:
        """Sin una sola dirección abierta al disolvente dentro de 8 Å."""
        return self.enterramiento >= ENTERRAMIENTO_ENCERRADA

    @property
    def candidata_a_conservar(self) -> bool:
        """El único corte que la medición sobre el catálogo deja en pie.

        Encerrada **y** con al menos `PUENTES_ESTRUCTURAL` contactos. Ver el
        encabezado del módulo para el barrido completo, y por qué los demás
        cortes —incluida la desplazabilidad que se propuso— se descartaron.

        NO SE APLICA. Es la candidata a medir contra redocking, no una política.
        """
        return self.encerrada and self.puentes >= PUENTES_ESTRUCTURAL


@dataclass(frozen=True)
class CensoDeAguas:
    """Lo que había en el sitio antes de retirarlo."""

    #: Aguas en el archivo depositado, en toda la estructura.
    en_la_estructura: int
    #: Aguas cuyo oxígeno cae dentro de la caja de acoplamiento.
    en_la_caja: int
    #: De las anteriores, cuántas alcanzan `PUENTES_BIEN_COORDINADA`.
    bien_coordinadas: int
    #: Puentes del agua mejor coordinada de la caja. 0 si no había ninguna.
    max_puentes: int
    #: Cada agua de la caja con su enterramiento y su hueco. Vacío cuando no se
    #: pidió la medición cara (`medir_sitio=False`, que es el camino caliente).
    aguas: tuple[AguaMedida, ...] = ()

    @property
    def candidatas_a_conservar(self) -> tuple[AguaMedida, ...]:
        """Las que pasarían el criterio de enterramiento + desplazabilidad."""
        return tuple(a for a in self.aguas if a.candidata_a_conservar)

    @property
    def hay_algo_que_declarar(self) -> bool:
        return self.en_la_caja > 0


def _coordenadas(linea: str) -> tuple[float, float, float] | None:
    try:
        return (float(linea[30:38]), float(linea[38:46]), float(linea[46:54]))
    except (ValueError, IndexError):
        return None


def _medir_sitio(
    agua: tuple[float, float, float],
    pesados: list[tuple[float, float, float]],
    puentes: int,
) -> AguaMedida:
    """Enterramiento y hueco de un agua concreta.

    ENTERRAMIENTO. Se toman las 26 direcciones del cubo y se marca cada una
    como tapada si hay algún átomo pesado del receptor dentro de
    `RADIO_ENTERRAMIENTO_A` y a menos de `SEMIANGULO_CONO_GRADOS` de ella. La
    fracción tapada va de 0 (expuesta al disolvente por todos lados) a 1
    (encerrada). Es una medida direccional, no un conteo de vecinos: dos aguas
    con los mismos 80 vecinos pueden estar una en una cavidad cerrada y otra en
    un surco abierto, y el conteo no las distingue.

    HUECO. Distancia al átomo pesado más cercano. Dice si en ese punto cabría un
    átomo del ligando, que es la otra mitad de la pregunta: un agua que ocupa
    sitio que el ligando puede usar no se conserva aunque esté enterrada.
    """
    coseno_limite = math.cos(math.radians(SEMIANGULO_CONO_GRADOS))
    radio2 = RADIO_ENTERRAMIENTO_A * RADIO_ENTERRAMIENTO_A

    tapadas = [False] * len(_DIRECCIONES)
    mas_cerca2 = float("inf")

    for atomo in pesados:
        dx = atomo[0] - agua[0]
        if dx > RADIO_ENTERRAMIENTO_A or dx < -RADIO_ENTERRAMIENTO_A:
            continue
        dy = atomo[1] - agua[1]
        if dy > RADIO_ENTERRAMIENTO_A or dy < -RADIO_ENTERRAMIENTO_A:
            continue
        dz = atomo[2] - agua[2]
        if dz > RADIO_ENTERRAMIENTO_A or dz < -RADIO_ENTERRAMIENTO_A:
            continue
        d2 = dx * dx + dy * dy + dz * dz
        if d2 > radio2 or d2 == 0.0:
            continue
        if d2 < mas_cerca2:
            mas_cerca2 = d2
        norma = math.sqrt(d2)
        ux, uy, uz = dx / norma, dy / norma, dz / norma
        for i, (vx, vy, vz) in enumerate(_DIRECCIONES):
            if not tapadas[i] and ux * vx + uy * vy + uz * vz >= coseno_limite:
                tapadas[i] = True

    return AguaMedida(
        posicion=agua,
        puentes=puentes,
        enterramiento=round(sum(tapadas) / len(_DIRECCIONES), 3),
        hueco_a=round(math.sqrt(mas_cerca2), 2) if mas_cerca2 < float("inf") else 99.0,
    )


def censar_aguas(
    contenido_pdb: str,
    centro: tuple[float, float, float],
    tamano: tuple[float, float, float],
    medir_sitio: bool = False,
) -> CensoDeAguas:
    """Cuenta las aguas del sitio sobre el PDB **con** aguas.

    `contenido_pdb` debe ser el depositado o el ensamblaje biológico, antes de
    filtrar. Con un PDB ya preparado el censo saldrá en cero, que es correcto:
    ahí ya no hay aguas.

    `medir_sitio` añade enterramiento y hueco por agua. Cuesta del orden de un
    barrido más sobre los átomos cercanos a cada agua de la caja —decenas de ms
    en un receptor típico— y no hace falta para la frase que se declara, así que
    va apagado en el camino del acoplamiento y encendido cuando se estudia la
    política de conservación.
    """
    aguas: list[tuple[float, float, float]] = []
    aceptores: list[tuple[float, float, float]] = []
    pesados: list[tuple[float, float, float]] = []

    for linea in contenido_pdb.splitlines():
        if not linea.startswith(("ATOM  ", "HETATM")):
            continue
        punto = _coordenadas(linea)
        if punto is None:
            continue
        residuo = linea[17:20].strip().upper()
        elemento = (linea[76:78].strip() or linea[12:16].strip()[:1]).upper()
        if residuo in ("HOH", "WAT", "DOD"):
            if elemento.startswith("O"):
                aguas.append(punto)
            continue
        if elemento in ("N", "O"):
            aceptores.append(punto)
        # Todo lo que no es hidrógeno cuenta para el enterramiento y el hueco:
        # un anillo aromático tapa una dirección igual que un nitrógeno, aunque
        # no forme puente.
        if elemento and not elemento.startswith("H") and elemento != "D":
            pesados.append(punto)

    if not aguas:
        return CensoDeAguas(0, 0, 0, 0)

    mitad = (tamano[0] / 2.0, tamano[1] / 2.0, tamano[2] / 2.0)
    en_caja = [
        agua
        for agua in aguas
        if all(abs(agua[eje] - centro[eje]) <= mitad[eje] for eje in range(3))
    ]
    if not en_caja:
        return CensoDeAguas(len(aguas), 0, 0, 0)

    corte2 = CORTE_PUENTE_A * CORTE_PUENTE_A
    bien = 0
    maximo = 0
    medidas: list[AguaMedida] = []
    for agua in en_caja:
        puentes = 0
        for aceptor in aceptores:
            # Descarte barato por eje antes de la distancia: sin esto son
            # decenas de miles de raíces cuadradas por receptor, en el camino
            # caliente del acoplamiento.
            dx = aceptor[0] - agua[0]
            if dx > CORTE_PUENTE_A or dx < -CORTE_PUENTE_A:
                continue
            dy = aceptor[1] - agua[1]
            if dy > CORTE_PUENTE_A or dy < -CORTE_PUENTE_A:
                continue
            dz = aceptor[2] - agua[2]
            if dz > CORTE_PUENTE_A or dz < -CORTE_PUENTE_A:
                continue
            if dx * dx + dy * dy + dz * dz <= corte2:
                puentes += 1
        maximo = max(maximo, puentes)
        if puentes >= PUENTES_BIEN_COORDINADA:
            bien += 1
        if medir_sitio:
            medidas.append(_medir_sitio(agua, pesados, puentes))

    return CensoDeAguas(len(aguas), len(en_caja), bien, maximo, tuple(medidas))


# ── Caché del censo, por receptor y caja ────────────────────────────────────
#
# EL COSTE QUE QUITA. `vina_service` llamaba a `censar_aguas` en cada
# acoplamiento, y antes leía el PDB depositado entero desde disco para
# alimentarlo. El cálculo son unos 4 ms; la lectura es E/S por corrida, sobre un
# archivo de cientos de KB, en el camino caliente.
#
# El resultado es determinista en `(pdb_id, centro, tamaño)`: mismo receptor y
# misma caja, mismo censo. Así que se guarda.
#
# LO QUE LA CACHÉ NO PUEDE SABER es si el archivo del receptor cambió por
# debajo. Por eso `invalidar_censo` existe y por eso la clave lleva el `pdb_id`:
# quien reescriba una estructura tiene que llamarla. En una instalación de
# escritorio, con el catálogo empaquetado, eso ocurre al reingerir un receptor.
_CACHE: dict[tuple, CensoDeAguas] = {}

#: Cota de entradas. Con 380 receptores en el catálogo y una caja por receptor,
#: 512 cubre el catálogo entero; el desalojo es sólo para sesiones que exploren
#: cajas personalizadas.
_CACHE_MAXIMO: int = 512


def _clave(pdb_id: str, centro, tamano, medir_sitio: bool) -> tuple:
    # Se redondea a la milésima de ángstrom: dos cajas que difieren en 1e-9 no
    # dan censos distintos, y sin redondeo el ruido de coma flotante convierte
    # cada corrida en una clave nueva y la caché nunca acierta.
    return (
        pdb_id,
        tuple(round(float(v), 3) for v in centro),
        tuple(round(float(v), 3) for v in tamano),
        medir_sitio,
    )


def censo_en_cache(pdb_id: str, centro, tamano, medir_sitio: bool = False):
    """El censo ya calculado para este receptor y caja, o `None`.

    Se consulta ANTES de leer el archivo: ése es el ahorro. Devolver `None` es
    la señal de que hay que leer el PDB y llamar a `censar_aguas`.
    """
    return _CACHE.get(_clave(pdb_id, centro, tamano, medir_sitio))


def guardar_censo(pdb_id: str, centro, tamano, censo: CensoDeAguas,
                  medir_sitio: bool = False) -> None:
    """Guarda el censo. Desaloja la entrada más antigua si se llenó."""
    if len(_CACHE) >= _CACHE_MAXIMO:
        del _CACHE[next(iter(_CACHE))]
    _CACHE[_clave(pdb_id, centro, tamano, medir_sitio)] = censo


def invalidar_censo(pdb_id: str | None = None) -> int:
    """Olvida lo guardado para un receptor, o todo si no se dice cuál.

    Hay que llamarla cuando la estructura depositada de un receptor se
    reescribe: la caché no puede enterarse sola, y un censo viejo describiría
    unas aguas que ya no están en el archivo.
    """
    global _CACHE
    if pdb_id is None:
        cuantas = len(_CACHE)
        _CACHE = {}
        return cuantas
    sobran = [k for k in _CACHE if k[0] == pdb_id]
    for k in sobran:
        del _CACHE[k]
    return len(sobran)


def describir_censo(censo: CensoDeAguas) -> str:
    """La frase que se guarda con la corrida. Mide, no advierte de más."""
    if not censo.hay_algo_que_declarar:
        return (
            "Preparación en condición desolvatada: la estructura depositada no "
            "tenía aguas cristalográficas dentro de la caja de acoplamiento, así "
            "que el sitio no perdió ninguna al prepararlo."
        )
    return (
        f"Preparación en condición desolvatada: se retiraron {censo.en_la_caja} "
        f"aguas cristalográficas de la caja de acoplamiento, "
        f"{censo.bien_coordinadas} de ellas con {PUENTES_BIEN_COORDINADA} o más "
        f"contactos a menos de {CORTE_PUENTE_A:.1f} Å con el receptor "
        f"(la mejor coordinada, {censo.max_puentes}). Si alguna de esas aguas "
        f"forma parte del reconocimiento en esta diana —la catalítica de la "
        f"proteasa del VIH-1, la red de la bisagra en varias quinasas—, los "
        f"contactos de esta corrida no la incluyen."
    )
