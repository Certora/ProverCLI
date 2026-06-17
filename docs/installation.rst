Installation
============

Requirements
------------

- Python 3.10 or higher
- pip package manager

Local Development Installation
-------------------------------

To install this package locally for development:

.. code-block:: bash

   # Clone the repository
   git clone https://github.com/Certora/ProverCLI.git
   cd ProverCLI

   # Install in editable mode (recommended for development)
   pip install -e .

   # Or install without editable mode
   pip install .

The editable mode (``-e``) allows you to make changes to the code and have them immediately reflected without reinstalling.

Installing in Another Project
------------------------------

To use this package in another Python project, you can install it directly from the git repository:

.. code-block:: bash

   # Install from GitHub via HTTPS
   pip install git+https://github.com/Certora/ProverCLI.git

   # Install a specific branch or tag
   pip install git+https://github.com/Certora/ProverCLI.git@branch-name

Using requirements.txt
^^^^^^^^^^^^^^^^^^^^^^

Add to your project's ``requirements.txt``:

.. code-block:: text

   git+https://github.com/Certora/ProverCLI.git

Using pyproject.toml
^^^^^^^^^^^^^^^^^^^^

Add to your ``pyproject.toml``:

.. code-block:: toml

   dependencies = [
       "prover-output-utility @ git+https://github.com/Certora/ProverCLI.git",
   ]

Development Dependencies
------------------------

To install development dependencies for testing and documentation:

.. code-block:: bash

   pip install -e .[dev]

This includes:

- pytest for testing
- sphinx for documentation
- black and isort for code formatting
- mypy for type checking

Verifying Installation
----------------------

To verify the installation was successful:

.. code-block:: bash

   # Check CLI tool is available
   prover-cli --help

   # Or import in Python
   python -c "from prover_output_utility import ProverOutputAPI; print('Installation successful!')"
