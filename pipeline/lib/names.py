"""Name and position normalisation helpers."""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable, Optional

# Common romanisations of Korean surnames (Revised Romanization + McCune–Reischauer + customary
# spellings). Used only as a soft consistency check when a faculty page gives no English name.
SURNAME_ROMANIZATIONS: dict[str, set[str]] = {
    "김": {"kim", "gim"}, "이": {"lee", "yi", "rhee", "rhie", "ri", "i", "lie"},
    "박": {"park", "pak", "bak", "bahk"}, "최": {"choi", "choe", "chey"},
    "정": {"jung", "jeong", "chung", "joung", "cheong", "jeung"}, "강": {"kang", "gang"},
    "조": {"cho", "jo", "joe", "chough"}, "윤": {"yoon", "yun", "youn"},
    "장": {"jang", "chang"}, "임": {"lim", "im", "yim", "rim"}, "한": {"han"},
    "오": {"oh", "o"}, "서": {"seo", "suh", "so", "sur"}, "신": {"shin", "sin", "shinn"},
    "권": {"kwon", "gwon", "kwun"}, "황": {"hwang", "whang"}, "안": {"ahn", "an"},
    "송": {"song"}, "전": {"jeon", "jun", "chun", "chon", "jon"}, "홍": {"hong"},
    "유": {"yoo", "yu", "ryu", "you", "lyu", "rhyu"}, "류": {"ryu", "yoo", "yu", "lyu", "rhyu"},
    "고": {"ko", "go", "koh"}, "문": {"moon", "mun"}, "양": {"yang"}, "손": {"son", "sohn"},
    "배": {"bae", "pae"}, "백": {"baek", "paik", "back", "baik", "paek", "beak"},
    "허": {"heo", "huh", "hur", "her"}, "남": {"nam"}, "심": {"shim", "sim"},
    "노": {"noh", "roh", "no", "ro"}, "하": {"ha"}, "곽": {"kwak", "gwak"},
    "성": {"sung", "seong"}, "차": {"cha"}, "주": {"joo", "ju", "chu", "choo"},
    "우": {"woo", "u", "wu"}, "구": {"koo", "ku", "gu", "goo"}, "민": {"min"},
    "진": {"jin", "chin"}, "지": {"ji", "chi"}, "엄": {"eom", "um", "uhm", "om"},
    "채": {"chae", "chai"}, "원": {"won", "weon"}, "천": {"cheon", "chun", "chon"},
    "방": {"bang", "pang"}, "공": {"kong", "gong"}, "현": {"hyun", "hyeon"},
    "함": {"ham", "hahm"}, "변": {"byun", "byeon", "pyun"}, "염": {"yeom", "yum", "youm"},
    "여": {"yeo", "yuh", "yo"}, "추": {"choo", "chu"}, "도": {"do", "doh", "to"},
    "소": {"so", "soh"}, "석": {"seok", "suk", "sok"}, "선": {"sun", "seon"},
    "설": {"seol", "sul", "sol"}, "마": {"ma"}, "길": {"gil", "kil"}, "연": {"yeon", "yun", "youn"},
    "위": {"wi", "wee"}, "표": {"pyo"}, "명": {"myung", "myeong"}, "기": {"ki", "gi", "kee"},
    "반": {"ban", "pan"}, "라": {"ra", "la", "na"}, "왕": {"wang"}, "금": {"keum", "kum", "geum"},
    "옥": {"ok"}, "육": {"yook", "yuk"}, "인": {"in"}, "맹": {"maeng"}, "제": {"je", "jae"},
    "모": {"mo"}, "탁": {"tak"}, "국": {"kook", "kuk", "guk"}, "어": {"eo", "uh"},
    "은": {"eun"}, "편": {"pyun", "pyeon"}, "용": {"yong"}, "예": {"yea", "ye", "yae"},
    "경": {"kyung", "gyeong"}, "봉": {"bong"}, "사": {"sa"}, "부": {"boo", "bu"},
    "황보": {"hwangbo"}, "남궁": {"namkoong", "namgung"}, "선우": {"sunwoo", "seonu"},
    "제갈": {"jegal"}, "독고": {"dokko"},
}

_TITLE_NOISE = re.compile(
    r"\((?:[^)]*?(?:chair|head|학과장|전공책임|책임교수|department|major)[^)]*?)\)|"
    r"(?:학과장|전공책임교수)", re.I)


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def clean_display_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    name = _TITLE_NOISE.sub("", name)
    name = re.sub(r"\s+", " ", name).strip(" ,/")
    return name or None


