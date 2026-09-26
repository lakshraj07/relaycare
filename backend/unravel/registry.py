"""The FHIR R4 patient registry (Firestore), and the seeded Lynch demo cohort.

Unravel watches the evidence commons on behalf of a clinic's real patients. That
clinic is modelled here as a registry of FHIR R4 resources in Firestore:

  - Patient                 the people (proband, at-risk relatives, cohort).
  - Observation             each carrier's variant, recorded with the
                            classification known AT TEST TIME (the registry's
                            memory, which is what goes stale).
  - FamilyMemberHistory     the proband's pedigree.

The gap Unravel closes is the distance between an Observation's *recorded*
classification and the *current* evidence. detect_reclassifications() diffs the
two; build_evidence_ledger() + the Adjudicator decide whether the change is real
and actionable.

The seeded cohort centres on Diane Marchetti, who carries MLH1 c.114C>G
(p.Asn38Lys), recorded as a VUS at her 2019 colorectal-cancer work-up. ClinVar
has since reclassified that variant to Pathogenic (3-star, expert panel), but the
news never reached Diane's family. The cohort also contains three "silent Dianes"
carrying the same variant, a deceased carrier (for the Steward's ethics branch),
a 1-star "trap" carrier whose tempting variant must be withheld, and benign /
unrelated cohort filler. The patients are a deliberately mixed, fictional cohort.
Every variant is a real ClinVar/Lynch variant present in the evidence warehouse,
so the registry and the science line up.

Genomic variants are stored on the Observation as a single component (LOINC
81252-9) carrying the canonical `chrom-pos-ref-alt` GRCh38 id, so the agent tools
can reconstruct a VariantKey without parsing HGVS.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .evidence import VariantKey

PROJECT = "unravel-ra"
COLLECTIONS = ("Patient", "Observation", "FamilyMemberHistory")

LOINC = "http://loinc.org"
V3_ROLE = "http://terminology.hl7.org/CodeSystem/v3-RoleCode"
RELATIVE_OF_URL = "https://unravel.health/fhir/relative-of"
ANCESTRY_URL = "https://unravel.health/fhir/ancestry"

# Ancestries well represented in AlphaMissense's training data. A carrier of any
# other ancestry triggers the predictor down-weighting (see evidence.py).
WELL_REPRESENTED_ANCESTRIES = {"European"}


# --- variant specs (all real, all in the warehouse) ----------------------------


@dataclass(frozen=True)
class VariantSpec:
    gid: str           # canonical GRCh38 id "chrom-pos-ref-alt"
    gene: str
    hgvs_c: str
    hgvs_p: str
    current: str       # current ClinVar classification (for narration)

    @property
    def key(self) -> VariantKey:
        chrom, pos, ref, alt = self.gid.split("-")
        return VariantKey(chrom, int(pos), ref, alt)


HERO = VariantSpec("3-36993661-C-G", "MLH1", "c.114C>G", "p.Asn38Lys", "Pathogenic")
TRAP = VariantSpec("3-37001040-G-A", "MLH1", "c.293G>A", "p.Gly98Asp",
                   "Conflicting classifications of pathogenicity")
MSH2_LP = VariantSpec("2-47478312-G-C", "MSH2", "c.2251G>C", "p.Gly751Arg", "Likely pathogenic")
MLH1_BENIGN = VariantSpec("3-37012077-A-G", "MLH1", "c.655A>G", "p.Ile219Val", "Benign")
MSH6_BENIGN = VariantSpec("2-47783349-G-A", "MSH6", "c.116G>A", "p.Gly39Glu", "Benign")
EPCAM_BENIGN = VariantSpec("2-47373967-T-C", "EPCAM", "c.344T>C", "p.Met115Thr", "Benign")


# --- FHIR builders -------------------------------------------------------------


RECONTACT_URL = "https://unravel.health/fhir/recontact-status"


def _patient(pid, family, given, gender, birth, *, deceased=False,
             role=None, relative_of=None, relationship=None, conditions=None,
             email=None, phone=None, recontact="not contacted"):
    res = {
        "resourceType": "Patient",
        "id": pid,
        "name": [{"family": family, "given": [given]}],
        "gender": gender,
        "birthDate": birth,
        "deceasedBoolean": deceased,
    }
    telecom = []
    if email:
        telecom.append({"system": "email", "value": email})
    if phone:
        telecom.append({"system": "phone", "value": phone})
    if telecom:
        res["telecom"] = telecom
    extensions = [{"url": RECONTACT_URL, "valueString": recontact}]
    if role:
        extensions.append({"url": "https://unravel.health/fhir/role", "valueString": role})
    if relative_of:
        extensions.append({
            "url": RELATIVE_OF_URL,
            "extension": [
                {"url": "proband", "valueReference": {"reference": f"Patient/{relative_of}"}},
                {"url": "relationship", "valueString": relationship or "relative"},
            ],
        })
    if extensions:
        res["extension"] = extensions
    if conditions:
        res["_conditions"] = conditions  # convenience, not strict FHIR
    return res


def _observation(oid, patient_id, variant: VariantSpec, recorded_class, recorded_date):
    return {
        "resourceType": "Observation",
        "id": oid,
        "status": "final",
        "category": [{"coding": [{
            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
            "code": "laboratory", "display": "Laboratory",
        }]}],
        "code": {"coding": [{"system": LOINC, "code": "69548-6",
                             "display": "Genetic variant assessment"}]},
        "subject": {"reference": f"Patient/{patient_id}"},
        "effectiveDateTime": recorded_date,
        "valueCodeableConcept": {"coding": [{"system": LOINC, "code": "LA9633-4",
                                             "display": "Present"}]},
        "component": [
            _comp("48018-6", "Gene studied", variant.gene),
            _comp("48004-6", "DNA change c.HGVS", variant.hgvs_c),
            _comp("48005-3", "Amino acid change p.HGVS", variant.hgvs_p),
            _comp("81252-9", "Genomic DNA change (gNomen)", variant.gid),
            _comp("53037-8", "Genetic variation clinical significance", recorded_class),
        ],
    }


def _comp(code, display, value):
    return {
        "code": {"coding": [{"system": LOINC, "code": code, "display": display}]},
        "valueString": value,
    }


def _family_history(fid, proband_id, relationship_code, relationship_display,
                    *, deceased=False, condition=None, onset_age=None):
    res = {
        "resourceType": "FamilyMemberHistory",
        "id": fid,
        "status": "completed",
        "patient": {"reference": f"Patient/{proband_id}"},
        "relationship": {"coding": [{"system": V3_ROLE, "code": relationship_code,
                                     "display": relationship_display}]},
        "deceasedBoolean": deceased,
    }
    if condition:
        c = {"code": {"text": condition}}
        if onset_age is not None:
            c["onsetAge"] = {"value": onset_age, "unit": "yr",
                             "system": "http://unitsofmeasure.org", "code": "a"}
        res["condition"] = [c]
    return res


# --- the seeded cohort ---------------------------------------------------------


def build_resources() -> dict[str, list[dict]]:
    """Construct every registry resource. Pure data; no Firestore needed."""
    patients: list[dict] = []
    observations: list[dict] = []
    histories: list[dict] = []

    # 1) The Marchetti family (the hero case).
    patients.append(_patient(
        "diane-marchetti", "Marchetti", "Diane", "female", "1971-04-12",
        role="proband", conditions=["Colorectal cancer (dx 2019, age 48)"],
        email="diane.marchetti@example.com", phone="+1-415-555-0142"))
    observations.append(_observation(
        "obs-diane", "diane-marchetti", HERO, "Uncertain significance", "2019-03-15"))
    # at-risk relatives, untested (Marco has no email on file -> shows the contact gap)
    patients.append(_patient("laura-marchetti", "Marchetti", "Laura", "female", "1968-09-02",
                             relative_of="diane-marchetti", relationship="sister",
                             email="laura.marchetti@example.com"))
    patients.append(_patient("sofia-marchetti", "Marchetti", "Sofia", "female", "1998-06-20",
                             relative_of="diane-marchetti", relationship="daughter",
                             email="sofia.m@example.com", phone="+1-415-555-0188"))
    patients.append(_patient("marco-marchetti", "Marchetti", "Marco", "male", "2001-11-30",
                             relative_of="diane-marchetti", relationship="son"))
    histories.append(_family_history("fmh-diane-mother", "diane-marchetti", "MTH", "mother",
                                     deceased=True, condition="Colorectal cancer", onset_age=47))
    histories.append(_family_history("fmh-diane-aunt", "diane-marchetti", "MAUNT",
                                     "maternal aunt", condition="Endometrial cancer", onset_age=52))

    # 2) Mei Tanaka: the same hero variant as Diane, recorded VUS, never
    #    recontacted. East Asian ancestry, so the predictor down-weighting (equity)
    #    arm runs on identical evidence to Diane. Her own family makes the cascade
    #    real on the second arm too.
    patients.append(_patient(
        "mei-tanaka", "Tanaka", "Mei", "female", "1965-02-11",
        role="proband", conditions=["Colorectal cancer (dx 2017, age 52)"],
        email="mei.tanaka@example.com", phone="+1-415-555-0173"))
    observations.append(_observation(
        "obs-mei-tanaka", "mei-tanaka", HERO, "Uncertain significance", "2017-08-01"))
    patients.append(_patient("kenji-tanaka", "Tanaka", "Kenji", "male", "1992-03-17",
                             relative_of="mei-tanaka", relationship="son",
                             email="kenji.tanaka@example.com"))
    patients.append(_patient("aiko-tanaka", "Tanaka", "Aiko", "female", "1968-07-29",
                             relative_of="mei-tanaka", relationship="sister"))
    histories.append(_family_history("fmh-mei-mother", "mei-tanaka", "MTH", "mother",
                                     deceased=True, condition="Colorectal cancer", onset_age=55))

    # 3) Deceased carrier (Steward ethics branch) with a living at-risk child.
    patients.append(_patient("thomas-nguyen", "Nguyen", "Thomas", "male", "1952-07-19",
                             deceased=True, role="proband",
                             conditions=["Colorectal cancer (deceased 2021)"]))
    observations.append(_observation("obs-thomas-nguyen", "thomas-nguyen", MSH2_LP,
                                     "Uncertain significance", "2015-04-10"))
    patients.append(_patient("david-nguyen", "Nguyen", "David", "male", "1986-03-08",
                             relative_of="thomas-nguyen", relationship="son",
                             email="david.nguyen@example.com"))
    histories.append(_family_history("fmh-thomas-sister", "thomas-nguyen", "SIS", "sister",
                                     condition="Endometrial cancer", onset_age=58))

    # 4) The 1-star trap carrier: a tempting low-confidence assertion that must be
    #    withheld. A daughter is at risk, which is exactly why withholding a thin
    #    claim (rather than alarming the family) is the careful call.
    patients.append(_patient("eric-larsson", "Larsson", "Eric", "male", "1975-10-02",
                             role="proband", conditions=["Colorectal cancer (dx 2018, age 43)"],
                             email="eric.larsson@example.com"))
    observations.append(_observation("obs-eric-larsson", "eric-larsson", TRAP,
                                     "Uncertain significance", "2018-11-22"))
    patients.append(_patient("anna-larsson", "Larsson", "Anna", "female", "2003-05-14",
                             relative_of="eric-larsson", relationship="daughter"))
    histories.append(_family_history("fmh-eric-father", "eric-larsson", "FTH", "father",
                                     deceased=True, condition="Colorectal cancer", onset_age=61))

    # 5) Grace Mensah: a recorded VUS that the evidence has since reclassified
    #    BENIGN, the opposite arm. African ancestry. The right action is
    #    reassurance and closing surveillance, not an alarm.
    patients.append(_patient("grace-mensah", "Mensah", "Grace", "female", "1969-06-18",
                             role="proband", conditions=["Polyp surveillance (since 2016)"],
                             email="grace.mensah@example.com"))
    observations.append(_observation("obs-grace-mensah", "grace-mensah", MLH1_BENIGN,
                                     "Uncertain significance", "2016-05-20"))
    patients.append(_patient("naomi-mensah", "Mensah", "Naomi", "female", "1995-11-08",
                             relative_of="grace-mensah", relationship="daughter",
                             email="naomi.mensah@example.com"))
    histories.append(_family_history("fmh-grace-aunt", "grace-mensah", "MAUNT",
                                     "maternal aunt", condition="Colorectal cancer", onset_age=64))

    # Ancestry (additive metadata only; variants/classifications unchanged). Drives
    # the predictor down-weighting: a carrier of an under-represented ancestry has
    # their AlphaMissense PP3 trusted one tier less. Mei Tanaka carries the SAME
    # HERO variant as Diane, so the two are a clean side-by-side demonstration.
    ancestry_map = {
        "diane-marchetti": "European", "laura-marchetti": "European",
        "sofia-marchetti": "European", "marco-marchetti": "European",
        "mei-tanaka": "East Asian", "kenji-tanaka": "East Asian", "aiko-tanaka": "East Asian",
        "thomas-nguyen": "East Asian", "david-nguyen": "East Asian",
        "eric-larsson": "European", "anna-larsson": "European",
        "grace-mensah": "African", "naomi-mensah": "African",
    }
    for p in patients:
        anc = ancestry_map.get(p["id"])
        if anc:
            p.setdefault("extension", []).append({"url": ANCESTRY_URL, "valueString": anc})

    return {"Patient": patients, "Observation": observations,
            "FamilyMemberHistory": histories}


def patient_ancestry(p: dict) -> str | None:
    for ext in p.get("extension", []):
        if ext.get("url") == ANCESTRY_URL:
            return ext.get("valueString")
    return None


def ancestry_underrepresented(p: dict) -> bool:
    """True if the patient's recorded ancestry is under-represented in the
    predictor's training data (so its score is trusted less)."""
    anc = patient_ancestry(p)
    return bool(anc) and anc not in WELL_REPRESENTED_ANCESTRIES


