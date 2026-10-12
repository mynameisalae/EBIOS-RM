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


# What one strategic scenario costs atelier 4 now that a scenario holds several modes
# opératoires (§18): one cheap enumeration call, then one full analysis per mode.
# ponytail: three modes per scenario is a guess — replace it from cost_calibration_log
# once a few real runs exist, like the constants above.
MODES_PER_SCENARIO = 3
TOKENS_IN_PER_ENUMERATION = 3000
TOKENS_OUT_PER_ENUMERATION = 500
SECONDS_PER_ENUMERATION = 10.0


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


def options_for(n: int) -> tuple[str, ...]:
    """The actions §17 allows at the count gate for ``n`` scenarios."""
    if n <= SOFT_LIMIT:
        return ("run", "cancel")
    if n <= HARD_LIMIT:
        return ("run_anyway", "merge", "choose_subset", "cancel")
    return ("merge", "choose_subset", "cancel")


def estimate_cost_and_time(n: int) -> Estimate:
    """Estimate ``n`` atelier 4 analyses — one mode opératoire each (§17, §18)."""
    return Estimate(
        n=n,
        llm_calls=n,
        input_tokens=n * TOKENS_IN_PER_SCENARIO,
        output_tokens=n * TOKENS_OUT_PER_SCENARIO,
        seconds=n * SECONDS_PER_SCENARIO,
        options=options_for(n),
    )


def estimate_workshop4(n_scenarios: int) -> Estimate:
    """What atelier 4 costs for ``n_scenarios`` strategic scenarios, modes included (§18).

    What the count gate of atelier 3 must show: a strategic scenario is no longer one
    call. It is one enumeration of its modes opératoires, then one analysis per mode —
    so the number the auditor rules on at that gate is the number of scenarios, and
    the price is several times that.
    """
    modes = n_scenarios * MODES_PER_SCENARIO
    analyses = estimate_cost_and_time(modes)
    return Estimate(
        n=n_scenarios,
        llm_calls=n_scenarios + modes,
        input_tokens=analyses.input_tokens + n_scenarios * TOKENS_IN_PER_ENUMERATION,
        output_tokens=analyses.output_tokens + n_scenarios * TOKENS_OUT_PER_ENUMERATION,
        seconds=analyses.seconds + n_scenarios * SECONDS_PER_ENUMERATION,
        options=options_for(n_scenarios),
    )
