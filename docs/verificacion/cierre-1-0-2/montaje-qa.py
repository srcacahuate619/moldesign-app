"""Paneles de revisión visual: las capturas originales permanecen intactas."""
from pathlib import Path
from PIL import Image, ImageDraw
import json
import re

ROOT = Path(__file__).resolve().parent
COMBOS = [(l, t, w) for w in (1024, 1440) for t in ("dark", "light") for l in ("es", "en")]
records = {}
for path in (ROOT / "capturas").glob("*.json"):
    item = json.loads(path.read_text(encoding="utf-8-sig"))
    if (item.get("commit", "").startswith(("66c682ae", "9628aa1c", "873d2307", "93b004cf", "33be61be", "44c3a97e"))
        and path.stem == item.get("name")
        and re.fullmatch(r"(inicio|opciones|acerca|molchat|evaluacion|resultado|nuevo-caso|detalles|parametros|parametros-final|motores|hotspots|dossier|historial|moldex|moldex-final|lotes|lote-fila|lote-dossier|catalogo-8hfi|catalogo-intento|catalogo-1uzj|preparacion-especie|preparacion-receptor|ciencia|ciencia-paper|molcy-8hfi|molcy-1uzj|molcy-corrida|lanzador)-(es|en)-(dark|light)-(1024|1440)", item["name"])):
        records[item["name"]] = item
areas = sorted({name.rsplit("-", 3)[0] for name in records if name.endswith(("-1024", "-1440"))})
(ROOT / "paneles").mkdir(exist_ok=True)
index = []
for area in areas:
    for group in range(2):
        board = Image.new("RGB", (1040, 1632), "#dddddd")
        draw = ImageDraw.Draw(board)
        for slot, (locale, theme, width) in enumerate(COMBOS[group * 4:group * 4 + 4]):
            name = f"{area}-{locale}-{theme}-{width}"
            path = ROOT / "capturas" / f"{name}.png"
            x, y = (slot % 2) * 520, (slot // 2) * 816
            draw.text((x + 8, y + 6), name, fill="#111111")
            if name not in records or not path.exists():
                draw.text((x + 8, y + 32), "PENDIENTE", fill="#aa0000")
                continue
            source = Image.open(path).convert("RGB")
            # Pantallas altas: tres bandas cubren cabecera, centro y final.
            if source.height > 1600:
                band = min(source.height, int(source.width * 0.5))
                positions = [0, (source.height - band) // 2, source.height - band]
                for i, top in enumerate(positions):
                    image = source.crop((0, top, source.width, top + band))
                    image.thumbnail((512, 252))
                    board.paste(image, (x + 4, y + 28 + i * 256))
            else:
                source.thumbnail((512, 780))
                board.paste(source, (x + 4, y + 28))
        target = ROOT / "paneles" / f"{area}-{group + 1}.jpg"
        board.save(target, quality=90)
        index.append(target.name)
(ROOT / "paneles" / "indice.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
print(json.dumps({"areas": areas, "paneles": len(index), "capturas_finales": len(records)}))
