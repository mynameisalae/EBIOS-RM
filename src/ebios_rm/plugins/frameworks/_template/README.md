# Adding a new law or standard

Copy this folder to `../<framework_id>/` (e.g. `hipaa/`, `pci_dss/`) and fill in both files.
No code changes are needed anywhere else — the reference-db-loader discovers
every folder with a `manifest.yaml` automatically (conception §12.5).

1. `manifest.yaml` — identity and legal nature of the referential.
2. `controls.json` — one row per control, matching `baseline_controls`
   (`src/ebios_rm/db/reference_schema.sql`). Use real, verified referential
   text only — never invented or paraphrased-as-if-official text (conception
   §2, anti-hallucination principle).
3. If the referential mixes security controls with purely legal provisions
   (financial penalties, mandatory notification, liability — like RGPD's
   Art. 83, conception §12.3), give those rows `covers_risk_category: []`
   and set `legal_impact_type` — they are automatically excluded from the
   workshop 4 relevance filter and instead feed the workshop 1 legal-impact
   assessment (§15.1).
