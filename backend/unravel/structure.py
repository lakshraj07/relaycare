"""structural_context: the 3D structural story (AlphaFold + AlphaMissense).

The wow-in-seconds visual. For a variant residue this tool returns the real
AlphaFold structure (from the public AlphaFold DB) plus AlphaMissense
pathogenicity painted per residue, and it computes the variant's 3D pathogenic
neighbourhood: the residues physically nearest the variant in the folded protein
and how pathogenic AlphaMissense thinks that pocket is, compared with the protein
as a whole. A variant buried in a cluster of pathogenic residues is far more
concerning than the same score in an otherwise tolerant region; that spatial
context is the structural argument.

Deterministic supporting evidence, never the classifier (per the ACMG framing):
this feeds the viewer and informs the Adjudicator's narrative, it does not set
the posterior. Per-residue AlphaMissense comes from
scripts/fetch_alphamissense_residue.sh; the structure is fetched and cached from
AlphaFold DB. The structure_url is public so the React viewer can load the model
directly.
"""

from __future__ import annotations

import csv
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

import requests

import tempfile

_STAGING = Path(__file__).resolve().parent.parent / "_staging"
# Per-residue AlphaMissense ships as committed package data (so it is in the
# Cloud Run image); fall back to _staging for locally regenerated copies.
_PACKAGED_AM = Path(__file__).resolve().parent / "data" / "alphamissense_residue.csv"
_RESIDUE_AM = _PACKAGED_AM if _PACKAGED_AM.exists() else _STAGING / "alphamissense_residue.csv"
# AlphaFold models cache to _staging locally, or a writable temp dir on Cloud Run.
_AF_CACHE = (_STAGING / "alphafold") if _STAGING.exists() else Path(tempfile.gettempdir()) / "unravel-alphafold"
_AF_API_URL = "https://alphafold.ebi.ac.uk/api/prediction/{uniprot}"
_AF_ENTRY_URL = "https://alphafold.ebi.ac.uk/entry/{uniprot}"

_af_prediction_cache: dict[str, dict] = {}

DEFAULT_RADIUS = 8.0  # angstroms; CA-CA contact shell

_HGVS_P = re.compile(r"p\.[A-Za-z]{3}(\d+)")

# Reviewed human UniProt accessions for the genes we commonly see. Lets the 3D
# story work for any gene, not just the onboarded ones; unknown genes fall back
# to a live UniProt lookup. AlphaFold has no single model for the very largest
# proteins (e.g. BRCA2, ATM > ~2700 aa), which is reported, not errored.
_UNIPROT = {
    "MLH1": "P40692", "MSH2": "P43246", "MSH6": "P20585", "PMS2": "P54278", "EPCAM": "Q16553",
    "BRCA1": "P38398", "BRCA2": "P51587", "TP53": "P04637", "PALB2": "Q86YC2", "ATM": "Q13315",
    "CHEK2": "O96017", "PTEN": "P60484", "STK11": "Q15831", "CDH1": "P12830", "APC": "P25054",
    "MUTYH": "Q9UIF7", "RAD51C": "O43502", "RAD51D": "O75771", "BARD1": "Q99728", "NBN": "O60934",
}


def _resolve_uniprot(gene: str) -> str | None:
    """Reviewed human UniProt accession for a gene symbol (static map, then live)."""
    if gene in _UNIPROT:
        return _UNIPROT[gene]
    try:
        url = ("https://rest.uniprot.org/uniprotkb/search?query=gene_exact:"
               f"{gene}+AND+organism_id:9606+AND+reviewed:true&fields=accession&format=json&size=1")
        results = requests.get(url, timeout=20).json().get("results", [])
        return results[0]["primaryAccession"] if results else None
    except Exception:
        return None


def parse_residue(hgvs_p: str | None) -> int | None:
    """Residue number from a 3-letter p.HGVS, e.g. 'p.Asn38Lys' -> 38."""
    if not hgvs_p:
        return None
    m = _HGVS_P.search(hgvs_p)
    return int(m.group(1)) if m else None


