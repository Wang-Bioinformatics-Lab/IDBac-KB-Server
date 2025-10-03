import dash
from dash import Dash, Input, Output
from flask_caching import Cache
import pandas as pd
import os
import logging

app = dash.Dash(__name__, suppress_callback_exceptions=True)
server = app.server

memory_cache = Cache(config={
    'CACHE_TYPE': 'simple', 
    'CACHE_DEFAULT_TIMEOUT': 0, 
    'CACHE_THRESHOLD': 10,  # Keep your threshold setting
})
memory_cache.init_app(app.server) 

def database_key_generator(*args, **kwargs):
    """Generates a key based on the file's mtime."""
    file_path = "database/summary.tsv"
    
    # Get the modification timestamp (seconds since epoch)
    try:
        mtime = os.path.getmtime(file_path)
    except FileNotFoundError:
        # If the file is missing, use a fixed key to force re-check
        return "database-not-found" 

    # Key = function name + mtime 
    # (We include the function name to avoid collisions with other functions)
    return f"load_database_{mtime}" 

@memory_cache.memoize(make_name=database_key_generator) 
def load_database(search):
    if not os.path.exists("database/summary.tsv"):
        logging.error("Database Summary File Not Found at database/summary.tsv")
        return None, None
    try:
        summary_df = pd.read_csv("database/summary.tsv", sep="\t")

        mtime = os.path.getmtime("database/summary.tsv")

        data = summary_df.to_dict('records')
        return data, mtime
    except Exception as e:
        logging.error(f"Error Loading Database Summary File: {e}")
        return None, None
