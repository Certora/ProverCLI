ProverCLI Documentation
==================================

A Python API for parsing outputs from the Certora Prover. This utility provides an easy-to-use interface for fetching and parsing prover verification results using either job URLs or job IDs.

.. image:: https://github.com/Certora/ProverCLI/workflows/CI/badge.svg
   :target: https://github.com/Certora/ProverCLI/actions
   :alt: CI Status

.. image:: https://img.shields.io/badge/python-3.10+-blue.svg
   :target: https://www.python.org/downloads/
   :alt: Python 3.10+

.. image:: https://img.shields.io/badge/License-GPLv3-blue.svg
   :target: https://www.gnu.org/licenses/gpl-3.0
   :alt: License: GPL v3

Features
--------

- **Flexible Input**: Accepts both job URLs (format: ``/output/user_id/job_id``) and job IDs
- **Simple Authentication**: Uses ``cert_cli_login`` for authentication
- **Comprehensive Parsing**: Extracts job info, verification results, rule details, and statistics
- **Error Handling**: Robust error handling with custom exceptions
- **Type Safety**: Full type hints for better development experience
- **Caching**: Built-in persistent caching for improved performance
- **Local Support**: Can work with local ``emv-*`` folders

Contents
--------

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   installation
   quickstart
   examples
   authentication

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   api/prover_output_api
   api/models
   api/exceptions
   api/utilities

.. toctree::
   :maxdepth: 1
   :caption: Additional Information

   cli
   caching
   changelog

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
