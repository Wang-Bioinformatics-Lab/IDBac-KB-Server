# -*- coding: utf-8 -*-
from dash import dcc
from dash import html
from dash import dash_table
from dash import callback
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import plotly.express as px
import os
from io import BytesIO

import pandas as pd

import dash
from dash import html, register_page  #, callback # If you need callbacks, import it here.

from data_loader import load_database

# from app import server
# memory_cache = Cache(config={
#     'CACHE_TYPE': 'simple', 
#     'CACHE_DEFAULT_TIMEOUT': 0, 
#     'CACHE_THRESHOLD': 10,  # Keep your threshold setting
# })
# memory_cache.init_app(server) 


PLOTLY_EXPORT_CONFIG = config = {
  'toImageButtonOptions': {
    'format': 'png', # one of png, svg, jpeg, webp
    'filename': 'IDBac',
    'scale': 5 
  }
}

register_page(
    __name__,
    name='IDBac Database',
    top_nav=True,
    path='/knowledgebase'
)

MAINTENANCE_STATUS = dbc.Alert(
    [
        html.H5("Maintenance Status Update", className="alert-heading"),
        html.P("The database is currently under maintenance and values may change. Anticipated completion is 5/12/2025 at 15:00 PST."),
        html.P("If you have any questions, please contact us at nkrull@uic.edu."),
    ],
    color="warning",
    dismissable=True,
)

STATUS_BANNER = dbc.Row(
    [
        # dbc.Col(
        #     MAINTENANCE_STATUS,
        #     width=12,
        # )
    ],
    # style={"marginTop": 30},
)

DATASELECTION_CARD = [
    dbc.CardHeader(html.H5("IDBac-KB Spectra List")),
    dbc.CardBody(
        [   
            html.Div([
                dash_table.DataTable(
                    id='displaytable',
                    columns=[],
                    data=[],
                    hidden_columns=[],
                    row_selectable='single',
                    # --- Properties for Server-Side Pagination, Sorting, and Filtering ---
                    page_action='custom',
                    page_current=0, # Start at the first page
                    page_size=10,   # Number of rows per page
                    page_count=1,   # Will be updated in the callback
                    sort_action='custom',
                    sort_mode='multi', # Optional, but common for server-side
                    filter_action='custom',
                    # --------------------------------------------------------------------
                    export_format='none',
                    export_headers='display',
                    filter_options={'case': 'insensitive',
                                    'placeholder_text': 'Filter table...'},
                    style_header={
                        'backgroundColor': "#e9e9e9",
                        'color': '#3a3a3a',
                        'whiteSpace': 'normal',
                        },
                    style_filter={
                            'backgroundColor': '#e9e9e9',
                            'color': '#3a3a3a',
                            'fontStyle': 'italic',
                        },
                    style_table={
                        'width': '100%',
                        'overflowX': 'auto',
                    },
                    )
                    
            ],
            id="displaycontent"),
            html.Br(),
            dbc.Row(
            dbc.Col(
                    dbc.Button("Download Table as CSV", id="download-button", color="primary"),
                    className="d-flex justify-content-end"
                )
            ),
            dcc.Download(id="download-dataframe-csv"),
            html.Br(),
            html.Div(id="update-summary")

        ]
    )
]

DB_DISPLAY_DASHBOARD = [
    html.Div(
        [
            html.Div(DATASELECTION_CARD, ),
        ]
    )
]

