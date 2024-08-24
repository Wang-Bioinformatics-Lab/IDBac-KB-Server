# -*- coding: utf-8 -*-
from dash import dcc
from dash import html
from dash import dash_table
import dash_bootstrap_components as dbc
import plotly.express as px

import os

import pandas as pd

from dash import html, register_page  #, callback # If you need callbacks, import it here.


register_page(
    __name__,
    name='Home',
    top_nav=True,
    path='/'
)

summary_df = None
number_of_database_entries = ""
if os.path.exists("database/summary.tsv"):
    summary_df = pd.read_csv("database/summary.tsv", sep="\t")
    number_of_database_entries = str(len(summary_df))
    summary_df["FullTaxonomy"] = summary_df["FullTaxonomy"].fillna("No Taxonomy")
    not_16S = ~ summary_df["FullTaxonomy"].str.contains("User Submitted 16S") & ~ summary_df["FullTaxonomy"].str.contains("No Taxonomy")
    is_16S  = summary_df["FullTaxonomy"].str.contains("User Submitted 16S")

    summary_df.assign(Genus="", Species="")
    summary_df.loc[not_16S, "Genus"] = summary_df.loc[not_16S, "FullTaxonomy"].str.split(";").str[-2]
    summary_df.loc[not_16S, "Species"] = summary_df.loc[not_16S, "FullTaxonomy"].str.split(";").str[-1]
    summary_df.loc[is_16S, "Genus"] = summary_df.loc[is_16S, "FullTaxonomy"].str.split().str[0]
    summary_df.loc[is_16S, "Species"] = "User Submitted 16S"

    # Get counts by Genus and Species for px.bar
    # summary_df = summary_df.groupby(["Genus", "Species"]).size().reset_index(name="count")
    summary_df = summary_df.groupby(["Genus"]).size().reset_index(name="count")
    # Strip the Genus column of whitespace
    summary_df["Genus"] = summary_df["Genus"].str.strip()

NAVBAR = dbc.Navbar(
    children=[
        dbc.NavbarBrand(
            html.Img(src="assets/GNPS2xIDBac.png", width="240px"),
            href="https://gnps2.org"
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

# Count of Spectra, Bar Chart of Taxonomy
DATABASE_CONTENTS = [
    dbc.CardHeader(html.H5("Database Contents")),
    dbc.CardBody(
        [
            html.H5(f"Total number of spectra: {number_of_database_entries}"),
            html.H5(f"Number of unique genera: {len(summary_df)}"),
            dcc.Graph(id="taxonomy-pie-chart",
                      figure=px.pie(summary_df, 
                                    values="count", 
                                    names="Genus",
                                    title="Taxonomy Distribution",
                                ).update_traces(textposition='inside').update_layout(uniformtext_minsize=12, uniformtext_mode='hide')

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
                    dbc.Card(DATABASE_CONTENTS),
                ],
                className="w-50"
            ),
        ], style={"marginTop": 30}),
        dbc.Row([
            dbc.Col(
                [
                    dbc.Card(ADDITIONAL_DATA),
                ],
                className="w-50",
            ),
            dbc.Col(
                [
                    dbc.Card(CONTRIBUTORS_DASHBOARD)
                ],
                className="w-50",
            ),
        ], style={"marginTop": 30}),
    ],
    fluid=True,
    className="",
)

def layout(**kwargs):
    return html.Div(children=[BODY], id="database-page", className="database-page", style={"width": "100%"})