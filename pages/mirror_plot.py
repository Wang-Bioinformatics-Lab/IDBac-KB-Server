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

import numba as nb
import numpy as np

from scipy.ndimage import uniform_filter1d
import os

import pandas as pd

from dash import html, register_page 

from utils import convert_to_mzml, fetch_with_retry
import logging
from typing import Tuple

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
        html.H6("Add USI to Analysis", className="mb-3"),
        dbc.InputGroup(
            [
                dcc.Input(
                    id="mirror-plot-usi-input",
                    type="text",
                    placeholder="Enter USI (e.g., mzspec:GNPS2:TASK-00712d4c9c3849b7a5211851a46deefa-nf_output/merged/DFI.2.27.mzML:scan:1)",
                    style={'width': '100%'}
                ),
                dbc.Button("Submit USI", id="mirror-plot-usi-submit", n_clicks=0, color="primary"),
            ],
            className="mb-3",
            style={"display": "flex", "alignItems": "center"}
        ),
        html.H6("Select Data Identifiers to Compare", className="mb-3"),
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
                    html.Label("Mass Range (m/z):"),
                    dcc.RangeSlider(
                        id="mirror-plot-mass-range",
                        min=2_000,
                        max=20_000,
                        step=10,
                        value=[3_000, 20_000],
                        marks=None,
                        tooltip={"placement": "bottom", "always_visible": True},
                    ),
                    html.Label("Bin Size:"),
                    dcc.Dropdown(
                        id='mirror-plot-bin-size',
                        options=[
                            {'label': '10 Da', 'value': 10},
                            {'label': '5 Da', 'value': 5},
                            {'label': '1 Da', 'value': 1},
                        ],
                        value=10,
                        placeholder="Select Bin Size",
                        style={'margin':'5px'},
                    ),
                    html.Label("Presence-Absence Mode:"),
                    dcc.Dropdown(
                        id="presence-absence",
                        options=[
                            {'label': 'Enabled', 'value': True},
                            {'label': 'Disabled', 'value': False},
                        ],
                        value=False,
                        placeholder="Select Presence-Absence Mode",
                        style={'margin':'5px'},
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

def _get_spectrum_resolver(usi:str)->dict:
    """ Returns the exact spectrum specified by the usi.
    Args:
        usi (str): The USI of the spectrum to fetch.
    Returns:
        dict: The spectrum in JSON format.
    """

    # Looks like this: https://metabolomics-usi.gnps2.org/json/?usi1=mzspec%3AGNPS2%3ATASK-ddd9cb3cf41f435ab66c06554836dc5e-gnps_network/specs_ms.mgf%3Ascan%3A714

    r = fetch_with_retry(
        f"https://metabolomics-usi.gnps2.org/json/?usi1={usi}",
    )
    r.raise_for_status()

    j = r.json() # j['peaks] is a list of lists [[mz, intensity], ...]
    if 'peaks' not in j:
        logging.error(f"Failed to fetch spectrum for USI {usi}. Response: {j}")
        return None
    if len(j['peaks']) == 0:
        return {}
    
    # Convert to dict with 'mz' and 'i' keys
    spectrum = {
        'peaks': [{'mz': peak[0], 'i': peak[1]} for peak in sorted(j['peaks'], key=lambda x: x[0])],
    }
    return spectrum

def _get_processed_spectrum(database_id:str, bin_width:int)->dict:
    """ Returns the processed spectrum for a given database_id.

    Args:
        database_id (str): The database_id to search for.

    Returns:
        dict: The processed spectrum.
    """

    if str(database_id).startswith("mzspec"):
        # This is a resolver string, use the spectrum resolver to get the peaks
        return _get_spectrum_resolver(database_id)

    # Finding all the database files
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

@nb.njit
def find_matches(ref_spec_mz: np.ndarray, qry_spec_mz: np.ndarray,
                 tolerance: float, shift: float = 0.0) -> Tuple[np.ndarray, np.ndarray]:
    """Find matching peaks between two spectra."""
    matches_idx1 = np.empty(len(ref_spec_mz) * len(qry_spec_mz), dtype=np.int64)
    matches_idx2 = np.empty_like(matches_idx1)
    match_count = 0
    lowest_idx = 0

    for peak1_idx in range(len(ref_spec_mz)):
        mz = ref_spec_mz[peak1_idx]
        low_bound = mz - tolerance
        high_bound = mz + tolerance

        for peak2_idx in range(lowest_idx, len(qry_spec_mz)):
            mz2 = qry_spec_mz[peak2_idx] - shift
            if mz2 > high_bound:
                break
            if mz2 < low_bound:
                lowest_idx = peak2_idx
            else:
                matches_idx1[match_count] = peak1_idx
                matches_idx2[match_count] = peak2_idx
                match_count += 1

    return matches_idx1[:match_count], matches_idx2[:match_count]

@nb.njit
def collect_peak_pairs(ref_spec: np.ndarray, qry_spec: np.ndarray, min_matched_peak: int, sqrt_transform: bool,
                       tolerance: float, shift: float = 0.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Find and score matching peak pairs between spectra."""

    if len(ref_spec) == 0 or len(qry_spec) == 0:
        return np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.float32)

    # Exact matching
    matches_idx1, matches_idx2 = find_matches(ref_spec[:, 0], qry_spec[:, 0], tolerance, 0.0)

    # If shift is not 0, perform hybrid search
    if abs(shift) > 1e-6:
        matches_idx1_shift, matches_idx2_shift = find_matches(ref_spec[:, 0], qry_spec[:, 0], tolerance, shift)
        matches_idx1 = np.concatenate((matches_idx1, matches_idx1_shift))
        matches_idx2 = np.concatenate((matches_idx2, matches_idx2_shift))

    if len(matches_idx1) < min_matched_peak:
        return np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.float32)

    # Calculate scores for matches
    if sqrt_transform:
        scores = np.sqrt(ref_spec[matches_idx1, 1] * qry_spec[matches_idx2, 1]).astype(np.float32)
    else:
        scores = (ref_spec[matches_idx1, 1] * qry_spec[matches_idx2, 1]).astype(np.float32)

    # Sort by score descending
    sort_idx = np.argsort(-scores)
    return matches_idx1[sort_idx], matches_idx2[sort_idx], scores[sort_idx]


@nb.njit
def score_matches(matches_idx1: np.ndarray, matches_idx2: np.ndarray,
                  scores: np.ndarray, ref_spec: np.ndarray, qry_spec: np.ndarray,
                  sqrt_transform: bool, penalty: float):
    """Calculate final similarity score from matching peaks."""

    # Use boolean arrays for tracking used peaks - initialized to False
    used1 = np.zeros(len(ref_spec), dtype=nb.boolean)
    used2 = np.zeros(len(qry_spec), dtype=nb.boolean)

    total_score = 0.0
    used_matches = 0

    # Find best non-overlapping matches
    for i in range(len(matches_idx1)):
        idx1 = matches_idx1[i]
        idx2 = matches_idx2[i]
        if not used1[idx1] and not used2[idx2]:
            total_score += scores[i]
            used1[idx1] = True
            used2[idx2] = True
            used_matches += 1

    if used_matches == 0:
        return 0.0, 0

    # # Sum intensities of matched peaks
    # matched_intensities = np.zeros(used_matches, dtype=np.float32)

    # new intensities of qry peaks, matched peaks are the same, others are penalized
    new_qry_intensities = np.zeros(len(qry_spec), dtype=np.float32)

    match_idx = 0
    for i in range(len(qry_spec)):
        if used2[i]:
            # matched_intensities[match_idx] = qry_spec[i, 1]
            new_qry_intensities[i] = qry_spec[i, 1]
            match_idx += 1
        else:
            new_qry_intensities[i] = qry_spec[i, 1] * (1 - penalty)

    if sqrt_transform:
        norm1 = np.sqrt(np.sum(np.sqrt(ref_spec[:, 1] * ref_spec[:, 1])))
        norm2 = np.sqrt(np.sum(np.sqrt(new_qry_intensities * new_qry_intensities)))
    else:
        norm1 = np.sqrt(np.sum(ref_spec[:, 1] * ref_spec[:, 1]))
        norm2 = np.sqrt(np.sum(new_qry_intensities * new_qry_intensities))

    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0, used_matches

    score = total_score / (norm1 * norm2)

    return min(float(score), 1.0), used_matches


def cosine_similarity(qry_spec: np.ndarray, ref_spec: np.ndarray,
                      tolerance: float = 0.1,
                      min_matched_peak: int = 1,
                      sqrt_transform: bool = True,
                      penalty: float = 0.,
                      shift: float = 0.0):
    """
    Calculate similarity between two spectra.

    Parameters
    ----------
    qry_spec: np.ndarray
        Query spectrum.
    ref_spec: np.ndarray
        Reference spectrum.
    tolerance: float
        Tolerance for m/z matching.
    min_matched_peak: int
        Minimum number of matched peaks.
    sqrt_transform: bool
        If True, use square root transformation.
    penalty: float
        Penalty for unmatched peaks. If set to 0, traditional cosine score; if set to 1, traditional reverse cosine score.
    shift: float
        Shift for m/z values. If not 0, hybrid search is performed. shift = prec_mz(qry) - prec_mz(ref)
    """
    tolerance = np.float32(tolerance)
    penalty = np.float32(penalty)
    shift = np.float32(shift)

    if qry_spec.size == 0 or ref_spec.size == 0:
        return (0.0, 0), np.array([]), np.array([])

    # normalize the intensity
    ref_spec[:, 1] /= np.max(ref_spec[:, 1])
    qry_spec[:, 1] /= np.max(qry_spec[:, 1])

    matches_idx1, matches_idx2, scores = collect_peak_pairs(
        ref_spec, qry_spec, min_matched_peak, sqrt_transform,
        tolerance, shift
    )

    if len(matches_idx1) == 0:
        return (0.0, 0), np.array([]), np.array([])

    return score_matches(
        matches_idx1, matches_idx2, scores,
        ref_spec, qry_spec, sqrt_transform, penalty
    ), matches_idx2, matches_idx1   # Note this is reversed, this is correct based on return from collect_peak_pairs

def create_mirror_plot(spectrum_a, spectrum_b=None, mass_range=None, mass_tolerance=0.1):
    """ Creates a mirror plot of two spectra using stem plots and computes cosine similarity.

    Args:
        spectrum_a (dict): The first spectrum.
        spectrum_b (dict, optional): The second spectrum.
        mass_range (tuple, optional): The mass range to filter peaks (min, max).
        mass_tolerance (float, optional): The mass tolerance for matching peaks.

    Returns:
        tuple: (Figure, cosine similarity score)
    """
    fig = Figure()

    def filter_mass_range(mz_values, intensity_values, mass_range):
        """Filters the mz and intensity values based on the mass range."""
        if mass_range is None:
            return mz_values, intensity_values
        mask = (mz_values >= mass_range[0]) & (mz_values <= mass_range[1])
        return mz_values[mask], intensity_values[mask]

    def add_stem_trace(fig, mz_values, intensity_values, color):
        """Adds a stem plot trace for given mz and intensity values."""
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
    mz_a = np.array([x['mz'] for x in spectrum_a['peaks']])
    i_a = np.array([x['i'] for x in spectrum_a['peaks']])
    mz_a, i_a = filter_mass_range(mz_a, i_a, mass_range)
    sorted_indices = np.argsort(mz_a)
    mz_a = mz_a[sorted_indices]
    i_a = i_a[sorted_indices]
    # Normalize intensities
    if len(i_a) > 0:
        i_a = i_a / np.max(i_a) * 100.0
    spectrum_a = np.column_stack((mz_a, i_a))

    cosine_score = None  # Default in case there's no second spectrum

    if spectrum_b:
        # Second spectrum (inverted intensities)
        mz_b = np.array([x['mz'] for x in spectrum_b['peaks']])
        i_b = np.array([x['i'] for x in spectrum_b['peaks']])
        mz_b, i_b = filter_mass_range(mz_b, i_b, mass_range)
        sorted_indices = np.argsort(mz_b)
        mz_b = mz_b[sorted_indices]
        i_b = i_b[sorted_indices]
        # Normalize intensities
        if len(i_b) > 0:
            i_b = i_b / np.max(i_b) * 100.0
        spectrum_b = np.column_stack((mz_b, i_b))

        (cosine_score, num_matched_peaks), used_peaks_a, used_peaks_b = cosine_similarity(
            qry_spec=spectrum_a,
            ref_spec=spectrum_b,
            tolerance=mass_tolerance,
            min_matched_peak=1,
            sqrt_transform=False,
            penalty=0.0
        )

        if len(used_peaks_a)>0:
            matched_mz_a = mz_a[used_peaks_a]   # Contains indices of matched peaks
            matched_i_a = i_a[used_peaks_a]
        else:
            matched_mz_a = np.array([])
            matched_i_a = np.array([])

        if len(used_peaks_b)>0:
            matched_mz_b = mz_b[used_peaks_b]
            matched_i_b = i_b[used_peaks_b]
        else:
            matched_mz_b = np.array([])
            matched_i_b = np.array([])

        unmatched_mz_a = mz_a[np.setdiff1d(np.arange(len(mz_a)), used_peaks_a)]
        unmatched_i_a = i_a[np.setdiff1d(np.arange(len(i_a)), used_peaks_a)]
        unmatched_mz_b = mz_b[np.setdiff1d(np.arange(len(mz_b)), used_peaks_b)]
        unmatched_i_b = i_b[np.setdiff1d(np.arange(len(i_b)), used_peaks_b)]

        print(used_peaks_a)

        # Plot matched peaks in green
        add_stem_trace(fig, matched_mz_a, matched_i_a, 'green')
        add_stem_trace(fig, matched_mz_b, -1 * matched_i_b, 'green')

        # Plot unmatched peaks in blue (spectrum A) and red (spectrum B)
        add_stem_trace(fig, unmatched_mz_a, unmatched_i_a, 'blue')
        add_stem_trace(fig, unmatched_mz_b, -1 * unmatched_i_b, 'red')
    else:
        # If there's only one spectrum, plot everything in blue
        add_stem_trace(fig, mz_a, i_a, 'blue')

    # Adjust x-axis range if specified
    if mass_range:
        fig.update_xaxes(range=(mass_range[0]-50, mass_range[1]+50))

    return fig, cosine_score

@callback(
    Output("data-store", "data", allow_duplicate=True),
    Input("mirror-plot-usi-submit", "n_clicks"),
    State("mirror-plot-usi-input", "value"),
    State("data-store", "data"),
    prevent_initial_call=True,
)
def update_data_store(n_clicks, usi, data_store):
    """ Updates the data store with the spectrum data from the USI input.

    Args:
        n_clicks (int): The number of clicks on the submit button.
        usi (str): The USI of the spectrum to fetch.

    Returns:
        dict: The data store containing strain names and database IDs.
    """
    logging.info(f"Adding USI {usi} to data store.")
    print(f"Adding USI {usi} to data store.", flush=True)
    if not usi:
        return dash.no_update

    # Fetch the spectrum using the USI
    spectrum = _get_spectrum_resolver(usi)
    if not spectrum or 'peaks' not in spectrum or len(spectrum['peaks']) == 0:
        return dash.no_update

    # Add the usi to the store as an option
    new_value =  {
        "Strain name": usi,
        "database_id": usi,
    }

    if data_store is None:
        data_store = [new_value]
    else:
        data_store.append(new_value)

    logging.info(f"Successfully added USI {usi} to data store.")
    print(f"Successfully added USI {usi} to data store.", flush=True)

    return data_store

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
        data (dict): The data store containing strain names and database IDs.

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
    State("mirror-plot-bin-size", "value"),
    State("presence-absence", "value"),
    Input("mirror-plot-update", "n_clicks"),
    prevent_initial_call=True,
)
def update_plot(input_a, input_b, mass_range, bin_size, presence, n_clicks):
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
    spectrum_a = _get_processed_spectrum(database_id_a, bin_size)
    spectrum_b = _get_processed_spectrum(database_id_b, bin_size)

    # If presence-absence set nonzero intensities to 1
    if presence and spectrum_a is not None:
        for peak in spectrum_a['peaks']:
            if peak['i'] > 0:
                peak['i'] = 1.0
    if presence and spectrum_b is not None:
        for peak in spectrum_b['peaks']:
            if peak['i'] > 0:
                peak['i'] = 1.0

    # Create the mirror plot
    fig, cos_sim = create_mirror_plot(spectrum_a, spectrum_b, mass_range)

    fig.update_layout(
        title=f"Mirror Plot of Spectra, Cosine Similarity: {cos_sim:.2f}" if cos_sim else "Mirror Plot of Spectrum A",
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

