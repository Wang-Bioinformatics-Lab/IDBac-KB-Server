import dash
from dash import Dash, Input, Output
from flask_caching import Cache
import pandas as pd
import os
import logging
import time
import threading
import redis
import pickle

app = dash.Dash(__name__, suppress_callback_exceptions=True)
server = app.server

# Redis-based cache with stale-while-revalidate pattern
# Works across multiple workers since Redis is shared
try:
    redis_client = redis.Redis(host='idbac-kb-redis', port=6379, db=0, decode_responses=False)
    redis_client.ping()
    logging.info("Connected to Redis for database caching")
except Exception as e:
    logging.error(f"Failed to connect to Redis: {e}")
    redis_client = None

_cache_check_interval = 30  # Check for updates every 30 seconds

CACHE_KEY_DATA = 'database:summary:data'
CACHE_KEY_MTIME = 'database:summary:mtime'
CACHE_KEY_LAST_CHECK = 'database:summary:last_check'
CACHE_KEY_REFRESH_LOCK = 'database:summary:refresh_lock'

def _refresh_database_background():
    """Background task to refresh database cache in Redis."""
    
    if redis_client is None:
        return
    
    file_path = "database/summary.tsv"
    
    try:
        if not os.path.exists(file_path):
            logging.error("Database Summary File Not Found at database/summary.tsv")
            return
        
        file_mtime = os.path.getmtime(file_path)
        
        # Check if file has changed
        cached_mtime_bytes = redis_client.get(CACHE_KEY_MTIME)
        if cached_mtime_bytes is not None:
            cached_mtime = float(cached_mtime_bytes)
            if cached_mtime == file_mtime:
                # No changes needed
                return
        
        # File changed or no cache - reload
        logging.info(f"Reloading database from {file_path} in background")
        summary_df = pd.read_csv(file_path, sep="\t")
        data = summary_df.to_dict('records')
        
        # Update Redis cache
        redis_client.set(CACHE_KEY_DATA, pickle.dumps(data))
        redis_client.set(CACHE_KEY_MTIME, str(file_mtime))
        
        logging.info("Database reload complete")
    except Exception as e:
        logging.error(f"Error reloading database in background: {e}")
    finally:
        # Release the distributed lock
        redis_client.delete(CACHE_KEY_REFRESH_LOCK)

def load_database(search):
    """Load database with stale-while-revalidate pattern using Redis.
    Returns cached data immediately, triggers background refresh if needed."""
    
    # Fallback to direct file read if Redis is unavailable
    if redis_client is None:
        logging.warning("Redis unavailable, reading directly from file")
        return _load_database_from_file()
    
    current_time = time.time()
    
    try:
        # Check if it's time to refresh (but don't block on it)
        last_check_bytes = redis_client.get(CACHE_KEY_LAST_CHECK)
        last_check = float(last_check_bytes) if last_check_bytes else 0
        should_refresh = (current_time - last_check) >= _cache_check_interval
        
        if should_refresh:
            redis_client.set(CACHE_KEY_LAST_CHECK, str(current_time))
            
            # Try to acquire distributed lock across all workers
            lock_acquired = redis_client.set(CACHE_KEY_REFRESH_LOCK, '1', nx=True, ex=60)
            
            if lock_acquired:
                # This worker got the lock - start background refresh
                thread = threading.Thread(target=_refresh_database_background, daemon=True)
                thread.start()
        
        # Always return cached data immediately if available
        cached_data_bytes = redis_client.get(CACHE_KEY_DATA)
        if cached_data_bytes is not None:
            cached_mtime_bytes = redis_client.get(CACHE_KEY_MTIME)
            cached_mtime = float(cached_mtime_bytes) if cached_mtime_bytes else None
            data = pickle.loads(cached_data_bytes)
            return data, cached_mtime
        
        # First call ever - must load synchronously
        logging.info("First load - loading database synchronously")
        return _load_database_from_file(update_redis=True)
        
    except Exception as e:
        logging.error(f"Error accessing Redis cache: {e}")
        return _load_database_from_file()

def _load_database_from_file(update_redis=False):
    """Fallback: load database directly from file."""
    file_path = "database/summary.tsv"
    
    if not os.path.exists(file_path):
        logging.error("Database Summary File Not Found at database/summary.tsv")
        return None, None
    
    try:
        summary_df = pd.read_csv(file_path, sep="\t")
        file_mtime = os.path.getmtime(file_path)
        data = summary_df.to_dict('records')
        
        # Update Redis if requested and available
        if update_redis and redis_client is not None:
            try:
                redis_client.set(CACHE_KEY_DATA, pickle.dumps(data))
                redis_client.set(CACHE_KEY_MTIME, str(file_mtime))
                redis_client.set(CACHE_KEY_LAST_CHECK, str(time.time()))
            except Exception as e:
                logging.error(f"Failed to update Redis cache: {e}")
        
        return data, file_mtime
    except Exception as e:
        logging.error(f"Error Loading Database Summary File: {e}")
        return None, None
