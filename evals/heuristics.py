"""Model-free checks: does a returned sentence stand alone in a draft? Do results carry the tags asked for?"""
from __future__ import annotations

import re

_WORD = re.compile(r"[A-Za-z']+")
DANGLING = {"he", "she", "his", "her", "him", "they", "them", "their", "this", "these", "those", "such",
            "its", "then", "thus", "hence", "therefore", "however", "also"}
CAP_OK = {"i", "i'm", "i've", "i'll", "i'd", "god", "lord", "o", "oh", "mr", "mrs", "miss", "sir",
          "christmas", "sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
          "english", "heaven"}
SAY = re.compile(r"\b(said|cried|replied|exclaimed|answered|asked|whispered|shouted)\b", re.I)
ARCHAIC = re.compile(r"\b(thee|thou|thy|thine|hath|doth|art thou|ye)\b", re.I)
CONTRACTION = re.compile(r"^(there|it|that|here|what|let|he|she|who|where)'s\b", re.I)
QUOTES = re.compile(r"[\"“”]")


def flags(text: str, allow_archaic: bool = False) -> list[str]:
    """Reasons a sentence would need editing before it can be dropped into a personal draft."""
    out = []
    t = text.strip()
    opens = t.startswith(('"', "\u201c", "'", "\u2018"))
    closes = t.endswith(('."', '!"', '?"', '".', ".'", "!'", "?'", '")', ".\u201d", "!\u201d", "?\u201d"))
    if (len(QUOTES.findall(t)) % 2 or (closes and not opens)
            or (t[:1] in "'\u2018" and t[-1:] not in "'\u2019")):
        out.append("quote_debris")
    elif opens and t[-1:] in "\"'\u201d\u2019":
        out.append("quoted")  # whole sentence is a quotation: fine to reuse once the marks are dropped
    if t[:1] in "\"“" and t[-1:] in "\"”" and SAY.search(t):
        out.append("dialogue_tag")
    elif SAY.search(t) and QUOTES.search(t):
        out.append("dialogue_tag")
    words = _WORD.findall(t)
    if words and words[0].lower() in DANGLING:
        out.append("dangling_ref")
    if t[:1].islower():
        out.append("fragment_start")
    # Proper names: capitalised words not at the start of a sentence or quotation (rough but cheap).
    body = re.sub(r"^[\"'\u201c\u2018(\s]+", "", t)
    caps = re.findall(r"(?<![.!?;:\"'\u201c\u2018\u2014(-] )(?<![\"'\u201c\u2018\u2014(-])\b[A-Z][a-z]+", body)
    names = [w for w in caps if w.lower() not in CAP_OK]
    if names and body.startswith(names[0]):
        names = names[1:]
    if names or (re.match(r"^[A-Z][a-z]+'s\b", body) and not CONTRACTION.match(body)):
        out.append("proper_name")
    if re.search(r"\d", t):
        out.append("digits")
    if not allow_archaic and ARCHAIC.search(t):
        out.append("archaic")
    if re.search(r"[\[\]{}<>|_=*#]|\s--\s|--$", t):
        out.append("markup")
    return out


def has_tag(result: dict, tag: str) -> bool:
    parts = set((result.get("register") or "").split("+"))
    styles = set(result.get("styles") or [])
    if tag == "intimate":
        return "emotive" in parts and bool(parts & {"first_person", "personal"})
    if tag == "conversational":
        return bool(parts & {"dialogue", "first_person", "personal"})
    return tag in parts or tag in styles


def expected_tags(q: dict) -> list[str]:
    tags = []
    if q.get("register"):
        tags.append(q["register"])
    if q.get("style"):
        tags += [s.strip() for s in q["style"].split(",") if s.strip()]
    return tags


def norm_tokens(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text)}


def near_dup_rate(texts: list[str], threshold: float = 0.8) -> float:
    """Share of results that are near duplicates (token Jaccard >= threshold) of an earlier result."""
    seen: list[set[str]] = []
    dups = 0
    for t in texts:
        s = norm_tokens(t)
        if any(len(s & o) / max(1, len(s | o)) >= threshold for o in seen):
            dups += 1
        seen.append(s)
    return dups / len(texts) if texts else 0.0
