# server/search/vector_search.py
import os
from openai import AsyncOpenAI
from neo4j import AsyncDriver
from server.models.skill_node import SkillCandidate

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMS = 1536
INDEX_NAME = "skill_description_embedding"

_CYPHER_VECTOR_SEARCH = """
CALL db.index.vector.queryNodes($index, $k, $embedding)
YIELD node, score
RETURN node.id AS id, node.name AS name,
       score AS semantic_score, node.hub_score AS hub_score
"""

_CYPHER_SET_EMBEDDING = """
MATCH (s:Skill {id: $skill_id})
SET s.embedding = $embedding
"""

_openai_client: AsyncOpenAI | None = None


def _get_openai_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "OPENAI_API_KEY is not set. Copy .env.example to .env and fill in your key."
            )
        _openai_client = AsyncOpenAI(api_key=api_key)
    return _openai_client


async def embed_text(text: str) -> list[float]:
    client = _get_openai_client()
    response = await client.embeddings.create(input=text, model=EMBEDDING_MODEL)
    return response.data[0].embedding


async def search_skills(
    driver: AsyncDriver, query: str, top_n: int = 3,
) -> list[SkillCandidate]:
    embedding = await embed_text(query)
    async with driver.session() as session:
        result = await session.run(
            _CYPHER_VECTOR_SEARCH, index=INDEX_NAME, k=top_n, embedding=embedding
        )
        candidates: list[SkillCandidate] = []
        async for record in result:
            candidates.append(SkillCandidate(
                id=record["id"], name=record["name"],
                semantic_score=round(float(record["semantic_score"]), 4),
                hub_score=round(float(record["hub_score"] or 0.0), 4),
            ))
    return candidates[:top_n]


async def update_skill_embedding(driver: AsyncDriver, skill_id: str, description: str) -> None:
    embedding = await embed_text(description)
    async with driver.session() as session:
        await session.run(_CYPHER_SET_EMBEDDING, skill_id=skill_id, embedding=embedding)