# --- Firestore I/O -------------------------------------------------------------


def get_client(project: str = PROJECT):
    from google.cloud import firestore
    return firestore.Client(project=project)


def seed(client=None, *, wipe: bool = True) -> dict[str, list[dict]]:
    """Write the cohort to Firestore (idempotent). Returns the resources written."""
    client = client or get_client()
    resources = build_resources()
    for collection in COLLECTIONS:
        coll = client.collection(collection)
        if wipe:
            for doc in coll.list_documents():
                doc.delete()
        for res in resources.get(collection, []):
            coll.document(res["id"]).set(res)
    return resources


def fetch_all(client=None) -> dict[str, list[dict]]:
    """Read every registry resource back from Firestore."""
    client = client or get_client()
    return {c: [d.to_dict() for d in client.collection(c).stream()] for c in COLLECTIONS}


# --- read helpers (used by the agent tools) ------------------------------------


def observation_variant(obs: dict) -> VariantKey | None:
    """Reconstruct the VariantKey from an Observation's 81252-9 component."""
    for comp in obs.get("component", []):
        for coding in comp.get("code", {}).get("coding", []):
            if coding.get("code") == "81252-9":
                gid = comp.get("valueString", "")
                parts = gid.split("-")
                if len(parts) == 4:
                    return VariantKey(parts[0], int(parts[1]), parts[2], parts[3])
    return None


