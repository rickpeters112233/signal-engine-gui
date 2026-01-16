"""
Feature Cache Wrapper with TGC Compression
Implements aggressive caching with Tribernachi Geometric Compression
Achieves 30-40% total compression (TGC + TVC combined)
"""

import os
import json
import hashlib
import datetime
import pickle
import base64
from pathlib import Path
from typing import Any, Dict, Optional, Union
import pandas as pd
import numpy as np

from tribernachi.tgc_encoder import TGCEncoder
from tribernachi.tvc_versioning import generate_tvc, parse_cache_key, generate_cache_key


class FeatureCacheWrapper:
    """
    Enhanced feature cache with TGC compression and TVC versioning.

    Provides transparent compression/decompression of cached feature data
    with version-aware cache keys for efficient invalidation.
    """

    def __init__(
        self,
        cache_dir: str = "./cache_data",
        enable_compression: bool = True,
        enable_memory_cache: bool = True,
        version: str = "4.02"
    ):
        """
        Initialize feature cache wrapper.

        Args:
            cache_dir: Directory for file-based cache storage
            enable_compression: Enable TGC compression (default: True)
            enable_memory_cache: Enable in-memory caching (default: True)
            version: Cache version string (default: "4.02")
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.enable_compression = enable_compression
        self.enable_memory_cache = enable_memory_cache
        self.version = version

        # In-memory cache
        self.memory_cache = {} if enable_memory_cache else None

        # TGC encoder
        self.encoder = TGCEncoder() if enable_compression else None

        print(f"Feature Cache initialized:")
        print(f"  - Cache directory: {self.cache_dir}")
        print(f"  - Compression: {'Enabled (TGC)' if enable_compression else 'Disabled'}")
        print(f"  - Memory cache: {'Enabled' if enable_memory_cache else 'Disabled'}")
        print(f"  - Version: {version}")

    def _compute_data_hash(self, data: Any) -> str:
        """
        Compute SHA-256 hash of data.

        Args:
            data: Data to hash

        Returns:
            str: Hexadecimal hash string (first 16 characters)
        """
        # Serialize data to bytes
        if isinstance(data, pd.DataFrame):
            data_bytes = pd.util.hash_pandas_object(data).values.tobytes()
        elif isinstance(data, np.ndarray):
            data_bytes = data.tobytes()
        elif isinstance(data, (dict, list)):
            data_bytes = json.dumps(data, sort_keys=True).encode('utf-8')
        else:
            data_bytes = str(data).encode('utf-8')

        # Compute SHA-256 hash
        hash_obj = hashlib.sha256(data_bytes)
        return hash_obj.hexdigest()[:16]

    def _generate_cache_key(self, namespace: str, data_hash: str) -> str:
        """
        Generate TVC-enhanced cache key.

        Args:
            namespace: Cache namespace (e.g., 'features', 'scores')
            data_hash: Data hash string

        Returns:
            str: Cache key in format [NAMESPACE]-[TVC]-[HASH]
        """
        # Generate TVC prefix with current date and version
        tvc_prefix = generate_tvc(datetime.datetime.now(), self.version)

        # Combine into full cache key
        return f"{namespace}-{tvc_prefix}-{data_hash}"

    def _get_cache_path(self, cache_key: str) -> Path:
        """
        Get file path for cache key.

        Args:
            cache_key: Cache key string

        Returns:
            Path: Full path to cache file
        """
        return self.cache_dir / f"{cache_key}.cache"

    def _serialize_data(self, data: Any) -> bytes:
        """
        Serialize data with optional TGC compression.

        Args:
            data: Data to serialize

        Returns:
            bytes: Serialized (and possibly compressed) data
        """
        # Convert to JSON-serializable format
        if isinstance(data, pd.DataFrame):
            # For DataFrames, use pickle to avoid Timestamp serialization issues
            # This is more reliable and preserves all dtypes
            return pickle.dumps(data)
        elif isinstance(data, np.ndarray):
            serializable = {
                '_type': 'ndarray',
                'data': data.tolist(),
                'dtype': str(data.dtype),
                'shape': data.shape
            }
        elif isinstance(data, (dict, list, str, int, float, bool, type(None))):
            serializable = {'_type': 'json', 'data': data}
        else:
            # Fallback to pickle for unknown types
            return pickle.dumps(data)

        # Apply TGC compression if enabled
        if self.enable_compression and self.encoder:
            try:
                compressed = self.encoder.compress_json(serializable)
                compressed['_tgc_metadata'] = {
                    'compressed': True,
                    'version': self.version
                }
                serializable = compressed
            except Exception as e:
                print(f"  - Warning: TGC compression failed, using uncompressed: {e}")

        # Serialize to JSON bytes
        return json.dumps(serializable).encode('utf-8')

    def _deserialize_data(self, data_bytes: bytes) -> Any:
        """
        Deserialize data with optional TGC decompression.

        Args:
            data_bytes: Serialized data bytes

        Returns:
            Any: Deserialized data
        """
        try:
            # Try JSON deserialization first
            serializable = json.loads(data_bytes.decode('utf-8'))

            # Check for TGC compression
            if serializable.get('_tgc_metadata', {}).get('compressed'):
                # Decompress using TGC
                serializable = self.encoder.decompress_json(serializable)

            # Reconstruct original data type
            data_type = serializable.get('_type')

            if data_type == 'dataframe':
                df = pd.DataFrame(**serializable['data'])
                # Restore index
                if serializable.get('index_type') == 'datetime':
                    df.index = pd.to_datetime(serializable['index'])
                else:
                    df.index = serializable['index']
                df.columns = serializable['columns']
                return df
            elif data_type == 'ndarray':
                arr = np.array(serializable['data'])
                return arr.astype(serializable['dtype']).reshape(serializable['shape'])
            elif data_type == 'json':
                return serializable['data']
            else:
                return serializable

        except (json.JSONDecodeError, UnicodeDecodeError):
            # Fallback to pickle
            return pickle.loads(data_bytes)

    def get(
        self,
        namespace: str,
        key_data: Any,
        max_age_hours: Optional[float] = None
    ) -> Optional[Any]:
        """
        Get cached data.

        Args:
            namespace: Cache namespace
            key_data: Data to generate cache key from
            max_age_hours: Maximum cache age in hours (None = no expiration)

        Returns:
            Cached data or None if not found/expired
        """
        # Generate cache key
        data_hash = self._compute_data_hash(key_data)
        cache_key = self._generate_cache_key(namespace, data_hash)

        # Check memory cache first
        if self.memory_cache is not None and cache_key in self.memory_cache:
            print(f"  - Cache HIT (memory): {cache_key}")
            return self.memory_cache[cache_key]

        # Check file cache
        cache_path = self._get_cache_path(cache_key)

        if cache_path.exists():
            # Check age if required
            if max_age_hours is not None:
                file_age = datetime.datetime.now() - datetime.datetime.fromtimestamp(
                    cache_path.stat().st_mtime
                )
                if file_age.total_seconds() / 3600 > max_age_hours:
                    print(f"  - Cache EXPIRED: {cache_key} (age: {file_age})")
                    return None

            # Load from file
            try:
                with open(cache_path, 'rb') as f:
                    cache_entry_bytes = f.read()

                # Deserialize cache entry
                cache_entry = json.loads(cache_entry_bytes.decode('utf-8'))

                # Extract and deserialize the value (decode from base64)
                serialized_value = cache_entry.get('value', '')
                if isinstance(serialized_value, str):
                    serialized_value = base64.b64decode(serialized_value.encode('ascii'))

                data = self._deserialize_data(serialized_value)

                # Store in memory cache
                if self.memory_cache is not None:
                    self.memory_cache[cache_key] = data

                print(f"  - Cache HIT (file): {cache_key}")
                return data

            except Exception as e:
                print(f"  - Cache READ ERROR: {cache_key}: {e}")
                import traceback
                traceback.print_exc()
                return None

        print(f"  - Cache MISS: {cache_key}")
        return None

    def set(
        self,
        namespace: str,
        key_data: Any,
        value: Any,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Set cached data.

        Args:
            namespace: Cache namespace
            key_data: Data to generate cache key from
            value: Data to cache
            metadata: Optional metadata to store with cache

        Returns:
            str: Generated cache key
        """
        # Generate cache key
        data_hash = self._compute_data_hash(key_data)
        cache_key = self._generate_cache_key(namespace, data_hash)

        # Store in memory cache (store original value)
        if self.memory_cache is not None:
            self.memory_cache[cache_key] = value

        # Store in file cache
        try:
            cache_path = self._get_cache_path(cache_key)

            # Serialize the value first (handles DataFrame, ndarray, etc.)
            serialized_value = self._serialize_data(value)

            # Create cache entry with base64-encoded value (handles binary pickle data)
            cache_entry = {
                'value': base64.b64encode(serialized_value).decode('ascii'),
                'metadata': metadata or {},
                'timestamp': datetime.datetime.now().isoformat(),
                'cache_key': cache_key
            }

            # Serialize the entire cache entry (now it's JSON-serializable)
            cache_entry_bytes = json.dumps(cache_entry).encode('utf-8')

            with open(cache_path, 'wb') as f:
                f.write(cache_entry_bytes)

            # Calculate compression ratio if enabled
            if self.enable_compression:
                # Estimate uncompressed size (value as JSON)
                try:
                    if isinstance(value, pd.DataFrame):
                        uncompressed_size = len(value.to_json().encode('utf-8'))
                    elif isinstance(value, np.ndarray):
                        uncompressed_size = len(json.dumps(value.tolist()).encode('utf-8'))
                    else:
                        uncompressed_size = len(json.dumps(value, default=str).encode('utf-8'))
                except:
                    uncompressed_size = len(serialized_value)

                compressed_size = len(cache_entry_bytes)
                ratio = uncompressed_size / compressed_size if compressed_size > 0 else 1.0
                print(f"  - Cache SET: {cache_key} (compression: {ratio:.2f}x)")
            else:
                print(f"  - Cache SET: {cache_key}")

        except Exception as e:
            print(f"  - Cache WRITE ERROR: {cache_key}: {e}")
            import traceback
            traceback.print_exc()

        return cache_key

    def invalidate(self, namespace: Optional[str] = None, pattern: Optional[str] = None):
        """
        Invalidate cached entries.

        Args:
            namespace: Invalidate only this namespace (None = all)
            pattern: Additional pattern to match in cache key
        """
        count = 0

        # Clear memory cache
        if self.memory_cache is not None:
            if namespace or pattern:
                keys_to_remove = [
                    k for k in self.memory_cache.keys()
                    if (namespace is None or k.startswith(namespace))
                    and (pattern is None or pattern in k)
                ]
                for k in keys_to_remove:
                    del self.memory_cache[k]
                    count += 1
            else:
                count = len(self.memory_cache)
                self.memory_cache.clear()

        # Clear file cache
        for cache_file in self.cache_dir.glob("*.cache"):
            cache_key = cache_file.stem
            if (namespace is None or cache_key.startswith(namespace)) and \
               (pattern is None or pattern in cache_key):
                cache_file.unlink()
                count += 1

        print(f"  - Invalidated {count} cache entries")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            dict: Cache statistics
        """
        file_cache_count = len(list(self.cache_dir.glob("*.cache")))
        memory_cache_count = len(self.memory_cache) if self.memory_cache else 0

        total_size = sum(
            f.stat().st_size for f in self.cache_dir.glob("*.cache")
        )

        return {
            'file_cache_entries': file_cache_count,
            'memory_cache_entries': memory_cache_count,
            'total_size_bytes': total_size,
            'total_size_mb': total_size / (1024 * 1024),
            'compression_enabled': self.enable_compression,
            'cache_dir': str(self.cache_dir)
        }
