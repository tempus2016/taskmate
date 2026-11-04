"""pt-BR must read as Brazilian Portuguese, not European Portuguese (#771).

Much of pt-BR started as a copy of pt (Portugal), so it said "Guardar",
"A guardar...", "Tens alterações não guardadas", "ecrã", "bónus", "gerir",
"Toca no ícone" and "Conseguiste!" where a Brazilian user expects "Salvar",
"Salvando...", "Você tem alterações não salvas", "tela", "bônus",
"gerenciar", "Toque no ícone" and "Você conseguiu!". This test bans the
common European markers in both pt-BR files. pt.json is Portugal's and is
left alone.

"Guardar" itself is not banned: Brazilians also guardar (put away) toys and
guardar (save up) points; only the "save data" sense moved to "Salvar".
"""

from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate"
FILES = [ROOT / "www" / "locales" / "pt-BR.json", ROOT / "translations" / "pt-BR.json"]

# European Portuguese words and constructions, with the Brazilian form wanted.
MARKERS = {
    r"\b(?:[tT]u|[tT]ens|[tT]eu|[tT]ua|[tT]eus|[tT]uas|contigo)\b": "você / seu / sua",
    r"\b\w+-te\b": "te + verb (or você)",
    r"\b(?:[cC]onseguiste|[fF]izeste|[gG]anhaste|[tT]erminaste|[cC]ompletaste|[cC]oncluíste|[eE]scolheste)\b": "você + 3rd-person past (você conseguiu)",
    r"\b[bB][óÓ]nus\b": "bônus",
    r"\b[eE]crãs?\b": "tela",
    r"\btelemóve(?:l|is)\b": "celular",
    r"\b[uU]tilizador(?:es|as?)?\b": "usuário",
    r"\b[fF]icheiros?\b": "arquivo",
    r"\b[rR]egistos?\b": "registro",
    r"\b[eE]quipas?\b": "equipe",
    r"\b[gG]erir\b": "gerenciar",
    r"\bcontrolos?\b": "controle",
    r"\b[dD]efinições\b": "configurações",
    r"\b[pP]enalizaç(?:ão|ões)\b": "penalidade",
    r"\b[eE]limin(?:ar|e|a)\b": "excluir",
    r"\bA (?:guardar|carregar|enviar|processar|verificar|gerar|criar|atualizar|preparar)\b": "gerund (Salvando…, Carregando…)",
    r"\bPor favor (?:define|introduz)\b": "Defina / Digite",
    r"\bGuardar (?:alterações|ordem)\b": "Salvar alterações / Salvar ordem",
    r"\b(?:Toca|Clica|Introduz|Arrasta)\b": "Toque / Clique / Digite / Arraste",
    r"\bVista (?:unificada|de um dia)\b": "Visão",
}

# Words that match a marker but are fine Brazilian Portuguese, by the exact
# word matched (lower-case). Keep this short and say why for each entry.
ALLOWED_WORDS: set[str] = set()

# Whole strings allowed to contain a marker, by "file:key", with the reason.
ALLOWED_KEYS: dict[str, str] = {}


def _flat(obj, prefix=""):
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield from _flat(value, f"{prefix}.{key}" if prefix else key)
    elif isinstance(obj, str):
        yield prefix, obj


def test_pt_br_has_no_european_portuguese_markers():
    offenders = []
    for path in FILES:
        for key, value in _flat(json.loads(path.read_text(encoding="utf-8"))):
            if f"{path.name}:{key}" in ALLOWED_KEYS:
                continue
            for pattern, want in MARKERS.items():
                for match in re.finditer(pattern, value):
                    if match.group(0).lower() in ALLOWED_WORDS:
                        continue
                    offenders.append(f"{path.parent.name}/{path.name} {key}: {match.group(0)!r} (use {want})")
    assert offenders == [], "European Portuguese in pt-BR:\n  " + "\n  ".join(offenders)


def test_markers_do_catch_the_old_wording():
    """Guard the patterns themselves against silently matching nothing."""
    samples = [
        "Tens alterações não guardadas",
        "A guardar...",
        "Bónus guardado",
        "Ecrã motivacional",
        "Gerir bónus",
        "Toca no ícone do lápis",
        "Conseguiste! Continua assim!",
        "Por favor define uma entidade",
        "Eliminar recompensa",
        "Aplicar penalização",
    ]
    for text in samples:
        assert any(re.search(p, text) for p in MARKERS), text
