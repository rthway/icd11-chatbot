"""
Local ICD-11 lookup chatbot.
Rule-based natural-language search over the official WHO ICD-11 MMS
dataset -- no AI/LLM models are used anywhere in this pipeline.
"""
from pathlib import Path

from flask import Flask, jsonify, render_template, request

import build_db
from search import DATA_PATH, ICD11Search, format_answer, format_hierarchy

if not Path(DATA_PATH).exists():
    build_db.main()

app = Flask(__name__)
engine = ICD11Search()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/query", methods=["POST"])
def query():
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    if not message:
        return jsonify({"reply": "Please type a disease name or an ICD-11 code.", "matches": []})

    mode, result = engine.search(message)

    if mode in ("code", "exact"):
        return jsonify({"reply": format_answer(result), "matches": [result]})

    if mode == "fuzzy":
        options = result[:5]
        lines = ["I couldn't find an exact match. Did you mean one of these?"]
        matches = []
        for entry, score in options:
            hierarchy = format_hierarchy(entry)
            lines.append(f"- **{entry['code']}** — {entry['title']}" + (f" ({hierarchy})" if hierarchy else ""))
            matches.append(entry)
        return jsonify({"reply": "\n".join(lines), "matches": matches})

    return jsonify({
        "reply": "No matching ICD-11 entity found. Try rephrasing, e.g. \"icd11 code for asthma\" or a code like \"1A00\".",
        "matches": [],
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
