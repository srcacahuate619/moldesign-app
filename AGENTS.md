# AGENTS.md

Orientación para agentes de código que trabajen en este repositorio o lo
evalúen desde fuera. Este archivo describe **lo que MolDesign es hoy, medido**,
no lo que aspira a ser. La distinción es el producto: MolDesign existe para
decir cuándo *no* confiar en un número, así que su propia documentación no puede
permitirse exagerar.

Si eres un humano, empieza por [`README.md`](README.md). Este archivo asume que
vas a leer o modificar código.

---

## Qué es MolDesign hoy

Una **aplicación de escritorio** (Windows, Tauri v2 + Next.js + FastAPI + Python
embebido) para producir, organizar y comunicar **evidencia computacional
estructural** en etapas tempranas de investigación farmacológica.

No responde «¿esta molécula será un buen fármaco?». Su contrato es más estrecho
y más honesto:

> ¿Qué evidencia produjo esta corrida, con qué estructura y configuración, qué
> controles superó, qué incertidumbre permanece y qué sería justificable hacer
> después?

## Identidad de producto: confianza y transferencia estructural

MolDesign ocupa el espacio entre una estructura inicial y un cálculo científico
costoso. Su trabajo no es acumular motores ni prometer *drug discovery*
end-to-end, sino convertir decisiones estructurales que suelen quedar implícitas
en un objeto auditable, transferible y capaz de abstenerse.

```text
estructura + ligandos + contexto experimental
                    ↓
      MolDesign: readiness y procedencia
      - detecta bloqueantes y ambigüedades
      - registra decisiones y alternativas
      - conserva hashes, versiones y condiciones
                    ↓
        paquete estructural reproducible
                    ↓
      FEP+, OpenFE u otro cálculo externo
```

La arquitectura conceptual tiene cuatro capas:

| Capa | Responsabilidad |
|---|---|
| **Identidad permanente** | Confianza, procedencia y transferencia entre una hipótesis estructural y un cálculo posterior. |
| **Primer caso de uso de alto valor** | Auditar y preparar sistemas para flujos de energía libre sin ejecutar FEP. |
| **Implementación actual** | Producir y conservar evidencia de docking con Vina; ESMFold sólo aporta estructuras de péptidos que después acopla Vina. |
| **Destinos externos** | FEP+, OpenFE u otros protocolos; cada adaptador debe demostrar por separado qué puede reconstruir. |

Estas reglas forman parte del contrato del producto:

1. **FEP-ready es el primer flujo, no toda la identidad.** La misma capa podría
   preceder MD, ABFE o QM/MM, pero sólo después de medir y documentar la
   compatibilidad correspondiente.
2. **La unidad de valor no es un score aislado.** Es el sistema transferible:
   receptor, serie de ligandos, estados químicos, poses, correspondencias
   atómicas, referencias experimentales, decisiones y procedencia.
3. **«Preparado» no significa «el parser lo acepta».** Cadenas y unidad
   biológica, huecos, protonación, tautomería, estereoquímica, aguas, metales,
   cofactores y pose inicial deben resolverse o quedar declarados como
   incertidumbre.
4. **La abstención es una salida válida.** Un paquete puede quedar
   `BLOCKED`, `REVIEW` o `READY`; ocultar una ambigüedad para producir un
   archivo sería un defecto.
5. **La transferencia se prueba fuera de la sesión.** Un tercero debe poder
   reconstruir el paquete con sus archivos, manifiesto, hashes, versiones y
   decisiones registradas.
6. **«FEP+ ready» no equivale a certificación de Schrödinger.** Es una meta de
   preparación estructural independiente del proveedor hasta que una prueba de
   integración demuestre compatibilidad con una versión concreta.

Los primeros usuarios plausibles son equipos que sufren una frontera de
responsabilidad: CRO ↔ cliente, colaborador estructural ↔ equipo de simulación,
core facility ↔ laboratorio, biotech pequeña ↔ proveedor de FEP, o un grupo que
mantiene pipelines propios con OpenFE. La validación de producto debe medir si
reduce iteraciones, rechazos tardíos, decisiones perdidas y tiempo de preparación;
no sólo cuántas funciones ofrece.

