# Entrega · Receptores propios (1.0.2)

> **Nota de reubicación (2026-10-11).** El worktree `receptores-propios` se retiró el 2026-10-11. Su rama `claude/receptores-propios` está íntegra en desarrollo (`6eef2ce9`): para leer el código usa `git show claude/receptores-propios:<ruta>`. Los enlaces a `D:\moldesign-build\.worktrees\receptores-propios\...` ya no existen. Índice: [REUBICACIONES_2026-10-11.md](docs/REUBICACIONES_2026-10-11.md).

Rama `claude/receptores-propios` (worktree `D:\moldesign-build\.worktrees\receptores-propios`), creada desde
`codex/release-hygiene` en `e9b032ae`. **Sin push y sin merge.** `codex/release-hygiene` ya avanzó (hoy `e548229d`
en el árbol principal): la integración necesita un merge, con conflictos esperables en
`docs/versions/1.0.2_cambios.md`, `docs/api/test-counts.json` y `docs/api/i18n-inventario.json` (los dos últimos se
regeneran, no se resuelven a mano; ver «Al integrar»).

Esta entrega sigue la regla del encargo: una entrega parcial y honesta vale más que una completa con supuestos. **Los
nueve puntos están hechos y verificados con Vina real por la API**, pero hay cosas que no se pudieron verificar y están
dichas en la sección 5.

---

## 1. Commits y archivos

| # | Commit | Qué entrega | Archivos principales |
|---|---|---|---|
| 1 | `827c1ae8` | Camino C sin origen: un PDBQT listo para Vina se evalúa **tal cual** (mismo hash antes y después, sin Meeko ni red); el informe declara hash, cadenas y tipos de átomo y deja `null` con motivo en lo que no se puede saber; Preparación sigue bloqueando lo imprescindible sin dato | `services/targets/perfil_receptor.py` (perfil `perfil.json`, sólo `USR_*`), `pdbqt_propio.py`, `ingesta_propia.py`, `errores_subida.py`, `services/docking/preparer_propio.py`, `preflight.py`, `vina_service.py`, `services/dossier/preparacion.py` |
| 2 | `e4e1f82b` | Lo básico: extensiones sin distinguir mayúsculas, `.gz` con tope de 128 MiB descomprimidos (bomba → 413), contenido contra extensión, mensajes sin SDF ni rutas del disco | `services/targets/entrada_receptor.py`, `api/routers/targets.py` |
| 3 | `e1797d7c` | mmCIF/PDBx con gemmi 0.7.5: cadenas por `auth_asym_id`, primer modelo, `REMARK 465`, ensamblaje sólo si se puede representar, paridad 8HFI PDB ↔ mmCIF | `services/targets/conversion_mmcif.py` |
| 4+5 | `073096f1` | Cadenas de varias letras y códigos CCD de 5 caracteres con correspondencia explícita (visible en Preparación con el código original); PDB con varios modelos o sin elemento normalizado y declarado; camino C **con** estructura de origen (auditoría origen→PDBQT tras comprobar que son el mismo receptor) | `normalizar_pdb.py`, `pdbqt_propio.py::exigir_correspondencia`, `services/dossier/preparacion_entrada.py` |
| 6 | `ada1394c` | Camino B: una estructura ya preparada por el equipo se **respeta** (HID/HIE/HIP/CYX/ASH/GLH/LYN, aguas, metales, cofactores sin lista blanca); se comprueba residuo a residuo que Meeko aplicó la plantilla declarada; se abstiene con motivo ante Na⁺ (en PDBQT `NA` es un nitrógeno aceptor), especies sin plantilla o sin radio covalente | `services/docking/preparer_respetando.py` |
| 7 | `e91bddea` | PQR: se lee declarando que Vina no usa las cargas; **defecto encontrado con una salida real de PDB2PQR 3.7.1**: `1CBDISU` se leía como un átomo sin cadena y escribía una línea corrupta sin avisar → ahora columnas primero, línea ambigua rechazada y parches de CHARMM (`TER`, `DISU`) rechazados con motivo y acción. Corpus real del punto 4 (8XVK `A1D5J`, 8YUT `A1D67`) | `lector_pqr.py`, `tests/data/receptores_propios/*` |
| 8 | `b0529f41` | Estructuras predichas y pLDDT: detección por lo que declara el archivo; pLDDT sólo con la convención **verificada en un archivo real** (AlphaFold DB); requisito nuevo `receptor.confianza_estructural` que pide revisión y **no bloquea** | `services/targets/prediccion.py`, `services/dossier/preparacion_confianza.py` |
| 9 | `faa610da` | El modal presenta los tres caminos (A cruda, B ya preparada, C PDBQT con origen opcional), extensiones y `.gz`, cadena de texto libre, errores reales del backend, 31 claves `pr_rp_*` ES/EN. Arreglos que salieron de la suite completa: 8 códigos de aviso sin declarar, nombre del camino B en un mensaje, inventario i18n | `frontend/components/interfaces/pro/CustomReceptorModal.tsx`, `frontend/context/traducciones/pro.ts`, `frontend/lib/api.ts`, `backend/services/avisos.py` |
| — | `d126ba8d` | Arnés: seis textos en español de antes del encargo declarados como ruido conocido (sección 5) | `scripts/qa_subida_receptores.py` |
| — | *(el commit de esta entrega)* | Esta nota, una prueba más (PDBQT con origen AlphaFold) y el conteo | `ENTREGA_RECEPTORES_PROPIOS.md`, `backend/tests/test_prediccion.py` |

