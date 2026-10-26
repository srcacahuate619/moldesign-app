"""Exact and template-based translation for backend messages."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from core.i18n_catalog import ENGLISH_MESSAGES
from core.i18n_receptores_propios import PLANTILLAS as PLANTILLAS_RECEPTORES_PROPIOS

_MARCADOR = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
_SEPARAR_FRASES = re.compile(r"(?<=\.)\s+")

# Las plantillas se mantienen juntas para que el par de idiomas y sus marcadores
# se revisen como una unidad. Los valores capturados se copian sin reformatear.
PLANTILLAS_ES_EN: tuple[tuple[str, str], ...] = (
    (
        "Afinidad débil en la escala de Vina ({affinity} kcal/mol): por encima de -6 el score deja de discriminar bien entre unir y no unir, así que este resultado sirve para descartar, no para priorizar. El score de Vina ordena candidatos; no es energía libre ni se traduce a una concentración.",
        "Weak affinity on the Vina scale ({affinity} kcal/mol): above -6, the score no longer discriminates well between binding and non-binding, so this result supports exclusion rather than prioritization. The Vina score ranks candidates; it is not free energy and does not translate into a concentration.",
    ),
    (
        "Interacción Subóptima: Solo impacta el {percentage}% de los hotspots. Potencial para mejorar la afinidad mediante derivatización dirigida.",
        "Suboptimal interaction: only {percentage}% of hotspots are contacted. There is potential to improve affinity through targeted derivatization.",
    ),
    (
        "Oportunidad Crítica: Se han fallado residuos de importancia máxima ({residues}).",
        "Critical opportunity: residues of highest importance were missed ({residues}).",
    ),
    (
        "Eficiencia de ligando LE={le}. A {atoms} átomos pesados, el umbral de 0.45 se cruza con cualquier afinidad mejor que {affinity} kcal/mol, así que superarlo no distingue una unión buena de una mediocre. En este rango de masa (< 300 Da, Rule of Three) la eficiencia por átomo es alta por construcción: sirve para comparar entre moléculas del mismo tamaño, no como veredicto.",
        "Ligand efficiency LE={le}. With {atoms} heavy atoms, the 0.45 threshold is crossed by any affinity better than {affinity} kcal/mol, so exceeding it does not distinguish good binding from mediocre binding. In this mass range (< 300 Da, Rule of Three), efficiency per atom is high by construction: it can compare molecules of the same size, but cannot serve as a verdict.",
    ),
    (
        "La especie acoplada no es la entrada: {input} → {docked}. Las alternativas no evaluadas siguen siendo incertidumbre química.",
        "The docked species differs from the input: {input} → {docked}. Unevaluated alternatives remain a source of chemical uncertainty.",
    ),
    ("SHA-256 del modelo: {hash}.", "Model SHA-256: {hash}."),
    (
        "Baja eficiencia de ligando (LE={le}): la molécula aporta {atoms} átomos pesados para {affinity} kcal/mol. Superar 0.25 a este tamaño exigiría una afinidad mejor que {threshold} kcal/mol. Considerar recortar átomos que no contribuyen a la unión.",
        "Low ligand efficiency (LE={le}): the molecule contributes {atoms} heavy atoms for {affinity} kcal/mol. Exceeding 0.25 at this size would require an affinity better than {threshold} kcal/mol. Consider removing atoms that do not contribute to binding.",
    ),
    (
        "Eficiencia de ligando alta (LE={le}): buena economía de átomos para este nivel de unión, con el umbral convencional de 0.45 (Hopkins et al. 2004) evaluado dentro del espacio Ro5 para el que está calibrado.",
        "High ligand efficiency (LE={le}): good atom economy for this level of binding, with the conventional 0.45 threshold (Hopkins et al. 2004) evaluated within the Rule of Five space for which it is calibrated.",
    ),
    (
        "Afinidad de {affinity} kcal/mol en la escala de Vina. Por debajo de 300 Da (Rule of Three) una afinidad en este rango es lo habitual y no descalifica la molécula: el criterio en espacio de fragmentos es la eficiencia por átomo, no la afinidad absoluta. El score de Vina ordena candidatos; no es energía libre ni se traduce a una concentración.",
        "Affinity of {affinity} kcal/mol on the Vina scale. Below 300 Da (Rule of Three), affinity in this range is usual and does not disqualify the molecule: the criterion in fragment space is efficiency per atom, rather than absolute affinity. The Vina score ranks candidates; it is not free energy and does not translate into a concentration.",
    ),
    ("Con la carga actual puedes usar entre 1 y {maximum} hilos. Dejamos margen para otras aplicaciones; actualiza los recursos y vuelve a intentarlo.", "With current load you can use between 1 and {maximum} threads. We leave headroom for other applications; refresh resources and try again."),
    ("Con la VRAM libre actual puedes elegir de 128 a {maximum} MiB adicionales. Actualiza los recursos o elige CPU.", "With currently free VRAM you can choose between 128 and {maximum} additional MiB. Refresh resources or choose CPU."),
    ("No resuelto: {motivo}", "Unresolved: {motivo}"),
    # Molcy, instalación de Molecular Nodes (VM-MOLCY-01): el código de salida, la última línea y la ruta se copian tal cual.
    ("El Python auxiliar de Blender terminó con {codigo} antes de poder instalar extensiones.",
     "Blender's helper Python exited with {codigo} before it could install extensions."),
    ("Último mensaje: {detalle}", "Last message: {detalle}"),
    ("Registro completo: {ruta}", "Full record: {ruta}"),
    ("No se puede demostrar la pose {pose} de la piscina: {motivo}", "The pool's pose {pose} cannot be proven: {motivo}"),
    ("Falta la conformación {conformacion} de entrada.", "Input conformation {conformacion} is missing."),
    ("No se pudo reconstruir la geometría del ensamble: {motivo}", "The ensemble geometry could not be rebuilt: {motivo}"),
    ("{count} tautómeros candidatos, ninguno descartado con evidencia; la especie acoplada se declaró, pero su población no se predijo", "{count} candidate tautomers, none discarded with evidence; the docked species was declared, but its population was not predicted"),
    (
        "Se pidieron {pedidas} conformaciones y se generaron {conseguidas}: "
        "la cobertura geométrica es menor que la solicitada.",
        "{pedidas} conformers were requested and {conseguidas} were generated: "
        "geometric coverage is lower than requested.",
    ),
    (
        "{count} elegidos de {total} del catálogo: {n1} … y {n2} más",
        "{count} selected out of {total} in the catalog: {n1} … and {n2} more",
    ),
    (
        "{count} elegidos de {total} del catálogo: {lista}",
        "{count} selected out of {total} in the catalog: {lista}",
    ),
    (
        "Página {n} de {total}",
        "Page {n} of {total}",
    ),
    ("Falta `{n1}`.", "Missing `{n1}`."),
    ("  raíz:        {n1}", "  root:        {n1}"),
    ("  manifiesto:  v{n1}", "  manifest:    v{n1}"),
    ("  archivos:    {n1} presentes / {n2} declarados", "  files:       {n1} present / {n2} declared"),
    ("  aviso:   {n1}", "  warning: {n1}"),
    ("  ERROR:   {n1}", "  Error:   {n1}"),
    ("El archivo no es un ZIP legible: {n1}", "The file is not a readable ZIP: {n1}"),
    ("Entrada insegura `{n1}`: {n2}.", "Unsafe ZIP entry `{n1}`: {n2}."),
    ("Entrada duplicada en el ZIP: `{n1}`.", "Duplicate ZIP entry: `{n1}`."),
    ("Entrada `{n1}` es un enlace simbólico.", "ZIP entry `{n1}` is a symbolic link."),
    ("El paquete debe tener una sola carpeta raíz; tiene {n1}.", "The package must have a single root folder; found {n1}."),
    ("`manifest.json` no es JSON válido: {n1}", "`manifest.json` is not valid JSON: {n1}"),
    (
        "El manifiesto es v{n1} y este verificador soporta versiones entre v1 y v{n2}.",
        "The manifest is v{n1}; this verifier supports versions v1 through v{n2}.",
    ),
    ("Ruta insegura en el manifiesto `{n1}`: {n2}.", "Unsafe path in manifest `{n1}`: {n2}."),
    ("Ruta duplicada en el manifiesto: `{n1}`.", "Duplicate path in manifest: `{n1}`."),
    ("`{n1}` se declara `{n2}` pero el paquete SÍ lo contiene.", "`{n1}` is declared as `{n2}`, but the package contains it."),
    ("`{n1}`: falta un tamaño entero no negativo.", "`{n1}`: missing a nonnegative integer size."),
    ("`{n1}`: falta un SHA-256 hexadecimal válido.", "`{n1}`: missing a valid hexadecimal SHA-256 hash."),
    ("Falta el archivo declarado `{n1}`.", "Declared file `{n1}` is missing."),
    ("`{n1}`: tamaño {n2} B, el manifiesto declara {n3} B.", "`{n1}`: {n2} B; the manifest declares {n3} B."),
    ("`{n1}`: SHA-256 no coincide (modificado).", "`{n1}`: SHA-256 does not match (modified)."),
    ("`{n1}` está en el paquete y no lo declara el manifiesto.", "`{n1}` is in the package but is not declared in the manifest."),
    ("`{n1}` no es texto UTF-8: {n2}", "`{n1}` is not UTF-8 text: {n2}"),
    ("Línea mal formada en `{n1}`: {n2}", "Malformed line in `{n1}`: {n2}"),
    ("`{n1}` contiene una ruta duplicada: `{n2}`.", "`{n1}` contains a duplicate path: `{n2}`."),
    ("`{n1}` no está ordenado.", "`{n1}` is not sorted."),
    ("`{n1}` no aparece en `{n2}`.", "`{n1}` does not appear in `{n2}`."),
    ("`{n1}`: el hash de `{n2}` no coincide.", "`{n1}`: the hash of `{n2}` does not match."),
    ("`{n1}` lista `{n2}`, que no está en el paquete.", "`{n1}` lists `{n2}`, which is not in the package."),
    ("`{n1}` no debe contener su propio hash (`{n2}`).", "`{n1}` must not contain its own hash (`{n2}`)."),
    ("<b>Aviso de integridad:</b> {n1}", "<b>Integrity notice:</b> {n1}"),
    ("<b>{n1}</b> — Esta corrida no registró veredicto físico por pose.", "<b>{n1}</b> — This run has no recorded physical verdict per pose."),
    ("Campos de procedencia sin sellar en esta corrida: {n1}.", "Unsealed provenance fields in this run: {n1}."),
    ("{n1} · corrida {n2}", "{n1} · run {n2}"),
    (" — el caso declaró la cadena {n1}; el PDBQT acoplado contiene {n2}", " — the case declared chain {n1}; the docked PDBQT contains {n2}"),
    ("ABSTENCIÓN · {n1}", "ABSTENTION · {n1}"),
    ("{n1} (se pidió {n2}; fuera del rango admitido)", "{n1} (requested {n2}; outside the supported range)"),
    # Frases compuestas en tiempo de ejecución (sin marcadores): no son literales del código.
    ('Población química no determinada.', 'Chemical population is undetermined.'),
    ('Población química no determinada; el grupo sin pKa sigue en revisión', 'Chemical population is undetermined; the group without a pKa remains under review'),
    ('Población química no determinada; el grupo sin pKa sigue en revisión.', 'Chemical population is undetermined; the group without a pKa remains under review.'),
    ('Población química no determinada; monocatión como hipótesis en revisión por datos experimentales discrepantes cerca de pH fisiológico', 'Chemical population is undetermined; the monocation remains a hypothesis under review because experimental data near physiological pH disagree'),
    ('Población química no determinada; monocatión como hipótesis en revisión por datos experimentales discrepantes cerca de pH fisiológico.', 'Chemical population is undetermined; the monocation remains a hypothesis under review because experimental data near physiological pH disagree.'),
    # Variantes completas ANTES de la genérica: la genérica se tragaba el resto
    # de la frase («…a pH 7.4, de 4 enumerados» en un dossier en inglés).
    ('Microestado más próximo al predicho a pH {ph}, de {count} enumerados; {total} empataron y el desempate fue alfabético', 'Microstate closest to the one predicted at pH {ph}, out of {count} enumerated; {total} tied, with alphabetical order as the tiebreaker'),
    ('Microestado más próximo al predicho a pH {ph}, de {count} enumerados; {total} empataron y el desempate fue alfabético.', 'Microstate closest to the one predicted at pH {ph}, out of {count} enumerated; {total} tied, with alphabetical order as the tiebreaker.'),
    ('Microestado más próximo al predicho a pH {ph}, de {count} enumerados; monocatión como hipótesis en revisión por datos experimentales discrepantes cerca de pH fisiológico', 'Microstate closest to the one predicted at pH {ph}, out of {count} enumerated; the monocation remains a hypothesis under review because experimental data near physiological pH disagree'),
    ('Microestado más próximo al predicho a pH {ph}, de {count} enumerados; monocatión como hipótesis en revisión por datos experimentales discrepantes cerca de pH fisiológico.', 'Microstate closest to the one predicted at pH {ph}, out of {count} enumerated; the monocation remains a hypothesis under review because experimental data near physiological pH disagree.'),
    ('Microestado más próximo al predicho a pH {ph}, de {count} enumerados; el grupo sin pKa sigue en revisión', 'Microstate closest to the one predicted at pH {ph}, out of {count} enumerated; the group without a pKa remains under review'),
    ('Microestado más próximo al predicho a pH {ph}, de {count} enumerados; el grupo sin pKa sigue en revisión.', 'Microstate closest to the one predicted at pH {ph}, out of {count} enumerated; the group without a pKa remains under review.'),
    ('Microestado más próximo al predicho a pH {ph}, de {count} enumerados', 'Microstate closest to the one predicted at pH {ph}, out of {count} enumerated'),
    ('Microestado más próximo al predicho a pH {ph}, de {count} enumerados.', 'Microstate closest to the one predicted at pH {ph}, out of {count} enumerated.'),
    ('Microestado más próximo al predicho a pH {ph}; {total} empataron y el desempate fue alfabético', 'Microstate closest to the one predicted at pH {ph}; {total} tied, with alphabetical order as the tiebreaker'),
    ('Microestado más próximo al predicho a pH {ph}; {total} empataron y el desempate fue alfabético.', 'Microstate closest to the one predicted at pH {ph}; {total} tied, with alphabetical order as the tiebreaker.'),
    ('Microestado más próximo al predicho a pH {ph}; monocatión como hipótesis en revisión por datos experimentales discrepantes cerca de pH fisiológico', 'Microstate closest to the one predicted at pH {ph}; the monocation remains a hypothesis under review because experimental data near physiological pH disagree'),
    ('Microestado más próximo al predicho a pH {ph}; monocatión como hipótesis en revisión por datos experimentales discrepantes cerca de pH fisiológico.', 'Microstate closest to the one predicted at pH {ph}; the monocation remains a hypothesis under review because experimental data near physiological pH disagree.'),
    ('Microestado más próximo al predicho a pH {ph}; el grupo sin pKa sigue en revisión', 'Microstate closest to the one predicted at pH {ph}; the group without a pKa remains under review'),
    ('Microestado más próximo al predicho a pH {ph}; el grupo sin pKa sigue en revisión.', 'Microstate closest to the one predicted at pH {ph}; the group without a pKa remains under review.'),
    ('Menor carga formal entre alternativas y entrada; {n1} carece de pKa verificado.', 'Lowest formal charge among the alternatives and input; {n1} has no verified pKa.'),
    ('Primer SMILES canónico por orden alfabético: la tabla no reconoció centros ionizables y no estimó poblaciones; {n1} candidatos.', 'First canonical SMILES in alphabetical order: the table did not recognize ionizable centers or estimate populations; {n1} candidates.'),
    ('Primer SMILES canónico por orden alfabético: la tabla no reconoció centros ionizables y no estimó poblaciones.', 'First canonical SMILES in alphabetical order: the table did not recognize ionizable centers or estimate populations.'),
    ("Microestado más próximo al predicho a pH {ph}.", "Microstate closest to the one predicted at pH {ph}."),
    ("Microestado más próximo al predicho a pH {ph}", "Microstate closest to the one predicted at pH {ph}"),
    (
        "Microstate closest to the one predicted at pH {n1}, de {n2} enumerados",
        "Microstate closest to the one predicted at pH {n1}, out of {n2} enumerated",
    ),
    (", de {n1} enumerados", ", out of {n1} enumerated"),
    ("; {n1} empataron y el desempate fue alfabético", "; {n1} tied, with alphabetical order as the tiebreaker"),
    ("Menor carga formal entre alternativas y entrada; {n1} carece de pKa verificado. Población química no determinada.", "Lowest formal charge among the alternatives and input; {n1} has no verified pKa. Chemical population is undetermined."),
    ("La entrada declaraba {n1} estereocentro(s) y {n2} doble(s) E/Z que la especie acoplada no conserva (la normalización cambió esos átomos): lo acoplado no es el estereoisómero escrito.", "The input declared {n1} stereocenter(s) and {n2} E/Z double bond(s) that the docked species does not retain (normalization changed those atoms): the docked species is not the written stereoisomer."),
    ("La entrada dejó {n1} centro(s) y {n2} doble(s) E/Z sin especificar; el conformero representa un isómero. {n3} doble(s) siguen sin clasificar desde 3D. Los demás estereoisómeros no se evaluaron.", "The input left {n1} center(s) and {n2} E/Z double bond(s) unspecified; the conformer represents one isomer. {n3} double bond(s) remain unassigned from 3D. The other stereoisomers were not evaluated."),
    ("Registros HETATM retirados del ensamblaje: aguas {n1}, metales {n2}, cofactores orgánicos {n3}, otras especies {n4}. A {n5} Å o menos de la caja: retirado {n6}; conservado {n7}.", "HETATM records removed from the assembly: waters {n1}, metals {n2}, organic cofactors {n3}, other species {n4}. Within {n5} Å of the box: removed {n6}; retained {n7}."),
    ("La escala se sujetó a HA={n1}: el ajuste de Reynolds cubre 15-50 átomos pesados y esta molécula queda fuera, así que el valor es un límite, no una interpolación.", "The scale was capped at HA={n1}: the Reynolds fit covers 15–50 heavy atoms, and this molecule falls outside that range, so the value is a bound, not an interpolation."),
    ("{n1} kcal/mol por átomo pesado ({n2} átomos). Hopkins et al. 2004. Depende del tamaño por construcción: medido sobre la cohorte de este proyecto (17 431 moléculas), su correlación con el número de átomos es tan fuerte como la del score crudo, con el signo cambiado.", "{n1} kcal/mol per heavy atom ({n2} atoms). Hopkins et al. 2004. It depends on size by construction: measured across this project's cohort (17,431 molecules), its correlation with atom count is as strong as that of the raw score, with the opposite sign."),
    ("{n1} = |afinidad| / HA^0.3. Nissink, J. Chem. Inf. Model. 49 (2009) 1617. El artículo no publica un umbral, así que aquí no hay ninguno.", "{n1} = |affinity| / HA^0.3. Nissink, J. Chem. Inf. Model. 49 (2009) 1617. The paper does not publish a threshold, so none is used here."),
    # SCI-A-024/026: la piscina se dice en inglés; van antes de la genérica, que
    # dejaba « · pose elegida entre N candidatas» en castellano dentro de {n3}.
    ("Ensemble · {n1} de {n2} conformaciones · pose elegida entre {n3} candidatas",
     "Ensemble · {n1} of {n2} conformers · pose chosen from {n3} candidates"),
    ("Ensemble · {n1} de {n2} conformaciones · pose elegida entre hasta {n3} candidatas (recuento no registrado)",
     "Ensemble · {n1} of {n2} conformers · pose chosen from up to {n3} candidates (count not recorded)"),
    ("Ensemble · {n1} de {n2} conformaciones{n3}", "Ensemble · {n1} of {n2} conformers{n3}"),
    # SCI-A-025/038: el método de la geometría de entrada es el que registró la corrida.
    ("Confórmero único ({frase1}) · se pidieron {n1} conformaciones",
     "Single conformer ({frase1}) · {n1} conformers were requested"),
    ("Confórmero único ({frase1})", "Single conformer ({frase1})"),
    ("{n1} + UFF (MMFF94 no parametrizó la molécula), sin converger",
     "{n1} + UFF (MMFF94 could not parametrize the molecule), not converged"),
    ("{n1} + UFF (MMFF94 no parametrizó la molécula)",
     "{n1} + UFF (MMFF94 could not parametrize the molecule)"),
    ("{n1} + MMFF94, sin converger", "{n1} + MMFF94, not converged"),
    ("{n1}, sin optimizar: MMFF94 y UFF fallaron", "{n1}, not optimized: MMFF94 and UFF failed"),
    ("Se pidieron {n1} conformaciones y la corrida siguió con una sola: el ensemble no se generó y su cobertura no está.",
     "{n1} conformers were requested and the run continued with a single one: the ensemble was not generated and its coverage is missing."),
    ("Se pidieron {n1} conformaciones y se generaron {n2}: la cobertura geométrica es menor que la solicitada. El ensemble amplía cobertura; no mejora, por sí solo, la elección de la pose top-1.", "{n1} conformers were requested and {n2} were generated: geometric coverage is below the requested amount. An ensemble broadens coverage; by itself, it does not improve top-1 pose selection."),
    ("{count} elegidos{n2} del catálogo: {n3}", "{count} selected{n2} from the catalog: {n3}"),
    ("{count} del catálogo: {lista}", "{count} from the catalog: {lista}"),
    ("El cliente declaró la relación corrida/inputs como «{n1}», pero las huellas dicen «{n2}». Manda lo comprobable.", "The client declared the run/input relationship as “{n1}”, but the fingerprints say “{n2}”. The verifiable evidence takes precedence."),
    ("{n1} control(es) reconocido(s)", "{n1} acknowledged check(s)"),
    ("centro {n1} · tamaño {n2} Å", "center {n1} · size {n2} Å"),
    ("El caso pide la corrida «{n1}» y el resultado almacenado pertenece a «{n2}». El paquete no puede afirmar que describan lo mismo.", "The case requests run “{n1}”, but the stored result belongs to “{n2}”. The package cannot claim that they describe the same run."),
    ("{n1}/{n2} poses con veredicto", "{n1}/{n2} poses with a verdict"),
    ("La sugerida (#{n1}) NO es la top-1 de Vina (#{n2})", "The suggested pose (#{n1}) is NOT Vina's top-1 (#{n2})"),
    ("{n1} de {n2} poses", "{n1} of {n2} poses"),
    ("{n1}/3 trazas: versión del motor, semilla y parser.", "{n1}/3 traces: engine version, seed, and parser."),
    ("Declarado por el caso: {n1}", "Declared by the case: {n1}"),
    ("{n1} kcal/mol (score de Vina, sin transformar)", "{n1} kcal/mol (Vina score, untransformed)"),
    ("pKi {n1} · equivale a {n2} kcal/mol · dentro del dominio de aplicabilidad", "pKi {n1} · equivalent to {n2} kcal/mol · within the applicability domain"),
    ("{n1} — UMS HISTÓRICO (warheads + donantes + MolChamb), no la variante SMARTS-only del ADR 75. La corrida es anterior a SCHEMA 18 y no registró la señal autorizada.", "{n1} — HISTORICAL UMS (warheads + donors + MolChamb), not the SMARTS-only variant in ADR 75. The run predates SCHEMA 18 and did not record the approved signal."),
    ("El PDB «{n1}» no es ninguno de los tres perfiles de M5-Zn (3DC3/CA2, 1GKC/MMP9, 1O86/ACE). M5-Zn prepara el receptor, conserva el zinc, ejecuta Vina y calcula señales diagnósticas, pero NO hereda los pesos de otra diana.", "PDB “{n1}” is not one of the three M5-Zn profiles (3DC3/CA2, 1GKC/MMP9, 1O86/ACE). M5-Zn prepares the receptor, retains zinc, runs Vina, and calculates diagnostic signals, but does NOT inherit weights from another target."),
    ("El estado «{n1}» no es VALIDATED, así que este número no habilita ninguna conclusión: no entra en el ranking, ni en la recomendación, ni en el veredicto. Se muestra para que pueda auditarse.", "Status “{n1}” is not VALIDATED, so this number does not support any conclusion: it is excluded from ranking, recommendation, and verdict. It is shown for auditability."),
    ("Componentes ausentes en esta corrida: {n1}.", "Components missing from this run: {n1}."),
    ("; {n1} ausente(s) en REMARK 465", "; {n1} missing in REMARK 465"),
    ("; {n1} Å de la caja)", "; {n1} Å from the box)"),
    # Las cabeceras antes que el hueco suelto: si no, éste casaba la frase entera y dejaba la cabecera en castellano.
    ("{n1} corte(s) del esqueleto; {n2} junto al sitio: {frase1}", "{n1} backbone break(s); {n2} near the site: {frase1}"),
    ("{n1} corte(s) del esqueleto; todos lejos del sitio: {frase1}", "{n1} backbone break(s); all far from the site: {frase1}"),
    ("{n1}: {n2} → {n3} (C–N {n4} Å; {n5} ausente(s) en REMARK 465; {n6} Å de la caja)", "{n1}: {n2} → {n3} (C–N {n4} Å; {n5} missing in REMARK 465; {n6} Å from the box)"),
    ("{n1}: {n2} → {n3} (C–N {n4} Å; REMARK 465 no declara los residuos ausentes; {n5} Å de la caja)", "{n1}: {n2} → {n3} (C–N {n4} Å; REMARK 465 does not declare missing residues; {n5} Å from the box)"),
    ("{n1} corte(s) del esqueleto", "{n1} backbone break(s)"),
    ("{n1} fuera del margen del sitio:", "{n1} outside the site's margin:"),
    ("; {n1} en el sitio:", "; {n1} in the site:"),
    ("Ninguna: toda la proteína a {n1} Å o menos de la caja está en el receptor.", "None: all protein within {n1} Å of the box is in the receptor."),
    ("A {n1} Å o menos de la caja y fuera del receptor:", "Within {n1} Å of the box and outside the receptor:"),
    ("· SHA-256 del SDF {n1}", "· SDF SHA-256 {n1}"),
    # Preparación, «Receptor preparado» (services/dossier/preparacion.py)
    ("SHA-256 {n1} · receta {n2}", "SHA-256 {n1} · recipe {n2}"),
    ("Pose principal: top-1 de Vina (#{n1}); el selector sugiere #{n2}", "Primary pose: Vina top-1 (#{n1}); the selector suggests #{n2}"),
    ("Pose principal: top-1 de Vina (#{n1})", "Primary pose: Vina top-1 (#{n1})"),
    # Preparación: ensamble, cofactor declarado ligando del cristal y tautómero cambiado (2026-10-10).
    ("{n1} SDF de poses, uno por conformación: {n2}", "{n1} pose SDFs, one per conformation: {n2}"),
    ("Falta el archivo de poses o su hash en la(s) conformación(es) {n1}.",
     "The pose file or its hash is missing for conformation(s) {n1}."),
    ("{n1}/{n2} registrados en cada una de las {n3} conformaciones",
     "{n1}/{n2} recorded for each of the {n3} conformations"),
    ("{n1}/{n2} registrados", "{n1}/{n2} recorded"),
    ("Faltan: {frase1}", "Missing: {frase1}"),
    # Va antes que «Retirados a {m} Å o menos: {lista}» (receptores propios), que se tragaría la segunda frase.
    ("Retirados a {m} Å o menos: {lista}. Cofactor retirado como ligando del cristal: {lista2}.",
     "Removed at {m} Å or less: {lista}. Cofactor removed as the crystal ligand: {lista2}."),
    ("Cofactor retirado como ligando del cristal: {lista}.", "Cofactor removed as the crystal ligand: {lista}."),
    # Comprobación previa: cofactores sin plantilla con la regla de prepare_target (2026-10-11).
    ("Sin plantilla Meeko local a {m} Å o menos de la caja: {frase1}.",
     "No local Meeko template within {m} Å of the box: {frase1}."),
    ("La preparación retirará {frase1}: a más de {m} Å de la caja.",
     "Preparation will remove {frase1}: more than {m} Å from the box."),
    ("Entrada {n1} → tautómero canónico {n2}", "Input {n1} → canonical tautomer {n2}"),
    # Criterio de la caja (sin distancias): salía en castellano en la versión inglesa.
    ("A {m} Å o menos de la caja y fuera del receptor: {frase1}", "Within {m} Å of the box and outside the receptor: {frase1}"),
    ("cadena {ids1}, {count} residuo(s)", "chain {ids1}, {count} residue(s)"),
    ("cadena {ids1} · sitio entre {ids2} · generada(s) por simetría desde el depósito (REMARK 350, BIOMOLECULE 1): "
     "{n1}",
     "chain {ids1} · site between {ids2} · generated by symmetry from the deposit (REMARK 350, BIOMOLECULE 1): {n1}"),
    ("cadena {ids1} · generada(s) por simetría desde el depósito (REMARK 350, BIOMOLECULE 1): {n1}",
     "chain {ids1} · generated by symmetry from the deposit (REMARK 350, BIOMOLECULE 1): {n1}"),
    ("cadena {ids1} · sitio entre {ids2}", "chain {ids1} · site between {ids2}"),
    ("cadena {ids1}", "chain {ids1}"),
    ("{count} diferencia(s) con la secuencia de referencia (SEQADV): {frase1}.",
     "{count} difference(s) from the reference sequence (SEQADV): {frase1}."),
    ("{count} diferencia(s) con la secuencia de referencia (SEQADV), ninguna a {n1} Å o menos del ligando: {frase1}.",
     "{count} difference(s) from the reference sequence (SEQADV), none within {n1} Å of the ligand: {frase1}."),
    ("Según el REMARK 999: {frase1}", "According to REMARK 999: {frase1}"),
    ("Hay diferencias con la secuencia natural a {n1} Å o menos del ligando: el sitio cristalizado no es el de la "
     "proteína natural, y un cálculo posterior hereda esa diferencia.",
     "There are differences from the natural sequence within {n1} Å of the ligand: the crystallized site is not that of "
     "the natural protein, and a downstream calculation inherits that difference."),
    ("{count} residuo(s) con átomos de ocupación cero (REMARK 475/480): {frase1}",
     "{count} residue(s) with zero-occupancy atoms (REMARK 475/480): {frase1}"),
    ("{count} residuo(s) con átomos de ocupación cero (REMARK 475/480), ninguno a {n1} Å o menos del ligando: {frase1}. "
     "El receptor preparado los conserva con ocupación 1,00.",
     "{count} residue(s) with zero-occupancy atoms (REMARK 475/480), none within {n1} Å of the ligand: {frase1}. "
     "The prepared receptor keeps them with occupancy 1.00."),
    ("El cristal no los sostiene y están a {n1} Å o menos del ligando: el receptor preparado los conserva con "
     "ocupación 1,00, así que su posición es un modelo, no una medida.",
     "The crystal does not support them and they are within {n1} Å of the ligand: the prepared receptor keeps them "
     "with occupancy 1.00, so their position is a model, not a measurement."),
    ("El depósito declara que al ligando del cristal {n1} le faltan átomos (REMARK 610): la comparación de la pose con "
     "él y las distancias medidas desde él son parciales.",
     "The deposit declares that the crystal ligand {n1} is missing atoms (REMARK 610): comparing the pose with it, and "
     "distances measured from it, are partial."),
    # Preparación medida desde el ligando (services/dossier/contexto_estructural.py, 2026-10-10).
    # Las listas van en {frase…}: con {lista} la plantilla se tragaba la frase siguiente.
    # Recuentos globales de registros HETATM retirados (fila del dossier, 2026-10-22).
    ("aguas {n1}, metales {n2}, cofactores orgánicos {n3}, otras especies {n4}",
     "waters {n1}, metals {n2}, organic cofactors {n3}, other species {n4}"),
    ("Retirados a {m} Å o menos del ligando: {frase1}; más lejos: {frase2}",
     "Removed within {m} Å of the ligand: {frase1}; farther away: {frase2}"),
    ("Retirados a {m} Å o menos del ligando: {frase1}", "Removed within {m} Å of the ligand: {frase1}"),
    # Metales y cofactores en dos niveles (2026-10-22): coordinados por el ligando del cristal, o sólo cerca.
    ("En contacto con el ligando del cristal: {frase1}.", "In contact with the crystal ligand: {frase1}."),
    ("Conservados y coordinados por el ligando del cristal: {frase1}.",
     "Kept and coordinated by the crystal ligand: {frase1}."),
    ("Ninguno retirado a {m} Å o menos del ligando; más lejos: {frase1}; conservados: {frase2}",
     "None removed within {m} Å of the ligand; farther away: {frase1}; kept: {frase2}"),
    ("Ninguno retirado a {m} Å o menos del ligando; más lejos: {frase1}",
     "None removed within {m} Å of the ligand; farther away: {frase1}"),
    ("Ninguno retirado a {m} Å o menos del ligando; conservados: {frase1}",
     "None removed within {m} Å of the ligand; kept: {frase1}"),
    ("Ninguno retirado a {m} Å o menos del ligando", "None removed within {m} Å of the ligand"),
    ("{n1} retirada(s) a {m} Å o menos del ligando: {frase1}; {n2} más retirada(s) a {m2} Å o menos de la caja; {n3} conservada(s)",
     "{n1} removed within {m} Å of the ligand: {frase1}; {n2} more removed within {m2} Å of the box; {n3} kept"),
    ("Ninguna retirada a {m} Å o menos del ligando; {n1} retirada(s) a {m2} Å o menos de la caja; {n2} conservada(s)",
     "None removed within {m} Å of the ligand; {n1} removed within {m2} Å of the box; {n2} kept"),
    ("Retiradas a {m} Å o menos del ligando: {frase1}; más lejos: {frase2}",
     "Removed within {m} Å of the ligand: {frase1}; farther away: {frase2}"),
    ("Retiradas a {m} Å o menos del ligando: {frase1}", "Removed within {m} Å of the ligand: {frase1}"),
    # Otras copias del ligando del cristal (FEP-06-PRE-2, 6SXC, 2026-10-25).
    ("Incluye otra(s) copia(s) del ligando del cristal: {frase1}. Puede ser una segunda molécula unida al sitio; la "
     "preparación la retira y un cálculo posterior tiene que decidir si la conserva.",
     "Includes other copy(ies) of the crystal ligand: {frase1}. It may be a second molecule bound to the site; "
     "preparation removes it and a downstream calculation has to decide whether to keep it."),
    ("Ninguna retirada a {m} Å o menos del ligando; más lejos: {frase1}",
     "None removed within {m} Å of the ligand; farther away: {frase1}"),
    ("{n1} corte(s) del esqueleto; {n2} a {m} Å o menos del ligando: {frase1}",
     "{n1} backbone break(s); {n2} within {m} Å of the ligand: {frase1}"),
    ("{n1} corte(s) del esqueleto; todos a más de {m} Å del ligando: {frase1}",
     "{n1} backbone break(s); all more than {m} Å from the ligand: {frase1}"),
    ("{n1}: {n2} → {n3} (C–N {n4} Å; {n5} ausente(s) en REMARK 465; {n6} Å del ligando)",
     "{n1}: {n2} → {n3} (C–N {n4} Å; {n5} missing in REMARK 465; {n6} Å from the ligand)"),
    ("{n1}: {n2} → {n3} (C–N {n4} Å; REMARK 465 no declara los residuos ausentes; {n5} Å del ligando)",
     "{n1}: {n2} → {n3} (C–N {n4} Å; REMARK 465 does not declare missing residues; {n5} Å from the ligand)"),
    ("{n1} truncada(s); {n2} a {m} Å o menos del ligando: {frase1}; resto: {frase2}",
     "{n1} truncated; {n2} within {m} Å of the ligand: {frase1}; rest: {frase2}"),
    ("{n1} truncada(s); todas a más de {m} Å del ligando; resto: {frase1}",
     "{n1} truncated; all more than {m} Å from the ligand; rest: {frase1}"),
    ("{n1} truncada(s); {n2} en el sitio: {frase1}; resto: {frase2}",
     "Truncated side-chain count: {n1}; site count: {n2}; residues: {frase1}; rest: {frase2}"),
    ("{n1} truncada(s); todas fuera del sitio; resto: {frase1}",
     "Truncated side-chain count: {n1}; all are outside the site; rest: {frase1}"),
    ("{n1} truncada(s); {n2} a {m} Å o menos del ligando: {frase1}",
     "{n1} truncated; {n2} within {m} Å of the ligand: {frase1}"),
    ("{n1} truncada(s); todas a más de {m} Å del ligando", "{n1} truncated; all more than {m} Å from the ligand"),
    ("Residuos de proteína fuera del receptor a {m} Å o menos del ligando, por cadena: {frase1}",
     "Protein residues outside the receptor within {m} Å of the ligand, by chain: {frase1}"),
    ("Ninguna: no hay proteína fuera del receptor a {m} Å o menos del ligando.",
     "None: no protein outside the receptor is within {m} Å of the ligand."),
    ("His a {m} Å o menos del ligando: {frase1}.", "His within {m} Å of the ligand: {frase1}."),
    ("His que coordinan un metal conservado con el hidrógeno en el nitrógeno que lo coordina: {frase1}.",
     "His coordinating a retained metal with the hydrogen on the coordinating nitrogen: {frase1}."),
    ("Cys que coordinan un metal conservado como tiol neutro, con el HG en el azufre que lo coordina: {frase1}.",
     "Cys coordinating a retained metal as a neutral thiol, with HG on the coordinating sulfur: {frase1}."),
    ("{count} de las {total} poses guardadas quedan a {m} Å o menos de un corte del esqueleto (rangos {ids1}): "
     "acoplan contra el bucle ausente y no son comparables con las demás.",
     "{count} of the {total} saved poses lie within {m} Å of a backbone break (ranks {ids1}): they dock against the "
     "missing loop and are not comparable with the others."),
    ("{count} corte(s) a {m} Å o menos de la caja: Vina busca junto a ellos, y ninguna de las {total} poses guardadas "
     "quedó a {n3} Å o menos.",
     "{count} break(s) within {m} Å of the box: Vina searches next to them, and none of the {total} saved poses came "
     "within {n3} Å."),
    ("El depósito traía hidrógenos que contradecían su propia estructura y se retiraron antes de Meeko: "
     "{n1} His sin hidrógeno en ND1 ni NE2 (la plantilla eligió su estado como en un depósito sin hidrógenos) "
     "y {n2} HG de cisteínas con puente disulfuro.",
     "The deposit carried hydrogens that contradicted its own structure, and they were removed before Meeko: "
     "{n1} His without hydrogen on ND1 or NE2 (the template chose their state as for a deposit without hydrogens) "
     "and {n2} HG of disulfide-bonded cysteines."),
    ("Estados no estándar a {m} Å o menos del ligando: {frase1}.",
     "Non-standard states within {m} Å of the ligand: {frase1}."),
    ("Bolsillo de {n1} Å alrededor del centro de la caja: {n2} de {n3} residuos de las cadenas {n4}; "
     "{n5} corte(s) del esqueleto creados por el recorte",
     "Pocket of {n1} Å around the box center: {n2} of {n3} residues of chains {n4}; "
     "{n5} backbone break(s) created by the crop"),
    ("{n1} de {n2} puente(s) disulfuro quedan como tiol libre en el receptor: {frase1}",
     "{n1} of {n2} disulfide bridge(s) remain as free thiols in the receptor: {frase1}"),
    ("{n1} de {n2} puente(s) disulfuro de la estructura sin estado químico registrado en el receptor: {frase1}",
     "{n1} of {n2} disulfide bridge(s) in the structure without a recorded chemical state in the receptor: {frase1}"),
    ("{n1} puente(s) disulfuro en la estructura; ninguno queda como tiol libre en el receptor",
     "{n1} disulfide bridge(s) in the structure; none remains as a free thiol in the receptor"),
    ("{n1} residuo(s) con conformaciones alternativas a {m} Å o menos del ligando: {frase1}",
     "{n1} residue(s) with alternate conformations within {m} Å of the ligand: {frase1}"),
    ("Ninguna a {m} Å o menos del ligando", "None within {m} Å of the ligand"),
    ("Pose top-1 y ligando del cristal {n1}", "Top-1 pose and crystal ligand {n1}"),
    ("Metales, cofactores y otras especies cuentan a {n1} Å o menos del ligando; aguas, a {n2} Å; "
     "huecos y residuos, a {n3} Å.",
     "Metals, cofactors and other species count within {n1} Å of the ligand; waters, within {n2} Å; "
     "gaps and residues, within {n3} Å."),
    ("Grupos con pKa a {n1} unidades o menos del pH {n2}: {frase1}.",
     "Groups with a pKa within {n1} units of pH {n2}: {frase1}."),
    ("{n1} (pKa ≈ {n2}; {n3} % en la otra forma)", "{n1} (pKa ≈ {n2}; {n3} % in the other form)"),
    # Preparación: tautómeros con población despreciable (chem/tautomeros_minoritarios.py).
    ("Forma minoritaria acoplada: {n1} ({frase1})", "Minor form docked: {n1} ({frase1})"),
    ("Vuelve a evaluar con la forma mayoritaria: {n1}", "Evaluate again with the major form: {n1}"),
    ("Vuelve a evaluar con una de estas formas, que ninguna regla descarta: {n1}",
     "Evaluate again with one of these forms; no rule discards them: {n1}"),
    ("Los demás candidatos de RDKit ({n1}) son formas minoritarias conocidas: {frase1}.",
     "The other RDKit candidates ({n1}) are known minor forms: {frase1}."),
    # Preparación: unión covalente, membrana y cobertura del campo de fuerzas.
    ("{frase1}: las distancias se miden desde la caja.", "{frase1}: distances are measured from the box."),
    ("Ojiva: {frase1}.", "Warhead: {frase1}."),
    ("Ligando del cristal unido a la proteína: {n1}.", "Crystal ligand bound to the protein: {n1}."),
    ("Se buscaron {n1} tipos de ojiva; la lista no es exhaustiva.",
     "{n1} warhead types were searched; the list is not exhaustive."),
    # {frase1}: detrás puede venir la frase del radical, y con {n1} se copiaría en castellano.
    ("Elementos sin parámetros en OpenFF 2 (Sage) ni en GAFF2: {frase1}.",
     "Elements without parameters in OpenFF 2 (Sage) or GAFF2: {frase1}."),
    ("Todos sus elementos están en OpenFF 2 (Sage) y en GAFF2 ({n1}).",
     "All its elements are in OpenFF 2 (Sage) and GAFF2 ({n1})."),
    ("No estándar: {frase1}.", "Non-standard: {frase1}."),
    # Sólo dígitos y un identificador: con {n…} la cadena se tragaba las frases siguientes.
    ("{count} segmentos transmembrana probables en la cadena {ids1}.",
     "{count} probable transmembrane segments in chain {ids1}."),
    ("Lípidos o detergentes en el cristal: {n1}.", "Lipids or detergents in the crystal: {n1}."),
    # Revisión rutinaria y revisión del caso (2026-10-11): el umbral va en {m}.
    ("La pide toda corrida protonada por plantilla, y ninguna histidina tiene un nitrógeno del anillo a {m} Å "
     "o menos del ligando.",
     "Every run protonated by template requests it, and no histidine has a ring nitrogen within {m} Å "
     "of the ligand."),
    ("Histidina(s) con un nitrógeno del anillo a {m} Å o menos del ligando: {frase1}.",
     "Histidine(s) with a ring nitrogen within {m} Å of the ligand: {frase1}."),
    ("Aguas que pueden puentear el ligando con la proteína (a {m} Å o menos de un N u O de cada uno): "
     "{frase1}.",
     "Waters that can bridge the ligand and the protein (within {m} Å of an N or O of each): {frase1}."),
    ("Ninguna de las aguas retiradas puentea el ligando con la proteína (a {m} Å o menos de un N u O de cada "
     "uno): decidir "
     "cuáles conservar es la misma decisión en toda corrida contra un cristal.",
     "None of the removed waters bridges the ligand and the protein (within {m} Å of an N or O of each): "
     "deciding which "
     "ones to keep is the same decision in every run against a crystal."),
    ("Hidropatía de Kyte-Doolittle (ventanas de {n1}, media ≥ {n2}): {n3} segmento(s) en la cadena {n4}; "
     "uno o dos aparecen también en proteínas solubles.",
     "Kyte-Doolittle hydropathy (windows of {n1}, mean ≥ {n2}): {n3} segment(s) in chain {n4}; "
     "one or two also appear in soluble proteins."),
    ("{n1} fila(s) de trabajo. La columna es la afinidad Vina observada: una señal de ranking dentro de este protocolo, no una medida de energía libre ni una probabilidad de actividad.", "{n1} work row(s). The column shows observed Vina affinity: a ranking signal within this protocol, not a free-energy measurement or a probability of activity."),
    ("Se imprimen las primeras {n1}. El paquete ZIP lleva `rows.csv` con todas.", "The first {n1} are printed. The ZIP package includes all rows in `rows.csv`."),
    ("Población: {n1} moléculas canónicas etiquetadas ({n2} activas, {n3} inactivas), cobertura {n4}.", "Population: {n1} labeled canonical molecules ({n2} active, {n3} inactive), coverage {n4}."),
    ("NO EVALUADAS · {n1}: {n2}", "NOT EVALUATED · {n1}: {n2}"),
    (
        "Los artefactos que NO estaban disponibles aparecen en el manifiesto con estado `{n1}` y su razón. No se omiten y no se fabrican.",
        "Artifacts that were NOT available are listed in the manifest with status `{n1}` and a reason. They are not omitted or fabricated.",
    ),
    (
        "{n1} · cadenas {n2} — el caso declaró la cadena {n3}; el PDBQT acoplado contiene {n4} (medido sobre los bytes del PDBQT hasheado)",
        "{n1} · chains {n2} — the case declared chain {n3}; the docked PDBQT contains {n4} (measured from the hashed PDBQT bytes)",
    ),
    (
        "{n1} · cadena {n2}",
        "{n1} · chain {n2}",
    ),
    (
        # {frase1}: lo de delante («8HFI · cadenas A») también es texto del
        # sistema. Esta plantilla va antes que la específica y la tapaba.
        "{frase1} (medido sobre los bytes del PDBQT hasheado)",
        "{frase1} (measured from the hashed PDBQT bytes)",
    ),
    (
        "{n1} — score de ranking derivado, no una afinidad ni una medida experimental",
        "{n1} — derived ranking score, not an affinity or experimental measurement",
    ),
    (
        "{n1} · NO HABILITA UNA CONCLUSIÓN",
        "{n1} · DOES NOT SUPPORT A CONCLUSION",
    ),
    (
        "El ligando del cristal ({n1}) se retiró como parte de la corrida.",
        "The crystal ligand ({n1}) was removed as part of the run.",
    ),
    (
        "{n1} truncada(s); todas fuera del sitio",
        "Truncated side-chain count: {n1}; all are outside the site",
    ),
    (
        "{n1} truncada(s); {n2} en el sitio: {n3}",
        "Truncated side-chain count: {n1}; site count: {n2}; residues: {n3}",
    ),
    (
        "{n1} corte(s) del esqueleto; todos lejos del sitio: {n2}",
        "Backbone break count: {n1}; all are away from the site: {n2}",
    ),
    (
        "{n1} corte(s) del esqueleto; {n2} junto al sitio: {n3}",
        "Backbone break count: {n1}; site count: {n2}; gaps: {n3}",
    ),
    (
        "Pose principal: top-1 de Vina (#{n1}) · el selector coincide",
        "Primary pose: Vina top-1 (#{n1}) · the selector agrees",
    ),
    (
        "Pose principal: top-1 de Vina (#{n1}) · sin recomendación del selector",
        "Primary pose: Vina top-1 (#{n1}) · no selector recommendation",
    ),
    (
        "Primer SMILES canónico por orden alfabético: la tabla no reconoció centros ionizables y no estimó poblaciones",
        "First canonical SMILES in alphabetical order: the table did not recognize ionizable centers or estimate populations",
    ),
    (
        "Primer SMILES canónico por orden alfabético: la tabla no reconoció centros ionizables y no estimó poblaciones; {n1} candidatos",
        "First canonical SMILES in alphabetical order: the table did not recognize ionizable centers or estimate populations; {n1} candidates",
    ),
    (
        "Selección de biguanida; monocatión como hipótesis en revisión por datos experimentales discrepantes cerca de pH fisiológico",
        "Biguanide selection; the monocation remains a hypothesis under review because experimental data near physiological pH disagree",
    ),
    (
        "{n1} de {n2} poses recibieron veredicto y ninguna falla los controles de química o geometría.",
        "{n1} of {n2} poses received a verdict, and none failed the chemistry or geometry checks.",
    ),
    (
        "{n1} de {n2} poses recibieron veredicto y ninguna falla los controles de química o geometría. Motor: no declarado. Cobertura {n3}/{n4} poses.",
        "{n1} of {n2} poses received a verdict, and none failed the chemistry or geometry checks. Engine: not declared. Coverage: {n3}/{n4} poses.",
    ),
    (
        "{n1} de {n2} poses recibieron veredicto y ninguna falla los controles de química o geometría. Motor: {n3}. Cobertura {n4}/{n5} poses.",
        "{n1} of {n2} poses received a verdict, and none failed the chemistry or geometry checks. Engine: {n3}. Coverage: {n4}/{n5} poses.",
    ),
    (
        "Los controles físicos no llegaron a emitir veredicto ({n1}). Describe lo que le pasó al validador, no a la molécula.",
        "The physical checks did not produce a verdict ({n1}). This describes what happened to the validator, not the molecule.",
    ),
    (
        "{n1} poses quedan a <=1 kcal/mol; diferencia pose 1-2 {n2} kcal/mol. {frase1}",
        "{n1} poses are within 1 kcal/mol; the pose 1–2 difference is {n2} kcal/mol. {frase1}",
    ),
    (
        "Diferencia pose 1-2 {n1} kcal/mol. {frase1}",
        "Pose 1–2 difference: {n1} kcal/mol. {frase1}",
    ),
    # SCI-A-023: el ensemble sale del protocolo; las réplicas no las registra ninguna corrida.
    ("Las poses salen de un ensemble de {n1} conformaciones; no se registraron réplicas.",
     "The poses come from an ensemble of {n1} conformers; no replicates were recorded."),
    ("{n1} SEÑALES REPORTADAS", "{n1} SIGNALS REPORTED"),
    (
        "El stacking M4 se ejecuto degradado: se excluyeron componentes ausentes ({n1}) y se renormalizaron los pesos. La formula efectiva queda conservada aparte de los pesos nominales del diseno.",
        "M4 stacking ran in degraded mode: missing components ({n1}) were excluded and the weights were renormalized. The effective formula is recorded separately from the design's nominal weights.",
    ),
    (
        "{n1} poses quedan dentro de 1 kcal/mol; la selección de una sola pose es ambigua.",
        "{n1} poses are within 1 kcal/mol; selecting a single pose is ambiguous.",
    ),
    (
        "Sólo {n1} de {n2} poses recibieron veredicto físico.",
        "Only {n1} of {n2} poses received a physical verdict.",
    ),
    (
        "La pose sugerida (#{n1}) y la top-1 de Vina (#{n2}) no son la misma. Ambas se conservan.",
        "The suggested pose (#{n1}) and Vina top-1 (#{n2}) are not the same. Both are retained.",
    ),
    (
        "· <b>Validez fisica:</b> En esta corrida los controles de quimica y geometria no se evaluaron (la corrida es anterior a esa etapa o el validador no llego a emitir veredicto). Eso no dice nada sobre las poses: ausencia de evaluacion no es ausencia de choques, enlaces imposibles o artefactos de preparación.<br/><br/>",
        "· <b>Physical validity:</b> The chemistry and geometry checks were not evaluated in this run (the run predates this step, or the validator did not produce a verdict). This says nothing about the poses: no evaluation does not mean there are no clashes, impossible bonds, or preparation artifacts.<br/><br/>",
    ),
    (
        "· <b>Validez fisica:</b> Los controles de quimica y geometria de las poses se describen en su seccion (estado: {n1}). Superarlos no demuestra validez experimental ni descarta artefactos de preparacion, y «requiere revision» no es una pose aprobada.<br/><br/>",
        "· <b>Physical validity:</b> The pose chemistry and geometry checks are described in their section (status: {n1}). Passing them does not demonstrate experimental validity or rule out preparation artifacts, and ‘requires review’ is not an approved pose.<br/><br/>",
    ),
    ("Informe de evaluación · {n1}", "Evaluation report · {n1}"),
    (
        "Registro temporal de la evaluación: {n1} &nbsp;·&nbsp; MolDesign {n2}",
        "Evaluation timestamp: {n1} &nbsp;·&nbsp; MolDesign {n2}",
    ),
    (
        "<font color='{n1}'><b>SIGUIENTE ACCIÓN JUSTIFICABLE: {n2}</b></font><br/>{n3}",
        "<font color='{n1}'><b>JUSTIFIABLE NEXT ACTION: {n2}</b></font><br/>{n3}",
    ),
    (
        "Este documento responde qué evidencia computacional produjo la corrida, qué partes son reproducibles, qué supuestos hizo, qué controles superó, qué incertidumbres permanecen y qué sería justificable hacer después. No responde si la molécula es un buen fármaco.",
        "This document describes what computational evidence the run produced, which parts are reproducible, what assumptions it made, which checks it passed, what uncertainties remain, and what would be justified next. It does not answer whether the molecule is a good drug.",
    ),
    (
        "<b>Contexto Fisiológico:</b> {n1}",
        "<b>Physiological context:</b> {n1}",
    ),
    (
        "<font color='#b91c1c'><b>Reserva de especificidad:</b> La señal normalizada quedó por debajo del umbral operativo del pipeline. Los contactos reportados no coinciden suficientemente con los hotspots de referencia del catálogo. Esta observación exige revisión del patrón de contactos; no demuestra promiscuidad. La afinidad de referencia es {n1} kcal/mol.</font>",
        "<font color='#b91c1c'><b>Specificity caveat:</b> The normalized signal was below the pipeline's operational threshold. The reported contacts do not sufficiently match the catalog's reference hotspots. This observation calls for review of the contact pattern; it does not demonstrate promiscuity. Reference affinity is {n1} kcal/mol.</font>",
    ),
    (
        "<b>Margen de score de Vina (ΔΔG de docking):</b> <font color='{n1}'>{n2} kcal/mol</font>. {frase1}. Los scores de Vina entre receptores distintos no son energías libres experimentales directamente comparables, y esta diferencia no es una razón de afinidades medida.",
        "<b>Vina score margin (docking ΔΔG):</b> <font color='{n1}'>{n2} kcal/mol</font>. {frase1}. Vina scores from different receptors are not directly comparable experimental free energies, and this difference is not a measured affinity ratio.",
    ),
    (
        "<font color='#94a3b8' size='6'>* {n1} anti-target(s) subido(s) por el usuario incluido(s) en este panel.</font>",
        "<font color='#94a3b8' size='6'>* {n1} user-uploaded anti-target(s) included in this panel.</font>",
    ),
    (
        "<b>Lectura de las reglas:</b> {n1}. Estas reglas describen propiedades; no califican por sí solas la idoneidad farmacológica.",
        "<b>Rule interpretation:</b> {n1}. These rules describe properties; on their own, they do not assess pharmacological suitability.",
    ),
    ("<b>Penalizaciones Sintéticas:</b> {n1}", "<b>Synthetic penalties:</b> {n1}"),
    (
        "<b><font color='#b91c1c'>ALERTA PAINS:</font></b> Esta molecula contiene subestructuras PAINS ({n1} patrones: {n2}). Los PAINS son falsos positivos frecuentes en ensayos biologicos. Se recomienda validacion experimental exhaustiva.",
        "<b><font color='#b91c1c'>PAINS ALERT:</font></b> This molecule contains PAINS substructures ({n1} patterns: {n2}). PAINS often produce false positives in biological assays. Extensive experimental validation is recommended.",
    ),
    ("<b><font color='#b91c1c'>Alertas de Toxicoforos:</font></b> {n1}", "<b><font color='#b91c1c'>Toxicophore alerts:</font></b> {n1}"),
    ("SHA-256 del modelo: {n1}.", "Model SHA-256: {n1}."),
    (
        "- <b>Motor de docking:</b> {n1}<br/>- <b>Semilla:</b> {n2}<br/>- <b>Parser de poses:</b> {n3}<br/>- <b>Motor/modelo derivado:</b> {n4}<br/>- <b>Dominio de aplicabilidad:</b> {n5}<br/>- <b>Fallback:</b> {n6}",
        "- <b>Docking engine:</b> {n1}<br/>- <b>Seed:</b> {n2}<br/>- <b>Pose parser:</b> {n3}<br/>- <b>Derived engine/model:</b> {n4}<br/>- <b>Applicability domain:</b> {n5}<br/>- <b>Fallback:</b> {n6}",
    ),
    (
        "Preparación en condición desolvatada: la estructura depositada no tenía aguas cristalográficas dentro de la caja de acoplamiento, así que el sitio no perdió ninguna al prepararlo.",
        "Desolvated preparation: the deposited structure had no crystallographic waters inside the docking box, so none were removed from the site during preparation.",
    ),
    (
        "Preparación en condición desolvatada: se retiraron {n1} aguas cristalográficas de la caja de acoplamiento, {n2} de ellas con {n3} o más contactos a menos de {n4} Å con el receptor (la mejor coordinada, {n5}). Si alguna de esas aguas forma parte del reconocimiento en esta diana —la catalítica de la proteasa del VIH-1, la red de la bisagra en varias quinasas—, los contactos de esta corrida no la incluyen.",
        "Desolvated preparation: {n1} crystallographic waters were removed from the docking box; {n2} had at least {n3} contacts within {n4} Å of the receptor (the best-coordinated water had {n5}). If any of these waters participates in recognition by this target—such as the catalytic water in HIV-1 protease or the hinge network in some kinases—this run's contacts do not include it.",
    ),
    # Receptor propio que conserva aguas (camino B o C): `censo_de_aguas.describir_aguas_conservadas`.
    (
        "El receptor acoplado conserva {n1} agua(s) cristalográfica(s) dentro de la caja de acoplamiento: las trae el archivo que se subió, y Vina las trata como parte rígida del receptor. MolDesign no las retiró ni comprobó cuáles son estructurales; sin la estructura de origen no se sabe si se retiró alguna.",
        "The docked receptor retains {n1} crystallographic water(s) inside the docking box: they come with the uploaded file, and Vina treats them as a rigid part of the receptor. MolDesign did not remove them or check which are structural; without the source structure, it is unknown whether any were removed.",
    ),
    (
        "El receptor acoplado conserva las {n1} agua(s) cristalográfica(s) que su estructura de origen tiene dentro de la caja de acoplamiento: las decidió quien preparó el archivo, y Vina las trata como parte rígida del receptor. MolDesign no las retiró ni comprobó cuáles son estructurales.",
        "The docked receptor retains all {n1} crystallographic water(s) that its source structure has inside the docking box: they were chosen by whoever prepared the file, and Vina treats them as a rigid part of the receptor. MolDesign did not remove them or check which are structural.",
    ),
    (
        "El receptor acoplado conserva {n1} de las {n2} aguas cristalográficas que su estructura de origen tiene dentro de la caja de acoplamiento; las otras {n3} no están en el receptor. Vina trata las conservadas como parte rígida del receptor. MolDesign no comprobó cuáles son estructurales.",
        "The docked receptor retains {n1} of the {n2} crystallographic waters that its source structure has inside the docking box; the other {n3} are not in the receptor. Vina treats the retained waters as a rigid part of the receptor. MolDesign did not check which are structural.",
    ),
    (
        "Esta evaluación es anterior a la validación geométrica/física en producción. No se validó ninguna pose: no es que fallara, es que no se evaluó.",
        "This evaluation predates geometric/physical validation in production. No pose was validated: it did not fail; it was not evaluated.",
    ),
    ("La evaluación no conservó ninguna pose.", "The evaluation retained no poses."),
    ("El validador de poses no se pudo importar ({n1}).", "The pose validator could not be imported ({n1})."),
    (
        "No se pudo usar el receptor exacto de esta corrida ({n1}); no se emite veredicto geométrico.",
        "The exact receptor for this run could not be used ({n1}); no geometric verdict is issued.",
    ),
    ("El validador lanzó {n1} sobre esta pose.", "The validator raised {n1} for this pose."),
    (
        "El PDB «{n1}» no es ninguno de los tres perfiles de M5-Zn ({n2}). M5-Zn prepara, conserva el Zn, ejecuta Vina y calcula señales diagnósticas, pero no hereda los pesos de otra diana: el score compuesto queda sin calcular.",
        "PDB “{n1}” is not one of the three M5-Zn profiles ({n2}). M5-Zn prepares the receptor, retains Zn, runs Vina, and calculates diagnostic signals, but does not inherit weights from another target; the composite score is not calculated.",
    ),
    (
        "El PDB corresponde a un perfil de M5-Zn pero no se confirmó el Zn en el snapshot estructural ni en el bolsillo. Un carboxilato, tiol o sulfonamida en el ligando no convierte el caso en metaloenzima.",
        "The PDB corresponds to an M5-Zn profile, but Zn was not confirmed in the structural snapshot or binding pocket. A carboxylate, thiol, or sulfonamide in the ligand does not make the target a metalloenzyme.",
    ),
    (
        "Faltan componentes con peso distinto de cero: {n1}. No se renormalizan pesos ni se sustituye un modelo por otro; las señales que sí existen se muestran por separado.",
        "Components with nonzero weights are missing: {n1}. Weights are not renormalized, and one model is not substituted for another; available signals are shown separately.",
    ),
    (
        "Perfil {n1}: score calculado y REPRODUCIBLE, pero su benchmark está en revisión. {n2} No debe leerse como evidencia de acoplamiento metaloproteico.",
        "Profile {n1}: score calculated and REPRODUCIBLE, but its benchmark is under review. {n2} It should not be read as evidence of metalloprotein docking.",
    ),
    (
        "Perfil {n1}. Score de ranking derivado, no una afinidad ni una medida experimental. Normalización de Vina congelada en {n2}.",
        "Profile {n1}. Derived ranking score, not an affinity or experimental measurement. Vina normalization is fixed at {n2}.",
    ),
    (" | <b>Spearman ρ:</b> {n1}", " | <b>Spearman rank correlation (ρ):</b> {n1}"),
    (
        " | <b>Ligando Co-cristalizado:</b> {n1}",
        " | <b>Co-crystallized ligand:</b> {n1}",
    ),
    (
        "Corrida: <font name='{n1}'>{n2}</font>. Este informe describe el resultado de una molécula en una corrida. El <b>dossier del caso</b> (contexto, decisiones, procedencia y paquete verificable) es otro documento: se obtiene desde el informe del caso.",
        "Run: <font name='{n1}'>{n2}</font>. This report describes one molecule's result in one run. The <b>case dossier</b> (context, decisions, provenance, and verifiable package) is a separate document available from the case report.",
    ),
    (
        "Corrida no identificada en el resultado. Este informe describe el resultado de una molécula en una corrida. El <b>dossier del caso</b> (contexto, decisiones, procedencia y paquete verificable) es otro documento: se obtiene desde el informe del caso.",
        "Run not identified in the result. This report describes one molecule's result in one run. The <b>case dossier</b> (context, decisions, provenance, and verifiable package) is a separate document available from the case report.",
    ),
    # La metodología del informe terminaba con la validez física impresa a mano
    # («no evaluada en esta versión de producción»), que contradecía la matriz
    # del mismo PDF. Ahora la frase es condicional y entra por {frase1}, que se
    # traduce aparte: una frase suya que falte deja el párrafo en castellano
    # entero, en vez de mezclar idiomas (SCI-A-008).
    (
        "<b>Sistema de entrada:</b> receptor {n1}, estado de preparación {n2}, cofactores: {n3}. El informe no atribuye protonación, eliminación de aguas, minimización ni estados de carga cuando esas operaciones no fueron serializadas por la corrida.<br/><b>Exploración de poses:</b> el resultado registra {n4} poses, motor {n5}, semilla {n6} y parser {n7}. Las afinidades son señales de la función de scoring y ranking; no son medidas experimentales de energía libre.<br/><b>Modelos derivados:</b> motor {n8}, modelo {n9}, {n10}. Cada salida se reporta por separado; el informe no convierte el índice compuesto heredado en una conclusión científica.<br/>{frase1}",
        "<b>Input system:</b> receptor {n1}, preparation status {n2}, cofactors: {n3}. This report does not attribute protonation, water removal, minimization, or charge states unless the run serialized those operations.<br/><b>Pose search:</b> the result records {n4} poses, engine {n5}, seed {n6}, and parser {n7}. Affinities are signals from the scoring and ranking functions; they are not experimental free-energy measurements.<br/><b>Derived models:</b> engine {n8}, model {n9}, {n10}. Each output is reported separately; the report does not turn the legacy composite index into a scientific conclusion.<br/>{frase1}",
    ),
    # SCI-A-020/043/046-048: sin anotación curada, la clasificación y el título del
    # depósito se conservan como dato (texto del PDB, que ya está en inglés).
    ("Contexto fisiológico no disponible: el receptor no tiene una anotación funcional curada. Clasificación del depósito: {n1}; título del depósito: {n2}.",
     "Physiological context unavailable: the receptor has no curated functional annotation. Deposited classification: {n1}; deposited title: {n2}."),
    ("Contexto fisiológico no disponible: el receptor no tiene una anotación funcional curada. Clasificación del depósito: {n1}.",
     "Physiological context unavailable: the receptor has no curated functional annotation. Deposited classification: {n1}."),
    ("Contexto fisiológico no disponible: el receptor no tiene una anotación funcional curada. Título del depósito: {n1}.",
     "Physiological context unavailable: the receptor has no curated functional annotation. Deposited title: {n1}."),
    # SCI-A-026: los pesos del protocolo sin salida, con la lista de modelos.
    ("El protocolo de familia asigna peso en el stacking a {n1}, pero esas etapas no serializaron salida en esta corrida. El peso describe lo que el protocolo esperaba, no lo que aporto: no debe leerse como que ese modelo domino el resultado.",
     "The family protocol assigns stacking weight to {n1}, but those stages serialized no output in this run. The weight describes what the protocol expected, not what it contributed: it must not be read as that model having dominated the result."),
    # C-GAP-02: el contexto de ensayo frente a la corrida.
    ("Contrato {n1}: {n2} campo(s) contrastable(s) declarado(s) y {n3} sin contraparte en la corrida",
     "Contract {n1}: {n2} comparable field(s) declared and {n3} without a counterpart in the run"),
    ("Ensayo {n1} · corrida {n2}", "Assay {n1} · run {n2}"),
    ("El ensayo declara pH {n1} y el ligando se protonó a pH {n2}: la especie acoplada puede no ser la del ensayo.",
     "The assay declares pH {n1} and the ligand was protonated at pH {n2}: the docked species may not be the assay's."),
    ("El constructo del ensayo declara las cadenas {n1} y el receptor acoplado contiene {n2}.",
     "The assay construct declares chains {n1} and the docked receptor contains {n2}."),
    ("El ensayo declara {n1} y la corrida conservó {n2}.", "The assay declares {n1} and the run kept {n2}."),
    ("Coinciden dentro de ±{n1} unidades de pH.", "They match within ±{n1} pH units."),
    # CLAVE-09: con qué se enumeraron los microestados, en el dossier.
    ("dimorphite-dl {n1} · pH {n2}–{n3} · precisión {n4} · máximo {n5} · huella {n6} · recortada al máximo",
     "dimorphite-dl {n1} · pH {n2}–{n3} · precision {n4} · maximum {n5} · fingerprint {n6} · truncated at the maximum"),
    ("dimorphite-dl {n1} · pH {n2}–{n3} · precisión {n4} · máximo {n5} · huella {n6}",
     "dimorphite-dl {n1} · pH {n2}–{n3} · precision {n4} · maximum {n5} · fingerprint {n6}"),
    # CLAVE-09: la enumeración de microestados llegó al tope de dimorphite.
    ("dimorphite-dl devolvió {n1} microestados, su máximo: el conjunto puede estar incompleto y la especie acoplada se eligió entre los que devolvió.",
     "dimorphite-dl returned {n1} microstates, its maximum: the set may be incomplete and the docked species was chosen among those it returned."),
    # SCI-A-022: la corrida que sólo declara el caso.
    ("{n1} (declarada por el caso)", "{n1} (declared by the case)"),
    ("El resultado almacenado pertenece a la corrida «{n1}».", "The stored result belongs to run «{n1}»."),
    # SCI-A-068: la lista de cofactores sale de la diana cuando la corrida no registró la suya.
    ("lista de la diana (la corrida no registró la suya): {n1}",
     "the target's list (the run did not record its own): {n1}"),
    (
        "<b>Validez física:</b> los controles de química y geometría de esta corrida emitieron veredicto ({n1}) y su cobertura se detalla en su sección; superarlos no demuestra validez experimental ni descarta artefactos de preparación.",
        "<b>Physical validity:</b> the chemistry and geometry checks of this run issued a verdict ({n1}) and its coverage is detailed in its own section; passing them does not demonstrate experimental validity nor rule out preparation artifacts.",
    ),
    (
        "· <b>Selectividad:</b> Se evaluo la selectividad frente a {n1} anti-targets (margen ΔΔG: {n2} kcal/mol). Los scores de Vina entre receptores distintos no son energias libres experimentales comparables. La selectividad in vivo puede diferir debido a metabolitos activos, union a proteinas plasmaticas y efectos de dosis.",
        "· <b>Selectivity:</b> Selectivity was evaluated against {n1} anti-targets (ΔΔG margin: {n2} kcal/mol). Vina scores from different receptors are not comparable experimental free energies. In vivo selectivity may differ because of active metabolites, plasma protein binding, and dose effects.",
    ),
    ("{n1} poses serializadas; mejor afinidad cruda {n2} kcal/mol · {n3} {n4}.", "{n1} serialized poses; best raw affinity {n2} kcal/mol · {n3} {n4}."),
    ("{n1} poses serializadas; mejor afinidad cruda {n2} kcal/mol · {n3}.", "{n1} serialized poses; best raw affinity {n2} kcal/mol · {n3}."),
    ("{n1} poses serializadas; mejor afinidad cruda {n2} kcal/mol {n3}.", "{n1} serialized poses; best raw affinity {n2} kcal/mol {n3}."),
    ("{n1} poses serializadas; mejor afinidad cruda {n2} kcal/mol.", "{n1} serialized poses; best raw affinity {n2} kcal/mol."),
    (
        "Trazas mínimas {n1}/{n2} (versión del motor, semilla y parser); elementos de reconstrucción {n3}/{n4} — faltan: {n5}. Reconstrucción por un tercero: no demostrada.",
        "Minimum traces {n1}/{n2} (engine version, seed, and parser); reconstruction items {n3}/{n4} — missing: {n5}. Reconstruction by a third party: not demonstrated.",
    ),
    (
        "Trazas mínimas {n1}/{n2} (versión del motor, semilla y parser); elementos de reconstrucción {n3}/{n4}. Reconstrucción por un tercero: no demostrada.",
        "Minimum traces {n1}/{n2} (engine version, seed, and parser); reconstruction items {n3}/{n4}. Reconstruction by a third party: not demonstrated.",
    ),
    ("Faltan elementos para reconstruir la corrida: {n1}.", "Missing items for run reconstruction: {n1}."),
    # {frase…}: el nombre del modelo y el motivo del respaldo son a su vez textos
    # del sistema. El dossier compone esta frase en castellano y la traduce al
    # exportar: sin traducir lo capturado, el PDF inglés llevaba el motivo en
    # castellano («Familia 'transporter' sin modelo entrenado…»).
    (
        "{frase1}; fallback: {frase2}.. El motor de acoplamiento y su version se declaran en la traza de reproducibilidad, no aqui: son identidades distintas.",
        "{frase1}; fallback: {frase2}. The docking engine and its version are listed in the reproducibility trace, not here; they are distinct identities.",
    ),
    (
        "{frase1}. El motor de acoplamiento y su version se declaran en la traza de reproducibilidad, no aqui: son identidades distintas.",
        "{frase1}. The docking engine and its version are listed in the reproducibility trace, not here; they are distinct identities.",
    ),
    (
        "{frase1}; fallback: {frase2}. El motor de acoplamiento y su version se declaran en la traza de reproducibilidad, no aqui: son identidades distintas.",
        "{frase1}; fallback: {frase2}. The docking engine and its version are listed in the reproducibility trace, not here; they are distinct identities.",
    ),
    ("Mapa de contactos no evaluado: faltan {n1}.", "Contact map not evaluated: missing {n1}."),
    (
        "<b>Lectura de las reglas:</b> {n1}. Estas reglas describen propiedades; no califican por sí solas la idoneidad farmacológica.",
        "<b>Rule interpretation:</b> {n1}. These rules describe properties; on their own, they do not assess pharmacological suitability.",
    ),
    ("MW alto ({n1} Da)", "High molecular weight ({n1} Da)"),
    ("LogP alto ({n1})", "High LogP ({n1})"),
    ("Exceso Donadores H-Bond ({n1})", "Excess H-bond donors ({n1})"),
    ("Exceso Aceptores H-Bond ({n1})", "Excess H-bond acceptors ({n1})"),
    ("TPSA alta ({n1} Å²)", "High TPSA ({n1} Å²)"),
    ("Flexibilidad alta ({n1} rot. bonds)", "High flexibility ({n1} rotatable bonds)"),
    (
        "<b>Pesos de combinación registrados (familia {n1}):</b> {n2}",
        "<b>Recorded stacking weights (family {n1}):</b> {n2}",
    ),
    (
        "<b>Factores correctivos registrados:</b> {n1}",
        "<b>Recorded adjustment factors:</b> {n1}",
    ),
    ("'{n1}' no es un motor descargable de esta versión.", "'{n1}' is not a downloadable engine in this version."),
    ("No existe molécula con id={n1}", "No molecule exists with id={n1}"),
    ("No existe una corrida persistida con ese task_id para molecule_id={n1}", "No persisted run exists for that task_id and molecule_id={n1}"),
    ("No existe resultado persistido para molecule_id={n1}", "No persisted result exists for molecule_id={n1}"),
    ("La cohorte está en estado `{n1}` y no se puede ejecutar.", "The cohort is in state `{n1}` and cannot be run."),
    ("No se pudo preparar el receptor {n1}: {n2}", "Could not prepare receptor {n1}: {n2}"),
    ("Una corrida en estado `{n1}` no se reanuda. Sólo se reanuda lo que quedó a medias: `interrupted` o `completed_with_exceptions`.", "A run in state `{n1}` cannot be resumed. Only runs left incomplete can be resumed: `interrupted` or `completed_with_exceptions`."),
    ("La corrida está en `{n1}` y todavía puede cambiar. Un dossier de una corrida en marcha documentaría un progreso, no un resultado: espera a que termine o cancélala.", "The run is in `{n1}` and may still change. A dossier for an in-progress run would document progress, not a result: wait for it to finish or cancel it."),
    ("`sort` sólo admite `{n1}`. No hay ningún otro criterio de orden en esta superficie.", "`sort` only accepts `{n1}`. No other sort criterion is available here."),
    ("`{n1}` no es un número JSON válido. La configuración de una cohorte no admite valores no finitos.", "`{n1}` is not a valid JSON number. Cohort configuration does not allow non-finite values."),
    ("`study` no es un JSON válido: {n1}", "`study` is not valid JSON: {n1}"),
    ("El motor «{n1}» no está disponible en esta instalación; una cohorte nueva sólo puede usar {n2}.", "Engine “{n1}” is not available in this installation; a new cohort can only use {n2}."),
    ("El archivo supera el límite de {n1} MB.", "The file exceeds the {n1} MB limit."),
    ("La cohorte declara {n1} filas y el límite del producto es {n2}. Divídela en cohortes comparables en lugar de recortarla en silencio.", "The cohort declares {n1} rows, above the product limit of {n2}. Split it into comparable cohorts instead of silently truncating it."),
    ("No hay estructura local para el receptor {n1} y no es un identificador público que pueda recuperarse.", "No local structure is available for receptor {n1}, and it is not a public identifier that can be retrieved."),
    ("No se pudo obtener la estructura PDB para {n1}.", "Could not retrieve the PDB structure for {n1}."),
    ("No existe resultado para molecule_id={n1}", "No result exists for molecule_id={n1}"),
    ("No existe resultado de evaluación para molecule_id={n1}", "No evaluation result exists for molecule_id={n1}"),
    ("No se pudo obtener el PDB del receptor {n1}.", "Could not retrieve the PDB for receptor {n1}."),
    (
        "RDKit no puede parsear el SMILES '{n1}'. Verifica la sintaxis: átomos entre corchetes [], anillos cerrados con números, aromaticidad con minúsculas.",
        "RDKit could not parse SMILES '{n1}'. Check the syntax: bracket atoms [], rings closed with numbers, and aromatic atoms in lowercase.",
    ),
    ("Valencia inválida: {n1}. Ejemplo: carbono sp3 solo puede tener 4 enlaces.", "Invalid valence: {n1}. For example, an sp3 carbon can have only 4 bonds."),
    ("Error de sanitización: {n1}", "Sanitization error: {n1}"),
    ("La molécula contiene {n1} — AutoDock Vina no tiene parámetros confiables para estos elementos.", "The molecule contains {n1} — AutoDock Vina has no reliable parameters for these elements."),
    ("{n1} El score de docking puede ser impreciso.", "{n1} The docking score may be imprecise."),
    ("Átomos no soportados detectados: {n1}.", "Unsupported atoms detected: {n1}."),
    ("{n1} Verifica que la molécula sea drug-like.", "{n1} Check that the molecule is drug-like."),
    ("Carga formal atómica extrema ({n1}={n2}). Máximo permitido: ±{n3}.", "Extreme atomic formal charge ({n1}={n2}). Maximum allowed: ±{n3}."),
    ("Carga formal neta extrema ({n1}). Máximo permitido: ±{n2}.", "Extreme net formal charge ({n1}). Maximum allowed: ±{n2}."),
    (
        "Se detectaron {n1} estereocentro(s) sin estereoquimica definida. RDKit elegira un enantiomero arbitrario para el docking 3D. Usa '@' o '@@' en el SMILES para especificar la quiralidad deseada.",
        "{n1} stereocenter(s) have undefined stereochemistry. RDKit will choose an arbitrary enantiomer for 3D docking. Use '@' or '@@' in SMILES to specify the desired chirality.",
    ),
    (
        "Se detectaron {n1} doble(s) enlace(s) estereogenico(s) sin E/Z definida. El conformero 3D representara una geometria concreta; usa '/' y '\\' en el SMILES para declarar el isomero deseado.",
        "{n1} stereogenic double bond(s) have undefined E/Z configuration. The 3D conformer will represent one specific geometry; use '/' and '\\' in SMILES to specify the desired isomer.",
    ),
    ("La molécula tiene solo {n1} átomo(s) pesado(s). El mínimo para evaluación farmacológica es 5.", "The molecule has only {n1} heavy atom(s). The minimum for pharmacological evaluation is 5."),
    ("{n1}: {n2} Da y {n3} átomos pesados. {n4}. {n5}", "{n1}: {n2} Da and {n3} heavy atoms. {n4}. {n5}"),
    (
        "Masa molecular por debajo del rango de las reglas de drug-likeness ({n1} Da). El filtro de Ghose et al. 1999 empieza en {n2} Da y {n3} átomos pesados: a este tamaño esos filtros, y los umbrales de eficiencia de ligando, no están evaluando lo que dicen evaluar. El acoplamiento se ejecuta igual.",
        "Molecular weight is below the range for the drug-likeness rules ({n1} Da). The Ghose et al. 1999 filter starts at {n2} Da and {n3} heavy atoms: at this size, those filters and ligand-efficiency thresholds do not assess what they claim to assess. Docking still runs.",
    ),
    ("La molécula contiene {n1} fragmentos desconectados. En modo científico estricto se rechazan sales/mezclas para evitar ambigüedad en docking y scoring.", "The molecule contains {n1} disconnected fragments. Strict scientific mode rejects salts/mixtures to avoid ambiguity in docking and scoring."),
    ("La molécula tiene {n1} fragmentos desconectados (posiblemente una sal o mezcla). Solo se evaluará el fragmento más grande. Considera usar únicamente la parte activa.", "The molecule has {n1} disconnected fragments (possibly a salt or mixture). Only the largest fragment will be evaluated. Consider using only the active moiety."),
    ("Usando fragmento de {n1} átomos para la evaluación.", "Using a fragment with {n1} atoms for evaluation."),
    ("La molécula contiene contraiones/sales que fueron removidos automáticamente. Adicionalmente, se detectaron múltiples fragmentos y se seleccionó el fragmento orgánico más grande de {n1} átomos pesados.", "The molecule contains counterions/salts that were removed automatically. Multiple fragments were also detected, and the largest organic fragment with {n1} heavy atoms was selected."),
    ("La molécula contiene {n1} fragmentos desconectados (posiblemente una sal o mezcla). Se seleccionó el fragmento más grande de {n2} átomos pesados para la evaluación.", "The molecule contains {n1} disconnected fragments (possibly a salt or mixture). The largest fragment with {n2} heavy atoms was selected for evaluation."),
    ("SMILES inválido: {n1}", "Invalid SMILES: {n1}"),
    ("SMILES canónico {n1} · fórmula {n2} · {n3} átomos pesados.", "Canonical SMILES {n1} · formula {n2} · {n3} heavy atoms."),
    ("Elementos sin parámetros fiables en Vina: {n1}.", "Elements without reliable Vina parameters: {n1}."),
    ("El archivo existe pero no se pudo leer: {n1}.", "The file exists but could not be read: {n1}."),
    ("El PDB de {n1} todavía no está en disco y no se pudo sellar su contenido.", "The PDB for {n1} is not on disk yet, so its contents could not be hashed."),
    ("Filtrar {n1} '{n2}' no dejó ningún átomo de proteína.", "Filtering {n1} '{n2}' left no protein atoms."),
    ("Las cadenas '{n1}' aportan {n2} átomos de proteína al receptor de la corrida: el sitio se forma entre ellas.", "Chains '{n1}' contribute {n2} protein atoms to the run's receptor; the site spans these chains."),
    ("La cadena '{n1}' aporta {n2} átomos de proteína al receptor de la corrida.", "Chain '{n1}' contributes {n2} protein atoms to the run's receptor."),
    ("No evaluado: sin la fuente en disco no se puede comprobar la cadena '{n1}'.", "Not evaluated: chain '{n1}' cannot be checked without the on-disk source."),
    ("Existe un receptor preparado compatible con la cadena '{n1}' y {n2} átomos.", "A prepared receptor with chain '{n1}' and {n2} atoms is available."),
    ("El PDBQT cacheado contiene la(s) cadena(s) {n1}, no exclusivamente '{n2}'.", "The cached PDBQT contains chain(s) {n1}, not only '{n2}'."),
    ("La fuente incluye {n1} cadena(s); el receptor de la corrida sólo conserva '{n2}'.", "The source contains {n1} chain(s); the run's receptor retains only '{n2}'."),
    ("Ruta de docking: se eliminan TODAS las aguas; los metales sólo se conservan si el receptor los declara explícitamente; se conservan los cofactores orgánicos reconocidos ({n1}).", "Docking path: ALL waters are removed; metals are retained only when explicitly declared by the receptor; recognized organic cofactors are retained ({n1})."),
    ("{n1} átomos de agua", "{n1} water atoms"),
    ("{n1} átomos metálicos", "{n1} metal atoms"),
    ("{n1} átomos de cofactor orgánico", "{n1} organic cofactor atoms"),
    ("{n1} otros heteroátomos (ligandos, lípidos, aditivos)", "{n1} other heteroatoms (ligands, lipids, additives)"),
    ("{n1} ({n2} átomo{n3})", "{n1} ({n2} atom{n3})"),
    # El singular: un marcador nunca captura vacío, y «ZN (1 átomo)» quedaba en castellano.
    ("{n1} ({n2} átomo)", "{n1} ({n2} atom)"),
    # {frase1}: «NA (2 átomos), ZN (1 átomo)» se traduce elemento a elemento.
    ("Se eliminan {n1} átomos metálicos antes del acoplamiento: {frase1}.", "{n1} metal atoms are removed before docking: {frase1}."),
    ("Se eliminan {n1} átomos metálicos antes del acoplamiento.", "{n1} metal atoms are removed before docking."),
    ("El motor '{n1}' no usa la ruta Vina que inspecciona esta comprobación previa.", "Engine '{n1}' does not use the Vina path inspected by this preflight."),
    ("No se encontró el ejecutable de {n1}.", "Could not find the {n1} executable."),
    ("Open Babel {n1} presente con el hash declarado ({n2}, sha256 {n3}…). No se ejecutó para comprobarlo: esta comprobación previa no lanza procesos.", "Open Babel {n1} is present with the declared hash ({n2}, SHA-256 {n3}…). It was not run for verification: this preflight does not launch processes."),
    ("La configuración enviada tiene centro (0, 0, 0), así que la corrida derivará la caja del propio PDB: centro {n1}, lado {n2} Å (origen: {n3}).", "The submitted configuration has center (0, 0, 0), so the run will derive the box from the PDB: center {n1}, side {n2} Å (source: {n3})."),
    ("Centro {n1} · origen: {n2}; tamaño {n3} Å · origen: {n4}.", "Center {n1} · source: {n2}; size {n3} Å · source: {n4}."),
    ("Caja fuera de los límites de ejecución: lados entre {n1} y {n2} Å, centro finito entre -{n3} y {n4} Å.", "Box is outside execution limits: sides must be between {n1} and {n2} Å, and the finite center between -{n3} and {n4} Å."),
    (" El centro del sitio declarado por el catálogo queda a {n1} Å de esta caja.", " The catalog-declared site center is {n1} Å from this box."),
    ("Caja en {n1} · tamaño {n2} Å: NO abarca ningún átomo del receptor. Separación medida de {n3} Å con la extensión del receptor ({n4} a {n5} Å).{n6} La búsqueda ocurrirá en espacio vacío salvo que buscar lejos del receptor sea tu intención; queda registrado aquí.", "Box at {n1} · size {n2} Å: it contains NO receptor atoms. Measured separation from the receptor extent ({n4} to {n5} Å): {n3} Å.{n6} The search will run in empty space unless searching away from the receptor is intentional; this is recorded here."),
    ("La caja abarca volumen con átomos del receptor (extensión {n1} a {n2} Å).", "The box overlaps volume containing receptor atoms (extent {n1} to {n2} Å)."),
    ("Caja de {n1} Å³; exhaustividad efectiva {n2}.", "Box volume: {n1} Å³; effective exhaustiveness: {n2}."),
    ("Campos de nivel superior ignorados frente a pipeline_config — {n1}. La corrida ejecuta los valores de pipeline_config.stage_params.", "Top-level fields ignored in favor of pipeline_config — {n1}. The run executes the values in pipeline_config.stage_params."),
    ("Todos los residuos declarados están en la(s) cadena(s) {n1}.", "All declared residues are on chain(s) {n1}."),
    ("SA Score RDKit {n1} > 7: síntesis potencialmente difícil. La evaluación estructural continúa; SA no demuestra inviabilidad sintética.", "RDKit SA Score {n1} > 7: synthesis may be difficult. Structural evaluation continues; SA does not prove that synthesis is infeasible."),
    ("Molécula grande ({n1} átomos pesados, {n2} enlaces rotables) — el docking será lento (búsqueda conformacional extensa). Si el tiempo es un límite, revisa el tamaño de la caja y la exhaustividad de Vina; reducirlos limita la búsqueda y puede cambiar las poses. La ruta ESMFold para péptidos es exploratoria y no tiene un benchmark de precisión de poses.", "Large molecule ({n1} heavy atoms, {n2} rotatable bonds) — docking will be slow because conformational search is extensive. If time is a constraint, review the box size and Vina exhaustiveness; reducing them limits the search and may change the poses. The ESMFold peptide path is exploratory and has no pose-accuracy benchmark."),
    ("Molécula grande ({n1} átomos pesados, {n2} enlaces rotables) — el docking será lento (búsqueda conformacional extensa). Si el tiempo es un límite, revisa el tamaño de la caja y la exhaustividad de Vina; reducirlos limita la búsqueda y puede cambiar las poses.", "Large molecule ({n1} heavy atoms, {n2} rotatable bonds) — docking will be slow because conformational search is extensive. If time is a constraint, review the box size and Vina exhaustiveness; reducing them limits the search and may change the poses."),
    ("Molécula con {n1} átomos pesados y {n2} enlaces rotables — el docking puede tardar más de lo habitual. Si necesitas reducir el tiempo, revisa la caja y la exhaustividad de Vina; una búsqueda menor puede cambiar las poses.", "Molecule with {n1} heavy atoms and {n2} rotatable bonds — docking may take longer than usual. To reduce run time, review the box and Vina exhaustiveness; a smaller search may change the poses."),
    ("ipTM de interfaz: {n1}", "Interface ipTM: {n1}"),
    ("Ruta peptídica ({n1}): la estructura la predijo el modelo y el acoplamiento lo hizo AutoDock Vina. La afinidad reportada es la de Vina, sin transformar. La {n2} describe el PLEGADO, no la unión, y no se convierte a kcal/mol. Resultado exploratorio: no hay benchmark de poses ni de repetibilidad para este protocolo.", "Peptide path ({n1}): the model predicted the structure, and AutoDock Vina performed docking. The reported affinity is Vina's, untransformed. The {n2} describes FOLDING, not binding, and is not converted to kcal/mol. This is an exploratory result: this protocol has no benchmark for pose accuracy or repeatability."),
    ("{n1} de {n2} conformaciones no pasaron por el acoplamiento y se descartaron en vez de entrar con una afinidad inventada.", "{n1} of {n2} conformers did not undergo docking and were discarded instead of being assigned a fabricated affinity."),
    ("Ruta peptídica ({n1}): se obtuvo la estructura plegada pero NINGUNA pose pasó por un motor de acoplamiento ({n2} sin acoplar, {n3} sin afinidad). No se fabrica una afinidad: antes se devolvía −4.0 kcal/mol. La {n4} describe el plegado.", "Peptide path ({n1}): a folded structure was obtained, but NONE of the poses were processed by a docking engine ({n2} not docked, {n3} without affinity). No affinity is fabricated; the previous behavior returned −4.0 kcal/mol. The {n4} describes folding."),
    ("Fallo en Docking Peptídico ({frase1}). Se usó AutoDock Vina como fallback.", "Peptide docking failed ({frase1}). AutoDock Vina was used as a fallback."),
    # SCI-A-032: la causa de la sustitución, en las dos formas que emite peptide_docking.
    ("MOTOR SUSTITUIDO: se pidió '{n1}' y el servicio respondió, pero {frase1}. La pose NO viene de un modelo de plegamiento: la produjo AutoDock Vina con exhaustividad reducida (4) sobre la caja declarada en el caso. No compares este resultado con uno plegado.",
     "SUBSTITUTED ENGINE: '{n1}' was requested and the service responded, but {frase1}. The pose does NOT come from a folding model: AutoDock Vina produced it with reduced exhaustiveness (4) on the box declared in the case. Do not compare this result with a folded one."),
    ("MOTOR SUSTITUIDO: se pidió '{n1}' y ese servicio no está disponible en esta instalación ({frase1}). La pose NO viene de un modelo de plegamiento: la produjo AutoDock Vina con exhaustividad reducida (4) sobre la caja declarada en el caso. No compares este resultado con uno plegado.",
     "SUBSTITUTED ENGINE: '{n1}' was requested and that service is not available in this installation ({frase1}). The pose does NOT come from a folding model: AutoDock Vina produced it with reduced exhaustiveness (4) on the box declared in the case. Do not compare this result with a folded one."),
    ("Metales de transición detectados: {n1}. Se usa AutoDock Vina como aproximación. El docking cuántico con GFN2-xTB + AutoDock 4 está en desarrollo y se activará automáticamente en una versión futura. Los resultados de afinidad pueden ser menos precisos para compuestos de coordinación.", "Transition metals detected: {n1}. AutoDock Vina is used as an approximation. Quantum docking with GFN2-xTB + AutoDock 4 is in development and will be enabled automatically in a future version. Affinity results may be less accurate for coordination compounds."),
    ("se eligió el que coincide con los centros ionizados esperados a pH {n1} (+{n2}/−{n3})", "the one matching the expected ionized centers at pH {n1} (+{n2}/−{n3}) was selected"),
    ("La regresión de XGBoost (pKi {n1}, equivalente a {n2} kcal/mol) queda FUERA del dominio de aplicabilidad del modelo: la molécula no se parece a las del conjunto de entrenamiento. Se muestra como referencia, no como predicción. La afinidad del caso es la de Vina.", "The XGBoost regression (pKi {n1}, equivalent to {n2} kcal/mol) is OUTSIDE the model's applicability domain: the molecule is unlike those in the training set. It is shown as a reference, not a prediction. The case affinity is Vina's."),
    ("No se pudo encolar: {n1}", "Could not enqueue: {n1}"),
    ("Cola de evaluaciones saturada: no se pudo iniciar en {n1}s.", "Evaluation queue is saturated; could not start within {n1}s."),
    ("Timeout: evaluación excedió {n1}s de ejecución.", "Timeout: evaluation exceeded {n1}s of run time."),
    ("⚠️ Molécula grande ({n1} átomos pesados, {n2} enlaces rotables) — el docking será lento (búsqueda conformacional extensa). Si el tiempo es un límite, revisa el tamaño de la caja y la exhaustividad de Vina; reducirlos limita la búsqueda y puede cambiar las poses. La ruta ESMFold para péptidos es exploratoria y no tiene un benchmark de precisión de poses.", "Large molecule ({n1} heavy atoms, {n2} rotatable bonds) — docking will be slow because conformational search is extensive. If time is a constraint, review the box size and Vina exhaustiveness; reducing them limits the search and may change the poses. The ESMFold peptide path is exploratory and has no pose-accuracy benchmark."),
    ("⚠️ Molécula grande ({n1} átomos pesados, {n2} enlaces rotables) — el docking será lento (búsqueda conformacional extensa). Si el tiempo es un límite, revisa el tamaño de la caja y la exhaustividad de Vina; reducirlos limita la búsqueda y puede cambiar las poses.", "Large molecule ({n1} heavy atoms, {n2} rotatable bonds) — docking will be slow because conformational search is extensive. If time is a constraint, review the box size and Vina exhaustiveness; reducing them limits the search and may change the poses."),
    ("⚠️ Molécula con {n1} átomos pesados y {n2} enlaces rotables — el docking puede tardar más de lo habitual. Si necesitas reducir el tiempo, revisa la caja y la exhaustividad de Vina; una búsqueda menor puede cambiar las poses.", "⚠️ Molecule with {n1} heavy atoms and {n2} rotatable bonds — docking may take longer than usual. To reduce run time, review the box and Vina exhaustiveness; a smaller search may change the poses."),
    ("Selectividad en background no disponible: {n1}", "Background selectivity is unavailable: {n1}"),
    ("La etapa de validacion estructural lanzo {n1}. El acoplamiento de esta evaluacion NO se ve afectado.", "The structural validation stage raised {n1}. Docking for this evaluation is NOT affected."),
    ("El ensemble de {n1} conformaciones no se pudo generar ({n2}); la corrida sigue con una sola.", "The ensemble of {n1} conformers could not be generated ({n2}); the run will continue with one."),
    (
        "Todavía no hay corridas terminadas en este equipo, así que esto sale de un modelo medido en otra máquina. Se calibrará solo a partir del acoplamiento número {n1}.",
        "No runs have finished on this computer yet, so this estimate comes from a model measured on another computer. It will be calibrated only after docking run {n1}.",
    ),
    (
        "En este equipo hay {n1} acoplamiento terminado, menos de los {n2} que hacen falta para calibrar, así que esto sale de un modelo medido en otra máquina. Se calibrará solo a partir del acoplamiento número {n2}.",
        "This computer has {n1} completed docking run, fewer than the {n2} needed for calibration, so this estimate comes from a model measured on another computer. It will be calibrated only after docking run {n2}.",
    ),
    (
        "En este equipo hay {n1} acoplamientos terminados, menos de los {n2} que hacen falta para calibrar, así que esto sale de un modelo medido en otra máquina. Se calibrará solo a partir del acoplamiento número {n2}.",
        "This computer has {n1} completed docking runs, fewer than the {n2} needed for calibration, so this estimate comes from a model measured on another computer. It will be calibrated only after docking run {n2}.",
    ),
    (
        "Calibrado con {n1} acoplamientos que ya se ejecutaron en este equipo.",
        "Calibrated from {n1} docking runs already completed on this computer.",
    ),
    (
        "La preparación retira {n1} átomos de agua, {n2} otros heteroátomos (ligandos, lípidos, aditivos).",
        "Preparation removes {n1} water atoms and {n2} other heteroatoms (ligands, lipids, and additives).",
    ),
    # Cualquier otra combinación de aguas, metales, cofactores y otras especies.
    ("La preparación retira {frase1}.", "Preparation removes {frase1}."),
    # Avisos de la preparación del receptor (vina_service): salían en castellano en inglés.
    (
        "Meeko eliminó residuos del receptor fuera del margen crítico: {frase1}.",
        "Meeko removed receptor residues outside the critical margin: {frase1}.",
    ),
    (
        "El cristal no resolvía {count} cadena(s) lateral(es); se truncaron a ALA o GLY, conservando sólo átomos observados. EN EL SITIO, así que la cavidad acoplada pierde esos grupos: {n1}.",
        "The crystal did not resolve {count} side chain(s); they were truncated to ALA or GLY, keeping only the observed atoms. IN THE SITE, so the docked cavity loses those groups: {n1}.",
    ),
    (
        "El cristal no resolvía {count} cadena(s) lateral(es); se truncaron a ALA o GLY, conservando sólo átomos observados, todas fuera del sitio.",
        "The crystal did not resolve {count} side chain(s); they were truncated to ALA or GLY, keeping only the observed atoms, all outside the site.",
    ),
    # Estereoquímica sin declarar (ligand_state_warnings): cada frase por separado.
    (
        "La entrada dejó {count} centro(s) quirales y {total} doble(s) enlace(s) E/Z sin especificar.",
        "The input left {count} chiral center(s) and {total} E/Z double bond(s) unspecified.",
    ),
    ("Isómero derivado del conformero 3D: {n1}.", "Isomer derived from the 3D conformer: {n1}."),
    ("{count} doble(s) enlace(s) siguen sin clasificar desde 3D.", "{count} double bond(s) remain unclassified from 3D."),
    # Frases fijas que el código compone dentro de un f-string: plantillas sin marcadores.
    ("No se pudo identificar el isómero derivado del conformero 3D.", "The isomer derived from the 3D conformer could not be identified."),
    ("No se evaluaron los demás estereoisómeros.", "The other stereoisomers were not evaluated."),
    (
        "Este receptor no tiene Spearman ρ medido y su familia estructural no tiene stacking calibrado: se ejecuta con el contrato alpha conservador común. No hay evidencia de que el ranking correlacione con afinidad real aquí. Trata el resultado como una hipótesis a comprobar, no como una medida.",
        "This receptor has no measured Spearman ρ, and its structural family has no calibrated stacking, so it runs under the shared conservative alpha contract. There is no evidence that the ranking correlates with actual affinity here. Treat the result as a hypothesis to test, not as a measurement.",
    ),
    (
        "Más allá de Ro5 (bRo5) ({n1} Da). Beyond Rule of Five (Doak, Over, Giordanetto, Kihlberg, Chem. Biol. 21:1115, 2014): 500 < MW ≤ 1000 Da. Espacio con fármacos orales reales —macrociclos, péptidos cíclicos, inhibidores de interacción proteína-proteína— que la regla de los cinco excluye por construcción. La corrida se ejecuta; lo que deja de aplicar son los filtros de Ro5 y los umbrales de eficiencia de ligando, que no están calibrados a este tamaño.",
        "Beyond Ro5 (bRo5) ({n1} Da). Beyond the Rule of Five (Doak, Over, Giordanetto, Kihlberg, Chem. Biol. 21:1115, 2014): 500 < MW ≤ 1000 Da. This is a space occupied by real oral drugs—macrocycles, cyclic peptides, and protein–protein interaction inhibitors—that the Rule of Five excludes by construction. The run proceeds; Ro5 filters and ligand-efficiency thresholds do not apply because they are not calibrated for this size.",
    ),
    (
        "{n1} acoplamiento · exhaustiveness {n2} sobre {n3} núcleos",
        "{n1} docking run · exhaustiveness {n2} across {n3} cores",
    ),
    (
        "Tu equipo tiene {n1} núcleos y la exhaustividad es {n2}: las búsquedas van en {n3} tandas. Bajarla a {n1} haría la corrida más rápida sin cambiar el receptor ni la caja.",
        "Your computer has {n1} cores and exhaustiveness is {n2}: the searches run in {n3} batches. Lowering it to {n1} would make the run faster without changing the receptor or search box.",
    ),
    (
        "Plantillas de histidina de Meeko: {n1}.",
        "Meeko histidine templates: {n1}.",
    ),
    (
        "El selector recomienda la pose {n1} con un margen de {n2}. Es una RECOMENDACIÓN: la pose principal del producto sigue siendo la {n3} de Vina.",
        "The selector recommends pose {n1} with a margin of {n2}. This is a RECOMMENDATION: the product's primary pose remains Vina pose {n3}.",
    ),
    (
        "PoseBusters en configuracion `{n1}` -sin verdad de terreno, que en produccion no existe-. Ningun control de quimica o geometria falla. Ausencia de alertas no significa ausencia de choques, enlaces imposibles o artefactos de preparacion.",
        "PoseBusters in `{n1}` mode—without ground truth, which is not available in production. No chemistry or geometry checks fail. The absence of alerts does not mean there are no clashes, impossible bonds, or preparation artifacts.",
    ),
    # ABS-TR-01: el detalle del validador físico, frase a frase, en todos sus estados.
    # El productor (pose_physical_validity.py) está sellado; sólo se traduce.
    ("PoseBusters en configuracion `{n1}` -sin verdad de terreno, que en produccion no existe-.",
     "PoseBusters in `{n1}` mode—without ground truth, which is not available in production."),
    ("Ningun control de quimica o geometria falla.",
     "No chemistry or geometry checks fail."),
    ("Fallan {count} controles de quimica o geometria: {n1}.",
     "{count} chemistry or geometry check(s) fail: {n1}."),
    ("No se pudieron cargar entradas ({n1}), asi que los controles intermoleculares NO se evaluaron: eso es un problema de la entrada, no de la pose.",
     "Some inputs could not be loaded ({n1}), so the intermolecular checks were NOT evaluated: that is a problem with the input, not with the pose."),
    ("{count} controles no devolvieron un booleano y NO se cuentan como superados: {n1}.",
     "{count} check(s) did not return a boolean and are NOT counted as passed: {n1}."),
    ("Ausencia de alertas no significa ausencia de choques, enlaces imposibles o artefactos de preparacion.",
     "The absence of alerts does not mean there are no clashes, impossible bonds, or preparation artifacts."),
    ("No se pudo reconstruir la pose para validarla ({n1}).",
     "The pose could not be reconstructed for validation ({n1})."),
    ("No se pudo reconstruir la representación canónica de hidrógenos ({n1}).",
     "The canonical hydrogen representation could not be reconstructed ({n1})."),
    ("El proxy energetico RDKit no pudo ejecutarse ({frase1}).",
     "The RDKit energy proxy could not run ({frase1})."),
    ("Bateria completa no ejecutada: {frase1}.",
     "Full battery not run: {frase1}."),
    ("Solo se corrio un PROXY ENERGETICO RDKit NO CALIBRADO, que **no** es el control `internal_energy` de PoseBusters: usa MMFF en vez de UFF, {count} conformeros en vez de {total} y una razon distinta, y su umbral no esta calibrado contra ninguna medicion.",
     "Only an UNCALIBRATED RDKit ENERGY PROXY was run, which is **not** PoseBusters' `internal_energy` check: it uses MMFF instead of UFF, {count} conformers instead of {total} and a different ratio, and its threshold is not calibrated against any measurement."),
    ("Razon {n1} contra un umbral de {n2}: dentro de rango.",
     "Ratio {n1} against a threshold of {n2}: within range."),
    ("Razon {n1} contra un umbral de {n2}: FUERA de rango.",
     "Ratio {n1} against a threshold of {n2}: OUT of range."),
    ("ESE VALOR FUERA DE RANGO NO ES UN VEREDICTO DE FALLA: `PROD-PV-H-01` midio que este proxy rechaza el 14.2% de las poses que el control oficial de PoseBusters aprueba, y siempre en esa direccion.",
     "THAT OUT-OF-RANGE VALUE IS NOT A FAILURE VERDICT: `PROD-PV-H-01` measured that this proxy rejects 14.2% of the poses that the official PoseBusters check passes, always in that direction."),
    ("Por eso se reporta como revision y no como control fallido.",
     "That is why it is reported as review and not as a failed check."),
    ("No se evaluaron distancias al receptor, valencias, aromaticidad ni planaridad.",
     "Distances to the receptor, valences, aromaticity and planarity were not evaluated."),
    ("PoseBusters no esta instalado en este entorno",
     "PoseBusters is not installed in this environment"),
    ("no se paso la ruta del receptor, y la configuracion `dock` la necesita para los controles intermoleculares",
     "the receptor path was not passed, and the `dock` mode needs it for the intermolecular checks"),
    ("PoseBusters fallo al ejecutarse ({n1})",
     "PoseBusters failed to run ({n1})"),
    ("no se pudo parametrizar la molecula",
     "the molecule could not be parameterized"),
    ("no se generaron conformeros de referencia",
     "no reference conformers were generated"),
    ("el ensemble de referencia no dio energias",
     "the reference ensemble produced no energies"),
    (
        "Se comparan los recuentos de carga formal de cada microestado con los centros que Henderson-Hasselbalch predice ionizados a pH {n1}, usando los pKa por clase de este módulo. Los empates se rompen por orden alfabético del SMILES, no por el orden de dimorphite-dl, que no es reproducible entre corridas.",
        "The formal-charge counts for each microstate are compared with the centers Henderson–Hasselbalch predicts to be ionized at pH {n1}, using this module's class-based pKa values. Ties are broken by alphabetical SMILES order, not by dimorphite-dl order, which is not reproducible across runs.",
    ),
    (
        "{n1} tautómeros enumerados y ninguno descartado con evidencia; la especie acoplada se identifica aparte",
        "{n1} tautomers enumerated, and none were excluded based on evidence; the docked species is identified separately",
    ),
    (
        "El margen entre la primera y la segunda ({n1}) no llega al umbral de abstención ({n2}). El selector no recomienda.",
        "The margin between the top two poses ({n1}) is below the abstention threshold ({n2}). The selector makes no recommendation.",
    ),
    (
        "{n1} se ejecuta en un servicio aparte que esta versión no instala. La aplicación sabe hablar con él, pero hay que levantarlo y todavía no hay ninguna dirección configurada.",
        "{n1} runs as a separate service that this version does not install. The application can communicate with it, but the service must be started and no address is configured yet.",
    ),
    (
        "{n1} se ejecuta en un servicio aparte que esta versión no instala. La aplicación sabe hablar con él, pero hay que levantarlo y ahora mismo apunta a {n2}.",
        "{n1} runs as a separate service that this version does not install. The application can communicate with it, but the service must be started; it currently points to {n2}.",
    ),
    (
        "ESMFold está instalado y apagado. Se enciende cuando lo pidas y ocupa memoria sólo mientras esté encendido.",
        "ESMFold is installed and off. It starts when requested and uses memory only while running.",
    ),
    (
        "Meeko elimina {n1} residuo(s) a 6 Å o menos de la caja, del sitio: {n2}. No se acopla contra un sitio incompleto.",
        "Meeko removes {n1} residue(s) within 6 Å of the box or binding site: {n2}. Docking will not use an incomplete site.",
    ),
    (
        "Meeko no puede construir el receptor ({n1}).",
        "Meeko could not build the receptor ({n1}).",
    ),
    (
        "Plantillas de histidina asignadas por Meeko: {n1}. La asignación procede de plantillas y no valida el microestado experimental ni un pH concreto.",
        "Meeko-assigned histidine templates: {n1}. The assignment is template-based and does not validate the experimental microstate or a specific pH.",
    ),
    (
        "Eficiencia de ligando LE={n1} (kcal/mol por átomo pesado). Los umbrales convencionales ({n2} / {n3}, Hopkins et al. {n4}) están calibrados en espacio Ro5 y no se aplican a esta molécula: a este tamaño LE decrece por construcción. Se informa el valor sin veredicto.",
        "Ligand efficiency LE={n1} (kcal/mol per heavy atom). Conventional thresholds ({n2} / {n3}, Hopkins et al. {n4}) are calibrated in Rule of Five space and do not apply to this molecule: at this size, LE decreases by construction. The value is reported without a verdict.",
    ),
    (
        "Familia '{n1}' sin modelo validado (quality gate: p {n2} >= {n3}) — modelo universal usado.",
        "Family '{n1}' has no validated model (quality gate: p {n2} >= {n3}) — the universal model was used.",
    ),
    (
        "{n1} · cadenas {n2} (medido sobre los bytes del PDBQT hasheado)",
        "{n1} · chains {n2} (measured from the hashed PDBQT bytes)",
    ),
    (
        "cadenas {n1} — el caso declaró la cadena {n2}; el PDBQT acoplado contiene {n3} (medido sobre los bytes del PDBQT hasheado)",
        "chains {n1} — the case declared chain {n2}; the docked PDBQT contains {n3} (measured from the hashed PDBQT bytes)",
    ),
    (
        "{count} molécula(s) canónica(s) llevan etiquetas `active` contradictorias en distintas filas. No se elige una por el usuario.",
        "{count} canonical molecule(s) carry contradictory `active` labels in different rows. One is not chosen on the user's behalf.",
    ),
    (
        "Sólo hay {count} moléculas etiquetadas con afinidad; el mínimo para que la métrica signifique algo es {total}.",
        "There are only {count} labeled molecules with an affinity; the minimum for the metric to mean anything is {total}.",
    ),
    # El valor de «Receptor acoplado» sin su paréntesis, que va en la razón. Con
    # {ids…}, sólo identificadores: no se traga un párrafo que empiece igual.
    ("{ids1} · cadenas {ids2}", "{ids1} · chains {ids2}"),
    ("cadenas {ids1}", "chains {ids1}"),
    (
        "{n1} = LE / LE_scale(HA), con LE_scale = 0.0715 + 7.5328/HA + 25.7079/HA² − 361.4722/HA³ (Reynolds, Tounge, Bembenek, J. Med. Chem. 51 (2008) 2432, ec. 1-2). LE_scale usada: {n2} en unidades de pKi. PROXY: la escala está ajustada contra Ki experimental, no contra scores de acoplamiento; la conversión usa {n3} kcal/mol por unidad logarítmica. FQ ≈ 1 significa proximidad a la envolvente eficiente del conjunto de Reynolds para ese tamaño — no es probabilidad de unión ni calidad de pose.",
        "{n1} = LE / LE_scale(HA), where LE_scale = 0.0715 + 7.5328/HA + 25.7079/HA² − 361.4722/HA³ (Reynolds, Tounge, Bembenek, J. Med. Chem. 51 (2008) 2432, Eq. 1–2). LE_scale used: {n2} in pKi units. PROXY: the scale was fitted against experimental Ki, not docking scores; the conversion uses {n3} kcal/mol per log unit. FQ ≈ 1 means proximity to the efficient frontier of the Reynolds set for that size—it is not a probability of binding or pose quality.",
    ),
    (
        "{n1} = LE / LE_scale(HA), con LE_scale = 0.0715 + 7.5328/HA + 25.7079/HA² − 361.4722/HA³ (Reynolds, Tounge, Bembenek, J. Med. Chem. 51 (2008) 2432, ec. 1-2). LE_scale usada: {n2} en unidades de pKi. PROXY: la escala está ajustada contra Ki experimental, no contra scores de acoplamiento; la conversión usa {n3} kcal/mol por unidad logarítmica. FQ ≈ 1 significa proximidad a la envolvente eficiente del conjunto de Reynolds para ese tamaño — no es probabilidad de unión ni calidad de pose. La escala se sujetó a HA={n4}: el ajuste de Reynolds cubre 15-50 átomos pesados y esta molécula queda fuera, así que el valor es un límite, no una interpolación.",
        "{n1} = LE / LE_scale(HA), where LE_scale = 0.0715 + 7.5328/HA + 25.7079/HA² − 361.4722/HA³ (Reynolds, Tounge, Bembenek, J. Med. Chem. 51 (2008) 2432, Eq. 1–2). LE_scale used: {n2} in pKi units. PROXY: the scale was fitted against experimental Ki, not docking scores; the conversion uses {n3} kcal/mol per log unit. FQ ≈ 1 means proximity to the efficient frontier of the Reynolds set for that size—it is not a probability of binding or pose quality. The scale was capped at HA={n4}: the Reynolds fit covers 15–50 heavy atoms, and this molecule falls outside that range, so the value is a bound, not an interpolation.",
    ),
    (
        "{n1} (umbral {n2})",
        "{n1} (threshold {n2})",
    ),
    (
        "{n1} agua(s)",
        "{n1} water(s)",
    ),
    (
        "El ligando del cristal ({n1}) se retiró como parte de la corrida.",
        "The crystal ligand ({n1}) was removed as part of the run.",
    ),
    ("No resuelto: {n1}: {n2}", "Unresolved: {n1}: {n2}"),
    (
        "Curado estructuralmente; sin calibrar y sin pipeline de familia — faltan Spearman ρ del receptor y stacking calibrado para su familia",
        "Structurally curated; calibration and a family pipeline are missing — the receptor's Spearman ρ and calibrated stacking for its family are missing",
    ),
    (
        "{n1} · familia {n2}",
        "{n1} · {n2} family",
    ),
    (
        "modelo {n1}; fallback: {frase2}. El motor de acoplamiento y su version se declaran en la traza de reproducibilidad, no aqui: son identidades distintas.",
        "{n1} model; fallback: {frase2}. The docking engine and its version are listed in the reproducibility trace, not here; they are distinct identities.",
    ),
    (
        "Familia '{n1}' sin modelo entrenado disponible — modelo universal usado.",
        "Family '{n1}' has no trained model available — the universal model was used.",
    ),
    # SCI-A-007: `review` tiene dos causas y el texto nombraba sólo una. Las
    # frases viajan por separado: `traducir` va frase a frase, así que cambiar
    # una redacción sin mover su par deja el párrafo entero en castellano.
    (
        'La batería no corrió entera sobre todas las poses, o la pose principal pasa y alguna alternativa falla.',
        'Either the full check suite did not run on every pose, or the primary pose passes while an alternative fails.',
    ),
    (
        '«Revisión necesaria» describe una comprobación que hay que mirar, NO una pose aprobada.',
        '‘Review required’ describes a check that must be inspected, NOT an approved pose.',
    ),
    (
        'Motor: no declarado.',
        'Engine: not declared.',
    ),
    (
        'Motor: {n1}.',
        'Engine: {n1}.',
    ),
    (
        'Cobertura {n1}/{n2} poses.',
        'Coverage: {n1}/{n2} poses.',
    ),
    (
        'Calibrado para este receptor (Spearman ρ medido) — ρ = {n1}, IC 95 % [{n2}; {n3}], n = {n4}',
        'Calibrated for this receptor (measured Spearman ρ) — ρ = {n1}, 95% CI [{n2}; {n3}], n = {n4}',
    ),
    (
        'Calibrado para este receptor (Spearman ρ medido) (ρ = {n1}, IC 95 % [{n2}; {n3}], n = {n4}, panel {ids1})',
        'Calibrated for this receptor (measured Spearman ρ) (ρ = {n1}, 95% CI [{n2}; {n3}], n = {n4}, panel {ids1})',
    ),
    (
        'El ranking del motor se calibró para este receptor con exhaustividad {n1}, {n2} poses y semilla {n3}; la medida describe corridas con esos parámetros.',
        'The engine ranking was calibrated for this receptor with exhaustiveness {n1}, {n2} poses and seed {n3}; the measurement describes runs with those parameters.',
    ),
    (
        'Pipeline calibrado por familia; este receptor no está calibrado individualmente — falta calibrar Spearman ρ contra afinidades medidas de este receptor',
        'Family-calibrated pipeline; this receptor is not individually calibrated — Spearman ρ has not been calibrated against measured affinities for this receptor',
    ),
    (
        'Sin curar: sin familia estructural conocida — falta curar el receptor: familia estructural, preparación y Spearman ρ',
        'Not curated: no known structural family — the receptor still needs curation: structural family, preparation, and Spearman ρ',
    ),
    (
        'Medido con exhaustividad {e}, {p} poses y semilla {s}.',
        'Measured with exhaustiveness {e}, {p} poses and seed {s}.',
    ),
    (
        'Verificado · ρ = {rho} (IC 95 %: {a}–{b}; n = {n}; {endpoint}, {panel}).',
        'Verified · ρ = {rho} (95% CI: {a}–{b}; n = {n}; {endpoint}, {panel}).',
    ),
    (
        'Pose del cristal reproducida en {ok} de {semillas} semillas (RMSD ≤ 2 Å).',
        'Crystal pose reproduced in {ok} of {semillas} seeds (RMSD ≤ 2 Å).',
    ),
    # Las dos variantes del sello que no describe la corrida, ANTES de la que sólo
    # difiere: con `.+?`, {difiere} se tragaría «… y no declara …».
    (
        'El sello se midió con exhaustividad {e}, {p} poses y semilla {s} sobre el receptor {sha}; esta corrida difiere en {difiere} y no declara {campos}: la calibración no la describe.',
        'The seal was measured with exhaustiveness {e}, {p} poses and seed {s} on receptor {sha}; this run differs in {difiere} and does not declare {campos}: the calibration does not describe it.',
    ),
    (
        'El sello se midió con exhaustividad {e}, {p} poses y semilla {s} sobre el receptor {sha}; esta corrida no declara {campos}: no se puede comprobar que la calibración la describa.',
        'The seal was measured with exhaustiveness {e}, {p} poses and seed {s} on receptor {sha}; this run does not declare {campos}: it cannot be confirmed that the calibration describes it.',
    ),
    (
        'El sello se midió con exhaustividad {e}, {p} poses y semilla {s} sobre el receptor {sha}; esta corrida difiere en {difiere}: la calibración no la describe.',
        'The seal was measured with exhaustiveness {e}, {p} poses and seed {s} on receptor {sha}; this run differs in {difiere}: the calibration does not describe it.',
    ),
    (
        'Condición declarada: {codigo}.',
        'Declared condition: {codigo}.',
    ),
    (
        'Aviso del catálogo: {codigo}.',
        'Catalog notice: {codigo}.',
    ),
)

@dataclass(frozen=True)
class _PlantillaCompilada:
    regex: re.Pattern[str]
    ingles: str


def _normalizar(texto: str) -> str:
    return " ".join(texto.split())


def _literal_flexible(texto: str) -> str:
    """Escape a literal while accepting normalized whitespace runs."""
    partes = re.split(r"(\s+)", texto)
    return "".join(r"\s+" if parte.isspace() else re.escape(parte) for parte in partes)


def _compilar(es: str, en: str) -> _PlantillaCompilada:
    marcadores_es = Counter(_MARCADOR.findall(es))
    marcadores_en = Counter(_MARCADOR.findall(en))
    if marcadores_es != marcadores_en:
        raise ValueError(f"Template markers differ: {es!r} / {en!r}")

    partes: list[str] = []
    vistos: set[str] = set()
    cursor = 0
    for coincidencia in _MARCADOR.finditer(es):
        partes.append(_literal_flexible(es[cursor:coincidencia.start()]))
        nombre = coincidencia.group(1)
        if nombre in vistos:
            partes.append(f"(?P={nombre})")
        elif nombre in {"count", "total"}:
            partes.append(f"(?P<{nombre}>\\d+)")
        elif nombre == "ph":
            # Sólo un número: con `.+?` y DOTALL, «…a pH {n1}» casaba un párrafo
            # entero que empezara así y dejaba el resto sin traducir.
            partes.append(f"(?P<{nombre}>\\d+(?:[.,]\\d+)?)")
        elif nombre.startswith("ids"):
            # Identificadores (PDB, cadenas «A+B»): nunca una frase.
            partes.append(f"(?P<{nombre}>[A-Za-z0-9+,]+)")
        else:
            partes.append(f"(?P<{nombre}>.+?)")
            vistos.add(nombre)
        cursor = coincidencia.end()
    partes.append(_literal_flexible(es[cursor:]))
    return _PlantillaCompilada(re.compile("^" + "".join(partes) + "$", re.DOTALL), en)


#: Elementos sueltos de una lista capturada por {frase…}. Van los últimos: con `.+?`
#: casarían también una lista entera, y eso se resuelve elemento a elemento.
PLANTILLAS_DE_ELEMENTOS: tuple[tuple[str, str], ...] = (
    ("{n1} ({n2} Å de la caja)", "{n1} ({n2} Å from the box)"),
    ("{n1} ({n2} Å de la caja, retirado)", "{n1} ({n2} Å from the box, removed)"),
    ("{n1} ×{n2} ({frase1})", "{n1} ×{n2} ({frase1})"),
)

_PLANTILLAS = tuple(_compilar(es, en) for es, en in (
    *PLANTILLAS_ES_EN, *PLANTILLAS_RECEPTORES_PROPIOS, *PLANTILLAS_DE_ELEMENTOS))

#: Castellano que no debe quedar dentro de una traducción: tildes o palabras
#: funcionales en minúscula (los códigos de residuo van en mayúsculas: «SIN», «LA»).
_PARECE_CASTELLANO = re.compile(r"[áéíóúñ¿¡]|\b(?:el|la|los|las|del|que|con|sin|una|por|para|se|es|al|de|y)\b")


def _aplicar_plantilla(plantilla: _PlantillaCompilada, texto: str) -> str | None:
    coincidencia = plantilla.regex.fullmatch(texto)
    if coincidencia is None:
        return None
    grupos = coincidencia.groupdict()
    for nombre, valor in grupos.items():
        if nombre.startswith("frase") and valor:
            grupos[nombre] = _traducir_frase_capturada(valor)
            # Mejor el mensaje entero en castellano que traducido a medias.
            if _PARECE_CASTELLANO.search(grupos[nombre]):
                return None
    try:
        return plantilla.ingles.format_map(grupos)
    except (KeyError, ValueError):
        return None


def _partir_lista(valor: str) -> list[str]:
    """Los elementos de «a (x, y), b»: sólo las comas fuera de paréntesis separan."""
    elementos, actual, nivel = [], [], 0
    i = 0
    while i < len(valor):
        caracter = valor[i]
        nivel += {"(": 1, ")": -1}.get(caracter, 0)
        if nivel == 0 and valor.startswith(", ", i):
            elementos.append("".join(actual))
            actual, i = [], i + 2
            continue
        actual.append(caracter)
        i += 1
    elementos.append("".join(actual))
    return elementos


def _traducir_frase_capturada(valor: str) -> str:
    """Un texto del sistema capturado por {frase…}, traducido; si no se conoce, intacto.

    La plantilla puede haberse comido su punto final («…usado.. El motor»): se
    prueba también con él y se devuelve sin él. Una lista se traduce elemento a
    elemento cuando entera no casa sin dejar castellano.
    """
    candidatas = [traducir(valor, "en")]
    if not valor.endswith("."):
        con_punto = traducir(valor + ".", "en")
        if con_punto != valor + "." and con_punto.endswith("."):
            candidatas.append(con_punto[:-1])
    elementos = _partir_lista(valor)
    if len(elementos) > 1:
        candidatas.append(", ".join(traducir(e, "en") for e in elementos))
    for candidata in candidatas:
        if candidata != valor and not _PARECE_CASTELLANO.search(candidata):
            return candidata
    return candidatas[0]


def _traducir_una(texto: str) -> str | None:
    directa = ENGLISH_MESSAGES.get(texto)
    if directa is not None:
        return directa

    normalizado = _normalizar(texto)
    directa = ENGLISH_MESSAGES.get(normalizado)
    if directa is not None:
        return directa

    for plantilla in _PLANTILLAS:
        traducida = _aplicar_plantilla(plantilla, texto)
        if traducida is not None:
            return traducida
    return None


def traducir(texto: str, idioma: str) -> str:
    """Translate a complete message, leaving it intact if any sentence fails."""
    if (
        not isinstance(texto, str)
        or not isinstance(idioma, str)
        or idioma.lower().split("-", 1)[0] != "en"
    ):
        return texto

    coincidencia = _traducir_una(texto)
    if coincidencia is not None:
        return coincidencia

    separadores = list(_SEPARAR_FRASES.finditer(texto))
    if separadores:
        frases: list[str] = []
        cursor = 0
        for separador in separadores:
            frases.append(texto[cursor:separador.start()])
            cursor = separador.end()
        frases.append(texto[cursor:])
        traducidas = [_traducir_una(frase) for frase in frases]
        if all(frase is not None for frase in traducidas):
            partes: list[str] = []
            for indice, frase in enumerate(traducidas):
                partes.append(frase or "")
                if indice < len(separadores):
                    partes.append(separadores[indice].group())
            return "".join(partes)
    return texto
