Command Line Interface
======================

ProverCLI ships a command-line tool called ``prover-cli`` that
exposes most of the Python API through flags. It is the recommended way
to interact with the prover output API from shell scripts, CI pipelines,
and ad-hoc investigations.

Installation
------------

The CLI is installed automatically with the package:

.. code-block:: bash

   pip install git+https://github.com/Certora/ProverCLI.git

Verify:

.. code-block:: bash

   prover-cli --help
   prover-cli --who-am-i

Job Input
---------

Every per-job command takes exactly one of these (mutually exclusive):

.. option:: --job-id JOB_ID

   Prover job ID (the hash portion of a job URL).

.. option:: --job-url JOB_URL

   Full prover job URL (e.g. ``https://prover.certora.com/output/12345/...``).
   Staging URLs (``https://vaas-stg.certora.com/output/...``) are
   auto-detected.

.. option:: --local-path PATH

   Path to a local ``emv-*`` folder. No authentication required.

Per-Job Actions
---------------

These apply to whichever job-input flag you provided. The **default** (no
action flag) returns the violated rules.

.. option:: --status-only

   Print job status (SUCCEEDED, FAILED, RUNNING, ...) only.

.. option:: --check-running

   Print whether the job is still running, with finish time when available.

.. option:: --full-report

   One-shot triage: return the full ``JobReport`` containing rules grouped
   by status (violated / timeout / error / verified / other), resolved &
   unresolved calls, alerts grouped by type, duration, and job status.

   .. code-block:: bash

      # Compact text summary
      prover-cli --job-id JOB --full-report

      # Full JSON for machine consumption
      prover-cli --job-id JOB --full-report --format json

   JSON shape::

      {
        "job_id": "...",
        "report": {
          "job_url": "...",
          "duration": 31.64,
          "job_status": "SUCCEEDED",
          "rules":   {"violated": [...], "timeout": [...], "error": [...],
                       "verified": [...], "other": [...]},
          "calls":   {"unresolved": [...], "resolved": [...]},
          "alerts_by_type": {"<type>": [...]}
        }
      }

.. option:: --all-checks

   All checks (pass + fail), including non-leaf tree nodes.

.. option:: --leaf-checks

   Leaf checks only — actual assertions.

.. option:: --calltrace FILE

   Calltrace for the specific output file path (e.g.
   ``rule_output_58.json``). File paths come from a check's
   ``output_files`` list.

.. option:: --breadcrumbs FILE

   Breadcrumb trace from a DAP file (e.g.
   ``dap_calltrace_56-certora-dap.json``).

.. option:: --statsdata

   Contents of ``statsdata.json`` (timing, memory, etc.).

.. option:: --alerts

   Typed alerts from the alert report.

Standalone Commands
-------------------

These do not take a job-input flag:

.. option:: --recent-jobs

   List recent jobs from the data API.

   .. code-block:: bash

      # 20 jobs from the last 7 days, org-wide
      prover-cli --recent-jobs --days-back 7 --limit 20

      # Only this user's jobs, as JSON
      prover-cli --recent-jobs --my-jobs-only --format json

.. option:: --cancel JOB [JOB ...]

   Cancel one or more jobs by ID or URL.

.. option:: --who-am-i

   Show the authenticated user.

.. option:: --group-id GROUP_ID

   Summarize all runs in a verification group. Accepts a UUID or a
   ``prover.certora.com/?groupIds=...`` URL.

.. option:: --sighash SIGNATURE_OR_HEX

   Compute the 4-byte sighash for a function signature, or look up
   candidate signatures from a hex sighash.

   .. code-block:: bash

      prover-cli --sighash "transfer(address,uint256)"
      prover-cli --sighash "0xa9059cbb"

Filters for Listing Commands
----------------------------

.. option:: --days-back N

   How many days back to search. Default: ``365``. Used with
   ``--group-id`` and ``--recent-jobs``.

.. option:: --limit N

   Maximum jobs to return. Default: ``100``, capped at ``100`` by the API.
   Used with ``--recent-jobs``.

.. option:: --my-jobs-only

   With ``--recent-jobs``, restrict to the authenticated user. Default is
   org-wide (``all_users=True``).

Output Options
--------------

.. option:: --format {json,text}

   Output format. Default: ``text`` (human-readable summary). Use ``json``
   when piping into ``jq`` or another consumer.

.. option:: --output FILE, -o FILE

   Write output to a file instead of stdout.

.. option:: --verbose, -v

   Verbose output, including stack traces on errors.

.. option:: --help, -h

   Show help and exit.

Examples
--------

Triage an unknown job
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   prover-cli --job-id JOB --full-report --format json \
     | jq '.report | {duration, job_status,
                       violated:   (.rules.violated | length),
                       timeout:    (.rules.timeout  | length),
                       error:      (.rules.error    | length),
                       verified:   (.rules.verified | length),
                       unresolved: (.calls.unresolved | length)}'

List violated rules and grab a calltrace
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   JOB=cd0cf888bbf94497a4b6759553b2e180

   prover-cli --job-id "$JOB" --leaf-checks --format json \
     | jq -r '.checks[] | select(.status == "VIOLATED")
               | [.rule_name, .method_name, (.output_files // [])[0]] | @tsv'

   # Pick a FILE from the line above
   prover-cli --job-id "$JOB" --calltrace FILE --format json

Scan recent jobs for a pattern
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   prover-cli --recent-jobs --days-back 30 --limit 50 --format json \
     | jq '.jobs[] | select(.is_running == false) | {job_id, runtime, contract}'

Cancel multiple jobs
^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   prover-cli --cancel 12345 67890

Sighash lookup in a pipeline
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   echo "0xa9059cbb" | xargs -I {} prover-cli --sighash {} --format json

Group summary as JSON
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   prover-cli --group-id b78ea54a-a924-4f05-b1a7-58b29c1585ae --format json -o summary.json

Local emv-* folder
^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   prover-cli --local-path ./emv-1-certora-19-Aug--13-09 --full-report
   prover-cli --local-path ./emv-1-certora-19-Aug--13-09 --calltrace 'rule_output_58.json'

Pipeline integration
^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   # Fail the build if the job has any violated rules
   COUNT=$(prover-cli --job-id "$JOB" --full-report --format json \
             | jq '.report.rules.violated | length')
   [ "$COUNT" -eq 0 ] || { echo "Found $COUNT violations"; exit 1; }

Environment Variables
---------------------

.. envvar:: CERTORAKEY

   Certora API key. Used when ``cert_cli_login`` cookies are not present
   (e.g. CI service accounts).

.. envvar:: PROVER_OUTPUT_CACHE_DIR

   Override the default cache directory for API responses.

   .. code-block:: bash

      export PROVER_OUTPUT_CACHE_DIR=/tmp/prover_cache
      prover-cli --job-id 67890

Authentication Errors
---------------------

If the CLI reports an authentication failure, refresh your session:

.. code-block:: bash

   cert_cli_login

Or set ``CERTORAKEY`` in your environment.

Local Mode Limitations
----------------------

When using ``--local-path``, the following commands are not available
(they hit the data API):

- ``--recent-jobs``
- ``--cancel``
- ``--who-am-i``
