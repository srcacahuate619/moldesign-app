"""Inglés de lo que dicen la comprobación previa, Preparación y las advertencias de un receptor propio.

Se mantiene aparte de ``i18n_catalog.py`` y ``i18n_plantillas.py`` para que quien revise un cambio de
la subida vea juntos el texto en castellano y su par. Ambos módulos lo incorporan al final.

Los textos con datos (hashes, cadenas, residuos, distancias) son plantillas ``{marcador}``: el valor
capturado se copia sin tocar.
"""

from __future__ import annotations

#: Frases enteras (sin datos variables).
MENSAJES: dict[str, str] = {
    # ── Un PDBQT sin estructura de origen ────────────────────────────────────
    "Sin la estructura de origen no se puede saber qué se retiró al preparar este PDBQT: súbela junto al PDBQT para auditar.":
        "Without the source structure it cannot be known what was removed when this PDBQT was prepared: upload it together with the PDBQT to audit.",
    "Sin la estructura de origen no se puede saber qué se retiró al preparar el PDBQT: súbela para auditar.":
        "Without the source structure it cannot be known what was removed when the PDBQT was prepared: upload it to audit.",
    "Sube la estructura de origen del PDBQT (PDB o mmCIF) junto con el PDBQT y vuelve a evaluar: con ella Preparación calcula qué especies se retiraron.":
        "Upload the PDBQT's source structure (PDB or mmCIF) together with the PDBQT and evaluate again: with it, Preparation computes which species were removed.",
    "Un PDBQT no lleva el JSON de plantillas de Meeko: la protonación es la que declaró quien lo preparó y MolDesign no la puede comprobar.":
        "A PDBQT does not carry Meeko's template JSON: the protonation is the one declared by whoever prepared it and MolDesign cannot check it.",
    "Sin la estructura de origen no se puede saber qué se retiró al preparar el PDBQT (aguas, metales, cofactores, residuos, huecos). Súbela junto al PDBQT para auditar.":
        "Without the source structure it cannot be known what was removed when the PDBQT was prepared (waters, metals, cofactors, residues, gaps). Upload it together with the PDBQT to audit.",
    "El receptor es el PDBQT tal como se subió: no se filtra ninguna cadena.":
        "The receptor is the PDBQT as uploaded: no chain is filtered.",
    "El PDBQT se usa tal cual: MolDesign no retira aguas, metales ni cofactores. Lo que contiene es lo que decidió quien lo preparó.":
        "The PDBQT is used as is: MolDesign does not remove waters, metals or cofactors. What it contains is what whoever prepared it decided.",
    "Un resultado no se puede comparar con otro sin declarar la política de cada ruta.":
        "One result cannot be compared with another without declaring the policy of each route.",
    "La corrida lo usa tal cual; su hash entra en la huella.":
        "The run uses it as is; its hash enters the fingerprint.",
    "No se pudo leer el PDBQT que se subió; la corrida no tiene receptor.":
        "The uploaded PDBQT could not be read; the run has no receptor.",
    "La declara quien preparó el PDBQT; MolDesign no la comprueba ni la modifica.":
        "It is declared by whoever prepared the PDBQT; MolDesign neither checks nor modifies it.",
    "Un PDBQT no lleva el JSON de plantillas de Meeko, así que no se puede atribuir una protonación concreta a cada residuo. El hash del archivo identifica lo que se acopla.":
        "A PDBQT does not carry Meeko's template JSON, so a specific protonation cannot be attributed to each residue. The file hash identifies what is docked.",
    # ── Protonación declarada por el usuario ─────────────────────────────────
    "MolDesign usó la protonación del archivo tal como venía y no la modificó. No fija un pH ni comprueba el estado de histidinas, ácidos y bases del sitio: la responsabilidad de esa decisión es de quien preparó el receptor.":
        "MolDesign used the protonation in the file as it came and did not modify it. It sets no pH and does not check the state of histidines, acids and bases at the site: the responsibility for that decision lies with whoever prepared the receptor.",
    "Archivo del receptor": "Receptor file",
    "El receptor conserva las aguas que traía el archivo; las retiradas eran de otras cadenas o estaban lejos de la unidad que se acopla. La decisión sobre cuáles son estructurales y cuáles desplazables es de quien preparó el receptor.":
        "The receptor keeps the waters the file carried; the removed ones belonged to other chains or were far from the unit being docked. The decision on which are structural and which displaceable lies with whoever prepared the receptor.",
    "Declarada por el usuario (origen: usuario)": "Declared by the user (origin: user)",
    "La protonación del receptor es la declarada por quien lo preparó (origen: usuario); MolDesign no la comprueba ni fija un pH.":
        "The receptor protonation is the one declared by whoever prepared it (origin: user); MolDesign does not check it or set a pH.",
    "No se pudo leer el PDBQT subido.": "The uploaded PDBQT could not be read.",
    # ── Estructura ya preparada por el usuario (camino B) ──
    "MolDesign conservó la protonación del archivo y comprobó, residuo a residuo, que Meeko aplicó las plantillas declaradas. No fija un pH ni decide si es la adecuada para el sitio: la responsabilidad de esa decisión es de quien preparó el receptor.":
        "MolDesign kept the protonation in the file and checked, residue by residue, that Meeko applied the declared templates. It sets no pH and does not decide whether it is adequate for the site: the responsibility for that decision lies with whoever prepared the receptor.",
    "Receptor ya preparado por el usuario: se conservan las aguas, los metales y los cofactores que trae el archivo (sin lista blanca). Sólo se retiran, y se declaran, las especies de otras cadenas y las que Meeko no puede representar lejos del sitio.":
        "Receptor already prepared by the user: the waters, metals and cofactors in the file are kept (no whitelist). Only species of other chains and those Meeko cannot represent far from the site are removed, and declared.",
    "Junto al sitio la preparación se abstiene: ni se adivinan ni se retiran en silencio. Lejos de él se retiran y se declaran.":
        "Next to the site the preparation abstains: they are neither guessed nor silently removed. Far from it they are removed and declared.",
    "MolDesign no fija un pH ni decide la protonación: la responsabilidad es de quien preparó el receptor.":
        "MolDesign sets no pH and does not decide the protonation: the responsibility lies with whoever prepared the receptor.",
    "Es la estructura de origen del PDBQT: sólo se usa para auditarlo; el receptor de la corrida es el PDBQT tal como se subió.":
        "It is the PDBQT's source structure: it is only used to audit it; the run's receptor is the PDBQT as uploaded.",
}

