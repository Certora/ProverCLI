Caching
=======

ProverCLI includes a built-in caching system to improve performance by storing API responses locally.

Overview
--------

The caching system:

- **Automatically caches** API responses to disk
- **Reduces network calls** for repeated queries
- **Speeds up development** by reusing previously fetched data
- **Is transparent** - works without code changes
- **Is persistent** - survives across sessions

By default, caching is **enabled**.

Basic Usage
-----------

Enable Cache (Default)
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from prover_output_utility import ProverOutputAPI

   # Cache is enabled by default
   api = ProverOutputAPI()

   # First call fetches from API and caches
   violations = api.get_violated_rules("12345678")

   # Second call uses cache (much faster!)
   violations = api.get_violated_rules("12345678")

Disable Cache
^^^^^^^^^^^^^

.. code-block:: python

   # Disable cache for fresh data
   api = ProverOutputAPI(enable_cache=False)

   # Every call fetches fresh data from API
   violations = api.get_violated_rules("12345678")

Cache Statistics
----------------

Track cache performance:

.. code-block:: python

   api = ProverOutputAPI(enable_cache=True)

   # Make some requests
   api.get_violated_rules("12345678")
   api.get_all_checks("12345678")
   api.get_violated_rules("12345678")  # Cache hit!

   # Check statistics
   print(f"Cache hits: {api.cache.hits}")
   print(f"Cache misses: {api.cache.misses}")
   print(f"Hit rate: {api.cache.hits / (api.cache.hits + api.cache.misses) * 100:.1f}%")

Cache Location
--------------

Default Location
^^^^^^^^^^^^^^^^

The cache is stored in:

- **Linux/Mac:** ``~/.prover_output_cache/``
- **Windows:** ``%USERPROFILE%\.prover_output_cache\``

Check the cache directory:

.. code-block:: python

   api = ProverOutputAPI()
   print(f"Cache directory: {api.cache.cache_dir}")

Custom Location
^^^^^^^^^^^^^^^

Set a custom cache directory:

.. code-block:: python

   from prover_output_utility.api.cache import APICache
   from prover_output_utility import ProverOutputAPI

   # Create custom cache
   custom_cache = APICache(cache_dir="/tmp/my_prover_cache")

   # Note: You'll need to set this on the data fetcher
   # For most users, using the default cache is recommended

Or use environment variable:

.. code-block:: bash

   export PROVER_OUTPUT_CACHE_DIR=/tmp/my_prover_cache
   python my_script.py

Cache Behavior
--------------

What Gets Cached
^^^^^^^^^^^^^^^^

The following API calls are cached:

- ``get_violated_rules()``
- ``get_all_checks()``
- ``get_leaf_checks()``
- ``get_call_resolutions()``
- ``get_calltrace()``
- ``get_breadcrumbs()``
- ``get_job_info()``
- ``get_tree_view_data()``
- ``get_statsdata()``
- ``get_console_logs()``
- ``get_alert_report()``
- ``download_job_outputs()``

What Doesn't Get Cached
^^^^^^^^^^^^^^^^^^^^^^^^

These operations always hit the API:

- ``get_job_status()`` - Status may change
- ``is_job_running()`` - Status may change
- ``list_recent_jobs()`` - Results change over time
- ``cancel_job()`` - Write operation
- ``who_am_i()`` - User info may change

Cache Keys
^^^^^^^^^^

Cache keys are based on:

- Method name
- Job identifier
- Additional parameters (e.g., output file name)

This means:

.. code-block:: python

   api = ProverOutputAPI()

   # These create separate cache entries
   api.get_violated_rules("12345678")
   api.get_violated_rules("87654321")

   # These use the same cache entry
   api.get_violated_rules("12345678")
   api.get_violated_rules("12345678")

Managing Cache
--------------

Clear Cache
^^^^^^^^^^^

To clear the cache, delete the cache directory:

.. code-block:: bash

   # Linux/Mac
   rm -rf ~/.prover_output_cache/

   # Windows
   rmdir /s %USERPROFILE%\.prover_output_cache

Or programmatically:

.. code-block:: python

   import shutil
   from prover_output_utility import ProverOutputAPI

   api = ProverOutputAPI()
   cache_dir = api.cache.cache_dir

   # Clear cache
   shutil.rmtree(cache_dir, ignore_errors=True)
   print(f"Cleared cache at {cache_dir}")

