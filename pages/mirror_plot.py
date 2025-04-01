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
import logging

dev_mode = False
if not os.path.isdir('/app'):
    dev_mode =  True

register_page(
    __name__,
    name='IDBac Database',
    top_nav=True,
    path='/admin/mirror_plot'
)

PAGE_SIZE = 12

SPECTRA_DASHBOARD = html.Div([
    dbc.CardHeader(html.H5("Processed Database Spectra")),
    dbc.CardBody([
        dbc.RadioItems(
            id="mirror-plot-search-type",
            options=[
                {"label": "Search by Strain Name", "value": "strain_name"},
                {"label": "Search by Database ID", "value": "database_id"},
            ],
            value="strain_name",
            inline=True,
            className="mb-3"
        ),
        html.Div(
            id="mirror-plot-input-container", children=[
                    dcc.Dropdown(
                        id="mirror-plot-input-a",
                        placeholder="Select Data Identifier A",
                        style={'margin':'5px'},
                        options=[],
                        multi=False
                    ),
                    dcc.Dropdown(
                        id="mirror-plot-input-b",
                        placeholder="Select Data Identifier B",
                        style={'margin':'5px'},
                        options=[],
                        multi=False
                    ),
                    # Mass Range
                    dcc.RangeSlider(
                        id="mirror-plot-mass-range",
                        min=2_000,
                        max=20_000,
                        step=10,
                        value=[3_000, 20_000],
                        marks=None,
                        tooltip={"placement": "bottom", "always_visible": True},
                    ),
                    # Update Plot Button
                    dbc.Button("Update Plot", id="mirror-plot-update", n_clicks=0),

            ]),
        html.Div(
            id="mirror-plot-container",
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

def _get_processed_spectrum(database_id:str)->dict:
    """ Returns the processed spectrum for a given database_id.

    Args:
        database_id (str): The database_id to search for.

    Returns:
        dict: The processed spectrum.
    """
    # Finding all the database files
    bin_width = 10 # Fixed bin width of 10 for now
    if dev_mode:
        database_files = glob.glob(f"workflows/idbac_summarize_database/nf_output/{str(bin_width)}_da_bin/output_spectra_json/**/{database_id}.json")
    else:
        database_files = glob.glob(f"/app/workflows/idbac_summarize_database/nf_output/{str(bin_width)}_da_bin/output_spectra_json/**/{database_id}.json")

    if len(database_files) == 0:
        return None
    
    if len(database_files) > 1:
        return None

    with open(database_files[0]) as file_handle:
        spectrum_dict = json.load(file_handle)

        return spectrum_dict

def get_id_from_name(strain_name:str, data:dict)->str:
    """ Returns the database ID for a given strain name.

    Args:
        strain_name (str): The strain name to search for.
        data (dict): The data store.

    Returns:
        str: The database ID.
    """
    if strain_name == "" or strain_name is None:
        logging.warning("No strain name provided to get_id_from_name.")
        return None, "No strain name provided."

    candidates = [x for x in data['Strain name'] == strain_name]
    if len(candidates) == 0:
        return None, "No matching database ID found."
    if len(candidates) > 1:
        logging.warning(f"Multiple candidates found for strain name {strain_name}.")
        return candidates[0], "Multiple candidates found."
    return candidates[0], None

def create_mirror_plot(spectrum_a, spectrum_b=None, mass_range=None):
    """ Creates a mirror plot of two spectra using stem plots without markers at the end.

    Args:
        spectrum_a (dict): The first spectrum.
        spectrum_b (dict, optional): The second spectrum.

    Returns:
        Figure: The mirror plot figure.
    """
    fig = Figure()

    def filter_mass_range(mz_values, intensity_values, mass_range):
        """ Filters the mz and intensity values based on the mass range.

        Args:
            mz_values (list): The mz values.
            intensity_values (list): The intensity values.
            mass_range (list): The mass range.

        Returns:
            tuple: Filtered mz and intensity values.
        """
        if mass_range is None:
            return mz_values, intensity_values
        mask = (mz_values >= mass_range[0]) & (mz_values <= mass_range[1])
        return mz_values[mask], intensity_values[mask]

    # Function to create stem plot traces without markers
    def add_stem_trace(fig, mz_values, intensity_values, color):
        for mz, intensity in zip(mz_values, intensity_values):
            fig.add_trace(
                Scatter(
                    x=[mz, mz], 
                    y=[0, intensity], 
                    mode='lines',
                    line=dict(color=color, width=1),
                    showlegend=False
                )
            )

    # First spectrum
    mz_a = [x['mz'] for x in spectrum_a['peaks']]
    i_a = [x['i'] for x in spectrum_a['peaks']]
    mz_a, i_a = filter_mass_range(np.array(mz_a), np.array(i_a), mass_range)
    add_stem_trace(fig, mz_a, i_a, 'blue')

    if spectrum_b:
        # Second spectrum (inverted intensities)
        mz_b = [x['mz'] for x in spectrum_b['peaks']]
        i_b = [-x['i'] for x in spectrum_b['peaks']]
        mz_b, i_b = filter_mass_range(np.array(mz_b), np.array(i_b), mass_range)
        add_stem_trace(fig, mz_b, i_b, 'red')

    if mass_range:
        fig.update_xaxes(range=(mass_range[0]-50, mass_range[1]+50))
    return fig

@callback(
    Output("mirror-plot-input-a", "options"),
    Output("mirror-plot-input-b", "options"),
    Input("mirror-plot-search-type", "value"),
    Input("data-store", "data"),
    prevent_initial_call=False,
)
def update_input_options(search_type, data):
    """ Updates the options for the input dropdowns based on the data store.

    Args:
        search_type (str): The selected search type.
        data (dict): The data store.

    Returns:
        list: The options for the input dropdowns.
    """
    if data is None:
        return [], []

    names = [x["Strain name"] for x in data]
    db_ids = [x["database_id"] for x in data]

    if search_type == "strain_name":
        options = [{"label": "None", "value": ""}] + [{"label": name, "value": db_id} for name, db_id in zip(names, db_ids)]
    elif search_type == "database_id":
        options = [{"label": "None", "value": ""}] + [{"label": db_id, "value": db_id} for name, db_id in zip(names, db_ids)]
    else:
        raise ValueError("Invalid search type")
        
    return options, options

# Callback that sets inputs from URL if not specied
@callback(
    Output("mirror-plot-input-a", "value"),
    Output("mirror-plot-input-b", "value"),
    Output("mirror-plot-search-type", "value"),
    Input("url", "search"),
    Input("data-store", "data"),
)
def set_inputs_from_url(search, _):
    """ Sets the inputs from the URL if not specified.

    Args:
        search (str): The URL search string.

    Returns:
        str: The values for the input dropdowns.
    """
    if search is None or search == "":
        return "", "", "strain_name"
    
    params = dict(param.split("=") for param in search[1:].split("&"))
    input_a = params.get("input_a", "")
    input_b = params.get("input_b", "None")
    search_type = params.get("search_type", "strain_name")

    print("Automatically setting inputs from URL:")
    print(f"Input A: {input_a}", flush=True)
    print(f"Input B: {input_b}", flush=True)
    print(f"Search Type: {search_type}", flush=True)

    return input_a, input_b, search_type

@callback(
    Output("mirror-plot-container", "children"),
    State("mirror-plot-input-a", "value"),
    State("mirror-plot-input-b", "value"),
    State("mirror-plot-mass-range", "value"),
    Input("mirror-plot-update", "n_clicks"),
    prevent_initial_call=True,
)
def update_plot(input_a, input_b, mass_range, n_clicks):
    """ Updates the search input based on the selected search type.
    Args:
        input_a (str): The value of the first input.
        input_b (str): The value of the second input.
        data (dict): The data store.
        n_clicks (int): The number of clicks on the update button."
    """
    if input_a is None or input_a == "":
        return html.Div("Please select a valid input for A.")

    database_id_a = input_a
    database_id_b = input_b


    # Mirror plot of spectra with optional bottom plot
    spectrum_a = _get_processed_spectrum(database_id_a)
    spectrum_b = _get_processed_spectrum(database_id_b)

    # Create the mirror plot
    fig = create_mirror_plot(spectrum_a, spectrum_b, mass_range)

    fig.update_layout(
        title="Mirror Plot of Spectra",
        xaxis_title="m/z",
        yaxis_title="Intensity",
        showlegend=False,
        width=800,
        height=600,
    )

    return html.Div([
        dcc.Graph(
            id="mirror-plot",
            figure=fig,
            style={"width": "100%", "height": "100%"},
        ),
        html.Div(id="mirror-plot-output"),
    ])