MIDDLE_DASHBOARD = [
    dbc.CardHeader(html.H5("Data Exploration")),
    dbc.CardBody(
        [   
            # Select bin size for the histogram
            dbc.InputGroup(
                [
                    dbc.InputGroupText("Bin Size"),
                    dbc.Select(id="spectra-bin-size",
                              options=[
                                  {"label": "1 Da", "value": 1},
                                  {"label": "5 Da", "value": 5},
                                  {"label": "10 Da", "value": 10},
                                ],
                              value=10,
                            ),
                ],
                id="spectra-bin-size-input",
                style={"display": "none"},
            ),
            dcc.Loading(
                id="spectra-plot",
                children=[html.Div([html.Div(id="loading-output-23")])],
                type="default",
            ),
            # Wrap ButtonGroup inside Row and Col to center it
            dbc.Row(
                dbc.Col(
                    dbc.ButtonGroup(
                        [
                            dbc.Button("Download Binned", color="primary", id="download-binned-spectra"),
                            dbc.Button("Download Raw", color="primary", id="download-raw-spectra"),
                            dbc.Button("View Raw", color="primary", id="view-raw-spectra", href=""),
                        ],
                        id="download-buttons",
                        style={"display": "none", "width": "100%"}
                    ),
                    width="auto",  # Center in a 12-column grid
                ),
                className="d-flex justify-content-center"
            ),
            dcc.Download(id="download-raw-mzml"),
            dcc.Download(id="download-binned-mzml"),
        ]
    )
]

@callback(
    Output('view-raw-spectra', 'href'),
    Input('displaytable', 'derived_virtual_selected_rows'),
    State('displaytable', 'derived_virtual_data'),
)
def update_view_raw_link(selected_rows, table_data):
    if selected_rows is None or len(selected_rows) == 0:
        return ""
    
    selected_row = table_data[selected_rows[0]]
    database_id = selected_row["database_id"]
    return f"/raw-viewer/?database_id={database_id}"

@callback(
    Output("download-dataframe-csv", "data"),
    Input("download-button", "n_clicks"),
    prevent_initial_call=True
)
def download_table_as_csv(n_clicks):
    database = pd.DataFrame(load_database(None)[0])
    if database is None or database.empty:
        return dash.no_update
    df = pd.DataFrame(database)
    return dcc.send_data_frame(df.to_csv, "IDBac_KB_Spectra_List.csv", index=False)


db_content_dropdown_options = [
    # {'label': 'Kingdom', 'value': 'Kingdom'},
    {'label': 'Phylum', 'value': 'phylum'},
    {'label': 'Class', 'value': 'class'},
    {'label': 'Order', 'value': 'order'},
    {'label': 'Family', 'value': 'family'},
    {'label': 'Genus', 'value': 'genus'},
    {'label': 'Species', 'value': 'species'}
]

tax_tree = None
try:
    if not os.path.exists("/app/assets/tree.png"):
        raise FileNotFoundError()
    tax_tree = html.Div(
        [
            html.H5(
                "Taxonomic Tree",
                style={"color": "#2a3f5f", "fontSize": "1.1rem", "textAlign": "center"}
            ),
            html.Img(
                src="/download_tree_png",
                style={
                    "width": "75%",      # relative to column width
                    "maxWidth": "612px", # never bigger than 612px
                    "height": "auto",    # keep aspect ratio
                    "margin": "0 auto",
                    "display": "block"
                }
            ),
        ],
        style={
            "display": "flex",
            "flexDirection": "column",
            "alignItems": "center",
            "justifyContent": "flex-start",  # heading pinned at top
            "height": "100%"
        }
    )
except Exception as e:
    print("Error loading taxonomic tree", e)
    tax_tree = None

TREE_DOWNLOAD_BUTTONS = dbc.Row(
                                [   # The buttons linking to images aren't playing nicely here, so use html.A instead
                                    dbc.Col(
                                        html.A(dbc.Button("Download SVG", color="primary", className="mr-1"),
                                                href="/download_tree_svg"),
                                        width="auto"
                                    ),
                                    dbc.Col(
                                        html.A(dbc.Button("Download PNG", color="primary", className="mr-1"),
                                                href="/download_tree_png"),
                                        width="auto"
                                    )
                                ],
                                justify="center"  # This centers the columns in the row
                            )

