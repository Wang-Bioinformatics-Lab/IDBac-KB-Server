# -*- coding: utf-8 -*-
import logging

import dash
from dash import dcc
from dash import html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
import plotly.graph_objects as go

import os
from flask import Flask, send_file, send_from_directory, render_template

import pandas as pd

import json
import glob

from flask_caching import Cache

dev_mode = False
if not os.path.isdir('/app'):
    dev_mode =  True

logging.basicConfig(level=logging.WARNING)

server = Flask(__name__)

from routes import api_blueprint
server.register_blueprint(api_blueprint)

app = dash.Dash(
    __name__, 
    server=server, 
    external_stylesheets=[dbc.themes.BOOTSTRAP, '/assets/styles.css'],
    url_base_pathname='/',  # Use a different base path for Dash
    use_pages=True
)

app.title = 'Wang Lab - IDBac KB'

cache = Cache(app.server, config={
    'CACHE_TYPE': 'filesystem',
    'CACHE_DIR': 'temp/flask-cache',
    'CACHE_DEFAULT_TIMEOUT': 0,
    'CACHE_THRESHOLD': 10000
})
memory_cache = Cache(config={
    'CACHE_TYPE': 'simple', 
    'CACHE_DEFAULT_TIMEOUT': 0, 
    'CACHE_THRESHOLD': 10,  # Keep your threshold setting
})
memory_cache.init_app(app.server) 

server = app.server

# setting tracking token
app.index_string = """<!DOCTYPE html>
<html>
    <head>
        <!-- Umami Analytics -->
        <script async defer data-website-id="4611e28d-c0ff-469d-a2f9-a0b54c0c8ee0" src="https://analytics.gnps2.org/umami.js"></script>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>"""

NAVBAR = dbc.Navbar(
    children=[
        dbc.NavbarBrand(
            html.Img(src="../assets/GNPS2xIDBac.png", width="240px", style={"padding-left": "15px"}),
            href="https://gnps2.org"
        ),
        dbc.Nav(
            dbc.NavItem(
                dbc.Button(
                    "Sign Up",
                    color="primary",
                    href="https://gnps2.org/user/signup",
                    style={"padding-left": "30px", "padding-right": "30px", "margin-right": "30px"},
                    className="button-blue"
                )
            ),
            className="ms-auto",  # Align to the right
            navbar=True
        )
    ],
    color="light",
    dark=False,
    sticky="top",
)

# Container should be full width
app.layout = dbc.Container([ 
    dcc.Store(id='data-store', storage_type='memory',),
    dcc.Store(id='data-mtime-store', storage_type='memory',),
    NAVBAR,
    dash.page_container
], fluid=True, style={"width": "100%", "margin": "0", "padding": "0"})

def _get_url_param(param_dict, key, default):
    return param_dict.get(key, [default])[0]

@app.callback([
                Output('update-summary', 'children')
              ],
              [Input('url', 'search')])
def last_updated(search):
    path_to_database_consolidated_file = os.path.join("/app/workflows/idbac_summarize_database/nf_output/10_da_bin/", "output_merged_spectra.json")

    # checking the age of this file
    if os.path.exists(path_to_database_consolidated_file):
        last_updated_time = os.path.getmtime(path_to_database_consolidated_file)
        last_updated_time = pd.to_datetime(last_updated_time, unit='s')

        return ["Last Updated: {} UTC".format(last_updated_time)]
    else:
        return [""]

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

@app.callback(    
            Output('data-store', 'data'),       # Update the data in the store
            Output('data-mtime-store', 'data'), # Store the mtime of the file
            Input('url', 'search'))
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

@app.callback(
    [
        Output('displaytable', 'data'),
        Output('displaytable', 'columns'),
        Output('displaytable', 'hidden_columns'),
        Output('displaytable', 'page_count') # New output for page_count
    ],
    [
        Input('data-store', 'data'), # Full data stored in a dcc.Store
        Input('url', 'search'),
        
        # --- New Inputs from the DataTable ---
        Input('displaytable', 'page_current'),
        Input('displaytable', 'page_size'),
        Input('displaytable', 'sort_by'),
        Input('displaytable', 'filter_query')
        # ------------------------------------
    ],
    prevent_initial_call=True
)
def update_table_server_side(full_data_dict, search, page_current, page_size, sort_by, filter_query):
    df = pd.DataFrame(full_data_dict)

    if page_current is None:
        page_current = 0

    # --- Manual Filtering Example (Simple) ---
    # This is highly simplified. For full functionality, you should use a
    # robust parsing method, like the one in the Dash documentation examples.

    if filter_query is not None and filter_query.strip() != "":
        filtering_expressions = filter_query.split(' && ')
        for expression in filtering_expressions:
            if ' eq ' in expression:
                col, val = expression.split(' eq ')
                col = col.strip('{ }')
                val = val.strip(' "')
                if col in df.columns:
                    df = df[df[col].astype(str).str.lower() == val.lower()]
        # ------------------------------------------

    # 3. Apply Sorting
    if sort_by is not None:
        if len(sort_by):
            df = df.sort_values(
                [col['column_id'] for col in sort_by],
                ascending=[
                    col['direction'] == 'asc'
                    for col in sort_by
                ],
                inplace=False
            )
    
    # 4. Calculate Total Pages
    total_rows = len(df)
    page_count = (total_rows + page_size - 1) // page_size
    
    # 5. Apply Pagination (Slice the data)
    data_page = df.iloc[
        page_current * page_size : (page_current + 1) * page_size
    ]

    # 6. Define Columns (as before, but using the filtered/sorted df)
    shown_columns = set(["Strain name", "Culture Collection", "PI", "genus", "species", "Isolate Source",])
    shown_columns = list(set(df.columns) & shown_columns)
    hidden_columns = list(set(df.columns) - set(shown_columns))

    columns = [{"name": i, "id": i, "hideable": True} for i in df.columns]

    # 7. Return the data for the current page, column definitions, hidden columns, and page count
    return [
        data_page.to_dict('records'),
        columns,
        hidden_columns,
        page_count # The total number of pages
    ]


