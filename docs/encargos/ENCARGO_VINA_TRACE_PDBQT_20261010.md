# Encargo: `vina_trace.exe` rechaza un PDBQT que `vina.exe` acopla

Fecha: 2026-10-10 · rama `codex/release-hygiene` (HEAD `039d9858`) · encontrado durante la auditoría de
Preparación ([informe](https://claude.ai/artifact/Jd2jgmd9ncLiFbnFMj7ofC)).

Lee `AGENTS.md` antes de empezar. No edites `scripts/artifacts_science/` y no empujes nada.

## Qué pasa

La evaluación de **1HSG (proteasa del VIH-1, cadenas A+B) + indinavir** termina en
`DockingFailed: … (Vina exit code: 1)`. El usuario no ve la causa: el estado de la tarea sólo trae el
código de salida, aunque el stderr de Vina queda escrito en el `vina.log` de la corrida.

`backend/services/docking/vina_service.py::_run_vina_subprocess` llama a
`services/docking/search_trace.instrumented()`, que sustituye `tools/vina/vina.exe` por
`tools/vina/vina_trace.exe` siempre que `tools/vina/vina-trace-manifest.json` coincide con el binario de
referencia. Es el binario instrumentado que alimenta la traza de búsqueda de Molcy.

Medido a mano con los mismos archivos que generó el pipeline:

| Binario | Versión | Resultado |
|---|---|---|
| `tools/vina/vina_trace.exe` | `AutoDock Vina v1.2.7-trace` | exit 1 · `PDBQT parsing error: Unknown or inappropriate tag found in flex residue or ligand. > ENDBRANCH  39  41` |
| `tools/vina/vina.exe` | `AutoDock Vina v1.2.7` | exit 0 · 9 poses, mejor −10,3 kcal/mol (exh 1) y −9,4…−10 (exh 8, semilla 42) |

Argumentos del pipeline: `--exhaustiveness 8 --num_modes 9 --cpu 4 --seed 42`, caja centro
`(13.073, 22.467, 5.557)`, lado 25 Å. La traza necesita `VINA_TRACE_PREFIX` apuntando a una carpeta.

## El ligando

- SMILES de entrada: `CC(C)(C)NC(=O)[C@@H]1CN(Cc2cccnc2)CCN1C[C@@H](O)C[C@@H](Cc1ccccc1)C(=O)N[C@@H]1c2ccccc2C[C@@H]1O`
- Meeko lo preparó como dicatión (las dos aminas de la piperazina protonadas), 51 átomos, `TORSDOF 14`.
- Ramas anidadas en el PDBQT: `BRANCH 1 28 > 28 29 > 29 37 > 39 41 > 43 50`. El error aparece al cerrar
  `BRANCH 39 41`, que contiene un indano (anillo fusionado) y anida la rama `43 50` (el OH del indanol).
  Hipótesis sin comprobar: el parser del binario instrumentado trata distinto una rama anidada a esa
  profundidad, o una rama cuyo primer átomo cierra un anillo.

## Cómo reproducirlo

1. Levanta un backend con datos temporales. El arnés de la puerta 12 sirve:
   `scripts/accept_evaluation_runtime.py` (`entorno_runtime`, `_start_backend`, `_auth`, `_projection`).
2. Preflight y submit de 1HSG, cadena A, con el SMILES de arriba y la configuración por defecto.
3. El receptor preparado queda en `data/targets/1HSG/prepared-*.pdbqt` y el ligando en
   `data/ligands/<hash>/vina_input.pdbqt` (el de 51 átomos).
4. Ejecuta los dos binarios con los argumentos de arriba y compara.

## Qué hay que hacer

1. Encontrar por qué `vina_trace.exe` parsea distinto de `vina.exe`. Las fuentes y el commit de origen
   están declarados en `tools/vina/vina-trace-manifest.json` (`upstream_commit`, `source_files`).
2. Medir cuántos ligandos afecta: preparar con Meeko un conjunto con ramas profundas o anidadas
   (macrociclos, péptidos cortos, inhibidores de proteasa del catálogo: 1HSG, 1RV7, 2BQV, 3S43, 4NJT…) y
   pasar los dos binarios.
3. Arreglarlo. Si el código del binario de traza está en el repositorio, recompilarlo y actualizar su
   manifiesto. Si no, una salida segura: reintentar con `vina.exe` y declarar en la corrida que esa
   corrida no tiene traza de búsqueda (Molcy la necesita), nunca en silencio.
4. Que el error de Vina llegue al usuario: hoy `DockingFailed` guarda el stderr en `detail`, pero el
   estado de la tarea sólo enseña «Vina exit code: 1».
5. Una prueba de regresión con este ligando, y la fila en `docs/versions/1.0.2_cambios.md`.

## Por qué importa

La proteasa del VIH es el caso de libro de sitio entre cadenas y una diana clásica de FEP. Con este
fallo, ninguna corrida de ese tipo llega a la pestaña Preparación.

## Resultado (2026-10-10)

Cerrado en `8104f7d0` (traza) y `437672e8` (el error de Vina en el estado de la tarea). La hipótesis
de las ramas no se sostuvo: el parser es el de upstream y leía el archivo entero. La causa era
`get_file_contents` (`utils.cpp`), que lee en modo texto un PDBQT con CRLF; desde 4096 bytes, el
runtime de MinGW dejaba bytes viejos del archivo al final del búfer, donde `vina.exe` deja ceros.
Fallaba en 51 de 345 ligandos de PDBbind preparados como el producto (14,8 %); ahora en ninguno.
Medidas, alcance y verificación en `docs/TRAZA_BUSQUEDA_MOLCY.md` («Ligandos con CRLF de 4096
bytes o más»). 1HSG + indinavir por la API: −10,395 kcal/mol, con traza, llega a Preparación.

El runtime base publicado (`runtime-base-v1.1.1.zip`) no trae `vina_trace.exe`, así que un clon
aprovisionado con él no acoplaba nada desde el 10-05; se reconstruye como v1.1.2.
