"""Contracts between the agents (docs/04). Every LLM output is validated against one of these."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from backend.app.overlay import Persona, Slot
from backend.state.models import Moment

Decision = Literal["air", "merge_with", "hold", "drop"]
Status = Literal["verified", "fallback", "dropped"]


class ProducerItem(BaseModel):
    """What the Producer decided for one candidate moment."""

    moment_id: str
    decision: Decision
    priority: int = Field(ge=0, le=100, default=50)
    slot: Slot = "lower_third"
    duration_s: float = Field(ge=2, le=15, default=7.0)
    personas: list[Persona] = Field(default_factory=lambda: ["analyst", "casual"])  # type: ignore[arg-type]
    merge_with: str | None = None
    brief: str = Field(default="", description="One line for the Analyst: what to explain.")
    reason: str = ""


class ProducerDecision(BaseModel):
    items: list[ProducerItem]


class Claim(BaseModel):
    """One checkable statement. The Verifier recomputes `value` from the match data."""

    text: str
    metric: str
    value: float
    team: str | None = None
    player_id: str | None = None
    t_from: float | None = Field(default=None, description="Window start, match seconds")
    t_to: float | None = Field(default=None, description="Window end, match seconds")


class AnalystOutput(BaseModel):
    headline: str = Field(max_length=90, description="At most 6 words")
    why: str = Field(max_length=420, description="One sentence, at most 30 words.")
    claims: list[Claim] = Field(min_length=1, max_length=4)


class ClaimCheck(BaseModel):
    claim_index: int
    status: Literal["approved", "rejected"]
    claimed: float
    measured: float | None = None
    reason: str = ""


class Verdict(BaseModel):
    overall: Literal["approved", "rejected"]
    checks: list[ClaimCheck]
    stray_numbers: list[float] = Field(default_factory=list)
    reason: str = ""


class Variant(BaseModel):
    """Text for one persona. Length limits are enforced by trimming, not by rejecting."""

    headline: str = Field(description="At most 6 words")
    body: str
    commentary: str = Field(description="One spoken line for the Voice agent, under 25 words.")


class NarratorOutput(BaseModel):
    variants: dict[Persona, Variant]


class RecapOutput(BaseModel):
    """What the Recap Editor writes. The facts behind it are computed, not written."""

    headline: str
    paragraphs: list[str] = Field(min_length=1, max_length=4)
    highlights: list[str] = Field(
        min_length=3, max_length=9, description="Short lines for a 60 second highlights read"
    )


class Recap(BaseModel):
    match_id: str
    kind: Literal["half_time", "full_time"]
    persona: Persona
    lang: str
    status: Literal["verified", "fallback"]
    translation: str = "english"
    t_match: float
    output: RecapOutput
    facts: dict[str, object]
    trail: list[str] = Field(default_factory=list)


class Localised(BaseModel):
    """Persona variants in one language, and how they were made."""

    lang: str
    status: Literal["english", "translated", "polished", "llm", "unavailable"]
    variants: dict[Persona, Variant]
    note: str = ""


class LocalisedLines(BaseModel):
    """What the model returns when it polishes or translates a list of lines."""

    lines: list[str]


class Brief(BaseModel):
    """Message from the Producer to the Analyst (and back, with feedback, after a rejection)."""

    moment: Moment
    item: ProducerItem
    attempt: int = 1
    feedback: str | None = None
    previous: AnalystOutput | None = None
    trail: list[str] = Field(default_factory=list, description="Audit trail, oldest first")


class Checked(BaseModel):
    """Message from the Analyst to the Verifier."""

    brief: Brief
    analysis: AnalystOutput | None
    analyst_failed: bool = False


class Verified(BaseModel):
    """Message from the Verifier onwards."""

    brief: Brief
    analysis: AnalystOutput | None
    verdict: Verdict | None
    final: bool = False


class Aired(BaseModel):
    """What leaves the workflow for one moment: the text per persona plus its audit trail."""

    moment_id: str
    status: Status
    item: ProducerItem
    analysis: AnalystOutput | None = None
    variants: dict[Persona, Variant] = Field(default_factory=dict)
    trail: list[str] = Field(default_factory=list)


ToolName = Literal["state_now", "player", "team_recent", "compare", "leaders", "moments"]


class ToolCall(BaseModel):
    """One lookup the Scout wants run. Code runs it; the model only sees what it asked for."""

    tool: ToolName
    team: str | None = Field(default=None, description="Club name or code, for team tools")
    player: str | None = Field(default=None, description="Player name as the viewer wrote it")
    metric: str | None = Field(default=None, description="For leaders and compare")
    minutes: int | None = Field(default=None, ge=1, le=90, description="Window length")


class AskPlan(BaseModel):
    """What the Scout decided: the lookups that answer the question, or why not to answer."""

    on_topic: bool = Field(description="False for anything that is not about this match")
    calls: list[ToolCall] = Field(default_factory=list, max_length=3)
    reason: str = ""


class AskDraft(BaseModel):
    """The Analyst's answer to a viewer question, written only from the evidence rows."""

    answer: str = Field(max_length=480, description="Two or three sentences, numbers copied.")
    used: list[str] = Field(default_factory=list, description="Keys of the evidence rows used")


class Evidence(BaseModel):
    key: str
    label: str
    value: float


class AskAnswer(BaseModel):
    """What the viewer gets back. Every number in `answer` is in `evidence`."""

    question: str
    answer: str
    status: Literal["verified", "numbers_only", "declined", "unavailable"]
    lang: str
    translation: str = "english"
    t_match: float
    clock: str
    evidence: list[Evidence] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list, description="Text facts, like key moments")
    tools: list[str] = Field(default_factory=list)
    trail: list[str] = Field(default_factory=list)
