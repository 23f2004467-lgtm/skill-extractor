# Skill Extractor

A small Flask web app I built to extract structured skill maps from learning material. Takes markdown (paste, file, or pre-loaded modules), runs it through an LLM with structured output, validates the result, and shows you a graph of topic relationships.

## Quick Start

```bash
# Install deps
pip install -r requirements.txt

# Set up API key (pick one: OpenRouter, Gemini, or Groq)
echo "OPENROUTER_API_KEY=your_key" > .env

# Run CLI
python skill_extractor.py samples/input.md

# Run web UI
python app.py
# Open http://localhost:5001
```

## How It Works

1. Split markdown into sections on H1/H2 headings
2. Extract topics from each section using LLM tool-calling (Pydantic-validated)
3. Deduplicate topics by normalized name
4. Find relationships between topics (prerequisite/related/subtopic)
5. Validate: no dangling refs, no self-loops, no cycles in prerequisite chains
6. Retry step 4 with feedback if validation fails (max 3 attempts)

## Output

- JSON: `<input>_skillmap.json` with topics + relationships
- Web UI: interactive graph (vis-network) + topic cards
- CLI: tree view of prerequisite chains

## API Providers

Priority: OpenRouter > Gemini > Groq. Set the corresponding env var to choose.
