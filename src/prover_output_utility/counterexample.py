# SPDX-FileCopyrightText: 2026 Certora Ltd.
#
# SPDX-License-Identifier: GPL-3.0-only

"""
Render a violated rule's counterexample as compact XML.

A rule's raw output (``prover-cli --calltrace rule_output_<k>.json``) holds the failing assertion,
its source location, and the call trace as a tree of frames. The rendering keeps the frames a
reader needs, substitutes each frame's values into its message, and leaves out the frames every
trace of a chain carries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

#: The prover writes a frame's message as a format template: literal text with ``'{n}'`` standing in
#: for the n-th of the message's ``arguments``.
_PLACEHOLDER = re.compile(r"'\{(\d+)\}'")


def _frame(message: Dict[str, Any]) -> str:
    """A frame's identity: its message template with every value replaced by ``{}``.

    A counterexample's values live in ``arguments``, never in ``text``, so frames emitted from the
    same site share this string whatever values they took.
    """
    return _PLACEHOLDER.sub("{}", message.get("text", ""))


def _render_message(message: Dict[str, Any]) -> str:
    """The message template with this counterexample's values substituted for its placeholders."""
    arguments = message.get("arguments") or []

    def value(placeholder: re.Match[str]) -> str:
        index = int(placeholder.group(1))
        return f"'{arguments[index].get('value')}'" if index < len(arguments) else placeholder.group(0)

    return _PLACEHOLDER.sub(value, message.get("text", ""))


@dataclass(frozen=True)
class TraceShape:
    """Which call-trace frames are worth rendering for one chain.

    Frames are named by their message template (``{}`` where a value goes). ``dropped`` removes a
    frame and everything under it. ``elided`` keeps the frame and replaces its subtree with a count.
    """

    dropped: frozenset[str] = frozenset()
    elided: frozenset[str] = frozenset()


#: Frames every chain's traces carry and no counterexample needs.
_GENERIC_NOISE = frozenset({"Setup", "Global State"})

GENERIC_TRACE = TraceShape(dropped=_GENERIC_NOISE)

EVM_TRACE = TraceShape(
    dropped=_GENERIC_NOISE | {"Evaluate branch condition", "unknown loop source code"},
)

#: Solana traces are dominated by account materialization under
#: ``cvlr_deserialize_nondet_accounts``. That subtree is elided rather than dropped, so a reader can
#: tell setup happened and how much of it was hidden. ``unknown loop source code`` is kept: a
#: loop-unwinding violation nests its failure under it.
SOLANA_TRACE = TraceShape(
    dropped=_GENERIC_NOISE | {"__rust_alloc: {}", "CVT_alloc_slice: {}"},
    elided=frozenset({"cvlr_solana::layout::cvlr_deserialize_nondet_accounts(...)"}),
)

TRACE_SHAPES: Dict[str, TraceShape] = {
    "evm": EVM_TRACE,
    "solana": SOLANA_TRACE,
    "soroban": GENERIC_TRACE,
}


def _descendants(node: Dict[str, Any]) -> int:
    return sum(1 + _descendants(child) for child in node.get("childrenList") or [])


def calltrace_to_xml(node: Dict[str, Any], shape: TraceShape) -> str:
    """Render one call-trace node and the children ``shape`` keeps."""
    parts = [f"<message>{_render_message(node.get('message') or {})}</message>"]
    for child in node.get("childrenList") or []:
        message = child.get("message") or {}
        frame = _frame(message)
        if frame in shape.dropped:
            continue
        if frame in shape.elided:
            parts.append(
                f"<child><message>{_render_message(message)}</message>"
                f"<elided>{_descendants(child)} frames of setup</elided></child>"
            )
            continue
        parts.append(f"<child>{calltrace_to_xml(child, shape)}</child>")
    return "".join(parts)


def render_counterexample(dump: Dict[str, Any], shape: TraceShape) -> Optional[str]:
    """One violated rule's counterexample, or None when its output carries no call trace.

    ``dump`` is the rule's raw output file (``assertMessage``, ``jumpToDefinition``,
    ``callTrace``). The result is ``<counterexample>`` with the failing ``<assert>``, its
    ``<source>`` as ``file:line``, and the rendered trace. ``shape`` has no default: another
    chain's shape would silently drop frames this chain's traces need.
    """
    trace = dump.get("callTrace")
    if not isinstance(trace, dict):
        return None
    parts = []
    assertion = dump.get("assertMessage")
    if isinstance(assertion, str) and assertion:
        parts.append(f"<assert>{assertion}</assert>")
    location = dump.get("jumpToDefinition")
    if isinstance(location, dict):
        file, start = location.get("file"), location.get("start")
        if isinstance(file, str) and isinstance(start, dict) and isinstance(start.get("line"), int):
            parts.append(f"<source>{file}:{start['line']}</source>")
    parts.append(calltrace_to_xml(trace, shape))
    return "<counterexample>" + "".join(parts) + "</counterexample>"
