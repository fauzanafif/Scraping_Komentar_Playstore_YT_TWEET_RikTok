import streamlit as st
import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from io import BytesIO
from google_play_scraper import reviews
import tweepy
from TikTokApi import TikTokApi
import re

def download_file(df, file_format):
    buffer = BytesIO()
    if file_format == "Excel":
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Sheet1")
        buffer.seek(0)
        return buffer, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif file_format == "CSV":
        buffer.write(df.to_csv(index=False).encode("utf-8"))
        buffer.seek(0)
        return buffer, "text/csv"
    elif file_format == "JSON":
        buffer.write(df.to_json(orient="records").encode("utf-8"))
        buffer.seek(0)
        return buffer, "application/json"
    return None, None

def extract_app_id_from_url(url):
    """
    Ekstrak app ID dari URL Play Store.
    """
    try:
        match = re.search(r"id=([\w\.]+)", url)
        if match:
            return match.group(1)
        else:
            raise ValueError("URL Play Store tidak valid atau ID tidak ditemukan.")
    except Exception as e:
        st.error(f"Error extracting app ID: {str(e)}")
        return None

def scrape_playstore(url, count=2000):
    """
    Scrape ulasan dari Play Store berdasarkan URL aplikasi.
    """
    try:

        app_id = extract_app_id_from_url(url)
        if not app_id:
            raise ValueError("Gagal mengekstrak app ID dari URL.")

        result, _ = reviews(app_id, lang='id', count=count)
        reviews_data = []
        for review in result:
            reviews_data.append({
                "Date": review['at'],
                "User": review['userName'],
                "Content": review['content'],
                "Score": review['score']
            })
        return pd.DataFrame(reviews_data)

    except Exception as e:
        st.error(f"Error scraping PlayStore: {str(e)}")
        return pd.DataFrame()

def scrape_twitter(api_key, api_secret, access_token, access_token_secret, query, count=10):
    try:
        auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_token_secret)
        api = tweepy.API(auth)
        tweets = api.search_tweets(q=query, count=count, tweet_mode='extended')
        results = []
        for tweet in tweets:
            results.append({
                "Date": tweet.created_at,
                "User": tweet.user.screen_name,
                "Tweet": tweet.full_text,
                "Likes": tweet.favorite_count,
                "Retweets": tweet.retweet_count
            })
        return pd.DataFrame(results)
    except Exception as e:
        st.error(f"Error scraping Twitter: {str(e)}")
        return pd.DataFrame()

def video_comments(api_key, video_id):
    replies = []
    try:
        youtube = build('youtube', 'v3', developerKey=api_key)
        video_response = youtube.commentThreads().list(part='snippet,replies', videoId=video_id).execute()

        while video_response:
            for item in video_response['items']:
                published = item['snippet']['topLevelComment']['snippet']['publishedAt']
                user = item['snippet']['topLevelComment']['snippet']['authorDisplayName']
                comment = item['snippet']['topLevelComment']['snippet']['textDisplay']
                likeCount = item['snippet']['topLevelComment']['snippet']['likeCount']
                replies.append([published, user, comment, likeCount])

                if item['snippet']['totalReplyCount'] > 0:
                    for reply in item['replies']['comments']:
                        published = reply['snippet']['publishedAt']
                        user = reply['snippet']['authorDisplayName']
                        repl = reply['snippet']['textDisplay']
                        likeCount = reply['snippet']['likeCount']
                        replies.append([published, user, repl, likeCount])

            if 'nextPageToken' in video_response:
                video_response = youtube.commentThreads().list(
                    part='snippet,replies',
                    pageToken=video_response['nextPageToken'],
                    videoId=video_id
                ).execute()
            else:
                break
    except HttpError as e:
        st.error(f"API Error: {str(e)}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Terjadi kesalahan: {str(e)}")
        return pd.DataFrame()

    return pd.DataFrame(replies, columns=["Date", "User", "Comment", "Likes"])

def scrape_tiktok_comments(video_url):
    try:
        # Inisialisasi TikTokApi
        with TikTokApi() as api:
            # Ekstraksi video ID dari URL
            video_id = extract_video_id(video_url)
            if not video_id:
                raise ValueError("URL TikTok tidak valid atau tidak dapat diekstrak.")

            # Ambil komentar dari video
            video = api.video(id=video_id)
            comments = video.comments()

            # Proses komentar ke dalam DataFrame
            results = []
            for comment in comments:
                results.append({
                    "Date": comment.create_time,
                    "User": comment.author.username,
                    "Comment": comment.text,
                    "Likes": comment.digg_count
                })

            return pd.DataFrame(results)

    except Exception as e:
        st.error(f"Error scraping TikTok: {str(e)}")
        return pd.DataFrame()

def extract_video_id(url):
    """
    Fungsi untuk mengekstrak video ID dari URL TikTok.
    """
    import re
    try:
        match = re.search(r'\/video\/(\d+)', url)
        if match:
            return match.group(1)
        else:
            raise ValueError("Format URL TikTok tidak valid.")
    except Exception as e:
        st.error(f"Error extracting video ID: {str(e)}")
def show():
    st.title("📊 Scraping Komentar")
    st.markdown("Selamat datang di aplikasi scraping data! Pilih platform yang ingin Anda scraping, Semangat NLP😂 .!!!")

    platform = st.selectbox("Pilih platform:", ["Google Play Store", "Twitter", "YouTube", "TikTok"])

    if platform == "Google Play Store":
        app_id = st.text_input("Masukkan link aplikasi playstore:")
        count = st.number_input("Jumlah ulasan (default: 2000)", min_value=1, step=1, value=2000)
        if st.button("Scrape Data"):
            if app_id:
                data = scrape_playstore(app_id, count)
                st.dataframe(data)
            else:
                st.warning("Harap masukkan App ID.")
    elif platform == "Twitter":
        api_key = st.text_input("Masukkan API Key:")
        api_secret = st.text_input("Masukkan API Secret Key:")
        access_token = st.text_input("Masukkan Access Token:")
        access_token_secret = st.text_input("Masukkan Access Token Secret:")
        query = st.text_input("Masukkan Query:")
        count = st.number_input("Jumlah tweet:", min_value=1, step=1, value=10)
        if st.button("Scrape Data"):
            if api_key and api_secret and access_token and access_token_secret and query:
                data = scrape_twitter(api_key, api_secret, access_token, access_token_secret, query, count)
                st.dataframe(data)
            else:
                st.warning("Harap masukkan semua kredensial dan query.")
    elif platform == "YouTube":
        api_key = st.text_input("Masukkan API Key YouTube:")
        video_id = st.text_input("Masukkan Video ID:")
        if st.button("Scrape Data"):
            if api_key and video_id:
                data = video_comments(api_key, video_id)
                st.dataframe(data)
            else:
                st.warning("Harap masukkan API Key dan Video ID.")
    elif platform == "TikTok":
        video_url = st.text_input("Masukkan URL Video TikTok:")
        if st.button("Scrape Data"):
            if video_url:
                data = scrape_tiktok_comments(video_url)
                st.dataframe(data)
            else:
                st.warning("Harap masukkan URL Video TikTok.")

if __name__ == "__main__":
    show()
