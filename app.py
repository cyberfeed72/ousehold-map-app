import streamlit as st
import pandas as pd
import io
import chardet
import os
from streamlit_folium import st_folium
from geopy.distance import geodesic
import folium

# Cloud or local 判定
IS_CLOUD = os.environ.get("STREAMLIT_SERVER_HEADLESS") == "1"

# 初期データ読込み
if 'df' not in st.session_state:
    df1 = pd.read_csv('加古川市住所データ.csv', encoding='utf-8')
    df2 = pd.read_csv('姫路市全域住所データ - 2024331.csv', encoding='utf-8')
    df = pd.concat([df1, df2], ignore_index=True)
    df['世帯数'] = pd.to_numeric(df['世帯数'].astype(str).str.replace(',', '', regex=False), errors='coerce').fillna(0).astype(int)
    st.session_state.df = df

# CSVアップロード
st.sidebar.header("住所データ管理")
uploaded_file = st.sidebar.file_uploader("CSVまたはExcelファイルをアップロードしてください", type=["csv", "xlsx"])

if uploaded_file:
    if uploaded_file.name.endswith('.csv'):
        rawdata = uploaded_file.read()
        encoding_guess = chardet.detect(rawdata)['encoding'] or 'shift-jis'
        new_df = pd.read_csv(io.StringIO(rawdata.decode(encoding_guess)), encoding=encoding_guess)
    elif uploaded_file.name.endswith('.xlsx'):
        new_df = pd.read_excel(uploaded_file)

    new_df['世帯数'] = pd.to_numeric(new_df['世帯数'].astype(str).str.replace(',', '', regex=False), errors='coerce').fillna(0).astype(int)
    st.session_state.df = pd.concat([st.session_state.df, new_df], ignore_index=True).drop_duplicates().reset_index(drop=True)
    st.sidebar.success('データ追加完了！')

# データ表示
with st.sidebar.expander("CSVデータ確認"):
    st.dataframe(st.session_state.df)

# 検索機能
search_town = st.text_input('町名を入力（部分一致可）:')
download_df = pd.DataFrame(columns=st.session_state.df.columns)

if search_town:
    filtered_df = st.session_state.df[st.session_state.df['住所（スプレッドシート用）'].str.contains(search_town, na=False)]
    filtered_df = filtered_df.dropna(subset=['Latitude', 'Longitude'])

    if not filtered_df.empty:
        selected_town = st.selectbox('町名を選択:', filtered_df['住所（スプレッドシート用）'])
        radius_km = st.number_input('半径km:', 0.5, 10.0, 3.0, 0.5)
        center = filtered_df.query('`住所（スプレッドシート用）` == @selected_town').iloc[0]

        m = folium.Map([center['Latitude'], center['Longitude']], zoom_start=14)
        folium.Circle([center['Latitude'], center['Longitude']], radius_km * 1000, fill=True, color='blue').add_to(m)

        for idx, row in st.session_state.df.iterrows():
            dist = geodesic((center['Latitude'], center['Longitude']), (row['Latitude'], row['Longitude'])).km
            if dist <= radius_km:
                folium.Marker([row['Latitude'], row['Longitude']], popup=row['住所（スプレッドシート用）']).add_to(m)
                download_df = pd.concat([download_df, row.to_frame().T])

        st_folium(m)

if not download_df.empty:
    csv = download_df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 CSVダウンロード", csv, f"範囲内_{search_town}.csv", 'text/csv')

else:
    st.info("検索結果なし or 未検索。")