Funciona **sin red**. Los pesos de los modelos se descargan una vez, a petición
explícita del investigador, y a partir de ahí la aplicación es autónoma. Esto no
es un detalle de implementación: es un requisito verificado por una guardia del
build (`frontend/scripts/check-no-remote-assets.js`).

### Lo que ejecuta de verdad

**Dos motores, y sólo dos.**

| Motor | Estado |
|---|---|
| **AutoDock Vina 1.2.7** | Empaquetado en el instalador. Es el motor de docking. |
| **ESMFold** | Descargable bajo demanda (8,4 GB). Pliega péptidos; el acoplamiento lo hace después Vina. |

El menú avanzado nombra siete motores. Los otros cinco —QuickVina 2, DiffDock,
ColabFold, ESMFold Pro, RFdiffusion— aparecen como **«Próximamente»**, con su
motivo, y la interfaz los deshabilita. `GET /evaluation/engines` declara qué
puede ejecutar *esta* instalación y por qué no lo demás.

**No los añadas ni los actives sin evidencia.** Ver `backend/tests/
test_motores_declarados_son_los_que_existen.py`. Hay tres pruebas guardián
(`ENG-001`, `ENG-003`, `ENG-004`) que fallan a propósito si alguien vuelve a
ofrecer un motor que la build no ejecuta. Esas pruebas existen porque ya pasó:
`diffpepdock` estaba en el contrato de la API, despachaba a ESMFold, y
etiquetaba la corrida con su propio nombre — una mentira de procedencia en el
dossier.

### Por qué DiffDock y ColabFold no están

No es falta de tiempo. Está medido en esta misma máquina:

- **DiffDock** (vía NVIDIA NIM, 19 complejos publicados *después* de su corte de
  entrenamiento): 84% de RMSD < 2 Å pero **21% de poses físicamente válidas**
  (PoseBusters). Y su `position_confidence` está **anticorrelacionado** con la
  validez: filtrar por «alta confianza» empeora el resultado al 14%. Para un
  producto cuya propuesta es saber cuándo no confiar, un motor sin señal de
  confianza utilizable no aporta nada.
- **ColabFold** necesita bases de datos de MSA de ~2 TB o un servicio remoto, y
  los parámetros de AlphaFold2 son CC BY-NC.

Referencia externa que lo enmarca: PoseBusters 2024 (Buttenschoen, Morris &
Deane, *Chem. Sci.* 15, 3130) da Vina 58% y DiffDock 12% con validez física
exigida.

### Lo que MolDesign NO es

- **No corre dinámica molecular ni FEP.** Ver la sección siguiente.
- **No predice actividad biológica.** Las capas ADMET son experimentales y se
  presentan como tales.
- **No sustituye validación experimental**, y la interfaz lo dice en cada
  informe.
- **No es un servicio en la nube.** Todo el cómputo es local.

---

## Primer caso de uso: preparación **FEP-ready**

Ésta es la confusión más probable de un agente, así que va explícita:

> **MolDesign no ejecutará FEP.** Ser «FEP-ready» significa preparar y auditar
> el sistema estructural que consumirá un cálculo externo, conservar las
> decisiones que lo definen y permitir que un tercero reconstruya el paquete.

El cálculo de energía libre lo hará otro (Schrödinger FEP+, OpenFE u otro
protocolo). El hueco que MolDesign ocupa está *antes*: preparación, control y
transferencia de los supuestos estructurales que esos métodos dan por hechos.

**Ésta es una dirección de producto, no el estado actual.** Hasta superar
`FEP-05` y `FEP-06`, la formulación correcta es «auditor de readiness para FEP
en desarrollo», no «sistema compatible con FEP+».

Estado auditado hoy, sobre 203 complejos:

