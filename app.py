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

# --- セッション状態の初期化 ---
if 'selected_towns' not in st.session_state:
    st.session_state.selected_towns = []

if 'last_selection_count' not in st.session_state:
    st.session_state.last_selection_count = 0

if 'selection_changed' not in st.session_state:
    st.session_state.selection_changed = False

# 選択変更の検知関数
def detect_selection_change():
    current_count = len(st.session_state.selected_towns)
    if current_count != st.session_state.last_selection_count:
        st.session_state.selection_changed = True
        st.session_state.last_selection_count = current_count
    return st.session_state.selection_changed

# 選択状態を更新する関数
def update_selection(town, is_selected):
    if is_selected and town not in st.session_state.selected_towns:
        st.session_state.selected_towns.append(town)
        st.session_state.selection_changed = True
    elif not is_selected and town in st.session_state.selected_towns:
        st.session_state.selected_towns.remove(town)
        st.session_state.selection_changed = True

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

# タブ選択（円形指定とチェックボックス指定の切り替え）
tab1, tab2 = st.tabs(["円形範囲指定", "町名個別選択"])

with tab1:
    st.subheader("エリア検索（円形範囲指定）")
    
    search_town = st.text_input('町名を入力してください（部分一致でOK）:', key="circle_search")

    if search_town:
        # フィルタリングされたデータから検索
        filtered_df = display_df[display_df['住所（スプレッドシート用）'].str.contains(search_town, na=False)]
        filtered_df = filtered_df.dropna(subset=['Latitude', 'Longitude'])

        if filtered_df.empty:
            st.warning('該当する町名が見つかりません。')
        else:
            selected_town = st.selectbox('町名を選択してください:', filtered_df['住所（スプレッドシート用）'])
            radius_km = st.number_input('半径をkmで入力してください', min_value=0.5, max_value=10.0, step=0.5, value=3.0)
            
            # 単価情報の入力欄を追加（最小値を0.1に変更）
            unit_price = st.number_input('ポスティング単価（円/世帯）:', min_value=0.1, value=10.0, step=0.1, key="circle_price")

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

            # 合計世帯数と売上予測を表示（「予想売上」→「算出金額」に変更）
            total_households = download_df['世帯数'].sum()
            estimated_sales = total_households * unit_price
            
            col1, col2 = st.columns(2)
            with col1:
                st.success(f'🏘️ 選択した範囲（半径{radius_km}km）内の合計世帯数: {total_households:,}世帯')
            with col2:
                st.info(f'💰 算出金額: {estimated_sales:,}円（{unit_price}円/世帯）')

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
            
            # エクセルダウンロード機能も追加（サマリーシートの表記も変更）
            with export_col2:
                try:
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        download_df.to_excel(writer, index=False, sheet_name='住所データ')
                        # サマリーシートを追加
                        summary_data = pd.DataFrame({
                            '項目': ['検索町名', '半径', '総世帯数', 'ポスティング単価', '算出金額'],
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

# ここから町名個別選択機能を追加
with tab2:
    st.subheader("町名個別選択")
    
    # 検索フィルター
    search_filter = st.text_input('検索フィルター（町名の一部を入力）:', key="checkbox_filter")
    
    # 方向フィルター（オプション）の改良版 - 複数選択可能に
    st.write("方向フィルター（オプション）")
    direction_col1, direction_col2 = st.columns(2)
    
    with direction_col1:
        base_point_search = st.text_input('基準点を検索:', key="base_point_search")
        base_point_df = display_df[display_df['住所（スプレッドシート用）'].str.contains(base_point_search, na=False)] if base_point_search else pd.DataFrame()
        
        if not base_point_df.empty:
            base_point_options = base_point_df['住所（スプレッドシート用）'].tolist()
            base_point = st.selectbox('基準点を選択:', base_point_options, key="base_point_select")
        else:
            base_point = None
            if base_point_search:
                st.warning('該当する基準点が見つかりません。')
    
    with direction_col2:
        # 複数方向選択可能に変更
        directions = ["北側", "南側", "東側", "西側"]
        selected_directions = []
        
        # 水平方向
        horizontal_col1, horizontal_col2 = st.columns(2)
        with horizontal_col1:
            if st.checkbox("東側", key="east_direction"):
                selected_directions.append("東側")
        with horizontal_col2:
            if st.checkbox("西側", key="west_direction"):
                selected_directions.append("西側")
        
        # 垂直方向
        vertical_col1, vertical_col2 = st.columns(2)
        with vertical_col1:
            if st.checkbox("北側", key="north_direction"):
                selected_directions.append("北側")
        with vertical_col2:
            if st.checkbox("南側", key="south_direction"):
                selected_directions.append("南側")
    
    # 都市の選択状態と対応する一括選択ボタン
    if selected_city != "すべての市":
        st.write(f"{selected_city}の町名を一括操作:")
        city_select_col1, city_select_col2 = st.columns(2)
        with city_select_col1:
            if st.button(f'{selected_city}の全町名を選択', key="select_city_all"):
                # 該当する市の全町名をセッション状態に保存
                city_towns = display_df[display_df['住所（スプレッドシート用）'].str.contains(selected_city, na=False)]['住所（スプレッドシート用）'].unique().tolist()
                if 'selected_towns' not in st.session_state:
                    st.session_state.selected_towns = []
                st.session_state.selected_towns = list(set(st.session_state.selected_towns + city_towns))
                st.session_state.selection_changed = True
                st.success(f"{len(city_towns)}件の{selected_city}の町名を選択しました")
        
        with city_select_col2:
            if st.button(f'{selected_city}の全町名を解除', key="deselect_city_all"):
                # 該当する市の全町名をセッション状態から削除
                if 'selected_towns' in st.session_state:
                    city_towns = display_df[display_df['住所（スプレッドシート用）'].str.contains(selected_city, na=False)]['住所（スプレッドシート用）'].unique().tolist()
                    st.session_state.selected_towns = [town for town in st.session_state.selected_towns if town not in city_towns]
                    st.session_state.selection_changed = True
                    st.success(f"{selected_city}の町名の選択を解除しました")
    
    # 町名リストの作成（検索フィルターを適用）
    filtered_towns_df = display_df.copy()
    
    # 検索フィルターを適用
    if search_filter:
        filtered_towns_df = filtered_towns_df[filtered_towns_df['住所（スプレッドシート用）'].str.contains(search_filter, na=False)]
    
    # 方向フィルターを適用（基準点が選択されていて、方向も選択されている場合）
    if base_point and selected_directions:
        # 基準点の座標を取得
        base_point_row = display_df[display_df['住所（スプレッドシート用）'] == base_point].iloc[0]
        base_latitude = base_point_row['Latitude']
        base_longitude = base_point_row['Longitude']
        
        # 方向に基づいてフィルタリング
        direction_filtered_indices = []
        for idx, row in filtered_towns_df.iterrows():
            if pd.notna(row['Latitude']) and pd.notna(row['Longitude']):
                # 方向の判定
                is_north = row['Latitude'] > base_latitude
                is_south = row['Latitude'] < base_latitude
                is_east = row['Longitude'] > base_longitude
                is_west = row['Longitude'] < base_longitude
                
                # 選択された方向のいずれかに当てはまればOK（OR条件）
                matches_direction = False
                for direction in selected_directions:
                    if (direction == "北側" and is_north) or \
                       (direction == "南側" and is_south) or \
                       (direction == "東側" and is_east) or \
                       (direction == "西側" and is_west):
                        matches_direction = True
                        break
                
                if matches_direction:
                    direction_filtered_indices.append(idx)
        
        # フィルタリングを適用
        filtered_towns_df = filtered_towns_df.loc[direction_filtered_indices]
    
    # 町名のリストを取得（重複排除、ソート）
    unique_towns = sorted(filtered_towns_df['住所（スプレッドシート用）'].unique())
    
    # 「すべて選択」と「すべて解除」ボタン
    select_col1, select_col2, select_col3 = st.columns(3)
    with select_col1:
        if st.button('現在の表示をすべて選択', key="select_all"):
            for town in unique_towns:
                if town not in st.session_state.selected_towns:
                    st.session_state.selected_towns.append(town)
            st.session_state.selection_changed = True
            st.success(f"{len(unique_towns)}件の町名を選択しました")
    
    with select_col2:
        if st.button('現在の表示をすべて解除', key="deselect_all"):
            st.session_state.selected_towns = [town for town in st.session_state.selected_towns if town not in unique_towns]
            st.session_state.selection_changed = True
            st.success("表示中の町名の選択を解除しました")
    
    with select_col3:
        if st.button('選択を全解除', key="clear_all"):
            st.session_state.selected_towns = []
            st.session_state.selection_changed = True
            st.success("すべての選択を解除しました")
    
    # 方向フィルターが適用されている場合の表示
    if base_point and selected_directions:
        direction_text = "・".join(selected_directions)
        st.success(f"基準点「{base_point}」の {direction_text} の町名を表示しています（{len(unique_towns)}件）")
    
    # チェックボックスでの町名選択
    st.write(f"町名を選択（{len(unique_towns)}件）:")
    
    # 反転選択オプション - 現在表示されている町名の選択状態を一括反転
    if st.button('表示中の選択を反転', key="invert_selection"):
        new_selections = []
        for town in st.session_state.selected_towns:
            if town not in unique_towns:  # 現在表示されていない選択済みの町名は保持
                new_selections.append(town)
        
        for town in unique_towns:
            if town not in st.session_state.selected_towns:  # 現在表示されていて未選択の町名を追加
                new_selections.append(town)
        
        st.session_state.selected_towns = new_selections
        st.session_state.selection_changed = True
        st.success("表示中の町名の選択状態を反転しました")
    
    # 町名リストが多い場合にスクロール可能なコンテナに
    town_container = st.container()
    
    # 選択状態を表示するための辞書を作成
    selection_state = {}
    
    # スクロール可能なコンテナにする
    with town_container:
        # 表示する町名の数に応じて列数を調整
        num_towns = len(unique_towns)
        if num_towns > 50:
            num_cols = 3
        elif num_towns > 20:
            num_cols = 2
        else:
            num_cols = 1
        
        # 列ごとに表示する町名の数を計算
        towns_per_col = -(-num_towns // num_cols)  # 切り上げ除算
        
        # 列を作成
        cols = st.columns(num_cols)
        
        # 各列にチェックボックスを配置
        for i in range(num_cols):
            start_idx = i * towns_per_col
            end_idx = min(start_idx + towns_per_col, num_towns)
            
            with cols[i]:
                for town in unique_towns[start_idx:end_idx]:
                    # その町の世帯数を取得
                    town_households = filtered_towns_df[filtered_towns_df['住所（スプレッドシート用）'] == town]['世帯数'].sum()
                    
                    # チェックボックスの状態を更新
                    is_checked = st.checkbox(
                        f"{town} ({town_households:,}世帯)",
                        value=town in st.session_state.selected_towns,
                        key=f"town_{town}"
                    )
                    
                    # 選択状態を記録
                    selection_state[town] = is_checked
                    
                    # セッション状態を更新
                    update_selection(town, is_checked)
    
    # 更新された選択状態を反映
    st.session_state.selection_changed = detect_selection_change()
    
    # 単価情報の入力欄
    unit_price_checkbox = st.number_input('ポスティング単価（円/世帯）:', min_value=0.1, value=10.0, step=0.1, key="checkbox_price")
    
    # 選択された町名の合計世帯数を計算
    if st.session_state.selected_towns:
        selected_towns_df = display_df[display_df['住所（スプレッドシート用）'].isin(st.session_state.selected_towns)]
        total_households_checkbox = selected_towns_df['世帯数'].sum()
        estimated_sales_checkbox = total_households_checkbox * unit_price_checkbox
        
        # 結果表示
        result_container = st.container()
        with result_container:
            st.success(f'🏘️ 選択した町名（{len(st.session_state.selected_towns)}件）の合計世帯数: {total_households_checkbox:,}世帯')
            st.info(f'💰 算出金額: {estimated_sales_checkbox:,}円（{unit_price_checkbox}円/世帯）')
        
        # 選択した町名を地図に表示 - 常に最新の状態を反映
        show_map = st.checkbox('選択した町名を地図に表示', value=True)
        map_container = st.container()
        
        if show_map:
            with map_container:
                # 地図の中心を計算（選択したすべての町の平均位置）
                valid_coords = selected_towns_df.dropna(subset=['Latitude', 'Longitude'])
                if not valid_coords.empty:
                    center_lat = valid_coords['Latitude'].mean()
                    center_lon = valid_coords['Longitude'].mean()
                    
                    # 地図作成
                    m_selected = folium.Map(location=[center_lat, center_lon], zoom_start=13)
                    
                    # 選択された町のマーカーを追加
                    for idx, row in valid_coords.iterrows():
                        folium.Marker(
                            [row['Latitude'], row['Longitude']],
                            popup=f"{row['住所（スプレッドシート用）']}:{row['世帯数']}世帯",
                            icon=folium.Icon(color='blue', icon='home')
                        ).add_to(m_selected)
                    
                    # 基準点がある場合は特別なマーカーを追加
                    if base_point:
                        base_point_row = display_df[display_df['住所（スプレッドシート用）'] == base_point].iloc[0]
                        folium.Marker(
                            [base_point_row['Latitude'], base_point_row['Longitude']],
                            popup=f"<b>{base_point}</b> (基準点)",
                            icon=folium.Icon(color='red', icon='star')
                        ).add_to(m_selected)
                    
                    # 地図表示 - キーを追加して更新を強制
                    map_key = f"map_{len(st.session_state.selected_towns)}"
                    st_folium(m_selected, width=700, height=500, key=map_key)
                    
                    # スクリーンショット（ローカルのみ）
                    if not IS_CLOUD:
                        try:
                            import chromedriver_autoinstaller
                            from selenium import webdriver
                            from selenium.webdriver.chrome.options import Options
                            
                            chromedriver_autoinstaller.install()
                            map_file = os.path.abspath('temp_map_selected.html')
                            m_selected.save(map_file)

                            options = Options()
                            options.add_argument('--headless')
                            options.add_argument('--no-sandbox')
                            options.add_argument('--disable-dev-shm-usage')
                            options.add_argument('--disable-gpu')
                            options.add_argument('--window-size=1920,1080')

                            driver = webdriver.Chrome(options=options)
                            driver.get(f'file://{map_file}')
                            time.sleep(5)

                            screenshot_file = os.path.abspath('map_selected_image.png')
                            driver.save_screenshot(screenshot_file)
                            driver.quit()

                            with open(screenshot_file, 'rb') as f:
                                st.download_button('🗺️ 選択地域の地図画像をダウンロード', f, 'map_selected_image.png', 'image/png')

                        except Exception as e:
                            st.error(f"地図のスクリーンショット取得に失敗しました（ローカル環境専用機能）: {e}")
                    else:
                        st.info("🛑 Web公開版では地図画像の自動保存機能は利用できません。")
                else:
                    st.warning('選択した町名に有効な座標データがありません。')
        
        # CSVダウンロード - 選択変更があったか定期的に確認して更新
        csv_buffer = io.StringIO()
        selected_towns_df.to_csv(csv_buffer, index=False)
        csv_data = csv_buffer.getvalue().encode('utf-8')
        
        # 方向情報を含めたファイル名
        direction_str = f"_{'-'.join(selected_directions)}" if selected_directions else ""
        file_prefix = base_point.replace("/", "／") if base_point else "選択地域"
        file_name = f"{file_prefix}{direction_str}_住所データ.csv"
        
        # エクスポートボタンのコンテナ
        export_col1, export_col2 = st.columns(2)
        with export_col1:
            st.download_button(
                '📥 選択地域の住所データをCSVでダウンロード',
                csv_data,
                file_name,
                'text/csv'
            )
        
        # エクセルダウンロード
        with export_col2:
            try:
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    selected_towns_df.to_excel(writer, index=False, sheet_name='住所データ')
                    
                    # 選択した町名のリスト
                    town_list_df = pd.DataFrame({'選択した町名': st.session_state.selected_towns})
                    town_list_df.to_excel(writer, index=False, sheet_name='選択町名リスト')
                    
                    # サマリーシート
                    direction_info = f"{'-'.join(selected_directions)}の町名" if selected_directions else "選択された町名"
                    base_info = f"基準点: {base_point}" if base_point else "基準点なし"
                    
                    summary_data = pd.DataFrame({
                        '項目': ['選択方法', '基準点情報', '選択町名数', '総世帯数', 'ポスティング単価', '算出金額'],
                        '値': [direction_info, base_info, f'{len(st.session_state.selected_towns)}件', 
                              f'{total_households_checkbox:,}世帯', f'{unit_price_checkbox}円/世帯', 
                              f'{estimated_sales_checkbox:,}円']
                    })
                    summary_data.to_excel(writer, index=False, sheet_name='サマリー')
                
                excel_data = buffer.getvalue()
                excel_file_name = file_name.replace('.csv', '.xlsx')
                
                st.download_button(
                    '📊 選択地域の住所データをExcelでダウンロード',
                    excel_data,
                    excel_file_name,
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
            except Exception as e:
                st.error(f"Excelファイル作成に失敗しました: {e}")
    else:
        st.warning('町名を選択してください')

# フッター情報
st.markdown("---")
st.markdown("**ポスティングエリア世帯数計算ツール** - 加古川市・姫路市・神戸市・西宮市・高砂市・明石市対応")