#: Frases con datos: ``{marcador}`` se copia tal cual.
PLANTILLAS: tuple[tuple[str, str], ...] = (
    ("cargas y radios del PQR descartados en {n} átomos (Vina no los usa)",
     "PQR charges and radii discarded for {n} atoms (Vina does not use them)"),
    ("cadena asignada (A) a {n} átomos sin cadena", "chain assigned (A) to {n} atoms without a chain"),
    ("residuos terminales reducidos: {lista}", "terminal residues reduced: {lista}"),
    ("Ninguno retirado a {m} Å o menos", "None removed at {m} Å or less"),
    ("Ninguno retirado a {m} Å o menos; conservados: {lista}", "None removed at {m} Å or less; kept: {lista}"),
    ("Retirados a {m} Å o menos: {lista}", "Removed at {m} Å or less: {lista}"),
    ("Ninguna retirada a {m} Å o menos; {n} conservada(s)", "None removed at {m} Å or less; {n} kept"),
    (
        "{n} retirada(s) a {m} Å o menos: {lista}; ninguna conservada",
        "{n} removed at {m} Å or less: {lista}; none kept",
    ),
    (
        "{n} retirada(s) a {m} Å o menos: {lista}; {k} conservada(s): {lista2}",
        "{n} removed at {m} Å or less: {lista}; {k} kept: {lista2}",
    ),
    ("Retiradas: {lista}", "Removed: {lista}"),
    ("{n} fuera del margen del sitio: {lista}", "{n} outside the site margin: {lista}"),
    (
        "Cofactores o residuos modificados sin plantilla Meeko validada, lejos del sitio: {frase1}. No forman parte de la cavidad acoplada.",
        "Cofactors or modified residues without a local Meeko template, far from the site: {frase1}. They are not part of the docked cavity.",
    ),
    ("nombres de residuo traducidos: {lista}", "residue names translated: {lista}"),
    (
        "La declara quien preparó el archivo: {n} residuo(s) con protonación en el nombre, y Meeko aplicó exactamente esas plantillas.",
        "It is declared by whoever prepared the file: {n} residue(s) with protonation in the name, and Meeko applied exactly those templates.",
    ),
    (
        "La declara quien preparó el archivo: {n} residuo(s) con protonación en el nombre, y Meeko aplicó exactamente esas plantillas. Plantillas de histidina: {lista}.",
        "It is declared by whoever prepared the file: {n} residue(s) with protonation in the name, and Meeko applied exactly those templates. Histidine templates: {lista}.",
    ),
    (
        "{n} especie(s) del archivo no tienen plantilla en Meeko o no se pueden tipar para Vina: {lista}.",
        "{n} species in the file have no Meeko template or cannot be typed for Vina: {lista}.",
    ),
    (
        "La protonación del receptor es la declarada por quien lo preparó (origen: usuario); MolDesign comprobó que Meeko aplicó las plantillas declaradas ({n} residuos) y no fija un pH.",
        "The receptor protonation is the one declared by whoever prepared it (origin: user); MolDesign checked that Meeko applied the declared templates ({n} residues) and sets no pH.",
    ),
    (
        "La protonación del receptor es la declarada por quien lo preparó (origen: usuario); MolDesign comprobó que Meeko aplicó las plantillas declaradas ({n} residuos) y no fija un pH. Plantillas de histidina comprobadas: {lista}.",
        "The receptor protonation is the one declared by whoever prepared it (origin: user); MolDesign checked that Meeko applied the declared templates ({n} residues) and sets no pH. Histidine templates checked: {lista}.",
    ),
    ("modelo 1 de {n}", "model 1 of {n}"),
    ("cadenas renombradas: {lista}", "chains renamed: {lista}"),
    ("elemento inferido del nombre en {n} átomos", "element inferred from the name in {n} atoms"),
    ("códigos largos sustituidos: {lista}", "long codes replaced: {lista}"),
    ("ensamblaje {id} aplicado ({n} operadores)", "assembly {id} applied ({n} operators)"),
    ("ensamblaje {id} aplicado (1 operador)", "assembly {id} applied (1 operator)"),
    ("origen: {fmt} SHA-256 {sha}", "source: {fmt} SHA-256 {sha}"),
    (
        "el PDBQT corresponde al origen ({n} de {m} residuos; desplazamiento mediano {d} Å)",
        "the PDBQT matches the source ({n} of {m} residues; median displacement {d} Å)",
    ),
    (
        "el ensamblaje {id} no cubre todos los polímeros del archivo ({lista} quedan fuera) y aplicar sus operadores a todas las cadenas inventaría copias",
        "assembly {id} does not cover all the polymers in the file ({lista} are left out) and applying its operators to every chain would invent copies",
    ),
    (
        "el ensamblaje {id} usa operadores distintos para cadenas distintas y el formato de matrices que lee MolDesign no puede expresarlo",
        "assembly {id} uses different operators for different chains and the matrix format MolDesign reads cannot express it",
    ),
    (
        "{pdb} se subió como PDBQT sin estructura de origen (SHA-256 {sha}): se evaluará exactamente ese archivo.",
        "{pdb} was uploaded as a PDBQT without a source structure (SHA-256 {sha}): exactly that file will be evaluated.",
    ),
    (
        "{pdb} se subió como PDBQT sin estructura de origen: se evaluará exactamente ese archivo.",
        "{pdb} was uploaded as a PDBQT without a source structure: exactly that file will be evaluated.",
    ),
    (
        "La cadena declarada '{cadena}' no aparece en el PDBQT, que contiene {lista}. Se acopla contra lo que contiene.",
        "The declared chain '{cadena}' does not appear in the PDBQT, which contains {lista}. Docking runs against what it contains.",
    ),
    (
        "El PDBQT aporta {n} átomos de las cadenas {lista} al receptor de la corrida.",
        "The PDBQT contributes {n} atoms from chain(s) {lista} to the run's receptor.",
    ),
    (
        "El receptor es el PDBQT que subiste, sin cambios ({n} átomos).",
        "The receptor is the PDBQT you uploaded, unchanged ({n} atoms).",
    ),
    (
        "La protonación del receptor es la declarada por quien lo preparó (origen: usuario); MolDesign no la comprueba ni fija un pH. Plantillas de histidina comprobadas: {lista}.",
        "The receptor protonation is the one declared by whoever prepared it (origin: user); MolDesign does not check it or set a pH. Histidine templates checked: {lista}.",
    ),
    # Estructuras predichas: confianza (pLDDT) junto al sitio.
    ("Sin indicios de estructura predicha en el archivo (método declarado: {metodo}).",
     "No evidence of a predicted structure in the file (declared method: {metodo})."),
    ("pLDDT medio {media} en {n} residuos ({k} por debajo de 70)",
     "mean pLDDT {media} over {n} residues ({k} below 70)"),
    ("sin residuos con pLDDT a {m} Å o menos de la caja", "no residues with pLDDT within {m} Å of the box"),
    ("sitio (a {m} Å o menos de la caja): {n} residuos, pLDDT mínimo {minimo}, medio {media}",
     "site (within {m} Å of the box): {n} residues, minimum pLDDT {minimo}, mean {media}"),
    ("{n} por debajo de 70: {lista}", "{n} below 70: {lista}"),
    ("otros {n} por debajo de 70 sin listar", "{n} more below 70 not listed"),
    ("{n} residuos del sitio sin pLDDT", "{n} site residues without pLDDT"),
)

