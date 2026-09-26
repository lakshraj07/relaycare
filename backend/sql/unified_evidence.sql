-- Unravel unified per-variant evidence view.
--
-- One row per GRCh38 ClinVar variant in the Lynch-gene slice, with the
-- population-frequency (gnomAD) and in-silico (AlphaMissense) evidence streams
-- joined on the canonical VCF coordinate (chromosome, position, ref, alt). This
-- is the table build_evidence_ledger() reads to assemble an ACMG ledger for the
-- Bayesian engine: ClinVar is the anchor (assertion + review stars), gnomAD
-- feeds PM2 / BS1 / BA1, AlphaMissense feeds PP3 / BP4.
--
-- All three feeds arrive via Fivetran GCS connectors (clinvar / gnomad /
-- alphamissense). AlphaMissense has one row per transcript, so it is deduped to
-- the highest-scoring transcript per coordinate. review_stars decodes ClinVar's
-- review_status into the 0-4 star scale that governs how much the Adjudicator
-- trusts the assertion (the 1-star trap vs the 3-star expert panel).
--
-- Apply:  bq query --project_id=unravel-ra --use_legacy_sql=false < backend/sql/unified_evidence.sql

CREATE OR REPLACE VIEW `unravel-ra.evidence.variant_evidence` AS
WITH am AS (
  SELECT
    chromosome, position, reference_allele, alternate_allele,
    am_pathogenicity, am_class
  FROM `unravel-ra.alphamissense.scores`
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY chromosome, position, reference_allele, alternate_allele
    ORDER BY am_pathogenicity DESC
  ) = 1
),
gnomad AS (
  SELECT
    chromosome, position, reference_allele, alternate_allele,
    allele_count, allele_number, allele_frequency
  FROM `unravel-ra.gnomad.allele_frequency`
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY chromosome, position, reference_allele, alternate_allele
    ORDER BY allele_frequency DESC
  ) = 1
)
SELECT
  c.gene_symbol,
  c.chromosome,
  c.position_vcf                                   AS position,
  c.reference_allele_vcf                           AS reference_allele,
  c.alternate_allele_vcf                           AS alternate_allele,
  c.variation_id,
  c.name                                           AS clinvar_name,
  c.clinical_significance,
  c.clin_sig_simple,
  c.review_status,
  CASE
    WHEN c.review_status = 'practice guideline' THEN 4
    WHEN c.review_status = 'reviewed by expert panel' THEN 3
    WHEN c.review_status = 'criteria provided, multiple submitters, no conflicts' THEN 2
    WHEN c.review_status IN (
      'criteria provided, single submitter',
      'criteria provided, conflicting classifications',
      'criteria provided, conflicting interpretations of pathogenicity'
    ) THEN 1
    ELSE 0
  END                                              AS review_stars,
  c.number_submitters,
  c.last_evaluated,
  g.allele_frequency                               AS gnomad_af,
  g.allele_count                                   AS gnomad_ac,
  g.allele_number                                  AS gnomad_an,
  am.am_pathogenicity,
  am.am_class
FROM `unravel-ra.clinvar.variant_summary` c
LEFT JOIN gnomad g
  ON c.chromosome           = g.chromosome
 AND c.position_vcf         = g.position
 AND c.reference_allele_vcf = g.reference_allele
 AND c.alternate_allele_vcf = g.alternate_allele
LEFT JOIN am
  ON c.chromosome           = am.chromosome
 AND c.position_vcf         = am.position
 AND c.reference_allele_vcf = am.reference_allele
 AND c.alternate_allele_vcf = am.alternate_allele
WHERE c.assembly = 'GRCh38';
