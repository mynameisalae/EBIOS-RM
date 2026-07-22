"""The framework-plugin contract.

A framework/standard/law plugin is a data-only folder under
plugins/frameworks/<framework_id>/ — no Python required for the common
case (conception §12.5 already requires zero code change to add a
referential). It contains exactly two files:

manifest.yaml
    id                          str, matches the folder name
    name                        str, display name
    framework_version           str, e.g. '2022', 'CSF 2.0', '2016/679'
    legal_nature                str, free text — licensing/publication status (conception §12.2)
    has_legal_impact_provisions bool, whether any control row sets legal_impact_type (§12.3)
    default_suggested           bool, pre-filled in org_context_form.applicable_frameworks (§12.4)

controls.json
    a JSON list of rows matching the baseline_controls schema
    (src/ebios_rm/db/reference_schema.sql): control_id, framework,
    description, category, covers_risk_category, framework_version,
    legal_impact_type, legal_impact_details.

registry.py discovers every folder with a manifest.yaml and feeds both the
intake form's suggested frameworks and the reference-db-loader — adding a
standard never touches this module, the loader, or any workshop.
"""
