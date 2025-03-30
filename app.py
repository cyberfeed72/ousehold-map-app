import os
import time
import io
import chardet
import streamlit as st
import pandas as pd
import folium
from geopy.distance import geodesic
from streamlit_folium import st_folium

# --- Cloud or local 判定 ---
IS_CLOUD = os.environ.get("STREAMLIT_SERVER_HEADLESS") == "1"

# --- 初期データ読込み ---
if 'df' not in st.session_state:
    try:
        # 既存のデータファイル
        df1 = pd.read_csv('加古川市住所データ.csv', encoding='utf-8')
        df2 = pd.read_csv('姫路市全域住所データ - 2024331.csv', encoding='utf-8')
        
        # 新規追加する市のデータファイル
        df_list = [df1, df2]
        
        try:
            df3 = pd.read_csv('神戸市住所データ.csv', encoding='utf-8')
            df_list.append(df3)
        except Exception as e:
            if not IS_CLOUD:
                st.warning(f"神戸市データファイルの読み込みに失敗: {str(e)}")
                
        try:
            df4 = pd.read_csv('明石市住所データ.csv', encoding='utf-8')
            df_list.append(df4)
        except Exception as e:
            if not IS_CLOUD:
                st.warning(f"明石市データファイルの読み込みに失敗: {str(e)}")
                
        try:
            df5 = pd.read_csv('西宮市住所データ.csv', encoding='utf-8')
            df_list.append(df5)
        except Exception as e:
            if not IS_CLOUD:
                st.warning(f"西宮市データファイルの読み込みに失敗: {str(e)}")
                
        try:
            df6 = pd.read_csv('高砂市住所データ.csv', encoding='utf-8')
            df_list.append(df6)
        except Exception as e:
            if not IS_CLOUD:
                st.warning(f"高砂市データファイルの読み込みに失敗: {str(e)}")
        
        # すべてのデータフレームを結合
        df = pd.concat(df_list, ignore_index=True)
        
    except Exception as e:
        st.error(f"データの読み込みに失敗しました: {str(e)}")
        df = pd.DataFrame(columns=['住所（スプレッドシート用）', '世帯数', 'Latitude', 'Longitude'])
    
    df['世帯数'] = pd.to_numeric(df['世帯数'].astype(str).str.replace(',', '', regex=False), errors='coerce').fillna(0).astype(int)
    st.session_state.df = df

# --- サイドバーに都市選択フィルター追加 ---
st.sidebar.header("データフィルター")
cities = ["すべての市", "加古川市", "姫路市", "神戸市", "西宮市", "高砂市", "明石市"]
selected_city = st.sidebar.selectbox("市を選択:", cities)

# 選択された市でデータをフィルタリング
if selected_city != "すべての市":
    filtered_city_df = st.session_state.df[st.session_state.df['住所（スプレッドシート用）'].str.contains(selected_city, na=False)]
    # 一時的にフィルタリングされたデータを使用
    display_df = filtered_city_df
else:
    display_df = st.session_state.df

# 現在のフィルタリング状態を表示
st.sidebar.info(f"現在のデータ: {selected_city if selected_city != 'すべての市' else '全地域'} ({len(display_df)} 件)")

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
    st.dataframe(display_df)

# --- 検索機能 ---
st.title("ポスティングエリア世帯数計算ツール")
st.subheader("エリア検索")

search_town = st.text_input('町名を入力してください（部分一致でOK）:')

