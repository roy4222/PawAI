"""LangGraph build_graph() — Phase 1 primary cutover, 11-node graph.

Flow:
  input → safety_gate ─┬─→ output (when safety_hit=True)
                       └─→ context → env → memory → llm → validator → repair
                           → skill_gate → output
  output → trace → END

Conditional edge after safety_gate keeps the safety path short (skip LLM).
"""
from __future__ import annotations

from langgraph.graph import StateGraph, END

from .state import ConversationState
from .nodes.input_normalizer import input_normalizer
from .nodes.safety_gate import safety_gate
from .nodes.context_builder import context_builder
from .nodes.env_builder import env_builder
from .nodes.memory_builder import memory_builder
from .nodes.llm_decision import llm_decision
from .nodes.json_validator import json_validator
from .nodes.response_repair import response_repair
from .nodes.skill_policy_gate import skill_policy_gate
from .nodes.output_builder import output_builder
from .nodes.trace_emitter import trace_emitter


def _route_after_safety(state: ConversationState) -> str:
    return "output" if state.get("safety_hit") else "context"


def build_graph():
    g = StateGraph(ConversationState)

    g.add_node("input", input_normalizer)
    g.add_node("safety_gate", safety_gate)
    g.add_node("context", context_builder)
    g.add_node("env", env_builder)
    g.add_node("memory", memory_builder)
    g.add_node("llm", llm_decision)
    g.add_node("validator", json_validator)
    g.add_node("repair", response_repair)
    g.add_node("skill_gate", skill_policy_gate)
    g.add_node("output", output_builder)
    g.add_node("trace", trace_emitter)

    g.set_entry_point("input")
    g.add_edge("input", "safety_gate")
    g.add_conditional_edges(
        "safety_gate",
        _route_after_safety,
        {"output": "output", "context": "context"},
    )
    g.add_edge("context", "env")
    g.add_edge("env", "memory")
    g.add_edge("memory", "llm")
    g.add_edge("llm", "validator")
    g.add_edge("validator", "repair")
    g.add_edge("repair", "skill_gate")
    g.add_edge("skill_gate", "output")
    g.add_edge("output", "trace")
    g.add_edge("trace", END)

    return g.compile()
