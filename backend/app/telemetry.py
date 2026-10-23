"""Send OpenTelemetry spans to Application Insights when it is configured.

Every model call already opens a span (`backend/agents/llm.py`). This turns them into something
you can look at: set `APPLICATIONINSIGHTS_CONNECTION_STRING` and the spans, with their agent
name, model deployment, latency and outcome, show up in the Azure portal under the resource's
Transaction search and Application map. With the variable unset, nothing is exported.

Each model call also carries the OpenTelemetry GenAI attributes (`genai_attributes`), which is
what the Foundry portal's Traces view reads. Connect the same Application Insights resource
to the Foundry project (docs/02) and the agent calls appear there too. Prompts and answers are
never recorded, only names, models, timings and outcomes.
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger("pitchside.telemetry")


def setup_telemetry() -> bool:
    """Start exporting to Application Insights. Returns False if it is not configured."""
    conn = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not conn:
        return False
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(connection_string=conn, enable_live_metrics=False)
    except Exception:  # monitoring must never stop the broadcast
        log.exception("could not start Application Insights export")
        return False
    log.info("exporting traces to Application Insights")
    return True


def genai_attributes(agent: str, deployment: str) -> dict[str, str]:
    """GenAI semantic-convention attributes for one model call (opentelemetry.io, gen-ai)."""
    return {
        "gen_ai.operation.name": "chat",
        "gen_ai.provider.name": "azure.ai.openai",
        "gen_ai.system": "azure.ai.openai",  # older name, still read by some viewers
        "gen_ai.request.model": deployment,
        "gen_ai.agent.name": agent,
    }
