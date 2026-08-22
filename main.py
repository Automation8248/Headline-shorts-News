import os
import random
import requests
import feedparser
import asyncio
import nest_asyncio
import edge_tts
import json
import uuid
import numpy as np
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from io import BytesIO
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips, CompositeAudioClip, CompositeVideoClip, ColorClip
from moviepy.audio.fx.all import volumex, audio_loop

nest_asyncio.apply()

# --- CONFIGURATION (STRICTLY FROM SECRETS) ---
try:
    WEBHOOK_URL = os.environ["WEBHOOK_URL"]
    SUCCESS_TELEGRAM_TOKEN = os.environ["SUCCESS_TELEGRAM_TOKEN"]
    ERROR_TELEGRAM_TOKEN = os.environ["ERROR_TELEGRAM_TOKEN"]
    TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
except KeyError as e:
    raise RuntimeError(f"Missing required environment variable in Secrets: {e}")

AUTOMATION_NAME = "USA_Politics_Daily_Bot"
SOCIAL_MEDIA = "Multi-Server Shorts"

# --- DIRECTORIES ---
METADATA_DIR = "metadata"
BGM_DIR = "bg_music"
os.makedirs(METADATA_DIR, exist_ok=True)
os.makedirs(BGM_DIR, exist_ok=True)

HASHTAG_FILE = os.path.join(METADATA_DIR, "hastag.txt")
TITLE_FILE = os.path.join(METADATA_DIR, "title.txt")
HISTORY_FILE = os.path.join(METADATA_DIR, "history.json")
COOLING_DAYS = 30

# --- 50+ USER AGENTS ---
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:119.0) Gecko/20100101 Firefox/119.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:118.0) Gecko/20100101 Firefox/118.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:119.0) Gecko/20100101 Firefox/119.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:119.0) Gecko/20100101 Firefox/119.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_8 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 16_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-A546B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 11; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 11_6_8) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.6.6 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_7_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_2) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/105.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 OPR/104.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/105.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/105.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Vivaldi/6.4.3160.47",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Vivaldi/6.4.3160.47",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Vivaldi/6.4.3160.47",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 YaBrowser/23.11.0.0 Yowser/2.5 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 YaBrowser/23.11.0.0 Yowser/2.5 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) FxiOS/120.0 Mobile/15E148 Safari/605.1.15",
    "Mozilla/5.0 (iPad; CPU OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) FxiOS/120.0 Mobile/15E148 Safari/605.1.15",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36 EdgA/120.0.0.0"
]

# --- TELEGRAM LOGGING ---
def send_telegram_msg(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
    try: requests.post(url, data=payload)
    except Exception as e: print(f"Telegram failed: {e}")

def log_success(video_url, title, hashtag):
    msg = f"✅ <b>Success</b>\n<b>Bot:</b> {AUTOMATION_NAME}\n<b>Platform:</b> {SOCIAL_MEDIA}\n<b>Title:</b> {title}\n<b>Hashtags:</b> {hashtag}\n<b>Video URL:</b> {video_url}"
    send_telegram_msg(SUCCESS_TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)

def log_error(error_msg):
    msg = f"❌ <b>Error</b>\n<b>Bot:</b> {AUTOMATION_NAME}\n<b>Platform:</b> {SOCIAL_MEDIA}\n<b>Error Details:</b> {error_msg}"
    send_telegram_msg(ERROR_TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)

# --- METADATA & COOLING LOGIC ---
def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            try: return json.load(f)
            except: return {"titles": {}, "hashtags": {}}
    return {"titles": {}, "hashtags": {}}

def save_history(history):
    with open(HISTORY_FILE, 'w') as f: json.dump(history, f)

def get_random_item_with_cooling(filepath, history_dict, item_type):
    if not os.path.exists(filepath):
        with open(filepath, 'w') as f: f.write(f"Dummy {item_type} Line 1\nDummy {item_type} Line 2\n")
    with open(filepath, 'r') as f: items = [line.strip() for line in f.readlines() if line.strip()]
    if not items: return "Default Item"
    
    now = datetime.now()
    available_items = []
    for item in items:
        last_used_str = history_dict.get(item)
        if last_used_str:
            if (now - datetime.fromisoformat(last_used_str)).days > COOLING_DAYS:
                available_items.append(item)
        else: available_items.append(item)
            
    if not available_items: available_items = items
    selected = random.choice(available_items)
    history_dict[selected] = now.isoformat()
    return selected

# --- LOCAL BACKGROUND MUSIC LOGIC ---
def get_random_bgm():
    """Sirf local 'bg_music' folder se MP3 select karega. Koi download nahi."""
    files = [f for f in os.listdir(BGM_DIR) if f.endswith('.mp3')]
    if not files: 
        raise Exception("❌ bg_music folder khali hai! Kripya manually apni MP3 files add karein.")
    return os.path.join(BGM_DIR, random.choice(files))

# --- AUDIO & EXACT TIMED SUBTITLES (PIL + NUMPY LOGIC) ---
async def generate_audio_and_subs(text, index):
    audio_file = f"temp_audio_{index}.mp3"
    communicate = edge_tts.Communicate(text, "en-US-AriaNeural")
    subs_data = [] 
    with open(audio_file, "wb") as file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio": file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                subs_data.append({
                    "start": chunk["offset"] / 10_000_000.0,
                    "end": (chunk["offset"] + chunk["duration"]) / 10_000_000.0,
                    "text": chunk["text"]
                })
    return audio_file, subs_data