Cada commit lleva sus pruebas y su fila en `docs/versions/1.0.2_cambios.md` (CRLF, sin líneas en blanco dentro de la
tabla). Total respecto a la base: 62 archivos (la mayor parte son fixtures reales), **+243 pruebas de backend (4029 → 4272)
y +26 de frontend**.

### Nuevo, de un vistazo

- Perfil por receptor propio `targets/USR_x/perfil.json` (esquema `receptor-propios/v1`; modos `automatico`, `respetar`,
  `pdbqt`). **El catálogo nunca tiene perfil**: `prepare_target` sólo se desvía si existe, y es lo que garantiza la
  invariancia de la sección 3.
- Errores de subida con contrato `{detail, codigo, datos}` en el idioma de la petición (`Accept-Language`), sin rutas
  del disco: `ErrorDeSubida` (`services/targets/errores_subida.py`).
- Preparación gana `receptor.entrada` («Archivo del receptor»: formato, modo, SHA-256, cada conversión, cada traducción
  de nombre, correspondencia con el origen) y `receptor.confianza_estructural`. **Ninguno aparece en el dossier de un
  receptor del catálogo.**
- La protonación de B y C se imprime como «declarada por el usuario», nunca como validada.

---

## 2. Arnés de la API con Vina real: antes → después

Arnés: `scripts/qa_subida_receptores.py --raiz <worktree>` (extiende el del encargo). Para cada caso aceptado: subida →
comprobación previa → evaluación con **Vina 1.2.7 real** → auditoría de Preparación por la ruta
`/evaluation/dossier/{id}/preparacion` en español y en inglés, más un barrido de castellano en la versión inglesa.

**Antes** (`informe_20261009.json`, base): **1/4**. `8hfi_curado.pdbqt` se sube «con éxito» y falla al evaluar
(`RECEPTOR_FUENTE_DISPONIBLE`); `8HFI_CRUDO.PDB` y `8hfi.cif` se rechazan (400).

**Después** (código final, corpus completo de 36 casos, `corpus_final.json`): **34/36 en la corrida completa; 36/36 tras
declarar como ruido conocido los seis textos en español de la sección 5** (los dos «NO» sólo los marcó el barrido de
castellano; Vina evaluó bien y la Preparación es la esperada). Sólo se **repitieron** esos tres casos del RCSB después del
cambio del arnés (3/3); los otros 33 no se repitieron porque el cambio sólo reduce marcas.

