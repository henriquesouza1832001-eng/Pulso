"""O catálogo servido pelo Worker (TypeScript) e o cameras.json do Engine precisam falar das mesmas câmeras."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_worker_catalog_matches_cameras_json():
    cams = json.loads((ROOT / "engine/config/cameras.json").read_text(encoding="utf-8"))["cameras"]
    ts = (ROOT / "apps/worker/src/data/cameras.ts").read_text(encoding="utf-8")
    ts_ids = {i for i in re.findall(r'id: "([^"]+)"', ts) if not i.startswith("panel-")}
    assert ts_ids == {c["id"] for c in cams}
    for c in cams:
        assert c["embed"]["url"] in ts and c["page_url"].startswith("https://")
        assert (c["lat"] is None) == (c["lon"] is None)


def test_no_duplicate_cameras():
    """Mesma câmera nunca entra duas vezes: nem pelo stream/iframe, nem pelo par provedor + rótulo."""
    cams = json.loads((ROOT / "engine/config/cameras.json").read_text(encoding="utf-8"))["cameras"]
    urls = [c["embed"]["url"].strip().lower().rstrip("/") for c in cams]
    assert len(urls) == len(set(urls)), "dois itens apontam para o mesmo stream"
    names = [(c["provider"].lower(), c["label"].lower()) for c in cams]
    assert len(names) == len(set(names)), "dois itens com o mesmo provedor e rótulo"
    ts = (ROOT / "apps/worker/src/data/cameras.ts").read_text(encoding="utf-8")
    page_ids = re.findall(r'id: "([^"]+)"', ts)
    assert len(page_ids) == len(set(page_ids))