def observation_field(obs: dict, code: str) -> str | None:
    for comp in obs.get("component", []):
        for coding in comp.get("code", {}).get("coding", []):
            if coding.get("code") == code:
                return comp.get("valueString")
    return None


def recorded_classification(obs: dict) -> str | None:
    return observation_field(obs, "53037-8")


def _relative_of(patient: dict) -> tuple[str, str] | None:
    """(proband_id, relationship) if this patient is recorded as a relative."""
    for ext in patient.get("extension", []):
        if ext.get("url", "").endswith("relative-of"):
            proband = relationship = None
            for sub in ext.get("extension", []):
                if sub.get("url") == "proband":
                    proband = sub.get("valueReference", {}).get("reference", "").split("/")[-1]
                elif sub.get("url") == "relationship":
                    relationship = sub.get("valueString")
            if proband:
                return proband, relationship or "relative"
    return None


def match_affected_patients(variant: VariantKey, *, data=None, client=None) -> dict:
    """Carriers of a variant plus their untested at-risk relatives.

    Returns {"variant", "carriers": [...], "relatives": [...]}. Each carrier
    carries patient + recorded classification; each relative carries patient +
    relationship + the carrier they descend from. This feeds the Cascade
    Coordinator's recontact drafting.
    """
    data = data or fetch_all(client)
    patients = {p["id"]: p for p in data["Patient"]}

    carrier_ids: list[str] = []
    for obs in data["Observation"]:
        if observation_variant(obs) == variant:
            carrier_ids.append(obs["subject"]["reference"].split("/")[-1])
    carrier_set = set(carrier_ids)

    carriers = []
    for cid in carrier_ids:
        p = patients.get(cid, {"id": cid})
        obs = next((o for o in data["Observation"]
                    if o["subject"]["reference"].endswith(cid)
                    and observation_variant(o) == variant), None)
        carriers.append({
            "patient": p,
            "recorded_classification": recorded_classification(obs) if obs else None,
            "deceased": p.get("deceasedBoolean", False),
        })

    relatives = []
    for p in patients.values():
        rel = _relative_of(p)
        if rel and rel[0] in carrier_set:
            relatives.append({"patient": p, "relationship": rel[1], "carrier_id": rel[0]})

    return {"variant": variant, "carriers": carriers, "relatives": relatives}


