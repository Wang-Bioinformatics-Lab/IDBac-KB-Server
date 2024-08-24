import dash
from dash import html, register_page
import dash_bootstrap_components as dbc

register_page(
    __name__,
    name='IDBac',
    top_nav=True,
    path='/'
)

# Define the buttons
BUTTONS = dbc.Row(
    [
        dbc.Col(dbc.Button("Deposit Data", color="primary", className="m-2", href="https://gnps2.org/workflowinput?workflowname=idbacdeposition_workflow"), width="auto"),
        dbc.Col(dbc.Button("Analyze Data", color="primary", className="m-2", href="https://gnps2.org/workflowinput?workflowname=idbac_analysis_workflow"), width="auto"),
        dbc.Col(dbc.Button("Interactive Interface", color="primary", className="m-2", href="https://analysis.idbac.org/"), width="auto"),
        dbc.Col(dbc.Button("Documentation", color="primary", className="m-2", href="https://wang-bioinformatics-lab.github.io/GNPS2_Documentation/idbacdepositions/"), width="auto"),
    ],
    justify="center",
    className="my-4"
)

# Define the body with buttons and some content
BODY = dbc.Container(
    [
        dbc.CardBody(
            [
                BUTTONS
            ]
        )
    ],
    fluid=True,
    className="content",
)

def layout(**kwargs):
    return html.Div(
        children=[
            html.Div(className="header-image"),
            html.Div(
                children=[
                    BODY
                ],
                className="content"
            )
        ],
        className="page-container"
    )
