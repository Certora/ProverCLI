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

   pip install certora-prover-cli

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

.. option:: --verdicts

   The job's verdicts rule by rule, read from its leaf checks: one per
   method of a parametric rule or invariant, and one per assertion. A
   rule's top-level node only summarizes them; it can read ``ERROR`` while
   a method is ``VIOLATED``, and it carries no counterexample. Text output
   prints one line per rule with its leaf statuses counted, a line for each
   leaf that is not ``VERIFIED``, and then every violated leaf's
   counterexample rendered as ``<counterexample>`` XML (failing assert,
   ``file:line``, and the call trace with values filled in). The JSON form
   (``--format json`` or ``--output``) also holds the full ``--full-report``
   content. Works with ``--local-path`` too.

.. option:: --save-report FILE

   With ``--verdicts``: print the verdicts as text and also write the JSON
   form to ``FILE``.

   .. code-block:: bash

      prover-cli --job-id JOB --verdicts --save-report certora/logs/part1.report.json

.. option:: --chain {evm,solana,soroban}

   Which call-trace frames a counterexample keeps (default ``evm``).

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

.. option:: --download-sources [DEST_DIR]

   Download the job's source files into
   ``DEST_DIR/inputs/.certora_sources/`` (``DEST_DIR`` defaults to the
   current directory), preserving the original tree structure. Files are
   fetched individually in parallel — no full-tarball download. A
   completed fetch leaves a ``.source_fetch_complete`` marker, so reruns
   are skipped. Remote jobs only.

   .. code-block:: bash

      prover-cli --job-id JOB --download-sources ./job_sources

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

.. option:: --wait TARGET [TARGET ...]

   Wait until every target has stopped, for at most ``--timeout`` seconds
   (default 90), checking every ``--interval`` seconds (default 30). A
   target is a job id, a job link, or the log of a ``certoraRun`` call
   (``*.log``, read for the last job link it printed; the file need not
   exist yet), or a glob of logs. Quote a glob, so it reaches the command
   even when nothing matches yet (zsh refuses an unmatched glob); a glob
   that matches nothing counts as one log with no job link. Prints
   ``<target> <job id> <status>`` per job, then
   ``ENDED`` or ``RUNNING``. A job has stopped when its status is
   ``SUCCEEDED``, ``FAILED``, ``CANCELED``, ``HALTED``,
   ``SERVICE_UNAVAILABLE`` or ``UPLOAD_FAILED``. ``CHECK_FAILED`` means the
   status request failed and does not end the wait.

   With ``--pid-file FILE`` naming the process that submits the logged
   jobs, a log with no job link is ``SUBMITTING`` while that process runs
   and ``NOT_SUBMITTED`` once it has exited, and the wait does not end
   while it runs. Keep ``--timeout`` under the timeout of whatever runs
   the command, and call it again on ``RUNNING``.

   .. code-block:: bash

      prover-cli --wait 'certora/logs/spec-p*_run3.log' \
          --pid-file certora/logs/spec_run3.pid --timeout 90

.. option:: --budget LOGS_DIR

   Prover jobs and minutes used by the job links in ``LOGS_DIR/*.log``,
   against ``--max-jobs``/``--max-minutes`` or ``LOGS_DIR/budget.json``
   (``{"jobs": N, "minutes": M}``), with the use per log group. A log's
   group is its name without a trailing ``_run<N>`` (or ``_r<M>run<N>``)
   and then a trailing ``-p<K>``: ``spec-p2_run3.log`` and
   ``spec_run1.log`` are both group ``spec``. A finished job counts its
   runtime on the server, rounded up to whole minutes; a job not yet
   finished counts ``--reserve-minutes`` (default 30) or its time so far
   if larger, so it can end up costing more than it was counted at.
   Finished jobs are cached in ``LOGS_DIR/.budget_cache.json``. With
   ``--more-jobs K``, exits ``3`` unless ``K`` more jobs fit (one job and
   ``--reserve-minutes`` each).

   .. code-block:: bash

      prover-cli --budget certora/logs --more-jobs 3

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

   **Deprecated.** Legacy Certora API key. Authentication now uses ``certora_login``
   cookie login (interactive) or AWS SigV4 in CI; ``CERTORAKEY`` should not be relied on.

.. envvar:: PROVER_OUTPUT_CACHE_DIR

   Override the default cache directory for API responses.

   .. code-block:: bash

      export PROVER_OUTPUT_CACHE_DIR=/tmp/prover_cache
      prover-cli --job-id 67890

Authentication Errors
---------------------

If the CLI reports an authentication failure, refresh your session:

.. code-block:: bash

   certora-cloud login

Local Mode Limitations
----------------------

When using ``--local-path``, the following commands are not available
(they hit the data API):

- ``--recent-jobs``
- ``--cancel``
- ``--who-am-i``
- ``--download-sources``