# --- contact + pedigree --------------------------------------------------------


def patient_email(p: dict) -> str | None:
    return next((t["value"] for t in p.get("telecom", []) if t.get("system") == "email"), None)


def patient_phone(p: dict) -> str | None:
    return next((t["value"] for t in p.get("telecom", []) if t.get("system") == "phone"), None)


def recontact_status(p: dict) -> str:
    for ext in p.get("extension", []):
        if ext.get("url") == RECONTACT_URL:
            return ext.get("valueString", "not contacted")
    return "not contacted"


def _person(p: dict, *, relationship: str, carrier: bool, recorded: str | None = None) -> dict:
    n = (p.get("name") or [{}])[0]
    return {
        "id": p.get("id"),
        "name": f"{' '.join(n.get('given', []))} {n.get('family', '')}".strip(),
        "relationship": relationship,
        "deceased": p.get("deceasedBoolean", False),
        "carrier": carrier,
        "recorded_classification": recorded,
        "email": patient_email(p),
        "phone": patient_phone(p),
        "recontact_status": recontact_status(p),
    }


def pedigree(seed_id: str, *, data=None, client=None) -> dict:
    """The family around a carrier: proband + at-risk relatives, with contact state.

    Given any carrier (or relative), find the proband they belong to and return the
    whole pedigree with each member's carrier status, contact details, and whether
    a recontact has been drafted/sent.
    """
    data = data or fetch_all(client)
    patients = {p["id"]: p for p in data["Patient"]}
    carrier_ids = {o["subject"]["reference"].split("/")[-1] for o in data["Observation"]}

    # resolve the proband: the seed itself if it is a proband/carrier, else its proband
    seed = patients.get(seed_id, {})
    rel = _relative_of(seed)
    proband_id = rel[0] if rel else seed_id
    proband = patients.get(proband_id, seed)
    proband_obs = next((o for o in data["Observation"]
                        if o["subject"]["reference"].endswith(proband_id)), None)

    members = [_person(proband, relationship="proband", carrier=proband_id in carrier_ids,
                       recorded=recorded_classification(proband_obs) if proband_obs else None)]
    fmh = [{"relationship": (h.get("relationship", {}).get("coding", [{}])[0].get("display")),
            "deceased": h.get("deceasedBoolean", False),
            "condition": (h.get("condition", [{}])[0].get("code", {}).get("text")
                          if h.get("condition") else None)}
           for h in data["FamilyMemberHistory"]
           if h.get("patient", {}).get("reference", "").endswith(proband_id)]

    for p in patients.values():
        r = _relative_of(p)
        if r and r[0] == proband_id:
            members.append(_person(p, relationship=r[1], carrier=p["id"] in carrier_ids))

    return {
        "proband_id": proband_id,
        "members": members,
        "history": fmh,
        "needs_contact": [m for m in members if m["relationship"] != "proband" and not m["carrier"]],
    }


