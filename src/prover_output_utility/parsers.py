# SPDX-FileCopyrightText: 2026 Certora Ltd.
#
# SPDX-License-Identifier: GPL-3.0-only

"""
Output parsers for different types of Prover data.
"""

import logging
from typing import Any, Dict, List

from .exceptions import ParseError


class OutputParser:
    """
    Main parser class for Certora Prover outputs.
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    def parse(self, raw_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse raw prover output into structured data.

        Args:
            raw_output: Raw API response data

        Returns:
            Parsed and structured output data
        """
        try:
            parsed_data = {
                "job_info": self._parse_job_info(raw_output),
                "verification_results": self._parse_verification_results(raw_output),
                "rule_results": self._parse_rule_results(raw_output),
                "contract_info": self._parse_contract_info(raw_output),
                "statistics": self._parse_statistics(raw_output),
            }

            return parsed_data

        except Exception as e:
            raise ParseError(f"Failed to parse prover output: {e}")

    def _parse_job_info(self, raw_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse job information from raw output.

        Args:
            raw_output: Raw API response data

        Returns:
            Job information dictionary
        """
        return {
            "job_id": raw_output.get("id", raw_output.get("job_id")),
            "status": raw_output.get("status"),
            "created_at": raw_output.get("created_at", raw_output.get("timestamp")),
            "completed_at": raw_output.get("completed_at"),
            "duration": raw_output.get("duration"),
            "prover_version": raw_output.get("prover_version"),
            "configuration": raw_output.get("config", {}),
        }

    def _parse_verification_results(self, raw_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse overall verification results.

        Args:
            raw_output: Raw API response data

        Returns:
            Verification results summary
        """
        results = raw_output.get("results", {})

        return {
            "overall_status": results.get("status"),
            "total_rules": results.get("total_rules", 0),
            "passed_rules": results.get("passed_rules", 0),
            "failed_rules": results.get("failed_rules", 0),
            "timeout_rules": results.get("timeout_rules", 0),
            "sanity_passed": results.get("sanity_passed", False),
            "compilation_errors": results.get("compilation_errors", []),
        }

    def _parse_rule_results(self, raw_output: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse individual rule results.

        Args:
            raw_output: Raw API response data

        Returns:
            List of rule result dictionaries
        """
        rules_data = raw_output.get("rules", [])
        if not isinstance(rules_data, list):
            rules_data = []

        parsed_rules = []
        for rule_data in rules_data:
            parsed_rule = {
                "rule_name": rule_data.get("name"),
                "status": rule_data.get("status"),
                "duration": rule_data.get("duration"),
                "counterexample": rule_data.get("counterexample"),
                "call_trace": rule_data.get("call_trace", []),
                "error_message": rule_data.get("error"),
                "timeout": rule_data.get("timeout", False),
            }
            parsed_rules.append(parsed_rule)

        return parsed_rules

    def _parse_contract_info(self, raw_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse contract information.

        Args:
            raw_output: Raw API response data

        Returns:
            Contract information dictionary
        """
        contract_data = raw_output.get("contract", {})

        return {
            "name": contract_data.get("name"),
            "address": contract_data.get("address"),
            "source_files": contract_data.get("files", []),
            "compiler_version": contract_data.get("compiler_version"),
            "optimization_settings": contract_data.get("optimization", {}),
        }

    def _parse_statistics(self, raw_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse execution statistics.

        Args:
            raw_output: Raw API response data

        Returns:
            Statistics dictionary
        """
        stats = raw_output.get("statistics", {})

        return {
            "total_time": stats.get("total_time"),
            "compilation_time": stats.get("compilation_time"),
            "verification_time": stats.get("verification_time"),
            "memory_usage": stats.get("memory_usage"),
            "cpu_usage": stats.get("cpu_usage"),
            "gas_analysis": stats.get("gas_analysis", {}),
        }


class RuleResultParser:
    """
    Specialized parser for individual rule results.
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    def parse_counterexample(self, counterexample_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse counterexample data into structured format.

        Args:
            counterexample_data: Raw counterexample data

        Returns:
            Structured counterexample information
        """
        if not counterexample_data:
            return {}

        return {
            "initial_state": counterexample_data.get("initial_state", {}),
            "final_state": counterexample_data.get("final_state", {}),
            "execution_trace": counterexample_data.get("trace", []),
            "variable_assignments": counterexample_data.get("variables", {}),
            "violated_assertion": counterexample_data.get("assertion"),
        }

    def parse_call_trace(self, call_trace_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Parse call trace data.

        Args:
            call_trace_data: Raw call trace data

        Returns:
            Structured call trace
        """
        parsed_trace = []

        for call in call_trace_data:
            parsed_call = {
                "function": call.get("function"),
                "contract": call.get("contract"),
                "parameters": call.get("parameters", {}),
                "return_value": call.get("return_value"),
                "gas_used": call.get("gas_used"),
                "subcalls": call.get("subcalls", []),
            }
            parsed_trace.append(parsed_call)

        return parsed_trace
