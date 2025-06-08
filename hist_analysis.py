import yfinance as yf
import pandas as pd
from functools import reduce
import json
from datetime import datetime
from dateutil import relativedelta
from scipy.stats import zscore


def consolidate(end_dt: str):
    hyperparams = read_json()
    window = hyperparams['window']
    tickers = hyperparams['cryptos']
    profiles = hyperparams['strat_profiles']

    end_date = datetime.strptime(end_dt, '%Y-%m-%d')
    start_date = end_date - relativedelta.relativedelta(years=window)
    start_dt = start_date.strftime('%Y-%m-%d')
    data = {}
    for ticker in tickers:
        crypto_data = get_crypto_data(ticker, start_dt, end_dt)

        df, summary = pnl_summary(crypto_data, hyperparams, ticker, profiles)
        data[ticker] = [df, summary]

    return data, [start_date, end_date]


def read_json():
    file = open('hyperparams.json')
    return json.load(file)


""" retrieving data """
def get_crypto_data(ticker: str, start_date, end_date):
    df = yf.download(ticker, start=start_date, end=end_date)
    df = df['Close']
    df = df.reset_index()
    return df[['Date', ticker]]


""" compute PnL using various investment strategies """
def pnl_summary(crypto_data, hyperparams, ticker, strategies):
    data = []
    summary_results = []
    for strategy in strategies:
        strat_params = hyperparams[strategy] if strategy in hyperparams else None
        if strat_params is not None:
            for sub_strat, params in strat_params.items():
                df, summary = eval(strategy)(crypto_data, ticker, params)
                new_name = f'{strategy}_{sub_strat}'
                df = df.rename(columns={strategy: new_name})
                summary['strategy'] = new_name
                data.append(df)
                summary_results.append(summary)
        else:
            df, summary = eval(strategy)(crypto_data, ticker, None)
            data.append(df)
            summary_results.append(summary)

    df = reduce(lambda df1, df2:
                pd.merge(left=df1, right=df2, on='Date', how='outer'),
                data)
    df = df.set_index('Date')

    summary_df = pd.DataFrame(summary_results).sort_values(by=['strategy'])

    return df, summary_df


""" investment profiles """


# buy one time then holds
def buy_and_hold(df: pd.DataFrame, crypto: str, hyperparams: dict = None):
    data = df.copy()
    data['cash_flow'] = 0.0
    data.loc[0, 'cash_flow'] = 1.0
    data['cash_flow_acc'] = data['cash_flow'].cumsum()

    return data_summary(data, 'buy_and_hold', crypto)


# buy a certain amount every week
def buy_every_week(df: pd.DataFrame, crypto: str, hyperparams: dict = None):
    data = df.copy()
    total_weeks = round(len(data) / 7)
    data['cash_flow'] = data.apply(lambda row: 1 / total_weeks if row.name % 7 == 0 else 0, axis=1)
    data['cash_flow_acc'] = data['cash_flow'].cumsum()

    return data_summary(data, 'buy_every_week', crypto)


# buys an initial amount and then buy if variation is lower than threshold
def cash_allocation(df: pd.DataFrame, crypto: str, hyperparams: dict = None):
    to_invest = 1.0
    initial_investment = hyperparams['initial_invest']
    threshold = hyperparams['threshold']

    data = df.copy()
    data['cash_flow'] = 0.0
    data.loc[0, 'cash_flow'] = to_invest * initial_investment
    data['variation'] = data[crypto] / data[crypto].shift() - 1

    n_days_to_invest = len(data[data['variation'] <= -threshold])
    invest_each_time = 0
    if n_days_to_invest != 0:
        invest_each_time = (to_invest - data['cash_flow'].sum()) / n_days_to_invest
    else:
        data.loc[0, 'cash_flow'] = to_invest

    data['cash_flow'] = data.apply(lambda row:
                                   invest_each_time * to_invest if not pd.isnull(row['variation']) and
                                   row['variation'] <= -threshold
                                   else row['cash_flow']
                                   , axis=1)
    data['cash_flow_acc'] = data['cash_flow'].cumsum()

    return data_summary(data, 'cash_allocation', crypto)


# buys an initial amount and then buy if z-score is lower than threshold
def z_score(df: pd.DataFrame, crypto: str, hyperparams: dict = None):
    to_invest = 1.0
    initial_investment = hyperparams['initial_invest']
    threshold = hyperparams['threshold']

    data = df.copy()
    data['cash_flow'] = 0.0
    data.loc[0, 'cash_flow'] = to_invest * initial_investment
    data['variation'] = data[crypto] / data[crypto].shift() - 1
    data['zscore_value'] = zscore(data['variation'].fillna(0))

    n_days_to_invest = len(data[data['zscore_value'] <= -threshold])
    invest_each_time = 0
    if n_days_to_invest != 0:
        invest_each_time = (to_invest - data['cash_flow'].sum()) / n_days_to_invest
    else:
        data.loc[0, 'cash_flow'] = to_invest

    data['cash_flow'] = data.apply(lambda row:
                                   invest_each_time * to_invest if not pd.isnull(row['variation']) and
                                   row['zscore_value'] <= -threshold
                                   else row['cash_flow']
                                   , axis=1)
    data['cash_flow_acc'] = data['cash_flow'].cumsum()

    return data_summary(data, 'z_score', crypto)


def data_summary(data: pd.DataFrame, strategy: str, crypto: str):
    data['buy'] = data['cash_flow'] / data[crypto]
    data['position'] = data['buy'].cumsum()
    data['position_value'] = data['position'] * data[crypto]
    data['pnl_pct'] = data['position_value'] / data['position_value'].shift() - 1
    data[strategy] = (data['position_value'] - data['cash_flow_acc']) * 100
    data['drawdown'] = (data['position_value'] - data['position_value'].cummax()) / data['position_value'].cummax()

    vol = data['pnl_pct'].std(ddof=1)
    summary_dict = {'strategy': strategy,
                    'pnl (%)': round(data[strategy].iloc[-1], 2),
                    'vol (%)': round(vol * 100, 2),
                    'sharpe': round(max(data['pnl_pct'].mean() / vol, 0), 2),
                    'MDD (%)': round(data['drawdown'].min() * 100, 2)}

    return data[['Date', strategy]], summary_dict