| Caso | HTTP | Código | Evaluación | E top-1 (kcal/mol) | Preparación | Cumple |
|---|---:|---|---|---:|---|:--:|
| `8hfi_crudo.pdb` | 201 | | SUCCESS | −7.557 | REVISION | sí |
| `8hfi_curado.pdbqt` (C sin origen) | 201 | | SUCCESS | −7.557 | BLOQUEADO (falta evidencia imprescindible, declarada) | sí |
| `8HFI_CRUDO.PDB` | 201 | | SUCCESS | −7.557 | REVISION | sí |
| `8hfi.cif` | 201 | | SUCCESS | −7.557 | REVISION | sí |
| `8hfi_curado_con_origen_pdb.pdbqt` | 201 | | SUCCESS | −7.557 | REVISION | sí |
| `8hfi_curado_con_origen_cif.pdbqt` | 201 | | SUCCESS | −7.557 | REVISION | sí |
| `8hfi_curado_con_origen_ajeno.pdbqt` | 400 | `PDBQT_NO_CORRESPONDE_AL_ORIGEN` | | | | sí |
| `8hfi_recortado.pdb` / `.cif` / `_crlf` / `_sin_elemento` / `rmn_varios_modelos` / `_altlocs` | 201 | | SUCCESS | −4.027 | REVISION | sí (×6) |
| `solo_adn.pdb` | 400 | `SIN_PROTEINA` | | | | sí |
| `mmcif_con_nombre_pdb.pdb` | 400 | `CONTENIDO_ES_MMCIF` | | | | sí |
| `pdb_con_nombre_pdbqt.pdbqt` | 400 | `CONTENIDO_ES_PDB` | | | | sí |
| `bomba.pdb.gz` | 413 | `GZ_DEMASIADO_GRANDE` | | | | sí |
| `sintetico_cadenas_largas_y_ccd5.cif` | 201 | | SUCCESS | −1.592 | REVISION | sí |
| `sintetico_100000_atomos.cif` | 201 | | SUCCESS | −1.546 | REVISION | sí |
| `cadena_inexistente.cif` | 400 | `CADENA_SIN_PROTEINA` | | | | sí |
| `8hfi_protonado_completo.pdb` (B) | 201 | | SUCCESS | −7.557 | REVISION | sí |
| `8hfi_protonado_completo_charmm.pdb` (B, `HSD/HSE/HSP/WAT`) | 201 | | SUCCESS | −7.557 | REVISION | sí |
| `8hfi_protonado_recorte.pdb` / `_charmm.pdb` | 201 | | SUCCESS | −4.217 | BLOQUEADO (hueco junto al sitio del recorte) | sí (×2) |
| `8hfi_protonado_sodio_cerca.pdb` | 400 | `ESPECIE_NO_REPRESENTABLE` | | | | sí |
| `8hfi_protonado_sodio_lejos.pdb` | 201 | | SUCCESS | −4.217 | BLOQUEADO | sí |
| `8XVK.cif` (RCSB, `A1D5J`) | 201 | | SUCCESS | −6.430 | REVISION | sí* |
| `8ZP2.cif` (RCSB, `A1LX4`) | 201 | | SUCCESS | −8.605 | BLOQUEADO (Na⁺ retirados junto al sitio) | sí* |
| `8YUT.cif` (RCSB, `A1D67`) | 201 | | SUCCESS | −1.654 | REVISION | sí |
| `8hfi_amber_ph74.pqr` (PDB2PQR 3.7.1 + PROPKA, AMBER) | 201 | | SUCCESS | −7.448 | REVISION | sí |
| `8hfi_parse.pqr` (PARSE; Meeko retira 2 `CSS` a 20 Å de la caja y lo declara) | 201 | | SUCCESS | −6.626 | REVISION | sí |
| `8hfi_charmm.pqr` / `8hfi_recortado_charmm.pqr` | 400 | `PQR_PARCHES_CHARMM` | | | | sí (×2) |
| `8hfi_recortado_amber.pqr` | 201 | | SUCCESS | −3.696 | REVISION | sí |
| `af_p23975_tm.pdb` (AlphaFold DB, caja en la transmembrana) | 201 | | SUCCESS | −4.671 | REVISION (`receptor.confianza_estructural` = REVISAR, 2 residuos < 70) | sí |
| `af_p23975_n.cif` (mismo modelo en mmCIF, caja en el extremo N) | 201 | | SUCCESS | −3.032 | REVISION (REVISAR, 25 de 25 residuos < 70) | sí |