# Count of Spectra, Bar Chart of Taxonomy
DATABASE_CONTENTS = [
    dbc.CardHeader(html.H5("Knowledgebase Contents")),
    dbc.CardBody(
        [
            # Top heading
            html.H3(
                id="database-contents-text",
                style={"color": "#d88000", "marginBottom": "20px"},
                className="text-center"
            ),

            # Row with pie chart and taxonomic tree
            dbc.Row(
                [
                    # Left column: pie chart + dropdown
                    dbc.Col(
                        [
                            dcc.Graph(
                                id="dynamic-taxonomy-pie-chart",
                                config=PLOTLY_EXPORT_CONFIG,
                                style={"height": "650px"}  # fixed height keeps annotation stable
                            ),
                            html.Div(
                                dcc.Dropdown(
                                    id='taxonomy-dropdown',
                                    options=db_content_dropdown_options,
                                    value='genus',
                                    clearable=False,
                                    className="mb-3",
                                    style={"width": "60%"}
                                ),
                                style={"display": "flex", "justifyContent": "center"}
                            ),
                        ],
                        xs=12, md=6,  # stack on mobile, side-by-side on medium+
                        className="d-flex flex-column"
                    ),

                    # Right column: taxonomic tree + heading + buttons
                    dbc.Col(
                        [
                            html.Div(
                                [
                                    html.H5(
                                        "Taxonomic Tree",
                                        style={"color": "#2a3f5f", "fontSize": "1.1rem", "textAlign": "center", "marginTop": "10px"}
                                    ),
                                    html.Img(
                                        src="/download_tree_png",
                                        style={
                                            "width": "75%",
                                            "maxWidth": "612px",
                                            "height": "auto",
                                            "margin": "0 auto",
                                            "display": "block"
                                        }
                                    ),
                                    TREE_DOWNLOAD_BUTTONS if tax_tree else None
                                ],
                                style={
                                    "display": "flex",
                                    "flexDirection": "column",
                                    "alignItems": "center",
                                    "justifyContent": "flex-start",  # heading pinned at top
                                    "height": "100%"
                                }
                            )
                        ],
                        xs=12, md=6,
                        className="d-flex flex-column",
                        style={
                            "borderLeft": "2px solid #ccc",
                            "borderLeftWidth": "2px",
                            "borderLeftStyle": "solid",
                            "borderLeftColor": "#ccc"
                        }
                    ),
                ],
                align="start"  # align columns at top
            ),
        ]
    )
]


ADDITIONAL_DATA = [
    dbc.CardHeader(html.H5("Additional Data")),
    dbc.CardBody(
        [
            dcc.Loading(
                id="additional-data",
                children=[html.Div([html.Div(id="loading-output-24")])],
                type="default",
            ),
        ]
    )
]

