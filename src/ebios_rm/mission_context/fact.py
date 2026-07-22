"""The Fact model — every assertion about the audited organization (conception §5).

Scope: only a field that asserts something about the organization becomes a
Fact; internal bookkeeping data stays a plain value (§5.2). source_quote is
mandatory and non-empty for any Fact of origin 'extraction' (§5.3) — enforced
in code before it ever reaches the auditor.
"""