\* Marcados «NO» en la corrida completa sólo por el barrido de castellano (sección 5); repetidos: 3/3.

Lecturas que importan:

- **Paridad entre rutas**: 8HFI por PDB crudo, mayúsculas, mmCIF y PDBQT con origen da el **mismo `receptor_sha256`
  (`30e66954…`) y −7.557 kcal/mol**. El modelo completo de AlphaFold DB por PDB y por mmCIF da el mismo `receptor_sha256`
  (`91e422f8…`).
- Preparación **no bloquea una predicción por su pLDDT** (REVISAR), pero sí bloquea lo que ya bloqueaba (huecos junto al
  sitio, metales retirados junto al sitio, PDBQT sin origen).
- Los rechazos dicen qué falló y qué hacer, en español e inglés, sin rutas.

---

## 3. Invariancia del catálogo (receta 7)

`scripts/invariancia_catalogo_receptores.py` prepara con `prepare_target` —la función que ejecuta cada corrida— los cinco
receptores del encargo en un directorio desechable y escribe el SHA-256 del PDBQT (`receptor_sha256`), el del informe de preparación y el hash de la receta. Se
ejecutó con el código de la base y **después de cada commit** (puntos 1, 2, 3, 4+5, 6, 7, 8 y el final); todos
idénticos byte a byte:

| Receptor | `receptor_sha256` de la base = después (el `informe_sha256` y el `recipe_hash` también coinciden) |
|---|---|
| 8HFI | `30e6695403f7b072cbe436daefa3479f9c8e33ee670590e5f04e01d3a7ff0e60` — IGUAL |
| 1C3R | `30bf30638c37145d815069a24fe5fa633217e23d6dd787448978db5c44541581` — IGUAL |
| 3F75 | `8b945aba2292c92ef32ff2c7a6ae3cdcf5ccd7a0d7041d4a5995bbd3d69189ff` — IGUAL |
| 5VA1 | `7f29ccf5d319bae3c31378988cc3f5c1d9291f117f862b2f4103e5af36619ee7` — IGUAL |
| 1HSG | `62f878f532434e8b7b9452d9f071de63bb45d8b4bf474927770fd130e7c62b4a` — IGUAL |

Además: `scripts/generate_goldens.py --check` (8 corridas doradas) y `generate_catalog_availability.py --check` limpios.
Receta 7 sin tocar; `check_openbabel_boundary.py`: 10 comprobaciones pasadas y 1 sin comprobar (G2, no hay bundle
staged; saltar no es aprobar).

---

## 4. Puertas (código final, python-embed 3.11.9)

| Puerta | Resultado |
|---|---|
| Suite completa del backend | **4232 pasan, 3 fallan, 36 saltadas, 2 xfail** (588 s). Los 3 fallos **ya fallan en la base `e9b032ae`** (comprobado en un worktree de la base): `test_dossier_en_espanol_no_cambia` (manifiesto de la instantánea; el AGENTS.md del árbol principal lo atribuye a reportlab 4.5.1 y dice haberlo arreglado) y las dos de `test_registro_cientifico` (falta el paper de `CAL-8HFI-01`; el árbol principal tiene un commit «Paper de CAL-8HFI-01…», no verificado aquí). La suite completa **encontró un fallo mío** (`test_codigos_de_aviso`: 8 códigos emitidos sin declarar) y quedó corregido en `faa610da`. |
| `npm run test:run` | 180 archivos, **1684 pruebas, todas pasan** (el AGENTS.md del árbol principal dice 1724 en 184: su base es posterior) |
| `npx tsc --noEmit` | limpio |
| `npm run lint` | 0 errores, 39 avisos (ninguno nuevo en los archivos tocados; `lib/api.ts:311` ya estaba) |
| `generate_goldens.py --check` | 8 corridas doradas verificadas |
| `generate_catalog_availability.py --check` | al día |
| `validar_sellos.py --check` | 168 sellados, 0 distintos, 0 ausentes |
| `report_test_counts.py --check` | 4272 recolectadas = registrado |
| `inventario_i18n.py --check` | 1632 pendientes (ratchet regenerado a 1632; ver sección 6, decisión 4) |

No se ejecutó `tauri:build`, `stage:desktop` ni `smoke:prod` (el encargo lo prohíbe).

