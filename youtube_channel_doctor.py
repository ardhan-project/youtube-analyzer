# youtube_channel_doctor.py

import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
import matplotlib.pyplot as plt

# ================== Konfigurasi Awal ==================
st.set_page_config(page_title="📊 Channel Doctor - V1", layout="wide")
st.title("📊 Channel Doctor - Versi Dasar (V1)")
st.write("Analisis Channel YouTube: Views, VPH, Lonjakan, dan Video Underperform")

# ================== Input API Key & Channel ==================
st.sidebar.header("⚙️ Pengaturan")
api_key = st.sidebar.text_input("🔑 Masukkan API Key YouTube Data API v3", type="password")
channel_input = st.sidebar.text_input("📺 Channel ID / URL / Handle", help="Contoh: UC_x5XG1OV2P6uZZ5FSM9Ttw atau @Google")
max_results = st.sidebar.slider("Jumlah video yang diambil", 10, 200, 50, 10)

if not api_key or not channel_input:
    st.warning("⚠️ Masukkan API Key dan Channel ID/Handle dulu di sidebar.")
    st.stop()

# ================== Fungsi Helper ==================
SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"

def get_channel_id(input_str):
    """Konversi handle/URL ke Channel ID"""
    if input_str.startswith("UC"):  # Sudah Channel ID
        return input_str
    if input_str.startswith("@"):  # Handle
        url = f"{CHANNELS_URL}?part=id&forHandle={input_str}&key={api_key}"
        resp = requests.get(url).json()
        return resp["items"][0]["id"] if "items" in resp else None
    if "youtube.com" in input_str:  # URL channel
        if "/channel/" in input_str:
            return input_str.split("/channel/")[1]
        if "/@" in input_str:
            handle = input_str.split("/@")[1]
            return get_channel_id("@" + handle)
    return None

def get_uploads_playlist(channel_id):
    url = f"{CHANNELS_URL}?part=contentDetails,snippet,statistics&id={channel_id}&key={api_key}"
    resp = requests.get(url).json()
    if "items" not in resp or len(resp["items"]) == 0:
        return None, None, None
    uploads = resp["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    stats = resp["items"][0]["statistics"]
    title = resp["items"][0]["snippet"]["title"]
    return uploads, stats, title

def get_videos_from_playlist(playlist_id, max_results=50):
    videos = []
    page_token = ""
    while len(videos) < max_results:
        url = f"https://www.googleapis.com/youtube/v3/playlistItems?part=contentDetails&playlistId={playlist_id}&maxResults=50&pageToken={page_token}&key={api_key}"
        resp = requests.get(url).json()
        if "items" not in resp:
            break
        for item in resp["items"]:
            videos.append(item["contentDetails"]["videoId"])
            if len(videos) >= max_results:
                break
        page_token = resp.get("nextPageToken", "")
        if not page_token:
            break
    return videos

def get_video_details(video_ids):
    url = f"{VIDEOS_URL}?part=snippet,statistics,contentDetails&id={','.join(video_ids)}&key={api_key}"
    resp = requests.get(url).json()
    return resp.get("items", [])

# ================== Proses Data ==================
with st.spinner("Mengambil data channel..."):
    channel_id = get_channel_id(channel_input)
    if not channel_id:
        st.error("❌ Tidak bisa menemukan Channel ID dari input.")
        st.stop()

    uploads_playlist, channel_stats, channel_title = get_uploads_playlist(channel_id)
    if not uploads_playlist:
        st.error("❌ Channel tidak ditemukan atau API Key salah.")
        st.stop()

    video_ids = get_videos_from_playlist(uploads_playlist, max_results)
    video_data = get_video_details(video_ids)

# ================== DataFrame ==================
rows = []
for v in video_data:
    vid = v["id"]
    title = v["snippet"]["title"]
    published = datetime.fromisoformat(v["snippet"]["publishedAt"].replace("Z", "+00:00"))
    views = int(v["statistics"].get("viewCount", 0))
    likes = int(v["statistics"].get("likeCount", 0))
    comments = int(v["statistics"].get("commentCount", 0))
    age_hours = (datetime.now(timezone.utc) - published).total_seconds() / 3600
    vph = views / age_hours if age_hours > 0 else 0
    rows.append([vid, title, published, views, likes, comments, round(vph, 2)])

df = pd.DataFrame(rows, columns=["VideoID", "Title", "Published", "Views", "Likes", "Comments", "VPH"])

# ================== Analisis ==================
st.header(f"📺 Analisis Channel: {channel_title}")
col1, col2, col3 = st.columns(3)
col1.metric("Total Views", f"{int(channel_stats['viewCount']):,}")
col2.metric("Subscribers", f"{int(channel_stats.get('subscriberCount',0)):,}")
col3.metric("Total Videos", f"{int(channel_stats['videoCount']):,}")

# Top Performers
st.subheader("🔥 Top 10 Video by Views")
st.dataframe(df.sort_values("Views", ascending=False).head(10))

st.subheader("🚀 Top 10 Video by VPH (Views per Hour)")
st.dataframe(df.sort_values("VPH", ascending=False).head(10))

# Underperform
median_views = df["Views"].median()
underperform = df[df["Views"] < median_views].sort_values("Views")
st.subheader("📉 Video Underperform (di bawah median views)")
st.dataframe(underperform.head(10))

# Grafik Lonjakan
st.subheader("📈 Lonjakan Views (Video Terbaru)")
df_sorted = df.sort_values("Published")
plt.figure(figsize=(10,5))
plt.plot(df_sorted["Published"], df_sorted["Views"], marker="o")
plt.xticks(rotation=45)
plt.ylabel("Views")
plt.title("Views Per Video (Chronological)")
st.pyplot(plt)

# ================== Download CSV ==================
st.subheader("⬇️ Export Data")
st.download_button("Download CSV", df.to_csv(index=False).encode("utf-8"), "channel_analysis.csv", "text/csv")

