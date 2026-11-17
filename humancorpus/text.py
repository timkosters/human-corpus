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


# --------------------------------------------------------------------------- #
# Style tags: multi-label, lexicon and pattern based. Each was spot-checked on samples of the
# published corpus and kept only if most tagged sentences fit. Stored as a bitmask.
# --------------------------------------------------------------------------- #
STYLES = ["grateful", "apologetic", "grieving", "celebratory", "sensory", "reflective", "advice",
          "casual", "aphorism", "archaic", "question", "exclamation"]
STYLE_BIT = {name: 1 << i for i, name in enumerate(STYLES)}

_GRATEFUL = set("thank thanks thankful grateful gratitude gratefully appreciate indebted".split())
_APOLOGY = re.compile(r"\b(i am sorry|i'm sorry|i was sorry|forgive me|pardon me|i apologi[sz]e|my apologies|"
                      r"i beg your pardon|i regret|my fault|i was wrong)\b", re.I)
_GRIEF = set("sorrow grief grieve grieving mourn mourning comfort comforted condolence condolences "
             "sympathy bereaved bereavement heal healing".split())
_GRIEF_PAT = re.compile(r"\b(you are not alone|in our thoughts|in my thoughts|deepest sympathy|sorry for your loss|"
                        r"rest in peace|time heals|(your|our|his|her|their|my) (sad |great |terrible )?loss|be comforted|take comfort|my heart goes out|thinking of you)\b", re.I)
_CELEB = set("congratulate congratulations congratulation congratulated celebrate celebration rejoice hurrah "
             "hooray huzzah toast bravo".split())
_CELEB_PAT = re.compile(r"\b(here's to|let us drink|raise (a|our|your) glass|well done|happy birthday|"
                        r"many happy returns)\b", re.I)
_ARCHAIC = set("thee thou thy thine hath doth thyself 'tis 'twas wherefore hither thither shalt wilt canst "
               "dost thou'rt".split())
_SIGHT = set("""red blue green yellow golden gold silver white black grey gray crimson scarlet purple violet amber
pale dark bright light shadow shadows glow glowed gleam gleamed shimmer shimmering glitter sparkle sparkled shining
shone dim dusk dawn twilight""".split())
_SENSE = set("""smell smelled scent scented fragrance fragrant perfume odor odour aroma stench sweet bitter sour salty
taste tasted sound sounds sounded hum hummed whisper whispered rustle rustled roar roared murmur murmured echo echoed
silence silent loud crackle creak creaked soft rough smooth warm cold cool damp wet dry silky velvet icy hot chill
chilly breeze wind rain mist fog snow sun sunlight moonlight""".split())
_REFLECT = set("remember remembered recall think thought wonder wondered realize realized realise realised believe "
               "believed suppose imagine imagined understand understood know knew learned learnt reflect "
               "reflected".split())
_ABSTRACT = set("life lives time years memory memories past youth age death world meaning".split())
_IMPER = set("""don't let take give make go come try remember be keep stop look listen think consider imagine write
tell ask use put place add mix stir cut hold turn open close find choose avoid follow note see read start begin
leave bring help""".split())
_CONTRACTION = re.compile(r"\b\w+n't\b|\b(i'm|you're|we're|they're|i've|you've|we've|i'll|you'll|we'll|i'd|you'd|"
                          r"it's|that's|there's|what's|let's|he's|she's)\b", re.I)
_APH_START = re.compile(r"(he who|she who|those who|whoever|no man|every man|a man |men |love |life |nothing |"
                        r"truth |a friend|friends |happiness|wisdom|the man who|the heart|a good |a wise |"
                        r"there is no|there is nothing)", re.I)
_APH_VERB = re.compile(r"\b(is|are|never|always|cannot|can't|must|makes|has|have|lies)\b", re.I)
_PAST = re.compile(r"\b(was|were|had|did)\b", re.I)
_PRON = _FIRST | _SECOND | _THIRD


def style_mask(s: str) -> int:
    """Bitmask over STYLES."""
    words = [w.lower() for w in _WORD.findall(s)]
    ws = set(words)
    low = s.lower()
    end = s.rstrip("\"'”’)")
    m = 0
    if (ws & _GRATEFUL and ws & (_FIRST | _SECOND) and "thanks to" not in low) or "thank you" in low:
        m |= STYLE_BIT["grateful"]
    if _APOLOGY.search(s):
        m |= STYLE_BIT["apologetic"]
    if _GRIEF_PAT.search(s) or (ws & _GRIEF and ws & _SECOND and ws & _FIRST):
        m |= STYLE_BIT["grieving"]
    if _CELEB_PAT.search(s) or (ws & _CELEB and ws & (_FIRST | _SECOND)):
        m |= STYLE_BIT["celebratory"]
    if sum(w in _SIGHT or w in _SENSE for w in words) >= 3 and ws & _SIGHT and ws & _SENSE:
        m |= STYLE_BIT["sensory"]
    if ws & _FIRST and ws & _REFLECT and ws & _ABSTRACT:
        m |= STYLE_BIT["reflective"]
    first, second = (words + ["", ""])[:2]
    if (first in _IMPER and not end.endswith("?") and second not in _PRON) or \
            re.search(r"\byou (should|must|ought to|need to)\b", s, re.I):
        m |= STYLE_BIT["advice"]
    if _CONTRACTION.search(s) and len(words) <= 20 and ws & (_FIRST | _SECOND):
        m |= STYLE_BIT["casual"]
    body = s.lstrip("\"'“‘")
    if len(words) <= 18 and _APH_START.match(body) and _APH_VERB.search(s) and not _PAST.search(s) \
            and not re.search(r"[A-Z]", body[1:]):
        m |= STYLE_BIT["aphorism"]
    if ws & _ARCHAIC:
        m |= STYLE_BIT["archaic"]
    if end.endswith("?"):
        m |= STYLE_BIT["question"]
    if end.endswith("!"):
        m |= STYLE_BIT["exclamation"]
    return m


def style_names(mask: int) -> list[str]:
    return [n for n in STYLES if mask & STYLE_BIT[n]]


# --------------------------------------------------------------------------- #
# Display cleanup: quotation debris left by sentence splitting. The cleaned text is always
# verbatim inside the stored sentence, so verify_draft still finds it ("contained").
# --------------------------------------------------------------------------- #
_DQ = '"“”'
_OPEN = '"“‘\''
_CLOSE = '"”’\''


def clean_quotes(s: str) -> str:
    """Drop unbalanced or wrapping quote marks at the ends of a sentence: `And I miss you."` -> `And I miss you.`"""
    t = s.strip()
    for _ in range(3):
        before = t
        n_dq = sum(t.count(c) for c in _DQ)
        # A whole sentence in quotes: "I hope you forgive me." -> I hope you forgive me.
        if len(t) > 2 and t[0] in _OPEN and t[-1] in _CLOSE and n_dq in (0, 2) and \
                not any(c in t[1:-1] for c in _DQ):
            t = t[1:-1].strip()
        elif n_dq % 2:
            if t[-1] in _DQ:
                t = t[:-1].rstrip()
            elif len(t) > 1 and t[-2] in _DQ and t[-1] in ".!?)":
                t = t[:-2] + t[-1]
            elif t[0] in _DQ:
                t = t[1:].lstrip()
        elif t[-1:] in "'’" and t[-2:-1] in ".!?," and t[:1] not in "'‘":
            t = t[:-1]
        elif t[:1] in "'‘" and t[-1:] not in "'’":
            t = t[1:].lstrip()
        if t == before:
            break
    if t.endswith(")") and "(" not in t:
        t = t[:-1]
    return t or s
