import dash
from dash import html, register_page
import dash_bootstrap_components as dbc

BUTTON_COL_WIDTH=2

register_page(
    __name__,
    name='IDBac',
    top_nav=True,
    path='/'
)

TAGLINE = "A platform for the deposition, analysis, and visualization of bacterial natural product biosynthetic gene clusters"

text_under_button1 = ""
text_under_button2 = ""
text_under_button3 = ""
text_under_button4 = ""
text_under_button5 = ""

BUTTONS = dbc.Col(
    dbc.Row(
        [
            dbc.Col(
                [
                    dbc.Button(
                        "View Database", color="primary", className="m-2 button-fixed", href="/database"
                        ), 
                    html.P(text_under_button1),
                ],
                width=BUTTON_COL_WIDTH),
            dbc.Col(
                [
                    dbc.Button(
                        "Deposit Data", color="primary", className="m-2 button-fixed", href="https://gnps2.org/workflowinput?workflowname=idbacdeposition_workflow"
                        ), 
                    html.P(text_under_button2),
                ],
                    width=BUTTON_COL_WIDTH),
            dbc.Col(
                [
                    dbc.Button(
                        "Analyze Data", color="primary", className="m-2 button-fixed", href="https://gnps2.org/workflowinput?workflowname=idbac_analysis_workflow"
                    ), 
                    html.P(text_under_button3),
                ],
                width=BUTTON_COL_WIDTH),
            dbc.Col(
                [
                    dbc.Button(
                        "Interactive Interface", color="primary", className="m-2 button-fixed", href="https://analysis.idbac.org/"
                    ),
                    html.P(text_under_button4),
                ],
                width=BUTTON_COL_WIDTH),
            dbc.Col(
                [
                    dbc.Button(
                        "Documentation", color="primary", className="m-2 button-fixed", href="https://wang-bioinformatics-lab.github.io/GNPS2_Documentation/idbacdepositions/"
                    ),
                    html.P(text_under_button5),
                ],
                width=BUTTON_COL_WIDTH),
        ],
        justify="center",
        className="my-4"
    ),
    width='75%'
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
                    html.H3(TAGLINE, className="tagline text-center"),
                    BODY
                ],
                className="content"
            )
        ],
        className="page-container"
    )
