"""PULSO Engine. Desacoplado da infraestrutura: fala com o resto só pelos contratos de models.py."""

# Transporte seguro contra SSRF para TODO o Engine (coletores e cliente do Worker). Ver safe_http.py.
from . import safe_http as _safe_http

_safe_http.install()
