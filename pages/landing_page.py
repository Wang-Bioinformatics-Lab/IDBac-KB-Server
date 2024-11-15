import dash
from dash import html, register_page
import dash_bootstrap_components as dbc

register_page(
    __name__,
    name='IDBac',
    top_nav=True,
    path='/'
)

TAGLINE = "A place to ID bacteria, organize strain collections & ask reasearch questions."

text_under_button1 = "Upload and analyze your MALDI-TOF MS data: protein dendrograms, metabolite association networks, or heatmaps."
text_under_button2 = "Deposit spectra of genetically verified strains to the public IDBac database."
text_under_button3 = "Explore number and type of strains in the database and their associated metadata."
text_under_button4 = "Interested in IDBac but not ready to commit? Explore the IDBac platform using a sample dataset."
text_under_button5 = "Click here to access instructions on how to use IDBac."

BUTTONS = dbc.Col(
    dbc.Row(
        [
            dbc.Col(
                [
                    dbc.Button(
                        "Analyze Data", color="primary", className="m-2 button-fixed button-blue", href="https://gnps2.org/workflowinput?workflowname=idbac_analysis_workflow"
                    ), 
                    html.P(text_under_button1, className="grey-box"),
                ],
                xs=12, sm=12, md=6, lg=2, xl=2  # Full width on mobile, one row on desktop
            ),
            dbc.Col(
                [
                    dbc.Button(
                        "Deposit Data", color="primary", className="m-2 button-fixed button-blue", href="https://gnps2.org/workflowinput?workflowname=idbacdeposition_workflow"
                    ), 
                    html.P(text_under_button2, className="grey-box"),
                ],
                xs=12, sm=12, md=6, lg=2, xl=2
            ),
            dbc.Col(
                [
                    dbc.Button(
                        "View Database", color="primary", className="m-2 button-fixed button-grey", href="/database"
                    ), 
                    html.P(text_under_button3, className="grey-box"),
                ],
                xs=12, sm=12, md=6, lg=2, xl=2
            ),
            dbc.Col(
                [
                    dbc.Button(
                        "Interactive Interface", color="primary", className="m-2 button-fixed button-grey", href="https://analysis.idbac.org/"
                    ),
                    html.P(text_under_button4, className="grey-box"),
                ],
                xs=12, sm=12, md=6, lg=2, xl=2
            ),
            dbc.Col(
                [
                    dbc.Button(
                        "Documentation", color="primary", className="m-2 button-fixed button-grey", href="https://wang-bioinformatics-lab.github.io/GNPS2_Documentation/idbacdepositions/"
                    ),
                    html.P(text_under_button5, className="grey-box"),
                ],
                xs=12, sm=12, md=6, lg=2, xl=2
            ),
        ],
        justify="center",
        className="button-container"
    ),
    width='100%'
)

# Define the Call-To-Action (CTA) section
CTA = dbc.Col(
        dbc.Row(
        [
            dbc.Col(
                [
                    dbc.Button(
                        "Sign Up Now", color="primary", className="m-2 button-fixed button-blue", href="https://gnps2.org/user/signup", style={"padding-left": "30px", 
                                                                                                                                               "padding-right": "30px"}
                    ),
                    # Some hyperlinked text href https://wang-bioinformatics-lab.github.io/GNPS2_Documentation/accounts/#account-creation
                    html.P(
                        [
                            html.A("Need a sign up token?", href="https://wang-bioinformatics-lab.github.io/GNPS2_Documentation/accounts/#account-creation", className="link")
                        ],
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
            html.Div(className="subheader-image"),
            html.Div(
                children=[
                    html.Br(),
                    html.Hr(),
                    BODY
                ], className="page-content"
            )
        ],
        className="page-container"
    )
