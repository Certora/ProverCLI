# SPDX-FileCopyrightText: 2026 Certora Ltd.
#
# SPDX-License-Identifier: GPL-3.0-only

"""
Tree view parsing utilities for extracting violations, checks, and call resolutions.
"""

import logging
from typing import Any, Dict, List, Optional

from ..models import (
    AssertType,
    CallResolutionInfo,
    CheckResult,
    NodeStatus,
    NodeType,
    SourceLocation,
    StoragePathInfo,
    convert_node_type,
)


class TreeParser:
    """Parses tree-view data to extract structured information."""

    def __init__(self, default_contract: Optional[str] = None):
        """Initialize the tree parser."""
        self.logger = logging.getLogger(__name__)
        self.default_contract = default_contract

    def parse_all_checks(self, tree_data: Dict[str, Any], include_rule_not_vacuous: bool = False) -> List[CheckResult]:
        """
        Parse tree-view data to extract all checks (both successful and failed).

        Args:
            tree_data: Tree-view JSON data from treeViewStatus.json
            include_rule_not_vacuous: If True, include rule_not_vacuous nodes and their descendants.

        Returns:
            List of all checks as ViolationInfo objects
        """
        all_checks: List[CheckResult] = []

        if not tree_data or "rules" not in tree_data:
            return all_checks

        # Recursively search through the tree structure for all checks
        for rule in tree_data["rules"]:
            self._extract_checks_from_node(rule, all_checks, [], leaf_only=False,
                                           include_rule_not_vacuous=include_rule_not_vacuous)

        return all_checks

    def parse_violations(self, tree_data: Dict[str, Any]) -> List[CheckResult]:
        """
        Parse tree-view data to extract all nodes with VIOLATED status.

        This returns ALL nodes that have status=VIOLATED, including ROOT, METHOD_INSTANTIATION,
        CONTRACT, and VIOLATED_ASSERT nodes. For only assertion-level violations, use
        parse_violated_asserts().

        Args:
            tree_data: Tree-view JSON data from treeViewStatus.json

        Returns:
            List of all checks with status VIOLATED
        """
        all_checks = self.parse_all_checks(tree_data)
        return [check for check in all_checks if check.status == NodeStatus.VIOLATED]

    def parse_violated_asserts(self, tree_data: Dict[str, Any]) -> List[CheckResult]:
        """
        Parse tree-view data to extract only VIOLATED_ASSERT nodes.

        This returns only the assertion-level violations (nodeType=VIOLATED_ASSERT)
        with status=VIOLATED. This is useful for getting the specific failed assertions
        without the parent nodes.

        Args:
            tree_data: Tree-view JSON data from treeViewStatus.json

        Returns:
            List of VIOLATED_ASSERT nodes with status VIOLATED
        """
        all_checks = self.parse_all_checks(tree_data)
        return [
            check for check in all_checks
            if check.node_type == NodeType.VIOLATED_ASSERT and check.status == NodeStatus.VIOLATED
        ]

    def parse_leaf_checks(self, tree_data: Dict[str, Any]) -> List[CheckResult]:
        """
        Parse tree-view data to extract only leaf checks (actual assertions without intermediate tree nodes).

        Args:
            tree_data: Tree-view JSON data from treeViewStatus.json

        Returns:
            List of leaf checks as CheckResult objects
        """
        leaf_checks: List[CheckResult] = []

        if not tree_data or "rules" not in tree_data:
            return leaf_checks

        # Recursively search through the tree structure for leaf checks only
        for rule in tree_data["rules"]:
            self._extract_checks_from_node(rule, leaf_checks, [], leaf_only=True)

        return leaf_checks

    def parse_call_resolutions(self, tree_data: Dict[str, Any]) -> List[CallResolutionInfo]:
        """
        Extract call resolution information from globalCallResolution field.

        Args:
            tree_data: Tree-view JSON data containing globalCallResolution

        Returns:
            List of CallResolutionInfo objects
        """
        call_resolutions = []

        if isinstance(tree_data, dict) and "globalCallResolution" in tree_data:
            global_resolution = tree_data["globalCallResolution"]

            for resolution_group in global_resolution:
                if not isinstance(resolution_group, dict):
                    continue

                callee_info = resolution_group.get("callee", {})
                callee_name = callee_info.get("name", "Unknown")

                # Only process calls that start with [?] (all call resolution entries)
                if not callee_name.startswith("[?]"):
                    continue

                selector = callee_info.get("selector")
                raw_storage_path = callee_info.get("storagePath")
                storage_path = StoragePathInfo(
                    base_contract=raw_storage_path["baseContract"],
                    path=raw_storage_path["path"],
                    alternative_callees=raw_storage_path.get("alternativeCallees", []),
                ) if raw_storage_path else None

                resolution_rows = resolution_group.get("globalCallResolutionRows", [])

                for row in resolution_rows:
                    if not isinstance(row, dict):
                        continue

                    call_resolution = self._parse_resolution_row(row, callee_name, resolution_group, storage_path, selector)
                    if call_resolution:
                        call_resolutions.append(call_resolution)

        self.logger.info(
            f"Found {len(call_resolutions)} call resolutions from globalCallResolution"
        )
        return call_resolutions

    def _extract_checks_from_node(
        self,
        node: Dict[str, Any],
        checks: List[CheckResult],
        rule_context: Optional[List[str]] = None,
        method_name: Optional[str] = None,
        leaf_only: bool = False,
        include_rule_not_vacuous: bool = False,
    ) -> None:
        """
        Recursively extract checks from a tree node.

        Args:
            node: Current tree node
            checks: List to append checks to
            rule_context: List of parent node names to track rule hierarchy
            method_name: Current method name from METHOD_INSTANTIATION or special INVARIANT_SUBCHECK
            leaf_only: If True, only extract leaf nodes. If False, extract all nodes.
            include_rule_not_vacuous: If True, include rule_not_vacuous nodes and their descendants.
        """
        if rule_context is None:
            rule_context = []

        node_type_str = node.get("nodeType", "")
        node_type = convert_node_type(node_type_str) if node_type_str else None
        node_name = node.get("name", "")

        # Skip rule_not_vacuous nodes and all their descendants
        if node_name == "rule_not_vacuous" and not include_rule_not_vacuous:
            return

        # Add current node name to context if it exists
        current_context = rule_context.copy()
        if node_name:
            current_context.append(node_name)

        # Track method name based on node type
        current_method_name = method_name

        # Handle METHOD_INSTANTIATION nodes - they define the method name
        if node_type == NodeType.METHOD_INSTANTIATION:
            current_method_name = node_name

        # Handle special INVARIANT_SUBCHECK nodes that act as method context
        elif node_type == NodeType.INVARIANT_SUBCHECK:
            if node_name in ["Induction base: After the constructor", "Induction step: Reset transient storage"]:
                current_method_name = node_name

        # Check if this is a leaf node (no children or only rule_not_vacuous children)
        has_children = "children" in node and node["children"]
        if has_children:
            non_vacuous_children = [c for c in node["children"] if c.get("name") != "rule_not_vacuous"]
            has_children = bool(non_vacuous_children)

        # Determine if we should process this node
        should_process = False

        # If leaf_only mode and this node has children, skip processing
        if leaf_only and has_children:
            should_process = False
        else:
            # Process nodes with execution data
            status = node.get("status")
            duration = node.get("duration")

            if node_type and (status or duration is not None):
                if node_type == NodeType.INVARIANT_SUBCHECK:
                    # Only process special INVARIANT_SUBCHECK nodes
                    if node_name in ["Induction base: After the constructor", "Induction step: Reset transient storage"]:
                        should_process = True
                else:
                    should_process = True

        if should_process:
            check_result = self._create_violation_info(node, current_context, current_method_name)
            checks.append(check_result)

        # Recursively check children nodes
        if "children" in node:
            for child in node["children"]:
                self._extract_checks_from_node(
                    child, checks, current_context, current_method_name, leaf_only, include_rule_not_vacuous
                )

    def _create_violation_info(
        self,
        node: Dict[str, Any],
        context: List[str],
        method_name: Optional[str] = None
    ) -> CheckResult:
        """
        Create a CheckResult object from a node and its context.

        Args:
            node: The tree node
            context: List of parent node names for hierarchy tracking
            method_name: The method name (from METHOD_INSTANTIATION or special INVARIANT_SUBCHECK)
        """
        assert_message = node.get("name", "")

        # Parse status
        status_str = node.get("status", "UNKNOWN")
        try:
            status = NodeStatus(status_str)
        except ValueError:
            status = NodeStatus.UNKNOWN

        # Parse node type
        node_type_str = node.get("nodeType", "UNKNOWN")
        node_type = convert_node_type(node_type_str)

        # Parse source location
        source_location = None
        if jump_data := node.get("jumpToDefinition"):
            source_location = SourceLocation.from_jump_to_definition(jump_data)

        # Extract contract and method from method_name if available
        contract_name = None
        method_only = None
        if method_name:
            contract_name = self._extract_contract_from_method(method_name)
            method_only = self._extract_method_from_method(method_name)

        return CheckResult(
            rule_name=self._get_rule_name_from_context(context),
            method_name=method_name,  # Use the explicitly tracked method name
            rule_id=node.get("ruleId"),
            contract_name=contract_name,
            method_only=method_only,
            assert_message=assert_message,
            status=status,
            node_type=node_type,
            ui_id=node.get("uiId"),
            output_files=node.get("output", []),
            debug_trace_file=node.get("debugAdapterCallTraceFileName"),
            duration=node.get("duration", 0),
            source_location=source_location,
            rule_context=context,
            assert_type=self._determine_assert_type(assert_message),
            notifications=node.get("errors", []),
        )

    def _parse_resolution_row(
        self, row: Dict[str, Any], callee_name: str, resolution_group: Dict[str, Any],
        storage_path: Optional[StoragePathInfo] = None,
        selector: Optional[str] = None,
    ) -> Optional[CallResolutionInfo]:
        """Parse a single resolution row into CallResolutionInfo."""
        summary = row.get("summary", "")
        is_warning = row.get("isWarning", True)

        # Parse comments for detailed resolution information
        comments = row.get("comments", [])
        callee_resolution = ""
        resolved_callees = None
        havoc_cause = None
        havoc_scope = None
        summary_application_reason = None

        for comment in comments:
            if isinstance(comment, dict):
                if "callee resolution" in comment:
                    callee_resolution = comment["callee resolution"]
                elif "resolved callees" in comment:
                    resolved_callees = comment["resolved callees"]
                elif "havoc cause" in comment:
                    havoc_cause = comment["havoc cause"]
                elif "havoc scope" in comment:
                    havoc_scope = comment["havoc scope"]
                elif "summary application reason" in comment:
                    summary_application_reason = comment["summary application reason"]

        caller_info = row.get("caller", {})
        call_site_info = row.get("callSite", {})

        caller_name = caller_info.get("name", "Unknown")
        call_site_snippet = call_site_info.get("snippet", "")

        # Extract source location
        source_location = "Unknown"
        if "jumpToDefinition" in call_site_info and call_site_info["jumpToDefinition"]:
            jump_to_def = call_site_info["jumpToDefinition"]
            if "file" in jump_to_def:
                file_name = jump_to_def["file"]
                if "start" in jump_to_def and "line" in jump_to_def["start"]:
                    line_num = jump_to_def["start"]["line"]
                    source_location = f"{file_name}:{line_num}"
                else:
                    source_location = file_name

        return CallResolutionInfo(
            callee_name=callee_name,
            caller_name=caller_name,
            call_site_snippet=call_site_snippet,
            source_location=source_location,
            summary=summary,
            is_warning=is_warning,
            callee_resolution=callee_resolution,
            resolved_callees=resolved_callees,
            havoc_cause=havoc_cause,
            havoc_scope=havoc_scope,
            selector=selector,
            summary_application_reason=summary_application_reason,
            storage_path=storage_path,
            raw_resolution_group=resolution_group,
        )

    def _get_rule_name_from_context(self, context: List[str]) -> str:
        """Extract the rule name from the context hierarchy."""
        if not context:
            return "unknown_rule"
        return context[0] if context else "unknown_rule"

    def _get_method_context_from_context(self, context: List[str]) -> str:
        """Extract method context from the context hierarchy."""
        if len(context) < 2:
            return "unknown_method"

        # First priority: Look for function signatures with parentheses (e.g., "method(uint256,address)")
        for item in context:
            if "(" in item and ")" in item and not item.startswith("assert"):
                return item

        # Second priority: Look for method context patterns like "EscrowDst.cancel"
        for item in context:
            if "." in item and not item.startswith("assert"):
                return item

        # If no method pattern found, return the second item
        return context[1] if len(context) > 1 else "unknown_method"

    def _extract_contract_from_method(self, method_context: str) -> str:
        """Extract contract name from method context."""
        if "." in method_context:
            return method_context.split(".")[0]
        return self.default_contract or "unknown_contract"

    def _extract_method_from_method(self, method_context: str) -> Optional[str]:
        """Extract method name from method context."""
        if "." in method_context:
            return method_context.split(".")[1]
        return method_context if method_context != "unknown_method" else None

    def _determine_assert_type(self, assert_message: str) -> AssertType:
        """Determine assert type from assert message."""
        if not assert_message:
            return AssertType.UNKNOWN

        message_lower = assert_message.lower()

        if "contract recursion limit" in message_lower:
            return AssertType.CONTRACT_RECURSION_LIMIT
        elif "summary recursion limit" in message_lower:
            return AssertType.SUMMARY_RECURSION_LIMIT
        elif "hashing" in message_lower and ("bound" in message_lower or "limit" in message_lower):
            return AssertType.HASHING_BOUND_ASSERTION
        elif "loop" in message_lower and ("bound" in message_lower or "limit" in message_lower):
            return AssertType.LOOP_BOUND_ASSERTION
        else:
            return AssertType.UNKNOWN
