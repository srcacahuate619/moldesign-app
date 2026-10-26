# Muestra revisada de la traducción · capa 1

Muestra aleatoria reproducible de 40 cadenas únicas catalogadas en `package.py`, `taxonomy.py`, `pdf.py` y `verify.py`. Selección: `random.Random(20261004)` sobre las cadenas únicas ordenadas por el inventario.

Revisión semántica: completada por el agente. Errores de sentido: **0/40**. Se comprobaron cautelas científicas, términos del glosario, códigos y marcadores.

### 01. `services/dossier/package.py:516`

**Español**

```text
No se declara a sí mismo: su hash cambiaría al escribirlo. Su integridad la cubre `checksums.sha256`, que se calcula después.
```

**English**

```text
It does not declare itself: its hash would change when written. Its integrity is covered by `checksums.sha256`, which is calculated afterward.
```

### 02. `services/dossier/package.py:266`

**Español**

```text
- `evidencia/pose_selector_model.json` — modelo, versión y SHA-256 del selector.
```

**English**

```text
- `evidencia/pose_selector_model.json` — selector model, version, and SHA-256.
```

### 03. `services/dossier/pdf.py:576`

**Español**

```text
El selector RECOMIENDA; no sustituye. La pose principal del producto sigue siendo la top-1 de Vina, que se conserva y se declara siempre. Cuando el selector se abstiene, falta o falla, la referencia es Vina top-1 en calidad de FALLBACK — no como un acierto del selector. El margen de confianza es la distancia entre la primera y la segunda pose según el modelo: no es una probabilidad ni una nota.
```

**English**

```text
The selector RECOMMENDS; it does not replace. The product's primary pose remains Vina top-1, which is always retained and declared. If the selector abstains, is missing, or fails, the reference is Vina top-1 as a FALLBACK—not as a selector success. The confidence margin is the distance between the first and second pose according to the model; it is not a probability or a score.
```

### 04. `services/dossier/taxonomy.py:90`

**Español**

```text
Hay evidencia, pero no autoriza una conclusión por sí sola.
```

**English**

```text
Evidence is available, but it does not support a conclusion on its own.
```

### 05. `services/dossier/pdf.py:491`

**Español**

```text
Aplica a los inputs actuales
```

**English**

```text
Applies to current inputs
```

### 06. `services/dossier/pdf.py:206`

**Español**

```text
Página {n1} de {n2}
```

**English**

```text
Page {n1} of {n2}
```

### 07. `services/dossier/package.py:390`

**Español**

```text
lectura humana del caso
```

**English**

```text
human-readable view of the case
```

### 08. `services/dossier/verify.py:202`

**Español**

```text
Ruta insegura en el manifiesto `{n1}`: {n2}.
```

**English**

```text
Unsafe path in manifest `{n1}`: {n2}.
```

### 09. `services/dossier/package.py:397`

**Español**

```text
evidencia estructural, selección y controles
```

**English**

```text
structural evidence, selection, and checks
```

### 10. `services/dossier/verify.py:278`

**Español**

```text
`{n1}` no aparece en `{n2}`.
```

**English**

```text
`{n1}` does not appear in `{n2}`.
```

### 11. `services/dossier/pdf.py:693`

**Español**

```text
16. Glosario de estados
```

**English**

```text
16. Status glossary
```

### 12. `services/dossier/package.py:330`

**Español**

```text
No es una recomendación. No afirma que la molécula sea un fármaco, un candidato
clínico ni un compuesto seguro. Los índices 0-100 que aparecen en el apéndice
del PDF no son probabilidad, confianza ni calidad, y no son decisionales.
```

**English**

```text
This is not a recommendation. It does not claim that the molecule is a drug, clinical candidate, or safe compound. The 0–100 indices in the PDF appendix are not probability, confidence, or quality measures, and they are not decision criteria.
```

### 13. `services/dossier/package.py:335`

**Español**

```text
El verificador comprueba, sin extraer ni ejecutar nada: que ninguna entrada
escape del directorio raíz, que el manifiesto sea de una versión compatible,
que todos los archivos declarados existan, que sus SHA-256 y tamaños coincidan,
que no haya duplicados y que no haya archivos no declarados.
```

**English**

```text
Without extracting or running anything, the verifier checks that no entry escapes the root directory, the manifest version is supported, all declared files exist, their SHA-256 hashes and sizes match, and there are no duplicates or undeclared files.
```

### 14. `services/dossier/package.py:260`

**Español**

```text
- `evidencia/pose_index.json` — qué pose es cuál y a qué bloque PDBQT exacto
  apunta. `outputs/poses.sdf` aparece además sólo cuando representa de verdad
  la colección; en un ensemble no se finge que el SDF de una conformación sea
  la piscina completa.
```

**English**

```text
- `evidencia/pose_index.json` — which pose is which and the exact PDBQT block it points to. `outputs/poses.sdf` is included only when it truly represents the collection; for an ensemble, a single-conformation SDF is not presented as the full set.
```

### 15. `services/dossier/package.py:362`

**Español**

```text
Un archivo ausente se declara; no se sustituye por un marcador que parezca el
artefacto.
```

**English**

```text
A missing file is declared; it is not replaced with a marker that looks like the artifact.
```

