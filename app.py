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

from flask import Flask, jsonify, render_template, request

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


def get_sample_files() -> list[str]:
    """Return list of available preset sample names from samples/*.md"""
    samples_dir = Path(__file__).parent / "samples"
    if not samples_dir.exists():
        return []
    return [f.stem for f in samples_dir.glob("*.md")]


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
    # Define styles for each relationship type
    styles = [
        "    classDef prereqStyle stroke:#0f0,stroke-width:2px;",
        "    classDef relatedStyle stroke:#00f,stroke-width:2px,stroke-dasharray: 5 5;",
        "    classDef subtopicStyle stroke:#f00,stroke-width:2px,stroke-dasharray: 10 5;",
    ]
    edge_classes = []

    for r in relationships:
        if r.type == "prerequisite":
            lines.append(f"  {r.from_id}[{r.from_id}] --> {r.to_id}[{r.to_id}]")
            edge_classes.extend([r.from_id, r.to_id])
        elif r.type == "related":
            lines.append(f"  {r.from_id}[{r.from_id}] -.-> {r.to_id}[{r.to_id}]")
            edge_classes.extend([r.from_id, r.to_id])
        elif r.type == "subtopic":
            lines.append(f"  {r.from_id}[{r.from_id}] ==> {r.to_id}[{r.to_id}]")
            edge_classes.extend([r.from_id, r.to_id])

    # Apply styles to all nodes that have edges
    if edge_classes:
        lines.extend(styles)
        unique_nodes = list(set(edge_classes))
        prereq_nodes = [r.from_id for r in relationships if r.type == "prerequisite"] + \
                       [r.to_id for r in relationships if r.type == "prerequisite"]
        related_nodes = [r.from_id for r in relationships if r.type == "related"] + \
                        [r.to_id for r in relationships if r.type == "related"]
        subtopic_nodes = [r.from_id for r in relationships if r.type == "subtopic"] + \
                         [r.to_id for r in relationships if r.type == "subtopic"]

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
    """Return list of available preset names from samples/*.md"""
    return {"samples": get_sample_files()}


@app.route("/process", methods=["POST"])
def process() -> dict:
    """Process markdown and return skill map with Mermaid diagrams.

    Accepts JSON body with either:
        - {"markdown": "..."} - raw markdown content
        - {"sample": "<name>"} - name of preset from samples/<name>.md

    Returns JSON with:
        - topics: list of topic dicts
        - relationships: list of relationship dicts
        - mermaid_prereq: Mermaid graph string (prerequisite edges only)
        - mermaid_full: Mermaid graph string (all edges, colored by type)
        - errors: list of validation error messages (empty if valid)
        - source_id: SHA-256 hash of input for idempotency
    """
    from groq import Groq

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    # Get markdown content from either direct input or sample file
    markdown: Optional[str] = data.get("markdown")
    sample_name: Optional[str] = data.get("sample")

    if markdown is not None:
        text = markdown
    elif sample_name is not None:
        sample_path = Path(__file__).parent / "samples" / f"{sample_name}.md"
        if not sample_path.exists():
            return jsonify({"error": f"Sample '{sample_name}' not found"}), 404
        text = sample_path.read_text(encoding="utf-8")
    else:
        return jsonify({"error": "Must provide either 'markdown' or 'sample'"}), 400

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
    })


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)
