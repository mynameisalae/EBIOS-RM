"""reference-db-loader entry point (conception §13.3).

Runs once per container start: applies reference_schema.sql, loads ATT&CK
data, then discovers every framework plugin under
src/ebios_rm/plugins/frameworks/ (see plugins/registry.py) and inserts each
one's controls.json into baseline_controls. Adding a new law or standard
means adding a plugin folder — this loader never hardcodes a framework
name (conception §12.5).
"""
