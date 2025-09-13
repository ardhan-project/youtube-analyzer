# youtube_channel_doctor_v3.py

import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timezone
import matplotlib.pyplot as plt

# === Google Auth untuk OAuth (opsional) ===
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# ================== Konfigurasi Awal ==================
st.set_page_config(page_title="📊 Channel Doctor - V3", layout="wide")
st.title("📊 Channel Doctor - V3")
st.write("Analisis Channel YouTube + Diagnosis & Obat Otomatis")

# ================== Sidebar ==================
st.sidebar.header("⚙️ Pengaturan")
api_key = st.sidebar.text_input("🔑 Masukkan API Key YouTube Data API v3", type="password")
channel_input = st.sidebar.text_input("📺 Channel ID / URL / Handle", help="Contoh: UC_x5XG1OV2P6uZZ5FSM9Ttw atau @Google")
max_results = st.sidebar.slider("Jumlah video yang diambil", 10, 200, 50, 10)

use_oauth = st.sidebar.checkbox("Gunakan OAuth (YouTube Analytics API)")
oauth_data = None

# ================== Jika OAuth dipilih ==================
if use_oauth:
    st.sidebar.write("📥 Upload file client_secret.json (OAuth)")
    oauth_file = st.sidebar.file_uploader("Pilih file client_secret.json", type=["json"])
    if oauth_file:
        with open("client_secret.json", "wb") as f:
            f.write(oauth_file.getbuffer())
        try:
            SCOPES = ["https://www.googleapis.com/auth/yt-analytics.readonly"]
            flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
            creds = flow.run_local_server(port=0)
            oauth_data = build("youtubeAnalytics", "v2", credentials=creds)
            st.success("✅ OAuth berhasil! Anda bisa akses data audience & analytics.")
        except Exception as e:
            st.error(f"OAuth gagal: {e}")
            oauth_data = None

# ================== Fungsi Helper ==================
SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"

def get_channel_id(input_str):
    if input_str.startswith("UC"):  
        return input_str
    if input_str.startswith("@"):  
        url = f"{CHANNELS_URL}?part=id&forHandle={input_str}&key={api_key}"
        resp = requests.get(url).json()
        return resp["items"][0]["id"] if "items" in resp else None
    if "youtube.com" in input_str:  
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

# ================== Ambil Data Dasar (API Key) ==================
if not api_key or not channel_input:
    st.warning("⚠️ Masukkan API Key dan Channel ID/Handle dulu di sidebar.")
    st.stop()

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

# ================== DataFrame Dasar ==================
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

# ================== Analisis Dasar ==================
st.header(f"📺 Analisis Channel: {channel_title}")
col1, col2, col3 = st.columns(3)
col1.metric("Total Views", f"{int(channel_stats['viewCount']):,}")
col2.metric("Subscribers", f"{int(channel_stats.get('subscriberCount',0)):,}")
col3.metric("Total Videos", f"{int(channel_stats['videoCount']):,}")

st.subheader("🔥 Top 10 Video by Views")
st.dataframe(df.sort_values("Views", ascending=False).head(10))

st.subheader("🚀 Top 10 Video by VPH (Views per Hour)")
st.dataframe(df.sort_values("VPH", ascending=False).head(10))

median_views = df["Views"].median()
underperform = df[df["Views"] < median_views].sort_values("Views")
st.subheader("📉 Video Underperform (di bawah median views)")
st.dataframe(underperform.head(10))

# Grafik Views Timeline
st.subheader("📈 Lonjakan Views (Video Terbaru)")
df_sorted = df.sort_values("Published")
plt.figure(figsize=(10,5))
plt.plot(df_sorted["Published"], df_sorted["Views"], marker="o")
plt.xticks(rotation=45)
plt.ylabel("Views")
plt.title("Views Per Video (Chronological)")
st.pyplot(plt)

# ================== Diagnosis Otomatis ==================
st.subheader("🩺 Diagnosis & Resep Channel")

diagnosis = []

# Performa umum
avg_vph = df["VPH"].mean()
if avg_vph < 5:
    diagnosis.append("⚠️ Rata-rata VPH rendah → konten kurang menarik algoritma YouTube. Obat: perbaiki judul/thumbnail & optimasi keyword trending.")
else:
    diagnosis.append("✅ VPH sehat → pertahankan pola judul & thumbnail saat ini.")

# Like ratio
df["LikeRatio"] = df.apply(lambda x: x["Likes"]/x["Views"] if x["Views"] > 0 else 0, axis=1)
avg_like_ratio = df["LikeRatio"].mean()
if avg_like_ratio < 0.02:
    diagnosis.append("⚠️ Like ratio < 2% → engagement rendah. Obat: ajak penonton like/subscribe di video.")
else:
    diagnosis.append("✅ Engagement baik → audiens suka konten Anda.")

# Underperform
if len(underperform) > len(df) * 0.5:
    diagnosis.append("⚠️ Lebih dari 50% video underperform → mungkin niche terlalu luas. Obat: fokus pada format/topik video yang terbukti sukses.")

# Jumlah upload
if int(channel_stats["videoCount"]) < 20:
    diagnosis.append("⚠️ Jumlah video masih sedikit. Obat: konsisten upload min. 2x per minggu.")
else:
    diagnosis.append("✅ Produksi konten cukup → fokus pada kualitas & konsistensi.")

# Tampilkan diagnosis
for d in diagnosis:
    st.write(d)

# ================== Audience Insight (jika OAuth aktif) ==================
if oauth_data:
    st.subheader("🌍 Audience Insight (via YouTube Analytics API)")
    try:
        request = oauth_data.reports().query(
            ids="channel==MINE",
            startDate="2024-01-01",
            endDate=datetime.today().strftime("%Y-%m-%d"),
            metrics="views,estimatedMinutesWatched,averageViewDuration",
            dimensions="country",
            sort="-views",
            maxResults=10
        )
        result = request.execute()
        if "rows" in result:
            aud_df = pd.DataFrame(result["rows"], columns=["Country", "Views", "MinutesWatched", "AvgDurationSec"])
            st.dataframe(aud_df)

            # Diagnosis tambahan berdasarkan negara
            top_country = aud_df.iloc[0]["Country"]
            st.info(f"🌎 Negara dengan minat tertinggi: **{top_country}** → gunakan judul/thumbnail berbahasa Inggris untuk jangkau audiens global.")
        else:
            st.info("Tidak ada data audience detail.")
    except Exception as e:
        st.error(f"Gagal mengambil audience insight: {e}")

# ================== Export CSV ==================
st.subheader("⬇️ Export Data")
st.download_button("Download CSV", df.to_csv(index=False).encode("utf-8"), "channel_analysis.csv", "text/csv")
