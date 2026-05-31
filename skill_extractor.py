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

from google import genai
from google.genai import types
from openai import OpenAI
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

# Pick provider based on available API key
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# Determine which provider to use
USE_OPENROUTER = bool(OPENROUTER_API_KEY)
USE_GEMINI = not USE_OPENROUTER and bool(GOOGLE_API_KEY)
USE_GROQ = not USE_OPENROUTER and not USE_GEMINI

# Model selection
if USE_OPENROUTER:
    MODEL = "meta-llama/llama-3.3-70b-instruct"  # Fast, reliable on OpenRouter
elif USE_GEMINI:
    MODEL = "gemini-2.5-flash"
else:
    MODEL = "llama-3.3-70b-versatile"

MAX_RETRIES = 3

# Initialize clients
_openrouter_client = None
_gemini_client = None
_groq_client = None

if USE_OPENROUTER:
    _openrouter_client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY
    )
elif USE_GEMINI:
    _gemini_client = genai.Client(api_key=GOOGLE_API_KEY)


# Pydantic models

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


# Pipeline functions

def split_sections(text: str) -> list[str]:
    """Split markdown into sections on H1/H2 headings."""
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


def extract_topics(section: str, client=None) -> list[Topic]:
    """Extract topics from a section using LLM tool-use."""
    if USE_OPENROUTER:
        return _extract_topics_openrouter(section, client)
    elif USE_GEMINI:
        return _extract_topics_gemini(section, client)
    else:
        return _extract_topics_groq(section, client)


def _extract_topics_openrouter(section: str, client: OpenAI | None = None) -> list[Topic]:
    """Extract topics using OpenRouter (OpenAI-compatible API)."""
    if client is None:
        client = _openrouter_client

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
                                "id": {"type": "string", "pattern": "^[a-z0-9-]+$"},
                                "name": {"type": "string"},
                                "description": {"type": "string"},
                                "difficulty": {"type": "string", "enum": ["beginner", "intermediate", "advanced"]},
                            },
                            "required": ["id", "name", "description", "difficulty"],
                        },
                    }
                },
                "required": ["topics"],
            },
        },
    }

    system_prompt = (
        "You extract technical topics from learning material. "
        "For each topic, provide: a short slug-style id (lowercase letters, "
        "numbers, hyphens only — no spaces), a short human-readable name, "
        "a one-sentence description, and a difficulty level. "
        "Only extract topics that are actually present in the text. "
        "Do not invent topics that aren't there."
    )

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Extract topics from this section:\n\n{section}"},
        ],
        tools=[tool_definition],
        tool_choice={"type": "function", "function": {"name": "record_topics"}},
        temperature=0,
    )

    message = response.choices[0].message
    if not message.tool_calls:
        raise ValueError("LLM did not call the record_topics tool")

    tool_call = message.tool_calls[0]
    try:
        args = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}")

    topics: list[Topic] = []
    for raw_topic in args.get("topics", []):
        try:
            topic = Topic(**raw_topic)
            topics.append(topic)
        except ValidationError as e:
            print(f"  WARNING: skipping invalid topic {raw_topic.get('name', '?')}: {e}")

    return topics


