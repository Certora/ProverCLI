Authentication
==============

ProverCLI uses ``cert_cli_login`` for authentication with the Certora Prover API.

Setup
-----

1. **Install Certora CLI** (if not already installed):

   .. code-block:: bash

      pip install certora-cli

2. **Login using cert_cli_login**:

   .. code-block:: bash

      cert_cli_login

   This will authenticate you with the Certora service and store your credentials securely.

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

By default, ProverCLI uses the credentials from ``cert_cli_login``:

.. code-block:: python

   from prover_output_utility import ProverOutputAPI

   # Automatically uses cert_cli_login credentials
   api = ProverOutputAPI()

Deprecated: CERTORAKEY
^^^^^^^^^^^^^^^^^^^^^^

The ``certora_key`` parameter is deprecated and should not be used:

.. code-block:: python

   # DEPRECATED - Do not use
   api = ProverOutputAPI(certora_key="your-key")

   # PREFERRED - Use cert_cli_login instead
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
       print("Please run: cert_cli_login")
       print(f"Error details: {e}")

Re-authenticating
-----------------

If your credentials expire or you need to switch accounts:

.. code-block:: bash

   # Logout
   cert_cli_logout

   # Login again
   cert_cli_login

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
         - uses: actions/checkout@v2

         - name: Set up Python
           uses: actions/setup-python@v2
           with:
             python-version: '3.10'

         - name: Install dependencies
           run: |
             pip install certora-cli
             pip install git+https://github.com/Certora/ProverCLI.git

         - name: Authenticate
           run: cert_cli_login
           env:
             CERTORA_KEY: ${{ secrets.CERTORA_KEY }}

         - name: Run verification
           run: python verify_script.py

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
2. **Use cert_cli_login**: Prefer the official authentication method
3. **Rotate credentials**: Periodically rotate your Certora credentials
4. **Use environment-specific credentials**: Use different credentials for development, staging, and production
5. **Limit scope**: Use credentials with minimal required permissions

Troubleshooting
---------------

Authentication fails with "Invalid credentials"
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

1. Ensure you've run ``cert_cli_login``
2. Try logging out and back in:

   .. code-block:: bash

      cert_cli_logout
      cert_cli_login

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
