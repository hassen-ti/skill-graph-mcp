# server/search/vector_search.py
import os
import logging
from typing import Any
from openai import AsyncOpenAI
from neo4j import AsyncDriver
from server.models.skill_node import SkillCandidate

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIMS = 3072
# 8191 token limit for text-embedding-3-large
_MAX_TOKENS = 8191
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


def _truncate_to_token_limit(text: str, max_tokens: int = _MAX_TOKENS) -> str:
    """Truncate text to stay within the model's token limit using tiktoken."""
    try:
        import tiktoken
        enc = tiktoken.encoding_for_model("text-embedding-3-large")
        tokens = enc.encode(text)
        if len(tokens) <= max_tokens:
            return text
        return enc.decode(tokens[:max_tokens])
    except Exception:
        # Fallback: rough char-based truncation (~4 chars/token)
        max_chars = max_tokens * 4
        return text[:max_chars]


async def embed_text(text: str) -> list[float]:
    client = _get_openai_client()
    text = _truncate_to_token_limit(text)
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


async def update_skill_embedding(client: Any, skill_id: str, text: str) -> None:
    from server.graph.neo4j_client import Neo4jClient
    embedding = await embed_text(text)
    await client._run(_CYPHER_SET_EMBEDDING, {"skill_id": skill_id, "embedding": embedding})
