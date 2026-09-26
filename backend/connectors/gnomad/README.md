# Custom Fivetran connector: gnomAD (Connector SDK)

A real "host Python on Fivetran" connector. Instead of staging CSVs to GCS and
syncing the files, `connector.py` pulls gnomAD v4 joint allele frequencies for the
hereditary-cancer genes **directly from the gnomAD GraphQL API** and upserts them
into the destination. Fivetran runs, schedules and incrementally syncs it.

It mirrors the schema of the GCS-based `gnomad.allele_frequency` table, so the
curated `evidence.variant_evidence` view joins it identically.

## Local test

```bash
cd backend/connectors/gnomad
fivetran debug --configuration configuration.json
```

Verified: a debug run synced **3,755 EPCAM variants** from the gnomAD API into the
local tester warehouse (`SYNC SUCCEEDED`, 3,755 upserts). Set `configuration.json`
`genes` to a comma-separated list, or leave it empty to sync all five Lynch genes.

## Deploy to Fivetran

```bash
fivetran deploy --api-key <KEY> --destination <DESTINATION> --connection gnomad_sdk
```

This pushes the Python connector to Fivetran, which then runs it on a schedule
(no GCS intermediate). The synced table lands in BigQuery and the view picks it up.
