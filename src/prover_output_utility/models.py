# SPDX-FileCopyrightText: 2026 Certora Ltd.
#
# SPDX-License-Identifier: GPL-3.0-only

"""
Data models for Certora Prover API responses.

This module contains dataclasses that wrap raw API responses with type safety
and convenience methods.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class AssertType(str, Enum):
    """Enumeration of assertion types from prover violations."""

    CONTRACT_RECURSION_LIMIT = "contract_recursion_limit"
    SUMMARY_RECURSION_LIMIT = "summary_recursion_limit"
    HASHING_BOUND_ASSERTION = "hashing_bound_assertion"
    LOOP_BOUND_ASSERTION = "loop_bound_assertion"
    SANITY_ASSERTION = "sanity_assertion"
    UNKNOWN = "unknown"


class NodeStatus(str, Enum):
    """Status of a verification node."""

    VIOLATED = "VIOLATED"
    VERIFIED = "VERIFIED"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"
    RUNNING = "RUNNING"
    PENDING = "PENDING"
    UNKNOWN = "UNKNOWN"


class JobStatus(str, Enum):
    """Status of a prover job based on the cloud API schema."""

    # Success statuses
    SUCCEEDED = "SUCCEEDED"

    # Failure statuses
    FAILED = "FAILED"
    CANCELED = "CANCELED"
    HALTED = "HALTED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    UPLOAD_FAILED = "UPLOAD_FAILED"

    # In-progress statuses
    POSTED = "POSTED"
    QUEUED = "QUEUED"
    RUNNABLE = "RUNNABLE"
    STARTING = "STARTING"
    RUNNING = "RUNNING"

    # Unknown status (fallback for unrecognized values)
    UNKNOWN = "UNKNOWN"


class NodeType(str, Enum):
    """Type of a tree view node."""

    ROOT = "ROOT"
    METHOD_INSTANTIATION = "METHOD_INSTANTIATION"
    CONTRACT = "CONTRACT"
    INVARIANT_SUBCHECK = "INVARIANT_SUBCHECK"
    INDUCTION_STEPS = "INDUCTION_STEPS"
    CUSTOM_INDUCTION_STEP = "CUSTOM_INDUCTION_STEP"
    ASSERT_SUBRULE_AUTO_GEN = "ASSERT_SUBRULE_AUTO_GEN"
    VIOLATED_ASSERT = "VIOLATED_ASSERT"
    SANITY = "SANITY"
    UNKNOWN = "UNKNOWN"


class AlertType(str, Enum):
    """
    Types of global alerts from alert_report.

    Matches CVTAlertType in the Prover's CVTAlertReporter.kt.
    Values are the "external name" strings that appear in the JSON output.
    """

    GENERAL = "General"
    CVL = "CVL"
    SUMMARIZATION = "Summarization"
    ANALYSIS = "Analysis"
    INTERNAL_FUNCTION_ANALYSIS = "Internal Function Analysis"
    STORAGE_ANALYSIS = "Storage Analysis"
    STORAGE_SPLITTING = "Storage Splitting"
    CALL_GRAPH = "Call Graph"
    PTA_FOR_OPTIMIZATIONS = "Pointer Analysis for Optimizations"
    MEMORY_PARTITIONING = "Memory Partitioning"
    OUT_OF_RESOURCES = "Out of Resources"
    CACHE = "Cache"
    DIAGNOSABILITY = "Diagnosability"
    BMC = "Bounded Model Check"
    FOUNDRY = "Foundry mode"


def convert_job_status(status_str: str) -> JobStatus:
    """
    Convert string status to JobStatus enum.

    Args:
        status_str: Status string from API response

    Returns:
        JobStatus enum value
    """
    try:
        return JobStatus(status_str)
    except ValueError:
        return JobStatus.UNKNOWN


def convert_node_type(node_type_str: str) -> NodeType:
    """
    Convert string node type to NodeType enum.

    Args:
        node_type_str: Node type string from tree view data

    Returns:
        NodeType enum value
    """
    try:
        return NodeType(node_type_str)
    except ValueError:
        return NodeType.UNKNOWN


def convert_assert_type(assert_type_str: str) -> AssertType:
    """
    Convert string assert type to AssertType enum.

    Args:
        assert_type_str: Assert type string

    Returns:
        AssertType enum value
    """
    try:
        return AssertType(assert_type_str)
    except ValueError:
        return AssertType.UNKNOWN


def convert_alert_type(alert_type_str: str) -> AlertType:
    """
    Convert string alert type to AlertType enum.

    Args:
        alert_type_str: Alert type string from alert_report JSON

    Returns:
        AlertType enum value
    """
    try:
        return AlertType(alert_type_str)
    except ValueError:
        return AlertType.GENERAL


@dataclass
class SourceLocation:
    """Represents a source code location."""

    file: str
    line: Optional[int] = None
    end_line: Optional[int] = None
    column: Optional[int] = None
    end_column: Optional[int] = None

    def __str__(self) -> str:
        """Format as file:line string."""
        if self.line:
            return f"{self.file}:{self.line}"
        return self.file

    @classmethod
    def from_jump_to_definition(
        cls, jump_data: Dict[str, Any]
    ) -> Optional["SourceLocation"]:
        """Create from jumpToDefinition data."""
        if not jump_data or not isinstance(jump_data, dict):
            return None

        file_path = jump_data.get("file")
        if not file_path:
            return None

        start = jump_data.get("start", {})
        end = jump_data.get("end", {})

        return cls(
            file=file_path,
            line=start.get("line")
            if isinstance(start, dict)
            else jump_data.get("line"),
            end_line=end.get("line") if isinstance(end, dict) else None,
            column=start.get("column") if isinstance(start, dict) else None,
            end_column=end.get("column") if isinstance(end, dict) else None,
        )


@dataclass
class CheckResult:
    """
    Represents a result of a prover check (a tree view item).
    """

    rule_name: str
    method_name: str
    assert_message: str
    status: NodeStatus
    node_type: NodeType
    contract_name: Optional[str] = None
    method_only: Optional[str] = None
    ui_id: Optional[str] = None
    output_files: List[str] = field(default_factory=list)
    debug_trace_file: Optional[str] = None
    duration: float = 0.0
    source_location: Optional[SourceLocation] = None
    assert_type: AssertType = AssertType.UNKNOWN
    notifications: List[str] = field(default_factory=list)
    rule_context: List[str] = field(default_factory=list)

    @property
    def is_violated(self) -> bool:
        """Check if this check was violated."""
        return self.status == NodeStatus.VIOLATED

    @property
    def is_verified(self) -> bool:
        """Check if this check was verified."""
        return self.status == NodeStatus.VERIFIED

    @property
    def has_calltrace(self) -> bool:
        """Check if calltrace data is available."""
        return bool(self.output_files)

    @property
    def has_breadcrumbs(self) -> bool:
        """Check if breadcrumb trace is available."""
        return bool(self.debug_trace_file)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization and backward compatibility."""
        return {
            "rule_name": self.rule_name,
            "method_name": self.method_name,
            "contract_name": self.contract_name,
            "method_only": self.method_only,
            "assert_message": self.assert_message,
            "status": self.status.value,
            "node_type": self.node_type.value,
            "ui_id": self.ui_id,
            "output_files": self.output_files,
            "debug_trace_file": self.debug_trace_file,
            "duration": self.duration,
            "jump_to_definition": (
                {
                    "file": self.source_location.file,
                    "line": self.source_location.line,
                }
                if self.source_location
                else None
            ),
            "assert_type": self.assert_type.value,
            "notifications": self.notifications,
            "rule_context": self.rule_context,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CheckResult":
        """Create from dictionary data."""
        status_str = data.get("status", "UNKNOWN")
        try:
            status = NodeStatus(status_str)
        except ValueError:
            status = NodeStatus.UNKNOWN

        node_type_str = data.get("node_type", "UNKNOWN")
        node_type = convert_node_type(node_type_str)

        assert_type_str = data.get("assert_type", "unknown")
        assert_type = convert_assert_type(assert_type_str)

        source_location = None
        if jump_data := data.get("jump_to_definition"):
            source_location = SourceLocation.from_jump_to_definition(jump_data)

        return cls(
            rule_name=data.get("rule_name", "unknown_rule"),
            method_name=data.get("method_name", "unknown_method"),
            assert_message=data.get("assert_message", ""),
            status=status,
            node_type=node_type,
            contract_name=data.get("contract_name"),
            method_only=data.get("method_only"),
            ui_id=data.get("ui_id"),
            output_files=data.get("output_files", []),
            debug_trace_file=data.get("debug_trace_file"),
            duration=data.get("duration", 0.0),
            source_location=source_location,
            assert_type=assert_type,
            notifications=data.get("notifications", []),
            rule_context=data.get("rule_context", []),
        )


@dataclass
class StoragePathInfo:
    """Storage path information from a call resolution callee."""

    base_contract: str
    path: str
    alternative_callees: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "base_contract": self.base_contract,
            "path": self.path,
            "alternative_callees": self.alternative_callees,
        }