| Auditoría | Listos | Cuello |
|---|---:|---|
| `FEP-01` integridad del ligando | **19%** (39/203) | 164 con tautómero ambiguo, **ninguno declarado** |
| `FEP-02` integridad del receptor | **41%** (83/203) | 86 con huecos de cadena, 43 con el sitio repartido, 52 con metales, mediana de 10 aguas sin documentar |
| `FEP-03` series congenéricas | 91 parejas / 18 dianas | El conjunto se armó para diversidad, lo contrario de lo que FEP+ necesita |

Orden de trabajo declarado (`docs/50_ROADMAP.md` §3):

1. **Declarar tautómeros** — **hecho** (`56e8733`, tres estados) y medido en
   `FEP-01-DECL` (GO): 180/203 (88,7%) quedan *declarados*, pero sólo **39 (19%)
   resueltos**; 141 necesitan multiestado y 22 superan el tope de 32. Declarado
   no es resuelto: la cifra que describe el estado real es la del 19%. Para
   docking con Vina apenas importa; para FEP+ es determinante, porque el
   tautómero define qué átomos donan y cuáles aceptan puentes de hidrógeno.
   Siguiente: un modelo energético validado para descartar candidatos.
2. **Documentar receptores** — huecos, cadenas múltiples, metales, aguas
   estructurales frente a desplazables.
3. **Reconstruir la cohorte congenérica** desde PDBBind: pocas dianas con muchos
   análogos.
4. **`FEP-05`** export reproducible: SDF/PDB/JSON con hashes, versiones, caja,
   semillas y advertencias.
5. **`FEP-06`** dry-run de transferencia — un tercero reconstruye el paquete sin
   conocer la sesión.

Horizonte declarado: 12–18 meses para el conjunto; ~3 meses para el 80% del
valor (los tres primeros puntos).

---

## El ejecutable

El instalador se distribuye por **GitHub Releases**, no vive en el árbol
(`frontend/src-tauri/target/` está en `.gitignore`).

```
MolDesign AI_1.0.0_x64-setup.exe     ~504 MiB
```

### NO ESTÁ FIRMADO

No lleva firma **Authenticode**. Consecuencias que conviene decir sin adornos:

- Windows mostrará el aviso de SmartScreen «aplicación no reconocida».
- **El SHA-256 es la única prueba de integridad que existe.** Verifícalo antes
  de ejecutarlo:

  ```powershell
  Get-FileHash ".\MolDesign AI_1.0.0_x64-setup.exe" -Algorithm SHA256
  ```

  y contrástalo con el `.sha256` y el `release-manifest.json` que acompañan a
  cada release.

La falta de firma es por falta de presupuesto para el certificado, no por
descuido. Está declarada en `release-manifest.json` como
`"firmado_authenticode": false`.

El manifiesto también trae `"arbol_limpio"`: si es `false`, ese instalador se
construyó desde un árbol con cambios sin commitear y **no es reproducible desde
el repositorio**. Compruébalo antes de asumir que el binario corresponde al
código que estás leyendo.

---

## Mapa del repositorio

```
backend/          FastAPI + pipeline científico (Python).
  api/            routers y main
  chem/           propiedades, conformers, validación
  services/       docking, pipeline, motores, IA, blockchain
  scoring/        rescoring y calibración
frontend/         Next.js 16 (export estático) + Tauri v2.
  src-tauri/      contenedor Rust: supervisa el backend, ventana, descargas
  scripts/        guardias del build (ver abajo)
rescoring/        modelos de rescoring y selector de pose
scripts/          herramientas de empaquetado y ciencia
  bundle_helper.py        arma el runtime que viaja en el instalador
  stage_openbabel_tool.py materializa Open Babel como herramienta externa
  check_openbabel_boundary.py  guarda de la frontera GPL (ver doc 79)
  artifacts_science/      artefactos SELLADOS de experimentos (no editar)
tools/            programas de terceros invocados por subproceso
  vina/ xtb/ llama/       binarios (no versionados)
  openbabel/              Open Babel GPL-2.0-only + manifiesto y licencia
  vc-runtime/             cinco DLL MSVC x64 firmadas + manifiesto y hashes
docs/             programa experimental, gates de release, auditorías
```