if search_town:
    # フィルタリングされたデータから検索
    filtered_df = display_df[display_df['住所（スプレッドシート用）'].str.contains(search_town, na=False)]
    filtered_df = filtered_df.dropna(subset=['Latitude', 'Longitude'])

    if filtered_df.empty:
        st.warning('該当する町名が見つかりません。')
    else:
        selected_town = st.selectbox('町名を選択してください:', filtered_df['住所（スプレッドシート用）'])
        radius_km = st.number_input('半径をkmで入力してください', min_value=0.5, max_value=10.0, step=0.5, value=3.0)
        
        # 単価情報の入力欄を追加
        unit_price = st.number_input('ポスティング単価（円/世帯）:', min_value=1, value=10)

        selected_row = filtered_df[filtered_df['住所（スプレッドシート用）'] == selected_town].iloc[0]
        map_center = [selected_row['Latitude'], selected_row['Longitude']]

        # 地図作成
        m = folium.Map(location=map_center, zoom_start=14)
        folium.Circle(location=map_center, radius=radius_km * 1000, color='blue', fill=True, fill_opacity=0.1).add_to(m)
        
        # 中心点マーカー（選択した地点）
        folium.Marker(
            map_center,
            popup=f"<b>{selected_town}</b>",
            icon=folium.Icon(color='red', icon='star')
        ).add_to(m)

        # 範囲内マーカー追加
        download_df = pd.DataFrame(columns=st.session_state.df.columns)
        for idx, row in st.session_state.df.iterrows():
            if pd.notna(row['Latitude']) and pd.notna(row['Longitude']):
                distance = geodesic((selected_row['Latitude'], selected_row['Longitude']), (row['Latitude'], row['Longitude'])).km
                if distance <= radius_km:
                    folium.Marker([row['Latitude'], row['Longitude']],
                              popup=f"{row['住所（スプレッドシート用）']}:{row['世帯数']}世帯",
                              icon=folium.Icon(color='green', icon='home')).add_to(m)
                    download_df = pd.concat([download_df, row.to_frame().T], ignore_index=True)

        # 合計世帯数と売上予測を表示
        total_households = download_df['世帯数'].sum()
        estimated_sales = total_households * unit_price
        
        col1, col2 = st.columns(2)
        with col1:
            st.success(f'🏘️ 選択した範囲（半径{radius_km}km）内の合計世帯数: {total_households:,}世帯')
        with col2:
            st.info(f'💰 予想売上: {estimated_sales:,}円（{unit_price}円/世帯）')

        st_folium(m, width=700, height=500)

        # --- スクリーンショット保存（ローカルのみ） ---
        if not IS_CLOUD:
            try:
                import chromedriver_autoinstaller
                from selenium import webdriver
                from selenium.webdriver.chrome.options import Options
                
                chromedriver_autoinstaller.install()
                map_file = os.path.abspath('temp_map.html')
                m.save(map_file)

                options = Options()
                options.add_argument('--headless')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--disable-gpu')
                options.add_argument('--window-size=1920,1080')

                driver = webdriver.Chrome(options=options)
                driver.get(f'file://{map_file}')
                time.sleep(5)

                screenshot_file = os.path.abspath('map_image.png')
                driver.save_screenshot(screenshot_file)
                driver.quit()

                with open(screenshot_file, 'rb') as f:
                    st.download_button('🗺️ 地図画像をダウンロード', f, 'map_image.png', 'image/png')

            except Exception as e:
                st.error(f"地図のスクリーンショット取得に失敗しました（ローカル環境専用機能）: {e}")
        else:
            st.info("🛑 Web公開版では地図画像の自動保存機能は利用できません。")

        # --- CSVダウンロード（町名入りファイル名にする） ---
        csv_buffer = io.StringIO()
        download_df.to_csv(csv_buffer, index=False)
        csv_data = csv_buffer.getvalue().encode('utf-8')
        file_name = f"範囲内住所データ_{selected_town}.csv"

        # エクスポートボタンのコンテナ
        export_col1, export_col2 = st.columns(2)
        with export_col1:
            st.download_button(
                '📥 範囲内住所データをCSVでダウンロード',
                csv_data,
                file_name,
                'text/csv'
            )
        
        # エクセルダウンロード機能も追加
        with export_col2:
            try:
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    download_df.to_excel(writer, index=False, sheet_name='住所データ')
                    # サマリーシートを追加
                    summary_data = pd.DataFrame({
                        '項目': ['検索町名', '半径', '総世帯数', 'ポスティング単価', '予想売上'],
                        '値': [selected_town, f'{radius_km}km', f'{total_households:,}世帯', f'{unit_price}円/世帯', f'{estimated_sales:,}円']
                    })
                    summary_data.to_excel(writer, index=False, sheet_name='サマリー')
                
                excel_data = buffer.getvalue()
                st.download_button(
                    '📊 範囲内住所データをExcelでダウンロード',
                    excel_data,
                    f"範囲内住所データ_{selected_town}_{radius_km}km.xlsx",
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
            except Exception as e:
                st.error(f"Excelファイル作成に失敗しました: {e}")
else:
    st.warning('町名を入力して検索してください（部分的でもOK）')

# フッター情報
st.markdown("---")
st.markdown("**ポスティングエリア世帯数計算ツール** - 加古川市・姫路市・神戸市・西宮市・高砂市・明石市対応")