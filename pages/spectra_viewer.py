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
from plotly.graph_objs import Scatter, Figure
import glob

import os

import pandas as pd

from dash import html, register_page 


dev_mode = False
if not os.path.isdir('/app'):
    dev_mode =  True

register_page(
    __name__,
    name='IDBac Database',
    top_nav=True,
    path='/admin/qc'
)

PAGE_SIZE = 12

SPECTRA_DASHBOARD = html.Div([
    dbc.CardHeader(html.H5("Database Spectra")),
    dbc.CardBody([
        html.Div(
            id="spectra-container",
            style={
                "display": "flex",
                "flex-wrap": "wrap",
                "justify-content": "space-around",
                "gap": "10px",
            },
        ),
        html.Div(
            dbc.Pagination(
                id="pagination",
                max_value=1,
                fully_expanded=False
            ),
            className="mt-3",
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

def _get_processed_spectrum(database_id:str)->dict:
    """ Returns the processed spectrum for a given database id.

    Args:
        database_id (str): The database id to search for.

    Returns:
        dict: The processed spectrum.
    """
    # Finding all the database files
    if dev_mode:
        database_files = glob.glob("workflows/idbac_summarize_database/nf_output/output_spectra_json/**/{}.json".format(os.path.basename(database_id)))
    else:
        database_files = glob.glob("/app/workflows/idbac_summarize_database/nf_output/output_spectra_json/**/{}.json".format(os.path.basename(database_id)))

    if len(database_files) == 0:
        return None
    
    if len(database_files) > 1:
        return None

    with open(database_files[0]) as file_handle:
        spectrum_dict = json.load(file_handle)

        return spectrum_dict

@callback(
    Output("pagination", "max_value"),
    Input('data-store', 'data'),  # Using data from dcc.Store
    prevent_initial_call=True
)
def update_pagination_max(data_table):
    if data_table is None:
        return 0
    # Calculate total pages based on the data table size
    total_items = len(data_table)
    return (total_items + PAGE_SIZE - 1) // PAGE_SIZE

def format_spectrum(spectrum: dict) -> dict:
    """Formats the spectrum for display.

    Args:
        spectrum (dict): The spectrum to format.

    Returns:
        dict: The formatted spectrum.
    """
    peak_dict = spectrum["peaks"]

    x = [float(peak["mz"]) for peak in peak_dict]
    y = [float(peak["i"]) for peak in peak_dict]

    # Sort by mz
    x, y = zip(*sorted(zip(x, y)))

    return {"x": x, "y": y}

@callback(
    Output("spectra-container", "children"),
    Output("pagination", "active_page"),
    Input("pagination", "active_page"),
    Input('data-store', 'data'),  # Using data from dcc.Store
    prevent_initial_call=False
)
def update_spectra_display(active_page, data_table):
    if active_page is None:
        active_page = 1

    if data_table is None:
        return [], active_page

    data_table = pd.DataFrame(data_table)

    start_index = (active_page - 1) * PAGE_SIZE
    end_index = start_index + PAGE_SIZE
    ids_to_display = data_table.iloc[start_index:end_index]['database_id'].values
    if ids_to_display is None:
        return [], active_page

    spectra_to_display = [_get_processed_spectrum(i) for i in ids_to_display]
    spectra_to_display = [format_spectrum(s) for s in spectra_to_display if s is not None]

    # Generate line plots for the current page
    children = [
        html.Div(
            dcc.Graph(
                figure=Figure(
                    data=Scatter(
                        x=s["x"],
                        y=s["y"],
                        mode="lines",
                        line=dict(color="blue"),
                    ),
                ).update_layout(
                    title=f"Spectrum {start_index + idx + 1}",
                    height=300,
                    margin=dict(l=10, r=10, t=30, b=10),
                ),
                config={"displayModeBar": False},
            ),
            style={
                "flex": "1 1 calc(33% - 10px)",
                "min-width": "300px",
                "box-sizing": "border-box",
            },
        )
        for idx, s in enumerate(spectra_to_display)
    ]
    return children, active_page