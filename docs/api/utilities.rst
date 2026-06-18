Utilities
=========

.. currentmodule:: prover_output_utility

This page documents utility functions and helper classes.

URL Utilities
-------------

.. currentmodule:: prover_output_utility.api.url_utils

Functions for parsing and extracting job information from URLs.

extract_job_id
^^^^^^^^^^^^^^

.. autofunction:: extract_job_id

   Extract job ID from a job URL or direct job ID string.

   **Examples:**

   .. code-block:: python

      from prover_output_utility.api.url_utils import extract_job_id

      # From URL
      job_id = extract_job_id("https://prover.certora.com/output/12345/67890/...")
      # Returns: "67890"

      # From direct ID
      job_id = extract_job_id("67890")
      # Returns: "67890"

extract_job_identifier
^^^^^^^^^^^^^^^^^^^^^^^

.. autofunction:: extract_job_identifier

   Extract job identifier and determine input type (remote or local).

   **Returns:**
      Tuple of (job_identifier, input_type) where input_type is "remote" or "local"

   **Examples:**

   .. code-block:: python

      from prover_output_utility.api.url_utils import extract_job_identifier

      # Remote job
      identifier, input_type = extract_job_identifier("12345678")
      # Returns: ("12345678", "remote")

      # Local emv folder
      identifier, input_type = extract_job_identifier("emv-12345678")
      # Returns: ("emv-12345678", "local")

extract_job_id_from_url
^^^^^^^^^^^^^^^^^^^^^^^^

.. autofunction:: extract_job_id_from_url

   Extract job ID specifically from a Certora prover URL.

   **Examples:**

   .. code-block:: python

      from prover_output_utility.api.url_utils import extract_job_id_from_url

      url = "https://prover.certora.com/output/12345/67890/index.html"
      job_id = extract_job_id_from_url(url)
      # Returns: "67890"

Parser Classes
--------------

TreeParser
^^^^^^^^^^

.. currentmodule:: prover_output_utility.api.tree_parser

.. autoclass:: TreeParser
   :members:
   :undoc-members:
   :show-inheritance:

   Parser for tree-view data structure.

   **Methods:**

   .. automethod:: parse_all_checks
   .. automethod:: parse_violations
   .. automethod:: parse_leaf_checks
   .. automethod:: parse_call_resolutions

BreadcrumbParser
^^^^^^^^^^^^^^^^

.. currentmodule:: prover_output_utility.breadcrumb

.. autoclass:: BreadcrumbParser
   :members:
   :undoc-members:
   :show-inheritance:

   Parser for breadcrumb trace data (DAP files).

   **Methods:**

   .. automethod:: parse_dap_file

OutputParser
^^^^^^^^^^^^

.. currentmodule:: prover_output_utility.parsers

.. autoclass:: OutputParser
   :members:
   :undoc-members:
   :show-inheritance:

   Parser for general prover output.

   **Methods:**

   .. automethod:: parse

Caching
-------

.. currentmodule:: prover_output_utility.api.cache

APICache
^^^^^^^^

.. autoclass:: APICache
   :members:
   :undoc-members:
   :show-inheritance:

   Persistent cache for API responses.

   **Attributes:**

   .. attribute:: hits
      :type: int

      Number of cache hits.

   .. attribute:: misses
      :type: int

      Number of cache misses.

   .. attribute:: cache_dir
      :type: Path

      Directory where cache files are stored.

   **Methods:**

   .. automethod:: __init__
   .. automethod:: get
   .. automethod:: set

   **Example:**

   .. code-block:: python

      from prover_output_utility import ProverOutputAPI

      # Cache is enabled by default
      api = ProverOutputAPI(enable_cache=True)

      # Make some requests
      api.get_violated_rules("12345678")
      api.get_violated_rules("12345678")  # This will be cached

      # Check cache statistics
      print(f"Cache hits: {api.cache.hits}")
      print(f"Cache misses: {api.cache.misses}")
      print(f"Cache directory: {api.cache.cache_dir}")

Authentication
--------------

.. currentmodule:: prover_output_utility.auth

ProverAuth
^^^^^^^^^^

.. autoclass:: ProverAuth
   :members:
   :undoc-members:
   :show-inheritance:

   Handles authentication via certora_login.

   **Methods:**

   .. automethod:: __init__
   .. automethod:: delete_stored_credentials

AWSAuth
^^^^^^^

.. currentmodule:: prover_output_utility.aws_auth

.. autoclass:: AWSAuth
   :members:
   :undoc-members:
   :show-inheritance:

   Handles AWS authentication for CI environments.
