# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Skill Extractor is a CLI tool that reads markdown learning materials and produces a structured skill map (JSON). It uses Groq's LLM to extract topics and identify relationships between them (prerequisite, related, subtopic).

## Commands

### Run the extractor
```bash
python skill_extractor.py samples/input.md
```
This produces `<input>_skillmap.json` and prints a tree view to stdout.

### Install dependencies
```bash
pip install -r requirements.txt
```
Requires: `groq>=0.11.0`, `pydantic>=2.0`

### Set up API key
Create a `.env` file in the project root:
```
GROQ_API_KEY=your_key_here
```

### Run tests
```bash
python -m pytest test_skill_extractor.py
# or
python test_skill_extractor.py
```

## Architecture

The pipeline (in `skill_extractor.py`):

1. **split_sections()**: Splits markdown on H1/H2 headings for chunked LLM processing
2. **extract_topics()**: Uses Groq tool-use to extract topics from each section (Pydantic `Topic` model)
3. **deduplicate_topics()**: Merges duplicate topics by normalized name
4. **find_relationships()**: Uses Groq tool-use to identify relationships between topics (Pydantic `Relationship` model)
5. **validate()**: Checks for dangling refs, self-loops, and cycles in prerequisite chains
6. **retry loop**: If validation fails, feeds errors back into the LLM prompt (max 3 attempts)

### Pydantic Models

All LLM outputs are validated through Pydantic models:
- `Topic`: id (slug pattern), name, description, difficulty (enum: beginner/intermediate/advanced)
- `Relationship`: from_id, to_id, type (enum: prerequisite/related/subtopic)
- `SkillMap`: container for topics + relationships

### LLM Tool-Use Pattern

Both `extract_topics()` and `find_relationships()` use the same pattern:
1. Define a JSON Schema tool
2. Set `tool_choice` to force the model to call it
3. Parse `tool_calls[0].function.arguments` as JSON
4. Validate through Pydantic, skip invalid entries with warnings

### Cycle Detection

The `validate()` function uses a three-color DFS algorithm (WHITE/GRAY/BLACK) to detect cycles in the prerequisite subgraph only — cycles in `related` or `subtopic` edges are allowed.

## Output Format

JSON output contains:
```json
{
  "topics": [{"id": "...", "name": "...", "description": "...", "difficulty": "..."}],
  "relationships": [{"from_id": "...", "to_id": "...", "type": "..."}]
}
```

The tree view printed to stdout shows prerequisite chains hierarchically, then summarizes subtopic and related relationships.