---

## 5. Lo que NO se pudo verificar

Dicho sin adornos:

1. **Boltz, Chai-1 y AlphaFold 3: su convención de pLDDT no está verificada.** Sus repositorios oficiales no traen ningún
   archivo de salida real (los busqué; ver sección 7). La documentación de Boltz dice que el pLDDT va en [0, 1] y la de
   AlphaFold 3 que es por átomo en 0–100, pero **no dice en qué campo del CIF queda**. Por eso un archivo suyo sale
   `NO_DISPONIBLE` con ese motivo, y no se afirma ni se lee. Sólo está verificada **AlphaFold DB** (`AF-P23975-F1-model_v6`,
   PDB y mmCIF: el factor B / `B_iso_or_equiv` son el pLDDT por residuo, 0–100, y coinciden con `_ma_qa_metric_local` en los
   617 residuos). Un ModelCIF de otra fuente que declare `_ma_qa_metric_local` se lee marcándolo «declarado por el archivo,
   sin verificar».
2. **PQR de otros campos de fuerzas y de otras herramientas.** Sólo se midieron AMBER, CHARMM y PARSE de PDB2PQR 3.7.1;
   TYL06, PEOEPB y SWANSON no. El PQR en modo automático (sin `respetar`) no se midió. PDB2PQR no escribe el ligando, los
   HETATM sin parámetros ni las aguas (`--drop-water`): la caja manda. Además movió 2 de 364 átomos pesados al optimizar
   enlaces de hidrógeno (el lector no mueve ninguno).
3. **El modal no se vio en un navegador.** La subida necesita sesión y backend en marcha; levanté `next dev`, pero la ruta
   de Evaluación pide iniciar sesión y no introduje credenciales. Está cubierto por 26 pruebas de DOM (incluidas
   extensiones, origen opcional, errores y textos ES/EN), no por una revisión visual ni en Tauri.
4. **El artefacto instalado.** No hay build: no se verificó el bundle (restricción 1 de AGENTS.md). Todo lo que importa
   está en `backend/` y usa gemmi, que ya viaja en el runtime (todas las pruebas corrieron con python-embed), pero «viaja»
   no está medido sobre un instalador.
5. **Seis textos en español dentro de la versión inglesa, anteriores a este trabajo** (los marqué como ruido conocido en el
   arnés, no los arreglé): «Meeko eliminó residuos del receptor fuera del margen crítico…» y «El cristal no resolvía N
   cadena(s) lateral(es)…» (`vina_service.py`, commits `12bd2110` y `20955f15`); la lista «Cofactors or modified residues
   without…» con «(X Å de la caja, retirado)» a medias; «La entrada dejó N centro(s) quirales…» (`be1c48d9`); «2 metal atoms
   are removed…: NA (2 átomos)» y «Preparation removes … y 2 átomos metálicos…». Salen para cualquier receptor del catálogo
   con ligandos quirales sin estereoquímica o con metales junto al sitio.
6. **Un PDBQT con origen predicho** se cubre con una prueba de extremo a extremo (PDBQT preparado por la propia subida +
   su modelo de AlphaFold), pero no con Vina por el arnés.
7. **Las descargas se hicieron una vez** y las pruebas usan recortes (hashes en `alphafold_procedencia.json` y
   `pdb2pqr_procedencia.json`); un tercero que repita la descarga debería obtener los mismos hashes de los originales
   (sección 7), no de los recortes.

---

## 6. Decisiones que tomé fuera del encargo

1. **Dónde vive el modo**: un `perfil.json` por receptor propio, sólo para `USR_*`. La alternativa (un campo en la base)
   obligaba a migrar el esquema y a tocar el camino del catálogo.
2. **Las conversiones se declaran, no se esconden**: de mmCIF a PDB clásico se usa `auth_asym_id`, el primer modelo, un
   ensamblaje sólo si es representable (si no, «unidad asimétrica» con el motivo) y sustitutos `Z00…` para códigos CCD de
   más de tres caracteres; todo con la correspondencia en el informe. Un NMR con varios modelos usa el 1 y lo dice.
