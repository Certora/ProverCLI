# ProverCLI

[![CI](https://github.com/Certora/ProverCLI/workflows/CI/badge.svg)](https://github.com/Certora/ProverCLI/actions)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

A Python API and CLI for parsing outputs from the Certora Prover. This utility provides an easy-to-use interface for fetching and parsing prover verification results using either job URLs or job IDs.

> Distributed on PyPI as **`certora-prover-cli`**; the Python import package is **`prover_output_utility`**
> (e.g. `from prover_output_utility import ProverOutputAPI`).

## Documentation

📖 Full Sphinx documentation lives in [`docs/`](docs/) — build it locally with `make -C docs html`
(see [`docs/README.md`](docs/README.md)).

The documentation includes:
- Complete API reference with all methods and classes
- Quick start guide and tutorials
- Usage examples and best practices
- CLI reference
- Authentication setup
- Caching documentation

## Features

- **Flexible Input**: Accepts job URLs (format: `/output/user_id/job_id`), job IDs, and local `emv-*` folders
- **Authentication**: Interactive cookie-based login via `certora_login`; AWS SigV4 in CI; no auth for local folders
- **Comprehensive Parsing**: Extracts job info, verification results, rule details, calltraces, breadcrumbs, and statistics
- **Error Handling**: Robust error handling with custom exceptions
- **Type Safety**: Full type hints and typed dataclass results

## Installation

### As a CLI tool (recommended for end users)

Install via [uv](https://docs.astral.sh/uv/) — each tool gets its own isolated venv, with one-command upgrade and uninstall:

```bash
# One-time uv install (skip if already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install from PyPI
uv tool install certora-prover-cli

# Upgrade / uninstall
uv tool upgrade certora-prover-cli
uv tool uninstall certora-prover-cli
```

Or with pip: `pip install certora-prover-cli`.

### Local development install

```bash
git clone https://github.com/Certora/ProverCLI.git
cd ProverCLI
pip install -e .
```

### As a dependency in another Python project

```toml
# pyproject.toml
dependencies = [
    "certora-prover-cli",
]
```

```bash
# requirements.txt
certora-prover-cli
```

## Quick Start

### Command Line Interface

After installation, you can use the `prover-cli` command:

```bash
# Get violated rules from a job (using job_id, not user_id)
prover-cli --job-id 67890
prover-cli --job-url "https://prover.certora.com/output/12345/67890/..."

# Save output to a file
prover-cli --job-id 67890 --output violations.json

# Get only job status
prover-cli --job-id 67890 --status-only

# Output as JSON
prover-cli --job-id 67890 --format json
```

### Using as a Python Package

Data-fetching methods return typed dataclasses (see [`models.py`](src/prover_output_utility/models.py)),
so results are accessed by attribute, not dict keys:

```python
from prover_output_utility import ProverOutputAPI

# Initialize the API (interactive cookie-based auth via certora_login)
api = ProverOutputAPI()

# Accepts a job URL (format: /output/user_id/job_id), a job ID, or a local emv-* path
violations = api.get_violated_rules("67890")
for v in violations:                       # each v is a CheckResult
    print(f"{v.rule_name} ({v.method_name}): {v.assert_message}")
    if v.source_location:
        print(f"  at {v.source_location}")  # file:line

# Job status without fetching full output
status = api.get_job_status("67890")        # JobStatus enum
print(f"Job status: {status}")
```

### Integration Example

```python
from prover_output_utility import ProverOutputAPI
from prover_output_utility.exceptions import ProverAPIError


class VerificationAnalyzer:
    def __init__(self):
        self.api = ProverOutputAPI()

    def analyze_job(self, job_input):
        try:
            all_checks = self.api.get_all_checks(job_input)
            violations = [c for c in all_checks if c.is_violated]
            if violations:
                return {
                    "status": "failed",
                    "summary": f"{len(violations)}/{len(all_checks)} checks failed",
                    "violations": violations,
                }
            return {"status": "passed", "summary": f"All {len(all_checks)} checks passed"}
        except ProverAPIError as e:
            return {"status": "error", "error": str(e)}


result = VerificationAnalyzer().analyze_job("67890")  # job_id, not user_id
print(result)
```

### Advanced Usage

```python
# List recent jobs (returns JobInfo objects)
for job in api.list_recent_jobs(limit=5):
    print(f"Job {job.job_id}: {job.status} ({job.start_time})")

# Deep trace analysis for a violation
for v in api.get_violated_rules("67890"):
    if v.has_calltrace:
        trace = api.get_calltrace_for_violation("67890", v)
        print(f"{v.rule_name}: {trace.frame_count} calltrace frames")
    if v.has_breadcrumbs:
        bc = api.get_breadcrumbs_for_violation("67890", v)
        print(f"{v.rule_name}: {bc.total_steps} breadcrumb steps")
```

## Authentication

Authentication is selected automatically by environment — see
[`docs/authentication.rst`](docs/authentication.rst) for details:

| Environment | Mechanism |
|---|---|
| Interactive (default) | Cookie-based login via `certora_login` (prompts/uses stored credentials) |
| CI (`CI` env var + AWS creds) | AWS SigV4 via an OIDC role |
| Local (`use_local=True`) | None — reads local `emv-*` folders |

```python
api = ProverOutputAPI()                 # interactive / CI (auto-detected)
api = ProverOutputAPI(use_local=True)   # parse local emv-* folders, no auth
```

> The legacy `CERTORAKEY` / `certora_key=` path is deprecated and no longer the
> recommended way to authenticate.

## Output Structure

Prefer the typed accessors — `get_violated_rules()`, `get_all_checks()`,
`get_job_info()`, `get_calltrace()`, `get_breadcrumbs()` — which return the
dataclasses defined in [`models.py`](src/prover_output_utility/models.py)
(`CheckResult`, `JobInfo`, `CalltraceInfo`, `BreadcrumbInfo`, …). The full API
reference is in [`docs/`](docs/). The lower-level `fetch_output()` returns the
raw parsed dictionary for backward compatibility.

## Error Handling

The API provides several custom exceptions:

- `ProverAPIError`: Base exception for API errors
- `AuthenticationError`: Authentication failed
- `JobNotFoundError`: Job not found or inaccessible
- `ParseError`: Failed to parse output
- `InvalidJobError`: Invalid job input format
- `APITimeoutError`: API request timed out

```python
from prover_output_utility import ProverOutputAPI
from prover_output_utility.exceptions import JobNotFoundError, AuthenticationError

api = ProverOutputAPI()

try:
    result = api.fetch_output("invalid-job-id")
except JobNotFoundError:
    print("Job not found")
except AuthenticationError:
    print("Authentication failed - check your certora_login session")
```

## Development

This repository holds the library/CLI code.

### Code Quality

```bash
# Install development dependencies
pip install -e .[dev]

# Format code
black src/
isort src/

# Type-check
mypy src/prover_output_utility/ --ignore-missing-imports
```

### License headers (REUSE)

```bash
uvx --from "reuse[charset-normalizer]" reuse lint
```

### Building Documentation

ProverCLI uses Sphinx for generating official documentation:

```bash
# Install documentation dependencies
pip install sphinx sphinx-rtd-theme

# Build HTML documentation
make -C docs html

# View documentation
open docs/_build/html/index.html
```

The documentation includes:
- Complete API reference (auto-generated from docstrings)
- User guide and tutorials
- Usage examples
- Authentication setup
- CLI reference
- Caching documentation

See [docs/README.md](docs/README.md) for detailed documentation build instructions.