def _extract_topics_gemini(section: str, client: genai.Client | None = None) -> list[Topic]:
    """Extract topics using Gemini's function calling API (new google.genai package)."""
    if client is None:
        client = _gemini_client

    # Define the tool for Gemini
    tool_definition = types.FunctionDeclaration(
        name="record_topics",
        description="Record the technical topics found in this section of learning material.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "topics": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "id": types.Schema(
                                type=types.Type.STRING,
                                description="A short slug: lowercase letters, digits, hyphens only."
                            ),
                            "name": types.Schema(type=types.Type.STRING),
                            "description": types.Schema(type=types.Type.STRING),
                            "difficulty": types.Schema(
                                type=types.Type.STRING,
                                enum=["beginner", "intermediate", "advanced"]
                            ),
                        },
                        required=["id", "name", "description", "difficulty"]
                    )
                )
            },
            required=["topics"]
        )
    )

    system_prompt = (
        "You extract technical topics from learning material. "
        "For each topic, provide: a short slug-style id (lowercase letters, "
        "numbers, hyphens only — no spaces), a short human-readable name, "
        "a one-sentence description, and a difficulty level. "
        "Only extract topics that are actually present in the text. "
        "Do not invent topics that aren't there."
    )

    user_prompt = f"Extract topics from this section:\n\n{section}"
    full_prompt = f"{system_prompt}\n\n{user_prompt}"

    response = client.models.generate_content(
        model=MODEL,
        contents=full_prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(function_declarations=[tool_definition])],
            temperature=0
        )
    )

    # Check for valid response
    if not response.candidates:
        raise ValueError("Gemini returned no candidates")

    candidate = response.candidates[0]

    # Check finish_reason for blocked/empty responses
    if hasattr(candidate, 'finish_reason') and candidate.finish_reason:
        if candidate.finish_reason.name in ('RECITATION', 'SAFETY', 'BLOCKED'):
            raise ValueError(f"Response blocked: {candidate.finish_reason.name}")

    if not candidate.content:
        raise ValueError("Gemini returned no content")

    if not candidate.content.parts or len(candidate.content.parts) == 0:
        raise ValueError("Gemini returned empty parts list")

    # Find the part with function_call (may be after text parts)
    function_call_part = None
    for part in candidate.content.parts:
        if part.function_call:
            function_call_part = part
            break

    if not function_call_part:
        raise ValueError("LLM did not call the record_topics tool")

    # In new API, args is already a dict
    args = function_call_part.function_call.args

    # Validate through Pydantic
    topics: list[Topic] = []
    for raw_topic in args.get("topics", []):
        try:
            topic = Topic(**raw_topic)
            topics.append(topic)
        except ValidationError as e:
            print(f"  WARNING: skipping invalid topic {raw_topic.get('name', '?')}: {e}")

    return topics


def _extract_topics_groq(section: str, client) -> list[Topic]:
    """Extract topics using Groq's function calling API (fallback)."""
    from groq import Groq
    if client is None:
        client = Groq(api_key=GROQ_API_KEY)

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
                                "id": {"type": "string", "pattern": "^[a-z0-9-]+$"},
                                "name": {"type": "string"},
                                "description": {"type": "string"},
                                "difficulty": {"type": "string", "enum": ["beginner", "intermediate", "advanced"]},
                            },
                            "required": ["id", "name", "description", "difficulty"],
                        },
                    }
                },
                "required": ["topics"],
            },
        },
    }

    system_prompt = (
        "You extract technical topics from learning material. "
        "For each topic, provide: a short slug-style id (lowercase letters, "
        "numbers, hyphens only — no spaces), a short human-readable name, "
        "a one-sentence description, and a difficulty level. "
        "Only extract topics that are actually present in the text. "
        "Do not invent topics that aren't there."
    )

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Extract topics from this section:\n\n{section}"},
        ],
        tools=[tool_definition],
        tool_choice={"type": "function", "function": {"name": "record_topics"}},
        temperature=0,
    )

    message = response.choices[0].message
    if not message.tool_calls:
        raise ValueError("LLM did not call the record_topics tool")

    tool_call = message.tool_calls[0]
    try:
        args = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}")

    topics: list[Topic] = []
    for raw_topic in args.get("topics", []):
        try:
            topic = Topic(**raw_topic)
            topics.append(topic)
        except ValidationError as e:
            print(f"  WARNING: skipping invalid topic {raw_topic.get('name', '?')}: {e}")

    return topics


def deduplicate_topics(topics: list[Topic]) -> list[Topic]:
    """Remove duplicate topics by normalized name."""
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
    client=None,
    feedback: str = "",
) -> list[Relationship]:
    """Ask LLM to identify relationships between the given topics.

    The prompt constrains valid IDs to those in the topics list.
    If `feedback` is non-empty, it gets prepended to the prompt so the
    model knows what went wrong on the previous attempt.
    """
    if USE_OPENROUTER:
        return _find_relationships_openrouter(topics, client, feedback)
    elif USE_GEMINI:
        return _find_relationships_gemini(topics, client, feedback)
    else:
        return _find_relationships_groq(topics, client, feedback)


