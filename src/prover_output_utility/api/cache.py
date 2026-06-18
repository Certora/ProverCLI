# SPDX-FileCopyrightText: 2026 Certora Ltd.
#
# SPDX-License-Identifier: GPL-3.0-only

"""
Persistent cache for API responses to avoid repeated expensive API calls.
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional


class APICache:
    """
    Persistent file-based cache for API responses.
    Caches breadcrumb data and other expensive API calls to disk.
    Job data is immutable, so cached data never expires.
    """
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize the API cache.
        
        Args:
            cache_dir: Directory to store cache files. Defaults to .certora_internal/api_cache in current directory
        """
        self.logger = logging.getLogger(__name__)
        
        # Set cache directory - use current working directory by default
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path.cwd() / ".certora_internal" / "api_cache"
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Track cache statistics
        self.hits = 0
        self.misses = 0
        
        self.logger.debug(f"API cache initialized at {self.cache_dir}")
    
    def _get_cache_key(self, method: str, *args) -> str:
        """Generate a cache key from method name and arguments."""
        # Create a unique key from method and args
        key_parts = [method] + [str(arg) for arg in args]
        key_str = "|".join(key_parts)
        
        # Hash for filename safety
        key_hash = hashlib.md5(key_str.encode()).hexdigest()
        
        return f"{method}_{key_hash[:16]}"
    
    def _get_cache_file(self, cache_key: str) -> Path:
        """Get the cache file path for a given key."""
        return self.cache_dir / f"{cache_key}.json"
    
    def _is_cache_valid(self, cache_file: Path) -> bool:
        """Check if a cache file exists and is valid. Since job data is immutable, cache never expires."""
        return cache_file.exists()
    
    def get(self, method: str, *args) -> Optional[Dict[str, Any]]:
        """
        Get cached data for a method call.
        
        Args:
            method: Method name (e.g., 'get_breadcrumbs')
            *args: Arguments to the method
        
        Returns:
            Cached data if available and valid, None otherwise
        """
        cache_key = self._get_cache_key(method, *args)
        cache_file = self._get_cache_file(cache_key)
        
        if self._is_cache_valid(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                
                self.hits += 1
                self.logger.debug(f"Cache hit for {method} (key: {cache_key})")
                return data.get('result')
                
            except Exception as e:
                self.logger.warning(f"Failed to read cache file {cache_file}: {e}")
                # Remove corrupted cache file
                cache_file.unlink(missing_ok=True)
        
        self.misses += 1
        self.logger.debug(f"Cache miss for {method} (key: {cache_key})")
        return None
    
    def set(self, method: str, result: Any, *args) -> None:
        """
        Store data in cache.
        
        Args:
            method: Method name
            result: Result to cache
            *args: Arguments to the method
        """
        cache_key = self._get_cache_key(method, *args)
        cache_file = self._get_cache_file(cache_key)
        
        cache_data = {
            'method': method,
            'args': [str(arg) for arg in args],
            'result': result,
            'cached_at': datetime.now().isoformat()
        }
        
        try:
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2, default=str)
            
            self.logger.debug(f"Cached result for {method} (key: {cache_key})")
            
        except Exception as e:
            self.logger.warning(f"Failed to write cache file {cache_file}: {e}")
    
    def clear(self) -> None:
        """Clear all cache entries."""
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()
        
        self.logger.info(f"Cleared cache directory: {self.cache_dir}")
        self.hits = 0
        self.misses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        cache_files = list(self.cache_dir.glob("*.json"))
        total_size = sum(f.stat().st_size for f in cache_files)
        
        return {
            'cache_dir': str(self.cache_dir),
            'total_files': len(cache_files),
            'total_size_bytes': total_size,
            'total_size_mb': total_size / (1024 * 1024),
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': self.hits / (self.hits + self.misses) if (self.hits + self.misses) > 0 else 0
        }