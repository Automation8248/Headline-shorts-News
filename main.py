import os
import random
import requests
import feedparser
import asyncio
import nest_asyncio
import edge_tts
import json
from datetime import datetime
from PIL import Image, ImageEnhance
from io import BytesIO
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips, CompositeAudioClip, CompositeVideoClip, TextClip
from moviepy.audio.fx.all import volumex, audio_loop

nest_asyncio.apply()

# --- CONFIGURATION ---
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "YOUR_WEBHOOK_URL")

# Telegram Setup 
SUCCESS_TELEGRAM_TOKEN = "8224108699:AAGDSyG07MrGFoiphWy6FsOtaSUraQ87yoI"
ERROR_TELEGRAM_TOKEN = "8224108699:AAGDSyG07MrGFoiphWy6FsOtaSUraQ87yoI"
TELEGRAM_CHAT_ID = "7584043609"

AUTOMATION_NAME = "USA_Politics_Daily_Bot"
SOCIAL_MEDIA = "Webhook/CustomPlatform"

# Folders and Files
METADATA_DIR = "metadata"
BGM_DIR = "bg_music"
os.makedirs(METADATA_DIR, exist_ok=True)
os.makedirs(BGM_DIR, exist_ok=True)

HASHTAG_FILE = os.path.join(METADATA_DIR, "hastag.txt")
TITLE_FILE = os.path.join(METADATA_DIR, "title.txt")
HISTORY_FILE = os.path.join(METADATA_DIR, "history.json")

COOLING_DAYS = 30
USER_AGENTS = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"]

# --- TELEGRAM LOGGING ---
def send_telegram_msg(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Telegram failed: {e}")

def log_success(video_url, title, hashtag):
    msg = f"✅ <b>Success</b>\n<b>Bot:</b> {AUTOMATION_NAME}\n<b>Platform:</b> {SOCIAL_MEDIA}\n<b>Title:</b> {title}\n<b>Hashtags:</b> {hashtag}\n<b>Video URL:</b> {video_url}"
    send_telegram_msg(SUCCESS_TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)

def log_error(error_msg):
    msg = f"❌ <b>Error</b>\n<b>Bot:</b> {AUTOMATION_NAME}\n<b>Platform:</b> {SOCIAL_MEDIA}\n<b>Error Details:</b> {error_msg}"
    send_telegram_msg(ERROR_TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)

# --- METADATA MANAGEMENT ---
def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            try: return json.load(f)
            except: return {"titles": {}, "hashtags": {}}
    return {"titles": {}, "hashtags": {}}

def save_history(history):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f)

def get_random_item_with_cooling(filepath, history_dict, item_type):
    if not os.path.exists(filepath):
        with open(filepath, 'w') as f:
            f.write(f"Dummy {item_type} Line 1\nDummy {item_type} Line 2\n")
            
    with open(filepath, 'r') as f:
        items = [line.strip() for line in f.readlines() if line.strip()]
    
    if not items: return "Default Item"
    now = datetime.now()
    available_items = []
    
    for item in items:
        last_used_str = history_dict.get(item)
        if last_used_str:
            last_used = datetime.fromisoformat(last_used_str)
            if (now - last_used).days > COOLING_DAYS:
                available_items.append(item)
        else:
            available_items.append(item)
            
    if not available_items: available_items = items
    selected = random.choice(available_items)
    history_dict[selected] = now.isoformat()
    return selected

# --- AUDIO & SUBTITLES ---
async def generate_audio_and_subs(text, index):
    audio_file = f"temp_audio_{index}.mp3"
    sub_file = f"temp_sub_{index}.vtt"
    communicate = edge_tts.Communicate(text, "en-US-JennyNeural")
    submaker = edge_tts.SubMaker()
    
    with open(audio_file, "wb") as file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                submaker.create_sub((chunk["offset"], chunk["duration"]), chunk["text"])

    with open(sub_file, "w", encoding="utf-8") as file:
        file.write(submaker.generate_subs())
    return audio_file, sub_file

def create_subtitles(vtt_path, audio_clip):
    subs = []
    try:
        with open(vtt_path, "r", encoding="utf-8") as f: lines = f.readlines()
        i = 1
        while i < len(lines):
            line = lines[i].strip()
            if "-->" in line:
                times = line.split(" --> ")
                def parse_time(t):
                    h, m, s = t.split(":")
                    s, ms = s.split(".")
                    return int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000.0
                start_t, end_t = parse_time(times[0]), parse_time(times[1])
                
                text_line = ""
                i += 1
                while i < len(lines) and lines[i].strip() != "":
                    text_line += lines[i].strip() + " "
                    i += 1
                
                txt_clip = TextClip(text_line.strip(), fontsize=60, color='yellow', font='Arial-Bold', bg_color='black')
                txt_clip = txt_clip.set_position(('center', 'center')).set_start(start_t).set_end(end_t)
                subs.append(txt_clip)
            i += 1
    except Exception as e: print(f"Subtitle error: {e}")
    return subs

