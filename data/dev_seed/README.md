# Dev seed — SAMPLE data only

`baseline_controls.dev.json` is a **small, clearly-labelled sample** used to
exercise Workshop 1 end-to-end during development (baseline assessment + the RGPD
security/legal split of conception §12.3/§15.1). It is **not** authoritative
referential text.

- The real framework plugins under `src/ebios_rm/plugins/frameworks/*/controls.json`
  stay **empty** until verified/licensed text is added (ISO 27001 is under a
  commercial licence; ANSSI/NIST/RGPD text must be transcribed from the real
  sources — never invented, conception §2).
- Every `description` here is prefixed `[SAMPLE]` so it can never be mistaken for
  the real control wording.

Load it into an in-memory reference DB via
`build_reference_db(":memory:", extra_controls=...)` — see `scripts/run_workshop1_dev.py`.