@dataclass
class _ResidueAM:
    uniprot: str
    by_residue: dict[int, float]

    @property
    def global_mean(self) -> float:
        vals = self.by_residue.values()
        return sum(vals) / len(vals) if vals else 0.0


def _load_residue_am(gene: str) -> _ResidueAM | None:
    """Per-residue AlphaMissense for an onboarded gene, or None if we don't have
    it (a non-onboarded gene still gets the AlphaFold structure, just without the
    per-residue enrichment overlay)."""
    if not _RESIDUE_AM.exists():
        return None
    by_residue: dict[int, float] = {}
    uniprot = ""
    with _RESIDUE_AM.open() as fh:
        for row in csv.DictReader(fh):
            if row["gene"] != gene:
                continue
            uniprot = row["uniprot"]
            by_residue[int(row["residue"])] = float(row["mean_am"])
    if not by_residue:
        return None
    return _ResidueAM(uniprot=uniprot, by_residue=by_residue)


def _af_prediction(uniprot: str) -> dict | None:
    """AlphaFold DB prediction metadata (cached). Returns None when AlphaFold has
    no model for the protein (e.g. very large proteins like BRCA2/ATM) or on a
    transient error, so the caller can report 'no structure' rather than 500."""
    if uniprot not in _af_prediction_cache:
        try:
            resp = requests.get(_AF_API_URL.format(uniprot=uniprot), timeout=60)
            resp.raise_for_status()
            _af_prediction_cache[uniprot] = resp.json()[0]
        except Exception:
            return None
    return _af_prediction_cache.get(uniprot)


def _alphafold_pdb(uniprot: str) -> tuple[Path, str]:
    """Download + cache the AlphaFold model; return (path, public pdb url)."""
    _AF_CACHE.mkdir(parents=True, exist_ok=True)
    pdb_url = _af_prediction(uniprot)["pdbUrl"]
    path = _AF_CACHE / pdb_url.rsplit("/", 1)[-1]
    if not path.exists():
        resp = requests.get(pdb_url, timeout=120)
        resp.raise_for_status()
        path.write_text(resp.text)
    return path, pdb_url


def _parse_ca(pdb_path: Path) -> dict[int, tuple[float, float, float, float]]:
    """CA coordinates and pLDDT (b-factor) per residue from a PDB file."""
    ca: dict[int, tuple[float, float, float, float]] = {}
    for line in pdb_path.read_text().splitlines():
        if line.startswith("ATOM") and line[12:16].strip() == "CA":
            resnum = int(line[22:26])
            x, y, z = float(line[30:38]), float(line[38:46]), float(line[46:54])
            plddt = float(line[60:66])
            ca[resnum] = (x, y, z, plddt)
    return ca


def _distance(a, b) -> float:
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


@dataclass
class StructuralContext:
    gene: str
    uniprot: str
    residue: int
    structure_url: str
    structure_page: str
    structure_source: str
    variant_mean_am: float
    variant_plddt: float | None
    radius_angstrom: float
    global_mean_am: float
    neighbourhood_mean_am: float
    enrichment: float            # neighbourhood mean / global mean
    n_neighbours: int
    pathogenic_neighbours: list[dict] = field(default_factory=list)
    heatmap: list[dict] = field(default_factory=list)
    am_available: bool = True        # per-residue AlphaMissense enrichment overlay
    structure_available: bool = True  # AlphaFold has a model for this protein

    def summary(self) -> str:
        if not self.structure_available:
            return (
                f"{self.gene} residue {self.residue}: AlphaFold has no single 3D model for this "
                f"protein (it exceeds the prediction length limit), so structural context is not "
                f"shown. The verdict still rests on the population, in-silico and ClinVar evidence."
            )
        plddt = f"{self.variant_plddt:.0f}" if self.variant_plddt is not None else "n/a"
        if not self.am_available:
            return (
                f"{self.gene} residue {self.residue}: AlphaFold model loaded (variant pLDDT {plddt}; "
                f"{self.n_neighbours} 3D neighbours within {self.radius_angstrom:.0f} A). Per-residue "
                f"AlphaMissense enrichment is computed for onboarded genes; this gene is served live, "
                f"so the structure is shown without the enrichment overlay."
            )
        return (
            f"{self.gene} residue {self.residue}: AlphaMissense {self.variant_mean_am:.2f}, "
            f"pLDDT {plddt}. Its {self.n_neighbours} 3D neighbours within "
            f"{self.radius_angstrom:.0f} A average {self.neighbourhood_mean_am:.2f} "
            f"({self.enrichment:.1f}x the protein-wide {self.global_mean_am:.2f}), "
            f"a {'pathogenic cluster' if self.enrichment >= 1.2 else 'mixed region'}."
        )


