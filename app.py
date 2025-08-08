# -*- coding: utf-8 -*-
import logging

import dash
from dash import dcc
from dash import html
from dash import dash_table
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
import plotly.express as px
import plotly.graph_objects as go 

import os
import urllib.parse
from flask import Flask, send_file, send_from_directory, render_template

import pandas as pd
import requests
import uuid
import werkzeug

import numpy as np
from tqdm import tqdm
import urllib
import json
import glob

from collections import defaultdict
from dotenv import dotenv_values, load_dotenv


from flask_caching import Cache
from flask import request

import tasks

from utils import convert_to_mzml


dev_mode = False
if not os.path.isdir('/app'):
    dev_mode =  True

logging.basicConfig(level=logging.WARNING)

server = Flask(__name__)

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

_env = dotenv_values()

server = app.server

# summary_df = None
# number_of_database_entries = ""
# if os.path.exists("database/summary.tsv"):
#     summary_df = pd.read_csv("database/summary.tsv", sep="\t")
#     number_of_database_entries = str(len(summary_df))

#     summary_df["FullTaxonomy"] = summary_df["FullTaxonomy"].fillna("No Taxonomy")
#     not_16S = ~ summary_df["FullTaxonomy"].str.contains("User Submitted 16S") & ~ summary_df["FullTaxonomy"].str.contains("No Taxonomy")
#     is_16S  = summary_df["FullTaxonomy"].str.contains("User Submitted 16S")

#     summary_df.loc[is_16S & (summary_df.genus.isna()), "Genus"] = summary_df.loc[is_16S, "FullTaxonomy"].str.split().str[0]
#     summary_df.loc[is_16S & (summary_df.species.isna()), "Species"] = "User Submitted 16S"

#     # Get counts by Genus and Species for px.bar
#     # summary_df = summary_df.groupby(["Genus", "Species"]).size().reset_index(name="count")
#     summary_df = summary_df.groupby(["Genus"]).size().reset_index(name="count")
#     # Strip the Genus column of whitespace
#     summary_df["Genus"] = summary_df["Genus"].str.strip()

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

# TODO: CACHE ME
@app.callback(    
            Output('data-store', 'data'),  # Update the data in the store
            Input('url', 'search'))
def load_database(search):
    if not os.path.exists("database/summary.tsv"):
        logging.error("Database Summary File Not Found at database/summary.tsv")
        return None
    try:
        summary_df = pd.read_csv("database/summary.tsv", sep="\t")
        data = summary_df.to_dict('records')
        return data
    except Exception as e:
        logging.error("Error Loading Database Summary File:", e)
        return None

@app.callback([
                Output('displaytable', 'data'),
                Output('displaytable', 'columns'),
                Output('displaytable', 'hidden_columns'),
              ],
              [ Input('data-store', 'data'),
                Input('url', 'search'),
            ])
def display_table(sumary_df, search):
    summary_df = pd.DataFrame(sumary_df)
    # Remove columns shown in "Additional Data"
    shown_columns = set(["Strain name", "Culture Collection", "PI",
                      "genus", "species", "Isolate Source",])
    # Make safe if columns are missing
    shown_columns = list(set(summary_df.columns) & shown_columns)
    hidden_columns = list(set(summary_df.columns) - set(shown_columns))

    columns = [{"name": i, "id": i, "hideable": True} for i in summary_df.columns]

    data = summary_df.to_dict('records')
    
    return [data, columns, hidden_columns]


# We will plot spectra based on which row is selected in the table
@app.callback(
    Output('spectra-plot', 'children'),
    [   
        Input('spectra-bin-size', 'value'),
        Input('displaytable', 'derived_virtual_data'),
        Input('displaytable', 'derived_virtual_selected_rows')
    ])
def update_spectrum(spectra_bin_size, table_data, table_selected):
    # Getting the row values

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

# API
@server.route("/api")
def api():
    return "Up"

@server.route("/api/database/refresh", methods=["GET"])
def refresh():
    # Calling task to summarize and update the catalog
    tasks.task_summarize_depositions.delay()

    return "Refreshing"

@server.route("/api/get_all_strain_names", methods=["GET"])
def get_all_strain_names():
    summary_df = pd.read_csv("database/summary.tsv", sep="\t")

    return json.dumps(summary_df["Strain name"].tolist())