#: «Archivo del receptor» se compone con una frase por hecho, separadas por « · ». Cada frase se traduce sola.
MENSAJES.update({
    "modo: estructura cruda, preparada por MolDesign": "mode: raw structure, prepared by MolDesign",
    "modo: estructura preparada por el usuario, respetada tal como venía":
        "mode: structure prepared by the user, respected as it came",
    "modo: PDBQT listo para Vina, sin estructura de origen": "mode: PDBQT ready for Vina, without a source structure",
    "modo: PDBQT listo para Vina, con estructura de origen": "mode: PDBQT ready for Vina, with a source structure",
    "convertido de mmCIF a PDB clásico": "converted from mmCIF to classic PDB",
    "convertido de PQR a PDB clásico": "converted from PQR to classic PDB",
    "números de serie de átomo repetidos (más de 99 999 átomos)":
        "atom serial numbers repeat (more than 99,999 atoms)",
    # Motivos de ensamblaje (conversion_mmcif._decidir_ensamblaje), tras «unidad asimétrica: »
    "el archivo no declara ensamblajes": "the file declares no assemblies",
    "el archivo declara ensamblajes pero sus tablas están incompletas y no se pudieron interpretar":
        "the file declares assemblies but their tables are incomplete and could not be interpreted",
})


# ── Estructuras predichas: confianza (pLDDT) junto al sitio ───────────────────
#: Las frases de ``services/dossier/preparacion_confianza.py``: una por hecho, separadas por « · ».
MENSAJES.update({
    "Confianza de la estructura (pLDDT)": "Structure confidence (pLDDT)",
    "El archivo es un modelo predicho (ModelCIF) pero no declara el pLDDT por residuo: no se lee la confianza del sitio.":
        "The file is a predicted model (ModelCIF) but does not declare the per-residue pLDDT: the confidence of the site is not read.",
    "El archivo parece una estructura predicha, pero MolDesign sólo tiene verificada la convención de AlphaFold DB (factor B = pLDDT, escala 0–100). De Boltz, Chai-1 y AlphaFold 3 no se verificó con un archivo real dónde guardan el pLDDT, así que no se afirma ni se lee.":
        "The file looks like a predicted structure, but MolDesign has only verified the AlphaFold DB convention (B-factor = pLDDT, scale 0–100). For Boltz, Chai-1 and AlphaFold 3 it was not verified with a real file where they store the pLDDT, so it is neither claimed nor read.",
    "Todos los valores de pLDDT del archivo son ≤ 1: podrían estar en escala 0–1 o ser una confianza ínfima. No se interpreta sin verificar la convención de esa fuente.":
        "All the pLDDT values in the file are ≤ 1: they could be on a 0–1 scale or be a negligible confidence. They are not interpreted without verifying that source's convention.",
    "El factor B del archivo no coincide con el pLDDT que declara _ma_qa_metric_local: no se sabe cuál es el correcto y no se usa ninguno.":
        "The file's B-factor does not match the pLDDT declared by _ma_qa_metric_local: it is not known which one is right and neither is used.",
    "Un PQR no conserva el factor B ni el método del archivo original: no se puede saber si la estructura es una predicción ni leer su confianza.":
        "A PQR does not keep the B-factor or the method of the original file: it cannot be known whether the structure is a prediction, nor its confidence read.",
    "Un PDBQT no conserva el factor B ni el método: sin la estructura de origen no se puede saber si es una predicción ni leer su confianza.":
        "A PDBQT does not keep the B-factor or the method: without the source structure it cannot be known whether it is a prediction, nor its confidence read.",
    "Confirma la cavidad con una estructura experimental del mismo receptor, o decide con tu criterio si el modelo basta para el sitio. Preparación no bloquea por esto.":
        "Confirm the cavity with an experimental structure of the same receptor, or decide on your own judgment whether the model is enough for the site. Preparation does not block on this.",
    "Hay residuos junto al sitio con pLDDT por debajo de 70: su posición es una conjetura del modelo y la cavidad acoplada podría no ser así. No bloquea: es una decisión científica abierta.":
        "There are residues next to the site with pLDDT below 70: their position is the model's guess and the docked cavity may not look like this. It does not block: it is an open scientific decision.",
    "La corrida no midió el pLDDT de los residuos junto al sitio.":
        "The run did not measure the pLDDT of the residues next to the site.",
    "Ningún residuo con pLDDT junto a la caja: no se puede juzgar la confianza del sitio.":
        "No residue with pLDDT next to the box: the confidence of the site cannot be judged.",
    "Sin indicios de estructura predicha en el archivo (no declara método).":
        "No evidence of a predicted structure in the file (no method declared).",
    "estructura predicha por AlphaFold DB": "structure predicted by AlphaFold DB",
    "estructura predicha (ModelCIF)": "predicted structure (ModelCIF)",
    "estructura predicha": "predicted structure",
    "pLDDT leído del factor B (convención verificada con un archivo real de AlphaFold DB)":
        "pLDDT read from the B-factor (convention verified with a real AlphaFold DB file)",
    "pLDDT leído de _ma_qa_metric_local (convención verificada con un archivo real de AlphaFold DB)":
        "pLDDT read from _ma_qa_metric_local (convention verified with a real AlphaFold DB file)",
    "pLDDT leído de _ma_qa_metric_local (declarado por el archivo; convención de esta fuente sin verificar con un archivo real)":
        "pLDDT read from _ma_qa_metric_local (declared by the file; this source's convention not verified with a real file)",
    "el pLDDT del sitio no se midió": "the pLDDT of the site was not measured",
    "pLDDT leído del archivo (convención sin verificar con un archivo real)":
        "pLDDT read from the file (convention not verified with a real file)",
})


