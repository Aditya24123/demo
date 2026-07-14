from __future__ import annotations

"""Compatibility facade for the agent package.

Tests and older callers import private helpers / provider symbols from this
module path; keep those re-exports stable while implementation lives in
``catalyst.agent.*``.
"""

from catalyst.agent import (
    TOOL_DECLARATIONS,
    run_llm_agent_loop,
    run_local_agent_fallback,
    should_use_local_agent_fast_path,
)
from catalyst.agent.helpers import (  # noqa: F401
    _compact_tool_result,
    _dynamic_context,
    _empty_aggregate,
)
from catalyst.agent.tool_exec import _execute_tool  # noqa: F401
from catalyst.providers.gemini import generate_gemini_agent_turn  # noqa: F401
from catalyst.providers.openai_compatible import (  # noqa: F401
    generate_openai_compatible_text,
    stream_openai_compatible_text,
)

__all__ = [
    "TOOL_DECLARATIONS",
    "run_llm_agent_loop",
    "run_local_agent_fallback",
    "should_use_local_agent_fast_path",
    "_compact_tool_result",
    "_dynamic_context",
    "_empty_aggregate",
    "_execute_tool",
    "generate_gemini_agent_turn",
    "generate_openai_compatible_text",
    "stream_openai_compatible_text",
]
