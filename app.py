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
from flask import Flask, send_from_directory

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
app = dash.Dash(__name__, server=server, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title = 'Wang Lab - IDBac KB'

cache = Cache(app.server, config={
    'CACHE_TYPE': 'filesystem',
    'CACHE_DIR': 'temp/flask-cache',
    'CACHE_DEFAULT_TIMEOUT': 0,
    'CACHE_THRESHOLD': 10000
})

_env = dotenv_values()

server = app.server

# setting tracking token
app.index_string = """<!DOCTYPE html>
<html>
    <head>
        <!-- Umami Analytics -->
        <script async defer data-website-id="ENTER YOUR TOKEN HERE" src="https://analytics.gnps2.org/umami.js"></script>
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
            html.Img(src="https://gnps2.org/static/img/logo.png", width="120px"),
            href="https://mingxunwang.com"
        ),
        dbc.Nav(
            [
                dbc.NavItem(dbc.NavLink("Wang Bioinformatics Lab - IDBac Knowledgebase - Version 0.1", href="#")),
                dbc.NavItem(dbc.NavLink("Download Summary", href="/api/spectra")),
            ],
        navbar=True)
    ],
    color="light",
    dark=False,
    sticky="top",
)

DATASELECTION_CARD = [
    dbc.CardHeader(html.H5("IDBac KB Spectra List")),
    dbc.CardBody(
        [   
            html.Div([
                dash_table.DataTable(
                    id='displaytable',
                    columns=[],
                    data=[],
                    row_selectable='single',
                    page_size=10,
                    sort_action='native',
                    filter_action='native',
                    export_format='xlsx',
                    export_headers='display')
            ],
            id="displaycontent")
        ]
    )
]

LEFT_DASHBOARD = [
    html.Div(
        [
            html.Div(DATASELECTION_CARD),
        ]
    )
]

MIDDLE_DASHBOARD = [
    dbc.CardHeader(html.H5("Data Exploration")),
    dbc.CardBody(
        [
            dcc.Loading(
                id="output",
                children=[html.Div([html.Div(id="loading-output-23")])],
                type="default",
            ),
        ]
    )
]

CONTRIBUTORS_DASHBOARD = [
    dbc.CardHeader(html.H5("Contributors")),
    dbc.CardBody(
        [
            "Mingxun Wang PhD - UC Riverside",
            html.Br(),
            html.Br(),
            html.H5("Citation"),
            html.A('Mingxun Wang, Jeremy J. Carver, Vanessa V. Phelan, Laura M. Sanchez, Neha Garg, Yao Peng, Don Duy Nguyen et al. "Sharing and community curation of mass spectrometry data with Global Natural Products Social Molecular Networking." Nature biotechnology 34, no. 8 (2016): 828. PMID: 27504778', 
                    href="https://www.nature.com/articles/nbt.3597"),
            html.Br(),
            html.Br(),
            html.A('Checkout our other work!', 
                href="https://www.cs.ucr.edu/~mingxunw/")
        ]
    )
]

EXAMPLES_DASHBOARD = [
    dbc.CardHeader(html.H5("Examples")),
    dbc.CardBody(
        [
            html.A('Basic', 
                    href=""),
        ]
    )
]

BODY = dbc.Container(
    [
        dcc.Location(id='url', refresh=False),
        dbc.Row([
            dbc.Col(
                dbc.Card(LEFT_DASHBOARD),
                className="w-100"
            ),
        ], style={"marginTop": 30}),
        dbc.Row([
            dbc.Col(
                [
                    dbc.Card(MIDDLE_DASHBOARD),
                ],
                className="w-50"
            ),
            dbc.Col(
                [
                    dbc.Card(CONTRIBUTORS_DASHBOARD),
                ],
                className="w-50"
            ),
        ], style={"marginTop": 30}),
    ],
    fluid=True,
    className="",
)

app.layout = html.Div(children=[NAVBAR, BODY])

def _get_url_param(param_dict, key, default):
    return param_dict.get(key, [default])[0]

@app.callback([
                Output('displaytable', 'data'),
                Output('displaytable', 'columns')
              ],
              [Input('url', 'search')])
def display_table(search):
    summary_df = pd.read_csv("database/summary.tsv", sep="\t")

    columns = [{"name": i, "id": i} for i in summary_df.columns]
    data = summary_df.to_dict('records')
    
    return [data, columns]


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
    task_result.get()

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