def _find_relationships_openrouter(
    topics: list[Topic],
    client: OpenAI | None = None,
    feedback: str = "",
) -> list[Relationship]:
    """Find relationships using OpenRouter (OpenAI-compatible API)."""
    if client is None:
        client = _openrouter_client

    topic_list = "\n".join(
        f"  - {t.id}: {t.name} ({t.difficulty})"
        for t in topics
    )
    valid_ids = [t.id for t in topics]

    tool_definition = {
        "type": "function",
        "function": {
            "name": "record_relationships",
            "description": "Record typed relationships between the given topics. from_id and to_id must be drawn from the provided topic list.",
            "parameters": {
                "type": "object",
                "properties": {
                    "relationships": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "from_id": {"type": "string", "enum": valid_ids},
                                "to_id": {"type": "string", "enum": valid_ids},
                                "type": {"type": "string", "enum": ["prerequisite", "related", "subtopic"]},
                            },
                            "required": ["from_id", "to_id", "type"],
                        },
                    }
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

    user_prompt_parts = ["Here are the topics:\n", topic_list, "\n\n"]
    if feedback:
        user_prompt_parts.append(feedback + "\n\n")
    user_prompt_parts.append("Identify the relationships between these topics.")
    user_prompt = "".join(user_prompt_parts)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        tools=[tool_definition],
        tool_choice={"type": "function", "function": {"name": "record_relationships"}},
        temperature=0,
    )

    message = response.choices[0].message
    if not message.tool_calls:
        raise ValueError("LLM did not call the record_relationships tool")

    tool_call = message.tool_calls[0]
    try:
        args = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}")

    relationships: list[Relationship] = []
    for raw_rel in args.get("relationships", []):
        try:
            rel = Relationship(**raw_rel)
            relationships.append(rel)
        except ValidationError as e:
            print(f"  WARNING: skipping invalid relationship {raw_rel}: {e}")

    return relationships


def _find_relationships_gemini(
    topics: list[Topic],
    client: genai.Client | None = None,
    feedback: str = "",
) -> list[Relationship]:
    """Find relationships using Gemini's function calling API (new google.genai package)."""
    if client is None:
        client = _gemini_client

    topic_list = "\n".join(
        f"  - {t.id}: {t.name} ({t.difficulty})"
        for t in topics
    )
    valid_ids = [t.id for t in topics]

    # Define tool for Gemini
    tool_definition = types.FunctionDeclaration(
        name="record_relationships",
        description="Record typed relationships between the given topics. from_id and to_id must be drawn from the provided topic list.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "relationships": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "from_id": types.Schema(
                                type=types.Type.STRING,
                                description="The id of the source topic.",
                            ),
                            "to_id": types.Schema(
                                type=types.Type.STRING,
                                description="The id of the target topic.",
                            ),
                            "type": types.Schema(
                                type=types.Type.STRING,
                                enum=["prerequisite", "related", "subtopic"]
                            ),
                        },
                        required=["from_id", "to_id", "type"]
                    )
                )
            },
            required=["relationships"]
        )
    )

    system_prompt = (
        "You identify learning relationships between technical topics. "
        "Use 'prerequisite' when one topic must be learned before another. "
        "Use 'subtopic' when one topic is a structural part of another. "
        "Use 'related' when two topics are connected but neither is a prerequisite. "
        "Only use ids from the provided topic list. "
        "Do not invent ids that aren't listed. "
        "Do not create relationships where from_id equals to_id."
    )

    user_prompt_parts = [
        "Here are the topics:\n",
        topic_list,
        "\n\n",
    ]
    if feedback:
        user_prompt_parts.append(feedback + "\n\n")
    user_prompt_parts.append("Identify the relationships between these topics.")
    full_prompt = "".join(user_prompt_parts)

    response = client.models.generate_content(
        model=MODEL,
        contents=full_prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(function_declarations=[tool_definition])],
            temperature=0
        )
    )

    # Check for valid response
    if not response.candidates:
        raise ValueError("Gemini returned no candidates")

    candidate = response.candidates[0]

    # Check finish_reason for blocked/empty responses
    if hasattr(candidate, 'finish_reason') and candidate.finish_reason:
        if candidate.finish_reason.name in ('RECITATION', 'SAFETY', 'BLOCKED'):
            raise ValueError(f"Response blocked: {candidate.finish_reason.name}")

    if not candidate.content:
        raise ValueError("Gemini returned no content")

    if not candidate.content.parts or len(candidate.content.parts) == 0:
        raise ValueError("Gemini returned empty parts list")

    # Find the part with function_call (may be after text parts)
    function_call_part = None
    for part in candidate.content.parts:
        if part.function_call:
            function_call_part = part
            break

    if not function_call_part:
        raise ValueError("LLM did not call the record_relationships tool")

    # In new API, args is already a dict
    args = function_call_part.function_call.args

    relationships: list[Relationship] = []
    for raw_rel in args.get("relationships", []):
        try:
            rel = Relationship(**raw_rel)
            relationships.append(rel)
        except ValidationError as e:
            print(f"  WARNING: skipping invalid relationship {raw_rel}: {e}")

    return relationships


