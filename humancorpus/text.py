"""Sentence splitting, cleaning and normalisation. Stdlib only."""
from __future__ import annotations

import hashlib
import re
import unicodedata

# Abbreviations that end with a period but rarely end a sentence.
_ABBREV = {
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "mt", "ft", "vs", "etc",
    "e.g", "i.e", "cf", "al", "approx", "inc", "ltd", "co", "corp", "no", "vol",
    "fig", "gen", "gov", "lt", "col", "capt", "sgt", "rev", "hon", "jan", "feb",
    "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec", "u.s",
    "u.k", "a.m", "p.m", "b.c", "a.d", "ca", "c", "op", "ed", "eds", "pp", "ch",
}

_SENT_END = re.compile(r'([.!?]["”’\')\]]*)\s+(?=["“‘(\[]?[A-Z0-9])')
_WS = re.compile(r"\s+")
_WORD = re.compile(r"[A-Za-zÀ-ɏ']+")
_BAD = re.compile(r"(https?://|www\.|\{\{|\}\}|\[\[|\]\]|==|\|)")


def split_sentences(paragraph: str) -> list[str]:
    """Split a paragraph into sentences with a conservative regex splitter."""
    paragraph = _WS.sub(" ", paragraph).strip()
    if not paragraph:
        return []
    out: list[str] = []
    start = 0
    for m in _SENT_END.finditer(paragraph):
        end = m.end(1)
        chunk = paragraph[start:end]
        last = chunk.rstrip('.!?"”’\')]').split(" ")[-1].lower()
        # Skip splits after abbreviations and single initials ("J. R. R.").
        if last.rstrip(".") in _ABBREV or (len(last) == 1 and last.isalpha()):
            continue
        out.append(chunk.strip())
        start = m.end()
    tail = paragraph[start:].strip()
    if tail:
        out.append(tail)
    return out


def word_count(s: str) -> int:
    return len(_WORD.findall(s))


def is_good_fragment(s: str, min_words: int = 4, max_words: int = 80) -> bool:
    """Reject headings, list debris, markup leftovers and junk."""
    n = word_count(s)
    if n < min_words or n > max_words:
        return False
    if _BAD.search(s):
        return False
    if s.rstrip('"”’\')]')[-1:] not in (".", "!", "?"):
        return False  # headings, captions, list items, discography lines
    letters = sum(ch.isalpha() for ch in s)
    if letters / max(len(s), 1) < 0.6:
        return False  # tables, numbers, citations
    if s.isupper():
        return False
    return True


def normalize(s: str) -> str:
    """Canonical form used for exact-match verification."""
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("’", "'").replace("‘", "'")
    s = s.replace("“", '"').replace("”", '"')
    s = s.replace("—", "-").replace("–", "-")
    s = _WS.sub(" ", s).strip().lower()
    return s


def fingerprint(s: str) -> str:
    return hashlib.blake2b(normalize(s).encode(), digest_size=10).hexdigest()


def clauses(sentence: str, min_words: int = 3) -> list[str]:
    """Break a sentence into phrase-sized pieces on clause punctuation."""
    parts = re.split(r"(?<=[,;:])\s+|\s+[—–-]{1,2}\s+|\s+\(|\)\s*", sentence)
    return [p.strip(" ,;:") for p in parts if p and word_count(p) >= min_words]


def is_reusable(s: str, max_caps: float = 0.15) -> bool:
    """General-purpose prose: few proper nouns, no digits. Drops "In 1987, Smith joined..." lines."""
    if any(ch.isdigit() for ch in s):
        return False
    words = s.split()
    if len(words) < 6 or len(words) > 45:
        return False
    caps = sum(1 for w in words[1:] if w.lstrip('"\'(\u201c\u2018')[:1].isupper() and w.lower() != "i")
    return caps / len(words) <= max_caps


# --------------------------------------------------------------------------- #
# Register (style) tags, used to find sentences that *sound* right, not just match a topic.
# --------------------------------------------------------------------------- #
REGISTERS = ["expository", "narrative", "dialogue", "first_person", "personal"]
EMOTIVE_BIT = 8  # added to the register code when the sentence carries feeling words

_FIRST = {"i", "me", "my", "mine", "myself", "we", "us", "our", "ours", "ourselves"}
_SECOND = {"you", "your", "yours", "yourself", "yourselves", "thee", "thou", "thy", "thine", "ye"}
_THIRD = {"he", "she", "him", "her", "his", "hers", "himself", "herself", "they", "them", "their"}
_EMOTIVE = set("""
love loved loves loving lover lovers beloved dear dearest darling sweet sweetheart heart hearts tender
tenderly tenderness kiss kissed kisses embrace embraced longing long longed yearn yearned yearning miss
missed missing adore adored adoring cherish cherished devotion devoted passion passionate desire desired
joy joyful happy happiness glad delight delighted bliss grateful gratitude thankful hope hoped hopes
hopeful sorrow sorrowful grief grieve grieved mourn mourned tears tear weep wept cry cried lonely
loneliness alone afraid fear feared fears ache ached aching pain hurt hurts sad sadness regret regretted
sorry forgive forgave forgiven forgiveness promise promised forever always soul souls warm warmth gentle
gently smile smiled smiles laugh laughed laughter dream dreamed dreams dreamt feel felt feeling feelings
wish wished wishes proud pride ashamed shame lost comfort comforted precious treasure faithful true
""".split())


def register_code(s: str) -> int:
    """0..4 = index into REGISTERS, plus EMOTIVE_BIT when the sentence uses feeling words."""
    words = [w.lower().strip("'") for w in _WORD.findall(s)]
    ws = set(words)
    if ws & _SECOND:
        code = 4  # personal: speaks to someone
    elif ws & _FIRST:
        code = 3
    elif any(q in s for q in ('"', "“", "”")):
        code = 2
    elif ws & _THIRD:
        code = 1
    else:
        code = 0
    if ws & _EMOTIVE:
        code |= EMOTIVE_BIT
    return code


def register_name(code: int) -> str:
    name = REGISTERS[code & 7]
    return name + ("+emotive" if code & EMOTIVE_BIT else "")
