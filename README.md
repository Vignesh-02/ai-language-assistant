# AI Language Assistant

Generates a daily language pack with 3 new words, 3 phrases, and 3 sentences in Spanish, Brazilian Portuguese, Italian, and French. Output is saved as a markdown file and a JSON history to avoid repeats.

## Setup

1. Create a `.env` file with:

```
CLAUDE_API_KEY=your_key_here
# Optional override
# CLAUDE_MODEL=claude-haiku-4-5-20251001
```

2. Install dependencies:

```
python3 -m pip install --user -r requirements.txt
```

## Run

```
python3 daily_language.py
```

## Output

- `DailyLanguageLearnings/Language/YYYY-MM-DD_language_pack.md`
- `DailyLanguageLearnings/daily_language.json` (history)
- `DailyLanguageLearnings/daily_language.log`
