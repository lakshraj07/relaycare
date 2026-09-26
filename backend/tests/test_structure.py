"""Tests for structural_context.

The neighbour-clustering geometry and enrichment math are tested deterministically
against a synthetic structure (no network). A guarded live test exercises the real
AlphaFold + AlphaMissense path for Diane's variant when the data is reachable.
"""

from pathlib import Path

import pytest

from unravel import structure
from unravel.structure import parse_residue, structural_context


def test_parse_residue():
    assert parse_residue("p.Asn38Lys") == 38
    assert parse_residue("p.Gly98Asp") == 98
    assert parse_residue(None) is None
    assert parse_residue("c.114C>G") is None


def test_neighbour_clustering_math(monkeypatch):
    # synthetic: res1 (the variant) is pathogenic and sits next to res2 (also
    # pathogenic, 3 A away); res3/res4 are benign and far (>8 A).
    am = structure._ResidueAM(uniprot="TEST", by_residue={1: 1.0, 2: 0.9, 3: 0.1, 4: 0.05})
    ca = {1: (0.0, 0.0, 0.0, 90.0), 2: (3.0, 0.0, 0.0, 88.0),
          3: (20.0, 0.0, 0.0, 70.0), 4: (21.0, 0.0, 0.0, 71.0)}
    monkeypatch.setattr(structure, "_load_residue_am", lambda gene: am)
    monkeypatch.setattr(structure, "_af_prediction", lambda u: {"pdbUrl": "http://x/model.pdb"})
    monkeypatch.setattr(structure, "_alphafold_pdb", lambda u: (Path("/dev/null"), "http://x"))
    monkeypatch.setattr(structure, "_parse_ca", lambda p: ca)

    sc = structural_context("TEST", residue=1, radius=8.0)
    assert sc.n_neighbours == 1                      # only res2 within 8 A
    assert sc.pathogenic_neighbours[0]["residue"] == 2
    assert sc.variant_mean_am == 1.0
    assert sc.variant_plddt == 90.0
    assert sc.neighbourhood_mean_am == pytest.approx(0.9)
    assert sc.global_mean_am == pytest.approx(0.5125)
    assert sc.enrichment > 1.5                        # pathogenic pocket
    assert len(sc.heatmap) == 4


def test_missing_residue_input_raises():
    with pytest.raises(ValueError):
        structural_context("MLH1")


@pytest.mark.parametrize("gene,hgvs_p,uniprot", [("MLH1", "p.Asn38Lys", "P40692")])
def test_live_alphafold_path(gene, hgvs_p, uniprot):
    if not structure._RESIDUE_AM.exists():
        pytest.skip("residue AlphaMissense file not staged")
    try:
        sc = structural_context(gene, hgvs_p=hgvs_p)
    except Exception as e:  # network/data unavailable
        pytest.skip(f"AlphaFold unreachable: {e}")
    assert sc.uniprot == uniprot
    assert sc.residue == 38
    assert sc.variant_mean_am > 0.9
    assert sc.enrichment > 1.2          # Diane's variant is in a pathogenic cluster
    assert sc.structure_url.endswith(".pdb")
    assert len(sc.heatmap) > 100
