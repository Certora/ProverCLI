Exceptions
==========

.. currentmodule:: prover_output_utility.exceptions

ProverCLI defines a hierarchy of custom exceptions for error handling.

Exception Hierarchy
-------------------

All exceptions inherit from :class:`ProverAPIError`.

::

    ProverAPIError
    ├── AuthenticationError
    ├── JobNotFoundError
    ├── ParseError
    ├── InvalidJobError
    └── APITimeoutError

Exception Classes
-----------------

ProverAPIError
^^^^^^^^^^^^^^

.. autoexception:: ProverAPIError
   :members:
   :show-inheritance:

   Base exception class for all ProverCLI errors.

AuthenticationError
^^^^^^^^^^^^^^^^^^^

.. autoexception:: AuthenticationError
   :members:
   :show-inheritance:

   Raised when authentication with the Certora Prover API fails.

   **Common causes:**

   - Not logged in via ``cert_cli_login``
   - Invalid or expired credentials
   - Missing authentication tokens

   **Resolution:**

   Run ``cert_cli_login`` to authenticate.

JobNotFoundError
^^^^^^^^^^^^^^^^

.. autoexception:: JobNotFoundError
   :members:
   :show-inheritance:

   Raised when a job cannot be found or is not accessible.

   **Common causes:**

   - Invalid job ID
   - Job doesn't exist
   - User doesn't have permission to access the job
   - Job was deleted

InvalidJobError
^^^^^^^^^^^^^^^

.. autoexception:: InvalidJobError
   :members:
   :show-inheritance:

   Raised when the job input format is invalid.

   **Common causes:**

   - Malformed job URL
   - Invalid job ID format
   - Empty or null job input

ParseError
^^^^^^^^^^

.. autoexception:: ParseError
   :members:
   :show-inheritance:

   Raised when parsing prover output fails.

   **Common causes:**

   - Corrupted output data
   - Unexpected output format
   - Missing required fields in output

APITimeoutError
^^^^^^^^^^^^^^^

.. autoexception:: APITimeoutError
   :members:
   :show-inheritance:

   Raised when an API request times out.

   **Common causes:**

   - Network connectivity issues
   - Server overload
   - Large job output taking too long to fetch

   **Resolution:**

   Retry the request after a short delay.

Usage Examples
--------------

Basic Error Handling
^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from prover_output_utility import ProverOutputAPI
   from prover_output_utility.exceptions import ProverAPIError

   api = ProverOutputAPI()

   try:
       violations = api.get_violated_rules("12345678")
   except ProverAPIError as e:
       print(f"Error occurred: {e}")

Specific Exception Handling
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from prover_output_utility import ProverOutputAPI
   from prover_output_utility.exceptions import (
       AuthenticationError,
       JobNotFoundError,
       InvalidJobError,
       APITimeoutError,
       ParseError
   )

   api = ProverOutputAPI()

   try:
       violations = api.get_violated_rules("12345678")

   except AuthenticationError:
       print("Authentication failed - please run cert_cli_login")

   except JobNotFoundError:
       print("Job not found - check the job ID and your permissions")

   except InvalidJobError:
       print("Invalid job ID format")

   except APITimeoutError:
       print("Request timed out - please try again")

   except ParseError:
       print("Failed to parse job output - output may be corrupted")

Retry Logic with Timeout
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   import time
   from prover_output_utility import ProverOutputAPI
   from prover_output_utility.exceptions import APITimeoutError

   api = ProverOutputAPI()

   max_retries = 3
   retry_delay = 5  # seconds

   for attempt in range(max_retries):
       try:
           violations = api.get_violated_rules("12345678")
           print(f"Successfully retrieved {len(violations)} violations")
           break

       except APITimeoutError:
           if attempt < max_retries - 1:
               print(f"Timeout on attempt {attempt + 1}, retrying in {retry_delay}s...")
               time.sleep(retry_delay)
           else:
               print("Max retries reached, giving up")
               raise

Graceful Degradation
^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from prover_output_utility import ProverOutputAPI
   from prover_output_utility.exceptions import JobNotFoundError, ParseError

   api = ProverOutputAPI()
   job_ids = ["12345678", "87654321", "11111111"]

   results = []
   for job_id in job_ids:
       try:
           violations = api.get_violated_rules(job_id)
           results.append({
               'job_id': job_id,
               'status': 'success',
               'violations': len(violations)
           })

       except JobNotFoundError:
           results.append({
               'job_id': job_id,
               'status': 'not_found',
               'violations': None
           })

       except ParseError:
           results.append({
               'job_id': job_id,
               'status': 'parse_error',
               'violations': None
           })

   # Continue with available results
   successful = [r for r in results if r['status'] == 'success']
   print(f"Successfully analyzed {len(successful)}/{len(job_ids)} jobs")
