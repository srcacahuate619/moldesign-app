from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def test_store_declara_molcy_beta_procesos_y_descarga_consentida():
    text=(ROOT/"docs/STORE_RUNFULLTRUST_JUSTIFICATION.md").read_text(encoding="utf-8")
    for marker in ("Molcy", "Beta", "%SystemRoot%", "PowerShell", "404453484", "3849d17a", "Molecular Nodes", "GPL-3.0-or-later", "explicit", "solicitud explícita"):
        assert marker in text

def test_store_declara_politica_no_verificada_y_limite_path():
    text=(ROOT/"docs/STORE_RUNFULLTRUST_JUSTIFICATION.md").read_text(encoding="utf-8")
    assert "no está verificada" in text
    assert "shutil.which" in text and "compute_quantum_features.py" in text
    assert "propietario" in text and "msix/msix-config.json" in text

def test_avisos_rdkit_nombran_componentes_y_evidencia_incompleta():
    text=(ROOT/"frontend/public/legal/THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    for marker in ("rdFreeSASA.pyd", "FreeSASA", "Telex", "Amadeus", "Roboto", "SA_Score", "NP_Score", "Christopher Kuenneth", "no verificado"):
        assert marker in text
