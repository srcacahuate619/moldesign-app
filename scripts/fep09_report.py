"""Escribe informe público y expediente desde las métricas, nunca desde memoria."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "scripts/artifacts_science/FEP-09-SENSIBILIDAD"


def percent(value):
    return "no medible" if value is None else f"{100*value:.2f} %".replace(".", ",")


def ci(values):
    return "no estimable" if values[0] is None else f"[{values[0]:.3f}; {values[1]:.3f}]".replace(".", ",")


def main():
    metrics = json.loads((ART / "metrics.json").read_text(encoding="utf-8"))
    verification = json.loads((ART / "verification.json").read_text(encoding="utf-8"))
    plan = json.loads((ART / "inventory.json").read_text(encoding="utf-8"))
    rows = [json.loads(l) for l in (ART / "per_complex.jsonl").read_text(encoding="utf-8").splitlines() if l]
    assert metrics["n_terminal"] == metrics["n_planned"] == len(rows), "No redactar como completo un estudio incompleto"
    assert verification["n_expected"] == len(rows)
    cats = metrics["categories"]
    table = ["| Categoría | n | Auditor | Detectado antes | IC 95 % ruta | Decisión / alcance |", "|---|---:|---:|---:|---|---|"]
    for category, data in cats.items():
        scope = data["decision"] if data["coverage"] == "declared" else "límite" if data["coverage"] == "limit" else "proxy"
        table.append(f"| {category} | {data['n_applicable']} | {data['detections_by_auditor']} | {data['detected_before']} | {ci(data['cp95_route'])} | {scope} |")
    table = "\n".join(table)
    alarms, noise = metrics["false_alarm"], metrics["baseline_noise"]
    proof = verification["context_reproduction"]
    ncontext = sum(n for key, n in verification["context_reference_counts"].items() if key.startswith("NO_EVALUADO: ") and "receta no coincide" in key)
    outcomes = metrics["outcomes"]
    controls_spatial = [c for c in alarms["controls"] if c["category"] == "hueco_lejano"]
    spatial_bad = sum(c["n_unexpected_changes"] for c in controls_spatial)
    noisy = ", ".join(f"{k} ({v})" for k, v in noise["changed_by_requirement"].items()) or "ninguno"
    commit_noise = noise["changed_by_requirement"].get("procedencia.commit", 0)
    commit_alarms = sum(d["requirement"] == "procedencia.commit" for c in alarms["controls"]
                        if c["category"] == "seriales_renumerados" for d in c["unexpected"])
    pub = []
    for source in plan["public_sources"]:
        found = [r for r in rows if r["arm"] == "C" and r["target"] == source["target"]]
        key = {"especie_del_ligando": "ligando.especie", "estereoquimica_del_ligando": "ligando.estereoquimica"}.get(source["category"])
        observed = "Sin registro con el nombre indicado en el commit fijado"
        if found:
            descriptions = []
            for r in found:
                req = next((q for q in r["requirements"] if q["clave"] == key), None)
                detail = f"{key}={req['estado']}, {req.get('valor') or req.get('razon') or 'sin detalle'}" if req else "sin requisito declarado de identidad del constructo experimental"
                descriptions.append(f"{r['ligand']}: {detail}; global {r['global_state']}")
            observed = "; ".join(descriptions)
        pub.append(f"| {source['target']} | [{source['ligand'] or 'construcción del receptor'}]({source['url']}) | {source['summary']} | {observed} |")
    public_table = "\n".join(["| Diana | Fuente abierta | Qué comunica la fuente | Observación de esta versión |", "|---|---|---|---|"]+pub)
    fep08 = []
    for target in ("cdk2", "thrombin", "tnks2"):
        row = next(r for r in rows if r["case_id"] == f"{target}__baseline__0")
        req = {r["clave"]: r for r in row["requirements"]}
        prep = row["docking_protocol"]["execution_provenance"]["receptor_prep"]
        fep08.append(f"| {target} | {req['receptor.huecos']['estado']}: {req['receptor.huecos'].get('valor')} | {'+'.join(prep.get('site_chains') or [prep.get('chain')])} |")
    concordance = "\n".join(["| Diana | Huecos físicos que declara Preparación | Cadenas del sitio declaradas |", "|---|---|---|"]+fep08)
    limitations = "\n".join(f"- {l}" for l in metrics["no_demuestra"])
    paper = f'''---
titulo: "Preparación detecta cortes del sitio; la sensibilidad completa queda abierta"
entradilla: "Un ensayo pareado por la API, con 15 dianas de OpenFF, defectos sembrados y controles independientes. Resultado {metrics['decision']}: la tabla conserva las detecciones, los límites y una comprobación de origen que no reconoce la receta de receptores ya preparados."
---

**{metrics['decision']}.** Se completaron {len(rows)} intentos confirmatorios:
{outcomes.get('audited', 0)} auditados, {outcomes.get('detected_before', 0)} rechazados antes
de Preparación y {outcomes.get('infrastructure_failure', 0)} fallos de infraestructura.
El piloto de ocho corridas se conserva aparte y no entra en estas cifras.

MolDesign pretende comunicar qué evidencia estructural produjo una corrida
y dónde debe abstenerse. Un control positivo sobre estructuras preparadas
por expertos, como FEP-08, no demuestra que la pestaña Preparación reaccione
a defectos. Este experimento mide esa reacción por requisito, sin ejecutar
energía libre ni cambiar el producto para mejorar su resultado.

## Qué se midió

Producto `f183e0af`, Python embebido 3.11.9, Meeko 0.7.1, camino B
(`respetar`, receta B versión 1, distinta de la receta automática 7), Vina
1.2.7, exhaustividad 8, nueve poses solicitadas, semilla 42, pH 7,4,
un confórmero y modo tautomérico efectivo `entrada`. Se usaron tres cápsulas
aisladas, cuatro núcleos por Vina, con datos y perfiles propios. No se
ejerció el frontend externo ni el instalador.

Benchmark de OpenFF en commit
`fd88824f9114244f95a14b485e6d6c96c1de716d`: 15 dianas con PDB y SDF en
las rutas prescritas, de las 21 entradas en targets.yml. Se excluyeron seis
por archivos ausentes, antes de ver resultados. Se eligió el primer registro
SDF legible por diana; la caja fija de 20 Å por lado se centró en sus átomos
pesados. Los archivos permanecen en el clon externo; aquí se conservan
nombres, hashes, intervenciones y respuestas.

Para cada diana se repitió tres veces una subida y preparación independiente
de la línea base. Cada variante del brazo A cambia una característica: cortes
del esqueleto, cadena o especie ausente, estado químico o protonación local.
Los generadores usan geometría directa y RDKit, sin importar las funciones
del producto. La ruta fue upload → preflight → submit → status → result →
POST preparacion, conservando estados y datos de todos los requisitos.

El [prerregistro](../auditorias/FEP-09-prerregistro.md) se fijó en
`9cdd0eab826bbbbe10d9b2469c52fbd0a0cf1638` antes de la primera corrida.
Una alerta ya presente en la base no cuenta como detección. Para categoría
declarada con n≥8 se exige límite inferior del IC exacto bilateral 95 %
de Clopper–Pearson ≥0,5 y falsa alarma de controles inocuos ≤0,10. Las
categorías con n insuficiente quedan INCONCLUSIVE; no se retiran del gate.

**Desviación declarada.** El prerregistro llama «canónico» al modo por
defecto, pero el arnés no especificó ese parámetro y la API de f183e0af
aplicó `entrada`, como muestran preflight y ligand_state. Esa descripción
era incorrecta; no se modificaron las peticiones entre brazos ni se
reintentaron corridas. El texto preregistrado queda intacto. Las métricas
describen la condición efectiva y el cierre queda INCONCLUSIVE; los
proxies no validan minoría tautomérica ni el comportamiento bajo un modo
canónico forzado.

## Qué salió

{table}

El gate global exige que todas las categorías declaradas pasen. Estereoquímica
tiene n=3; minoría tautomérica y especie con pKa independiente, n=0.
Aunque una categoría suficiente pase, estas tres quedan INCONCLUSIVE.

«Auditor» cuenta un aumento de riesgo del requisito esperado respecto a su
base, con el mínimo preregistrado; «detectado antes» guarda el rechazo
explícito anterior. Las tasas de los límites y proxies son respuestas al
ensayo, no sensibilidad bajo una cobertura que el producto no declara.
`metrics.json` conserva también saturación, ausencias, casos evaluables y
cambios colaterales, sin excluirlos para favorecer una tasa.

Hay saturación previa en {cats['cadena_del_sitio_ausente']['n_baseline_saturated']}
caso de cadena, {cats['especie_opuesta_proxy']['n_baseline_saturated']} de especie
proxy y {cats['protonacion_del_sitio']['n_baseline_saturated']} de protonación
del receptor: su aviso base ya alcanza el mínimo, sin incremento atribuible
a la intervención. Esos casos permanecen en el denominador descriptivo.

La falsa alarma de renumeración inocua fue {alarms['n_changed']}/
{alarms['n_requirements']} requisitos comparables ({percent(alarms['rate'])}).
El acuerdo de las bases fue {percent(noise['agreement'])}, sobre
{noise['n_comparable']} comparaciones; cambiaron {noise['n_changed']}.
Requisitos no reproducibles por estado o riesgo: {noisy}.
Las tres bases conservan un hash único de receptor por diana:
{sum(v == 1 for v in verification['baseline_receptor_distinct_hashes'].values())}/15.

En {commit_noise} comparaciones de base y {commit_alarms} de renumeración
cambió `procedencia.commit` entre REGISTRADO y NO_DISPONIBLE. El producto
declara commit sólo con árbol general limpio
(`vina_service.py::_source_commit`); los scripts y metadatos de este
experimento se editaron y commitearon durante la fase larga, con diff de
producto vacío. Las razones registradas explican esa ausencia por árbol
modificado. Se mantienen estos cambios en el conteo preregistrado y se
declara el factor de confusión: no prueban variación de química o de
preparación, ni son evidencia de no determinismo de protonación.

Los {len(controls_spatial)} cortes lejanos son un control espacial, con
{spatial_bad} cambios no previstos entre requisitos comparables. El
prerregistro permite revisión de esos extremos nuevos: el producto la
declara aun lejos del sitio. Esa revisión legítima no se presenta como una
falsa alarma ni se confunde con bloquear la cavidad.

## Una comprobación de procedencia que falla

La referencia de distancias quedó sin evaluar por discrepancia de receta
en {ncontext}/{outcomes.get('audited', 0)} auditorías de este camino B. En la reproducción mínima de cdk2,
el archivo de origen existe y el hash del receptor se verifica; la receta B
recalculada coincide con la registrada. Sin embargo, el comprobador del origen
usa la fórmula de la receta automática y concluye que no coincide.

La auditoría lo declara en `entorno.referencia`: «NO_EVALUADO». Por eso los
otros requisitos usan la caja como referencia y no pueden ofrecer toda la
geometría al ligando que declaran cuando reconocen el origen. El expediente
separa este defecto de las especies borradas **antes** del upload: el auditor
declara el diff que MolDesign produce, no reconstruir un origen que no recibió.
No se aplicó ningún parche durante el experimento.

## Concordancia descriptiva con FEP-08

{concordance}

FEP-08 marcó saltos de numeración en cdk2 y thrombin, y un sitio entre cadenas
en tnks2. Un salto de numeración no prueba un corte físico. Además, aquí se
observa la preparación de MolDesign por API y su referencia efectiva de caja.
Esta comparación no entra al gate ni convierte documentabilidad preliminar
en readiness de un cálculo posterior.

## Lo publicado por terceros

{public_table}

Se abrieron las incidencias el 2026-10-11. Son preocupaciones públicas y
preguntas, no demostraciones de que los curadores se equivocaron. El estado
de la versión fijada debe contrastarse por separado: por ejemplo, su
tnks2 lig_7 contiene [nH] neutro en la representación leída, y eg5 aporta
un registro con el nombre buscado. Con cuatro preocupaciones y tres
registros medidos, el brazo C es no concluyente y no tiene tasa.

## Qué no dice

{limitations}

No se verificó una población independiente para llamar minoritario a cada
alternativo RDKit ni un pKa individual que cumpla distancia >3 a pH 7,4.
Estas dos categorías estrictas tienen n=0 verificable; los proxies se
publican por separado. Tampoco se validó el carácter catalítico de cada
Asp/Glu intervenido, ni la correspondencia de numeración TYK2–4GIH.

## Consecuencia y reproducción

El resultado conserva qué categorías discriminan y cuáles quedan abiertas.
La comprobación del origen de modo B necesita un encargo de corrección
separado, y la cobertura química necesita una cohorte con estados verificados
independientemente. No se cambia el producto de 1.0.2 ni se publica la rama.

Manifiesto, datos agregados, shards y verificación:
`scripts/artifacts_science/FEP-09-SENSIBILIDAD/`.
Arnés: `scripts/fep09_inputs.py`, `fep09_run.py`, `fep09_analyze.py`,
`fep09_verify.py`, `fep09_reproduce.py`. El analizador incluye autotest
positivo y negativo; sus IC se contrastaron con scipy.stats.beta en 5.150
combinaciones, tolerancia 1e-9. La producción usa biblioteca estándar.

Datos CC BY 4.0 de OpenFF, atribuidos a
[Hahn et al., LiveCoMS 2022](https://doi.org/10.33011/livecoms.4.1.1497),
*Best Practices for Constructing, Preparing, and Evaluating Protein-Ligand
Binding Affinity Benchmarks*. Código del benchmark MIT. El clon externo y
su obtención están declarados en sellos_no_distribuidos.json.
'''
    (ROOT / "docs/papers/FEP-09-SENSIBILIDAD.md").write_text(paper, encoding="utf-8", newline="\n")
    audit = f'''# Preparación: sensibilidad medida el 2026-10-11

Producto `f183e0af`. Experimento FEP-09-SENSIBILIDAD, decisión
**{metrics['decision']}**, preregistro `9cdd0eab826bbbbe10d9b2469c52fbd0a0cf1638`.
{len(rows)} intentos confirmatorios, {outcomes.get('audited', 0)} auditorías,
{outcomes.get('detected_before', 0)} rechazos anteriores y
{outcomes.get('infrastructure_failure', 0)} fallos. Camino B respetar, receta
B versión 1, Meeko 0.7.1, Vina 1.2.7, 8/9/42, pH 7,4, tres cápsulas CPU=4.
No se cambió el producto; no hay parches en este expediente.

## FEP09-P01 — El comprobador de origen no reconoce la receta de modo B

**Cobertura declarada: sí. Severidad propuesta: P1.**
Preparación declara geometría respecto al ligando cuando el origen es
comprobable. El origen existe y su receta respetando coincide, pero la
comprobación usa receptor_recipe_hash de modo automático. Se pierde contexto
de distancias, puentes de agua, secuencia y otras medidas; se usa la caja.
Es una discrepancia de contratos de hash, no evidencia de manipulación del
archivo ni un fallo de docking.

Reproducción mínima: `{proof['case_id']}`.
Task original: `{proof['task_id']}`.
Entrada: `{proof['uploaded_input_sha256']}`.
Raw normalizado: `{proof['normalized_raw_sha256']}`.
Receptor: `{proof['prepared_sha256']}`.
Receta B registrada y recalculada: `{proof['recorded_recipe_hash']}`.
Receta automática sin marca de H contradictorios:
`{proof['automatic_recipe_recomputed_no_contradictory_h']}`.

Solicitud y respuestas exactas en
`{next(r['evidence_dir'] for r in rows if r['case_id'] == proof['case_id'])}/`:
upload_request.json, preflight_request.json, submit_request.json,
projection.json, result_metadata.json y preparacion.json.
La llamada final es `POST /evaluation/dossier/{{molecule_id}}/preparacion`,
con projection.json, después del status SUCCESS y result persistido.
Archivos originales se obtienen del clon PLB fijado; no se distribuyen aquí.

Esperado: `entorno.referencia` REGISTRADO tras reconocer la receta B.
Observado: `{proof['observed_reference']['estado']}`,
`{proof['observed_reference'].get('razon')}`.
Contratos del producto leídos: preparer_respetando.py::receta_respetando y
contexto_estructural.py::origen_comprobado. La verificación stdlib conserva
los documentos canónicos y hashes relevantes en verification.json.

## Límites, sin presentarlos como defectos de contrato

| ID | Intervención y requisito | Cobertura declarada | Severidad |
|---|---|---|---|
| FEP09-L01 | Cadena borrada antes de upload, receptor.cadenas_excluidas | Registra exclusión hecha por el preparador, no reconstruye una cadena ausente del origen | Sin severidad de bug; limitación de alcance |
| FEP09-L02 | Metal/cofactor borrado antes de upload, entorno.metales_cofactores | Diff del origen recibido frente a preparación; no origen histórico no aportado | Sin severidad de bug |
| FEP09-L03 | Agua puente borrada antes de upload, entorno.aguas | No infiere agua ausente del archivo recibido ni su carácter estructural | Sin severidad de bug |
| FEP09-L04 | Protonación local de receptor B, receptor.protonacion | Conserva estado del usuario; expresamente no valida pH ni His/Asp/Glu del sitio | Sin severidad de bug |
| FEP09-L05 | Tautómero alternativo y especie opuesta | Proxies sin población y pKa individuales independientes; no prueban categorías estrictas | Déficit del experimento, no bug probado |
| FEP09-L06 | Identidad de la construcción experimental de TYK2 | El auditor no declara comparación con secuencia/constructo del ensayo | Sin severidad de bug; fuente pública no resuelta |

Para cada intervención ejecutada: archivos, hashes, task_id, requisito esperado,
estado base, estado observado y clasificación en per_complex.jsonl,
metrics.json::comparisons y evidence del shard correspondiente. Una revisión
genérica ya presente no se cuenta como detección. No se propone parche con
estas tasas ni se equipara no detección con error de los autores de PLB.

## Tabla y condiciones

{table}

Falsa alarma inocua: {alarms['n_changed']}/{alarms['n_requirements']}
({percent(alarms['rate'])}); acuerdo de bases {percent(noise['agreement'])}.
Cada número conserva su condición y n. El informe público detalla los
proxies, el brazo C, las exclusiones y la concordancia FEP-08.

## Reproducir sin modificar el experimento

Crear cápsula QA nueva (por ejemplo agente 4, puerto 18014) desde este
worktree; usar export externo con --out y --no-build, sin tauri:build.
Después, con el clon OpenFF verificado:

```powershell
node scripts/qa_sandbox/sandbox-up.mjs --agente 4 --capsula D:/moldesign-build/.worktrees/.sandbox/fep09-repro --out D:/moldesign-build/frontend/out --no-build --vina-cpu 4
python scripts/fep09_reproduce.py --case cdk2__baseline__0 --capsule D:/moldesign-build/.worktrees/.sandbox/fep09-repro
python scripts/fep09_reproduce.py --case cdk2__hueco_en_el_sitio__0 --capsule D:/moldesign-build/.worktrees/.sandbox/fep09-repro
```

Los resultados nuevos se escriben en tmp/fep09-reproductions, nunca en
artifacts_science. Usar Python 3.14 para el arnés; el backend de QA usa
python-embed 3.11.9. Las credenciales de la cápsula no se versionan ni se
imprimen. No se ha reproducido esta muestra una segunda vez: el comando
está preparado para la revisión independiente.
'''
    (ROOT / "docs/auditorias/preparacion-sensibilidad-2026-10-11.md").write_text(audit, encoding="utf-8", newline="\n")
    print(f"Informe y expediente escritos desde {len(rows)} registros: {metrics['decision']}")


if __name__ == "__main__":
    main()
