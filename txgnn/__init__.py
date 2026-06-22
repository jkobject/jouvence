"""Public TxGNN package exports.

Heavy training dependencies such as DGL and torch are imported lazily so data
loading utilities can be used in lightweight environments.
"""

from manage_db.kg_schema import (
    Credibility,
    EDGE_PARQUET_COLUMNS,
    TXDATA_NODE_TYPE_MAP,
    TXDATA_RELATION_MAP,
    NODE_TYPES,
    NODE_XREF_COLUMNS,
    RELATION_BY_NAME,
    RELATIONS,
    RELATIONS_BY_SOURCE,
    RELATIONS_BY_TARGET,
    XREF_BY_COLUMN,
    XREF_RESOLUTION,
    NodeType,
    NodeTypeInfo,
    Relation,
    RelationKind,
    XrefResolution,
    node_type_names,
    relation_names,
    relations_between,
)

from .KGLoader import KGLoader, KGValidationReport


def __getattr__(name: str):
    if name == "TxData":
        from .TxData import TxData

        return TxData
    if name == "TxGNN":
        from .TxGNN import TxGNN

        return TxGNN
    if name == "TxEval":
        from .TxEval import TxEval

        return TxEval
    raise AttributeError(f"module 'txgnn' has no attribute {name!r}")


__all__ = [
    "TxData",
    "TxGNN",
    "TxEval",
    "KGLoader",
    "KGValidationReport",
    "NodeType",
    "NodeTypeInfo",
    "NODE_TYPES",
    "Relation",
    "RelationKind",
    "RELATIONS",
    "RELATION_BY_NAME",
    "RELATIONS_BY_SOURCE",
    "RELATIONS_BY_TARGET",
    "Credibility",
    "XrefResolution",
    "XREF_RESOLUTION",
    "XREF_BY_COLUMN",
    "NODE_XREF_COLUMNS",
    "TXDATA_NODE_TYPE_MAP",
    "TXDATA_RELATION_MAP",
    "EDGE_PARQUET_COLUMNS",
    "relation_names",
    "node_type_names",
    "relations_between",
]