---

## Construir

```bash
cd frontend
npm run test:run      # 1062 pruebas
npm run tauri:build   # instalador completo
```

`tauri:build` encadena quince puertas en `beforeBuildCommand`, más `cargo`/NSIS y
el sellado. Todas bloquean el build si fallan. La lista sale de
`frontend/src-tauri/tauri.conf.json`, no de la memoria de nadie (esta tabla
decía catorce y le faltaba la primera; la auditoría externa 001 lo midió el
2026-09-22):

| # | Puerta | Qué comprueba |
|---:|---|---|
| 1 | `check:runtime-arbol` | el runtime que las demás dan por hecho existe (`python-embed/` y compañía), con el Python del sistema |
| 2 | `check:csp` | la CSP de producción trae lo que la app necesita |
| 3 | `check:rescoring-manifest` | los pesos declarados son los que hay |
| 4 | `check:m5-manifest` | el manifiesto de M5-Zn |
| 5 | `check:goldens` | las ocho corridas doradas, byte a byte |
| 6 | `check:pesos-stacking` | la interfaz y el backend resuelven los mismos pesos |
| 7 | `check:openbabel-fuente` | `tools/openbabel/` coincide con su manifiesto y **convierte una molécula de verdad** |
| 8 | `stage:desktop` | copia el runtime y precompila el bytecode del arranque |
| 9 | `check:openbabel` | la frontera con Open Babel **sobre el bundle staged** (ver abajo) |
| 10 | `verify:desktop-runtime` | imports, Vina, Open Babel y `/health` con el Python embebido |
| 11 | `check:evaluation-runtime` | una evaluación real con Vina termina, persiste y reaparece desde el bundle |
| 12 | `check:dossier-embebido` | el dossier del runtime embebido coincide con el de desarrollo |
| 13 | `build:desktop` | export estático de Next |
| 14 | `check:exported-api-url` | ningún puerto de backend horneado |
| 15 | `check:no-remote-assets` | ningún recurso remoto |
| — | `cargo` + NSIS | el instalador |
| — | `seal:installer` | SHA-256 y manifiesto de release |

**El orden de 8 y 9 no es casual.** `check:openbabel` mira el ARTEFACTO —sin
bindings de Open Babel en `site-packages`, sin resolución por `PATH`, hash y
versión correctos, conversión PDBQT→SDF real— así que sólo puede correr después
de `stage:desktop`. Comprobar el repositorio no habría detectado nada: las
pruebas del *código* estaban verdes mientras la aplicación instalada fallaba,
que es la restricción 1 de más abajo. Ver
`docs/79_ADR_FRONTERA_OPEN_BABEL.md`.

Además: `npm run smoke:prod` levanta el backend con el Python empaquetado y el
entorno exacto de `src-tauri/src/backend.rs`, sirve el export real con la CSP de
producción e inyecta un `window.__TAURI__`. **Ejecútalo antes de dar por buena
cualquier corrección que toque empaquetado, CSP o estilos.**

---

## Restricciones que no debes romper

Cada una viene de un fallo real que costó al menos un instalador.

1. **Lo que se verifica tiene que ser lo que se entrega.** Las 688 pruebas de
   frontend estaban verdes mientras la app instalada tenía cinco fallos
   simultáneos. Todas corrían sobre el *código*; los fallos vivían en el
   *artefacto*. Si añades una prueba para un problema de empaquetado, que mire
   `out/` o el binario, no el `.tsx`.

2. **Un guardián tiene que demostrar que ve.** Un detector nuestro quedó con un
   carácter `0x08` dentro de su expresión regular, recorrió 167 archivos y
   anunció «limpio» sobre un export sucio. Los guardianes de `frontend/scripts/`
   llevan autotest con muestras que deben detectar y muestras que no. Mantenlo.

