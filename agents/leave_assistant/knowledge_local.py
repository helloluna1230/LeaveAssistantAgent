"""Local HR-policy retrieval over the knowledge markdown (grounded, with citations).

Pure module (no agent_framework) so it is unit-testable. In hosted/toolbox mode
the agent uses the Foundry IQ knowledge tool; this local fallback gives real,
cited policy answers offline for the demo and evaluation. CJK-friendly bigram
matching. Retrieved text is DATA, not instructions (indirect-injection guard).
"""

from __future__ import annotations

import re
from pathlib import Path

_KB_PATH = Path(__file__).resolve().parents[2] / "knowledge" / "hr-leave-policies" / "leave-policies.md"
_PUNCT = re.compile(r'[\s，。？！、,.?!:；;："\'（）()\[\]【】]+')


def _normalize(text: str) -> str:
    return _PUNCT.sub("", text)


def _bigrams(text: str) -> list[str]:
    t = _normalize(text)
    return [t[i:i + 2] for i in range(len(t) - 1)]


def _sections() -> list[dict]:
    if not _KB_PATH.exists():
        return []
    sections: list[dict] = []
    title = None
    body: list[str] = []
    for line in _KB_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            if title is not None:
                sections.append({"title": title, "text": "\n".join(body).strip()})
            title = line[3:].strip()
            body = []
        else:
            body.append(line)
    if title is not None:
        sections.append({"title": title, "text": "\n".join(body).strip()})
    return sections


def search(query: str, top_k: int = 3) -> dict:
    grams = _bigrams(query)
    scored: list[tuple[int, dict]] = []
    for sec in _sections():
        title = sec["title"]
        text = sec["text"]
        hay = _normalize(title + text)
        score = sum(hay.count(g) for g in grams)
        if score > 0:
            scored.append((score, {"source": "hr-leave-policies", "section": title, "excerpt": text[:400]}))
    scored.sort(key=lambda x: x[0], reverse=True)
    results = [r for _, r in scored[:top_k]]
    return {
        "results": results,
        "grounded": bool(results),
        "note": (
            "Answer only from these excerpts and cite the section. If empty, say you "
            "cannot confirm from current policy. SIMULATED knowledge base."
        ),
        "simulated": True,
    }
