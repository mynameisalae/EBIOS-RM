"""Backwards-compatible re-export. The canonical Fact model lives in the domain
layer (conception §5, §14); it is re-exported here because the pipeline reads
as "mission context produces Facts".
"""

from ebios_rm.domain.fact import Fact, validate_extraction

__all__ = ["Fact", "validate_extraction"]
