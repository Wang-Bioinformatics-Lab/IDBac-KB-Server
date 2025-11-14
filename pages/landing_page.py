import dash
from dash import html, register_page
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
from dash import callback
import json

register_page(
    __name__,
    name='IDBac',
    top_nav=True,
    path='/'
)

TAGLINE = "A place to ID bacteria, organize strain collections & ask research questions."

text_under_button1 = "Learn more about the IDBac platform and access step-by-step video tutorials."
text_under_button2 = "Explore the size and diversity of the IDBac Knowledgebase (IDBac-KB)."

DATABASE_CONTENTS = dbc.Container(html.H3(
    id="database-contents-text",
    style={"color": "#d88000"},  # You can change the color here
    className="text-center"
    ),
    fluid=True,
    className="database-contents",
    style={"margin-top": "5px"}
)

@callback(
    Output("database-contents-text", "children"),
    Input("database-contents-text", "children"),
    prevent_initial_call=False
)
def update_database_contents(_,):
    num_entries = 0
    num_genera = 0
    stats_path = "database/summary_statistics.json"

    try:
        stats = json.load(open(stats_path, "r", encoding='utf-8'))
        num_entries = stats["num_entries"]
        num_genera = stats["num_genera"]
        # TODO: Make pie chart statistics a part of summary stats
    except Exception as _:
        return ""
    
    return f"Collective Contributions: {num_entries:,} Entries & {num_genera:,} Genera"


BUTTONS = dbc.Col(
    dbc.Row(
        [
            dbc.Col(
                [
                    dbc.Button(
                        "IDBac Introduction & Video Tutorials", color="primary", className="m-2 button-fixed button-blue", href="https://sites.google.com/uic.edu/idbac-documentation/"
                    ), 
                    html.P(text_under_button1, className="grey-box"),
                ],
                xs=12, sm=12, md=4, lg=4, xl=4  # Full width on mobile, one row on desktop
            ),
            dbc.Col(
                [
                    dbc.Button(
                        "Visit the IDBac Knowledgebase", color="primary", className="m-2 button-fixed button-blue", href="/knowledgebase"
                    ), 
                    html.P(text_under_button2, className="grey-box"),
                ],
                xs=12, sm=12, md=4, lg=4, xl=4
            ),
        ],
        justify="center",
        className="button-container"
    ),
    width='80%'
)

# Define the Call-To-Action (CTA) section
CTA = dbc.Col(
        dbc.Row(
        [
            dbc.Col(
                [
                    # html.P(
                    #     [
                    #         html.A("Before signing up, get a token here.", href="https://wang-bioinformatics-lab.github.io/GNPS2_Documentation/idbac-request-an-account/", className="link")
                    #     ],
                    # ),
                    # dbc.Button(
                    #     "Sign Up Now", color="primary", className="m-2 button-fixed button-blue", href="https://gnps2.org/user/signup", style={"padding-left": "30px", 
                    #                                                                                                                            "padding-right": "30px"}
                    # ),
                    dbc.Button(
                        "Sign Up Now", color="primary", className="m-2 button-fixed button-blue", href="https://forms.gle/Zm6ZkevcKQ3mRiBt9", style={"padding-left": "30px", 
                                                                                                                                               "padding-right": "30px"}
                    ),
                ],
                xs=12, sm=12, md=12, lg=12, xl=12,  # Always take full width
            ),
        ],
        justify="center",
        className="cta-container",
    ), 
    width='100%',
)

# Define the body with buttons and some content
BODY = dbc.Container(
    [
        dbc.CardBody(
            [
                BUTTONS,
            ]
        ),
        dbc.CardBody(
            [
                CTA,
            ]
        ),
    ],
    fluid=True,
    className="body",
)

def layout(**kwargs):
    return html.Div(
        children=[
            html.Div(className="header-image"),
            html.H3(TAGLINE, className="tagline text-center"),
            html.Hr(style={"width": "60%", "margin": "auto"}),
            DATABASE_CONTENTS,
            html.Div(className="subheader-image"),
            html.Br(),
            html.Hr(style={"width": "60%", "margin": "auto"}),
            html.Div(
                children=[
                    BODY
                ], className="page-content"
            )
        ],
        className="page-container"
    )