### 16. `services/dossier/package.py:305`

**Español**

```text
- No afirma que el compuesto sea activo, eficaz, seguro ni un candidato a
  fármaco. Nada en este paquete sostiene esa clase de conclusión.
```

**English**

```text
- It does not claim that the compound is active, effective, safe, or a drug candidate. Nothing in this package supports that kind of conclusion.
```

### 17. `services/dossier/package.py:392`

**Español**

```text
índice ordenado de hashes
```

**English**

```text
sorted hash index
```

### 18. `services/dossier/pdf.py:307`

**Español**

```text
Observación y protocolo
```

**English**

```text
Observation and protocol
```

### 19. `services/dossier/package.py:391`

**Español**

```text
rol, tamaño, SHA-256 y estado de cada archivo
```

**English**

```text
role, size, SHA-256, and status of each file
```

### 20. `services/dossier/package.py:318`

**Español**

```text
Ninguno: todos los artefactos declarados están presentes.
```

**English**

```text
None: all declared artifacts are present.
```

### 21. `services/dossier/package.py:290`

**Español**

```text
- No garantiza que el resultado sea reproducible bit a bit: eso depende de la
  versión del motor y del hardware.
```

**English**

```text
- It does not guarantee bit-for-bit reproducibility; that depends on the engine version and hardware.
```

### 22. `services/dossier/pdf.py:603`

**Español**

```text
10. Controles físicos y geométricos
```

**English**

```text
10. Physical and geometric checks
```

### 23. `services/dossier/verify.py:214`

**Español**

```text
`{n1}` se declara `{n2}` pero el paquete SÍ lo contiene.
```

**English**

```text
`{n1}` is declared as `{n2}`, but the package contains it.
```

### 24. `services/dossier/verify.py:105`

**Español**

```text
ruta con unidad de disco
```

**English**

```text
path with a drive letter
```

### 25. `services/dossier/package.py:250`

**Español**

```text
3.1. La evidencia estructural, en crudo
```

**English**

```text
3.1. Raw structural evidence
```

### 26. `services/dossier/package.py:288`

**Español**

```text
4. Qué NO garantiza este paquete
```

**English**

```text
4. What this package does NOT guarantee
```

### 27. `services/dossier/pdf.py:362`

**Español**

```text
Alternativa válida
```

**English**

```text
Valid alternative
```

### 28. `services/dossier/pdf.py:413`

**Español**

```text
Dossier de evidencia computacional
```

**English**

```text
Computational evidence dossier
```

### 29. `services/dossier/package.py:341`

**Español**

```text
1. **El ZIP no se contiene a sí mismo.** Un paquete que llevara su propia copia
   no podría cerrarse: su hash cambiaría al incluirlo.
```

**English**

```text
1. **The ZIP does not contain itself.** A package containing its own copy could not be finalized: its hash would change when included.
```

### 30. `services/dossier/package.py:566`

**Español**

```text
cliente (proyección validada)
```

**English**

```text
client (validated projection)
```

### 31. `services/dossier/package.py:233`

**Español**

```text
3. Repetir el acoplamiento
```

**English**

```text
3. Repeat the docking run
```

### 32. `services/dossier/package.py:345`

**Español**

```text
2. **`checksums.sha256` no se hashea a sí mismo.** Escribir su hash dentro de sí
   mismo es imposible por la misma razón.
```

**English**

```text
2. **`checksums.sha256` does not include its own hash.** Writing its hash into the file is impossible for the same reason.
```

### 33. `services/dossier/package.py:393`

**Español**

```text
proyección del caso y modelo canónico
```

**English**

```text
case projection and canonical model
```

### 34. `services/dossier/pdf.py:697`

**Español**

```text
Los índices siguientes los calcula el pipeline por compatibilidad con lecturas anteriores. <b>No son decisionales.</b> No son probabilidad, ni confianza, ni calidad, y no deben usarse para comparar moléculas ni para priorizar trabajo experimental.
```

**English**

```text
The following indices are calculated by the pipeline for compatibility with earlier reports. <b>They are not decision criteria.</b> They are not probability, confidence, or quality measures, and should not be used to compare molecules or prioritize experimental work.
```

### 35. `services/dossier/pdf.py:210`

**Español**

```text
MolDesign · dossier de evidencia computacional · no es una recomendación clínica
```

**English**

```text
MolDesign · computational evidence dossier · not a clinical recommendation
```

### 36. `services/dossier/pdf.py:649`

**Español**

```text
15. Procedencia e instrucciones de verificación
```

**English**

```text
15. Provenance and verification instructions
```

### 37. `services/dossier/verify.py:110`

**Español**

```text
componente `..` (escape de directorio)
```

**English**

```text
`..` component (directory traversal)
```

### 38. `services/dossier/verify.py:260`

**Español**

```text
Línea mal formada en `{n1}`: {n2}
```

**English**

```text
Malformed line in `{n1}`: {n2}
```

### 39. `services/dossier/verify.py:89`

**Español**

```text
(no determinada)
```

**English**

```text
(undetermined)
```

### 40. `services/dossier/pdf.py:573`

**Español**

```text
8. Selección de pose
```

**English**

```text
8. Pose selection
```
