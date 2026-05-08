# server/models/skill_node.py
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field

NodeType = Literal["role", "tool", "domain", "responsibility", "cluster"]


class SkillNodeMetadata(BaseModel):
    id: str
    name: str
    description: str
    author: str = ""
    version: str = ""
    type: NodeType = "role"
    priority: int = Field(default=1, ge=1, le=3)
    prerequisites: list[str] = []
    hub_score: float = Field(default=0.0, ge=0.0, le=1.0)
    degree: int = 0
    context_cost: int = 0


class SkillPayload(BaseModel):
    instructions: str = ""
    tools: list[str] = []
    knowledge: list[str] = []
    exclude_tools: list[str] = []


class NeighborMetadata(BaseModel):
    id: str
    name: str
    description: str
    edge_type: str
    hub_score: float
    context_cost: int
    distance: int = 1


class SkillContextObject(BaseModel):
    metadata: SkillNodeMetadata
    layer_1: list[NeighborMetadata]
    layer_2: list[NeighborMetadata]
    payload: SkillPayload | None = None


class SkillCandidate(BaseModel):
    id: str
    name: str
    semantic_score: float
    hub_score: float