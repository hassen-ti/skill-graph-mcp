# User Guide — Skill Graph MCP

> Claude automatically becomes an expert by navigating the knowledge graph — without any manual `/skill install`.

## How it works

```
You type: "Help me build a secure login with JWT"
  └─► Claude: search_skills("secure authentication JWT")
        └─► auth-implementation-patterns [0.81]
              └─► get_skill("auth-implementation-patterns")
                    └─► Full JWT guide loaded → expert answer
```

## Prerequisites

1. Docker Desktop running
2. Neo4j container up (`http://localhost:7474`)
3. `skill-graph` in Claude MCP list: `claude mcp list` → `skill-graph: Connected`

## What triggers automatic skill lookup

| Domain | Example prompts |
|---|---|
| APIs / Backend | "Build a REST API", "Add JWT auth", "Design webhooks" |
| Frontend | "Create a React dashboard", "Add real-time updates" |
| DevOps | "Deploy to k8s", "Set up CI/CD", "Configure Nginx" |
| Security | "Review my code", "Implement OAuth2", "Prevent XSS" |
| Payments | "Integrate Stripe", "Add subscriptions" |
| Data | "Build a pipeline", "Set up Airflow", "Write dbt models" |

## Troubleshooting

**MCP not visible:** Check Docker is running, Neo4j at `localhost:7474`, restart Claude.

**Claude not using the graph:** Be specific — `"Implement JWT with refresh tokens in FastAPI"` not `"Help with auth"`.

**Rate limit:** `get_skill` is capped at 10/session. Start a new conversation.

**Neo4j error:** `docker-compose restart neo4j` then wait 30s.

## Graph at a glance

```
732 nodes: 713 skills + 14 archetypes + 5 clusters
3364 edges: COLLABORATES_WITH (semantic) + ENABLES (archetype→skill) + REQUIRES
```