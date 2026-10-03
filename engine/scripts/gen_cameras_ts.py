"""Gera apps/worker/src/data/cameras.ts a partir de engine/config/cameras.json (fonte única do catálogo de câmeras).

Uso: py engine/scripts/gen_cameras_ts.py
Cada item tem `embed` ({type,url}) quando o provedor permite prévia, ou `embed: null` (só cartão com link).
Itens com `enabled: false` não vão para o Worker.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
data = json.loads((ROOT / "engine/config/cameras.json").read_text(encoding="utf-8"))
q = lambda x: json.dumps(x, ensure_ascii=False)  # noqa: E731
lines = [
    "// GERADO por engine/scripts/gen_cameras_ts.py a partir de engine/config/cameras.json. Não edite à mão.",
    "// O PULSO é apenas o placeholder: mostra a prévia do próprio provedor (quando ele permite) e leva o clique à página de origem.",
    'import type { CameraFeed } from "@pulso/shared";',
    "",
    "export const CAMERAS: CameraFeed[] = [",
]
for c in data["cameras"]:
    if not c.get("enabled"):
        continue
    e = c.get("embed")
    prev = f'{{ type: {q(e["type"])}, url: {q(e["url"])} }}' if e else "null"
    lat = "null" if c.get("lat") is None else c["lat"]
    lon = "null" if c.get("lon") is None else c["lon"]
    lines.append(
        f'\t{{ id: {q(c["id"])}, label: {q(c["label"])}, city: {q(c["city"])}, state: {q(c["state"])}, provider: {q(c["provider"])}, '
        f'attribution: {q(c["attribution"])}, page_url: {q(c["page_url"])}, preview: {prev}, lat: {lat}, lon: {lon} }},'
    )
lines.append("];\n")
out = ROOT / "apps/worker/src/data/cameras.ts"
out.write_text("\n".join(lines), encoding="utf-8", newline="\n")
print("gravado", out, sum(1 for c in data["cameras"] if c.get("enabled")), "câmeras")
