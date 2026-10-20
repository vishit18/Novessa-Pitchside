# 0001. Numbers are computed in code, language comes from models

Status: accepted

## Context

A model that is asked for a number will sometimes make one up, and on a live broadcast a wrong number is on screen before anyone can check it.

## Decision

Every number comes from the deterministic state engine (`backend/state/`). The agents receive computed numbers and explain them. They never compute one. A Verifier agent recomputes each claim in the Analyst's draft through the same code (`backend/agents/intel.py`). A claim that fails goes back to the Analyst once. If it fails again, the moment airs as a numbers-only card.

## Consequences

- What reaches the screen is checked, and the Control Room shows the check.
- The Verifier checks the English draft only. A translation can still change a clock or a name, which is a known gap (see the README).
- The state engine has to cover everything an agent might want to say, so some commentary is plainer than a model would write on its own.
