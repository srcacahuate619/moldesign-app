"""Texto de contexto fisiológico para los certificados de MolDesign.

Este módulo no interpreta resultados ni modifica la evaluación.  Sólo conserva
la clasificación textual que antes vivía acoplada al renderer de ReportLab.
"""


def generate_physiological_context(pdb_id: str, header_lines: str | None) -> str:
    """Devuelve el contexto fisiológico a partir de los headers de un PDB.

    ``pdb_id`` se conserva en el contrato público porque los certificados lo
    proporcionan y futuros catálogos pueden usarlo. La clasificación actual se
    basa exclusivamente en el contenido del encabezado, igual que antes.
    """
    del pdb_id

    if not header_lines:
        return "Descripción fisiológica no disponible para este receptor personalizado."

    text = header_lines.upper()

    if any(k in text for k in ("GPCR", "RECEPTOR", "5-HT", "DOPAMINE", "ADRENERGIC", "SEROTONIN", "ACETYLCHOLINE", "GLYCOPROTEIN")):
        return (
            "Este target clasifica como un Receptor Acoplado a Proteínas G (GPCR) o receptor transmembranal. "
            "Los GPCRs median la transducción de señales extracelulares al interior celular a través de cascadas "
            "enzimáticas mediadas por nucleótidos de guanina. Son dianas esenciales en neurofarmacología y endocrinología."
        )
    if any(k in text for k in ("KINASE", "PHOSPHOTRASE", "TYROSINE KINASE", "MAPK", "CDK")):
        return (
            "Este target clasifica como una Proteína Quinasa (Kinase). Las quinasas son enzimas que catalizan la "
            "transferencia de grupos fosfato desde el ATP a sustratos específicos, actuando como interruptores críticos "
            "en vías de proliferación, crecimiento y señalización celular. Altamente relevantes en oncología."
        )
    if any(k in text for k in ("PROTEASE", "PEPTIDASE", "HYDROLASE", "HIV PROTEASE", "MPRO", "COV PROTEASE")):
        return (
            "Este target clasifica como una Hidrolasa / Proteasa. Las proteasas (ej. aspartil o cisteín proteasas) "
            "catalizan la ruptura de enlaces peptídicos de proteínas. Son dianas esenciales para el control del "
            "procesamiento de poliproteínas funcionales y la replicación en ciclos de infección viral (como en VIH o Coronavirus)."
        )
    if any(k in text for k in ("CHANNEL", "ION CHANNEL", "PORE", "PUMP", "POTASSIUM", "SODIUM", "CALCIUM")):
        return (
            "Este target clasifica como un Canal Iónico o transportador de membrana. Regula de manera selectiva "
            "el paso de iones a través de la bicapa lipídica, manteniendo el gradiente electroquímico e interviniendo "
            "en la excitabilidad neuronal, contracción muscular y señalización de segundos mensajeros."
        )

    return "Estructura proteica personalizada del usuario. Interactúa como catalizador o transductor de señal intracelular."
