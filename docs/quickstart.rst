Quick Start
===========

This guide will help you get started with ProverCLI.

Basic Usage
-----------

Initialize the API
^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from prover_output_utility import ProverOutputAPI

   # Initialize the API (authenticates automatically via certora_login)
   api = ProverOutputAPI()

Get Violated Rules
^^^^^^^^^^^^^^^^^^

.. code-block:: python

   # Using a job ID
   violations = api.get_violated_rules("12345678")

   # Or using a full job URL
   violations = api.get_violated_rules("https://prover.certora.com/output/12345/67890/...")

   # Print violation details
   for violation in violations:
       print(f"Rule: {violation.rule_name}")
       print(f"Method: {violation.method_name}")
       print(f"Message: {violation.assert_message}")
       print(f"Status: {violation.status}")
       print()

Get All Checks
^^^^^^^^^^^^^^

.. code-block:: python

   # Get all checks (passed and failed)
   all_checks = api.get_all_checks("12345678")

   # Filter by status
   passed = [c for c in all_checks if c.is_verified]
   failed = [c for c in all_checks if c.is_violated]

   print(f"Passed: {len(passed)}/{len(all_checks)}")
   print(f"Failed: {len(failed)}/{len(all_checks)}")

Check Job Status
^^^^^^^^^^^^^^^^

.. code-block:: python

   from prover_output_utility.models import JobStatus

   # Get job status
   status = api.get_job_status("12345678")

   if status == JobStatus.RUNNING:
       print("Job is still running...")
   elif status == JobStatus.SUCCEEDED:
       print("Job completed successfully!")

Get Job Information
^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   # Get detailed job info
   info = api.get_job_info("12345678")

   print(f"Job ID: {info.job_id}")
   print(f"Status: {info.status}")
   print(f"Started: {info.start_time}")
   print(f"Finished: {info.finish_time}")
   print(f"User: {info.user_id}")
   print(f"Project: {info.project}")

Debug with Calltraces
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   violations = api.get_violated_rules("12345678")

   for violation in violations:
       if violation.has_calltrace:
           # Get calltrace for this violation
           trace = api.get_calltrace_for_violation("12345678", violation)
           print(f"Trace for {violation.rule_name}:")
           print(f"  Frames: {trace.frame_count}")

Debug with Breadcrumbs
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   violations = api.get_violated_rules("12345678")

   for violation in violations:
       if violation.has_breadcrumbs:
           # Get breadcrumbs for this violation
           bc = api.get_breadcrumbs_for_violation("12345678", violation)
           print(f"Breadcrumbs for {violation.rule_name}:")
           print(f"  Total steps: {bc.total_steps}")
           print(f"  Function calls: {bc.function_calls}")
           print(f"  Storage operations: {bc.storage_operations}")

Command Line Usage
------------------

ProverCLI includes a command-line interface:

.. code-block:: bash

   # Get violated rules from a job
   prover-cli --job-id 67890

   # Using job URL
   prover-cli --job-url "https://prover.certora.com/output/12345/67890/..."

   # Save output to a file
   prover-cli --job-id 67890 --output violations.json

   # Get only job status
   prover-cli --job-id 67890 --status-only

   # Output as JSON
   prover-cli --job-id 67890 --format json

Error Handling
--------------

.. code-block:: python

   from prover_output_utility import ProverOutputAPI
   from prover_output_utility.exceptions import (
       JobNotFoundError,
       AuthenticationError,
       ProverAPIError
   )

   api = ProverOutputAPI()

   try:
       violations = api.get_violated_rules("12345678")
   except JobNotFoundError:
       print("Job not found - check the job ID")
   except AuthenticationError:
       print("Authentication failed - run: certora-cloud login")
   except ProverAPIError as e:
       print(f"API error: {e}")

Working with Local Files
-------------------------

If you have local ``emv-*`` folders:

.. code-block:: python

   # Initialize with local mode
   api = ProverOutputAPI(use_local=True)

   # Use local emv folder path
   violations = api.get_violated_rules("emv-12345678")

Caching
-------

Caching is enabled by default for faster repeated queries:

.. code-block:: python

   # Enable cache (default)
   api = ProverOutputAPI(enable_cache=True)

   # Check cache statistics
   print(f"Cache hits: {api.cache.hits}")
   print(f"Cache misses: {api.cache.misses}")

   # Disable cache for fresh data
   api_no_cache = ProverOutputAPI(enable_cache=False)

Next Steps
----------

- See :doc:`examples` for more advanced usage patterns
- Check :doc:`api/prover_output_api` for complete API reference
- Learn about :doc:`authentication` setup