CONTRIBUTORS_DASHBOARD = [
    dbc.CardHeader(html.H5("Contributors")),
    dbc.CardBody(
        [
            "Nyssa Krull - University of Illinois Chicago (Contact: nkrull [at] uic.edu)", html.Br(),
            "Michael Strobel - UC Riverside", html.Br(),
            "Robert A. Shepherd - UC Santa Cruz", html.Br(),
            "Chase M. Clark, PhD - University of Wisconsin", html.Br(),
            "Laura M. Sanchez, PhD - UC Santa Cruz", html.Br(),
            "Mingxun Wang, PhD - UC Riverside", html.Br(),
            "Brian T. Murphy, PhD - University of Illinois Chicago", html.Br(),
            html.Br(),
            html.Br(),
            html.H5("IDBac Citation"),
            html.A("Krull, N. K.; Strobel, M.; Saulog, J.; Zaroubi, L.; Paulo, B. S.; Timba, M.; Braun, D. R.; Mingolelli, G.; Raherisoanjato, J.; Shepherd, R. A.; Scott, A. F.; De Silva, C.; Fergusson, C.; Daniel, Z.; Pokharel, S. K.; Romanowski, S.; Hernandez, A.; Monge-Loría, M.; Dylla, C. E.; Natu, M. M.; Petukhova, V. Z.; Garg, N.; Jensen, P. R.; Blachowicz, A.; Cassilly, C. D.; Guan, L.; Stevens, D. C.; Winter, J. M.; McKinnie, S. M. K.; Adaikpoh, B. I.; Carlson, S.; McCauley, E. P.; Metcalf, W. W.; Bugni, T. S.; Mullowney, M. W.; Pamer, E. G.; Henke, M. T.; Barton, H.; Carter, D. O.; Eustáquio, A. S.; Linington, R. G.; Sanchez, L. M.; Wang, M.; Murphy, B. T. IDBac: An Open-Access Web Platform and Compendium for the Identification of Bacteria by MALDI-TOF Mass Spectrometry. Microbiology October 15, 2025.",
                   href="https://doi.org/10.1101/2025.10.15.682631"),
            html.Br(),
            html.Br(),
            html.H5("Robert Koch Institute (RKI) Database Citation"),
            html.A('Lasch, P., Beyer, W., Bosch, A. et al. A MALDI-ToF mass spectrometry database for identification and classification of highly pathogenic bacteria. Sci Data 12, 187 (2025).',
                   href="https://doi.org/10.1038/s41597-025-04504-z"),
            html.Br(),
            html.Br(),
            html.A('Lasch, P.; Stämmler, M.; Schneider, A. Version 4.2 (20230306) of the MALDI-ToF Mass Spectrometry Database for Identification and Classification of Highly Pathogenic Microorganisms from the Robert Koch-Institute (RKI), 2023.',
                    href='https://doi.org/10.5281/ZENODO.7702374'),
            html.Br(),
            html.Br(),
            html.H5("GNPS Citation"),
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
        STATUS_BANNER,
        dbc.Row([
            dbc.Col(
                className="w-100"
            ),
        ],
        style={"marginTop": 30}),
        dbc.Row([
            dbc.Col([
                dbc.Card(DATABASE_CONTENTS),
                dbc.Card(DB_DISPLAY_DASHBOARD, style={"marginTop": 30}),
            ],
            className="w-100"
            ),
        ], style={"marginTop": 30}),
        dbc.Row([
            dbc.Col(
                [
                    dbc.Card(MIDDLE_DASHBOARD),
                    dbc.Card(ADDITIONAL_DATA, style={"marginTop": 30}),
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

# Callback to update the second pie chart based on the dropdown value
@callback(
    Output('dynamic-taxonomy-pie-chart', 'figure'),
    Input('taxonomy-dropdown', 'value'),
)
def update_dynamic_pie_chart(selected_taxonomy):
    dynamic_summary_df = None
    count_16S = 0
    number_of_database_entries = ""
    percent_16S = 0.0
    database = pd.DataFrame(load_database(None)[0])
    if database is not None:
        dynamic_summary_df = pd.DataFrame(database)

        dynamic_summary_df[selected_taxonomy] = dynamic_summary_df[selected_taxonomy].fillna("No Taxonomy")
        
        # Handle 16S
        is_16S = (dynamic_summary_df[selected_taxonomy] == "No Taxonomy") & (dynamic_summary_df['16S Taxonomy'].notna())

        # Strip the column of whitespace
        dynamic_summary_df[selected_taxonomy] = dynamic_summary_df[selected_taxonomy].str.strip()

        # If genus, only take the first word
        if selected_taxonomy == "genus":
            dynamic_summary_df.loc[is_16S, selected_taxonomy] = dynamic_summary_df.loc[is_16S, "16S Taxonomy"]
            dynamic_summary_df.loc[dynamic_summary_df["genus"]!="No Taxonomy", "genus"] = dynamic_summary_df.loc[dynamic_summary_df["genus"]!="No Taxonomy", "genus"].str.split().str[0]
        else:
            dynamic_summary_df.loc[is_16S, selected_taxonomy] = "User Submitted 16S"

        # Get counts by Genus and Species for px.bar
        dynamic_summary_df = dynamic_summary_df.groupby([selected_taxonomy]).size().reset_index(name="count")

        count_16S = dynamic_summary_df[dynamic_summary_df[selected_taxonomy] == "User Submitted 16S"]["count"].sum()
        percent_16S = (count_16S / dynamic_summary_df["count"].sum()) * 100

        dynamic_summary_df = dynamic_summary_df[dynamic_summary_df[selected_taxonomy] != "User Submitted 16S"]

        dynamic_summary_df = dynamic_summary_df.loc[~ dynamic_summary_df[selected_taxonomy].isna()]


    fig = px.pie(dynamic_summary_df, 
                 values="count", 
                 names=selected_taxonomy,  # Update based on selected taxonomy level
                 title=f"Taxonomy Distribution by {selected_taxonomy}",
                ).update_traces(textposition='inside').update_layout(uniformtext_minsize=12, uniformtext_mode='hide')
    
    fig.update_traces(
        domain=dict(x=[0, 1], y=[0.1, 0.9])  # move pie down slightly
    )

    fig.update_layout(
        uniformtext_minsize=12,
        uniformtext_mode='hide',
        margin=dict(t=60, b=10, l=20, r=20),  # less padding around
        height=600,                            # force larger chart
    )


    print("count_16S", count_16S, flush=True)
    if count_16S > 0:
        fig.add_annotation(
            x=0.5,
            y=-0.1,
            text=f"Number of 16S entries excluded from chart: {int(count_16S):,} ({percent_16S:.2f}%)",
            showarrow=False,
            font=dict(size=14),
            xanchor="center",
            yanchor="bottom",
            xref="paper",
            yref="paper"
        )
    return fig

@callback(
    Output('download-binned-mzml', 'data'),
    Input('download-binned-spectra', 'n_clicks'),
    State('spectra-bin-size', 'value'),
    State('displaytable', 'derived_virtual_data'),
    State('displaytable', 'derived_virtual_selected_rows'),
)
def download_binned(n_clicks, bin_width, table_data, table_selected):
    if n_clicks is None or table_selected is None or len(table_selected) == 0:
        return None
    
    # Get the selected row data
    selected_row = table_data[table_selected[0]]
    database_id = selected_row["database_id"]
    
    return {'content': f"/api/spectrum/mzml-filtered?database_id={database_id}&bin_width={bin_width}",
            'filename': "binned_spectra.mzML"}

@callback(
    Output('download-raw-mzml', 'data'),
    Input('download-raw-spectra', 'n_clicks'),
    State('displaytable', 'derived_virtual_data'),
    State('displaytable', 'derived_virtual_selected_rows'),
)
def download_raw(n_clicks, table_data, table_selected):
    # Check if button was clicked and if a row is selected
    if n_clicks is None or table_selected is None or len(table_selected) == 0:
        return None  # No download action
    
    # Get the selected row data
    selected_row = table_data[table_selected[0]]
    database_id = selected_row["database_id"]

    # Return the download details
    return {
        'content': f"/api/spectrum/mzml-raw?database_id={database_id}",
        'filename': "raw_spectra.mzML"
    }


# Callback to update visibility based on table selection
@callback(
    Output("download-buttons", "style"),
    Output("spectra-bin-size-input", "style"),
    Input("displaytable", "derived_virtual_selected_rows"),
)
def update_button_visibility(selected_rows):
    # Check if there are any selected rows
    if selected_rows:
        return {"display": "block"}, {"display": "flex"}  # Show buttons if rows are selected
    else:
        return {"display": "none"}, {"display": "none"}  # Hide buttons if no rows are selected


def layout(**kwargs):
    return html.Div(children=[
        BODY, 
        ])