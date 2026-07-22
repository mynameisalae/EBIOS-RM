"""Discovers every plugin under plugins/frameworks/ (see base.py for the contract).

Used by: org_context_form to pre-fill applicable_frameworks suggestions
(conception §12.4), and by db/loader.py to populate baseline_controls at
reference-db-loader startup (§13.3).
"""