def add_patient(*, given: str, family: str, gender: str = "unknown", birth: str = "",
                email: str | None = None, phone: str | None = None,
                relative_of: str | None = None, relationship: str | None = None,
                gene: str | None = None, hgvs_c: str | None = None, gid: str | None = None,
                hgvs_p: str | None = None, variant_query: str | None = None,
                ancestry: str | None = None,
                recorded_class: str = "Uncertain significance", client=None) -> dict:
    """Add a patient (and optional variant observation) to the Firestore registry.

    A free-text `variant_query` (rsID, gene:c.HGVS, or chrom-pos-ref-alt) is
    resolved to canonical GRCh38 coordinates + gene + protein change via Ensembl
    VEP, so a clinician can enter any variant they found online and have it flow
    through the same five-agent loop. Explicit gid/gene/hgvs_c (the one-click
    family variant) takes precedence when supplied.
    """
    client = client or get_client()
    pid = f"{given}-{family}".lower().replace(" ", "-")

    resolved = None
    if variant_query and not gid:
        from .live_evidence import normalize_query
        nv = normalize_query(variant_query)
        if nv is None:
            raise ValueError(
                f"Could not resolve variant '{variant_query}'. Try gene:c.HGVS "
                f"(e.g. BRCA1:c.5096G>A) or chrom-pos-ref-alt (e.g. 17-43063930-G-A).")
        gid, gene, hgvs_c, hgvs_p = nv.gid, nv.gene or gene, nv.hgvs_c or hgvs_c, nv.hgvs_p or hgvs_p
        resolved = {"gid": nv.gid, "gene": nv.gene, "hgvs_c": nv.hgvs_c,
                    "hgvs_p": nv.hgvs_p, "consequence": nv.consequence}
        # count this as a live lookup of the gene (drives the onboarding signal)
        from .onboarding import record_lookup
        record_lookup(nv.gene)

    role = "carrier" if gid else None
    patient = _patient(pid, family, given, gender or "unknown", birth or "1980-01-01",
                       role=role, relative_of=relative_of, relationship=relationship,
                       email=email, phone=phone)
    if ancestry:
        patient.setdefault("extension", []).append({"url": ANCESTRY_URL, "valueString": ancestry})
    client.collection("Patient").document(pid).set(patient)

    obs_written = None
    if gid and gene:
        spec = VariantSpec(gid, gene, hgvs_c or "", hgvs_p or "", recorded_class)
        obs = _observation(f"obs-{pid}", pid, spec, recorded_class, "2024-01-01")
        client.collection("Observation").document(f"obs-{pid}").set(obs)
        obs_written = f"obs-{pid}"

    return {"patient_id": pid, "observation": obs_written, "ok": True, "resolved": resolved}