def name_tokens(name: str) -> list[str]:
    """Lower-case alphabetic tokens; hyphenated given names are joined ("Jin-Woo" -> "jinwoo")."""
    s = strip_accents(name).lower()
    s = re.sub(r"(?<=[a-z])-(?=[a-z])", "", s)
    s = re.sub(r"[^a-z\s]", " ", s)
    return [t for t in s.split() if t]


def name_key_variants(name: str) -> set[str]:
    """Order-insensitive keys: tokens sorted, and given-name pieces merged.

    "Jin Woo Kim", "Kim, Jin-Woo", "KIM Jinwoo" -> {"jinwoo kim", ...}
    """
    toks = name_tokens(name)
    keys: set[str] = set()
    if not toks:
        return keys
    keys.add(" ".join(sorted(toks)))
    # merge everything except one token (= surname) into a single given-name token
    for i, sur in enumerate(toks):
        rest = "".join(t for j, t in enumerate(toks) if j != i)
        if rest:
            keys.add(" ".join(sorted([sur, rest])))
    return keys


def drop_middle_initials(name: str) -> str:
    """'June M. Kwak' -> 'June Kwak'; 'Seung-Jae V. Lee' -> 'Seung-Jae Lee'."""
    return re.sub(r"\s+[A-Za-z]\.(?=\s)", "", name)


def _initials_compatible(a: str, b: str) -> bool:
    """'June M. Kwak' ~ 'June Myoung Kwak'; 'Alexander Bae' ~ 'J. Alexander Bae'.

    Full tokens must match exactly; single-letter initials may match a full token's first letter
    or be absent from the other name. At least two full tokens must match.
    """
    ta, tb = name_tokens(a), name_tokens(b)
    fa, fb = [t for t in ta if len(t) > 1], [t for t in tb if len(t) > 1]
    common = set(fa) & set(fb)
    if len(common) < 2:
        return False
    ra = [t for t in fa if t not in common]
    rb = [t for t in fb if t not in common]
    ia = [t for t in ta if len(t) == 1]
    ib = [t for t in tb if len(t) == 1]
    # every remaining full token must be explained by an initial on the other side
    return (all(any(t[0] == i for i in ib) for t in ra)
            and all(any(t[0] == i for i in ia) for t in rb))


def names_compatible(a: str, b: str) -> bool:
    if not a or not b:
        return False
    ka = name_key_variants(drop_middle_initials(a)) | name_key_variants(a)
    kb = name_key_variants(drop_middle_initials(b)) | name_key_variants(b)
    return bool(ka & kb) or _initials_compatible(a, b)


def search_variants(name_en: str) -> list[str]:
    """Query strings for OpenAlex author search (deduplicated, max 3)."""
    base = clean_display_name(name_en) or ""
    out: list[str] = []
    for v in (
        base.replace(",", " "),
        drop_middle_initials(base.replace(",", " ")),
        re.sub(r"-", " ", drop_middle_initials(base.replace(",", " "))),
    ):
        v = re.sub(r"\s+", " ", v).strip()
        if v and v not in out:
            out.append(v)
    # "KIM Young-Joon" -> "Young-Joon KIM"
    toks = base.replace(",", " ").split()
    if len(toks) >= 2 and toks[0].isupper() and len(toks[0]) > 1:
        flipped = " ".join(toks[1:] + toks[:1])
        if flipped not in out:
            out.append(flipped)
    return out[:3]


def korean_surname(name_ko: str) -> Optional[str]:
    name_ko = re.sub(r"\(.*?\)", "", name_ko).strip()
    if not re.fullmatch(r"[가-힣]{2,5}", name_ko):
        return None
    if len(name_ko) >= 4 and name_ko[:2] in SURNAME_ROMANIZATIONS:
        return name_ko[:2]
    return name_ko[0]


def surname_compatible(name_ko: Optional[str], display_name: str) -> Optional[bool]:
    """True/False if we can judge, None if the Korean name is not a standard Hangul name."""
    if not name_ko:
        return None
    sur = korean_surname(name_ko)
    if not sur or sur not in SURNAME_ROMANIZATIONS:
        return None
    toks = set(name_tokens(display_name))
    return bool(toks & SURNAME_ROMANIZATIONS[sur])