@dataclass
class CallResolutionInfo:
    """
    Comprehensive information about a call resolution from the prover tree view API.
    Contains all fields from globalCallResolution to allow consumers to make decisions
    based on summary type, warning status, resolved callees, etc.
    """

    callee_name: str
    caller_name: str
    call_site_snippet: str
    source_location: str
    summary: str
    is_warning: bool
    callee_resolution: str
    resolved_callees: Optional[str] = None
    havoc_cause: Optional[str] = None
    havoc_scope: Optional[str] = None
    selector: Optional[str] = None
    summary_application_reason: Optional[str] = None
    storage_path: Optional[StoragePathInfo] = None
    raw_resolution_group: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization and backward compatibility."""
        return {
            "caller": self.caller_name,
            "callee": self.callee_name,
            "call_site": self.call_site_snippet,
            "source_location": self.source_location,
            "function": self.callee_name,
            "summary": self.summary,
            "is_warning": self.is_warning,
            "resolved_callees": self.resolved_callees,
            "havoc_cause": self.havoc_cause,
            "selector": self.selector,
            "summary_application_reason": self.summary_application_reason,
            "storage_path": self.storage_path.to_dict() if self.storage_path else None,
        }

    def get(self, key: str, default: Any = None) -> Any:
        """Provide dict-like .get() method for backward compatibility."""
        dict_repr = self.to_dict()
        return dict_repr.get(key, default)


@dataclass
class CalltraceInfo:
    """
    Wraps calltrace data from a specific rule output file.
    """

    job_id: str
    output_file: str
    trace_data: Dict[str, Any]
    rule_name: Optional[str] = None

    @property
    def has_frames(self) -> bool:
        """Check if calltrace contains frame data."""
        return "frames" in self.trace_data

    @property
    def frame_count(self) -> int:
        """Get the number of frames in the trace."""
        return len(self.trace_data.get("frames", []))

    def get_frame(self, index: int) -> Optional[Dict[str, Any]]:
        """Get a specific frame by index."""
        frames = self.trace_data.get("frames", [])
        if 0 <= index < len(frames):
            return frames[index]
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "job_id": self.job_id,
            "output_file": self.output_file,
            "rule_name": self.rule_name,
            "calltrace": self.trace_data,
        }


@dataclass
class BreadcrumbInfo:
    """
    Wraps breadcrumb trace data from DAP files.
    """

    rule_identifier: str
    is_satisfy_rule: bool
    breadcrumbs: List[Dict[str, Any]]
    summary: Dict[str, int]
    dap_file: Optional[str] = None

    @property
    def total_steps(self) -> int:
        """Get total number of execution steps."""
        return self.summary.get("total_steps", 0)

    @property
    def function_calls(self) -> int:
        """Get number of function calls."""
        return self.summary.get("function_calls", 0)

    @property
    def storage_operations(self) -> int:
        """Get number of storage operations."""
        return self.summary.get("storage_operations", 0)

    def filter_by_type(self, breadcrumb_type: str) -> List[Dict[str, Any]]:
        """Filter breadcrumbs by type."""
        return [b for b in self.breadcrumbs if b.get("type") == breadcrumb_type]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "rule": {
                "identifier": self.rule_identifier,
                "is_satisfy_rule": self.is_satisfy_rule,
            },
            "breadcrumbs": self.breadcrumbs,
            "summary": self.summary,
            "dap_file": self.dap_file,
        }

    @classmethod
    def from_dict(
        cls, data: Dict[str, Any], dap_file: Optional[str] = None
    ) -> "BreadcrumbInfo":
        """Create from dictionary data."""
        rule_data = data.get("rule", {})
        return cls(
            rule_identifier=rule_data.get("identifier", ""),
            is_satisfy_rule=rule_data.get("is_satisfy_rule", False),
            breadcrumbs=data.get("breadcrumbs", []),
            summary=data.get("summary", {}),
            dap_file=dap_file,
        )


@dataclass
class JobInfo:
    """
    Represents job information from the API.
    """

    job_id: str
    status: JobStatus
    start_time: Optional[str] = None
    finish_time: Optional[str] = None
    user_id: Optional[str] = None
    project: Optional[str] = None
    contract: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_running(self) -> bool:
        """Check if job is still running."""
        return self.finish_time is None

    @property
    def is_completed(self) -> bool:
        """Check if job has completed."""
        return self.finish_time is not None

    @property
    def runtime(self) -> Optional[float]:
        """
        Get job runtime in seconds (finish_time - start_time).

        Returns:
            Runtime in seconds, or None if job is still running or timestamps unavailable.
        """
        if not self.start_time or not self.finish_time:
            return None
        try:
            start = datetime.fromisoformat(self.start_time)
            finish = datetime.fromisoformat(self.finish_time)
            return (finish - start).total_seconds()
        except (ValueError, TypeError):
            return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "start_time": self.start_time,
            "finish_time": self.finish_time,
            "user_id": self.user_id,
            "project": self.project,
            "contract": self.contract,
            "is_running": self.is_running,
            "runtime": self.runtime,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JobInfo":
        """Create from dictionary data.

        Accepts both the internal shape (job_id, status) and the data-api
        /v1/domain/jobs response shape (id, job_status).

        Note on status precedence: the data-api jobs listing returns BOTH
        ``status`` (low-level state like "UPLOADING") and ``job_status`` (the
        canonical lifecycle status: POSTED/QUEUED/RUNNING/SUCCEEDED/...).
        We prefer ``job_status`` to match what convert_job_status understands.
        """
        status_str = data.get("job_status") or data.get("status") or "unknown"
        status = convert_job_status(status_str)

        return cls(
            job_id=data.get("job_id") or data.get("id", ""),
            status=status,
            start_time=data.get("start_time"),
            finish_time=data.get("finish_time"),
            user_id=data.get("user_id"),
            project=data.get("project"),
            contract=data.get("contract"),
            raw_data=data,
        )


@dataclass
class TreeViewData:
    """
    Wraps tree view data for easier access and manipulation.
    """

    job_id: str
    rules: List[Dict[str, Any]]
    global_call_resolution: List[Dict[str, Any]] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def rule_count(self) -> int:
        """Get number of rules in the tree."""
        return len(self.rules)

    def find_rule(self, rule_name: str) -> Optional[Dict[str, Any]]:
        """Find a rule by name."""
        for rule in self.rules:
            if rule.get("name") == rule_name:
                return rule
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return (
            self.raw_data
            if self.raw_data
            else {
                "rules": self.rules,
                "globalCallResolution": self.global_call_resolution,
            }
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any], job_id: str) -> "TreeViewData":
        """Create from dictionary data."""
        return cls(
            job_id=job_id,
            rules=data.get("rules", []),
            global_call_resolution=data.get("globalCallResolution", []),
            raw_data=data,
        )


@dataclass
class ParsedAlert:
    """
    A parsed global alert from alert_report.

    Matches the JSON structure from CVTAlertReporter.kt.
    """

    alert_type: AlertType
    message: str
    severity: str = "WARNING"  # "INFO", "WARNING", or "ERROR"
    jump_to_definition: Optional[str] = None  # Source location, e.g., "src/Contract.sol:42"
    hint: Optional[str] = None  # Optional hint for resolving the issue
    url: Optional[str] = None  # Documentation URL
    timestamp: Optional[str] = None  # Alert creation timestamp

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "type": self.alert_type.value,
            "message": self.message,
            "severity": self.severity,
            "jumpToDefinition": self.jump_to_definition,
            "hint": self.hint,
            "url": self.url,
            "timeStamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ParsedAlert":
        """Create from dictionary data (e.g., from alertReport.json or cache)."""
        type_str = data.get("type", "General")
        alert_type = convert_alert_type(type_str)

        return cls(
            alert_type=alert_type,
            message=data.get("message", ""),
            severity=data.get("severity", "WARNING"),
            jump_to_definition=data.get("jumpToDefinition"),
            hint=data.get("hint"),
            url=data.get("url"),
            timestamp=data.get("timeStamp"),
        )


@dataclass
class SourceFileNode:
    """A node in the source files tree (file or directory)."""

    name: str
    selectable: bool
    output: str
    children: List["SourceFileNode"] = field(default_factory=list)
    ui_id: str = ""
    file_size_exceeded: bool = False
    size: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SourceFileNode":
        """Create from raw API response dictionary."""
        return cls(
            name=data.get("name", ""),
            selectable=data.get("selectable", False),
            output=data.get("output", ""),
            children=[cls.from_dict(c) for c in data.get("children", [])],
            ui_id=data.get("uiID", ""),
            file_size_exceeded=data.get("fileSizeExceeded", False),
            size=data.get("size", 0),
        )

    @staticmethod
    def from_list(data: List[Dict[str, Any]]) -> List["SourceFileNode"]:
        """Parse a list of raw API response dictionaries into SourceFileNode objects."""
        return [SourceFileNode.from_dict(item) for item in data]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "uiID": self.ui_id,
            "name": self.name,
            "selectable": self.selectable,
            "output": self.output,
            "children": [c.to_dict() for c in self.children],
            "fileSizeExceeded": self.file_size_exceeded,
            "size": self.size,
        }