3. **Qué se abstiene** (decidido midiendo con Meeko/Vina reales, no a ojo): Na⁺/K⁺/Cu²⁺/Ni²⁺ junto al sitio (en PDBQT `NA` es
   un nitrógeno aceptor), especies sin plantilla o sin radio covalente. `CYM` **sí** funciona (alias de `CYX-` en Meeko:
   corrijo la afirmación del contexto del encargo de que no existía). `HSD/HSE/HSP/WAT` se traducen y se declaran; en modo
   automático un `HSD` pierde la histidina (queda declarado en `removed_residues`), que es otro defecto previo y no lo toqué.
4. **Inventario i18n**: el AST no veía los pares `(es, en)` en tupla ni las traducciones de este módulo; lo amplié y traduje las
   cadenas fijas que faltaban. Quedan 1632 pendientes (f-strings con datos que se traducen por piezas y se comprueban con
   pruebas, y mensajes internos de error). **La base ya medía 1626 contra los 1600 registrados** (el ratchet estaba
   desactualizado en la base), así que mi aumento real son +6; el registro queda en 1632.
5. **Ocho códigos nuevos en `CODIGOS_DE_AVISO`** (`DECODIFICADO_LATIN1`, `MMCIF_*`, `PDBQT_*`) para que
   `test_codigos_de_aviso` pase. Esa lista es un contrato con la interfaz y su docstring pide anunciar los cambios en el
   canal entre sesiones (`CANAL-SESIONES.md`): **no lo anuncié**; hace falta avisar a quien lleve el frontend. La interfaz
   hoy no muestra títulos por código.
6. **PQR de CHARMM**: se rechaza (`TER` y `DISU` como residuos aparte) en vez de fusionar los parches con su aminoácido. Fusionar
   exigía renombrar `OT1/OT2`, `1CB/1SG`, `HN`, `HB1/HB2`… sin una referencia verificada.
7. **`receptor.confianza_estructural` no aparece en el dossier del catálogo** (su informe no cambia), aunque el encargo dice
   que en experimentales es NO_APLICA: para receptores propios experimentales sí es NO_APLICA (con el método declarado).
8. **Frontend**: quité el envío automático al elegir el archivo (impedía adjuntar el origen antes de subir); la cadena admite texto
   libre además de A–D; `uploadCustomTarget` conserva `codigo`, `datos` y `estado` y deja el mensaje vacío si no hay texto (el
   modal pone el suyo traducido); añadí `receptor.entrada` y `receptor.confianza_estructural` al mapa de nombres de la página
   Preparación.
9. **No edité `AGENTS.md`**: el de esta rama es anterior al del árbol principal y habría un conflicto seguro; el párrafo
   propuesto va abajo.
10. **Descargas**: las autorizó el propietario («todos los que necesites, siempre y cuando sean descargas confiables y
    aisladas»). Cada una en su carpeta nueva bajo `D:\moldesign-audits\receptores-propios-20261009\descargas`, sin tocar el
    runtime ni el repositorio; PDB2PQR y PROPKA en un venv aparte (Python 3.12). En el repositorio sólo hay recortes.

---

## 7. Procedencia de lo descargado

| Qué | Origen | SHA-256 | Bytes |
|---|---|---|---:|
| `8XVK.cif` | files.rcsb.org (8XVK, ambrisentán `A1D5J`) | `2fb0293dfa8015d37959ec8cfdf621a3cc6f1a4a6d3b719a81dfa1bf06fd908e` | 876275 |
| `8ZP2.cif` | files.rcsb.org (8ZP2, `A1LX4`) | `4c0410c9833387d2ed30c33981d9eb60714906756a0115e8f0bcfbaa97f5a3c7` | 1172344 |
| `8YUT.cif` | files.rcsb.org (8YUT, `A1D67`) | `110e2940cb85e2d578e8e95b5498e1035e5a82772ad5ef0aad413535e0a534bd` | 1006201 |
| `AF-P23975-F1-model_v6.pdb` | alphafold.ebi.ac.uk (NET humano) | `8743112110ad3f60b93a957b49e1572094556e4c637c9c92961d84b5719bc30b` | 405809 |
| `AF-P23975-F1-model_v6.cif` | alphafold.ebi.ac.uk | `e2f921b2b10d499aa1f8d5aebefb3f1c53a6cee0b95c755dbb3a7e5a048fd899` | 573880 |
| `boltz_prediction.md` | github.com/jwohlwend/boltz `docs/prediction.md` | `b9cb2ff437389864bde02e7e9fd9fbcc7de189ca2e240a5f3fb6261ca595a795` | 28107 |
| `chai_README.md` | github.com/chaidiscovery/chai-lab `README.md` | `ea6f6e64f6fc73d0e3dcbe6755c2aab226fa13bad279d1213acc0217f3f5013f` | 9226 |
| `af3_output.md` | github.com/google-deepmind/alphafold3 `docs/output.md` | `bb792ca2564e5a1f48512388efc4ffda00535f8847211e095f11ce15111362fe` | 13609 |
| PDB2PQR / PROPKA | `pip install pdb2pqr propka` en venv aparte | pdb2pqr 3.7.1, propka 3.5.1 | |

