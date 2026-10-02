import json

from pulso_engine.processing.keyword_engine import KeywordEngine


def test_classifies_ignoring_case_and_accents():
    kw = KeywordEngine()
    assert kw.classify("ARRASTÃO na avenida, com disparos") == "SECURITY"
    assert kw.classify("Acidente com colisão fecha a via") == "TRAFFIC"
    assert kw.classify("Dia tranquilo no centro") is None


def test_whole_word_match_only():
    kw = KeywordEngine()
    assert kw.classify("o ator principal chegou") is None  # 'ato' não casa dentro de 'ator'


def test_hot_reload_without_redeploy(tmp_path):
    f = tmp_path / "kw.json"
    f.write_text(json.dumps({"TRAFFIC": ["acidente"]}), encoding="utf-8")
    kw = KeywordEngine(f)
    assert kw.classify("pane no metrô") is None
    f.write_text(json.dumps({"TRAFFIC": ["acidente", "pane"]}), encoding="utf-8")
    import os
    os.utime(f, (f.stat().st_atime + 5, f.stat().st_mtime + 5))
    assert kw.classify("pane no metrô") == "TRAFFIC"
