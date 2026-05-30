"""
skill_extractor.py

Reads a markdown file and produces a structured skill map:
  - a list of topics (with id, name, description, difficulty)
  - a list of typed relationships between topics
    (prerequisite, related, or subtopic)

Pipeline:
  1. Read the markdown file from disk
  2. Split it into sections on H1/H2 headings
  3. For each section, ask the LLM (Groq) to extract topics
  4. Deduplicate topics across sections by normalized name
  5. Ask the LLM to identify relationships between the deduped topics
  6. Validate the relationships (no dangling refs, no self-loops, no cycles)
  7. If validation fails, retry the relationship call with the error
     fed back into the prompt. Up to 3 attempts.
  8. Write the final skill map as JSON. Print a tree view to stdout.

Usage:
    python skill_extractor.py samples/input.md
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Literal

from groq import Groq
from pydantic import BaseModel, Field, ValidationError

# Load .env manually (no python-dotenv dep; keep deps small)
def load_env():
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())

load_env()

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
MODEL = "llama-3.3-70b-versatile"
MAX_RETRIES = 3


# ─── Pydantic models — the contract for everything below ────────────────

class Topic(BaseModel):
    id: str = Field(..., pattern=r"^[a-z0-9-]+$")
    name: str
    description: str
    difficulty: Literal["beginner", "intermediate", "advanced"]


class Relationship(BaseModel):
    from_id: str
    to_id: str
    type: Literal["prerequisite", "related", "subtopic"]


class SkillMap(BaseModel):
    topics: list[Topic]
    relationships: list[Relationship]


# ─── Pipeline functions — we'll fill these in one at a time ─────────────

def split_sections(text: str) -> list[str]:
    """Split a markdown string into sections on H1/H2 headings.

    Returns a list of section strings. If the document has no headings,
    returns a single-element list with the whole text.
    """
    # Find every line that starts with # or ## (H1 or H2).
    # The (?=^#{1,2} ) is a lookahead — it matches the position right
    # before a heading line, so we split *at* the boundary but the
    # heading stays attached to its section.
    pattern = re.compile(r"(?=^#{1,2} )", re.MULTILINE)
    parts = pattern.split(text)

    # Strip whitespace and drop empty parts.
    sections = [p.strip() for p in parts if p.strip()]

    # If the markdown had no headings, sections will be empty.
    # In that case, return the whole text as a single section.
    if not sections:
        return [text.strip()]

    return sections    


def extract_topics(section: str, client: Groq) -> list[Topic]:
    """Ask Groq to extract topics from a single section.

    Uses tool-use to force a schema-conformant response. Returns a list of
    Topic objects. Raises ValueError if the response can't be parsed into
    valid Topics after Pydantic validation.
    """
        # Define the tool the model must call. This is a JSON Schema description
    # of what topics look like. The model can't respond with anything else.
    tool_definition = {
        "type": "function",
        "function": {
            "name": "record_topics",
            "description": "Record the technical topics found in this section of learning material.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topics": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {
                                    "type": "string",
                                    "description": "A short slug: lowercase letters, digits, hyphens only.",
                                    "pattern": "^[a-z0-9-]+$",
                                },
                                "name": {"type": "string"},
                                "description": {"type": "string"},
                                "difficulty": {
                                    "type": "string",
                                    "enum": ["beginner", "intermediate", "advanced"],
                                },
                            },
                            "required": ["id", "name", "description", "difficulty"],
                        },
                    },
                },
                "required": ["topics"],
            },
        },
    }

    # System prompt sets the assistant's role and the rules.
    system_prompt = (
        "You extract technical topics from learning material. "
        "For each topic, provide: a short slug-style id (lowercase letters, "
        "numbers, hyphens only — no spaces), a short human-readable name, "
        "a one-sentence description, and a difficulty level. "
        "Only extract topics that are actually present in the text. "
        "Do not invent topics that aren't there."
    )

    # User prompt is the content we want extraction from.
    user_prompt = f"Extract topics from this section:\n\n{section}"

    # Make the call. tool_choice forces the model to call our tool.
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        tools=[tool_definition],
        tool_choice={"type": "function", "function": {"name": "record_topics"}},
        temperature=0,
    )

    # The model's response is in choices[0].message. If it called the tool,
    # tool_calls will be a non-empty list. Otherwise, treat as failure.
    message = response.choices[0].message
    if not message.tool_calls:
        raise ValueError("LLM did not call the record_topics tool")

    # The tool arguments come back as a JSON-encoded string. Parse them.
    tool_call = message.tool_calls[0]
    try:
        args = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}")

    # Validate each raw topic dict through our Pydantic Topic model.
    # If a topic fails validation (wrong shape, bad id, missing field),
    # skip it with a warning rather than crashing the whole pipeline.
    topics: list[Topic] = []
    for raw_topic in args.get("topics", []):
        try:
            topic = Topic(**raw_topic)
            topics.append(topic)
        except ValidationError as e:
            print(f"  ⚠ skipping invalid topic {raw_topic.get('name', '?')}: {e}")

    return topics


def deduplicate_topics(topics: list[Topic]) -> list[Topic]:
    """Remove duplicate topics across sections, keying by lowercased name.

    Keeps the first occurrence. Returns a new list, doesn't mutate input.
    """
    seen: set[str] = set()
    unique: list[Topic] = []
    for topic in topics:
        # Normalize the name — strip whitespace and lowercase.
        # Same conceptual topic with slightly different spelling
        # ("Variables" vs "  variables  ") collapses to one entry.
        key = topic.name.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(topic)
    return unique


def find_relationships(
    topics: list[Topic],
    client: Groq,
    feedback: str = "",
) -> list[Relationship]:
    """Ask Groq to identify relationships between the given topics.

    The prompt constrains valid IDs to those in the topics list.
    If `feedback` is non-empty, it gets prepended to the prompt so the
    model knows what went wrong on the previous attempt.
    """
    # Build a list of valid topic IDs to show the model.
    # The model must only use these IDs in its relationships.
    topic_list = "\n".join(
        f"  - {t.id}: {t.name} ({t.difficulty})"
        for t in topics
    )
    valid_ids = [t.id for t in topics]

    # Tool definition — same structure pattern as record_topics,
    # but for relationships. Each relationship has from_id, to_id, type.
    tool_definition = {
        "type": "function",
        "function": {
            "name": "record_relationships",
            "description": (
                "Record typed relationships between the given topics. "
                "from_id and to_id must be drawn from the provided topic list."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "relationships": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "from_id": {
                                    "type": "string",
                                    "enum": valid_ids,
                                    "description": "The id of the source topic.",
                                },
                                "to_id": {
                                    "type": "string",
                                    "enum": valid_ids,
                                    "description": "The id of the target topic.",
                                },
                                "type": {
                                    "type": "string",
                                    "enum": ["prerequisite", "related", "subtopic"],
                                },
                            },
                            "required": ["from_id", "to_id", "type"],
                        },
                    },
                },
                "required": ["relationships"],
            },
        },
    }

    system_prompt = (
        "You identify learning relationships between technical topics. "
        "Use 'prerequisite' when one topic must be learned before another. "
        "Use 'subtopic' when one topic is a structural part of another. "
        "Use 'related' when two topics are connected but neither is a prerequisite. "
        "Only use ids from the provided topic list. "
        "Do not invent ids that aren't listed. "
        "Do not create relationships where from_id equals to_id."
    )

    # The user prompt includes the topic list, any feedback from a previous
    # failed attempt, and an instruction.
    user_prompt_parts = [
        "Here are the topics:\n",
        topic_list,
        "\n\n",
    ]
    if feedback:
        user_prompt_parts.append(feedback + "\n\n")
    user_prompt_parts.append(
        "Identify the relationships between these topics."
    )
    user_prompt = "".join(user_prompt_parts)

    # Call the API, forcing tool use.
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        tools=[tool_definition],
        tool_choice={
            "type": "function",
            "function": {"name": "record_relationships"},
        },
        temperature=0,
    )

    # Pull out the tool call and parse its arguments.
    message = response.choices[0].message
    if not message.tool_calls:
        raise ValueError("LLM did not call the record_relationships tool")

    tool_call = message.tool_calls[0]
    try:
        args = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}")

    # Validate each raw relationship dict through our Pydantic model.
    # Skip invalid ones with a warning rather than crashing.
    relationships: list[Relationship] = []
    for raw_rel in args.get("relationships", []):
        try:
            rel = Relationship(**raw_rel)
            relationships.append(rel)
        except ValidationError as e:
            print(f"  ⚠ skipping invalid relationship {raw_rel}: {e}")

    return relationships

def validate(
    topics: list[Topic],
    relationships: list[Relationship],
) -> list[str]:
    """Check the skill map for structural problems.

    Returns a list of error messages. Empty list = all good.
    Checks:
      - dangling references (from_id or to_id not in topic ids)
      - self-loops (from_id == to_id)
      - cycles in the prerequisite subgraph
    """
    errors: list[str] = []
    topic_ids = {t.id for t in topics}

    # ─── Pass 1: edge-level sanity checks ───────────────────────────────
    for r in relationships:
        if r.from_id not in topic_ids:
            errors.append(
                f"Relationship references unknown from_id '{r.from_id}'"
            )
        if r.to_id not in topic_ids:
            errors.append(
                f"Relationship references unknown to_id '{r.to_id}'"
            )
        if r.from_id == r.to_id:
            errors.append(f"Self-loop on topic '{r.from_id}'")

    # ─── Pass 2: cycle detection in the prerequisite subgraph ───────────
    # Build an adjacency list from only the prerequisite edges.
    # If 'A is a prerequisite of B' is stored as (from=A, to=B), then
    # adjacency[A] contains B.
    adjacency: dict[str, list[str]] = {tid: [] for tid in topic_ids}
    for r in relationships:
        if (
            r.type == "prerequisite"
            and r.from_id in topic_ids
            and r.to_id in topic_ids
        ):
            adjacency[r.from_id].append(r.to_id)

    # DFS with three colors — the classic cycle-detection algorithm.
    #   WHITE (0) = never visited
    #   GRAY  (1) = currently on the DFS path (we're inside its subtree)
    #   BLACK (2) = fully processed, confirmed no cycle from here
    #
    # A cycle exists iff DFS encounters a GRAY node — that means we've
    # looped back to a node already on the current path.
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {tid: WHITE for tid in topic_ids}
    reported_cycles: set[tuple[str, ...]] = set()

    def dfs(node: str, path: list[str]) -> None:
        if color[node] == GRAY:
            # Back edge — extract the cycle from `path`.
            cycle_start = path.index(node)
            cycle = tuple(path[cycle_start:] + [node])
            if cycle not in reported_cycles:
                reported_cycles.add(cycle)
                errors.append(
                    f"Cycle in prerequisite chain: {' -> '.join(cycle)}"
                )
            return
        if color[node] == BLACK:
            return
        color[node] = GRAY
        path.append(node)
        for neighbor in adjacency.get(node, []):
            dfs(neighbor, path)
        path.pop()
        color[node] = BLACK

    for tid in topic_ids:
        if color[tid] == WHITE:
            dfs(tid, [])

    return errors


def print_tree(skill_map: SkillMap) -> None:
    """Print a text-tree view of the prerequisite chains.

    Topics with no incoming prerequisite edges are roots; print each root
    and its descendants indented underneath. Other relationship types
    (subtopic, related) are summarized below the tree.
    """
    if not skill_map.topics:
        print("(no topics)")
        return

    topic_by_id = {t.id: t for t in skill_map.topics}

    # Build adjacency from prerequisite edges only: from_id -> [to_ids].
    # Also track which topics have at least one incoming prereq edge.
    prereq_children: dict[str, list[str]] = {t.id: [] for t in skill_map.topics}
    has_incoming: set[str] = set()
    for r in skill_map.relationships:
        if r.type == "prerequisite":
            prereq_children[r.from_id].append(r.to_id)
            has_incoming.add(r.to_id)

    # Roots: topics with no incoming prerequisite edge.
    roots = sorted(
        t.id for t in skill_map.topics if t.id not in has_incoming
    )

    # DFS print. We track visited so that if the same topic appears
    # under multiple parents (diamond shape), we don't recurse into
    # it again — we mark it as already shown.
    visited: set[str] = set()

    def print_node(tid: str, indent: int) -> None:
        t = topic_by_id[tid]
        prefix = "  " * indent
        bullet = "•" if indent == 0 else "↳"
        already = " (already shown above)" if tid in visited else ""
        print(f"{prefix}{bullet} {t.name} [{t.difficulty}]{already}")
        if tid in visited:
            return
        visited.add(tid)
        for child_id in sorted(prereq_children.get(tid, [])):
            print_node(child_id, indent + 1)

    # Print the prerequisite forest.
    for root in roots:
        print_node(root, 0)

    # Anything that wasn't reached by following prereq edges from a root —
    # those are topics with no prereq relationships at all.
    unvisited = sorted(t.id for t in skill_map.topics if t.id not in visited)
    if unvisited:
        print("\nTopics with no prerequisite relationships:")
        for tid in unvisited:
            t = topic_by_id[tid]
            print(f"  • {t.name} [{t.difficulty}]")

    # Summaries of other relationship types.
    subtopic_edges = [
        r for r in skill_map.relationships if r.type == "subtopic"
    ]
    related_edges = [
        r for r in skill_map.relationships if r.type == "related"
    ]

    if subtopic_edges:
        print("\nSubtopic relationships:")
        for r in subtopic_edges:
            f = topic_by_id.get(r.from_id)
            t = topic_by_id.get(r.to_id)
            if f and t:
                print(f"  {f.name} ⊃ {t.name}")

    if related_edges:
        print("\nRelated topic pairs:")
        for r in related_edges:
            f = topic_by_id.get(r.from_id)
            t = topic_by_id.get(r.to_id)
            if f and t:
                print(f"  {f.name} ↔ {t.name}")

# ─── Main entry point ───────────────────────────────────────────────────

def main(input_path: str) -> None:
    client = Groq(api_key=GROQ_API_KEY)

    # 1. Read input
    text = Path(input_path).read_text(encoding="utf-8")
    print(f"Read {len(text)} characters from {input_path}")

    # 2. Split into sections
    sections = split_sections(text)
    print(f"Split into {len(sections)} sections")

    # 3. Extract topics from each section
    all_topics: list[Topic] = []
    for i, section in enumerate(sections):
        print(f"  Extracting from section {i+1}/{len(sections)}...")
        topics = extract_topics(section, client)
        all_topics.extend(topics)

    # 4. Deduplicate
    topics = deduplicate_topics(all_topics)
    print(f"Extracted {len(topics)} unique topics")

    # 5. Find relationships, with retry-on-validation-failure
    relationships: list[Relationship] = []
    feedback = ""
    for attempt in range(MAX_RETRIES):
        print(f"  Relating attempt {attempt+1}/{MAX_RETRIES}...")
        relationships = find_relationships(topics, client, feedback)
        errors = validate(topics, relationships)
        if not errors:
            break
        feedback = (
            "Your previous response had validation errors:\n"
            + "\n".join(f"  - {e}" for e in errors)
            + "\n\nPlease fix these and try again."
        )
    else:
        # All retries exhausted; persist whatever we have, but flag it.
        print(f"⚠ Validation still failing after {MAX_RETRIES} attempts. "
              f"Saving partial output.")

    skill_map = SkillMap(topics=topics, relationships=relationships)

    # 6. Output
    output_path = Path(input_path).stem + "_skillmap.json"
    Path(output_path).write_text(skill_map.model_dump_json(indent=2))
    print(f"\nWrote {output_path}")

    print("\nSkill tree:")
    print_tree(skill_map)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python skill_extractor.py <markdown_file>")
        sys.exit(1)
    main(sys.argv[1])