@server.route("/api/spectrum", methods=["POST"])
def deposit():
    # Check the API credentials
    assert("CREDENTIALSKEY" in _env)
    request_credentials = request.values.get("CREDENTIALSKEY")

    if request_credentials != _env["CREDENTIALSKEY"]:
        return "Invalid Credentials", 403

    # Getting all the parameter arguments
    all_parameters = list(request.values.keys())

    spectrum_dict = json.loads(request.values.get("spectrum_json"))
    spectrum_dict["task"] = request.values.get("task")
    spectrum_dict["user"] = request.values.get("user")

    # Saving the results here
    task_result = tasks.task_deposit_data.delay(spectrum_dict, None)

    # Enable this call to be blocking
    return "DONE"

@server.route("/api/db-checksum", methods=["GET"])
def checksum():
    if dev_mode:
        return send_from_directory("workflows/idbac_summarize_database/nf_output/", "idbac_database.json.sha256")
    else:
        return send_from_directory("/app/workflows/idbac_summarize_database/nf_output/", "idbac_database.json.sha256")

@server.route("/api/spectrum", methods=["GET"])
def download():
    # Getting a single spectrum
    database_id = request.values.get("database_id")

    if database_id == "ALL":
        if dev_mode:
            return send_from_directory("workflows/idbac_summarize_database/nf_output/", "idbac_database.json")
        else:
            return send_from_directory("/app/workflows/idbac_summarize_database/nf_output/", "idbac_database.json")

    # Finding all the database files
    database_files = glob.glob("database/depositions/**/{}.json".format(os.path.basename(database_id)))

    if len(database_files) == 0:
        return "File not found", 404
    
    if len(database_files) > 1:
        return "Multiple files found", 500
    
    return send_from_directory(os.path.dirname(database_files[0]), os.path.basename(database_files[0]))

@server.route("/api/spectrum/mzml-raw", methods=["GET"])
def download_mzml_raw():
    # Get the database_id from the request
    database_id = request.args.get("database_id")
    
    if not database_id:
        return "Database ID is required", 400

    # Find the corresponding JSON file for the database ID
    database_files = glob.glob(f"database/depositions/**/{os.path.basename(database_id)}.json")

    if len(database_files) == 0:
        return "File not found", 404

    if len(database_files) > 1:
        return "Multiple files found", 500
    
    # Convert the file to mzML format
    mzml_bytes = convert_to_mzml(database_files[0])

    # Return the mzML bytes as a downloadable file
    mzml_bytes.seek(0)
    return send_file(
        mzml_bytes,
        as_attachment=True,
        download_name=f"{database_id}.mzML",
        mimetype="application/octet-stream"
    )

@server.route("/api/spectrum/mzml-filtered", methods=["GET"])
def download_mzml_filtered():
    # Getting a single spectrum
    database_id = request.values.get("database_id")
    bin_width   = request.values.get("bin_width", 10)

    # Finding all the database files
    database_files = f"/app/workflows/idbac_summarize_database/nf_output/{str(bin_width)}_da_bin/output_spectra_json/**/{os.path.basename(database_id)}.json"

    if len(database_files) == 0:
        return "File not found", 404
    
    if len(database_files) > 1:
        return "Multiple files found", 500
    
    # Get the file and convert to mzML
    mzml_bytes  = convert_to_mzml(database_files[0])

    # Return bytes as file
    mzml_bytes.seek(0)
    return send_file(
        mzml_bytes,
        as_attachment=True,
        download_name=f"{database_id}.mzML",
        mimetype="application/octet-stream"
    )


@server.route("/api/spectrum/filtered", methods=["GET"])
def filtered_spectra():
    # Getting a single spectrum
    database_id = request.values.get("database_id")
    bin_width   = request.values.get("bin_width", 10)

    if database_id == "ALL":
        if dev_mode:
            return send_from_directory(f"workflows/idbac_summarize_database/nf_output/{str(bin_width)}_da_bin/", "output_merged_spectra.json")
        else:
            return send_from_directory(f"/app/workflows/idbac_summarize_database/nf_output/{str(bin_width)}_da_bin/", "output_merged_spectra.json")

    # Finding all the database files
    database_files = glob.glob(f"/app/workflows/idbac_summarize_database/nf_output/{str(bin_width)}_da_bin/output_spectra_json/**/{os.path.basename(database_id)}.json")

    if len(database_files) == 0:
        return "File not found", 404
    
    if len(database_files) > 1:
        return "Multiple files found", 500
    
    return send_from_directory(os.path.dirname(database_files[0]), os.path.basename(database_files[0]))

