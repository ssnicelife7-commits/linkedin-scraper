"""
Headline Generator
Reads a Kanbox CSV export, calls Claude to generate 6 LinkedIn headline alternatives
per prospect, and writes an enriched CSV with assumptions tracked per row.
"""

import csv
import io
import os
import re
import time

import anthropic

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

SYSTEM_PROMPT = """You are an expert LinkedIn copywriter who crafts punchy, credible headlines
for B2B sales outreach personalisation.

Rules:
- Each headline must be ≤ 220 characters.
- Lead with value or outcome, not title.
- No buzzwords: "passionate", "dynamic", "results-driven", "guru", "ninja".
- No first-person ("I help…").
- Use numbers or specifics wherever the data supports it.
- When data is ambiguous or incomplete, make your best inference and document it
  in the ASSUMPTIONS field — do NOT refuse to generate headlines.
- If the prospect's most recent role appears to be a secondary/teaching role rather
  than their primary commercial role, use any other available signals (industry,
  previous roles, headline keywords) to infer the primary role and note the assumption.

Output format — respond with ONLY a JSON object, no markdown fences:
{
  "profile_snapshot": "<2-3 sentence summary of the prospect>",
  "alt_1": "...",
  "alt_2": "...",
  "alt_3": "...",
  "alt_4": "...",
  "alt_5": "...",
  "alt_6": "...",
  "assumptions": "<blank if none | comma-separated list of things inferred due to missing/ambiguous data>"
}"""

USER_TEMPLATE = """Prospect data from Kanbox export:

First name: {firstname}
Last name: {lastname}
Current headline: {current_headline}
Current company: {current_company}
Current title: {current_title}
Location: {location}
LinkedIn URL: {linkedin_url}
Industry: {industry}
Connections: {connections}
Extra notes: {extra_notes}

Generate 6 LinkedIn headline alternatives for outreach personalisation."""


def _kanbox_row_to_prompt(row: dict) -> str:
    def get(*keys):
        for k in keys:
            v = row.get(k, "").strip()
            if v:
                return v
        return "N/A"

    return USER_TEMPLATE.format(
        firstname=get("First Name", "firstname", "Prénom"),
        lastname=get("Last Name", "lastname", "Nom"),
        current_headline=get("Headline", "headline", "Titre"),
        current_company=get("Company", "company", "Entreprise actuelle"),
        current_title=get("Title", "title", "Poste actuel"),
        location=get("Location", "location", "Localisation"),
        linkedin_url=get("LinkedIn URL", "Profile URL", "url"),
        industry=get("Industry", "industry", "Secteur"),
        connections=get("Connections", "connections", "Relations"),
        extra_notes=get("Notes", "notes", ""),
    )


def _parse_claude_json(text: str) -> dict:
    """Extract the JSON object from Claude's reply, tolerating minor wrapping."""
    text = text.strip()
    # Strip accidental markdown fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    import json
    return json.loads(text)


def process_csv(csv_bytes: bytes) -> bytes:
    """
    Accept raw CSV bytes (Kanbox export), return enriched CSV bytes.
    Adds: profile_snapshot, alt_1–6, assumptions columns.
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig")))
    input_rows = list(reader)
    original_fields = reader.fieldnames or []

    extra_fields = ["profile_snapshot", "alt_1", "alt_2", "alt_3", "alt_4", "alt_5", "alt_6", "assumptions"]
    output_fields = list(original_fields) + [f for f in extra_fields if f not in original_fields]

    out_buf = io.StringIO()
    writer = csv.DictWriter(out_buf, fieldnames=output_fields, extrasaction="ignore")
    writer.writeheader()

    for i, row in enumerate(input_rows):
        print(f"  Processing row {i + 1}/{len(input_rows)}: {row.get('First Name', '')} {row.get('Last Name', '')}")
        prompt = _kanbox_row_to_prompt(row)

        try:
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            parsed = _parse_claude_json(message.content[0].text)
            row.update({k: parsed.get(k, "") for k in extra_fields})
        except Exception as exc:
            row.update({k: "" for k in extra_fields})
            row["assumptions"] = f"[ERROR: {exc}]"

        writer.writerow(row)

        # Polite pacing — avoid hammering the API
        if i < len(input_rows) - 1:
            time.sleep(0.5)

    return out_buf.getvalue().encode("utf-8")
