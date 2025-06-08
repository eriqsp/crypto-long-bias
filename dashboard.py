import plotly.express as px
from dash import Dash, dcc, html, dash_table
import dash_bootstrap_components as dbc
from hist_analysis import consolidate
import plotly.io as pio
from argparse import ArgumentParser
from datetime import timedelta, datetime


# TODO: make the dashboard more interactive - choose window, cryptos, strategies
# TODO: show parameters configurations on dashboard


def setup_args():
    ref_date = datetime.now() - timedelta(days=1)
    ref_date = ref_date.strftime('%Y-%m-%d')
    args = ArgumentParser()
    args.add_argument('-d', '--date', default=ref_date, type=str, help='Expected format: %Y-%m-%d')
    return args.parse_args()


arguments = setup_args()
crypto_data, dts = consolidate(arguments.date)


def generate_plot(df, crypto):
    fig = px.line(df, x=df.index, y=df.columns, markers=False, title=crypto)
    fig.update_layout(
        xaxis_title=None,
        yaxis_title="%",
        legend_title=None,
        plot_bgcolor="#1e1e1e",
        paper_bgcolor="#1e1e1e",
        margin=dict(t=50, b=50)
    )
    return fig


pio.templates.default = 'plotly_dark'
app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], title='Crypto Long Bias')

app.layout = dbc.Container([
    dbc.Row([
        dbc.Col(html.H2(f"Crypto Long Bias - {dts[0].strftime('%d%b%Y')} to {dts[1].strftime('%d%b%Y')}"), className="text-center text-light my-4")
    ]),
    html.Div(style={'height': '30px'}),
    dbc.Row([
        dbc.Row([
            dbc.Col(
                dcc.Graph(figure=generate_plot(data[0], crypto)),
                width=8
            ),
            dbc.Col(
                dash_table.DataTable(
                    data=data[1].to_dict('records'),
                    columns=[{"name": i, "id": i} for i in data[1].columns],
                    sort_action="native",
                    sort_mode="single",
                    style_table={'overflowX': 'auto'},
                    style_cell={'textAlign': 'center', 'backgroundColor': '#1e1e1e', 'color': 'white'},
                    style_header={'backgroundColor': '#333333', 'fontWeight': 'bold', 'color': 'white'}
                ),
                width=4
            )
        ], className='mb-5') for crypto, data in crypto_data.items()
    ])
], fluid=True, style={'backgroundColor': '#121212', 'minHeight': '100vh', 'paddingBottom': '50px'})


if __name__ == '__main__':
    app.run(debug=True)
