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

import pandas as pd

from dash import html, register_page  #, callback # If you need callbacks, import it here.


register_page(
    __name__,
    name='IDBac Database',
    top_nav=True,
    path='/database'
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
            dcc.Loading(
                id="output",
                children=[html.Div([html.Div(id="loading-output-23")])],
                type="default",
            ),
        ]
    )
]

db_content_dropdown_options = [
    # {'label': 'Kingdom', 'value': 'Kingdom'},
    {'label': 'Phylum', 'value': 'Phylum'},
    {'label': 'Class', 'value': 'Class'},
    {'label': 'Order', 'value': 'Order'},
    {'label': 'Family', 'value': 'Family'},
    {'label': 'Genus', 'value': 'Genus'},
    {'label': 'Species', 'value': 'Species'}
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
                value='Genus',  # default value
                clearable=False
            ),
            
            # pie chart (dynamic, controlled by dropdown)
            dcc.Graph(id="dynamic-taxonomy-pie-chart"),
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


# Callback to update the second pie chart based on the dropdown value
@callback(
    Output('dynamic-taxonomy-pie-chart', 'figure'),
    Input('taxonomy-dropdown', 'value')
)
def update_dynamic_pie_chart(selected_taxonomy):
    dynamic_summary_df = None
    number_of_database_entries = ""
    if os.path.exists("database/summary.tsv"):
        dynamic_summary_df = pd.read_csv("database/summary.tsv", sep="\t")
        number_of_database_entries = str(len(dynamic_summary_df))
        dynamic_summary_df["FullTaxonomy"] = dynamic_summary_df["FullTaxonomy"].fillna("No Taxonomy")
        not_16S = (~ dynamic_summary_df["FullTaxonomy"].str.contains("User Submitted 16S")) & (~ dynamic_summary_df["FullTaxonomy"].str.contains("No Taxonomy"))
        is_16S  = dynamic_summary_df["FullTaxonomy"].str.contains("User Submitted 16S")

        dynamic_summary_df.assign(Kingdom="", Phylum="", Class="", Order="", Family="", Genus="", Species="")
        taxonomy_split = dynamic_summary_df.loc[not_16S, "FullTaxonomy"].str.split(";", n=6, expand=True)
        taxonomy_split.columns = ["Kingdom", "Phylum", "Class", "Order", "Family", "Genus", "Species"]
        dynamic_summary_df.loc[not_16S, ["Kingdom", "Phylum", "Class", "Order", "Family", "Genus", "Species"]] = taxonomy_split
        
        # Handle 16S
        dynamic_summary_df.loc[is_16S, ["Kingdom", "Phylum", "Class", "Order", "Family", "Species"]] = "User Submitted 16S"
        dynamic_summary_df.loc[is_16S, "Genus"] = dynamic_summary_df.loc[is_16S, "FullTaxonomy"].str.split().str[0]

        # Get counts by Genus and Species for px.bar
        # dynamic_summary_df = dynamic_summary_df.groupby(["Genus", "Species"]).size().reset_index(name="count")
        dynamic_summary_df = dynamic_summary_df.groupby([selected_taxonomy]).size().reset_index(name="count")
        # Strip the column of whitespace
        dynamic_summary_df[selected_taxonomy] = dynamic_summary_df[selected_taxonomy].str.strip()

        if selected_taxonomy == "Genus":
            dynamic_summary_df["Genus"] = dynamic_summary_df["Genus"].str.split().str[0]

        # Print full dataframe for debugging
        with pd.option_context('display.max_rows', None, 'display.max_columns', None):  
            print(dynamic_summary_df[selected_taxonomy].value_counts(), flush=True)

        count_16S = dynamic_summary_df[dynamic_summary_df[selected_taxonomy] == "User Submitted 16S"]["count"].sum()
        percent_16S = (count_16S / dynamic_summary_df["count"].sum()) * 100

        dynamic_summary_df = dynamic_summary_df[dynamic_summary_df[selected_taxonomy] != "User Submitted 16S"]

        dynamic_summary_df = dynamic_summary_df.loc[~ dynamic_summary_df[selected_taxonomy].isna()]

    fig = px.pie(dynamic_summary_df, 
                 values="count", 
                 names=selected_taxonomy,  # Update based on selected taxonomy level
                 title=f"Taxonomy Distribution by {selected_taxonomy}",
                ).update_traces(textposition='inside').update_layout(uniformtext_minsize=12, uniformtext_mode='hide')
    
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

def layout(**kwargs):
    return html.Div(children=[BODY])