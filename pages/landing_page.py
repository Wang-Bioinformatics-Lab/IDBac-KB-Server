import dash
from dash import html, register_page  #, callback # If you need callbacks, import it here.

import dash_bootstrap_components as dbc


register_page(
    __name__,
    name='IDBac',
    top_nav=True,
    path='/'
)

BODY = dbc.Container(
    [
        dbc.CardBody(
            [
                html.H1("Welcome to the Home Page", className="card-title"),
                html.P(
                    "This is the Home page content.",
                    className="card-text",
                ),
            ]
        )
    ],
    fluid=True,
    className="",
)

def layout(**kwargs):
    return html.Div(children=[BODY])
    