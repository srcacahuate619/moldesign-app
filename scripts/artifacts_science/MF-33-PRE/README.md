# MF-33-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El ensemble conformacional de MolFlex NO aporta cobertura una vez que la busqueda tiene libertad torsional: dockear UN solo conformero de forma flexible alcanza la misma cobertura que dockear los K del ensemble. Si es cierto, MolFlex no esta roto sino que es REDUNDANTE, y la cartera C no debe reabrirse. Si es falso, el ensemble si aporta y la cartera se justifica con diana medible.

## Protocolo

Referencia: `Reapertura de la cartera C bajo la 19.1 declarando cambio de GENERADOR (rigido -> flexible), no de arquitectura ni de semilla. Cohorte congelada: los 48 de MF-02F/cohorte.json (33 COLOCACION + 15 CONTROL), la misma de MF-28 y MF-25. TRES BRAZOS, todos exh=8 semilla 42 num_modes=9 caja 25 A, mismo receptor: (A) conf0.flex.pdbqt, UN solo conformero flexible; (B) todos los conf*.flex.pdbqt, REUSADO SIN RECOMPUTO del brazo de control de MF-28 -CPU ya cronometrada, 42.6 CPU-h-; (C) todos los conf*.rigid.pdbqt con regex estricta que excluye *.relax.rigid.* (leccion del corrigendum de MF-21), que es el protocolo congelado de MolFlex. ELECCION DE conf0 DECLARADA: se toma el primer conformero ETKDG por indice, SIN mirar su RMSD al cristal; elegir el mejor conformero seria informacion de oraculo y esta prohibido. Metrica: rmsd_pose_pocket sin alineamiento, oraculo por brazo (mejor pose entre todas las del brazo). CPU medida en los tres brazos. ETAPA 2 CONDICIONAL, solo si B supera a A: brazo A2, un conformero con exhaustiveness escalado hasta igualar la CPU de B por complejo, para separar 'aporta el ensemble' de 'aporta la CPU'.`

## Gate

PRIMARIO A vs B pareado sobre COLOCACION (n=33), McNemar exacto bilateral. TRES LECTURAS DECLARADAS ANTES, con margen de equivalencia porque el resultado interesante es la ausencia de diferencia y esa NO se demuestra con un test de superioridad: (1) EQUIVALENCIA / ENSEMBLE NO APORTA si el CI95 de la diferencia pareada cae ENTERO dentro de +-4 complejos (+-12 pp) — MolFlex es redundante y la cartera C NO se reabre; (2) ENSEMBLE APORTA si b>=6 con c=0 (MDE por McNemar exacto, 2*0.5^6=0.031) — la cartera se justifica y la etapa 2 pasa a ser OBLIGATORIA antes de cualquier claim; (3) NO CONCLUYENTE en cualquier otro caso, y se reporta como tal, nunca como tendencia. SECUNDARIO descriptivo sin gate: C vs A y C vs B, que cuantifican cuanto cuesta la rigidez. CANDIDATO A CORRIGENDUM DE MF-09: si C queda muy por debajo de A y B, la conclusion de MF-09 -en 30 de 33 no existe pose <=2 A- mide una limitacion del PROTOCOLO congelado y no del espacio alcanzable, y MF-09 debe corregirse. PROHIBIDO: elegir conformero por RMSD; leer el score para elegir brazo; tocar val, test o D-RC-CONFIRM.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `b5c11ab2459be03e41e23806d5cd0acb089f83eb`, dirty=True

## Estado

- Creado: 2026-08-19T18:12:21.508677+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-19T19:34:58.981828+00:00)
- Finalizado: 2026-08-19T19:34:59.148295+00:00
- Razón de la decisión: Prerregistro declarado ANTES de ejecutar: hipotesis, tres brazos, margen de equivalencia de +-4 complejos, MDE de 6 discordantes con 0 en contra, eleccion de conf0 por indice sin mirar RMSD, y etapa 2 condicional. Se sella GO por convencion al declararse, NO por haber superado nada. Deja constancia de una ambiguedad de redaccion propia: el gate escribio 'b>=6 con c=0' sin definir la direccion; se corrige reportando ambos numeros en MF-33.
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
