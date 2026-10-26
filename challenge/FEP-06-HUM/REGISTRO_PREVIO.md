# FEP-06-HUM — registro previo (2026-10-25)

Escrito y commiteado **antes** de generar un solo paquete y antes de publicar el reto. Decisión del propietario (2026-10-25):
repetir la revisión ciega de FEP-06-PRE y FEP-06-PRE-2 con **investigadores humanos**, como reto público, con un paquete de
control que tiene un problema conocido.

## 1. Qué se pregunta

Si un investigador que prepara cálculos de energía libre, con sólo el paquete de una corrida que exporta MolDesign, encuentra
algo de la estructura de origen que el paquete pierde **sin declararlo**, y si el producto se atribuye alguna vez un estado
de transferencia que no se sostiene.

## 2. Qué no es

- **No es FEP-06.** Nadie reconstruye ni ejecuta un cálculo. Quien quiera hacerlo se documenta aparte y no decide.
- **No es ciego para el producto:** los diez sistemas los eligió Claude sabiendo qué declara el producto en cada uno.
- **No certifica** compatibilidad con FEP+, OpenFE ni ningún otro protocolo.

## 3. Lo que se fija

- **La clave** (`clave-fep06hum-2026-10-25.md`, fuera del repositorio) tiene SHA-256
  `332d187d8c75add85212ebf6482709bd272cecfdc492b90124d45d4c6aa6dabc`. Dice qué sistema es cada paquete, qué hechos
  debe citar una revisión, cuál es el control y la lista de asignación. Se publica entera al cerrar la ronda.
- **Diez paquetes**, exportados en inglés por la API del producto en una cápsula aislada, con la configuración por defecto de
  un caso (Vina 1.2.7, exhaustividad 8, 9 poses, semilla 42). El generador (`scripts/fep06hum/generar_paquetes.py`) queda
  fuera del repositorio público mientras la ronda esté abierta, porque nombra el control.
- **Un paquete de control con un problema conocido** que el producto no declara, medido antes en un experimento sellado. El
  paquete es el que exporta el producto: no se altera ningún fichero después de exportar. El reto público dice que existe,
  sin decir cuál.
- **Las 14 necesidades** de FEP-06-PRE (N01–N14) y los tres veredictos: READY_TO_PREPARE, PREPARABLE_WITH_QUESTIONS y
  NOT_PREPARABLE.

## 4. Decisión

- **Pérdida silenciosa confirmada:** algo del origen que el paquete no trae ni declara, señalado por al menos un revisor
  admitido y verificado por Claude contra el origen y `audit.json`. El problema conocido del control no cuenta como pérdida.
- **Control de sensibilidad:** el problema conocido debe aparecer en al menos la mitad de las revisiones admitidas de su
  paquete. Si no, **INCONCLUSIVE**: un panel que no ve un problema conocido no dice nada con su silencio.
- **NO_GO:** una o más pérdidas silenciosas confirmadas fuera del control, o un estado TRANSFERIBLE/READY del producto
  demostrado falso.
- **GO:** ninguna de las dos, el control detectado y la mediana de falsas alarmas por revisión del paquete limpio ≤ 1.
- **INCONCLUSIVE** en otro caso, con menos de 3 revisores admitidos, o con menos de 2 revisiones admitidas del control.
- **Cierre:** el 2026-12-06 o al llegar a 20 revisiones admitidas, lo que ocurra antes.

## 5. Admisión y crédito

- Cuenta la revisión que llega por la plantilla de issue del reto (veredicto, tabla de las 14 necesidades y pérdidas con
  fichero y línea). El revisor declara qué consultó además del paquete y si usó un modelo de lenguaje; una revisión redactada
  por un modelo no cuenta, una asistida sí y se informa aparte. Una persona cuenta una vez por paquete.
- Cada revisor recibe dos paquetes por orden de llegada, según la lista de la clave.
- Crédito: los revisores admitidos aparecen con su nombre, o el que elijan, en «Acerca de MolDesign · Colaboradores» y en el
  informe público de FEP-06-HUM, salga lo que salga.

Toda desviación se anota en `DESVIACIONES.md` (append-only) antes de leer ninguna revisión.