def _find_relationships_groq(
    topics: list[Topic],
    client,
    feedback: str = "",
) -> list[Relationship]:
    """Find relationships using Groq's function calling API (fallback)."""
    from groq import Groq
    if client is None:
        client = Groq(api_key=GROQ_API_KEY)

    topic_list = "\n".join(
        f"  - {t.id}: {t.name} ({t.difficulty})"
        for t in topics
    )
    valid_ids = [t.id for t in topics]

    tool_definition = {
        "type": "function",
        "function": {
            "name": "record_relationships",
            "description": "Record typed relationships between the given topics. from_id and to_id must be drawn from the provided topic list.",
            "parameters": {
                "type": "object",
                "properties": {
                    "relationships": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "from_id": {"type": "string", "enum": valid_ids},
                                "to_id": {"type": "string", "enum": valid_ids},
                                "type": {"type": "string", "enum": ["prerequisite", "related", "subtopic"]},
                            },
                            "required": ["from_id", "to_id", "type"],
                        },
                    }
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

    user_prompt_parts = ["Here are the topics:\n", topic_list, "\n\n"]
    if feedback:
        user_prompt_parts.append(feedback + "\n\n")
    user_prompt_parts.append("Identify the relationships between these topics.")
    user_prompt = "".join(user_prompt_parts)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        tools=[tool_definition],
        tool_choice={"type": "function", "function": {"name": "record_relationships"}},
        temperature=0,
    )

    message = response.choices[0].message
    if not message.tool_calls:
        raise ValueError("LLM did not call the record_relationships tool")

    tool_call = message.tool_calls[0]
    try:
        args = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}")

    relationships: list[Relationship] = []
    for raw_rel in args.get("relationships", []):
        try:
            rel = Relationship(**raw_rel)
            relationships.append(rel)
        except ValidationError as e:
            print(f"  WARNING: skipping invalid relationship {raw_rel}: {e}")

    return relationships

def validate(
    topics: list[Topic],
    relationships: list[Relationship],
) -> list[str]:
    """Check for dangling refs, self-loops, and cycles in prerequisite chains."""
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

    # DFS cycle detection using three colors:
    #   WHITE (0) = never visited, GRAY (1) = on current path, BLACK (2) = processed
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
    """Print prerequisite chains as a tree, summarize other relationships."""
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

# Main entry point

def main(input_path: str) -> None:
    # Initialize client based on provider
    if USE_OPENROUTER:
        client = _openrouter_client
        print(f"Using OpenRouter model: {MODEL}")
    elif USE_GEMINI:
        client = _gemini_client
        print(f"Using Gemini model: {MODEL}")
    else:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        print(f"Using Groq model: {MODEL}")

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