from __future__ import annotations

import pandas as pd

from manage_db.credibility import (
    Credibility,
    Edge,
    EdgeEvidence,
    dedup_edges,
    merge_composed_path,
    score_credibility,
)


def _evidence(
    source: str,
    raw_score: float | None = None,
    datatype: str | None = None,
    paper_id: str | None = None,
    author_group_key: str | None = None,
) -> EdgeEvidence:
    return EdgeEvidence(
        source=source,
        paper_id=paper_id,
        author_group_key=author_group_key,
        raw_score=raw_score,
        datatype=datatype,
    )


def test_curated_db_source_returns_3() -> None:
    evidences = [_evidence("drugbank", raw_score=0.1, datatype=None)]
    assert score_credibility(evidences) == Credibility.ESTABLISHED_FACT


def test_curated_db_overrides_low_raw_score() -> None:
    evidences = [_evidence("chembl_indication", raw_score=0.05)]
    assert score_credibility(evidences) == Credibility.ESTABLISHED_FACT


def test_single_low_score_returns_1() -> None:
    evidences = [
        _evidence(
            "opentargets:rna_expression",
            raw_score=0.3,
            datatype="rna_expression",
            paper_id="PMID1",
            author_group_key="labA",
        )
    ]
    assert score_credibility(evidences) == Credibility.SINGLE_EVIDENCE


def test_high_score_genetic_returns_2() -> None:
    evidences = [
        _evidence(
            "opentargets:genetic_association",
            raw_score=0.9,
            datatype="genetic_association",
            paper_id="PMID2",
            author_group_key="labB",
        )
    ]
    assert score_credibility(evidences) == Credibility.MULTI_EVIDENCE


def test_two_distinct_author_groups_returns_2() -> None:
    evidences = [
        _evidence(
            "opentargets:europepmc",
            raw_score=0.6,
            datatype="literature",
            paper_id="PMID3",
            author_group_key="labA",
        ),
        _evidence(
            "opentargets:europepmc",
            raw_score=0.65,
            datatype="literature",
            paper_id="PMID4",
            author_group_key="labB",
        ),
    ]
    assert score_credibility(evidences) == Credibility.MULTI_EVIDENCE


def test_two_papers_same_author_group_returns_1() -> None:
    evidences = [
        _evidence(
            "opentargets:europepmc",
            raw_score=0.6,
            datatype="literature",
            paper_id="PMID3",
            author_group_key="labA",
        ),
        _evidence(
            "opentargets:europepmc",
            raw_score=0.65,
            datatype="literature",
            paper_id="PMID5",
            author_group_key="labA",
        ),
    ]
    assert score_credibility(evidences) == Credibility.SINGLE_EVIDENCE


def test_dedup_same_paper_returns_1() -> None:
    evidences = [
        _evidence(
            "opentargets:genetic_association",
            raw_score=0.4,
            datatype="genetic_association",
            paper_id="PMID6",
            author_group_key="labC",
        ),
        _evidence(
            "opentargets:genetic_association",
            raw_score=0.6,
            datatype="genetic_association",
            paper_id="PMID6",
            author_group_key="labC",
        ),
    ]
    assert score_credibility(evidences) == Credibility.SINGLE_EVIDENCE


def test_compose_path_credibility_min() -> None:
    edges_a_c: list[Edge] = [
        {
            "x_id": "A",
            "x_type": "gene",
            "y_id": "C",
            "y_type": "pathway",
            "relation": "gene_to_pathway",
            "display_relation": "direct",
            "source": "source_ac",
            "credibility": Credibility.ESTABLISHED_FACT,
        }
    ]
    edges_c_b: list[Edge] = [
        {
            "x_id": "C",
            "x_type": "pathway",
            "y_id": "B",
            "y_type": "disease",
            "relation": "pathway_to_disease",
            "display_relation": "direct",
            "source": "source_cb",
            "credibility": Credibility.SINGLE_EVIDENCE,
        }
    ]

    composed = merge_composed_path(edges_a_c, edges_c_b)
    assert composed[0]["credibility"] == Credibility.SINGLE_EVIDENCE
    assert composed[0]["display_relation"] == "via:pathway:C"
    assert composed[0]["source"] == "composed:source_ac+source_cb"


def test_dedup_edges_preserves_sort() -> None:
    df = pd.DataFrame(
        [
            {
                "x_id": "a",
                "y_id": "b",
                "relation": "rel1",
                "source": "opentargets:lit",
                "paper_id": "PMID10",
                "author_group_key": "labA",
                "raw_score": 0.5,
                "datatype": "literature",
                "credibility": 1,
            },
            {
                "x_id": "a",
                "y_id": "b",
                "relation": "rel1",
                "source": "opentargets:lit",
                "paper_id": "PMID10",
                "author_group_key": "labA",
                "raw_score": 0.6,
                "datatype": "literature",
                "credibility": 1,
            },
            {
                "x_id": "a",
                "y_id": "c",
                "relation": "rel2",
                "source": "drugbank",
                "paper_id": None,
                "author_group_key": None,
                "raw_score": None,
                "datatype": None,
                "credibility": 3,
            },
        ]
    )

    deduped = dedup_edges(df)
    assert list(deduped["x_id"]) == ["a", "a"]
    assert list(deduped["y_id"]) == ["b", "c"]
    assert list(deduped["relation"]) == ["rel1", "rel2"]
    assert deduped.iloc[0]["source"] == "opentargets:lit"
    assert deduped.iloc[0]["credibility"] == Credibility.SINGLE_EVIDENCE
    assert deduped.iloc[1]["credibility"] == Credibility.ESTABLISHED_FACT


def test_score_credibility_deterministic() -> None:
    evidences_a = [
        _evidence("opentargets:genetic_association", 0.8, "genetic_association", "PMID11", "labD"),
        _evidence("opentargets:europepmc", 0.4, "literature", "PMID12", "labE"),
    ]
    evidences_b = list(reversed(evidences_a))
    assert score_credibility(evidences_a) == score_credibility(evidences_b)
