import os
import json
import logging
from datetime import datetime, timedelta

import anthropic

# --- PATH SETUP ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.join(SCRIPT_DIR, "DailyLanguageLearnings")
SAVE_DIR = os.path.join(BASE_DIR, "Language")
LOG_FILE = os.path.join(BASE_DIR, "daily_language.log")
HISTORY_FILE = os.path.join(BASE_DIR, "daily_language.json")

os.makedirs(SAVE_DIR, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def load_dotenv(path):
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception as exc:
        logging.warning(f"Failed to load .env: {exc}")


# Load local .env for non-interactive runs (e.g., launchd)
load_dotenv(os.path.join(SCRIPT_DIR, ".env"))

# --- CONFIG FROM ENV ---
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")

LANGUAGES = [
    "Spanish",
    "Brazilian Portuguese",
    "Italian",
    "French",
]


def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logging.warning(f"Failed to read history file: {exc}")
        return []


def recent_items(history, days=7):
    cutoff = datetime.now() - timedelta(days=days)
    recent = {}
    for entry in history:
        try:
            entry_date = datetime.fromisoformat(entry.get("date"))
        except Exception:
            continue
        if entry_date < cutoff:
            continue
        langs = entry.get("languages", {})
        for lang, items in langs.items():
            recent.setdefault(lang, {"words": set(), "phrases": set(), "sentences": set()})
            for w in items.get("words", []):
                recent[lang]["words"].add(w.get("term", ""))
            for p in items.get("phrases", []):
                recent[lang]["phrases"].add(p.get("term", ""))
            for s in items.get("sentences", []):
                recent[lang]["sentences"].add(s.get("term", ""))
    # Convert sets to sorted lists for prompt stability
    return {
        lang: {
            "words": sorted(list(vals["words"]))[:30],
            "phrases": sorted(list(vals["phrases"]))[:30],
            "sentences": sorted(list(vals["sentences"]))[:30],
        }
        for lang, vals in recent.items()
    }


def build_prompt(recent):
    recent_lines = []
    for lang in LANGUAGES:
        items = recent.get(lang, {"words": [], "phrases": [], "sentences": []})
        recent_lines.append(f"{lang} recent words: {', '.join(items['words']) or 'None'}")
        recent_lines.append(f"{lang} recent phrases: {', '.join(items['phrases']) or 'None'}")
        recent_lines.append(f"{lang} recent sentences: {', '.join(items['sentences']) or 'None'}")

    return f"""You are a meticulous language tutor.

Generate DAILY study content for: Spanish, Brazilian Portuguese, Italian, French.

Rules:
- For EACH language, provide exactly 3 single words, exactly 3 short phrases, and exactly 3 sentences.
- Words should be common, practical, and not proper nouns.
- Phrases should be natural, everyday use, 2-6 words.
- Sentences should be 6-12 words, natural, and must use at least 2 of the words from the same language's word list.
- Provide English translations for every word, phrase, and sentence.
- Avoid slang, offensive content, or sensitive topics.
- Do NOT repeat any item that appears in the recent lists below.
- Do not repeat items within the same language.
- Return STRICT JSON only (no code fences, no extra text).

JSON schema:
{{
  "languages": {{
    "Spanish": {{"words": [{{"term": "", "en": ""}}], "phrases": [{{"term": "", "en": ""}}], "sentences": [{{"term": "", "en": ""}}]}},
    "Brazilian Portuguese": {{"words": [{{"term": "", "en": ""}}], "phrases": [{{"term": "", "en": ""}}], "sentences": [{{"term": "", "en": ""}}]}},
    "Italian": {{"words": [{{"term": "", "en": ""}}], "phrases": [{{"term": "", "en": ""}}], "sentences": [{{"term": "", "en": ""}}]}},
    "French": {{"words": [{{"term": "", "en": ""}}], "phrases": [{{"term": "", "en": ""}}], "sentences": [{{"term": "", "en": ""}}]}}
  }}
}}

Recent items (avoid these):
""" + "\n".join(recent_lines)


def extract_json(text):
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        return text
    # Attempt to recover JSON if wrapped in fences or extra text
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]
    return None


def generate_language_pack(max_attempts=2):
    if not CLAUDE_API_KEY:
        logging.error("CLAUDE_API_KEY missing!")
        return None

    history = load_history()
    recent = recent_items(history, days=7)

    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    prompt = build_prompt(recent)
    prompt_chars = len(prompt)
    approx_prompt_tokens = max(1, prompt_chars // 4)
    logging.info(f"Approx prompt tokens: {approx_prompt_tokens} (chars: {prompt_chars})")

    for attempt in range(1, max_attempts + 1):
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text.strip()
        response_chars = len(raw)
        approx_response_tokens = max(1, response_chars // 4)
        logging.info(f"Approx response tokens: {approx_response_tokens} (chars: {response_chars})")
        json_text = extract_json(raw)
        if not json_text:
            logging.error("Failed to extract JSON from model output")
            logging.error(raw)
            continue

        try:
            data = json.loads(json_text)
            return data
        except Exception as exc:
            logging.error(f"JSON parse error: {exc}")
            logging.error(json_text)
            # One retry with a stricter prompt
            prompt = (
                "Return ONLY valid JSON that matches the required schema. "
                "Do not include extra text or omit any fields. "
                "Fix the JSON below and return the corrected JSON only:\n\n"
                + json_text
            )

    return None


def validate_pack(data):
    if not isinstance(data, dict):
        return False
    langs = data.get("languages", {})
    if not isinstance(langs, dict):
        return False
    for lang in LANGUAGES:
        block = langs.get(lang)
        if not isinstance(block, dict):
            return False
        words = block.get("words", [])
        phrases = block.get("phrases", [])
        sentences = block.get("sentences", [])
        if len(words) != 3 or len(phrases) != 3 or len(sentences) != 3:
            return False
        for item in words + phrases + sentences:
            if not isinstance(item, dict):
                return False
            if not item.get("term") or not item.get("en"):
                return False
    return True


def save_markdown(data):
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"{date_str}_language_pack.md"
    filepath = os.path.join(SAVE_DIR, filename)

    lines = [f"# Daily Language Pack ({date_str})", ""]
    for lang in LANGUAGES:
        block = data["languages"][lang]
        lines.append(f"## {lang}")
        lines.append("Words:")
        for w in block["words"]:
            lines.append(f"- {w['term']} — {w['en']}")
        lines.append("Phrases:")
        for p in block["phrases"]:
            lines.append(f"- {p['term']} — {p['en']}")
        lines.append("Sentences:")
        for s in block["sentences"]:
            lines.append(f"- {s['term']} — {s['en']}")
        lines.append("")

    content = "\n".join(lines).strip() + "\n"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    logging.info(f"Saved language pack: {filepath}")
    return filepath


def append_history(data):
    entry = {
        "date": datetime.now().isoformat(),
        "languages": data.get("languages", {}),
    }
    history = load_history()
    history.append(entry)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def main():
    print("Daily Language Pack")

    pack = generate_language_pack()
    if not pack:
        print("Failed to generate pack. Check daily_language.log")
        return 1

    if not validate_pack(pack):
        logging.error("Validation failed for language pack")
        print("Invalid pack format. Check daily_language.log")
        return 1

    filepath = save_markdown(pack)
    append_history(pack)

    print(f"Saved: {filepath}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
