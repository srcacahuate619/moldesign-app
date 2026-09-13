# MF-33-DOSIS

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

En ligandos conformacionalmente dificiles, aumentar la profundidad de busqueda desde un UNICO estado tiene rendimientos decrecientes porque conformaciones iniciales distintas acceden a cuencas de pose distintas. Si es cierta, el beneficio B-A3 debe CRECER con alguna medida de dificultad conformacional computable ANTES de dockear, y esa variable permitiria una politica adaptativa: ligando sencillo docking barato, ligando dificil ensemble flexible.

## Protocolo

Referencia: `ANALISIS EXPLORATORIO SIN COMPUTO DE DOCKING, sobre artefactos sellados. Respuesta continua beneficio = rmsd_A3 - rmsd_B (positiva cuando gana el ensemble), preferida a la binaria porque los discordantes son solo 7 y la continua usa los 33. Seis predictores: torsdof del conf0.flex.pdbqt, rot_bonds de RDKit, n_conformeros K -igualado entre brazos, no circular-, diversidad como RMSD medio por pares entre conformeros del ensemble con alineamiento de Kabsch, n_heavy, y frac_vuelve de MF-14 a 0.5 A via MF-33-CRUCES, que se marca como NO PROSPECTIVO porque se mide perturbando la pose nativa. Spearman de rangos, estrato primario COLOCACION n=33, los 48 como secundario. Correccion Benjamini-Hochberg q=0.05 sobre los 6. Script: scripts/analisis_mf33dosis_cuando_hace_falta_ensemble.py.`

## Gate

EXPLORATORIO, GENERACION DE HIPOTESIS, SIN GATES DE DECISION. No autoriza cambiar ninguna politica de muestreo. EFECTO MINIMO DETECTABLE DECLARADO: via z de Fisher con alpha=0.05 y potencia 0.80, este diseno solo ve |rho| >= 0.4711 con n=33 y >= 0.3949 con n=48; por debajo de eso un nulo significa NO DETECTABLE y no INEXISTENTE, y tras el FDR sobre 6 predictores el umbral efectivo es aun mas exigente. CORRECCION MULTIPLE OBLIGATORIA: con 6 contrastes y n=33 la probabilidad de que alguno de p<0.05 bajo H0 es del 26%. VALIDACION FUERA DE MUESTRA DECLARADA ANTES DE MIRAR: MF-33-EXT esta midiendo el brazo B sobre los 116 de train, de los que 68 no estan en esta cohorte; el protocolo es que este analisis produzca un ranking, que el primero se prerregistre con direccion y umbral antes de que MF-33-EXT cierre, y que se contraste en esos 68. Ni con FDR este analisis pasa a confirmatorio: el conjunto ya se ha mirado.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `23d61aa0d70eec923051258c1c1431339b9e1e08`, dirty=True

## Estado

