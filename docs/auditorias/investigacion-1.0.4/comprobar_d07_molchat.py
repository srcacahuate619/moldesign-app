"""Sonda sin proveedor de IA del campo legacy en el MolChat distribuido."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SIDE = ROOT / "tools/molchat"
sys.path.insert(0, str(SIDE / "src"))

from molchat_agent.conversation.deterministic import MoleculeProps, build_rank_response
from molchat_agent.conversation.engine import ConversationEngine
from molchat_agent.conversation.tools import MoleculeRecord

question = "¿Cuál tiene mayor score?"
direct = [MoleculeProps("A", total_score=83), MoleculeProps("B", total_score=42)]
platform = [
    ConversationEngine._to_props("A", MoleculeRecord("A", "CCO", {"mw": 46.1, "total_score": 83})),
    ConversationEngine._to_props("B", MoleculeRecord("B", "CCN", {"mw": 45.1, "total_score": 42})),
]
manifest = json.loads((SIDE / "molchat-manifest.json").read_text(encoding="utf-8"))
files = ("src/molchat_agent/conversation/deterministic.py", "src/molchat_agent/conversation/engine.py",
         "src/molchat_agent/conversation/tools.py")
inputs = {p: hashlib.sha256((SIDE / p).read_bytes()).hexdigest() for p in files}
for path, sha in inputs.items():
    assert sha == manifest["archivos"][path]["sha256"], path

result = {"commit": manifest["fuente"]["commit"], "archivos_sha256": inputs,
          "pregunta": question, "si_contexto_tipado_recibe_score": build_rank_response(question, direct),
          "por_mapeo_de_propiedades": build_rank_response(question, platform)}
assert result["si_contexto_tipado_recibe_score"] and result["por_mapeo_de_propiedades"] is None
print(json.dumps(result, ensure_ascii=True, indent=2))
