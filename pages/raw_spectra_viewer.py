# -*- coding: utf-8 -*-
from dash import dcc
from dash import html
from dash import dash_table
from dash import callback
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import json
import plotly
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from plotly.graph_objs import Scatter, Figure
import glob

import numpy as np
from scipy.ndimage import uniform_filter1d
import os

import pandas as pd

from dash import html, register_page 

from utils import convert_to_mzml
from typing import List

dev_mode = False
if not os.path.isdir('/app'):
    dev_mode =  True

register_page(
    __name__,
    name='IDBac Raw Spectra Viewer',
    top_nav=True,
    path='/raw-viewer'
)

PAGE_SIZE = 12

SPECTRA_DASHBOARD = html.Div([
    dbc.CardHeader(html.H5("Raw Database Spectra")),
    dbc.CardBody([
        # User input for database id
        dbc.Input(
            id="database-id",
            placeholder="Enter database ID",
            type="text",
            debounce=True,
            style={"marginBottom": "10px"},
        ),
        html.Div(
            id="raw-spectra",
            style={
                "display": "flex",
                "flex-wrap": "wrap",
                "justify-content": "space-around",
                "gap": "10px",
            },
        ),
    ]),
])

    

BODY = dbc.Container(
    [
        dcc.Location(id='url', refresh=False),
        dbc.Row([
            dbc.Col(
                dbc.Card(SPECTRA_DASHBOARD),
                className="w-100"
            ),
        ], style={"marginTop": 30}),
    ],
    fluid=True,
    className="",
)

def layout(**kwargs):
    return html.Div(children=[BODY,
                               # Store for intermediate data
                                dcc.Store(id='data-store', storage_type='memory'),
    ])

def _get_raw_spectrum(database_id:str)->dict:
    # Finding all the database files
    if database_id.lower().startswith("deleted-"):
        database_files = glob.glob("database/deleted_depositions/**/{}.json".format(os.path.basename(database_id.replace("deleted-", ""))))
    else:
        database_files = glob.glob("database/depositions/**/{}.json".format(os.path.basename(database_id)))

    if len(database_files) == 0:
        return "File not found", 404
    
    if len(database_files) > 1:
        return "Multiple files found", 500
    

    with open(os.path.join(os.path.dirname(database_files[0]), os.path.basename(database_files[0]))) as json_file:
        return json.load(json_file)


def format_spectrum(spectrum: dict) -> List[np.array]:
    """Formats the spectrum for display.

    Args:
        spectrum (dict): The spectrum to format.

    Returns:
        List[np.array]: The formatted spectrum.
    """
    peaks_list = spectrum["spectrum"]

    peaks = [np.array(x) for x in peaks_list]
    sorted_peaks = []
    # Sort eah peak list by mz
    for peak_list in peaks:
        sorted_indices = np.argsort(peak_list[:,0])
        sorted_peaks.append(peak_list[sorted_indices])

    return sorted_peaks

@callback(
    Output("raw-spectra", "children"),
    Input('data-store', 'data'),  # Using data from dcc.Store
    Input("database-id", 'value'),
    Input('url', 'search'),
    prevent_initial_call=False
)
def update_raw_viewer(data_table, database_id, search):
    print("got database_id", database_id, "search", search, flush=True)
    if database_id is None and search is not None:
        database_id = search.split('=')[-1]

    if data_table is None:
        return []

    data_table = pd.DataFrame(data_table)

    if database_id is None:
        database_id = data_table.iloc[0]["database_id"]

    database_id = str(database_id).strip()
    
    # Create download links for each database id
    download_link = html.A(
                            "Download Raw",
                            href=f"/api/spectrum/mzml-raw?database_id={database_id}",
                            target="_blank",
                            style={"margin": "5px"},
                        )

    spectrum_data = _get_raw_spectrum(database_id)
    spectra_to_display = format_spectrum(spectrum_data)

    # Calculate the number of subplots needed
    num_spectra = len(spectra_to_display)

    # Create subplots with shared x-axes
    fig = make_subplots(rows=num_spectra, cols=1, shared_xaxes=True, vertical_spacing=0.02)

    for i, s in enumerate(spectra_to_display, start=1):
        fig.add_trace(go.Scatter(x=s[:, 0], y=s[:, 1], mode='lines', name=f"Replicate {i}"), row=i, col=1)

    fig.update_layout(
        height=200 * num_spectra,
        margin=dict(l=5, r=5, t=5, b=5),
    )
    # Set x-axis title only using annotations
    fig.update_layout(
        annotations=[
            dict(
                text="m/z",
                xref="paper",
                yref="paper",
                x=0.5,
                y=-0.02,
                showarrow=False,
                font=dict(size=14, family="Arial"),
                xanchor="center",
                yanchor="middle"
            ),
            dict(
                text="Intensity",
                xref="paper",
                yref="paper",
                x=-0.10,
                y=0.5,
                showarrow=False,
                font=dict(size=14, family="Arial"),
                textangle=-90,
                xanchor="center",
                yanchor="middle"
            )
        ],
        margin=dict(l=60, r=5, t=5, b=60),
    )

    children = [
        html.Div(
            [
                html.Div(f"Database ID: {database_id}", style={"fontSize": "14px", "fontWeight": "bold", "textAlign": "center", "marginBottom": "5px",}),
                html.Div(download_link, style={"textAlign": "center", "marginBottom": "5px"}),
            ],
            style={"display":"block", "width":"100%"}
        ),
        html.Div(dcc.Graph(figure=fig))
    ]

    return children