# ProverCLI Documentation

This directory contains the official Sphinx documentation for ProverCLI.

The documentation is written in reStructuredText and built with Sphinx. There is no hosted
build — build it locally with the steps below (or wire it to GitHub Pages, see *Publishing*).

## Building the Documentation Locally

### Prerequisites

Install Sphinx and the required theme:

```bash
pip install sphinx sphinx-rtd-theme
```

Or install from the requirements file:

```bash
pip install -r docs/requirements.txt
```

### Build HTML Documentation

From the project root directory:

```bash
# Build HTML docs
make -C docs html

# Or from within the docs directory:
cd docs
make html
```

The generated HTML documentation will be in `docs/_build/html/`.

### View Documentation

Open the documentation in your browser:

```bash
# macOS
open docs/_build/html/index.html

# Linux
xdg-open docs/_build/html/index.html

# Windows
start docs/_build/html/index.html
```

Or use Python's built-in HTTP server:

```bash
cd docs/_build/html
python -m http.server 8000
```

Then navigate to http://localhost:8000 in your browser.

### Clean Build

To remove build artifacts and rebuild from scratch:

```bash
make -C docs clean
make -C docs html
```

## Documentation Structure

- `index.rst` - Main documentation page
- `installation.rst` - Installation guide
- `quickstart.rst` - Quick start tutorial
- `examples.rst` - Usage examples
- `authentication.rst` - Authentication setup
- `api/` - API reference (auto-generated)
  - `prover_output_api.rst` - Main API class
  - `models.rst` - Data models and enums
  - `exceptions.rst` - Exception classes
  - `utilities.rst` - Utility functions and parsers
- `cli.rst` - Command-line interface
- `caching.rst` - Caching documentation
- `changelog.rst` - Version history

## Editing Documentation

The documentation uses reStructuredText (RST) format. Key features:

### Code Blocks

\`\`\`rst
.. code-block:: python

   from prover_output_utility import ProverOutputAPI
   api = ProverOutputAPI()
\`\`\`

### Cross-references

\`\`\`rst
See :class:`ProverOutputAPI` for details.
\`\`\`

### API Documentation

API documentation is automatically generated from docstrings using Sphinx autodoc:

\`\`\`rst
.. autoclass:: ProverOutputAPI
   :members:
\`\`\`

## Publishing Documentation

### GitHub Pages

To publish to GitHub Pages:

```bash
# Build docs
make -C docs html

# Create gh-pages branch (first time only)
git checkout --orphan gh-pages
git rm -rf .
touch .nojekyll

# Copy built docs
cp -r docs/_build/html/* .

# Commit and push
git add .
git commit -m "Update documentation"
git push origin gh-pages
```

## Troubleshooting

### Module Import Errors

If you see import errors when building docs, ensure the package is installed:

```bash
pip install -e .
```

### Missing Dependencies

If Sphinx or the theme is not found:

```bash
pip install sphinx sphinx-rtd-theme
```

### Build Warnings

Some warnings about duplicate object descriptions are expected due to the documentation structure. These don't affect the final output.

## Resources

- [Sphinx Documentation](https://www.sphinx-doc.org/)
- [reStructuredText Primer](https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html)
- [Read the Docs Theme](https://sphinx-rtd-theme.readthedocs.io/)
