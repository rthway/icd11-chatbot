"""
Parses the official WHO ICD-11 MMS linearization export (tab-delimited
"Mini Output" from icd.who.int) into a clean JSON dataset of diagnosable
codes with their title and full chapter/block hierarchy.

No AI/LLM involved -- this is plain text parsing.
"""
import csv
import json
import re
import urllib.request
import zipfile
from pathlib import Path

WHO_ZIP_URL = "https://icd.who.int/dev11/Downloads/Download?fileName=LinearizationMiniOutput-MMS-en.zip"
RAW_DIR = Path(__file__).parent / "data" / "raw"
SRC = RAW_DIR / "LinearizationMiniOutput-MMS-en.txt"
OUT = Path(__file__).parent / "data" / "icd11_codes.json"


def ensure_source_file():
    if SRC.exists():
        return
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = RAW_DIR / "LinearizationMiniOutput-MMS-en.zip"
    print(f"Downloading official WHO ICD-11 MMS export from {WHO_ZIP_URL} ...")
    req = urllib.request.Request(WHO_ZIP_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp, open(zip_path, "wb") as f:
        f.write(resp.read())
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(RAW_DIR)
    zip_path.unlink()
    print(f"Downloaded and extracted to {RAW_DIR}")


def clean_title(raw):
    # Titles are indented with "- " per depth level, e.g. '- - - Cholera'
    t = raw.strip()
    if t.startswith('"') and t.endswith('"'):
        t = t[1:-1]
    t = re.sub(r"^(-\s*)+", "", t).strip()
    return t


def clean_browser_link(formula):
    m = re.search(r'https://[^"]+', formula)
    return m.group(0) if m else ""


def main():
    ensure_source_file()
    with open(SRC, encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter="\t", quotechar='"')
        header = next(reader)
        rows = list(reader)

    idx = {name: i for i, name in enumerate(header)}

    # First pass: collect block titles (BlockId -> clean title) and chapter titles (ChapterNo -> clean title)
    block_titles = {}
    chapter_titles = {}
    for row in rows:
        if len(row) <= idx["Title"]:
            continue
        title = clean_title(row[idx["Title"]])
        block_id = row[idx["BlockId"]].strip()
        class_kind = row[idx["ClassKind"]].strip()
        chapter_no = row[idx["ChapterNo"]].strip()
        if block_id:
            block_titles[block_id] = title
        if class_kind == "chapter" and chapter_no:
            chapter_titles[chapter_no] = title

    grouping_cols = ["Grouping1", "Grouping2", "Grouping3", "Grouping4", "Grouping5"]

    entries = []
    for row in rows:
        if len(row) <= idx["Code"]:
            continue
        code = row[idx["Code"]].strip()
        if not code:
            continue  # skip chapters/blocks themselves, keep only coded entities

        title = clean_title(row[idx["Title"]])
        class_kind = row[idx["ClassKind"]].strip()
        chapter_no = row[idx["ChapterNo"]].strip()
        is_leaf = row[idx["isLeaf"]].strip() == "True"
        browser_link = clean_browser_link(row[idx["BrowserLink"]])

        path = []
        for col in grouping_cols:
            val = row[idx[col]].strip() if idx[col] < len(row) else ""
            if val and val in block_titles:
                path.append(block_titles[val])

        entries.append({
            "code": code,
            "title": title,
            "class_kind": class_kind,
            "chapter": chapter_titles.get(chapter_no, ""),
            "path": path,  # ordered list of ancestor block titles, most general first
            "is_leaf": is_leaf,
            "browser_link": browser_link,
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False)

    print(f"Parsed {len(entries)} coded ICD-11 entities -> {OUT}")


if __name__ == "__main__":
    main()