def structural_context(
    gene: str,
    *,
    residue: int | None = None,
    hgvs_p: str | None = None,
    radius: float = DEFAULT_RADIUS,
    include_heatmap: bool = True,
) -> StructuralContext:
    """AlphaFold + AlphaMissense structural context for a variant residue."""
    residue = residue if residue is not None else parse_residue(hgvs_p)
    if residue is None:
        raise ValueError("provide residue or a parseable hgvs_p")

    am = _load_residue_am(gene)  # None for non-onboarded genes
    uniprot = am.uniprot if am else _resolve_uniprot(gene)

    def _bare(structure_ok: bool) -> StructuralContext:
        return StructuralContext(
            gene=gene, uniprot=uniprot or "", residue=residue,
            structure_url="", structure_page=_AF_ENTRY_URL.format(uniprot=uniprot) if uniprot else "",
            structure_source="", variant_mean_am=round(am.by_residue.get(residue, 0.0), 4) if am else 0.0,
            variant_plddt=None, radius_angstrom=radius,
            global_mean_am=round(am.global_mean, 4) if am else 0.0,
            neighbourhood_mean_am=0.0, enrichment=0.0, n_neighbours=0,
            am_available=bool(am), structure_available=structure_ok)

    if not uniprot:
        return _bare(False)
    pred = _af_prediction(uniprot)
    if pred is None:  # AlphaFold has no model for this protein (e.g. BRCA2, ATM)
        return _bare(False)

    pdb_path, pdb_url = _alphafold_pdb(uniprot)
    ca = _parse_ca(pdb_path)
    variant_ca = ca.get(residue)
    variant_plddt = variant_ca[3] if variant_ca else None

    neighbours: list[dict] = []
    if variant_ca:
        for resnum, coord in ca.items():
            if resnum == residue:
                continue
            d = _distance(variant_ca, coord)
            if d <= radius:
                neighbours.append({
                    "residue": resnum,
                    "distance": round(d, 2),
                    "mean_am": round(am.by_residue.get(resnum, 0.0), 4) if am else None,
                })
    neighbours.sort(key=lambda n: n["distance"])

    if am:
        global_mean = am.global_mean
        variant_am = am.by_residue.get(residue, 0.0)
        nb_mean = (sum(n["mean_am"] for n in neighbours) / len(neighbours)) if neighbours else 0.0
        enrichment = (nb_mean / global_mean) if global_mean else 0.0
        heatmap = ([{
            "residue": resnum, "mean_am": round(am.by_residue[resnum], 4),
            "plddt": round(ca[resnum][3], 1) if resnum in ca else None,
        } for resnum in sorted(am.by_residue)] if include_heatmap else [])
    else:
        global_mean = variant_am = nb_mean = enrichment = 0.0
        heatmap = []

    return StructuralContext(
        gene=gene,
        uniprot=uniprot,
        residue=residue,
        structure_url=pdb_url,
        structure_page=_AF_ENTRY_URL.format(uniprot=uniprot),
        structure_source="AlphaFold DB (model v4)",
        variant_mean_am=round(variant_am, 4),
        variant_plddt=round(variant_plddt, 1) if variant_plddt is not None else None,
        radius_angstrom=radius,
        global_mean_am=round(global_mean, 4),
        neighbourhood_mean_am=round(nb_mean, 4),
        enrichment=round(enrichment, 2),
        n_neighbours=len(neighbours),
        pathogenic_neighbours=neighbours,
        heatmap=heatmap,
        am_available=bool(am),
        structure_available=True,
    )
