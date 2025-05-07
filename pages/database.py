# -*- coding: utf-8 -*-
from dash import dcc
from dash import html
from dash import dash_table
from dash import callback
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import plotly
import plotly.express as px
import os
import logging
import traceback

import pandas as pd

from dash import html, register_page  #, callback # If you need callbacks, import it here.


register_page(
    __name__,
    name='IDBac Database',
    top_nav=True,
    path='/database'
)

HOVERTILES = dbc.Card(
    [
        dbc.CardHeader(html.H5("Culture Collections")),
        dbc.CardBody(
            [
                html.H3(
                    id="database-contents-text",
                    style={"color": "#d88000", "marginBottom": "20px"},  # You can change the color here
                    className="text-center"
                ),
                dbc.Row(id="tiles-container", className="g-2"),
            ]
        )
    ]
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
                    hidden_columns=[],
                    row_selectable='single',
                    page_size=10,
                    sort_action='native',
                    filter_action='native',
                    export_format='xlsx',
                    export_headers='display',
                    style_header={
                        'whiteSpace': 'normal',
                        },
                    style_table={
                        'width': '100%',
                        'overflowX': 'auto',
                    },
                    )
                    
            ],
            id="displaycontent"),
            html.Br(),
            html.Br(),
            html.Div(id="update-summary")

        ]
    )
]

DB_DISPLAY_DASHBOARD = [
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
                    html.H5("Taxonomic Tree"),
                    html.Img(src="/download_tree_png", style={"width": "75%", 'margin':'auto', 'display':'flex'}),
                ]
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
    dbc.CardHeader(html.H5("Database Contents")),
    dbc.CardBody(
        [
            # Dropdown for the  pie chart
            dcc.Dropdown(
                id='taxonomy-dropdown',
                options=db_content_dropdown_options,
                value='genus',  # default value
                clearable=False
            ),
            
            # pie chart (dynamic, controlled by dropdown)
            dcc.Graph(id="dynamic-taxonomy-pie-chart"),   # DISABLED FOR DEBUG TODO REMOVE
            # Horizontal line
            html.Hr() if tax_tree else None,
            # Taxonomic tree
            tax_tree,
            # Download buttons
            TREE_DOWNLOAD_BUTTONS if tax_tree else None
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
        dbc.Row([
            dbc.Col(
                dbc.Card(HOVERTILES),
                className="w-100"
            ),
        ],
        style={"marginTop": 30}),
        dbc.Row([
            dbc.Col(
                dbc.Card(DB_DISPLAY_DASHBOARD),
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
                    dbc.Card(DATABASE_CONTENTS),
                    dbc.Card(CONTRIBUTORS_DASHBOARD, style={"marginTop": 30}),
                ],
                className="w-50"
            ),
        ], style={"marginTop": 30}),
    ],
    fluid=True,
    className="",
)

# Load the database once and send to dcc.store on page load
# @callback(
#     Output('data-store', 'data'),
#     Input('url', 'pathname'),
# )
# def load_database(pathname):
#     if not os.path.exists("database/summary.tsv"):
#         return None
    
#     try:
#         df = pd.read_csv("database/summary.tsv", sep="\t")
#         return df.to_dict(orient='records')
#     except Exception as e:
#         logging.error("Error loading database", e)
#         return None

# Callback to update the hover tiles based on DB contents
@callback(
    Output('tiles-container', 'children'),
    Input('data-store', 'data'),
)
def update_hover_tiles(data):
    try:
        df = pd.DataFrame(data)
        df = df.loc[df['Culture Collection'].notna(), :]
        df = df.loc[df['genus'].notna(), :]
        culture_collections = df["Culture Collection"].unique()
        tiles = []
        for collection in culture_collections:
            unique_genera = df.loc[df['Culture Collection'] == collection, 'genus'].unique()
            if len(unique_genera) == 0:
                continue
            num_entries = len(df[df['Culture Collection'] == collection])
            under_text = ""
            if num_entries == 1:
                under_text = "1 entry"
            elif num_entries > 1:
                under_text = f"{num_entries:,} entries"
            tooltip_text = ', '.join(unique_genera)
            tiles.append(
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardBody(
                                [
                                    html.H5(collection),
                                    html.P(under_text),
                                    dbc.Tooltip(tooltip_text, target=f"tooltip-{collection}")
                                ]
                            )
                        ],
                        id=f"tooltip-{collection}"
                    ),
                    width=4  # Adjust the width to control the number of tiles per row
                )
            )
        return tiles
    except Exception as e:
        # Show stack trace
        logging.error("Error updating hover tiles", e)
        # Full trace
        traceback.print_exc()
        return []
    

# Callback to update the second pie chart based on the dropdown value
@callback(
    Output('dynamic-taxonomy-pie-chart', 'figure'),
    Input('taxonomy-dropdown', 'value'),
    Input('data-store', 'data'),
)
def update_dynamic_pie_chart(selected_taxonomy, data):
    dynamic_summary_df = None
    count_16S = 0
    number_of_database_entries = ""
    if data is not None:
        dynamic_summary_df = pd.DataFrame(data)

        dynamic_summary_df[selected_taxonomy] = dynamic_summary_df[selected_taxonomy].fillna("No Taxonomy")
        
        # Handle 16S
        is_16S = (dynamic_summary_df[selected_taxonomy] == "No Taxonomy") & (dynamic_summary_df['16S Taxonomy'].notna())

        # Strip the column of whitespace
        dynamic_summary_df[selected_taxonomy] = dynamic_summary_df[selected_taxonomy].str.strip()

        # Print full dataframe for DEBUG
        # with pd.option_context('display.max_rows', None, 'display.max_columns', None):  
        #     print(dynamic_summary_df, flush=True)

        # If genus, only take the first word
        if selected_taxonomy == "genus":
            dynamic_summary_df.loc[is_16S, selected_taxonomy] = dynamic_summary_df.loc[is_16S, "16S Taxonomy"]
            dynamic_summary_df.loc[dynamic_summary_df["genus"]!="No Taxonomy", "genus"] = dynamic_summary_df.loc[dynamic_summary_df["genus"]!="No Taxonomy", "genus"].str.split().str[0]
        else:
            dynamic_summary_df.loc[is_16S, selected_taxonomy] = "User Submitted 16S"

        # Print full dataframe for DEBUG
        # with pd.option_context('display.max_rows', None, 'display.max_columns', None):  
        #     print(dynamic_summary_df[selected_taxonomy].value_counts(), flush=True)

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
        dcc.Store(id='data-store', storage_type='memory',),
        BODY, 
        ])