3. **No adivines el puerto del backend.** Rust elige el primero libre de
   8000-8019 y lo entrega por `ensure_backend`. Caer a `:8000` te pone a hablar
   con el proceso ajeno que lo ocupe. `lib/config.ts` es el único dueño de esa
   dirección.

4. **Tauri reescribe la CSP.** Inyecta nonces, y un nonce **anula
   `'unsafe-inline'`** por especificación — con él se caen todos los
   `style={{...}}` de React. Por eso `tauri.conf.json` lleva
   `dangerousDisableAssetCspModification: ["style-src"]`. En `tauri dev` no
   ocurre, así que **desarrollo no prueba esto**.

5. **No edites `scripts/artifacts_science/`.** Son artefactos sellados con
   hashes. Cambiarles los bytes invalida el sellado.

6. **Los números científicos se citan con su condición.** Ejemplo vivo: la
   validez física de PoseBusters sólo es comparable bajo el protocolo de
   reconstrucción de hidrógenos documentado en `MF-33-H-COR`. Un número sin su
   condición es un número falso.

7. **Trabajo caro fuera del camino crítico.** El arranque pasó de ~57 s a ~6 s
   quitando dos cosas que nadie necesitaba para abrir la aplicación: un import
   de sondeo que arrastraba torch, y un precalentamiento de modelos que
   bloqueaba la ventana. Antes de añadir algo al arranque, mide con
   `python -X importtime`.

8. **La rama de desarrollo no se empuja al repositorio público.** Su historial
   contiene manuscritos sin enviar, el deck y registros internos
   (`scripts/retenidos_del_publico.txt`) y una contraseña antigua del servidor.
   Se publica replicando commits sobre la rama `publico` en un worktree. El
   2026-09-21 alguien empujó `codex/release-hygiene` y el tag `v1.0.1` y las 56
   rutas quedaron públicas; el 2026-09-22 se borró el repositorio y se recreó
   desde `publico`, porque borrar la rama no quitaba los commits de la caché
   de GitHub (seguían descargándose por SHA). Desde entonces
   `scripts/check_push_publico.py` es un hook `pre-push` que rechaza cualquier
   ref cuyo historial las toque o que añada una credencial. Si el hook no
   está, instálalo con `--instalar` antes de empujar nada.

---

## Licencia

**PolyForm Noncommercial 1.0.0** ([`LICENSE`](LICENSE)). Permite usar,
estudiar, modificar y redistribuir MolDesign para fines no comerciales. Los
modelos propios ligeros incluidos se rigen por los mismos límites, explicitados
en [`LICENSE-MODELS`](LICENSE-MODELS).

MolDesign es **source-available**, no software de código abierto según la
definición OSI, porque el uso comercial está reservado. Cualquier uso comercial
requiere una licencia escrita separada; ver
[`COMMERCIAL-LICENSE.md`](COMMERCIAL-LICENSE.md). La tarifa, regalía o comisión
se negocia caso por caso: el repositorio no concede una tasa automática.

Las versiones ya publicadas bajo AGPL conservan irrevocablemente esa licencia.
La licencia actual sólo gobierna esta versión y las posteriores que se publiquen
bajo ella. Las contribuciones requieren firmar el [CLA](CLA.md) para mantener
consolidado el derecho de relicenciamiento.

La integración Solana es exclusivamente un **POC en devnet**. La firma ocurre
en el frontend con `@solana/web3.js`; el backend sólo prepara y verifica memos
por JSON-RPC estándar. No reintroduzcas `solana-py`, `solders`, `jsonalias` ni
una clave institucional. El modo escritorio usa una identidad efímera y SOL de
prueba; ninguna salida constituye certificación ni validez científica. Ver
`docs/83_ADR_SOLANA_DEVNET_POC.md`.
El runtime incluye además cinco DLL x64 de Microsoft Visual C++ 14.50.35719
como despliegue app-local; no están cubiertas por la licencia de MolDesign y su procedencia y hashes viven en
`tools/vc-runtime/`.

