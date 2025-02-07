# -*- coding: utf-8 -*-
import dash
from dash import dcc
from dash import html
from dash import dash_table
from dash import callback
from dash import ctx  # Dash >=2.9.0
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import json
import plotly
import plotly.express as px
from plotly.graph_objs import Scatter, Figure
import glob

import numpy as np
from scipy.ndimage import uniform_filter1d
import os

import pandas as pd

from dash import html, register_page 

from utils import convert_to_mzml

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
        dbc.InputGroup([
            dbc.Input(id="search-input", placeholder="Enter Database ID...", type="text"),
            dbc.Button("Search", id="search-button", n_clicks=0),
        ], className="mb-3"),
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
    bin_width = 10 # Fixed bin width of 10 for now
    if dev_mode:
        database_files = glob.glob(f"workflows/idbac_summarize_database/nf_output/{str(bin_width)}_da_bin/output_spectra_json/**/{os.path.basename(database_id)}.json")
    else:
        database_files = glob.glob(f"/app/workflows/idbac_summarize_database/nf_output/{str(bin_width)}_da_bin/output_spectra_json/**/{os.path.basename(database_id)}.json")

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

def estimate_convexity(spectrum: dict, rescale:bool=False) -> tuple:
    """
    Estimates the convexity of a spectrum by fitting a quadratic polynomial
    and returning the coefficient of the x^2 term along with the fitted points.

    Args:
        spectrum (dict): The spectrum to estimate the convexity of.
                         Keys are "x" (array of x values) and "y" (array of y values).
        rescale (bool): Whether to rescale the x & y values before fitting.

    Returns:
        tuple: (float, np.ndarray, np.ndarray)
               - The coefficient of the x^2 term in the polynomial fit.
               - The x values of the fit (same as input x values).
               - The fitted y values corresponding to the input x values.
    """
    x = np.array(spectrum["x"])
    y = np.array(spectrum["y"])

    if rescale:
        # Rescale the x values between 0 and 100
        x = (x - np.min(x)) / (np.max(x) - np.min(x)) * 100
        # Rescale the y values between 0 and 100
        y = (y - np.min(y)) / (np.max(y) - np.min(y)) * 100
    
    # Fit a quadratic polynomial
    coefficients = np.polyfit(x, y, 2)
    
    # The coefficient of x^2 is the first coefficient
    convexity = coefficients[0]
    
    # Generate the fitted y values
    fitted_y = np.polyval(coefficients, x)

    print("coefficients", coefficients)
    
    return convexity, x, fitted_y

@callback(
    Output("spectra-container", "children"),
    Output("pagination", "active_page"),
    Input("pagination", "active_page"),
    Input("search-button", "n_clicks"),
    State("search-input", "value"),
    Input('data-store', 'data'),    # Set to input so when data loads asyncronously it triggers a refreshasyncronously 
    prevent_initial_call=False
)
def update_spectra_display(active_page, n_clicks, search_id, data_table):
    if data_table is None:
        return [], 1

    data_table = pd.DataFrame(data_table)

    # Determine if this callback was triggered by the search button
    if ctx.triggered_id == "search-button" and search_id:
        # Find the index of the searched ID
        matching_rows = data_table.index[data_table['database_id'] == search_id].tolist()
        if not matching_rows:
            return dash.no_update  # No match found

        index = matching_rows[0]
        active_page = (index // PAGE_SIZE) + 1  # Calculate the page number

    # Normal pagination handling
    if active_page is None:
        active_page = 1

    start_index = (active_page - 1) * PAGE_SIZE
    end_index = start_index + PAGE_SIZE
    ids_to_display = data_table.iloc[start_index:end_index]['database_id'].values
    if ids_to_display is None:
        return [], active_page
    
    # Create download links for each database id
    download_links = [
        html.A(
            "Download Raw",
            href=f"/api/spectrum/mzml-raw?database_id={database_id}",
            target="_blank",
            style={"margin": "5px"},
        )
        for database_id in ids_to_display
    ]

    spectra_to_display = [_get_processed_spectrum(i) for i in ids_to_display]
    spectra_to_display = [format_spectrum(s) for s in spectra_to_display if s is not None]
    temp = [estimate_convexity(s) for s in spectra_to_display]
    estimated_convexity, x, fitted_y = zip(*temp)
    temp = [estimate_convexity(s, rescale=True) for s in spectra_to_display]
    estimated_convexity_rescaled, x_rescaled, fitted_y_rescaled = zip(*temp)

    children = [
        html.Div(
            [
                html.Div(
                    [
                        f"Database ID: {ids_to_display[idx]}", html.Br(),
                        f"Rescaled Convexity: {estimated_convexity_rescaled[idx].item():.2e}", html.Br(),
                        download_links[idx],
                    ],
                    style={
                        "fontSize": "14px",
                        "fontWeight": "bold",
                        "textAlign": "center",
                        "marginBottom": "5px",
                    },
                ),
                dcc.Graph(
                    figure=Figure(
                        data=[
                            Scatter(
                                x=s["x"],
                                y=s["y"],
                                mode="lines",
                                name="Original Spectrum",
                                line=dict(color="blue"),
                            ),
                            Scatter(
                                x=x[idx],
                                y=fitted_y[idx],
                                mode="lines",
                                name="Fitted Line",
                                line=dict(color="red", dash="dash"),
                            ),
                        ],
                    ).update_layout(
                        title=None,
                        height=300,
                        margin=dict(l=10, r=10, t=10, b=10),
                    ),
                    config={"displayModeBar": False},
                ),
            ],
            style={
                "flex": "1 1 calc(33% - 10px)",
                "min-width": "300px",
                "box-sizing": "border-box",
            },
        )
        for idx, s in enumerate(spectra_to_display)
    ]
    
    return children, active_page
