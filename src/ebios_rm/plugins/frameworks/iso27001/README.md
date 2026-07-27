# ISO/IEC 27001 — control text not distributed

`controls.json` is **deliberately absent from this repository** and is gitignored.

ISO/IEC 27001 Annex A is a copyrighted standard licensed by AFNOR for exclusive,
non-collective internal use. Redistributing its control text — including in a git
repository — is not permitted (conception §12.2: *usage strictement interne,
jamais redistribué*).

The `manifest.yaml` is committed: it declares the framework, its version and its
licence status without reproducing any licensed content.

## To use ISO 27001 in a mission

Transcribe the Annex A controls from your organisation's own licensed copy into
`controls.json`, in the same format as the other framework plugins:

```json
[
  {
    "control_id": "ISO-A.5.1",
    "framework": "ISO27001",
    "description": "<text from your licensed copy>",
    "category": "organizational",
    "covers_risk_category": ["initial_access"],
    "framework_version": "2022",
    "legal_impact_type": null,
    "legal_impact_details": null
  }
]
```

Then rebuild the reference database:

```bash
PYTHONPATH=src python -m ebios_rm.db.loader
```

Without this file, ISO 27001 simply has no controls loaded. Declaring it in a
mission then stops the workshop with an explicit message rather than silently
reporting coverage that was never assessed — see the missing-controls stop in the
main README.

The freely reusable referentials (ANSSI guide d'hygiène, NIST CSF, RGPD) are
distributed with the project and need no such step.
