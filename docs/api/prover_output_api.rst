ProverOutputAPI
===============

.. currentmodule:: prover_output_utility

.. autoclass:: ProverOutputAPI
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

Main API Class
--------------

The :class:`ProverOutputAPI` class is the main entry point for interacting with Certora Prover outputs.

Constructor
^^^^^^^^^^^

.. automethod:: ProverOutputAPI.__init__

Core Data Fetching Methods
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. automethod:: ProverOutputAPI.get_violated_rules
.. automethod:: ProverOutputAPI.get_all_checks
.. automethod:: ProverOutputAPI.get_leaf_checks
.. automethod:: ProverOutputAPI.get_call_resolutions
.. automethod:: ProverOutputAPI.get_job_report
.. automethod:: ProverOutputAPI.fetch_output

Trace and Debug Methods
^^^^^^^^^^^^^^^^^^^^^^^^

.. automethod:: ProverOutputAPI.get_calltrace
.. automethod:: ProverOutputAPI.get_calltrace_for_violation
.. automethod:: ProverOutputAPI.get_breadcrumbs
.. automethod:: ProverOutputAPI.get_breadcrumbs_for_violation

Job Information Methods
^^^^^^^^^^^^^^^^^^^^^^^^

.. automethod:: ProverOutputAPI.get_job_status
.. automethod:: ProverOutputAPI.get_job_info
.. automethod:: ProverOutputAPI.is_job_running
.. automethod:: ProverOutputAPI.get_tree_view_data

Job Management Methods
^^^^^^^^^^^^^^^^^^^^^^

.. automethod:: ProverOutputAPI.list_recent_jobs
.. automethod:: ProverOutputAPI.cancel_job
.. automethod:: ProverOutputAPI.cancel_jobs

Data Retrieval Methods
^^^^^^^^^^^^^^^^^^^^^^^

.. automethod:: ProverOutputAPI.get_statsdata
.. automethod:: ProverOutputAPI.get_console_logs
.. automethod:: ProverOutputAPI.get_alert_report
.. automethod:: ProverOutputAPI.who_am_i

Rule Hierarchy and Advanced Methods
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. automethod:: ProverOutputAPI.parse_tree_view_path
.. automethod:: ProverOutputAPI.get_rule_hierarchy
.. automethod:: ProverOutputAPI.download_job_outputs
.. automethod:: ProverOutputAPI.fetch_custom_endpoint
