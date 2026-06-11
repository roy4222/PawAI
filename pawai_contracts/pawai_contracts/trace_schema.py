"""/brain/trace event schema — single source (Plan E, Roy ruling 2026-06-10 D5):
'Trace 的單一真相是 pawai_contracts schema + gateway JSONL。Brain 只負責說明自己
為什麼做/不做；Studio 只負責記錄與呈現；CLI 只負責讀取與匯出。'

decision_id chains one causal line: perception event → gate verdicts → plan →
skill_result. Emission: brain_node / interaction_executive (this plan);
conversation_graph joins later. Persistence: Studio gateway (separate plan).
ADDITIVE-ONLY: schema changes must stay backward-compatible (add fields, never
rename/remove)."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TraceKind(str, Enum):
    PERCEPTION_EVENT = "perception_event"
    CANDIDATE = "candidate"
    POLICY_DECISION = "policy_decision"
    PLAN_EMITTED = "plan_emitted"
    SKILL_RESULT = "skill_result"
    TTS_STATE = "tts_state"


class Verdict(str, Enum):
    ACCEPTED = "accepted"
    SUPPRESSED = "suppressed"
    BLOCKED = "blocked"


@dataclass
class TraceEvent:
    decision_id: str
    node: str                      # brain_node | interaction_executive | conversation_graph
    kind: TraceKind
    verdict: Verdict
    gate: str = ""                 # e.g. demo_phase / gesture_enabled / active_plan / tts_playing
    reason: str = ""               # e.g. phase:s3_object / cooldown:greet:Roy / banned_api:1301
    detail: dict[str, Any] = field(default_factory=dict)
    plan_id: str = ""
    ts: float = field(default_factory=time.time)
    v: int = 1

    def to_json(self) -> str:
        d = {
            "v": self.v, "ts": self.ts, "decision_id": self.decision_id,
            "node": self.node, "kind": self.kind.value, "verdict": self.verdict.value,
            "gate": self.gate, "reason": self.reason, "detail": self.detail,
        }
        if self.plan_id:
            d["plan_id"] = self.plan_id
        return json.dumps(d, ensure_ascii=False)


def make_suppressed(*, decision_id: str, node: str, gate: str, reason: str,
                    demo_phase: str = "", active_plan: str = "",
                    pending_confirm: str = "", cooldown_remaining_s: float | None = None,
                    source_summary: str = "") -> TraceEvent:
    """Roy-required suppressed payload: 被哪個 gate 擋 / 當時 demo_phase /
    active_plan 是誰 / pending_confirm 是誰 / cooldown 還剩多久 / 來源摘要."""
    return TraceEvent(
        decision_id=decision_id, node=node, kind=TraceKind.POLICY_DECISION,
        verdict=Verdict.SUPPRESSED, gate=gate, reason=reason,
        detail={
            "gate": gate, "reason": reason, "demo_phase": demo_phase,
            "active_plan": active_plan, "pending_confirm": pending_confirm,
            "cooldown_remaining_s": cooldown_remaining_s,
            "source_summary": source_summary,
        },
    )