# ---------------------------------------------------------------- given names
# Hangul syllable = initial + medial (+ final). Each jamo maps to the spellings seen in practice
# (Revised Romanization, McCune–Reischauer, customary), so "승우" accepts seungwoo / sungwoo / seung-u.
_INITIALS = [["g", "k"], ["kk", "gg", "k"], ["n"], ["d", "t"], ["tt", "dd", "t"], ["r", "l", "n", ""],
             ["m"], ["b", "p"], ["pp", "bb", "p"], ["s", "sh"], ["ss", "s"], [""], ["j", "ch", "z", "ts"],
             ["jj", "j", "ch"], ["ch", "c"], ["k"], ["t"], ["p"], ["h"]]
_MEDIALS = [["a"], ["ae", "e", "ai"], ["ya"], ["yae", "ye"], ["eo", "u", "o", "e"], ["e"],
            ["yeo", "you", "yu", "yo", "ye"], ["ye"], ["o", "oh"], ["wa"], ["wae", "we"], ["oe", "oi", "we", "wi"],
            ["yo"], ["u", "oo", "woo", "wu"], ["wo", "weo", "w"], ["we"], ["wi", "wee", "ui"], ["yu", "yoo", "you"],
            ["eu", "u", "e"], ["ui", "eui", "ee", "i"], ["i", "ee", "y", "ie"]]
_FINALS = [[""], ["k", "g"], ["k", "g"], ["k", "g"], ["n"], ["n"], ["n"], ["t", "d"], ["l", "r"],
           ["k", "l"], ["m", "l"], ["l", "p"], ["l"], ["l"], ["p", "l"], ["l"], ["m"], ["p", "b"], ["p", "b"],
           ["t", "s"], ["t", "s"], ["ng", "n"], ["t", "j"], ["t", "ch"], ["k"], ["t"], ["p"], ["t", "h"]]


def _syllable_pattern(ch: str) -> Optional[str]:
    code = ord(ch) - 0xAC00
    if not 0 <= code < 11172:
        return None
    ini, med, fin = code // 588, (code % 588) // 28, code % 28
    alts = {i + m + f for i in _INITIALS[ini] for m in _MEDIALS[med] for f in _FINALS[fin]}
    if ini == 11:  # silent ㅇ: "우" may be written "woo"/"wu", "여" as "yeo"
        alts |= {"w" + a for a in alts if a.startswith(("u", "o"))}
    if ini == 18:  # "환" written "whan"
        alts |= {"wh" + a[2:] for a in alts if a.startswith("hw")}
    return "(?:" + "|".join(sorted(map(re.escape, alts), key=len, reverse=True)) + ")"


def given_name_compatible(name_ko: Optional[str], display_name: str) -> Optional[bool]:
    """Does the given name in `display_name` romanise the Korean given name? None if not judgeable
    (non-standard Korean name, or only initials in the display name)."""
    if not name_ko:
        return None
    ko = re.sub(r"\(.*?\)", "", name_ko).strip()
    sur = korean_surname(ko)
    if not sur or sur not in SURNAME_ROMANIZATIONS:
        return None
    pats = [_syllable_pattern(c) for c in ko[len(sur):]]
    if not pats or any(p is None for p in pats):
        return None
    toks = name_tokens(re.sub(r"\b[A-Za-z]\.", " ", display_name))  # drop initials like "S."
    rest = [t for t in toks if t not in SURNAME_ROMANIZATIONS[sur]]
    if len(rest) == len(toks) and len(toks) > 1:  # surname not present: try either end as surname
        rest = toks[1:]
    given = "".join(rest)
    if len(given) < 2:
        return None
    return re.fullmatch("".join(pats), given) is not None


# ---------------------------------------------------------------- positions
_POS_PATTERNS = [
    (re.compile(r"assistant\s+prof|조교수", re.I), "조교수"),
    (re.compile(r"associate\s+prof|부교수", re.I), "부교수"),
    (re.compile(r"emerit|명예", re.I), None),
    (re.compile(r"adjunct|겸임|겸무|겸직|visiting|초빙|research\s+prof|연구교수|강의교수|lecture", re.I), None),
    (re.compile(r"\bprof|교수", re.I), "교수"),
]


def normalize_position(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    for pat, val in _POS_PATTERNS:
        if pat.search(raw):
            return val
    return None


def first_nonempty(values: Iterable[Optional[str]]) -> Optional[str]:
    for v in values:
        if v:
            return v
    return None