# --- NEWS & IMAGE ---
def get_latest_news():
    rss_url = "https://news.yahoo.com/rss/politics"
    feed = feedparser.parse(rss_url)
    news_list = []
    for entry in feed.entries:
        if len(news_list) >= 3: break
        title = entry.title.replace('#', '').replace('*', '').strip()
        image_url = entry.media_content[0]['url'] if 'media_content' in entry else None
        if image_url: news_list.append((title, image_url))
    return news_list

def create_image_frame(image_url, index):
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    response = requests.get(image_url, headers=headers, timeout=10)
    if response.status_code != 200: return None

    img = Image.open(BytesIO(response.content)).convert("RGB")
    target_width, target_height = 1080, 1920 
    img_ratio = img.width / img.height
    target_ratio = target_width / target_height
    
    if img_ratio > target_ratio:
        new_width = int(target_ratio * img.height)
        offset = (img.width - new_width) // 2
        img = img.crop((offset, 0, offset + new_width, img.height))
    else:
        new_height = int(img.width / target_ratio)
        offset = (img.height - new_height) // 2
        img = img.crop((0, offset, img.width, offset + new_height))
        
    img = img.resize((target_width, target_height), Image.Resampling.BILINEAR)
    img = ImageEnhance.Brightness(img).enhance(0.4) 
    
    temp_image_path = f"temp_frame_{index}.jpg"
    img.save(temp_image_path, quality=85)
    return temp_image_path

def download_openverse_bgm():
    existing_files = [f for f in os.listdir(BGM_DIR) if f.endswith('.mp3')]
    if existing_files: return random.choice([os.path.join(BGM_DIR, f) for f in existing_files])
    raise Exception("No BGM files found. Please manually add an mp3 to bg_music/")

# --- VIDEO ASSEMBLY ---
def create_combined_video(news_items, output_path="politics_viral_short.mp4"):
    clips = []
    for i, (text, img_url) in enumerate(news_items):
        img_path = create_image_frame(img_url, i)
        if not img_path: continue
            
        audio_path, vtt_path = asyncio.run(generate_audio_and_subs(text, i))
        audio_clip = AudioFileClip(audio_path).fx(volumex, 0.75) 
        img_clip = ImageClip(img_path).set_duration(audio_clip.duration + 0.5)
        
        subs = create_subtitles(vtt_path, audio_clip)
        video_with_text = CompositeVideoClip([img_clip] + subs).set_audio(audio_clip) if subs else img_clip.set_audio(audio_clip)
        
        if i > 0: video_with_text = video_with_text.crossfadein(0.5)
        clips.append(video_with_text)

    final_video = concatenate_videoclips(clips, method="compose")
    
    try:
        bg_music_path = download_openverse_bgm()
        bgm = AudioFileClip(bg_music_path).fx(volumex, 0.25)
        bgm_loop = audio_loop(bgm, duration=final_video.duration)
        final_video = final_video.set_audio(CompositeAudioClip([final_video.audio, bgm_loop]))
    except Exception as e: print(f"BGM Error: {e}")

    final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac")
    return output_path

def send_to_webhook(video_path, title, hashtag):
    with open(video_path, 'rb') as f:
        payload = {"title": title, "hashtags": hashtag}
        files = {"file": (video_path, f, "video/mp4")}
        response = requests.post(WEBHOOK_URL, data=payload, files=files, timeout=30)
    
    if response.status_code in [200, 204]: return "https://webhook-success-url.com/video.mp4"
    else: raise Exception(f"Webhook Failed: {response.status_code}")

if __name__ == "__main__":
    try:
        history = load_history()
        title = get_random_item_with_cooling(TITLE_FILE, history['titles'], "Title")
        hashtag = get_random_item_with_cooling(HASHTAG_FILE, history['hashtags'], "Hashtag")
        
        news_items = get_latest_news()
        if len(news_items) < 3: raise Exception("Not enough news items found.")
            
        video_file = create_combined_video(news_items)
        if os.path.exists(video_file):
            video_url = send_to_webhook(video_file, title, hashtag)
            save_history(history)
            log_success(video_url, title, hashtag)
            
    except Exception as e:
        log_error(str(e))
