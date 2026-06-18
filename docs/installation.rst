Installation
============

Requirements
------------

- Python 3.12 or higher
- pip package manager

Install from PyPI
-----------------

The package is published on PyPI as ``certora-prover-cli``:

.. code-block:: bash

   pip install certora-prover-cli

The Python import package is ``prover_output_utility`` (e.g.
``from prover_output_utility import ProverOutputAPI``).

Using requirements.txt / pyproject.toml
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   # requirements.txt
   certora-prover-cli

.. code-block:: toml

   # pyproject.toml
   dependencies = [
       "certora-prover-cli",
   ]

Install from source (development)
---------------------------------

.. code-block:: bash

   git clone https://github.com/Certora/ProverCLI.git
   cd ProverCLI
   pip install -e .          # editable install

The editable mode (``-e``) reflects code changes without reinstalling.

Development Dependencies
------------------------

.. code-block:: bash

   pip install -e .[dev]

This includes ``build`` (packaging) and ``reuse`` (license-header linting).

Verifying Installation
----------------------

To verify the installation was successful:

.. code-block:: bash

   # Check CLI tool is available
   prover-cli --help

   # Or import in Python
   python -c "from prover_output_utility import ProverOutputAPI; print('Installation successful!')"