- Creado: 2026-08-21T02:48:16.278946+00:00
- Status: finished
- Decisión: INCONCLUSIVE
- Sellado: sí (2026-08-21T02:48:17.951643+00:00)
- Finalizado: 2026-08-21T02:48:41.580373+00:00
- Razón de la decisión: NO APARECE NINGUN PREDICTOR PROSPECTIVO. Ninguno de los seis sobrevive la correccion de Benjamini-Hochberg, y los cinco que serian utiles para una politica adaptativa estan practicamente en cero: n_conformeros rho=-0.138 p=0.4447, rot_bonds rho=-0.107 p=0.5516, n_heavy rho=-0.084 p=0.6421, diversidad rho=-0.083 p=0.6536, torsdof rho=-0.023 p=0.8989. El unico con senal cruda es frac_vuelve -rho=-0.396, p=0.0225-, que no pasa el FDR y que ademas NO ES PROSPECTIVO: se mide perturbando la pose nativa, que en produccion no existe. INCONCLUSIVE Y NO NO_GO, y la distincion importa: el MDE declarado dice que este diseno solo ve |rho| >= 0.4711 con n=33. Un efecto moderado real quedaria invisible. Lo que se puede afirmar es que NO HAY UN EFECTO GRANDE, no que no haya efecto. EL RESULTADO MAS INFORMATIVO ES EL DE LA DIVERSIDAD, y va en contra de la lectura intuitiva: rho=-0.083 entre el RMSD medio por pares del ensemble y el beneficio del ensemble. Los complejos cuyos conformeros estan mas dispersos NO se benefician mas. Si el mecanismo fuese dosis-respuesta -mas diversidad disponible, mas beneficio- esa correlacion deberia ser positiva y grande, y es cero. Sugiere que el fenomeno no es de dosis sino de acierto: hace falta EL conformero adecuado, y tener mas dispersion no lo entrega de forma fiable. Es coherente con MF-33-A3, donde multiplicar por 29 las poses desde el mismo conformero no movio un complejo. NOTA DE DIRECCION, por si se cita mal: el signo de frac_vuelve es el que la hipotesis predice -cuenca mas rugosa, o sea menor fraccion que regresa, se asocia a mayor beneficio del ensemble-. La direccion acompana; la magnitud no llega y la variable no sirve para el proposito. CONSECUENCIA PARA EL PRODUCTO: la politica adaptativa -ligando sencillo docking barato, ligando dificil ensemble- NO se puede construir hoy sobre estas seis variables. La idea sigue siendo buena y lo que falta es el predictor, no la logica. QUE SIGUE, declarado antes de mirar y ya escrito en el gate: MF-33-EXT esta midiendo el brazo B sobre los 116, de los que 68 no estan en esta cohorte. Ese conjunto permite (a) repetir esta busqueda con n mas grande y MDE mejor, y (b) validar fuera de muestra cualquier candidato que aparezca. Con n=116 el |rho| detectable baja a ~0.26. LIMITES: exploratorio y sin gates; la diversidad usa correspondencia 1:1 sin tratar simetria molecular, asi que en ligandos simetricos queda inflada y es cota superior del desorden real; no dice por que la diversidad ayuda, igual que MF-33-A3 tampoco.
- Hashes de dataset: 2 archivo(s) con SHA-256
- Hashes de assets: 1 archivo(s) con SHA-256

## Flujo de trabajo

1. `init`: crea este directorio con `manifest.json` prellenado y skeletons vacíos.
2. Ejecutar el experimento: escribir `metrics.json`, `per_complex.jsonl` y `failures.jsonl`.
3. `validate`: verifica `manifest.json` contra `manifest.schema.json`.
4. `seal`: registra los SHA-256 de datasets/modelos/binarios/assets y congela el manifest.
5. `finish`: escribe la decisión (GO/NO_GO/INCONCLUSIVE), la razón y la duración.
6. `maintain`: documenta de forma auditada los assets sellados que cambian tras el sello.

Después del `seal`, `validate` falla si cualquier archivo sellado cambia o desaparece.

## Inmutabilidad post-seal

- No se permite volver a sellar un experimento ya sellado (protege el cegamiento FND-05).
- `finish` y `maintain` son las únicas operaciones que modifican `manifest.json` después del sellado.
- `maintain` solo actualiza `assets_hashes` y registra cada cambio en `seal_maintenance`; datasets/modelos/binarios son inmutables.
- El README.md regenerado por `seal`/`finish`/`maintain` es la excepción documentada a la regla anterior.
- Los artefactos de producción permanecen fuera de este árbol (docs/49, sección 17).

## Archivos

- `manifest.json`: registro único del experimento (config, hashes, código, ambiente, salida).
- `metrics.json`: métricas agregadas del experimento.
- `per_complex.jsonl`: una línea JSON por complejo evaluado.
- `failures.jsonl`: una línea JSON por fallo.
- `README.md`: este archivo.
