"""
Offline ICD-11 lookup engine. No AI/LLM calls -- pure rule-based text
processing: regex phrase-stripping, exact/substring matching, and
fuzzy string matching (rapidfuzz) over the official WHO ICD-11 dataset.
"""
import json
import re
from pathlib import Path

from rapidfuzz import fuzz, process

DATA_PATH = Path(__file__).parent / "data" / "icd11_codes.json"

# Longest/most specific phrases first so they get stripped before their
# shorter substrings would otherwise match.
FILLER_PATTERNS = [
    r"what is the icd[\s-]?11 code for",
    r"what is the icd[\s-]?11 code of",
    r"what's the icd[\s-]?11 code for",
    r"what's the icd[\s-]?11 code of",
    r"what is the icd[\s-]?11 diagnosis code for",
    r"icd[\s-]?11 diagnosis code for",
    r"icd[\s-]?11 diagnosis code of",
    r"icd[\s-]?11 code for",
    r"icd[\s-]?11 code of",
    r"icd[\s-]?11 for",
    r"icd[\s-]?11 of",
    r"diagnosis code for",
    r"diagnosis code of",
    r"find the code for",
    r"look ?up the code for",
    r"look ?up",
    r"what is the code for",
    r"what is the code of",
    r"the code for",
    r"the code of",
    r"code for",
    r"code of",
    r"what is",
    r"what's",
    r"tell me about",
    r"tell me",
    r"give me",
    r"search for",
    r"find",
    r"icd[\s-]?11",
    r"icd11",
]

CODE_TOKEN_RE = re.compile(r"^[0-9a-z]{2,4}(\.[0-9a-z]{1,4})?$")


def _normalize(text):
    text = text.lower().strip()
    text = re.sub(r"[?!.]+$", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _clean_title_for_match(title):
    t = title.lower()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


class ICD11Search:
    def __init__(self, data_path=DATA_PATH):
        with open(data_path, encoding="utf-8") as f:
            self.entries = json.load(f)

        self.by_code = {}
        for e in self.entries:
            self.by_code[e["code"].upper()] = e

        self.norm_titles = [_clean_title_for_match(e["title"]) for e in self.entries]

        self.by_norm_title = {}
        for i, nt in enumerate(self.norm_titles):
            self.by_norm_title.setdefault(nt, []).append(i)

    def _find_code_token(self, query):
        for tok in re.findall(r"[a-z0-9]+(?:\.[a-z0-9]+)?", query.lower()):
            if CODE_TOKEN_RE.match(tok) and any(c.isdigit() for c in tok):
                code = tok.upper()
                if code in self.by_code:
                    return self.by_code[code]
        return None

    def _strip_fillers(self, query):
        q = query.lower()
        for pat in FILLER_PATTERNS:
            q = re.sub(pat, " ", q, flags=re.IGNORECASE)
        q = re.sub(r"\s+", " ", q).strip(" ?!.")
        return q

    def search(self, raw_query, limit=5):
        """Returns (mode, result) where mode is one of:
        'code' -> single entry matched directly by code token
        'exact' -> single entry, exact title match
        'fuzzy' -> list of (entry, score) candidates
        'none'  -> nothing usable found
        """
        query = _normalize(raw_query)
        if not query:
            return "none", None

        code_hit = self._find_code_token(query)
        if code_hit:
            return "code", code_hit

        phrase = self._strip_fillers(query)
        if not phrase:
            return "none", None

        norm_phrase = _clean_title_for_match(phrase)

        if norm_phrase in self.by_norm_title:
            idxs = self.by_norm_title[norm_phrase]
            if len(idxs) == 1:
                return "exact", self.entries[idxs[0]]
            return "fuzzy", [(self.entries[i], 100.0) for i in idxs[:limit]]

        word_pattern = re.compile(r"\b" + re.escape(norm_phrase) + r"\b")
        word_hits = [i for i, nt in enumerate(self.norm_titles) if word_pattern.search(nt)]
        if word_hits:
            word_hits.sort(key=lambda i: len(self.norm_titles[i]))
            if len(word_hits) == 1:
                return "exact", self.entries[word_hits[0]]
            return "fuzzy", [(self.entries[i], 96.0) for i in word_hits[:limit]]

        substring_hits = [
            i for i, nt in enumerate(self.norm_titles)
            if norm_phrase in nt or nt in norm_phrase
        ]
        if substring_hits:
            substring_hits.sort(key=lambda i: len(self.norm_titles[i]))
            if len(substring_hits) == 1:
                return "exact", self.entries[substring_hits[0]]
            return "fuzzy", [(self.entries[i], 95.0) for i in substring_hits[:limit]]

        results = process.extract(
            norm_phrase, self.norm_titles, scorer=fuzz.WRatio, limit=limit
        )
        if not results:
            return "none", None

        candidates = [(self.entries[idx], score) for (_, score, idx) in results]
        top_score = candidates[0][1]

        if top_score < 60:
            return "none", None
        if top_score >= 90 and (len(candidates) == 1 or candidates[0][1] - candidates[1][1] >= 8):
            return "exact", candidates[0][0]
        return "fuzzy", candidates


def format_hierarchy(entry):
    parts = [p for p in entry.get("path", []) if p]
    if parts:
        return " > ".join(parts)
    return entry.get("chapter", "")


def format_answer(entry):
    hierarchy = format_hierarchy(entry)
    chapter = entry.get("chapter", "")
    lines = [
        f'In the ICD-11 classification, "{entry["title"]}" is assigned the code **{entry["code"]}**.'
    ]
    if hierarchy:
        lines.append(f"It is categorized under: {chapter} → {hierarchy}.")
    elif chapter:
        lines.append(f"It is categorized under the chapter: {chapter}.")
    if entry.get("browser_link"):
        lines.append(f"Full WHO entry: {entry['browser_link']}")
    return "\n".join(lines)
