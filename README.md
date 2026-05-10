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
| Embedding source | `payload.instructions` (full skill prompt, ~6700 chars avg) |
| Graph database | Neo4j 5.x with native vector index |
| Average node degree | 8.8 |
| Search Precision@5 | 0.875 (evaluated over 20 queries) |
| Search latency | < 500ms |

---

## Architecture

### MCP Server

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
│  - 732 Skill nodes with embeddings (payload.instructions)    │
│  - Native vector index (cosine similarity)                   │
│  - hub_score (degree centrality)                             │
└──────────────────────────────────────────────────────────────┘
```

### Visualization pipeline (`viz/`)

```
staging/skills/*.yaml
    │
    ▼ parse_skills.py         — builds graph.json (nodes + keyword edges)
    │
    ▼ enrich_semantic.py      — adds KMeans communities + UMAP 2D positions
    │   (reads embeddings from Neo4j, runs KMeans n=18, UMAP 1536D→2D)
    │
    ▼ build_html.py           — inlines graph.json into index_template.html
    │
    ▼ index.html              — standalone D3.js visualization (amber theme)
                                gitignored — rebuild locally
```

> **Note on embedding strategy:** two separate embedding sets are maintained:
> - **Search (Neo4j):** `payload.instructions` — full skill prompt, best semantic search quality
> - **Visualization (KMeans/UMAP):** same Neo4j embeddings — clusters may be denser but positions are semantically meaningful

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

# Step 2 — Generate semantic embeddings + inject keyword edges
python scripts/embed_skills.py

# Step 3 — Connect archetypes to domain skills
python scripts/merge_archetypes.py

# Step 4 — Load into Neo4j (dry-run first)
python -m registry.cli load staging/skills/ --schema skills/schema.json --dry-run
python -m registry.cli load staging/skills/ --schema skills/schema.json

# Step 5 — Upgrade to V3 embeddings (payload.instructions) for better search quality
#           Run H005 experiment first to generate the cache, then:
python scripts/push_embeddings_v3.py
```

### 5. Build the visualization (optional)

```bash
# Build graph.json from staging skills
python viz/parse_skills.py

# Enrich with semantic layout (requires Neo4j running)
python viz/enrich_semantic.py   # ~30s for UMAP on 732 skills

# Output: viz/index.html — open in browser, no server needed
```

### 6. Connect to Claude

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
  embedding: Float[]  // 1536-dim vector (payload.instructions)
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

## Embedding strategy

Five embedding strategies were tested and measured on 20 queries (Precision@5, MRR):

| Strategy | Text embedded | P@5 | Notes |
|---|---|---|---|
| V1 — description only | 1–2 sentences | 0.700 | Baseline, in production until 2026-05-10 |
| V2 — rich text | name + desc + caps + reqs | ~0.72 | caps/reqs empty in current dataset |
| V3 — payload.instructions | Full skill prompt (~6700 chars) | **0.875** | **Current production** |
| TF-IDF keywords | Top-30 discriminative terms | — | Increases graph density, not useful for viz |

Key insight: `payload.instructions` contains explicit technical terms (`MLflow`, `CSRF`, `medallion architecture`) that short descriptions omit, recovering 5 queries where V1 returned 0 precision.

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
- [D3.js](https://d3js.org/) — Interactive skill graph visualization
- [UMAP](https://umap-learn.readthedocs.io/) — Dimensionality reduction for viz layout
- [Model Context Protocol](https://modelcontextprotocol.io/) — Claude tool integration