Dependencias con copyleft en el runtime distribuido: cuatro paquetes LGPL
(`rpc-websockets`, `GridDataFormats`, `meeko`, `paramiko`) **y un programa GPL:
Open Babel 3.1.1.23, `GPL-2.0-only`**, que viaja en `tools/openbabel/`. No hay
AGPL de terceros ni SSPL; las restricciones no comerciales propias se declaran arriba.

Este párrafo ha estado mal dos veces, y las dos correcciones valen como aviso.

Decía «no hay GPL» y era falso: el detector de `scripts/generate_sbom.py` buscaba
la subcadena `GPL`, y Open Babel declara su licencia como `GNU GENERAL PUBLIC
LICENSE` —donde esa subcadena no aparece—, así que el gate quedaba verde con un
componente GPL dentro. El detector normaliza el nombre largo desde entonces.

Después decía que Open Babel «se invoca como biblioteca Python, no como
subproceso», y eso también era falso en el único punto de uso vivo: `vina_service`
ya lo invocaba por subproceso. Lo cierto era peor y más aburrido: los *bindings*
viajaban en `site-packages`, dos módulos de `rescoring/` los importaban, y el
binario se resolvía dentro del paquete Python con un respaldo a `"obabel"` a
secas que el `PATH` podía resolver a cualquier cosa.

**Resuelto el 2026-09-05.** Open Babel sigue en el instalador, pero como
**programa independiente**: fuera del entorno Python importable, con manifiesto,
hash, licencia y procedencia propios, invocado por un único adaptador
(`backend/services/external_tools/open_babel.py`) que verifica el hash antes de
ejecutar y **nunca** resuelve por `PATH`. Nueve guardas
(`scripts/check_openbabel_boundary.py`) bloquean el build si eso deja de ser
cierto. La decisión completa, con lo que queda prohibido y lo que sigue abierto
—incluida la recomendación de una revisión jurídica externa antes de vender
licencias comerciales—, está en `docs/79_ADR_FRONTERA_OPEN_BABEL.md`.

**No importes `openbabel`, `pybel` ni `_openbabel` desde `backend/` o
`rescoring/`.** No es una preferencia de estilo: los bindings GPL-2.0-only no pueden redistribuirse como una sola obra bajo PolyForm Noncommercial; un import destruiría la frontera de programa independiente.

Además, cinco paquetes Python y siete npm no declaran licencia en su metadata
—entre ellos `tabpfn`, cuyas condiciones no son las de sus dependencias—. El
SBOM los lista ahora en `sin_licencia_declarada`. Ver
`docs/69_GATE_DE_RELEASE.md`.

---

## Estado y honestidad

- Backend: **2546** pruebas recolectadas con el intérprete que se distribuye
  (`python-embed`, 3.11.9), medidas el 2026-09-22. Con el intérprete de
  desarrollo (3.14) son 36 más (2582):
  la diferencia son `importorskip` cuya dependencia no viaja en el bundle, y por
  eso el número que vale es el del runtime embebido. Frontend: **1062** en 117
  archivos (medido el 2026-09-23). `tsc` limpio.
  El conteo del backend lo mantiene `scripts/report_test_counts.py`, que
  escribe `docs/api/test-counts.json`: esa es la fuente, no este párrafo.
  Este párrafo ya envejeció dos veces —decía 2117 y 889, y luego 2518 cuando
  el registro ya daba 2542— mientras el registro estaba al día; si vuelven a
  discrepar, manda el registro.
- Smoke de producción: **13/13** (2026-09-23; la 13.ª comprueba que el smoke no
  toca la base de datos del usuario).
- Arranque medido en entorno de producción: **~6 s**.
- **Cero usuarios externos** todavía. El propio roadmap identifica esto como el
  riesgo de muerte real del proyecto, por encima del científico.
- La ciencia de ESMFold **no está validada**: está probado que carga y sirve
  poses, no que las poses sean buenas.

Si encuentras una afirmación en este repositorio que no puedas rastrear hasta
una medida, trátala como un defecto y dilo.
