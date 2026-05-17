"""
LinkedIn Headline Generator — Flask web app
Upload a Kanbox CSV → get back an enriched CSV with 6 headline alternatives per prospect.
"""

import os
import uuid
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, send_file, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret-change-me")

UPLOAD_DIR = Path(__file__).parent / "output"
UPLOAD_DIR.mkdir(exist_ok=True)


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/process", methods=["POST"])
def process():
    if "csv_file" not in request.files:
        flash("No file selected.")
        return redirect(url_for("index"))

    f = request.files["csv_file"]
    if not f.filename:
        flash("No file selected.")
        return redirect(url_for("index"))

    if not f.filename.lower().endswith(".csv"):
        flash("Please upload a .csv file.")
        return redirect(url_for("index"))

    if not os.environ.get("ANTHROPIC_API_KEY"):
        flash("ANTHROPIC_API_KEY environment variable is not set.")
        return redirect(url_for("index"))

    csv_bytes = f.read()

    from src.headline_generator import process_csv
    try:
        result_bytes = process_csv(csv_bytes)
    except Exception as exc:
        flash(f"Processing failed: {exc}")
        return redirect(url_for("index"))

    out_name = f"headlines_{uuid.uuid4().hex[:8]}.csv"
    out_path = UPLOAD_DIR / out_name
    out_path.write_bytes(result_bytes)

    return send_file(
        out_path,
        mimetype="text/csv",
        as_attachment=True,
        download_name=out_name,
    )


if __name__ == "__main__":
    app.run(debug=True)
