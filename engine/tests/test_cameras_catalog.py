"""Catálogo de câmeras: o arquivo do Worker (TypeScript) é GERADO do cameras.json; nenhuma câmera pode se repetir."""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAMS = json.loads((ROOT / "engine/config/cameras.json").read_text(encoding="utf-8"))["cameras"]
TS = ROOT / "apps/worker/src/data/cameras.ts"


def enabled():
    return [c for c in CAMS if c.get("enabled")]


def test_worker_file_is_generated_from_json():
    before = TS.read_text(encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "engine/scripts/gen_cameras_ts.py")], check=True, capture_output=True)
    assert TS.read_text(encoding="utf-8") == before, "rode `py engine/scripts/gen_cameras_ts.py` e commite o resultado"
    assert {i for i in re.findall(r'id: "([^"]+)"', before)} == {c["id"] for c in enabled()}


def test_no_duplicate_cameras():
    """Mesma câmera nunca entra duas vezes: nem pelo id, nem pelo stream/iframe, nem pela página, nem por provedor + rótulo."""
    ids = [c["id"] for c in CAMS]
    assert len(ids) == len(set(ids))
    streams = [c["embed"]["url"].strip().lower().rstrip("/") for c in CAMS if c.get("embed")]
    assert len(streams) == len(set(streams)), "dois itens apontam para o mesmo stream"
    pages = [c["page_url"].strip().lower().rstrip("/") for c in CAMS if c["id"].startswith(("skyline-", "motiva-", "realdata-")) and not c.get("embed")]
    assert len(pages) == len(set(pages)), "duas câmeras com a mesma página de origem"
    names = [(c["provider"].lower(), c["label"].lower(), c["city"].lower()) for c in CAMS]
    assert len(names) == len(set(names)), "dois itens com o mesmo provedor, rótulo e cidade"


def test_link_rules():
    for c in CAMS:
        assert c["page_url"].startswith("https://")
        assert (c["lat"] is None) == (c["lon"] is None)  # nunca coordenada pela metade nem inventada
        assert re.fullmatch(r"[A-Z]{2}", c["state"])
        if c.get("embed"):
            assert c["embed"]["type"] in ("iframe", "hls") and c["embed"]["url"].startswith("https://")
