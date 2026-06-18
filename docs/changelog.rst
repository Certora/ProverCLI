Changelog
=========

All notable changes to ProverCLI will be documented in this file.

The format is based on `Keep a Changelog <https://keepachangelog.com/en/1.0.0/>`_,
and this project adheres to `Semantic Versioning <https://semver.org/spec/v2.0.0.html>`_.

[Unreleased]
------------

Added
^^^^^

- ``prover-cli --full-report`` flag — one-shot triage that returns the full
  ``JobReport`` (rules grouped by status, calls, alerts, duration, job status)
  as a single JSON blob. Mirrors ``ProverOutputAPI.get_job_report()``.
- ``prover-cli --recent-jobs`` flag (with ``--days-back``, ``--limit``,
  ``--my-jobs-only``) — list recent jobs from the data API. Org-wide by
  default.
- ``ProverOutputAPI.list_recent_jobs(days_back=7, limit=100, all_users=True)``
  now backed by the real ``/v1/domain/jobs`` endpoint. Previous placeholder
  endpoint removed.

[0.1.0] - 2024-11-12
--------------------

Initial release of ProverCLI.

Added
^^^^^

Core API
""""""""

- ``ProverOutputAPI`` class with comprehensive methods for accessing prover outputs
- Support for job URLs and job IDs as input
- Support for local ``emv-*`` folders
- Authentication via ``certora_login``
- Persistent caching system for improved performance

Data Fetching Methods
""""""""""""""""""""""

- ``get_violated_rules()`` - Get all violated rules
- ``get_all_checks()`` - Get all checks (passed and failed)
- ``get_leaf_checks()`` - Get leaf-level checks only
- ``get_call_resolutions()`` - Get call resolution information
- ``fetch_output()`` - Backward compatibility method for full output

Trace and Debug
"""""""""""""""

- ``get_calltrace()`` - Get calltrace data for a rule
- ``get_calltrace_for_violation()`` - Get calltrace from CheckResult
- ``get_breadcrumbs()`` - Get breadcrumb trace from DAP file
- ``get_breadcrumbs_for_violation()`` - Get breadcrumbs from CheckResult

Job Information
"""""""""""""""

- ``get_job_status()`` - Get job status
- ``get_job_info()`` - Get comprehensive job information
- ``is_job_running()`` - Check if job is running
- ``get_tree_view_data()`` - Get tree-view data

Job Management
""""""""""""""

- ``list_recent_jobs()`` - List recent jobs
- ``cancel_job()`` - Cancel a single job
- ``cancel_jobs()`` - Cancel multiple jobs

Data Retrieval
""""""""""""""

- ``get_statsdata()`` - Get statsdata.json
- ``get_console_logs()`` - Get console logs
- ``get_alert_report()`` - Get alert report
- ``who_am_i()`` - Get current user information

Advanced Methods
""""""""""""""""

- ``parse_tree_view_path()`` - Parse tree view path
- ``get_rule_hierarchy()`` - Get rule hierarchy
- ``download_job_outputs()`` - Bulk download job outputs
- ``fetch_custom_endpoint()`` - Fetch from custom endpoint

Data Models
"""""""""""

- ``CheckResult`` - Verification check result
- ``CallResolutionInfo`` - Call resolution information
- ``CalltraceInfo`` - Calltrace data
- ``BreadcrumbInfo`` - Breadcrumb trace data
- ``JobInfo`` - Job information
- ``TreeViewData`` - Tree-view data
- ``SourceLocation`` - Source code location

Enumerations
""""""""""""

- ``NodeStatus`` - Verification node status
- ``JobStatus`` - Job status
- ``AssertType`` - Assertion type

Exceptions
""""""""""

- ``ProverAPIError`` - Base exception
- ``AuthenticationError`` - Authentication failure
- ``JobNotFoundError`` - Job not found
- ``ParseError`` - Parse failure
- ``InvalidJobError`` - Invalid job input
- ``APITimeoutError`` - Request timeout

Utilities
"""""""""

- URL parsing utilities (``extract_job_id``, ``extract_job_identifier``)
- Tree parser for verification results
- Breadcrumb parser for DAP files
- Cache system (``APICache``)
- Authentication helpers (``ProverAuth``, ``AWSAuth``)

Command Line Interface
""""""""""""""""""""""

- ``prover-cli`` command-line tool
- Support for job ID and job URL input
- JSON and text output formats
- File output support
- Status-only mode

Documentation
"""""""""""""

- Complete Sphinx documentation
- API reference with autodoc
- User guide and examples
- Installation instructions
- Authentication guide
- Caching documentation

[Unreleased]
------------

Planned features for future releases:

- Enhanced filtering and sorting for violations
- Support for diff between two job runs
- Batch processing utilities
- Integration with CI/CD platforms
- Web interface for browsing results
- Export to additional formats (CSV, HTML)
- Performance optimizations
- Additional retry logic for network failures
