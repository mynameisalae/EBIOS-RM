"""estimate_cost_and_time — used at the workshop 3 count gate (§17) and before every workshop 4 retry (§18).

Atelier 4 fans out one LLM call per strategic scenario (§18), so the number of
scenarios approved at the end of atelier 3 *is* the size of the next atelier. The
gate exists to put that number in front of the auditor before it is paid for.

The thresholds are the ones §17 pins, and they are code: past the hard threshold
« lancer tout de même » is not offered at all, so no amount of insisting at the
prompt can order a run of forty scenarios by accident.
"""

from __future__ import annotations

from dataclasses import dataclass

SOFT_LIMIT = 6   # up to here, running is the normal answer
HARD_LIMIT = 12  # past here, the list must be reduced first — never "run anyway"

# What one atelier 4 sub-agent call costs. ponytail: flat per-call constants, the
# calibration knob for a workload nobody has measured yet. Real numbers are already
# being recorded per call in cost_calibration_log; average them here once a few
# atelier 4 runs exist, instead of guessing harder now.
TOKENS_IN_PER_SCENARIO = 6000
TOKENS_OUT_PER_SCENARIO = 1500
SECONDS_PER_SCENARIO = 25.0


@dataclass(frozen=True)
class Estimate:
    """What running atelier 4 on ``n`` scenarios would take, and what may be decided.

    ``options`` is the whole decision surface offered to the auditor: the CLI may
    only present what is in it (§17).
    """

    n: int
    llm_calls: int
    input_tokens: int
    output_tokens: int
    seconds: float
    options: tuple[str, ...]

    @property
    def minutes(self) -> float:
        return self.seconds / 60


def options_for(n: int) -> tuple[str, ...]:
    """The actions §17 allows at the count gate for ``n`` scenarios."""
    if n <= SOFT_LIMIT:
        return ("run", "cancel")
    if n <= HARD_LIMIT:
        return ("run_anyway", "merge", "choose_subset", "cancel")
    return ("merge", "choose_subset", "cancel")


def estimate_cost_and_time(n: int) -> Estimate:
    """Estimate atelier 4's fan-out for ``n`` strategic scenarios (§17, §18)."""
    return Estimate(
        n=n,
        llm_calls=n,
        input_tokens=n * TOKENS_IN_PER_SCENARIO,
        output_tokens=n * TOKENS_OUT_PER_SCENARIO,
        seconds=n * SECONDS_PER_SCENARIO,
        options=options_for(n),
    )
