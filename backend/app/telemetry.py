"""Send OpenTelemetry spans to Application Insights when it is configured.

Every model call already opens a span (`backend/agents/llm.py`). This turns them into something
you can look at: set `APPLICATIONINSIGHTS_CONNECTION_STRING` and the spans, with their agent
name, model deployment, latency and outcome, show up in the Azure portal under the resource's
Transaction search and Application map. With the variable unset, nothing is exported.
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
