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

# --- 初期データ読込み ---
if 'df' not in st.session_state:
    df1 = pd.read_csv('加古川市住所データ.csv', encoding='utf-8')
    df2 = pd.read_csv('姫路市全域住所データ - 2024331.csv', encoding='utf-8')
    df = pd.concat([df1, df2], ignore_index=True)
    df['世帯数'] = pd.to_numeric(df['世帯数'].astype(str).str.replace(',', '', regex=False), errors='coerce').fillna(0).astype(int)
    st.session_state.df = df

# --- CSV/エクセルアップロード ---
st.sidebar.header("住所データ管理")
uploaded_file = st.sidebar.file_uploader("CSVまたはExcelファイルをアップロードしてください", type=["csv", "xlsx"], key="file_upload")

if uploaded_file:
    if uploaded_file.name.endswith('.csv'):
        rawdata = uploaded_file.read()
        encoding_guess = chardet.detect(rawdata)['encoding'] or 'shift-jis'
        try:
            new_df = pd.read_csv(io.StringIO(rawdata.decode(encoding_guess)))
        except UnicodeDecodeError:
            new_df = pd.read_csv(io.StringIO(rawdata.decode('shift-jis', errors='ignore')))
    elif uploaded_file.name.endswith('.xlsx'):
        new_df = pd.read_excel(uploaded_file, engine='openpyxl')

    new_df['世帯数'] = pd.to_numeric(new_df['世帯数'].astype(str).str.replace(',', '', regex=False), errors='coerce').fillna(0).astype(int)
    st.session_state.df = pd.concat([st.session_state.df, new_df], ignore_index=True).drop_duplicates().reset_index(drop=True)
    st.sidebar.success('データが追加されました！')

# --- 現在のデータ表示 ---
with st.sidebar.expander("現在のCSVデータを確認"):
    st.dataframe(st.session_state.df)

# --- 検索機能 ---
search_town = st.text_input('町名を入力してください（部分一致でOK）:')

if search_town:
    filtered_df = st.session_state.df[st.session_state.df['住所（スプレッドシート用）'].str.contains(search_town, na=False)]
    filtered_df = filtered_df.dropna(subset=['Latitude', 'Longitude'])

    if filtered_df.empty:
        st.warning('該当する町名が見つかりません。')
    else:
        selected_town = st.selectbox('町名を選択してください:', filtered_df['住所（スプレッドシート用）'])
        radius_km = st.number_input('半径をkmで入力してください', min_value=0.5, max_value=10.0, step=0.5, value=3.0)

        selected_row = filtered_df[filtered_df['住所（スプレッドシート用）'] == selected_town].iloc[0]
        map_center = [selected_row['Latitude'], selected_row['Longitude']]

        # 地図作成
        m = folium.Map(location=map_center, zoom_start=14)
        folium.Circle(location=map_center, radius=radius_km * 1000, color='blue', fill=True, fill_opacity=0.1).add_to(m)

        # 範囲内マーカー追加
        download_df = pd.DataFrame(columns=st.session_state.df.columns)
        for idx, row in st.session_state.df.iterrows():
            distance = geodesic((selected_row['Latitude'], selected_row['Longitude']), (row['Latitude'], row['Longitude'])).km
            if distance <= radius_km:
                folium.Marker([row['Latitude'], row['Longitude']],
                              popup=f"{row['住所（スプレッドシート用）']}:{row['世帯数']}世帯",
                              icon=folium.Icon(color='green', icon='home')).add_to(m)
                download_df = pd.concat([download_df, row.to_frame().T], ignore_index=True)

        # 合計世帯数表示
        total_households = download_df['世帯数'].sum()
        st.success(f'🟢 選択した範囲（半径{radius_km}km）内の合計世帯数: {total_households:,}世帯')

        st_folium(m, width=700, height=500)

        # Web or ローカル分岐
        if IS_CLOUD:
            st.info("🛑 Web公開版では地図画像の自動保存機能は無効になっています。")
        else:
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.chrome.options import Options
            import time

            map_file = os.path.abspath('temp_map.html')
            m.save(map_file)

            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')

            service = Service(executable_path='/usr/bin/chromedriver')
            driver = webdriver.Chrome(service=service, options=options)
            driver.get(f'file://{map_file}')
            time.sleep(5)

            screenshot_file = os.path.abspath('map_image.png')
            driver.save_screenshot(screenshot_file)
            driver.quit()

            with open(screenshot_file, 'rb') as f:
                st.download_button('🗺️ 地図画像をダウンロード', f, 'map_image.png', 'image/png')

        # CSVダウンロード（町名入りファイル名にする）
        csv_buffer = io.StringIO()
        download_df.to_csv(csv_buffer, index=False)
        csv_data = csv_buffer.getvalue().encode('utf-8')
        file_name = f"範囲内住所データ_{selected_town}.csv"

        st.download_button(
            '📥 範囲内住所データをCSVでダウンロード',
            csv_data,
            file_name,
            'text/csv'
        )
else:
    st.warning('町名を入力して検索してください（部分的でもOK）')