Las salidas de PDB2PQR (órdenes y hashes) están en `backend/tests/data/receptores_propios/pdb2pqr_procedencia.json`; las de
AlphaFold DB, en `alphafold_procedencia.json`.

---

## 8. Párrafo propuesto para `AGENTS.md`

Sustituye al que dice «El arreglo … está en curso para 1.0.2» (al integrar):

> **Subida de receptores propios, arreglada el 2026-10-09 (rama `claude/receptores-propios`).** Tres caminos, medidos con Vina
> real por la API sobre un corpus de 36 casos: **A** estructura cruda (PDB, `.ent`, mmCIF, con cadenas de varias letras y
> códigos CCD largos con correspondencia explícita, y estructuras predichas), **B** estructura ya preparada por el equipo (se
> respetan su protonación, aguas, metales y cofactores; la protonación se declara «por el usuario», nunca se valida; PQR de
> PDB2PQR con AMBER o PARSE) y **C** PDBQT listo para Vina (se evalúa tal cual; con la estructura de origen, Preparación audita
> lo que se retiró). Los rechazos dicen qué falló y qué hacer. De una estructura predicha sólo se lee el pLDDT con la
> convención verificada de **AlphaFold DB**; Boltz, Chai-1 y AlphaFold 3 salen «no disponible» porque no hay un archivo real
> con el que comprobarla. Un pLDDT < 70 junto al sitio pide revisión y no bloquea. El catálogo no cambió: los cinco receptores de
> la prueba de invariancia dan el mismo `receptor_sha256`. No verificado: el modal en un navegador, el bundle instalado y los
> campos de fuerzas TYL06, PEOEPB y SWANSON.

---

## 9. Al integrar

1. `git merge` de `codex/release-hygiene` en esta rama (o al revés). Resolver `docs/versions/1.0.2_cambios.md` conservando las
   filas de ambos lados (sin líneas en blanco dentro de la tabla; las filas de esta rama usan `(receptores-propios P9, …)`
   sustituido por hash salvo la última).
2. Regenerar, no resolver a mano: `python scripts/report_test_counts.py --write` y `python scripts/inventario_i18n.py`
   (con python-embed).
3. Avisar en el canal entre sesiones de los 8 códigos de aviso nuevos (decisión 5).
4. Actualizar el párrafo de `AGENTS.md` (sección 8).

## 10. Reproducir

```bash
# arnés completo (backend desechable, Vina real); --raiz es el worktree
python-embed/python.exe scripts/qa_subida_receptores.py --raiz <worktree> --salida <carpeta> --casos <casos.json>
# invariancia del catálogo
python-embed/python.exe scripts/invariancia_catalogo_receptores.py --salida base.json   # con el código de la base
python-embed/python.exe scripts/invariancia_catalogo_receptores.py --salida final.json  # con esta rama
python-embed/python.exe scripts/invariancia_catalogo_receptores.py --comparar base.json final.json
```

Los casos del arnés y sus informes están en `D:\moldesign-audits\receptores-propios-20261009\` (`corpus_final.json`,
`final\informe.json`, `suite_backend_final.log`, `suite_frontend_final.log`); no se versionan porque contienen rutas de esta
máquina y archivos de terceros.
