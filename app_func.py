import os
import json
import requests
from tqdm import tqdm
import numpy as np
import pandas as pd
import streamlit as st
from datetime import datetime
import plotly.graph_objects as go

def get_weight():
    weight = pd.read_excel(
        'https://www.stat.go.jp/data/cpi/2020/kaisetsu/zuhyou/4-1.xlsx', sheet_name='品目情報一覧', skiprows=[0,1,3,4],
        usecols=[0,1,2,3,4,5,7,8,9,10,12]
    )
    weight.columns = [
    '大分類', '中分類1', '中分類2', '小分類1', '小分類2', '品目', '類符号', '品目符号', 
    '含類総連番', '全国', '東京都区部',
    ]
    weight['品目符号'] = weight['品目符号'].fillna(weight['類符号']).map(int).map("{:04d}".format)
    weight[['大分類', '中分類1', '中分類2', '小分類1', '小分類2', '品目']] = weight[['大分類', '中分類1', '中分類2', '小分類1', '小分類2', '品目']].ffill(axis=1)
    weight = weight.iloc[:728]

    weight['@name'] = weight.apply(lambda x: f"{x['品目符号']} {x['品目']}", axis=1)
    weight = weight.set_index('@name')[['類符号', '全国', '東京都区部']]
    return weight

def get_cpi(area='全国', start_month="2000-01", end_month=None, verbose=True):
    endpoint = 'http://api.e-stat.go.jp/rest/3.0/app/json/getStatsData'
    params = {
    'cdTab': '1', 'appId': os.environ['ESTAT_API_ID'],
    'lang': 'J', 'statsDataId': '0003427113',
    'metaGetFlg': 'Y', 'cntGetFlg': 'N',
    'explanationGetFlg': 'Y', 'annotationGetFlg': 'Y',
    'sectionHeaderFlg': '1', 'replaceSpChars': '0',
    'cdArea': '13A01' if area == '東京都区部' else '00000'
    }
    if end_month is None:
        end_month = datetime.now()
    months = list(pd.date_range(start_month, end_month, freq='ME'))

    cpis = []
    for start, end in tqdm(zip(months[::10], months[9::10] + [pd.Timestamp(end_month)]), total=len(months[::10]), disable=not verbose):
        params['cdTime'] = ','.join([f"{month:%Y00%m%m}" for month in pd.date_range(f'{start:%Y-%m-01}', f'{end:%Y-%m-01}', freq='MS')])
        res = requests.get(endpoint, params=params)
        res = json.loads(res.text)
        assert res['GET_STATS_DATA']['RESULT']['ERROR_MSG'].startswith('正常に終了しました')
        if res['GET_STATS_DATA']['RESULT']['STATUS'] != 0:
            continue
        c = pd.DataFrame(res['GET_STATS_DATA']['STATISTICAL_DATA']['CLASS_INF']['CLASS_OBJ'][1]['CLASS']).set_index('@code')
        
        cpi = pd.DataFrame(res['GET_STATS_DATA']['STATISTICAL_DATA']['DATA_INF']['VALUE'])
        cpi[c.columns] = c.reindex(cpi['@cat01']).values
        cpi = cpi[~cpi['@time'].str.endswith('00')].copy()
        cpi['month'] = pd.to_datetime(cpi['@time'].map(lambda x: f"{x[:4]}-{x[-2:]}"))
        
        cpi['@parentCode'] = cpi['@parentCode'].fillna('0')
        cpi.loc[cpi['@name']=='0001 総合', '@level'] = '0'
        cpi.loc[cpi['@name']=='0001 総合', '@parentCode'] = np.nan
        cpi = cpi.set_index(['@parentCode', '@level', '@name', 'month'])[['$']].map(float)
        cpis.append(cpi)
    cpis = pd.concat(cpis).sort_index()
    return cpis

def render_item_option_and_extract_data(weight, cpi, area):
    levels = []
    i, option = 1, ('0001 総合', )
    while True:
        level = st.selectbox(
            f"項目{i}",
            option,
            index=0 if i==1 else None,
            key=f"項目{i}_{area}"
        )
        if level is None:
            break
        levels.append(level)

        parentCode = levels[-1].split()[0]
        if len(levels) == 1:
            parentCode = '0'

        main_weight = weight.xs(levels[-1])[area]
        main = cpi.xs(levels[-1], level='@name').reset_index().set_index('month')['$']
        component = cpi.xs(parentCode)['$'].unstack('month').reset_index('@level', drop=True)
        component = component[component.index.isin(weight.index)].T
        w = weight[weight.index.isin(component.columns)][area].to_dict()
        assert sum(w.values()) == main_weight
        weight_ratio = {k: v / main_weight for k, v in w.items()}
        df = pd.concat([main.to_frame(levels[-1]), component], axis=1).sort_index()

        option = weight[weight.index.isin(component.columns)].dropna(subset='類符号').index
        if len(option) == 0:
            break
        i += 1
    return levels, df, weight_ratio

def render_display_setting(base_month_option, base_month_default, area):
    item = st.selectbox(
        "項目",
        ('指数(基準月比%)', '前年同月比%'),
        index=1,
        key=f"item_selectbox_{area}"
    )
    base_month = None
    if item == '指数(基準月比%)':
        index = base_month_option.index(base_month_default)
        base_month = st.selectbox(
            "基準月",
            base_month_option,
            index=index,
            key=f"base_month_selectbox_{area}"
        )
        base_month += '-01'
    return item, base_month

def render_graph(df, weight_ratio, content, item):
    if len(df) == 0:
        st.write('基準月のデータがありません。')
        return None
    dat = []
    for i, column in enumerate(df.columns):
        name = column.split()[1]
        try:
            name = f"{column.split()[1]}({weight_ratio[column]:.2%})"
        except:
            main_i = i
        dat += [go.Scatter(
            x=df.index, y=df[column] * 100, name=name,
            customdata=df.apply(lambda x: f"{x.name:%Y-%m} {x[column]:.2%}", axis=1),
            hovertemplate="%{customdata}"
        )]
    fig = go.Figure(data=dat)

    fig.update_traces(line={'width':1})
    fig.update_traces(selector=main_i, line={'color': 'black', 'width':3})
    fig.update_layout(
        legend=dict(
            x=1,y=-0.1,xanchor='right',yanchor='top'
        ),
        width=700,
        height=700
    )
    st.subheader(
        f'{content} の価格指数({item})',
        help="'Autoscale'ボタンでズームアウト(2000年以降を表示)"
    )
    st.write("()内の数字はウェイト")
    fig.update_layout(
        xaxis_title='',
        yaxis_title=item
    )
    latest = df.index[-1]
    m = df.loc[latest-pd.Timedelta(weeks=53): latest].min().min()
    M = df.loc[latest-pd.Timedelta(weeks=53): latest].max().max()
    m *= 110 if m < 0 else 90
    M *= 90 if M < 0 else 110
    fig.update_layout(
        xaxis=dict(range=[latest-pd.Timedelta(weeks=53), latest]),
        yaxis=dict(range=[m, M])
    )
    st.plotly_chart(fig)

