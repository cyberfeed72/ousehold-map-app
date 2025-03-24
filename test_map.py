import pandas as pd
import folium
import webbrowser

# CSVを読み込む
df = pd.read_csv('加古川市住所データ.csv')

# 地図を作成する
map_center = [df.iloc[0]['Latitude'], df.iloc[0]['Longitude']]
m = folium.Map(location=map_center, zoom_start=13)

# マーカー表示
for idx, row in df.iterrows():
    folium.Marker(
        location=[row['Latitude'], row['Longitude']],
        popup=f"{row['住所（スプレッドシート用）']}: {row['世帯数']}世帯",
        icon=folium.Icon(icon='home', color='blue')
    ).add_to(m)

# デスクトップにHTMLを作成して保存
m.save('/Users/hiraokashigeru/Desktop/test_map.html')

# 作成したHTMLファイルをブラウザで自動的に開く
import webbrowser
webbrowser.open('file:///Users/hiraokashigeru/Desktop/test_map.html')