# ── Resto de cadenas fijas de la subida de un receptor propio ─────────────────
MENSAJES.update({
    "PDBQT subido por el investigador": "PDBQT uploaded by the researcher",
    "sin identificar": "unidentified",
    "preparer_respetando.filtrar_respetando (la función que ejecuta la corrida)":
        "preparer_respetando.filtrar_respetando (the function the run executes)",
    "Especies que Meeko no puede representar": "Species Meeko cannot represent",
    "Declarada por quien preparó el PDBQT; MolDesign no la comprueba (no hay informe de la herramienta que lo preparó ni pH declarado)":
        "Declared by whoever prepared the PDBQT; MolDesign does not check it (there is no report from the tool that prepared it and no declared pH)",
    "El PDBQT se usa tal cual; no pasa por Meeko ni se vuelve a protonar.":
        "The PDBQT is used as is; it does not go through Meeko or get protonated again.",
    "El PDBQT guardado ya no coincide con el hash registrado al subirlo; no se evalúa.":
        "The stored PDBQT no longer matches the hash recorded when it was uploaded; it is not evaluated.",
    "Meeko no pudo preparar el receptor respetando su protonación y sus especies.":
        "Meeko could not prepare the receptor while respecting its protonation and species.",
    "La preparación terminó sin generar el receptor .pdbqt.":
        "The preparation finished without generating the .pdbqt receptor.",
    "Meeko no escribió el JSON de plantillas del receptor.":
        "Meeko did not write the receptor's template JSON.",
    "selenometionina → metionina (Se → S)": "selenomethionine → methionine (Se → S)",
    "estructura cruda, preparada por MolDesign": "raw structure, prepared by MolDesign",
    "estructura preparada por el usuario, respetada tal como venía":
        "structure prepared by the user, respected as it came",
    "PDBQT listo para Vina, sin estructura de origen": "PDBQT ready for Vina, without a source structure",
    "PDBQT listo para Vina, con estructura de origen": "PDBQT ready for Vina, with a source structure",
    "Sin la estructura de origen MolDesign no puede auditar qué se retiró al preparar este PDBQT: súbela para que Preparación lo audite.":
        "Without the source structure MolDesign cannot audit what was removed when this PDBQT was prepared: upload it so Preparation audits it.",
    "Vina no usa las cargas del PQR: la carga parcial del PDBQT la calcula Meeko.":
        "Vina does not use the PQR charges: the PDBQT partial charge is computed by Meeko.",
    "el PQR no los trae: se escriben 1,00 y 0,00": "the PQR does not carry them: 1.00 and 0.00 are written",
    "pLDDT en _ma_qa_metric_local (ModelCIF)": "pLDDT in _ma_qa_metric_local (ModelCIF)",
    "AF-P23975-F1-model_v6.pdb y .cif, descargados de alphafold.ebi.ac.uk el 2026-10-09: el factor B (PDB) y B_iso_or_equiv (mmCIF) son el pLDDT por residuo, escala 0–100, y coinciden con _ma_qa_metric_local":
        "AF-P23975-F1-model_v6.pdb and .cif, downloaded from alphafold.ebi.ac.uk on 2026-10-09: the B-factor (PDB) and B_iso_or_equiv (mmCIF) are the per-residue pLDDT, scale 0–100, and match _ma_qa_metric_local",
})
