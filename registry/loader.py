# registry/loader.py
from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Any
import yaml
import jsonschema
from jsonschema import Draft7Validator

logger = logging.getLogger(__name__)
MAX_EXTEND_DEPTH: int = 3


def validate_yaml(skill_dict: dict, schema_path: Path) -> list[str]:
    with schema_path.open("r", encoding="utf-8") as fh:
        schema = json.load(fh)
    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(skill_dict), key=lambda e: list(e.path))
    return [_format_error(e) for e in errors]


def _format_error(error: jsonschema.ValidationError) -> str:
    if error.absolute_path:
        field_name = str(list(error.absolute_path)[-1])
        return f"{field_name}: {error.message}"
    return error.message


def resolve_extends_chain_loader(skill_id: str, registry: dict[str, dict], depth: int = 0) -> dict[str, Any]:
    if depth > MAX_EXTEND_DEPTH:
        raise ValueError(f"extends chain exceeds max depth {MAX_EXTEND_DEPTH} at '{skill_id}'")
    if skill_id not in registry:
        raise KeyError(f"extends references unknown skill '{skill_id}'")
    skill = registry[skill_id]
    payload = skill.get("payload") or {}
    own_instructions = payload.get("instructions", "")
    own_tools = set(payload.get("tools") or [])
    own_exclude = set(payload.get("exclude_tools") or [])
    own_knowledge = set(payload.get("knowledge") or [])
    parent_id = skill.get("extends")
    if parent_id is None:
        return {"instructions": own_instructions, "tools": own_tools - own_exclude, "knowledge": own_knowledge}
    parent_resolved = resolve_extends_chain_loader(parent_id, registry, depth + 1)
    resolved_instructions = own_instructions if own_instructions else parent_resolved["instructions"]
    resolved_tools = (own_tools | parent_resolved["tools"]) - own_exclude
    return {"instructions": resolved_instructions, "tools": resolved_tools, "knowledge": own_knowledge | parent_resolved["knowledge"]}


def load_skill_file(yaml_path: Path, schema_path: Path) -> dict:
    with yaml_path.open("r", encoding="utf-8") as fh:
        skill_dict = yaml.safe_load(fh)
    if not isinstance(skill_dict, dict):
        raise ValueError(f"{yaml_path}: YAML root must be a mapping")
    errors = validate_yaml(skill_dict, schema_path)
    if errors:
        raise ValueError(f"{yaml_path}: schema validation failed - {'; '.join(errors)}")
    return skill_dict


async def load_skills_directory(skills_dir, schema_path, client, embedder_module, dry_run=False):
    yaml_files = sorted([p for p in skills_dir.iterdir() if p.suffix in {".yaml", ".yml"}])
    if not yaml_files:
        logger.warning("No YAML files found in %s", skills_dir)
        return
    registry: dict[str, dict] = {}
    for yaml_path in yaml_files:
        skill = load_skill_file(yaml_path, schema_path)
        skill_id = skill["id"]
        if skill_id in registry:
            raise ValueError(f"Duplicate skill id '{skill_id}'")
        registry[skill_id] = skill
    _detect_orphan_edges(registry)
    if dry_run:
        print(f"Validated {len(registry)} skills OK.")
        return
    for skill in registry.values():
        await _write_skill_node(client, skill)
    for skill_id, skill in registry.items():
        for edge in skill.get("edges") or []:
            await _write_skill_edge(client, skill_id, edge["to"], edge["type"])
    for skill_id, skill in registry.items():
        if parent_id := skill.get("extends"):
            await _write_skill_edge(client, skill_id, parent_id, "EXTENDS")
    await client.recompute_hub_scores()
    cycles = await client.detect_cycles()
    if cycles:
        raise RuntimeError(f"Cycle detected: {cycles[0]}")
    await embedder_module.update_embeddings(client, registry)
    logger.info("Loaded %d skills.", len(registry))


def _detect_orphan_edges(registry):
    known_ids = set(registry.keys())
    for skill_id, skill in registry.items():
        for edge in skill.get("edges") or []:
            if edge["to"] not in known_ids:
                raise KeyError(f"'{skill_id}' has edge to unknown skill '{edge['to']}'")


async def _write_skill_node(client, skill):
    import tiktoken
    payload = skill.get("payload") or {}
    enc = tiktoken.get_encoding("cl100k_base")
    instructions_text = payload.get("instructions", "")
    skill_data = {
        "id": skill["id"], "name": skill["name"], "description": skill["description"],
        "type": skill["type"], "author": skill.get("author", ""),
        "version": skill.get("version", ""), "priority": skill.get("priority", 2),
        "context_cost": len(enc.encode(instructions_text)),
        "payload": {
            "instructions": instructions_text, "tools": payload.get("tools") or [],
            "knowledge": payload.get("knowledge") or [], "exclude_tools": payload.get("exclude_tools") or [],
        },
    }
    await client.upsert_skill_node(skill_data)


async def _write_skill_edge(client, from_id, to_id, edge_type):
    await client.upsert_edge(from_id, to_id, edge_type.upper().replace("-", "_"))


async def _recompute_hub_scores(client):
    await client.recompute_hub_scores()


async def _detect_cycles(client):
    return await client.detect_cycles()
