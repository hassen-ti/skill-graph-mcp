# Architecture — Skill Graph MCP

See the full architecture document in the repository for the complete technical deep-dive.

## Quick overview

```
DATA PIPELINE (one-time):
  713 SKILL.md → convert_skills.py → 718 YAML
                → embed_skills.py → +2865 semantic edges (cosine > 0.55)
                → merge_archetypes.py → +138 enables edges
                → registry.cli load → Neo4j (732 nodes, 3364 edges)

RUNTIME:
  Claude → stdio/MCP → FastMCP server
    search_skills(query) → OpenAI embed → Neo4j vector index → top-3
    get_skill(id)        → Neo4j node + payload + L1 neighbors
    navigate(id, type)   → Neo4j edge traversal
    get_knowledge(ref)   → safe local file read
```

## Neo4j schema

```cypher
(:Skill { id, name, description, type, hub_score, embedding, payload_json })
[:REQUIRES] [:ENABLES] [:COLLABORATES_WITH] [:USES] [:EXTENDS] [:PART_OF]
```

## Security model

- Path confinement via `Path.relative_to()` (not `startswith()`)
- Edge type whitelist at MCP tool boundary
- Input length validation on all tool parameters
- No default credentials — fail fast on missing env vars
- Parameterised Cypher queries throughout