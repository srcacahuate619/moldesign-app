# MolDesign

[![License: PolyForm Noncommercial 1.0.0](https://img.shields.io/badge/license-PolyForm%20Noncommercial-blue.svg)](LICENSE)
[![Commercial license](https://img.shields.io/badge/commercial-license%20required-orange.svg)](COMMERCIAL-LICENSE.md)

**MolDesign es una herramienta desktop con código fuente público para auditar, producir,
organizar y transferir evidencia computacional estructural en etapas iniciales
de investigación.**

No intenta responder «¿esta molécula será un buen fármaco?». Su contrato es más
concreto:

> ¿Qué evidencia produjo esta corrida, con qué estructura y configuración, qué
> controles superó, qué incertidumbre permanece y qué sería justificable hacer
> después?

## Dónde encaja

Los cálculos costosos parten de decisiones que a menudo quedan fuera del archivo:
qué unidad biológica se usó, qué cadenas y aguas se conservaron, cómo se trataron
huecos, metales, protonación, tautomería, estereoquímica y poses iniciales.
MolDesign aspira a ser la **capa local de confianza y transferencia** que vuelve
esas decisiones explícitas antes de entregar el sistema a otro método o equipo.

```text
hipótesis estructural
        ↓
MolDesign: audita, documenta y puede bloquear
        ↓
paquete reproducible + incertidumbres declaradas
        ↓
FEP+, OpenFE u otro cálculo externo
```

El primer caso de uso de alto valor es la preparación auditable para flujos de
energía libre. **MolDesign no ejecuta FEP**, y la versión actual todavía no está
verificada como compatible con FEP+ ni con OpenFE. Hoy produce evidencia
estructural con Vina; la exportación reproducible y la reconstrucción del paquete
por un tercero forman parte de la hoja de ruta.

Puede ser especialmente útil en transferencias entre una CRO y su cliente, un
equipo de biología estructural y uno de simulación, una core facility y un
laboratorio, o una biotech pequeña y su proveedor de FEP. No compite por ofrecer
más motores: su valor es mostrar qué se decidió, qué sigue ambiguo y cuándo aún
no está justificado pagar por el siguiente cálculo.

## MVP funcional

El flujo principal es local y orientado a casos:

1. Crear o abrir un caso de estudio.
2. Seleccionar una proteína del catálogo o cargar una estructura propia.
3. Declarar ligandos/hipótesis y ejecutar el preflight reproducible.
4. Evaluar con AutoDock Vina y las capas científicas disponibles.
5. Revisar afinidad, poses, aplicabilidad, advertencias, abstenciones y
   procedencia sin interpretar scores como probabilidades.
6. Conservar historial y evidencia en el directorio del caso.

El runtime desktop incluye Python científico, FastAPI, Vina, xTB, rescoring,
selector de pose y estructuras curadas. Los pesos de intérprete LLM y servicios
remotos son opcionales y no participan del camino crítico.

## Estado publicable de cada pipeline

Los tres protocolos están implementados y ejecutan. Eso no los hace
equivalentes: lo que cada uno permite **afirmar** es distinto, y esta tabla es
la fuente. Ante cualquier discrepancia con otro documento, manda ésta.

| Pipeline | Estado publicable |
|---|---|
| **M4 — molécula pequeña** | Operativo como evidencia exploratoria; los modelos declaran aplicabilidad limitada y se abstienen fuera de su dominio |
| **M5-Zn — metaloenzimas** | Infraestructura operativa; **ningún perfil positivo científicamente liberable**. Ver [corrigendum](docs/77_CORRIGENDUM_SITIO_DEL_BENCHMARK_M5_ZN.md) |
| **Péptidos — ESMFold + Vina** | Transferencia implementada y verificada; el docking sigue siendo **científicamente experimental**. Ver [decisión](docs/76_DECISION_TRANSFERENCIA_ESMFOLD_A_LIGANDO_V1.md) |

Que una prueba pase demuestra que el programa hace lo especificado. La validez
científica exige benchmark, controles, dominio de aplicabilidad y validación
externa, y se declara por separado.

## Qué MolDesign no afirma

- Docking no demuestra unión, eficacia ni seguridad.
- Un score no es probabilidad de éxito experimental.
- La ausencia de una alerta no prueba ausencia de artefactos.
- La interpretación final y la validación experimental corresponden al
  laboratorio.

## Qué produce hoy cada pipeline

Hay tres protocolos, y **sólo uno entrega un número**. No es un defecto oculto:
los otros dos se abstienen a propósito y dicen por qué. Conviene saberlo antes
de instalar, para no leer una abstención como un fallo.

| Protocolo | Qué hace hoy |
|---|---|
| **M4** — molécula pequeña | **Funciona de extremo a extremo.** Vina produce y puntúa poses; XGBoost reordena. Es el camino que sostiene el producto. |
| **M5-Zn** — metaloenzimas | **Ningún perfil produce `VALIDATED`.** Existe para tres estructuras (3DC3, 1GKC, 1O86). MMP9 y ACE están en cuarentena desde el corrigendum del 2026-09-04: sus benchmarks no acoplaron en el sitio del zinc catalítico. CA2/3DC3 exige la señal GNN-D, que **no tiene productor en producción**, así que devuelve `NOT_EVALUATED_MISSING_COMPONENT` nombrando el componente que falta. |
| **Péptidos** | **Se abstiene sin los pesos de ESMFold** (8,4 GB, descarga bajo demanda) y lo declara pidiendo la descarga. Con el sidecar disponible corre, pero su ciencia **no está validada**: está probado que carga y sirve poses, no que las poses sean buenas. |

Que un protocolo se abstenga con el motivo escrito es el comportamiento
correcto de este producto —la abstención es una salida válida, no un error— pero
no es lo mismo que funcionar. Ver
[`docs/77_CORRIGENDUM_SITIO_DEL_BENCHMARK_M5_ZN.md`](docs/77_CORRIGENDUM_SITIO_DEL_BENCHMARK_M5_ZN.md)
y `backend/services/pipeline/protocols/m5/ejecucion.py`, que lo dice en su
propia cabecera.

## Instalar en Windows

El release candidate x64 se genera como instalador NSIS. Requisitos prácticos:

- Windows 10/11 x64;
- 4 GB libres en disco (instalación actual: ~1.85 GiB);
- 16 GB de RAM recomendados;
- WebView2; el instalador puede requerir internet si el runtime no existe.

La receta de release y el checksum del artefacto validado están en
[docs/55_MVP_DESKTOP_RELEASE.md](docs/55_MVP_DESKTOP_RELEASE.md).

> El instalador local actual no está firmado digitalmente. Es apto para pruebas
> controladas; la firma Authenticode es obligatoria antes de distribución
> comercial pública.

## Desarrollo

> **Auditar o reproducir desde un fork:** [CONTRIBUTING.md](CONTRIBUTING.md) §2-§4 reúne los
> comandos exactos de la CI, el aprovisionamiento del runtime, el build y la
> verificación de los 167 experimentos sellados (`python scripts/validar_sellos.py --check`).

### Un clon no basta: hay que aprovisionar el árbol

`git clone` trae el código, los manifiestos, los hashes y las estructuras
curadas. **No trae** el intérprete embebido, los motores nativos ni los pesos
entrenados: son 2,2 GB que se distribuyen aparte. Sin ellos no arranca ni
`tauri dev`, porque el contenedor Rust exige `python-embed/python.exe` también
en desarrollo.

Lo primero, siempre, es preguntar qué falta:

    python scripts/bootstrap_dev_tree.py --check

Dice pieza por pieza qué falta, si bloquea o sólo degrada, y de dónde sale cada
una. No escribe nada y no necesita red. Para aprovisionarlo automáticamente:

    python scripts/bootstrap_dev_tree.py --fetch

El runtime base se aprovisiona por separado en desarrollo —fijado por revisión
inmutable y SHA-256 en el recibo del runtime, y verificado antes de extraer—.
La aplicación instalada no descarga ese runtime: ya viaja dentro del bundle.
Open Babel se materializa como programa externo sólo durante el staging de la
máquina de build; los usuarios finales reciben el binario verificado. Los
módulos pesados de Qwen y ESMFold sí son descargas opcionales del launcher.

Ese archivo se reconstruye desde este repositorio:

    python scripts/build_base_archive.py            # lo genera
    python scripts/build_base_archive.py --check    # ¿coincide con el publicado?

y la lista exacta de lo que hay dentro del intérprete distribuido vive en
[`backend/requirements-embed.lock.txt`](backend/requirements-embed.lock.txt),
medida sobre el propio `python-embed`, no resuelta contra el entorno de quien
compila.

> `backend/requirements-desktop.lock.txt` describe otra cosa: el entorno de
> desarrollo con el Python del sistema. No sirve para reconstruir el runtime
> distribuido, y su cabecera lo dice.

### Construir

Frontend:

    cd frontend
    npm ci
    npm run test:run
    npm run build:desktop

Aplicación desktop en desarrollo:

    cd frontend
    npx tauri dev

Instalador autocontenido, con el árbol ya aprovisionado:

    cd frontend
    npm run tauri:build

`beforeBuildCommand` de `src-tauri/tauri.conf.json` encadena quince puertas
(la lista completa está en `AGENTS.md`, «Construir») y Tauri las ejecuta solo. Las que gobiernan el orden:

    check:openbabel-fuente   `tools/openbabel/` coincide con su manifiesto y
                             convierte una molécula de verdad
    stage:desktop            copia backend, Python, rescoring y herramientas a
                             src-tauri/resources/ (artefacto de build: se borra
                             y se regenera entero en cada pasada)
    check:openbabel          la frontera GPL, medida SOBRE EL BUNDLE staged
    verify:desktop-runtime   comprueba el runtime staged antes de empaquetar
    check:dossier-embebido   el dossier del runtime embebido coincide con el de
                             desarrollo

**El orden no es opcional.** `resources/` no está versionado, así que un árbol
de trabajo puede tener un staging viejo. Empaquetar sin re-stagear produce un
instalador con un backend atrasado — y el fallo es silencioso: las etapas del
pipeline se importan dentro de `try/except` para que su fallo no tumbe un
docking terminado, de modo que un módulo ausente degrada a `None` sin error. La
app arrancaría, pasaría `/health` y produciría evaluaciones sin validación
física ni selector de pose.

`verify:desktop-runtime` lo comprueba explícitamente: compara el backend staged
contra el del repositorio archivo por archivo, y verifica que las dependencias
científicas declaradas en `requirements.txt` estén realmente en el Python
empaquetado. También bloquea secretos y estado local, verifica hashes, importa
el stack científico, ejecuta Vina, arranca FastAPI y valida `/health`.

Antes de stagear, cierra `llama-server.exe` y cualquier backend en marcha: un
`.dll` cargado no se puede reemplazar en Windows. `stage:desktop` lo detecta y
aborta **sin** borrar el staging anterior.

## Documentación clave

- [Mapa de alineación del producto](docs/53_MAPA_ALINEACION_PRODUCTO.md).
- [Roadmap científico/producto](docs/50_ROADMAP.md).
- [Limitaciones científicas](docs/19_LIMITATIONS.md).
- [Arquitectura desktop](docs/ARCHITECTURE_DESKTOP.md).
- [Release, instalación y evidencia del MVP](docs/55_MVP_DESKTOP_RELEASE.md).

## Licencias

- Código y modelos propios ligeros: PolyForm Noncommercial 1.0.0 — [LICENSE](LICENSE) y [LICENSE-MODELS](LICENSE-MODELS).
- Uso comercial: requiere un acuerdo escrito separado — [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md).
- MolDesign es *source-available*, no software de código abierto según la definición OSI.
- Dependencias binarias: sus licencias respectivas, incluidas en los
  componentes distribuidos cuando corresponda.

## Contribuir

Consulta [CONTRIBUTING.md](CONTRIBUTING.md). Se requiere CLA antes de integrar
la primera contribución.
