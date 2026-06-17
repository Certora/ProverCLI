# SPDX-FileCopyrightText: 2026 Certora Ltd.
#
# SPDX-License-Identifier: GPL-3.0-only

"""
Sighash utility for computing and looking up Ethereum function signatures.

This was done as part of the LLM tutorial to Certora R&D and is left here as a best-effort utility.
This tool does not know how to convert user-defined types into their proper ABI representations.

This module provides functionality to:
- Detect if input is a sighash (4-byte hex)
- Normalize full function definitions to canonical signatures
- Compute keccak256 sighash from signatures
- Look up sighashes via 4byte.directory API
"""

import re

import requests
from Crypto.Hash import keccak


def is_sighash(input_str: str) -> bool:
    """
    Detect if input is a hex sighash (0xaabbccdd or aabbccdd).

    Args:
        input_str: The input string to check

    Returns:
        True if input looks like a 4-byte sighash, False otherwise
    """
    # Remove 0x prefix if present
    clean = input_str.lower().strip()
    if clean.startswith("0x"):
        clean = clean[2:]

    # Must be exactly 8 hex characters
    return bool(re.match(r"^[0-9a-f]{8}$", clean))


def normalize_signature(input_str: str) -> str:
    """
    Convert full function definitions to canonical signature.

    Examples:
        "function transfer(address to, uint256 amount) public" -> "transfer(address,uint256)"
        "transfer(address,uint256)" -> "transfer(address,uint256)"
        "foo(bool[] calldata booboo) internal view" -> "foo(bool[])"

    Args:
        input_str: Full function definition or signature

    Returns:
        Canonical signature (function_name(type1,type2,...))
    """
    # Normalize whitespace (handle multiline declarations)
    text = re.sub(r'\s+', ' ', input_str).strip()

    # Remove 'function' keyword if present
    if text.startswith("function "):
        text = text[9:].strip()

    # Find the function name and the opening paren
    name_match = re.match(r"(\w+)\s*\(", text)
    if not name_match:
        raise ValueError(f"Cannot parse function signature: {input_str}")

    func_name = name_match.group(1)
    paren_start = name_match.end() - 1  # Position of '('

    # Find the matching closing paren by tracking depth
    depth = 0
    paren_end = -1
    for i in range(paren_start, len(text)):
        if text[i] == '(':
            depth += 1
        elif text[i] == ')':
            depth -= 1
            if depth == 0:
                paren_end = i
                break

    if paren_end == -1:
        raise ValueError(f"Cannot parse function signature: {input_str}")

    params_str = text[paren_start + 1:paren_end]

    # Remove trailing modifiers (everything after the closing paren)
    # The regex already captured just what's inside the parens

    # Parse parameters
    param_types = _parse_parameters(params_str)

    return f"{func_name}({','.join(param_types)})"


def _parse_parameters(params_str: str) -> list[str]:
    """
    Parse parameter string and extract only types.

    Handles:
    - Simple types: address, uint256, bool
    - Arrays: address[], uint256[]
    - Tuples: (address,uint256,uint256)
    - Nested structures: (address,uint,uint)[]

    Args:
        params_str: Parameter string from function signature

    Returns:
        List of canonical type names
    """
    if not params_str.strip():
        return []

    params = []
    current = ""
    depth = 0

    # Split by comma, but respect parentheses depth for tuples
    for char in params_str:
        if char == "(":
            depth += 1
            current += char
        elif char == ")":
            depth -= 1
            current += char
        elif char == "," and depth == 0:
            params.append(current.strip())
            current = ""
        else:
            current += char

    if current.strip():
        params.append(current.strip())

    # Process each parameter to extract just the type
    types = []
    for param in params:
        param_type = _extract_type(param)
        param_type = _normalize_type(param_type)
        types.append(param_type)

    return types