Check Cache Size
^^^^^^^^^^^^^^^^

.. code-block:: python

   import os
   from prover_output_utility import ProverOutputAPI

   def get_dir_size(path):
       total = 0
       for dirpath, dirnames, filenames in os.walk(path):
           for filename in filenames:
               filepath = os.path.join(dirpath, filename)
               total += os.path.getsize(filepath)
       return total

   api = ProverOutputAPI()
   cache_size = get_dir_size(api.cache.cache_dir)
   print(f"Cache size: {cache_size / 1024 / 1024:.2f} MB")

Performance Tips
----------------

Development vs Production
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   import os

   # Enable cache in development for faster iteration
   if os.getenv('ENV') == 'development':
       api = ProverOutputAPI(enable_cache=True)
   else:
       # Disable in production for fresh data
       api = ProverOutputAPI(enable_cache=False)

Bulk Downloads
^^^^^^^^^^^^^^

When downloading multiple jobs, cache provides significant speedup:

.. code-block:: python

   from prover_output_utility import ProverOutputAPI

   api = ProverOutputAPI(enable_cache=True)
   job_ids = ["12345678", "87654321", "11111111"]

   for job_id in job_ids:
       # First run: fetches from API
       # Subsequent runs: uses cache
       violations = api.get_violated_rules(job_id)
       print(f"Job {job_id}: {len(violations)} violations")

   print(f"Cache hits: {api.cache.hits}")
   print(f"Cache misses: {api.cache.misses}")

Testing with Cache
^^^^^^^^^^^^^^^^^^

For tests, you might want fresh data:

.. code-block:: python

   import pytest
   from prover_output_utility import ProverOutputAPI

   @pytest.fixture
   def api():
       # Disable cache in tests
       return ProverOutputAPI(enable_cache=False)

   def test_violations(api):
       violations = api.get_violated_rules("12345678")
       assert len(violations) > 0

Cache Implementation
--------------------

The cache uses:

- **JSON files** for storage
- **SHA256 hashing** for cache keys
- **Filesystem-based** persistence

Example cache file structure:

.. code-block:: text

   ~/.prover_output_cache/
   ├── get_violated_rules_12345678.json
   ├── get_all_checks_12345678.json
   ├── get_calltrace_12345678_rule1.json
   └── ...

Advanced Usage
--------------

Custom Cache Implementation
^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can implement your own cache by subclassing ``APICache``:

.. code-block:: python

   from prover_output_utility.api.cache import APICache
   import redis

   class RedisCache(APICache):
       def __init__(self):
           self.redis = redis.Redis(host='localhost', port=6379, db=0)
           self.hits = 0
           self.misses = 0

       def get(self, method, *args):
           key = self._make_key(method, *args)
           data = self.redis.get(key)

           if data:
               self.hits += 1
               return json.loads(data)
           else:
               self.misses += 1
               return None

       def set(self, method, data, *args):
           key = self._make_key(method, *args)
           self.redis.set(key, json.dumps(data))

       def _make_key(self, method, *args):
           return f"{method}:{':'.join(str(a) for a in args)}"

Troubleshooting
---------------

Cache Not Working
^^^^^^^^^^^^^^^^^

**Problem:** Cache statistics show only misses, no hits.

**Possible causes:**

1. Cache is disabled: ``ProverOutputAPI(enable_cache=False)``
2. Different parameters being used
3. Cache directory permissions issue

**Solution:**

.. code-block:: python

   api = ProverOutputAPI(enable_cache=True)
   print(f"Cache enabled: {hasattr(api, 'cache')}")
   print(f"Cache directory: {api.cache.cache_dir}")

   # Check permissions
   import os
   cache_dir = api.cache.cache_dir
   print(f"Cache dir writable: {os.access(cache_dir, os.W_OK)}")

Stale Cache Data
^^^^^^^^^^^^^^^^

**Problem:** Getting outdated results from cache.

**Solution:**

Clear the cache or disable caching:

.. code-block:: python

   # Option 1: Disable cache temporarily
   api = ProverOutputAPI(enable_cache=False)

   # Option 2: Clear and rebuild cache
   import shutil
   shutil.rmtree(api.cache.cache_dir, ignore_errors=True)
   api = ProverOutputAPI(enable_cache=True)