@server.route("/api/spectrum/ml_db", methods=["GET"])
def ml_db():
    # Getting a single spectrum
    database_id = request.values.get("database_id", 'ALL')

    if database_id == "ALL":
        if dev_mode:
            return send_from_directory("workflows/idbac_summarize_database/nf_output/ml_db/", "ml_db.json")
        else:
            return send_from_directory("/app/workflows/idbac_summarize_database/nf_output/ml_db/", "ml_db.json")
        
    else:
        # Return an error if the database_id is not "ALL"
        return "Only 'ALL' is supported for ml_db", 400

@server.route("/api/spectra", methods=["GET"])
def spectra_list():
    # Parse summary
    summary_df = pd.read_csv("database/summary.tsv", sep="\t")

    # return json
    return summary_df.to_json(orient="records")

@server.route("/admin/nextflow_report", methods=["GET"])
def nextflow_report():
    if dev_mode:
        if os.path.exists("workflows/idbac_summarize_database/IDBac_summarize_database_report.html"):
            return send_from_directory("workflows/idbac_summarize_database", "IDBac_summarize_database_report.html")
        else:
            return "No Report Found", 404
    else:
        if os.path.exists("/app/workflows/idbac_summarize_database/IDBac_summarize_database_report.html"):
            return send_from_directory("/app/workflows/idbac_summarize_database", "IDBac_summarize_database_report.html")
        else:
            return "No Report Found", 404
        
@server.route("/analysis-utils/get_genus_options", methods=["GET"])
def analysis_utils_get_genus_options():
    # TODO: Make more general to handle other columns
    summary_df = pd.read_csv("database/summary.tsv", sep="\t")
    genus_options = summary_df.loc[summary_df.genus.notna(), 'genus'].unique().tolist()

    # Format as Key: Value JSON
    genus_options = [{"value-key": str(genus), "display-key": str(genus).capitalize()} for genus in genus_options]
    return json.dumps(genus_options)

@server.route("/analysis-utils/get_species_options", methods=["GET"])
def analysis_utils_get_species_options():
    summary_df = pd.read_csv("database/summary.tsv", sep="\t")
    species_options = summary_df.loc[summary_df.species.notna(), 'species'].unique().tolist()

    # Format as Key: Value JSON
    species_options = [{"value-key": str(species), "display-key": str(species).capitalize()} for species in species_options]
    return json.dumps(species_options)
    
@server.route("/download_tree_png", methods=["GET"])
def download_tree_png():
    if dev_mode:
        if os.path.exists("workflows/idbac_summarize_database/nf_output/tree.png"):
            return send_from_directory("workflows/idbac_summarize_database/nf_output", "tree.png")
        else:
            return "No Image Found", 404
    else:
        if os.path.exists("/app/assets/tree.png"):
            return send_from_directory("/app/assets", "tree.png")
        else:
            return "No Image Found", 404

@server.route("/download_tree_svg", methods=["GET"])
def download_tree_svg():
    if dev_mode:
        if os.path.exists("workflows/idbac_summarize_database/nf_output/tree.svg"):
            return send_from_directory("workflows/idbac_summarize_database/nf_output", "tree.svg")
        else:
            return "No Image Found", 404
    else:
        if os.path.exists("/app/assets/tree.svg"):
            return send_from_directory("/app/assets", "tree.svg")
        else:
            return "No Image Found", 404
    
@server.route("/download_tree_nwk", methods=["GET"])
def download_tree_nwk():
    if dev_mode:
        if os.path.exists("workflows/idbac_summarize_database/nf_output/tree.nwk"):
            return send_from_directory("workflows/idbac_summarize_database/nf_output", "tree.nwk")
        else:
            return "No Image Found", 404
    else:
        if os.path.exists("/app/assets/tree.nwk"):
            return send_from_directory("/app/assets", "tree.nwk")
        else:
            return "No Image Found", 404

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