def _extract_type(param: str) -> str:
    """
    Extract the type from a parameter declaration.

    Examples:
        "address to" -> "address"
        "uint256 amount" -> "uint256"
        "bool[] calldata booboo" -> "bool[]"
        "(address,uint,uint) data" -> "(address,uint,uint)"

    Args:
        param: A single parameter declaration

    Returns:
        The type portion only
    """
    param = param.strip()

    # Modifiers to remove (these appear after the type and before/after the name)
    modifiers = ["memory", "storage", "calldata", "indexed"]

    # Handle tuple types - they start with '('
    if param.startswith("("):
        # Find the end of the tuple, including any array suffix
        depth = 0
        end_idx = 0
        for i, char in enumerate(param):
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    end_idx = i + 1
                    break

        # Check for array suffix after the tuple
        rest = param[end_idx:]
        if rest.startswith("[]"):
            return param[: end_idx + 2]
        return param[:end_idx]

    # For non-tuple types, split by whitespace and take the first token
    # but handle array notation which might be attached
    tokens = param.split()

    # First token should be the type (possibly with [] suffix)
    if not tokens:
        return param

    type_token = tokens[0]

    # Check if array brackets are separate: "uint256 [] name"
    if len(tokens) > 1 and tokens[1] == "[]":
        type_token += "[]"

    # Remove any modifiers that might be attached (shouldn't happen but be safe)
    for mod in modifiers:
        if type_token == mod:
            # The modifier is the first token, type might be second
            if len(tokens) > 1:
                type_token = tokens[1]
            break

    return type_token


def _normalize_type(type_str: str) -> str:
    """
    Normalize type aliases to canonical form.

    Examples:
        "uint" -> "uint256"
        "int" -> "int256"
        "byte" -> "bytes1"

    Args:
        type_str: Type string to normalize

    Returns:
        Canonical type string
    """
    # Handle tuple types recursively
    if type_str.startswith("("):
        # Find if there's an array suffix
        array_suffix = ""
        if type_str.endswith("[]"):
            array_suffix = "[]"
            type_str = type_str[:-2]

        # Parse the tuple contents
        inner = type_str[1:-1]  # Remove outer parens
        inner_types = _parse_parameters(inner)
        normalized_inner = ",".join(inner_types)
        return f"({normalized_inner}){array_suffix}"

    # Handle array types
    array_suffix = ""
    base_type = type_str
    if type_str.endswith("[]"):
        array_suffix = "[]"
        base_type = type_str[:-2]
    elif re.match(r".*\[\d+\]$", type_str):
        # Fixed-size array like uint256[10]
        match = re.match(r"(.*?)(\[\d+\])$", type_str)
        if match:
            base_type = match.group(1)
            array_suffix = match.group(2)

    # Normalize base type
    if base_type == "uint":
        base_type = "uint256"
    elif base_type == "int":
        base_type = "int256"
    elif base_type == "byte":
        base_type = "bytes1"

    return base_type + array_suffix


def compute_sighash(signature: str) -> str:
    """
    Compute keccak256 hash and return first 4 bytes as hex.

    Args:
        signature: Canonical function signature (e.g., "transfer(address,uint256)")

    Returns:
        4-byte sighash with 0x prefix (e.g., "0xa9059cbb")
    """
    k = keccak.new(digest_bits=256)
    k.update(signature.encode("utf-8"))
    return "0x" + k.hexdigest()[:8]


def lookup_sighash(sighash: str, timeout: float = 10.0) -> list[str]:
    """
    Query 4byte.directory API for matching signatures.

    Args:
        sighash: 4-byte sighash (with or without 0x prefix)
        timeout: Request timeout in seconds

    Returns:
        List of potential function signatures matching the sighash
    """
    # Normalize sighash
    clean = sighash.lower().strip()
    if not clean.startswith("0x"):
        clean = "0x" + clean

    url = f"https://www.4byte.directory/api/v1/signatures/?hex_signature={clean}"

    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        data = response.json()

        signatures = []
        for result in data.get("results", []):
            if "text_signature" in result:
                signatures.append(result["text_signature"])

        return signatures

    except requests.RequestException as e:
        raise RuntimeError(f"Failed to query 4byte.directory: {e}") from e


def handle_sighash_command(input_str: str) -> dict:
    """
    Handle the --sighash command by auto-detecting input type.

    Args:
        input_str: Either a sighash or a function signature

    Returns:
        Dict with either 'sighash' and 'signature' keys, or 'sighash' and 'signatures' keys
    """
    if is_sighash(input_str):
        # Input is a sighash, look it up
        signatures = lookup_sighash(input_str)
        return {
            "input": input_str,
            "type": "sighash_lookup",
            "sighash": input_str if input_str.startswith("0x") else "0x" + input_str,
            "signatures": signatures,
        }
    else:
        # Input is a function signature, compute sighash
        normalized = normalize_signature(input_str)
        sighash = compute_sighash(normalized)
        return {
            "input": input_str,
            "type": "signature_hash",
            "normalized_signature": normalized,
            "sighash": sighash,
        }
