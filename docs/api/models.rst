Data Models
===========

.. currentmodule:: prover_output_utility.models

This page documents all data models and enumerations used in ProverCLI.

Data Classes
------------

CheckResult
^^^^^^^^^^^

.. autoclass:: CheckResult
   :members:
   :undoc-members:
   :show-inheritance:

CallResolutionInfo
^^^^^^^^^^^^^^^^^^

.. autoclass:: CallResolutionInfo
   :members:
   :undoc-members:
   :show-inheritance:

CalltraceInfo
^^^^^^^^^^^^^

.. autoclass:: CalltraceInfo
   :members:
   :undoc-members:
   :show-inheritance:

BreadcrumbInfo
^^^^^^^^^^^^^^

.. autoclass:: BreadcrumbInfo
   :members:
   :undoc-members:
   :show-inheritance:

JobInfo
^^^^^^^

.. autoclass:: JobInfo
   :members:
   :undoc-members:
   :show-inheritance:

TreeViewData
^^^^^^^^^^^^

.. autoclass:: TreeViewData
   :members:
   :undoc-members:
   :show-inheritance:

SourceLocation
^^^^^^^^^^^^^^

.. autoclass:: SourceLocation
   :members:
   :undoc-members:
   :show-inheritance:

Enumerations
------------

NodeStatus
^^^^^^^^^^

.. autoclass:: NodeStatus
   :members:
   :undoc-members:
   :show-inheritance:

   Status of a verification node.

   .. attribute:: VIOLATED

      The check was violated (failed).

   .. attribute:: VERIFIED

      The check was verified (passed).

   .. attribute:: TIMEOUT

      The check timed out.

   .. attribute:: ERROR

      The check encountered an error.

   .. attribute:: RUNNING

      The check is currently running.

   .. attribute:: PENDING

      The check is pending execution.

   .. attribute:: UNKNOWN

      Unknown or unrecognized status.

JobStatus
^^^^^^^^^

.. autoclass:: JobStatus
   :members:
   :undoc-members:
   :show-inheritance:

   Status of a verification job.

   **Success statuses:**

   .. attribute:: SUCCEEDED

      Job completed successfully.

   **Failure statuses:**

   .. attribute:: FAILED

      Job failed.

   .. attribute:: CANCELED

      Job was canceled by user.

   .. attribute:: HALTED

      Job was halted.

   .. attribute:: SERVICE_UNAVAILABLE

      Service was unavailable.

   .. attribute:: UPLOAD_FAILED

      Upload failed.

   **In-progress statuses:**

   .. attribute:: POSTED

      Job has been posted.

   .. attribute:: QUEUED

      Job is queued for execution.

   .. attribute:: RUNNABLE

      Job is runnable.

   .. attribute:: STARTING

      Job is starting.

   .. attribute:: RUNNING

      Job is currently running.

   **Other:**

   .. attribute:: UNKNOWN

      Unknown or unrecognized status.

AssertType
^^^^^^^^^^

.. autoclass:: AssertType
   :members:
   :undoc-members:
   :show-inheritance:

   Type of assertion in a verification check.

   .. attribute:: CONTRACT_RECURSION_LIMIT

      Contract recursion limit assertion.

   .. attribute:: SUMMARY_RECURSION_LIMIT

      Summary recursion limit assertion.

   .. attribute:: HASHING_BOUND_ASSERTION

      Hashing bound assertion.

   .. attribute:: LOOP_BOUND_ASSERTION

      Loop bound assertion.

   .. attribute:: SANITY_ASSERTION

      Sanity check assertion.

   .. attribute:: UNKNOWN

      Unknown or unrecognized assertion type.

Helper Functions
----------------

convert_job_status
^^^^^^^^^^^^^^^^^^

.. autofunction:: convert_job_status
