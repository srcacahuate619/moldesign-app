# MolDesign — guía local de build y diagnóstico

Este documento reemplaza la receta histórica de julio de 2026. El instalador
debe construirse con el flujo declarado por Tauri; no se debe desactivar el
bundle, copiar un ejecutable a mano ni ejecutar un cargo build como sustituto
del build de escritorio.

## Requisitos

- Windows x64, Node.js 24.20.x y npm 11.19.x.
- Python 3.11 con el runtime embebido aprovisionado en python-embed/.
- Rust estable con rustfmt y clippy.
- Espacio suficiente para el runtime, los recursos curados y el staging.

Un clon limpio no contiene el runtime ni los pesos grandes. Comprobarlo sin
escribir nada:

    python scripts/bootstrap_dev_tree.py --check

El aprovisionamiento de desarrollo, cuando el runtime base esté publicado y
se haya aceptado su licencia, se hace con:

    python scripts/bootstrap_dev_tree.py --fetch

La aplicación instalada no ejecuta ese script: el runtime de producción viaja
dentro del instalador. Los pesos de Qwen y ESMFold son módulos opcionales y se
descargan desde la interfaz bajo demanda, siempre con SHA-256.

## Verificación antes de build

Desde la raíz:

    python scripts/generate_sbom.py --check --permitir-runtime-ausente
    python scripts/check_model_license_boundary.py --check
    python scripts/check_openbabel_boundary.py
    python scripts/verify_release_source_offer.py --check

Desde frontend/:

    npm ci
    npm run typecheck
    npm run test:run
    npm run smoke:prod

Las pruebas que requieren runtime, pesos o Open Babel se omiten sólo cuando
declaran el motivo; una omisión no es un resultado científico positivo.

## Build de escritorio

Desde frontend/:

    npm run tauri:build

La configuración de tauri.conf.json encadena las puertas de CSP, manifiestos,
goldens, staging del runtime, frontera Open Babel, runtime embebido, dossier,
export estático y ausencia de URLs remotas. No edites temporalmente esa cadena
para obtener un instalador.

La salida se sella con SHA-256 y release-manifest.json. El instalador actual
no tiene firma Authenticode; el hash y el manifiesto son la única prueba de
integridad hasta comprar un certificado.

## Diagnóstico

El backend se resuelve desde resources/ en producción y arranca en un puerto
libre entre 8000 y 8019. El frontend debe usar la dirección entregada por
ensure_backend; nunca asumir el puerto 8000.

Los logs se escriben en el directorio de logs de Tauri. El runtime instalado
es de sólo lectura: no debe recibir bases de usuario, logs ni bytecode.

Open Babel viaja como programa externo GPL-2.0-only en tools/openbabel/. No se
importa desde Python ni se resuelve por PATH. El adaptador verifica versión y
hash antes de invocarlo. Vina es el motor de docking y ESMFold sólo produce
estructuras de péptidos; ninguna de las dos afirmaciones convierte el producto
en un predictor de actividad.

## Alcance científico

MolDesign produce evidencia estructural, controles, aplicabilidad y
abstenciones. No ejecuta FEP ni sustituye validación experimental. La ciencia
de ESMFold está validada como carga y transferencia estructural, no como
exactitud de poses. M5-Zn mantiene sus perfiles en revisión o abstención hasta
que exista evidencia de sitio y componentes productores trazables.

Para documentación de distribución, licencias y runtime consultar AGENTS.md,
docs/78_DECISION_DISTRIBUCION_DE_PESOS_Y_RUNTIME.md y
docs/79_ADR_FRONTERA_OPEN_BABEL.md.