def create_caption_clips(subs_data, max_width=900):
    """
    Uses PIL to draw text exactly as requested, bypassing ImageMagick.
    Groups words into chunks of 3 and exact aligns them with TTS audio timing.
    """
    try:
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 75)
    except IOError:
        try:
            font = ImageFont.truetype("arialbd.ttf", 75)
        except IOError:
            font = ImageFont.load_default()

    chunk_size = 3
    chunks_data = []
    
    for i in range(0, len(subs_data), chunk_size):
        chunk = subs_data[i:i+chunk_size]
        combined_text = " ".join([w["text"] for w in chunk])
        start_t = chunk[0]["start"]
        end_t = chunk[-1]["end"]
        chunks_data.append({"text": combined_text, "start": start_t, "end": end_t})
        
    clips = []
    colors = ['white', 'yellow']
    
    for i, chunk in enumerate(chunks_data):
        img = Image.new('RGBA', (max_width, 150), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        try:
            bbox = draw.textbbox((0, 0), chunk["text"], font=font)
            w = bbox[2] - bbox[0]
        except AttributeError:
            w, h = draw.textsize(chunk["text"], font=font)
            
        x, y = (max_width - w) / 2, 20
        
        stroke = 4
        for dx in [-stroke, 0, stroke]:
            for dy in [-stroke, 0, stroke]:
                draw.text((x+dx, y+dy), chunk["text"], font=font, fill='black')
                
        current_color = colors[i % 2]
        draw.text((x, y), chunk["text"], font=font, fill=current_color)
        
        img_np = np.array(img)
        chunk_duration = chunk["end"] - chunk["start"]
        
        txt_clip = ImageClip(img_np[:, :, :3]).set_duration(chunk_duration)
        mask = ImageClip(img_np[:, :, 3] / 255.0, ismask=True).set_duration(chunk_duration)
        
        txt_clip = txt_clip.set_mask(mask).set_position(('center', 1400)).set_start(chunk["start"])
        clips.append(txt_clip)
        
    return clips

# --- IMAGE & NEWS ---
def get_latest_news():
    feed = feedparser.parse("https://news.yahoo.com/rss/politics")
    news_list = []
    for entry in feed.entries:
        if len(news_list) >= 3: break
        title = entry.title.replace('#', '').replace('*', '').strip()
        img = entry.media_content[0]['url'] if 'media_content' in entry else None
        if img: news_list.append((title, img))
    return news_list

def create_square_image_clip(image_url, duration):
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    response = requests.get(image_url, headers=headers, timeout=10)
    if response.status_code != 200: return None

    img = Image.open(BytesIO(response.content)).convert("RGB")
    size = min(img.width, img.height)
    offset_x = (img.width - size) // 2
    offset_y = (img.height - size) // 2
    img = img.crop((offset_x, offset_y, offset_x + size, offset_y + size))
    img = img.resize((1000, 1000), Image.Resampling.BILINEAR)
    
    img_path = f"temp_sq_{uuid.uuid4().hex[:4]}.jpg"
    img.save(img_path, quality=90)
    
    bg = ColorClip(size=(1080, 1920), color=(0,0,0)).set_duration(duration)
    img_clip = ImageClip(img_path).set_duration(duration).set_position("center")
    
    return CompositeVideoClip([bg, img_clip])

# --- VIDEO ASSEMBLY ---
def create_combined_video(news_items, output_path="politics_viral_short.mp4"):
    clips = []
    for i, (text, img_url) in enumerate(news_items):
        audio_path, subs_data = asyncio.run(generate_audio_and_subs(text, i))
        audio_clip = AudioFileClip(audio_path).fx(volumex, 0.75) 
        
        video_with_img = create_square_image_clip(img_url, audio_clip.duration + 0.5)
        if not video_with_img: continue
        
        subs = create_caption_clips(subs_data, 900)
        
        if subs:
            video_with_text = CompositeVideoClip([video_with_img] + subs).set_audio(audio_clip)
        else:
            video_with_text = video_with_img.set_audio(audio_clip)
            
        if i > 0: video_with_text = video_with_text.crossfadein(0.5)
        clips.append(video_with_text)

    final_video = concatenate_videoclips(clips, method="compose")
    
    # --- BGM Application (Random Start, Cut & Loop Logic) ---
    # --- BGM Application (Start from 0s, Cut & Loop Logic) ---
    try:
        bg_music_path = get_random_bgm()
        bgm = AudioFileClip(bg_music_path)
        
        # Volume set karo (25%)
        bgm = bgm.fx(volumex, 0.45)
        
        # audio_loop automatically 0 seconds se shuru karega aur video length tak cut/repeat karega
        bgm_looped = audio_loop(bgm, duration=final_video.duration)
        
        # Voiceover aur BGM ko mix karo
        final_mixed_audio = CompositeAudioClip([final_video.audio, bgm_looped])
        final_video = final_video.set_audio(final_mixed_audio)
        
    except Exception as e: 
        print(f"BGM mixing failed: {e}")

    final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac")
    return output_path

# --- MULTI-SERVER FILE UPLOAD FALLBACK LOGIC ---
def send_to_fallback_servers(video_path):
    UPLOAD_SERVERS = [
        {"name": "Catbox", "url": "https://catbox.moe/user/api.php", "data": {"reqtype": "fileupload"}, "file_field": "fileToUpload"},
        {"name": "Litterbox", "url": "https://litterbox.catbox.moe/resources/internals/api.php", "data": {"reqtype": "fileupload", "time": "72h"}, "file_field": "fileToUpload"},
        {"name": "0x0.st", "url": "https://0x0.st", "data": {}, "file_field": "file"},
        {"name": "Uguu", "url": "https://uguu.se/upload.php", "data": {}, "file_field": "files[]"},
        {"name": "GoFile", "url": "https://store1.gofile.io/uploadFile", "data": {}, "file_field": "file"},
        {"name": "Buzzheavier", "url": "https://buzzheavier.com/api/upload", "data": {}, "file_field": "file"},
        {"name": "Fileditch", "url": "https://up1.fileditch.com/upload.php", "data": {}, "file_field": "files[]"},
        {"name": "storage.to", "url": "https://storage.to/api/upload", "data": {}, "file_field": "file"},
        {"name": "qu.ax", "url": "https://qu.ax/upload.php", "data": {}, "file_field": "files[]"},
        {"name": "Oshi.at", "url": "https://oshi.at", "data": {}, "file_field": "f"},
        {"name": "hostb", "url": "https://hostb.org/api/upload", "data": {}, "file_field": "file"},
        {"name": "JuiceBox", "url": "https://juicebox.net/api/upload", "data": {}, "file_field": "file"},
        {"name": "Streamable", "url": "https://api.streamable.com/upload", "data": {}, "file_field": "file"},
        {"name": "Sendvid", "url": "https://sendvid.com/api/upload", "data": {}, "file_field": "file"},
        {"name": "UploadFiles.io", "url": "https://up.uploadfiles.io/upload", "data": {}, "file_field": "file"},
        {"name": "Upload.ee", "url": "https://www.upload.ee/api/upload", "data": {}, "file_field": "file"},
        {"name": "FileMirage", "url": "https://filemirage.com/api/upload", "data": {}, "file_field": "file"},
        {"name": "FilePort", "url": "https://fileport.io/api/upload", "data": {}, "file_field": "file"},
        {"name": "FileShot", "url": "https://fileshot.net/api/upload", "data": {}, "file_field": "file"},
        {"name": "PixVid", "url": "https://pixvid.org/api/upload", "data": {}, "file_field": "file"}
    ]

    for server in UPLOAD_SERVERS:
        print(f"Trying to upload to {server['name']}...")
        try:
            with open(video_path, 'rb') as f:
                headers = {"User-Agent": random.choice(USER_AGENTS)}
                files = {server['file_field']: f}
                response = requests.post(server['url'], data=server['data'], files=files, headers=headers, timeout=60)
            
            if response.status_code in [200, 201]:
                try: 
                    link = response.json().get("data", {}).get("downloadPage", response.text.strip())
                except json.JSONDecodeError: 
                    link = response.text.strip()
                
                if link.startswith("http"):
                    print(f"Upload successful on {server['name']}: {link}")
                    return link
            print(f"{server['name']} failed with status {response.status_code}. Trying next...")
        except Exception as e:
            print(f"{server['name']} upload error: {e}. Trying next...")

    raise Exception("All 20 file upload servers failed.")

def post_to_webhook(title, hashtag, video_url):
    payload = {"title": title, "hashtags": hashtag, "video_url": video_url}
    response = requests.post(WEBHOOK_URL, json=payload, timeout=30)
    if response.status_code not in [200, 204]:
        raise Exception(f"Webhook failed with status {response.status_code}")

if __name__ == "__main__":
    try:
        history = load_history()
        title = get_random_item_with_cooling(TITLE_FILE, history['titles'], "Title")
        hashtag = get_random_item_with_cooling(HASHTAG_FILE, history['hashtags'], "Hashtag")
        
        news_items = get_latest_news()
        if len(news_items) < 3: 
            raise Exception("Not enough news items found.")
            
        video_file = create_combined_video(news_items)
        if os.path.exists(video_file):
            uploaded_link = send_to_fallback_servers(video_file)
            post_to_webhook(title, hashtag, uploaded_link)
            
            save_history(history)
            log_success(uploaded_link, title, hashtag)
            
    except Exception as e:
        log_error(str(e))
