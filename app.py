# -*- coding: utf-8 -*-
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
from flask import Flask, send_from_directory, render_template

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

summary_df = None
number_of_database_entries = ""
if os.path.exists("database/summary.tsv"):
    summary_df = pd.read_csv("database/summary.tsv", sep="\t")
    number_of_database_entries = str(len(summary_df))
    summary_df["FullTaxonomy"] = summary_df["FullTaxonomy"].fillna("No Taxonomy")
    not_16S = ~ summary_df["FullTaxonomy"].str.contains("User Submitted 16S") & ~ summary_df["FullTaxonomy"].str.contains("No Taxonomy")
    is_16S  = summary_df["FullTaxonomy"].str.contains("User Submitted 16S")

    summary_df.assign(Genus="", Species="")
    summary_df.loc[not_16S, "Genus"] = summary_df.loc[not_16S, "FullTaxonomy"].str.split(";").str[-2]
    summary_df.loc[not_16S, "Species"] = summary_df.loc[not_16S, "FullTaxonomy"].str.split(";").str[-1]
    summary_df.loc[is_16S, "Genus"] = summary_df.loc[is_16S, "FullTaxonomy"].str.split().str[0]
    summary_df.loc[is_16S, "Species"] = "User Submitted 16S"

    # Get counts by Genus and Species for px.bar
    # summary_df = summary_df.groupby(["Genus", "Species"]).size().reset_index(name="count")
    summary_df = summary_df.groupby(["Genus"]).size().reset_index(name="count")
    # Strip the Genus column of whitespace
    summary_df["Genus"] = summary_df["Genus"].str.strip()

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
            [
                dbc.NavItem(dbc.NavLink("Home", href="/")),
                dbc.NavItem(dbc.NavLink("Database", href="/database")),
                dbc.NavItem(dbc.NavLink("Download Summary", href="https://idbac.org/api/spectra")), # Must use full url to have 'get' request
            ],
        navbar=True)
    ],
    color="light",
    dark=False,
    sticky="top",
)

# Container should be full width
app.layout = dbc.Container([ 
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
    path_to_database_consolidated_file = os.path.join("/app/workflows/idbac_summarize_database/nf_output/", "output_merged_spectra.json")

    # checking the age of this file
    if os.path.exists(path_to_database_consolidated_file):
        last_updated_time = os.path.getmtime(path_to_database_consolidated_file)
        last_updated_time = pd.to_datetime(last_updated_time, unit='s')

        return ["Last Updated: {} UTC".format(last_updated_time)]
    else:
        return [""]


@app.callback([
                Output('displaytable', 'data'),
                Output('displaytable', 'columns'),
                Output('displaytable', 'hidden_columns')
              ],
              [Input('url', 'search')])
def display_table(search):
    summary_df = pd.read_csv("database/summary.tsv", sep="\t")
    # Remove columns shown in "Additional Data"
    hidden_columns = set(["FullTaxonomy", "task", "Scan/Coordinate", 
                      "Filename", "Comment", "16S Sequence", "16S Taxonomy", "database_id", 
                      "user", "Latitude", "Longitude", "Altitude",
                      "Sample Collected by", "Isolate Collected by",
                      "MS Collected by", "Cultivation temp", "Cultivation time",
                      "NCBI taxid", "Strain ID"])
    # Make safe if columns are missing
    hidden_columns = list(hidden_columns.intersection(summary_df.columns))

    columns = [{"name": i, "id": i, "hideable": True} for i in summary_df.columns]

    data = summary_df.to_dict('records')
    
    return [data, columns, hidden_columns]


# We will plot spectra based on which row is selected in the table
@app.callback(
    Output('output', 'children'),
    [   
        Input('displaytable', 'derived_virtual_data'),
        Input('displaytable', 'derived_virtual_selected_rows')
    ])
def update_spectrum(table_data, table_selected):
    # Getting the row values

    if table_selected is None or len(table_selected) == 0:
        return "No spectra selected"

    selected_row = table_data[table_selected[0]]

    # Getting the database id
    database_id = selected_row["database_id"]

    # Getting the processed spectrum
    spectra_json = _get_processed_spectrum(database_id)

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
    taxonomies = data.get("FullTaxonomy")
    databse_id = data.get("database_id")
    task       = data.get("task")
    sequence   = data.get("16S Sequence")
    filename   = data.get("Filename")
    comment    = data.get("Comment")

    # If any of the above are None or '', replace with "No Data"
    if taxonomies is None or taxonomies == "":
        taxonomies = "No Data"
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

    # Output the data
    return [html.H5("Database ID:"),
            html.P(databse_id),
            html.H5("Filename:"),
            html.P(filename),
            html.H5("Task:"),
            html.P(task),
            html.H5("Comment:"),
            html.P(comment),
            html.H5("Taxonomy:"),
            html.P(taxonomies),
            html.H5("16S Sequence:"),
            html.P(sequence)]

# API
@server.route("/api")
def api():
    return "Up"

@server.route("/api/database/refresh", methods=["GET"])
def refresh():
    # Calling task to summarize and update the catalog
    tasks.task_summarize_depositions.delay()

    return "Refreshing"

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

@server.route("/api/spectrum", methods=["GET"])
def download():
    # Getting a single spectrum
    database_id = request.values.get("database_id")

    if database_id == "ALL":
        return send_from_directory("/app/workflows/idbac_summarize_database/nf_output/", "idbac_database.json")

    # Finding all the database files
    database_files = glob.glob("database/depositions/**/{}.json".format(os.path.basename(database_id)))

    if len(database_files) == 0:
        return "File not found", 404
    
    if len(database_files) > 1:
        return "Multiple files found", 500
    
    return send_from_directory(os.path.dirname(database_files[0]), os.path.basename(database_files[0]))

@server.route("/api/spectrum/filtered", methods=["GET"])
def filtered_spectra():
    # Getting a single spectrum
    database_id = request.values.get("database_id")

    if database_id == "ALL":
        return send_from_directory("/app/workflows/idbac_summarize_database/nf_output/", "output_merged_spectra.json")

    # Finding all the database files
    database_files = glob.glob("/app/workflows/idbac_summarize_database/nf_output/output_spectra_json/**/{}.json".format(os.path.basename(database_id)))

    if len(database_files) == 0:
        return "File not found", 404
    
    if len(database_files) > 1:
        return "Multiple files found", 500
    
    return send_from_directory(os.path.dirname(database_files[0]), os.path.basename(database_files[0]))

@server.route("/api/spectra", methods=["GET"])
def spectra_list():
    # Parse summary
    summary_df = pd.read_csv("database/summary.tsv", sep="\t")

    # return json
    return summary_df.to_json(orient="records")

@server.route("/admin/nextflow_report", methods=["GET"])
def nextflow_report():
    if os.path.exists("/app/workflows/idbac_summarize_database/IDBac_summarize_database_report.html"):
        return send_from_directory("/app/workflows/idbac_summarize_database", "IDBac_summarize_database_report.html")
    else:
        return "No Report Found", 404

def _get_processed_spectrum(database_id):
    # Finding all the database files
    database_files = glob.glob("/app/workflows/idbac_summarize_database/nf_output/output_spectra_json/**/{}.json".format(os.path.basename(database_id)))

    if len(database_files) == 0:
        return None
    
    if len(database_files) > 1:
        return None

    with open(database_files[0]) as file_handle:
        spectrum_dict = json.load(file_handle)

        return spectrum_dict

if __name__ == "__main__":
    app.run_server(debug=True, port=5000, host="0.0.0.0")
