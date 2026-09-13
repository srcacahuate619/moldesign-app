"""
services/ai/tools/admet_tools.py

Herramienta offline de predicción ADMET usando ADMET-AI (modelos locales).
"""

from __future__ import annotations

from services.ai.tool_registry import ToolDef, get_tool_registry


async def predict_admet(smiles: str) -> str:
    """Predecir propiedades ADMET usando ADMET-AI (modelos locales)."""
    try:
        from chem.blood_viability import get_admet_model
        model = get_admet_model()
        if model is None:
            return "Error: ADMET-AI no disponible."
        results = model.predict(smiles)

        if not results:
            return "Error: ADMET-AI no pudo procesar este SMILES."

        lines = ["Predicciones ADMET:"]
        for prop, value in results.items():
            if isinstance(value, (float, int)):
                v = round(value, 2) if isinstance(value, float) else value
                lines.append(f"  {prop}: {v}")
            else:
                lines.append(f"  {prop}: {value}")

        return "\n".join(lines[:12])
    except ImportError:
        return "Error: ADMET-AI no instalado."
    except Exception as e:
        return f"Error en ADMET: {str(e)[:150]}"


def register_admet_tools():
    registry = get_tool_registry()
    registry.register(ToolDef(
        name="predict_admet",
        clase="inferencia",
        procedencia="ADMET-AI local (modelo entrenado, no medida)",
        description=(
            "Predice ADMET: solubilidad (LogS), BBB, absorción intestinal (HIA), "
            "toxicidad hepática, unión a proteínas (PPB). Tarda ~3-5s."
        ),
        parameters={"smiles": {"type": "string", "required": True}},
        offline=True,
        fn=predict_admet,
    ))
