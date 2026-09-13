# REC-12

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Los cofactores no metalicos del sitio -HETATM que no son ni agua ni metal, como NAD, FAD o hemo, y tambien aditivos de cristalizacion como glicerol o sulfato- son el eje de especificacion que nadie ha inventariado, y podrian explicar los cristales que REC-09 encontro puntuando absurdo con CERO aguas bloqueantes: 1d7i y 1ew9.

## Protocolo

Referencia: `Metodo identico al de REC-08-EXT, tercera entidad. Sitio a 8 A de un atomo pesado del ligando cristalografico -el radio de FEP-02-; emparejamiento entre original y preparado POR COORDENADA con tolerancia de 0.5 A, porque la preparacion renumera. Fuente del original: data/pdbbind/<pid>/<pid>_protein.pdb, la misma que uso REC-08-EXT. Script: scripts/analisis_rec12_cofactores.py. G1 de validez de la fuente anadido tras el primer intento: la fuente debe contener HETATM no-agua no-metal en algun sitio de la estructura, porque si no los contiene un inventario de cero seria del ARCHIVO y no de las estructuras.`

## Gate

INVENTARIO SIN GATES DE DECISION, con UN GATE DE VALIDEZ DE LA FUENTE. G1: fraccion de complejos cuyo <pid>_protein.pdb contiene algun HETATM que no sea agua ni metal, en cualquier posicion de la estructura. Minimo 0.05 para que el inventario se pueda leer. Si G1 falla, el cero medido NO es un hecho sobre las estructuras sino sobre el archivo, y el inventario NO SE LEE. LIMITACION DECLARADA: no clasifica cofactor funcional frente a aditivo de cristalizacion -esa distincion es quimica y por complejo-; no decide sobre 1d7i ni 1ew9; el emparejamiento por coordenada hace que los recuentos de perdida sean cota superior.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `f4728ae7fb7cada83af63136d81bc829716e9611`, dirty=True

## Estado

- Creado: 2026-08-20T22:40:14.011968+00:00
- Status: finished
- Decisión: INCONCLUSIVE
- Sellado: sí (2026-08-20T22:40:14.838142+00:00)
- Finalizado: 2026-08-20T22:40:35.204188+00:00
- Razón de la decisión: G1 DE VALIDEZ DE LA FUENTE FALLA: 1 de 48 = 0.0208, por debajo del minimo de 0.05. EL INVENTARIO NO SE LEE, y el hallazgo es por que. La fuente del programa para la estructura original es data/pdbbind/<pid>/<pid>_protein.pdb, y PDBBind entrega ahi una estructura LIMPIADA: conserva aguas y metales y ELIMINA el resto de heteroatomos. Verificado sobre los 48 disponibles: los unicos resnames HETATM en el conjunto entero son HOH (8844 atomos), CA (22), ZN (15), MG (6), HG (1), CU (1) y ACE (6), y ACE es un grupo acetilo de cierre de cadena, no un cofactor. El cero de cofactores que el primer intento produjo era del ARCHIVO, no de las estructuras. LO QUE ESTO SI ESTABLECE, Y NO ES MENOR: todos los receptores del programa se construyeron desde una fuente que elimina los cofactores no metalicos. Si algun complejo de la cohorte necesita un NAD, un FAD o un hemo para que su sitio este completo, ese receptor esta incompleto Y NADIE PODRIA VERLO CON LOS DATOS ACTUALES, porque la evidencia se pierde en el mismo archivo del que se parte. Eso es exactamente un defecto de especificacion del tipo que REC-08-EXT y REC-09 vinieron destapando, con el agravante de que aqui el instrumento de deteccion tambien esta ciego. NO SE ESTABLECE que haya cofactores perdidos: no se ha medido ninguno, ni a favor ni en contra. LA PREGUNTA DE REC-09 SIGUE ABIERTA: 1d7i y 1ew9 puntuan absurdo con cero aguas bloqueantes, y esta via no los explica ni los descarta. QUE HARIA FALTA PARA MEDIRLO: la entrada original de RCSB de cada complejo, no el protein.pdb de PDBBind. Son 116 descargas y el analisis es el mismo script sin tocar; el bloqueo es de datos, no de metodo. Se deja anotado como deuda con su coste. LIMITE ADICIONAL descubierto de paso: el servidor solo tiene 48 de los 116 <pid>_protein.pdb -el local tiene 3887 archivos de PDBBind-, asi que incluso con una fuente valida habria que sincronizar antes. Ninguno de los dos problemas se arregla con computo.
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
