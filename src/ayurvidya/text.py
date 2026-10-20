"""Devanagari text utilities: normalisation, IAST transliteration, akshara counting and
pada (quarter-verse) splitting.

Everything here is deterministic and dependency-free, so it is fast and fully testable.
For other schemes (Harvard-Kyoto, ITRANS, SLP1, Kannada script) use the
`indic_transliteration` package; `to_devanagari()` calls it automatically when installed.
"""
from __future__ import annotations

import re
import unicodedata

# ---------------------------------------------------------------- tables
_VOWELS = {  # IAST -> (independent, matra)
    "a": ("अ", ""), "ā": ("आ", "ा"), "i": ("इ", "ि"), "ī": ("ई", "ी"),
    "u": ("उ", "ु"), "ū": ("ऊ", "ू"), "ṛ": ("ऋ", "ृ"), "ṝ": ("ॠ", "ॄ"),
    "ḷ": ("ऌ", "ॢ"), "ḹ": ("ॡ", "ॣ"), "e": ("ए", "े"), "ai": ("ऐ", "ै"),
    "o": ("ओ", "ो"), "au": ("औ", "ौ"),
}
_CONS = {
    "k": "क", "kh": "ख", "g": "ग", "gh": "घ", "ṅ": "ङ",
    "c": "च", "ch": "छ", "j": "ज", "jh": "झ", "ñ": "ञ",
    "ṭ": "ट", "ṭh": "ठ", "ḍ": "ड", "ḍh": "ढ", "ṇ": "ण",
    "t": "त", "th": "थ", "d": "द", "dh": "ध", "n": "न",
    "p": "प", "ph": "फ", "b": "ब", "bh": "भ", "m": "म",
    "y": "य", "r": "र", "l": "ल", "v": "व",
    "ś": "श", "ṣ": "ष", "s": "स", "h": "ह", "ḻ": "ळ",
}
_OTHER = {"ṃ": "ं", "ṁ": "ं", "ḥ": "ः", "m̐": "ँ", "'": "ऽ", "’": "ऽ"}
_VIRAMA = "्"

_DEV_CONS = {v: k for k, v in _CONS.items()}
_DEV_IND = {v[0]: k for k, v in _VOWELS.items()}
_DEV_MATRA = {v[1]: k for k, v in _VOWELS.items() if v[1]}
_DEV_OTHER = {"ं": "ṃ", "ः": "ḥ", "ँ": "m̐", "ऽ": "'", "।": "|", "॥": "||", "ॐ": "oṃ"}
_DEV_DIGITS = "०१२३४५६७८९"

_IAST_TOKENS = sorted(list(_VOWELS) + list(_CONS) + list(_OTHER), key=len, reverse=True)


# ---------------------------------------------------------------- normalisation
def normalize(text: str) -> str:
    """Canonical Devanagari form used for storage and display."""
    t = unicodedata.normalize("NFC", text)
    t = t.replace("‌", "").replace("‍", "")          # ZWNJ / ZWJ
    t = re.sub(r"\|\|", "॥", t)
    t = t.replace("|", "।")
    t = re.sub(r"[ \t]+", " ", t)
    return "\n".join(line.strip() for line in t.splitlines()).strip()


