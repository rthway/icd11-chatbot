# ICD-11 Code Finder

A chatbot that maps natural-language questions ("what is the icd11 code for cholera")
to official ICD-11 diagnosis codes.

**No AI/LLM model is used anywhere in this pipeline.** Matching is done with plain
rule-based text processing — regex phrase-stripping, exact/word-boundary/substring
matching, and classic fuzzy string matching ([rapidfuzz](https://github.com/rapidfuzz/RapidFuzz))
— over the official WHO ICD-11 dataset.

## How it works

1. **Data**: `build_db.py` downloads the official WHO ICD-11 MMS ("Mortality and
   Morbidity Statistics") linearization export directly from `icd.who.int`
   (no account/API key required) and parses it into `data/icd11_codes.json` — a
   flat list of ~35,000 coded entities, each with its code, title, and full
   chapter/block classification hierarchy.
2. **Search** (`search.py`): a query goes through, in order:
   - a regex check for a bare code token (e.g. `1A00`) → direct lookup
   - filler-phrase stripping (removes "what is the icd11 code for", "diagnosis
     code for", etc.) to isolate the disease term
   - exact title match → whole-word match → substring match → fuzzy match
     (rapidfuzz `WRatio`)
   - ambiguous queries return a short "did you mean" list instead of guessing
3. **App** (`app.py`): a small Flask server exposing the chat UI and a JSON API.

## Limitations

The free WHO bulk export includes codes, titles, and classification hierarchy,
but **not** the long-form clinical definitions, inclusion/exclusion terms, or
coding notes — those live behind WHO's authenticated ICD-11 API (free, but
requires registering a client ID/secret at https://icd.who.int/icdapi) or the
interactive browser. Instead of inventing definition text, responses include
the code's full hierarchy (chapter → block → category) and a direct link to
the official WHO browser entry.

## Project layout

```
build_db.py           # downloads + parses the WHO dataset into data/icd11_codes.json
search.py              # the offline search engine
app.py                 # Flask app (web UI + /api/query)
templates/index.html   # chat UI
requirements.txt
Dockerfile
```

## Running locally

Requires Python 3.10+.

```bash
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000. The first run of `python app.py` (or `python
build_db.py`) automatically downloads and parses the WHO dataset into
`data/` if it isn't already present — this needs internet access once.

## Running with Docker

```bash
docker build -t icd11-chatbot .
docker run -p 5000:5000 icd11-chatbot
```

The image fetches and builds the WHO dataset at **build time**, so
`docker build` needs internet access; `docker run` does not. Open
http://localhost:5000.

## API

`POST /api/query`

Request:
```json
{ "message": "what is the icd11 code for cholera" }
```

Response:
```json
{
  "reply": "In the ICD-11 classification, \"Cholera\" is assigned the code **1A00**. ...",
  "matches": [ { "code": "1A00", "title": "Cholera", "chapter": "...", "path": ["...", "..."], "is_leaf": true, "browser_link": "https://..." } ]
}
```

`matches` is a list because ambiguous queries return multiple candidates
instead of a single guess.

## Regenerating the dataset

The WHO source data is not committed to this repository (see `.gitignore`) —
it's fetched fresh by `build_db.py`. To force a re-download (e.g. after a new
ICD-11 release), delete `data/` and re-run:

```bash
python build_db.py
```

## Data source & attribution

Data is sourced directly from the World Health Organization's ICD-11 for
Mortality and Morbidity Statistics (MMS) linearization, published at
https://icd.who.int. ICD-11 is © World Health Organization. Review WHO's
terms of use at https://icd.who.int/en if you plan to redistribute or use
this data beyond personal/internal lookup purposes.
