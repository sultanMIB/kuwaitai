from enum import Enum
from typing import Text

class VectorDBEnums(Enum):
    QDRANT = "QDRANT"
    PGVECTOR = "PGVECTOR"
class DistanceMethodEnums(Enum):
    COSINE ="cosine"
    DOT = "dot"


class PgVectorTableSchemeEnums(Enum):
    ID="id"
    VECTOR="vector"
    TEXT="text"
    METADATA="metadata"
    CHUNK_ID="chunk_id"
    _PREFIX="pgvector"

class PgVectorDistanceMethodEnums(Enum):
    COSINE="vector_cosine_ops"
    DOT="vector_12_ops"
class PgVectorIndexTypeEnums(Enum):
    IVFFLAT="ivfflat"
    HNSW="hnsw"
