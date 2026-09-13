# Distribución MSIX / Microsoft Store

Ruta **separada** de NSIS. El instalador NSIS sigue siendo el de siempre
(`tauri.conf.json` + `tauri.conf.prod.json` → `npm run tauri:build`) y nada de
aquí lo sustituye ni lo modifica.

## Por qué son dos pasos y no uno

`tauri build --bundles` admite exactamente `msi` y `nsis` en la CLI 2.11. **No
hay target MSIX.** La guía oficial para Store con Tauri es la que se sigue aquí:
compilar la app con Tauri y empaquetar después con el CLI `winapp` de Microsoft.

## Piezas

| Ruta | Qué es |
|---|---|
| `msix/msix-config.json` | Fuente única de verdad: identidad, versión, nivel de confianza. |
| `msix/Package.appxmanifest` | **Generado.** No editar a mano: `build_msix.py` lo sobrescribe. |
| `msix/assets/` | **Generados** por `winapp manifest update-assets`. |
| `frontend/src-tauri/tauri.conf.msix.json` | Config de Tauri para Store. |
| `scripts/build_msix.py` | Orquestador reproducible de las 7 fases. |
| `scripts/accept_msix_store.py` | Autotests: instala, ejecuta, actualiza, desinstala. |

### Sobre `tauri.conf.msix.json`

Se **mezcla** sobre `tauri.conf.json` con `--config`. Contiene sólo lo que
cambia:

- **`bundle.active: false` / `targets: []`** — Tauri compila el exe y no genera
  instalador. El MSIX lo arma `build_msix.py`.
- **`app.security.csp`** — copiada **verbatim** de `tauri.conf.prod.json`. El
  build de Store debe correr con la misma política de seguridad que el de NSIS;
  relajarla produciría un binario distinto del validado. Hay un autotest que lo
  comprueba.
- **`bundle.publisher: "amezcua-dev.com"`** — metadato del binario, coincide con
  `PublisherDisplayName`. **No** es la identidad criptográfica: ésa es
  `Package/Identity/Publisher` y vive en `msix-config.json`.

El fichero no lleva claves de comentario (`_nota` y similares): el esquema de
Tauri las rechaza con *«Additional properties are not allowed»* y el build
falla. Por eso la justificación está aquí y no dentro del JSON.

## Dónde aterrizan los artefactos

En la **raíz de producción**, `E:\rel` por defecto, que está deliberadamente
fuera del árbol de desarrollo **y en otro disco físico**. Cada envío estrena su
propia carpeta:

```
E:\rel\
  devcert.pfx                ← el mismo para todas las versiones; no se commitea
  v1.0.2.0\
    layout\
    amezcua-dev.com.MolDesign_1.0.2.0_x64.msix
    build-evidence.json
    accept-evidence.json         ← la escriben los arneses junto al paquete
    accept-cases-evidence.json
    wack-report.xml
```

Tres razones, y ninguna es estética:

1. **Un disco distinto.** Un fallo del disco de trabajo no se lleva el paquete
   sellado ni su evidencia.
2. **Nadie pisa producción desde desarrollo.** Así fue como un `--check` dejó
   corrupto `dist/base-v1.0.0.zip` durante una auditoría.
3. **Una carpeta por versión, que nunca se reutiliza.** El fallo concreto que
   esto cierra: el `.msix` se reempaquetó con el mismo nombre y las tres
   evidencias quedaron describiendo bytes que ya no existían. Ahora cada
   evidencia guarda además el **sha256** del paquete que probó.

Se cambia con `--dist` o con `MOLDESIGN_DIST_RAIZ`. Dos avisos:

- **La raíz debe ser corta.** El fichero más hondo del runtime staged (torch y
  sus `third_party` anidados) queda a ~238 caracteres y Windows corta en 260.
  `build_msix.py` mide el path proyectado **antes** de copiar y aborta si no
  cabe, en vez de fallar a media copia.
- **No hay repliegue.** Si la unidad de producción no está, el build aborta. Se
  consideró replegar al árbol de desarrollo y se descartó: dejaría el paquete en
  un disco con la evidencia diciendo otro.

El `build-evidence.json` registra ahora si el árbol estaba limpio y cuántos
ficheros había sin commitear. Empaquetar con cambios locales sigue siendo
posible —hay motivos legítimos— pero deja de poder presentarse como un build
reproducible desde un commit.

## Identidad — exacta e inmutable

```
Package/Identity/Name                      amezcua-dev.com.MolDesign
Package/Identity/Publisher                 CN=6441FBBA-B77A-4619-9CEB-ACEDE74573C0
Package/Properties/PublisherDisplayName    amezcua-dev.com
```

