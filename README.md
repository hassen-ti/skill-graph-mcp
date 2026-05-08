# Skill Graph MCP — GraphRAG Knowledge Base for Claude

> **732 skills. Semantic search. Graph traversal. Zero manual installation.**
> Claude automatically loads expert context by navigating a Neo4j knowledge graph via MCP.

---

## What is this?

**Skill Graph MCP** is a [Model Context Protocol](https://modelcontextprotocol.io/) server that gives Claude access to a semantic knowledge graph of 732 expert skills. Instead of installing skills manually, Claude autonomously searches, retrieves and traverses the graph to load the right expert context for any task.

```
User: "I want to build a real-time e-commerce site with Stripe"
  └─► Claude calls search_skills("e-commerce stripe payments")
        └─► semantic_score: stripe-integration [0.73], payment-integration [0.75]
              └─► Claude calls get_skill("stripe-integration")
                    └─► Full expert context loaded → Claude is now a Stripe expert
```

**No `/skill install`. No copy-paste. Claude navigates autonomously.**

---

## Key numbers

| Metric | Value |
|---|---|
| Skills in graph | 732 nodes |
| Semantic edges | 3,364 relationships |
| Embedding model | OpenAI `text-embedding-3-small` (1536 dims) |
| Graph database | Neo4j 5.x with native vector index |
| Average node degree | 8.8 |
| Avg semantic search score | 0.73+ |
| Search latency | < 500ms |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        Claude (LLM)                          │
│                  calls MCP tools autonomously                │
└──────────────────┬───────────────────────────────────────────┘
                   │ stdio (MCP protocol)
┌──────────────────▼───────────────────────────────────────────┐
│              Skill Graph MCP Server (FastMCP)                │
│                                                              │
│  search_skills(query)  ──► embed query (OpenAI)              │
│                             vector search (Neo4j)            │
│                                                              │
│  get_skill(id, depth)  ──► fetch node + payload              │
│                             layer_1/layer_2 neighbors        │
│                                                              │
│  navigate(id, type)    ──► traverse edges                    │
│                             REQUIRES / ENABLES / COLLABORATES│
│                                                              │
│  get_knowledge(ref)    ──► safe file read (whitelist)        │
└──────────────────┬───────────────────────────────────────────┘
                   │ bolt://localhost:7687
┌──────────────────▼───────────────────────────────────────────┐
│                Neo4j 5.x (Docker)                            │
│  - 732 Skill nodes with embeddings                           │
│  - Native vector index (cosine similarity)                   │
│  - hub_score (degree centrality)                             │
└──────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

- Python 3.12+
- Docker Desktop
- An OpenAI API key (for query embedding — ~$0.000002/query)
- Neo4j 5.x via Docker (see below)

---

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/Hassen-Ti/skill-graph-mcp.git
cd skill-graph-mcp
pip install -e .
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in your keys:
#   OPENAI_API_KEY=sk-...
#   NEO4J_PASSWORD=your_password
```

### 3. Start Neo4j

```bash
docker-compose up -d
# Neo4j will be available at http://localhost:7474
# Wait ~30s for startup
```

### 4. Build the knowledge graph

```bash
# Step 1 — Convert skills to YAML (requires your skills source)
python scripts/convert_skills.py

# Step 2 — Generate semantic embeddings + inject edges
python scripts/embed_skills.py

# Step 3 — Connect archetypes to domain skills
python scripts/merge_archetypes.py

# Step 4 — Load into Neo4j (dry-run first)
python -m registry.cli load staging/skills/ --schema skills/schema.json --dry-run
python -m registry.cli load staging/skills/ --schema skills/schema.json
```

### 5. Connect to Claude

Add to your `claude_desktop_config.json` (`%APPDATA%\Claude\` on Windows):

```json
{
  "mcpServers": {
    "skill-graph": {
      "command": "/path/to/python",
      "args": ["-m", "server.main"],
      "cwd": "/path/to/skill-graph-mcp",
      "env": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "your_password",
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```

Restart Claude Desktop. The MCP will appear alongside your other servers.

---

## MCP Tools Reference

### `search_skills(query)`

Semantic search over 732 skills using OpenAI embeddings + Neo4j vector index.

| Parameter | Type | Description |
|---|---|---|
| `query` | string | Natural-language description of the capability needed |

**Returns:** Top 3 `SkillCandidate` objects with `semantic_score` and `hub_score`.

```json
[
  {"id": "stripe-integration", "semantic_score": 0.7311, "hub_score": 0.1429},
  {"id": "payment-integration", "semantic_score": 0.7464, "hub_score": 0.1905}
]
```

---

### `get_skill(id, depth="shallow")`

Retrieve the full expert context for a skill, including instructions and neighbors.

| Parameter | Type | Description |
|---|---|---|
| `id` | string | Skill node identifier (from search results) |
| `depth` | string | `"shallow"` (L1 neighbors) or `"full"` (L1 + L2) |

**Rate-limited to 10 calls per session** to control context cost.

---

### `navigate(from_id, edge_type, direction="outbound")`

Traverse graph edges from a skill node.

| Parameter | Type | Options |
|---|---|---|
| `from_id` | string | Any skill ID |
| `edge_type` | string | `REQUIRES`, `ENABLES`, `COLLABORATES_WITH`, `USES`, `EXTENDS`, `PART_OF` |
| `direction` | string | `"outbound"`, `"inbound"`, `"both"` |

---

### `get_knowledge(ref)`

Read a knowledge-base document safely (path-confined, extension-whitelisted).

| Parameter | Type | Description |
|---|---|---|
| `ref` | string | Plain filename (e.g. `"api_patterns.md"`) — no path separators |

---

## Graph Schema

```
(:Skill {
  id: String          // unique, lowercase, hyphens allowed
  name: String
  description: String
  type: String        // "domain" | "tool" | "role" | "cluster"
  hub_score: Float    // degree centrality [0.0 - 1.0]
  embedding: Float[]  // 1536-dim OpenAI vector
  payload_json: String // JSON: instructions, tools, knowledge
})

[:REQUIRES]          // A cannot function without B
[:ENABLES]           // A unlocks or enhances B
[:COLLABORATES_WITH] // Semantic similarity
[:USES]              // A leverages B as a tool
[:EXTENDS]           // A specialises B
[:PART_OF]           // A belongs to cluster B
```

---

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

---

## Security

- API keys via environment variables only
- `get_knowledge`: 3-layer path confinement (`relative_to()`, extension whitelist, symlink resolution)
- Cypher queries use parameterised statements throughout
- Edge type validation via whitelist at MCP tool boundary
- Rate limiting on `get_skill` (10/session)

See [docs/SECURITY_AUDIT.md](docs/SECURITY_AUDIT.md) for the full audit report.

---

## License

MIT

---

## Built with

- [FastMCP](https://github.com/jlowin/fastmcp) — Python MCP server framework
- [Neo4j](https://neo4j.com/) — Graph database with native vector index
- [OpenAI](https://platform.openai.com/) — `text-embedding-3-small` embeddings
- [Model Context Protocol](https://modelcontextprotocol.io/) — Claude tool integration