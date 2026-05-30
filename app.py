"""
app.py

Flask web UI for the skill extractor pipeline.
Wraps the existing skill_extractor.py without modifying it.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template, request
from markdownify import markdownify as md

# Import from the existing pipeline (don't modify skill_extractor.py)
import skill_extractor

# Initialize Flask app
app = Flask(__name__)

# Constants from skill_extractor
GROQ_API_KEY = skill_extractor.GROQ_API_KEY
MODEL = skill_extractor.MODEL
MAX_RETRIES = skill_extractor.MAX_RETRIES
Topic = skill_extractor.Topic
Relationship = skill_extractor.Relationship
SkillMap = skill_extractor.SkillMap

# Import pipeline functions
split_sections = skill_extractor.split_sections
extract_topics = skill_extractor.extract_topics
deduplicate_topics = skill_extractor.deduplicate_topics
find_relationships = skill_extractor.find_relationships
validate = skill_extractor.validate

# Fetching configuration
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
CONTENT_SELECTORS = ["article", ".text", ".content", "main", ".article-content"]
TAGS_TO_STRIP = ["nav", "footer", "script", "style", "noscript", "iframe", "aside"]


def get_sample_files() -> list[str]:
    """Return list of available preset sample names from samples/*.md (sorted)."""
    samples_dir = Path(__file__).parent / "samples"
    if not samples_dir.exists():
        return []
    return sorted([f.stem for f in samples_dir.glob("*.md")])


def fetch_url_to_markdown(url: str) -> Optional[str]:
    """Fetch a URL and convert to markdown, or None if it fails."""
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        resp.raise_for_status()
        html = resp.text

        soup = BeautifulSoup(html, "html.parser")

        # Strip out unwanted tags
        for tag in TAGS_TO_STRIP:
            for element in soup.find_all(tag):
                element.decompose()

        # Try each selector
        article_html = None
        for selector in CONTENT_SELECTORS:
            element = soup.select_one(selector)
            if element:
                article_html = str(element)
                break

        # Fallback to body
        if article_html is None:
            body = soup.find("body")
            if body:
                article_html = str(body)
            else:
                return None

        markdown = md(article_html, heading_style="ATX")
        if len(markdown.strip()) < 50:
            return None

        return markdown
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
        return None


def generate_mermaid_prereq(relationships: list[Relationship]) -> str:
    """Generate Mermaid graph with only prerequisite edges."""
    lines = ["graph LR"]
    for r in relationships:
        if r.type == "prerequisite":
            lines.append(f"  {r.from_id}[{r.from_id}] --> {r.to_id}[{r.to_id}]")
    return "\n".join(lines)


def generate_mermaid_full(relationships: list[Relationship]) -> str:
    """Generate Mermaid graph with all edges, colored by type."""
    lines = ["graph TD"]

    # Define styles
    styles = [
        "    classDef prereqStyle stroke:#ff9800,stroke-width:2px;",
        "    classDef relatedStyle stroke:#2196f3,stroke-width:2px,stroke-dasharray: 5 5;",
        "    classDef subtopicStyle stroke:#4caf50,stroke-width:2px,stroke-dasharray: 10 5;",
    ]

    prereq_nodes = []
    related_nodes = []
    subtopic_nodes = []

    for r in relationships:
        if r.type == "prerequisite":
            lines.append(f"  {r.from_id}[{r.from_id}] --> {r.to_id}[{r.to_id}]")
            prereq_nodes.extend([r.from_id, r.to_id])
        elif r.type == "related":
            lines.append(f"  {r.from_id}[{r.from_id}] --- {r.to_id}[{r.to_id}]")
            related_nodes.extend([r.from_id, r.to_id])
        elif r.type == "subtopic":
            lines.append(f"  {r.from_id}[{r.from_id}] -.- {r.to_id}[{r.to_id}]")
            subtopic_nodes.extend([r.from_id, r.to_id])

    # Apply styles
    if prereq_nodes or related_nodes or subtopic_nodes:
        lines.extend(styles)
        if prereq_nodes:
            lines.append(f"    class {' '.join(set(prereq_nodes))} prereqStyle;")
        if related_nodes:
            lines.append(f"    class {' '.join(set(related_nodes))} relatedStyle;")
        if subtopic_nodes:
            lines.append(f"    class {' '.join(set(subtopic_nodes))} subtopicStyle;")

    return "\n".join(lines)


def compute_source_id(markdown: str) -> str:
    """Compute SHA-256 hash of input for idempotency tracking."""
    return hashlib.sha256(markdown.encode("utf-8")).hexdigest()[:16]


def serialize_topics(topics: list[Topic]) -> list[dict]:
    """Convert Topic objects to dicts for JSON response."""
    return [t.model_dump() for t in topics]


def serialize_relationships(relationships: list[Relationship]) -> list[dict]:
    """Convert Relationship objects to dicts for JSON response."""
    return [r.model_dump() for r in relationships]


@app.route("/")
def index() -> str:
    """Serve the index page."""
    return render_template("index.html")


@app.route("/samples", methods=["GET"])
def list_samples() -> dict[str, list[str]]:
    """Return list of available preset names from samples/*.md (sorted)."""
    return {"samples": get_sample_files()}


@app.route("/process", methods=["POST"])
def process() -> dict:
    """Process markdown and return skill map with Mermaid diagrams.

    Accepts JSON body with ONE of:
        - {"markdown": "..."} - raw markdown content
        - {"sample_name": "..."} - name of preset from samples/<name>.md
        - {"url": "..."} - URL to fetch and convert to markdown

    Returns JSON with:
        - topics: list of topic dicts
        - relationships: list of relationship dicts
        - mermaid_prereq: Mermaid graph string (prerequisite edges only)
        - mermaid_full: Mermaid graph string (all edges, colored by type)
        - errors: list of validation error messages (empty if valid)
        - source_id: SHA-256 hash of input for idempotency
        - input_length: length of input markdown
    """
    from groq import Groq

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    # Get markdown content from one of the sources
    markdown: Optional[str] = data.get("markdown")
    sample_name: Optional[str] = data.get("sample_name")
    url: Optional[str] = data.get("url")

    if markdown is not None:
        text = markdown
    elif sample_name is not None:
        sample_path = Path(__file__).parent / "samples" / f"{sample_name}.md"
        if not sample_path.exists():
            return jsonify({"error": f"Sample '{sample_name}' not found"}), 404
        text = sample_path.read_text(encoding="utf-8")
    elif url is not None:
        text = fetch_url_to_markdown(url)
        if text is None:
            return jsonify({"error": f"Failed to fetch content from {url}"}), 400
    else:
        return jsonify({"error": "Must provide one of: markdown, sample_name, or url"}), 400

    input_length = len(text)

    # Compute source ID for idempotency
    source_id = compute_source_id(text)

    # Initialize Groq client
    client = Groq(api_key=GROQ_API_KEY)

    # 1. Split into sections
    sections = split_sections(text)

    # 2. Extract topics from each section
    all_topics: list[Topic] = []
    for section in sections:
        topics = extract_topics(section, client)
        all_topics.extend(topics)

    # 3. Deduplicate
    topics = deduplicate_topics(all_topics)

    # 4. Find relationships with retry loop
    relationships: list[Relationship] = []
    feedback = ""
    errors: list[str] = []

    for attempt in range(MAX_RETRIES):
        relationships = find_relationships(topics, client, feedback)
        errors = validate(topics, relationships)
        if not errors:
            break
        feedback = (
            "Your previous response had validation errors:\n"
            + "\n".join(f"  - {e}" for e in errors)
            + "\n\nPlease fix these and try again."
        )

    # 5. Generate Mermaid diagrams
    mermaid_prereq = generate_mermaid_prereq(relationships)
    mermaid_full = generate_mermaid_full(relationships)

    return jsonify({
        "topics": serialize_topics(topics),
        "relationships": serialize_relationships(relationships),
        "mermaid_prereq": mermaid_prereq,
        "mermaid_full": mermaid_full,
        "errors": errors,
        "source_id": source_id,
        "input_length": input_length,
    })


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)
