import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from app_func import get_weight, get_cpi, render_item_option_and_extract_data, render_display_setting, render_graph

st.set_page_config(page_title="CPI Watch", page_icon=":label:")
st.title('CPI Watch')

@st.cache_resource
def initialize():
    data = {}
    data['weight'] = get_weight()

    data['cpi'] = {
        '全国': get_cpi(area='全国', start_month="2000-01"),
        '東京都区部': get_cpi(area='東京都区部', start_month="2000-01"),
    }
    data['cpi']['全国_最新月'] = data['cpi']['全国'].index.get_level_values('month').max()
    data['cpi']['東京都区部_最新月'] = data['cpi']['東京都区部'].index.get_level_values('month').max()
    return data

data = initialize()
jp, tokyo = st.tabs(["全国", "東京都区部"])
options = [('0001 総合', )]

with jp:
    with st.container(border=True):
        st.write("## 項目")
        levels, df, weight_ratio = render_item_option_and_extract_data(
            weight=data['weight'][['類符号', '全国']],
            cpi=data['cpi']['全国'],
            area='全国'
            )
        st.write('## 表示')
        item, base_month = render_display_setting(
            base_month_option=list(map("{:%Y-%m}".format, data['cpi']['全国'].index.get_level_values('month').unique())),
            base_month_default='2020-01', area='全国'
        )

        if item == '指数(基準月比%)':
            df = (df - df.loc[base_month]) / df.loc[base_month]
        else:
            df = (df - df.shift(12)) / df.shift(12)
        df = df.dropna()
    
    with st.container(border=True):
        fig = render_graph(df, weight_ratio)
        st.header(
            f'{levels[-1].split()[1]} の価格指数の推移',
            help="'Autoscale'ボタンでズームアウト(2000年以降を表示)"
        )
        st.write("()内の数字はウェイト")
        fig.update_layout(
            xaxis=dict(range=['2019-12-01', df.index[-1]]),
            xaxis_title='月',
            yaxis_title=item
        )
        st.plotly_chart(fig)
with tokyo:
    with st.container(border=True):
        st.write("## 項目")
        levels, df, weight_ratio = render_item_option_and_extract_data(
            weight=data['weight'][['類符号', '東京都区部']],
            cpi=data['cpi']['東京都区部'],
            area='東京都区部'
        )

        st.write('## 表示')
        item, base_month = render_display_setting(
            base_month_option=list(map("{:%Y-%m}".format, data['cpi']['東京都区部'].index.get_level_values('month').unique())),
            base_month_default='2020-01', area='東京都区部')

        if item == '指数(基準月比%)':
            df = (df - df.loc[base_month]) / df.loc[base_month]
        else:
            df = (df - df.shift(12)) / df.shift(12)
        df = df.dropna()
    
    with st.container(border=True):
        fig = render_graph(df, weight_ratio)
        st.title(
            f'{levels[-1].split()[1]} の価格指数の推移',
            help="'Autoscale'ボタンでズームアウト(2000年以降を表示)"
        )
        st.write("()内の数字はウェイト")
        fig.update_layout(
            xaxis=dict(range=['2019-12-01', df.index[-1]]),
            xaxis_title='月',
            yaxis_title=item
        )
        st.plotly_chart(fig)
