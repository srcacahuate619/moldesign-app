# Auditoría de seguridad de dependencias (local)

Fecha de la medición: 2026-09-06.

Este documento registra el estado local previo al primer push público. No
sustituye una revisión de seguridad y distingue deliberadamente entre un
paquete instalado, un módulo incluido en el export y una ruta ejecutable.

## Toolchain reproducible

Desde `frontend/`:

```text
nvm use 24.20.0
npm ci
npm run typecheck
npm run lint
npm run test:run
npm run build:desktop
npm run smoke:prod
npm audit --omit=dev
npm audit
```

El contrato está fijado por `.nvmrc`, `engines` y `packageManager`: Node
24.20.x y npm 11.19.x. Ketcher 3.18 requiere Node >=24.14.1.

## Resultado medido

| Ámbito | Total | Alta | Moderada | Baja | Crítica |
|---|---:|---:|---:|---:|---:|
| Dependencias de producción | 19 | 7 | 12 | 0 | 0 |
| Todas las dependencias | 19 | 7 | 12 | 0 | 0 |

La migración eliminó los avisos directos de Next, Ketcher, Vite y Vitest:
Next 16.3.4, React 19.2.8, Ketcher 3.18.0, Vite 8.2.2 y Vitest 5.0.0. El
export estático compila, 859 pruebas pasan y el smoke de producción pasa
12/12.

## Riesgo residual aceptado: rama Solana

Los 19 registros se propagan desde cuatro avisos raíz y todos pertenecen a la
función opcional de certificación Solana:

- Siete `high` (`react-native`, Metro e `image-size`) quedan instalados por
  peers obligatorios del adaptador móvil. Webpack selecciona la variante
  browser y ninguno aparece en `out/`; Metro no se ejecuta en MolDesign.
- `stream-json` sólo está referenciado por utilidades Node de `jayson`; el
  cliente browser que usa `@solana/web3.js` no lo importa y la cadena no está
  en el export.
- `uuid` sí llega al cliente JSON-RPC, pero `jayson` llama `v4()` sin buffer. El
  aviso GHSA-w5hq-g745-h8pq afecta v3/v5/v6 cuando reciben un buffer.

Esto es una aceptación de riesgo acotada al artefacto actual, no una afirmación
de seguridad general sobre esos paquetes. Debe revisarse cuando cambie el lock,
el bundler o la integración Solana.

No se aplican overrides mayores a `stream-json`/`uuid`: romperían el contrato de
`jayson` para corregir rutas que no se ejecutan. Tampoco se adopta
`npm ci --omit=peer` como mecanismo para poner el contador en cero: omite peers
de todo el árbol y haría que el entorno auditado no fuera el mismo que usa el
build. Se vigilará que upstream haga opcional React Native.

## Observaciones de compatibilidad

`miew-react@0.11.0`, dependencia interna de Ketcher, conserva metadata de peer
limitada a React 18 aunque `ketcher-react@3.18.0` declara React 18 o 19. `npm ci`
lo avisa; export, TypeScript, pruebas y smoke verifican la ruta usada por
MolDesign. Si Ketcher actualiza ese peer, se retira esta excepción.

Next 16.3.4 tiene además un defecto de export RSC en Windows: genera algunos
segmentos como directorios mientras el navegador solicita nombres planos. El
postbuild `scripts/normalize-next-rsc-export.mjs` materializa de forma
determinista los nombres solicitados, ejecuta un autotest y es verificado por
el smoke. La guarda `check-solana-browser-boundary.mjs`, también ejecutada por
el postbuild, falla si React Native/Metro o `stream-json` alcanzan los chunks.
Referencia upstream: https://github.com/vercel/next.js/issues/92339.

## Criterio de release

El contador de npm no está en cero, pero no quedan avisos conocidos en una ruta
alcanzable del export de escritorio. El release debe bloquearse si aparece un
aviso fuera de esta rama aceptada, si los paquetes móviles entran en `out/`, si
cambia la API de `uuid` usada por `jayson`, o si falla cualquiera de build,
smoke, TypeScript o pruebas.
