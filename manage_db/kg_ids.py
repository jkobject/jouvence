"""Identifier normalization helpers for KG node and edge endpoints."""

from __future__ import annotations

import re

# OpenTargets and OBO-derived exports commonly serialize ontology CURIEs with
# underscores (for example ``EFO_0000094``). The KG schema stores CURIEs with a
# colon separator. Keep the conversion deliberately syntax-only: this does not
# assert that the term is present in a given LaminDB/bionty source.
_UNDERSCORE_CURIE_RE = re.compile(
    r"^(EFO|MONDO|HP|OBA|GO|MP|NCIT|GSSO|DOID|CL|UBERON|Orphanet)_([A-Za-z0-9]+)$"
)


def normalize_ontology_curie(value: object) -> str | None:
    """Return a canonical CURIE string when *value* is a known ontology ID.

    ``None``/blank-ish values return ``None``. Known OpenTargets underscore
    forms are converted to colon CURIEs. Values outside the known syntax are
    returned unchanged after trimming.
    """

    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "<na>"}:
        return None
    match = _UNDERSCORE_CURIE_RE.match(text)
    if match:
        return f"{match.group(1)}:{match.group(2)}"
    return text


def normalize_disease_id(value: object) -> str | None:
    """Canonicalize disease-node IDs used by KG disease evidence paths."""

    return normalize_ontology_curie(value)


def bionty_disease_source_supports_ontology_id(ontology_id: str) -> bool:
    """Return whether the configured bionty Disease source can resolve an ID.

    Jouvence currently pins ``bt.Disease`` to MONDO. Missing disease records must
    be created only via bionty's source API, not by direct insertion of arbitrary
    EFO/OBA/HP/etc. IDs. A non-MONDO disease endpoint is therefore a registry
    blocker until an explicit EFO/OXO/custom-registry policy exists.
    """

    return ontology_id.startswith("MONDO:")