La asigna Partner Center. Cambiar cualquiera de las tres rompe la
correspondencia con la reserva del nombre y el paquete deja de ser actualizable
para quien ya lo tenga instalado.

## Versión del Store

Cuatro campos, `Major.Minor.Build.Revision`, con **Revision siempre 0**: el
Store reserva ese campo y rechaza un paquete que lo use.

`build_msix.py` la deriva de `version` de `tauri.conf.json` (semver, que puede
traer prerelease) con este mapeo:

| semver | Build |
|---|---|
| `alpha.N` | `N` |
| `beta.N` | `10000 + N` |
| `rc.N` | `20000 + N` |
| sin prerelease | `30000 + patch` |

`1.0.0-alpha.2` → **`1.0.2.0`**.

Los tramos separados garantizan `alpha < beta < rc < final` dentro de un mismo
`Major.Minor`, que es lo que el Store exige: la versión debe crecer de forma
monótona entre envíos.

> **Decisión pendiente.** Este mapeo es **política de publicación**, no un hecho
> técnico. Necesita confirmación antes del primer envío real: una vez publicada
> una versión, el Store no admite retroceder. `store_build_override` permite
> fijar el Build a mano.

## Nivel de confianza: `runFullTrust`

```xml
<rescap:Capability Name="runFullTrust" />
```
con `EntryPoint="Windows.FullTrustApplication"`.

No es opcional:

- el backend es un **intérprete Python embebido propio** que se lanza como
  subproceso y abre un socket en `127.0.0.1`;
- **AutoDock Vina** se invoca como proceso externo y escribe temporales;
- **Open Babel** se invoca por CLI como programa independiente, por frontera de
  licencia GPL-2.0-only;
- la app escribe SQLite, poses y logs en el perfil del usuario.

Sin plena confianza no hay pipeline.

> `runFullTrust` es una capacidad **restringida**: Partner Center exige
> justificación escrita y la revisa una persona. **El texto de esa justificación
> es decisión del responsable del producto**, no de este script.

## Escritura fuera de `WindowsApps`

`C:\Program Files\WindowsApps\...` es de **sólo lectura** para la app. Rutas
declaradas por el producto, todas fuera del paquete:

| Qué | Dónde |
|---|---|
| Datos y SQLite | `%USERPROFILE%\MolDesign\data` |
| Poses y artefactos | `%USERPROFILE%\MolDesign\data` |
| Logs del backend | `%TEMP%\MolDesign\logs` |
| Temporales de Vina | `%TEMP%\vina` |
| Bytecode | no se escribe: `PYTHONDONTWRITEBYTECODE=1` y el bundle trae `.pyc` |

`accept_msix_store.py` no las da por buenas: se las **pregunta al backend
empaquetado** y comprueba que ninguna cae bajo `WindowsApps`.

## Cómo construir

```bash
python scripts/build_msix.py --todo                 # las 7 fases
python scripts/build_msix.py --todo --omitir-tauri  # reutiliza el exe
python scripts/build_msix.py --fases manifest,layout,package,sign
```

Fases: `stage → tauri → assets → manifest → layout → package → sign`.

La fase `tauri` **no** duplica `stage:desktop` ni `build:desktop`: el
`beforeBuildCommand` de `tauri.conf.json` ya encadena las puertas del producto
(manifiesto de rescoring, M5, goldens, pesos de stacking, frontera de Open
Babel, gate de evaluación, dossier). Saltárselas produciría un MSIX que no pasó
las mismas puertas que el NSIS.

## Cómo validar

```bash
python scripts/accept_msix_store.py --msix E:\rel\v<version>\<paquete>.msix
```

## Firma

El certificado de desarrollo (`E:\rel\devcert.pfx`) existe **sólo** para
poder instalar y probar en esta máquina: Windows exige que el sujeto coincida
exactamente con `Package/Identity/Publisher`. **No se distribuye ni se
commitea.** El paquete que se envía a Partner Center no se firma localmente: lo
firma el Store.

## Lo que esta ruta NO hace

- No edita `LICENSE`, `LICENSE-MODELS`, `COMMERCIAL-LICENSE.md`, SBOM ni textos
  de licencia.
- No toca checkpoints, pesos, manifiestos científicos ni umbrales.
- No hace push ni publica en Partner Center.
- **No redirige el destino de las descargas de modelos.** Es una frontera de
  seguridad deliberada y bloquea ESMFold y el LLM local en MSIX. Ver
  `docs/86_DISTRIBUCION_MSIX_MICROSOFT_STORE.md`.
