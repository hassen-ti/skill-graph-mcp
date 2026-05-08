# server/models/edge.py
from enum import Enum


class EdgeType(str, Enum):
    REQUIRES = "requires"
    ENABLES = "enables"
    COLLABORATES_WITH = "collaborates_with"
    USES = "uses"
    PART_OF = "part_of"
    EXTENDS = "extends"


class EdgeDirection(str, Enum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"
    BOTH = "both"