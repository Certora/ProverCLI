# SPDX-FileCopyrightText: 2026 Certora Ltd.
#
# SPDX-License-Identifier: GPL-3.0-only

"""
Breadcrumb API for parsing DAP calltrace files and generating execution summaries.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional


class BreadcrumbParser:
    """
    Parser for DAP (Debug Adapter Protocol) calltrace files.
    Generates breadcrumb summaries focusing on function calls, storage operations, and branching.
    """

    def __init__(self, source_root: Optional[str] = None):
        """
        Initialize the breadcrumb parser.

        Args:
            source_root: Root directory for source files. If None, uses current working directory.
        """
        self.source_root = Path(source_root) if source_root else Path.cwd()

    def parse_dap_file(self, dap_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse a DAP calltrace file and generate a breadcrumb summary.

        Args:
            dap_data: Parsed DAP JSON data

        Returns:
            Breadcrumb summary with hierarchical trace structure
        """
        result: Dict[str, Any] = {
            "rule": self._extract_rule_info(dap_data.get("rule", {})),
            "breadcrumbs": [],
            "summary": {
                "total_steps": 0,
                "function_calls": 0,
                "storage_operations": 0,
                "branches": 0,
                "variable_assignments": 0,
            },
        }

        if "trace" not in dap_data:
            return result

        # Process trace entries
        for trace_entry in dap_data["trace"]:
            breadcrumb = self._process_trace_entry(trace_entry)
            if breadcrumb:
                result["breadcrumbs"].append(breadcrumb)
                self._update_summary(result["summary"], breadcrumb)

        result["summary"]["total_steps"] = len(result["breadcrumbs"])
        return result

    def _extract_rule_info(self, rule_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract rule information from DAP data."""
        return {
            "identifier": rule_data.get("fullyQualifiedRuleIdentifier", ""),
            "is_satisfy_rule": rule_data.get("isSatisfyRule", False),
        }

    def _process_trace_entry(self, trace_entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a single trace entry and extract relevant information."""
        statement = trace_entry.get("statement", "")
        frames = trace_entry.get("frames", [])

        # Classify the statement type
        stmt_type = self._classify_statement(statement)

        if stmt_type == "ignored":
            return None

        breadcrumb = {
            "type": stmt_type,
            "statement": statement,
            "frames": [],
            "source_info": None,
            "variables": [],
            "details": {},
        }

        # Process frames (stack hierarchy)
        for frame in frames:
            frame_info = self._process_frame(frame)
            if frame_info:
                breadcrumb["frames"].append(frame_info)

                # Use the first frame's source info as primary
                if not breadcrumb["source_info"] and frame_info.get("source_info"):
                    breadcrumb["source_info"] = frame_info["source_info"]

        # Extract specific details based on statement type
        self._extract_statement_details(statement, breadcrumb)

        return breadcrumb

    def _classify_statement(self, statement: str) -> str:
        """Classify the type of statement."""
        if "call.trace.push" in statement:
            return "function_call"
        elif "call.trace.pop" in statement:
            return "function_return"
        elif "AssignExpCmd" in statement and (
            "StorageRead" in statement or "StorageWrite" in statement
        ):
            return "storage_operation"
        elif "AssignExpCmd" in statement:
            return "variable_assignment"
        elif "BranchCmd" in statement or "ConditionalBranchCmd" in statement:
            return "branch"
        elif "internal.func.start" in statement:
            return "internal_function_call"
        elif "snippet.cmd" in statement:
            return "source_step"
        elif "cvl.label" in statement:
            return "cvl_annotation"
        else:
            return "ignored"

    def _process_frame(self, frame: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a stack frame."""
        stack_entry = frame.get("stackEntry", {})
        frame_type = stack_entry.get("type", "")

        frame_info = {
            "name": stack_entry.get("name", ""),
            "type": frame_type,
            "source_info": None,
            "variables": [],
        }

        # Extract source information
        range_info = frame.get("range")
        if range_info:
            source_info = self._extract_source_info(range_info)
            if source_info:
                frame_info["source_info"] = source_info

        # Extract variables
        var_containers = frame.get("variableContainers", [])
        for container in var_containers:
            if container.get("header") == "Locals":
                variables = self._extract_variables(container.get("variables", []))
                frame_info["variables"].extend(variables)

        return frame_info

    def _extract_source_info(self, range_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract source file information and snippet."""
        spec_file = range_info.get("specFile")
        source_file = range_info.get("sourceFile")
        file_path = spec_file or source_file

        if not file_path:
            return None

        start = range_info.get("start", {})
        end = range_info.get("end", {})

        start_line = start.get("line", 0) + 1  # Convert to 1-based
        end_line = end.get("line", 0) + 1

        source_info = {
            "file": file_path,
            "start_line": start_line,
            "end_line": end_line,
            "content": None,
        }

        # Try to read source content
        content = self._read_source_snippet(file_path, start_line, end_line)
        if content:
            source_info["content"] = content

        return source_info

    def _read_source_snippet(self, file_path: str, start_line: int, end_line: int) -> Optional[str]:
        """Read a snippet of source code."""
        try:
            full_path = self.source_root / file_path
            if not full_path.exists():
                return None

            with open(full_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            if start_line <= 0 or start_line > len(lines):
                return None

            if start_line == end_line:
                # Single line
                return lines[start_line - 1].strip()
            else:
                # Multiple lines - use ellipsis
                first_line = lines[start_line - 1].strip()
                return f"{first_line}..."

        except (IOError, UnicodeDecodeError):
            return None

    def _extract_variables(self, variables_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract variable information from frames."""
        result = []

        for var in variables_list:
            var_info = {
                "name": var.get("name", ""),
                "value": self._simplify_value(var.get("value", "")),
                "children": [],
            }

            # Process children variables
            children = var.get("children", [])
            if children:
                var_info["children"] = self._extract_variables(children)

            result.append(var_info)

        return result

    def _simplify_value(self, value: str) -> str:
        """Simplify complex values for readability."""
        if not value or len(value) <= 50:
            return value

        # Truncate long values
        return value[:47] + "..."

    def _extract_statement_details(self, statement: str, breadcrumb: Dict[str, Any]) -> None:
        """Extract specific details from different statement types."""
        if breadcrumb["type"] == "function_call":
            # Extract method signature
            match = re.search(r"evmExternalMethodInfo=([^,)]+)", statement)
            if match:
                breadcrumb["details"]["method"] = match.group(1)

        elif breadcrumb["type"] == "storage_operation":
            # Determine if read or write
            if "StorageRead" in statement:
                breadcrumb["details"]["operation"] = "read"
            elif "StorageWrite" in statement:
                breadcrumb["details"]["operation"] = "write"

            # Extract variable being assigned
            match = re.search(r"AssignExpCmd\s+(\w+)", statement)
            if match:
                breadcrumb["details"]["variable"] = match.group(1)

        elif breadcrumb["type"] == "variable_assignment":
            # Extract variable being assigned
            match = re.search(r"AssignExpCmd\s+([^:]+)", statement)
            if match:
                breadcrumb["details"]["variable"] = match.group(1).strip()

        elif breadcrumb["type"] == "branch":
            breadcrumb["details"]["condition"] = "conditional branch"

        elif breadcrumb["type"] == "internal_function_call":
            # Extract method signature
            match = re.search(r"methodSignature=([^,)]+)", statement)
            if match:
                breadcrumb["details"]["method"] = match.group(1)

        elif breadcrumb["type"] == "source_step":
            # Extract range information
            match = re.search(r"range=([^)]+)", statement)
            if match:
                breadcrumb["details"]["range"] = match.group(1)

    def _update_summary(self, summary: Dict[str, int], breadcrumb: Dict[str, Any]) -> None:
        """Update summary statistics."""
        breadcrumb_type = breadcrumb["type"]

        if breadcrumb_type in ["function_call", "internal_function_call"]:
            summary["function_calls"] += 1
        elif breadcrumb_type == "storage_operation":
            summary["storage_operations"] += 1
        elif breadcrumb_type == "branch":
            summary["branches"] += 1
        elif breadcrumb_type == "variable_assignment":
            summary["variable_assignments"] += 1


def format_breadcrumbs_text(breadcrumbs_data: Dict[str, Any]) -> str:
    """Format breadcrumbs data as human-readable text."""
    lines = []

    # Rule info
    rule = breadcrumbs_data["rule"]
    lines.append(f"Rule: {rule['identifier']}")
    lines.append(f"Is Satisfy Rule: {rule['is_satisfy_rule']}")
    lines.append("")

    # Summary
    summary = breadcrumbs_data["summary"]
    lines.append("=== EXECUTION SUMMARY ===")
    lines.append(f"Total Steps: {summary['total_steps']}")
    lines.append(f"Function Calls: {summary['function_calls']}")
    lines.append(f"Storage Operations: {summary['storage_operations']}")
    lines.append(f"Branches: {summary['branches']}")
    lines.append(f"Variable Assignments: {summary['variable_assignments']}")
    lines.append("")

    # Breadcrumbs
    lines.append("=== EXECUTION TRACE ===")

    current_depth = 0
    for i, crumb in enumerate(breadcrumbs_data["breadcrumbs"], 1):
        # Determine nesting level from frames
        depth = len(crumb["frames"]) if crumb["frames"] else current_depth
        indent = "  " * depth

        # Type icon
        type_icons = {
            "function_call": "🔵",
            "function_return": "🔴",
            "storage_operation": "💾",
            "variable_assignment": "📝",
            "branch": "🔀",
            "internal_function_call": "🟦",
            "source_step": "📍",
            "cvl_annotation": "🏷️",
        }

        icon = type_icons.get(crumb["type"], "•")
        lines.append(f"{indent}{i:3d}. {icon} {crumb['type'].upper()}")

        # Add method/variable details
        if crumb["details"].get("method"):
            lines.append(f"{indent}     Method: {crumb['details']['method']}")
        elif crumb["details"].get("variable"):
            lines.append(f"{indent}     Variable: {crumb['details']['variable']}")
        elif crumb["details"].get("operation"):
            lines.append(f"{indent}     Operation: {crumb['details']['operation']}")

        # Add source info
        if crumb["source_info"]:
            src = crumb["source_info"]
            location = f"{src['file']}:{src['start_line']}"
            if src["start_line"] != src["end_line"]:
                location += f"-{src['end_line']}"
            lines.append(f"{indent}     📁 {location}")

            if src["content"]:
                lines.append(f"{indent}     💬 {src['content']}")

        lines.append("")

    return "\n".join(lines)