def strip_verse_markers(text: str) -> str:
    """Remove danda + verse numbers (॥१२॥, ।९।) and brackets: the form used for search/embedding."""
    t = normalize(text)
    t = re.sub(r"[।॥]\s*[०-९0-9]+\s*[।॥]", " ", t)
    t = re.sub(r"[।॥()\[\]{}]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def dev_digits_to_int(s: str) -> int:
    return int("".join(str(_DEV_DIGITS.index(c)) if c in _DEV_DIGITS else c for c in s))


def int_to_dev_digits(n: int | str) -> str:
    return "".join(_DEV_DIGITS[int(c)] if c.isdigit() else c for c in str(n))


def is_devanagari(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and sum("ऀ" <= c <= "ॿ" for c in letters) / len(letters) > 0.5


# ---------------------------------------------------------------- transliteration
def iast_to_devanagari(text: str) -> str:
    text = unicodedata.normalize("NFC", text.lower())
    out: list[str] = []
    i, prev_cons = 0, False
    while i < len(text):
        tok = next((t for t in _IAST_TOKENS if text.startswith(t, i)), None)
        if tok is None:
            if prev_cons:
                out.append(_VIRAMA)
                prev_cons = False
            ch = text[i]
            out.append("॥" if text.startswith("||", i) else "।" if ch == "|" else ch)
            i += 2 if text.startswith("||", i) else 1
            continue
        if tok in _CONS:
            if prev_cons:
                out.append(_VIRAMA)
            out.append(_CONS[tok])
            prev_cons = True
        elif tok in _VOWELS:
            ind, matra = _VOWELS[tok]
            out.append(matra if prev_cons else ind)
            prev_cons = False
        else:  # anusvara, visarga, avagraha
            prev_cons = False
            out.append(_OTHER[tok])
        i += len(tok)
    if prev_cons:
        out.append(_VIRAMA)
    return "".join(out)


def devanagari_to_iast(text: str) -> str:
    text = normalize(text)
    out: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if ch in _DEV_CONS:
            out.append(_DEV_CONS[ch])
            if nxt == _VIRAMA:
                i += 1
            elif nxt in _DEV_MATRA:
                out.append(_DEV_MATRA[nxt])
                i += 1
            else:
                out.append("a")
        elif ch in _DEV_IND:
            out.append(_DEV_IND[ch])
        elif ch in _DEV_OTHER:
            out.append(_DEV_OTHER[ch])
        elif ch in _DEV_DIGITS:
            out.append(str(_DEV_DIGITS.index(ch)))
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def to_devanagari(text: str) -> str:
    """Best-effort conversion of a user query to Devanagari (queries may be typed in IAST/HK/ITRANS)."""
    if is_devanagari(text) or not re.search(r"[a-zA-Zāīūṛṝḷṃḥṅñṭḍṇśṣ]", text):
        return normalize(text)
    if re.search(r"[āīūṛṝḷḹṃḥṅñṭḍṇśṣ]", text):          # diacritics => IAST
        return normalize(iast_to_devanagari(text))
    if not looks_harvard_kyoto(text):                    # plain English question: leave it alone
        return text
    try:                                                 # Sanskrit typed in Harvard-Kyoto, e.g. "vAyuH"
        from indic_transliteration import sanscript
        return normalize(sanscript.transliterate(text, sanscript.HK, sanscript.DEVANAGARI))
    except ImportError:
        return text


_ENGLISH = {"what", "is", "are", "the", "a", "an", "of", "and", "or", "in", "on", "to", "how", "why",
            "which", "who", "does", "do", "for", "with", "by", "from", "this", "that", "meaning", "explain"}


def looks_harvard_kyoto(text: str) -> bool:
    """Plain-ASCII text counts as Harvard-Kyoto Sanskrit only if it has no common English words AND
    uses an HK capital inside a word (vAyu, prANa, zIta) - so 'What is Vata?' stays English."""
    words = re.findall(r"[A-Za-z]+", text)
    if not words or any(w.lower() in _ENGLISH for w in words):
        return False
    return any(re.search(r"[a-z][AIURLMHNTDSG]|^[AIURMHNTDSG]{2}|z", w) for w in words)                                  # leave English questions untouched


def fold_for_search(text: str) -> str:
    """Script-independent, diacritic-free lowercase form (for keyword matching of Sanskrit)."""
    t = devanagari_to_iast(strip_verse_markers(text)) if is_devanagari(text) else text.lower()
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ']+", " ", t).strip()


# ---------------------------------------------------------------- aksharas and padas
_DEV_VOWEL_SIGNS = set(_DEV_MATRA)


def aksharas(word: str) -> list[str]:
    """Split a Devanagari string into syllables (aksharas). Anusvara/visarga/avagraha attach to the
    preceding syllable; a final consonant with virama attaches to the preceding syllable too."""
    sylls: list[str] = []
    cur = ""
    chars = [c for c in normalize(word) if not c.isspace()]
    i = 0
    while i < len(chars):
        c = chars[i]
        if c in _DEV_IND:
            if cur and _has_vowel(cur):
                sylls.append(cur)
                cur = ""
            cur += c
        elif c in _DEV_CONS:
            if cur and _has_vowel(cur):
                sylls.append(cur)
                cur = ""
            cur += c
        else:   # matra, virama, anusvara, visarga, avagraha, nukta
            cur += c
        i += 1
    if cur:
        if sylls and not _has_vowel(cur):
            sylls[-1] += cur          # trailing half-consonant, e.g. the न् of भगवान्
        else:
            sylls.append(cur)
    return sylls


def _has_vowel(s: str) -> bool:
    """True once the cluster carries a vowel (independent, matra or inherent 'a')."""
    if any(c in _DEV_IND for c in s):
        return True
    for j, c in enumerate(s):
        if c in _DEV_CONS:
            nxt = s[j + 1] if j + 1 < len(s) else ""
            if nxt != _VIRAMA:
                return True
    return False


def count_aksharas(text: str) -> int:
    return sum(len(aksharas(w)) for w in strip_verse_markers(text).split())


def split_half_into_padas(half: str) -> tuple[str, str]:
    """Split one half-verse (ardha) into two padas of equal syllable count.

    Splits at the word boundary nearest to the midpoint; if the midpoint falls inside a word
    (sandhi often joins padas), the word is cut at the akshara boundary and marked with '-',
    exactly as in the project's Sampradanam template ("स्वेदासृक्स्रावणश्चापि" style breaks)."""
    words = strip_verse_markers(half).split()
    counts = [len(aksharas(w)) for w in words]
    total = sum(counts)
    target = total // 2
    acc = 0
    for idx, n in enumerate(counts):
        if acc == target:
            return " ".join(words[:idx]), " ".join(words[idx:])
        if acc + n > target:
            sy = aksharas(words[idx])
            cut = target - acc
            left = " ".join(words[:idx] + ["".join(sy[:cut]) + "-"])
            right = " ".join(["".join(sy[cut:])] + words[idx + 1:])
            return left.strip(), right.strip()
        acc += n
    return " ".join(words), ""


def split_padas(shloka: str) -> list[str]:
    """Split a padya shloka into its 4 padas using the half-verse dandas and akshara counts."""
    t = normalize(shloka)
    t = re.sub(r"[॥।]\s*[०-९0-9]+\s*[॥।]", "\n", t)        # verse numbers end a half
    halves = [h.strip() for h in re.split(r"[।॥\n]+", t) if strip_verse_markers(h)]
    padas: list[str] = []
    for h in halves:
        a, b = split_half_into_padas(h)
        padas += [p for p in (a, b) if p]
    return padas


def guess_metre(shloka: str) -> str:
    padas = split_padas(shloka)
    if not padas:
        return "unknown"
    per = sorted(len(aksharas(p.replace("-", ""))) for p in padas)
    mid = per[len(per) // 2]
    return {8: "anushtubh", 11: "trishtubh (e.g. shalini/indravajra)", 12: "jagati"}.get(mid, f"{mid} syllables/pada")
