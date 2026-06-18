Authentication
==============

ProverCLI authenticates with the Certora Prover API using ``certora_login`` (provided by the
``certora-cloud`` dependency). Login happens **automatically** the first time you construct
``ProverOutputAPI()`` — it opens a browser PKCE flow when no valid session is stored, then caches
the credentials. You can also pre-authenticate from the shell with ``certora-cloud login``.

Setup
-----

1. **Install ProverCLI** (the ``certora_login`` tooling ships with it via the ``certora-cloud`` dependency — no separate install needed):

   .. code-block:: bash

      pip install prover-cli

2. **(Optional) Pre-authenticate** — otherwise this happens automatically on first API use:

   .. code-block:: bash

      certora-cloud login

   This authenticates you with the Certora service and stores your credentials securely.

3. **Verify authentication**:

   .. code-block:: python

      from prover_output_utility import ProverOutputAPI

      api = ProverOutputAPI()
      user_info = api.who_am_i()
      print(f"Authenticated as: {user_info}")

Authentication in Code
----------------------

Default Authentication
^^^^^^^^^^^^^^^^^^^^^^

By default, ``ProverOutputAPI()`` authenticates automatically via ``certora_login`` (logging in on
first use if needed):

.. code-block:: python

   from prover_output_utility import ProverOutputAPI

   # Triggers certora_login automatically on first use
   api = ProverOutputAPI()

Deprecated: CERTORAKEY
^^^^^^^^^^^^^^^^^^^^^^

The ``certora_key`` parameter is deprecated and should not be used:

.. code-block:: python

   # DEPRECATED - Do not use
   api = ProverOutputAPI(certora_key="your-key")

   # PREFERRED - automatic certora_login
   api = ProverOutputAPI()

Handling Authentication Errors
-------------------------------

If authentication fails, you'll receive an ``AuthenticationError``:

.. code-block:: python

   from prover_output_utility import ProverOutputAPI
   from prover_output_utility.exceptions import AuthenticationError

   api = ProverOutputAPI()

   try:
       violations = api.get_violated_rules("12345678")
   except AuthenticationError as e:
       print("Authentication failed!")
       print("Please run: certora-cloud login")
       print(f"Error details: {e}")

Re-authenticating
-----------------

If your credentials expire or you need to switch accounts, log in again:

.. code-block:: bash

   certora-cloud login

CI/CD Environments
------------------

For CI/CD pipelines, authentication is typically handled via environment variables or service accounts. Consult your CI/CD platform documentation for setting up Certora authentication.

Example GitHub Actions workflow:

.. code-block:: yaml

   name: Verify Contracts

   on: [push, pull_request]

   jobs:
     verify:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4

         - name: Set up Python
           uses: actions/setup-python@v5
           with:
             python-version: '3.12'

         - name: Install dependencies
           run: pip install prover-cli

         - name: Run verification
           run: python verify_script.py
           env:
             # In CI, authentication uses AWS SigV4 via the runner's configured
             # AWS credentials (no interactive login / API key needed).
             CI: "true"

Checking Current User
---------------------

To check which user you're authenticated as:

.. code-block:: python

   from prover_output_utility import ProverOutputAPI

   api = ProverOutputAPI()
   user_info = api.who_am_i()

   print(f"User ID: {user_info.get('user_id')}")
   print(f"Email: {user_info.get('email')}")
   print(f"Organization: {user_info.get('organization')}")

Security Best Practices
-----------------------

1. **Never commit credentials**: Don't hardcode API keys or credentials in your code
2. **Use certora_login**: Prefer the official authentication method (``certora-cloud login`` / automatic login)
3. **Rotate credentials**: Periodically rotate your Certora credentials
4. **Use environment-specific credentials**: Use different credentials for development, staging, and production
5. **Limit scope**: Use credentials with minimal required permissions

Troubleshooting
---------------

Authentication fails with "Invalid credentials"
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

1. Ensure you've logged in (``certora-cloud login``)
2. Try logging in again to refresh your session:

   .. code-block:: bash

      certora-cloud login

3. Check that you have valid Certora account access

Cannot access jobs
^^^^^^^^^^^^^^^^^^

Make sure you have permission to access the specific job:

- You must be the owner of the job, or
- The job must be from a project you have access to

.. code-block:: python

   from prover_output_utility import ProverOutputAPI
   from prover_output_utility.exceptions import JobNotFoundError

   api = ProverOutputAPI()

   try:
       violations = api.get_violated_rules("12345678")
   except JobNotFoundError:
       print("Job not found or you don't have permission to access it")
