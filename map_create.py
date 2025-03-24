import pandas as pd
import folium
import os

# CSVファイルを読み込み
df = pd.read_csv('加古川市住所データ.csv')

# CSVの中身を確認（任意）
print(df.head())

# 地図の中心を設定
map_center = [df.iloc[0]['Latitude'], df.iloc[0]['Longitude']]

# 地図を作成
m = folium.Map(location=map_center, zoom_start=13)

# CSVデータをもとに地図に表示
for idx, row in df.iterrows():
    town = row['住所（スプレッドシート用）']
    households = row['世帯数']
    lat = row['Latitude']
    lon = row['Longitude']

    folium.Marker(
        location=[lat, lon],
        popup=f"{town}: {households}世帯",
        icon=folium.Icon(icon='home', color='blue')
    ).add_to(m)

# 強制的に絶対パスでHTMLとして保存（必ずファイルが作られます）
save_path = os.path.expanduser('~/Desktop/kakogawa_seitai_map.html')
m.save(save_path)

print(f"地図を作成しました。保存場所: {save_path}")
