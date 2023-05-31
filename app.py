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
            html.Img(src="https://gnps-cytoscape.ucsd.edu/static/img/GNPS_logo.png", width="120px"),
            href="https://mingxunwang.com"
        ),
        dbc.Nav(
            [
                dbc.NavItem(dbc.NavLink("Wang Bioinformatics Lab - IDBac Knowledgebase - Version 0.1", href="#")),
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
            html.Div(id="displaycontent")
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
                html.Div(),
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
                Output('displaycontent', 'children')
              ],
              [Input('url', 'search')])
def display_table(search):
    summary_df = pd.read_csv("database/summary.tsv", sep="\t")

    # Creating plotly dash table
    table = dash_table.DataTable(
        id='table',
        columns=[{"name": i, "id": i} for i in summary_df.columns],
        data=summary_df.to_dict('records'),
        page_size=10)
    
    return [[table]]


# API
@server.route("/api")
def api():
    return "Up"

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

    # Calling task to summarize and update the catalog
    tasks.task_summarize_depositions.delay()

    # Enable this call to be blocking
    return "DONE"

@server.route("/api/spectrum", methods=["GET"])
def download():
    # Getting a single spectrum
    database_id = request.values.get("database_id")

    # send back the file
    return send_from_directory("database/depositions", database_id + ".json")

@server.route("/api/spectra", methods=["GET"])
def spectra_list():
    # Parse summary
    summary_df = pd.read_csv("database/summary.tsv", sep="\t")

    # return json
    return summary_df.to_json(orient="records")

if __name__ == "__main__":
    app.run_server(debug=True, port=5000, host="0.0.0.0")