# We will plot spectra based on which row is selected in the table
@app.callback(
    Output('spectra-plot', 'children'),
    [   
        Input('spectra-bin-size', 'value'),
        Input('displaytable', 'derived_virtual_data'),
        Input('displaytable', 'derived_virtual_selected_rows')
    ])
def update_spectrum(spectra_bin_size, table_data, table_selected):
    if table_selected is None or len(table_selected) == 0:
        return "No spectra selected"

    selected_row = table_data[table_selected[0]]

    # Getting the database id
    database_id = selected_row["database_id"]

    # Getting the processed spectrum
    spectra_json = _get_processed_spectrum(database_id, int(spectra_bin_size))

    ms_peaks = spectra_json["peaks"]

    # Now lets draw it
    max_int = max([peak["i"] for peak in ms_peaks])
    # Drawing the spectrum object
    mzs = [peak["mz"] for peak in ms_peaks]
    ints = [peak["i"]/max_int for peak in ms_peaks]
    neg_ints = [intensity * -1 for intensity in ints]

    # Hover data
    hover_labels = ["{:.4f} m/z, {:.2f} int".format(mzs[i], ints[i]) for i in range(len(mzs))]

    ms_fig = go.Figure(
        data=go.Scatter(x=mzs, y=ints, 
            mode='markers',
            marker=dict(size=0.00001),
            error_y=dict(
                symmetric=False,
                arrayminus=[0]*len(neg_ints),
                array=neg_ints,
                width=0
            ),
            text=hover_labels,
            textposition="top right"
        )
    )

    return [dcc.Graph(figure=ms_fig)]

@app.callback(
    Output('additional-data', 'children'),
    [   
        Input('displaytable', 'derived_virtual_data'),
        Input('displaytable', 'derived_virtual_selected_rows')
    ])
def update_additional_data(table_data, table_selected):
    # Getting the row values

    if table_selected is None or len(table_selected) == 0:
        return "No spectra selected"

    selected_row = table_data[table_selected[0]]

    # Getting the database id
    database_id = selected_row["database_id"]

    # Get the row in the dataframe
    df = pd.read_csv("database/summary.tsv", sep="\t")
    selected_row = df[df["database_id"] == database_id]
    data = selected_row.to_dict('records')[0]

    # Getting the taxonomies
    ordered_taxonomy_keys = [
                                'superkingdom',
                                'kingdom',
                                'phylum',
                                'class',
                                'order',
                                'family',
                                'genus',
                                'species group',
                                'species subgroup',
                                'species',
                                'subspecies',
                                'strain',
                                'clade'
                            ]
    taxonomies = [data.get(key, "") for key in ordered_taxonomy_keys]
    databse_id = data.get("database_id")
    task       = data.get("task")
    sequence   = data.get("16S Sequence")
    filename   = data.get("Filename")
    comment    = data.get("Comment")

    # If any of the above are None or '', replace with "No Data"
    for i in range(len(taxonomies)):
        if taxonomies[i] is None or taxonomies[i] == "" or str(taxonomies[i]).lower() == "nan":
            taxonomies[i] = "No Data"
    if databse_id is None or databse_id == "":
        databse_id = "No Data"
    if task is None or task == "":
        task = "No Data"
    if sequence is None or sequence == "":
        sequence = "No Data"
    if filename is None or filename == "":
        filename = "No Data"
    if comment is None or comment == "":
        comment = "No Data"

    main_output = [html.H5("Database ID:"),
            html.P(databse_id),
            html.H5("Filename:"),
            html.P(filename),
            html.H5("Task:"),
            html.P(task),
            html.H5("Comment:"),
            html.P(comment),]

    taxonomies_output = [html.H5("Taxonomy")] + [html.P(f"{str(key).capitalize()}: {val}") for key,val in zip(ordered_taxonomy_keys, taxonomies)]
    
    # Add Together
    final_output = main_output + taxonomies_output + [html.H5("16S Sequence:"), html.P(sequence)]

    # Output the data
    return final_output

def _get_processed_spectrum(database_id:str, bin_width:int)->dict:
    """ Returns the processed spectrum for a given database id.

    Args:
        database_id (str): The database id to search for.
        bin_width (int): The size of bins used in the spectrum (Da).

    Returns:
        dict: The processed spectrum.
    """
    # Finding all the database files
    database_files = glob.glob(f"/app/workflows/idbac_summarize_database/nf_output/{str(bin_width)}_da_bin/output_spectra_json/**/{os.path.basename(database_id)}.json")

    if len(database_files) == 0:
        return None
    
    if len(database_files) > 1:
        return None

    with open(database_files[0]) as file_handle:
        spectrum_dict = json.load(file_handle)

        return spectrum_dict

if __name__ == "__main__":
    app.run_server(debug=True, port=5000, host="0.0.0.0")
