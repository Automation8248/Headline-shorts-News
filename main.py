import os
import random
import requests
import feedparser
import asyncio
import nest_asyncio
import edge_tts
import string
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from io import BytesIO
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips, CompositeAudioClip
from moviepy.audio.fx.all import volumex, audio_loop

nest_asyncio.apply()

# Webhook URL[cite: 1]
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://webhook.site/2e349cff-2239-4307-b676-e6046b3a8fd1") #[cite: 1]
FIXED_AUTHOR = "USA Politics Daily" #[cite: 1]

# 1. ADD MULTIPLE USER AGENTS
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"
]

def get_latest_news():
    """USA Politics ki top 3 latest news aur images fetch karta hai[cite: 1]"""
    rss_url = "https://news.yahoo.com/rss/politics" #[cite: 1]
    feed = feedparser.parse(rss_url) #[cite: 1]
    
    news_list = []
    for entry in feed.entries: #[cite: 1]
        if len(news_list) >= 3: # 3 news filter
            break
            
        title = entry.title #[cite: 1]
        clean_title = title.replace('#', '').replace('*', '').strip() #[cite: 1]
        
        image_url = None #[cite: 1]
        if 'media_content' in entry: #[cite: 1]
            image_url = entry.media_content[0]['url'] #[cite: 1]
        
        if image_url: #[cite: 1]
            news_list.append((clean_title, image_url))
            
    return news_list

# Generate Female Voiceover
async def generate_audio(text, index):
    output_file = f"temp_audio_{index}.mp3"
    # 'en-US-JennyNeural' is a clear female voice
    communicate = edge_tts.Communicate(text, "en-US-JennyNeural")
    await communicate.save(output_file)
    return output_file

def draw_quote_text_centered(draw, text, author, font, canvas_width, canvas_height, max_width=850):
    """Text ko quotes ke sath wrap aur center karta hai[cite: 1]"""
    quote_text = f'"{text}"' #[cite: 1]
    words = quote_text.split() #[cite: 1]
    
    clean_words = [w.translate(str.maketrans('', '', string.punctuation)) for w in words] #[cite: 1]
    longest_words = set(sorted(clean_words, key=len, reverse=True)[:3]) #[cite: 1]
    
    space_width = font.getlength(" ") #[cite: 1]
    lines = [] #[cite: 1]
    current_line = [] #[cite: 1]
    current_line_width = 0 #[cite: 1]
    
    for word in words: #[cite: 1]
        word_clean = word.translate(str.maketrans('', '', string.punctuation)) #[cite: 1]
        is_highlight = word_clean in longest_words #[cite: 1]
        word_width = font.getlength(word) #[cite: 1]
        
        if current_line and current_line_width + space_width + word_width > max_width: #[cite: 1]
            lines.append(current_line) #[cite: 1]
            current_line = [(word, is_highlight)] #[cite: 1]
            current_line_width = word_width #[cite: 1]
        else:
            current_line.append((word, is_highlight)) #[cite: 1]
            if current_line_width == 0: #[cite: 1]
                current_line_width = word_width #[cite: 1]
            else:
                current_line_width += space_width + word_width #[cite: 1]
                
    if current_line: #[cite: 1]
        lines.append(current_line) #[cite: 1]
        
    lines.append([]) #[cite: 1]
    lines.append([(f"- {author}", False)]) #[cite: 1]
    
    font_size = getattr(font, 'size', 80) #[cite: 1]
    line_height = font_size * 1.3 #[cite: 1]
    total_text_height = len(lines) * line_height #[cite: 1]
    
    start_y = (canvas_height - total_text_height) / 2  #[cite: 1]
    
    y = start_y #[cite: 1]
    for line in lines: #[cite: 1]
        if not line: #[cite: 1]
            y += line_height * 0.7  #[cite: 1]
            continue #[cite: 1]
            
        line_width = sum(font.getlength(w) for w, _ in line) + space_width * (len(line) - 1) #[cite: 1]
        x = (canvas_width - line_width) / 2  #[cite: 1]
        
        for word, is_highlight in line: #[cite: 1]
            color = "#FFA500" if is_highlight else "white" #[cite: 1]
            if word.startswith("- "): #[cite: 1]
                color = "#E0E0E0" #[cite: 1]
                
            draw.text((x, y), word, font=font, fill=color) #[cite: 1]
            x += font.getlength(word) + space_width #[cite: 1]
        y += line_height #[cite: 1]

def create_image_frame(text, image_url, index):
    print(f"Downloading image {index + 1}...")
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    response = requests.get(image_url, headers=headers, timeout=10)
    
    if response.status_code != 200:
        return None

    canvas = Image.new("RGB", (1080, 1920), "black") #[cite: 1]
    img = Image.open(BytesIO(response.content)).convert("RGB") #[cite: 1]
    
    target_width = 1080 #[cite: 1]
    target_height = 1920  #[cite: 1]
    
    img_ratio = img.width / img.height #[cite: 1]
    target_ratio = target_width / target_height #[cite: 1]
    
    if img_ratio > target_ratio: #[cite: 1]
        new_width = int(target_ratio * img.height) #[cite: 1]
        offset = (img.width - new_width) // 2 #[cite: 1]
        img = img.crop((offset, 0, offset + new_width, img.height)) #[cite: 1]
    else:
        new_height = int(img.width / target_ratio) #[cite: 1]
        offset = (img.height - new_height) // 2 #[cite: 1]
        img = img.crop((0, offset, img.width, offset + new_height)) #[cite: 1]
        
    img = img.resize((target_width, target_height), Image.Resampling.BILINEAR) #[cite: 1]
    
    enhancer = ImageEnhance.Brightness(img) #[cite: 1]
    img = enhancer.enhance(0.6) #[cite: 1]
    
    canvas.paste(img, (0, 0)) #[cite: 1]
    draw = ImageDraw.Draw(canvas) #[cite: 1]
    
    try:
        font = ImageFont.truetype("arialbd.ttf", 80)  #[cite: 1]
    except IOError:
        font = ImageFont.load_default() #[cite: 1]

    draw_quote_text_centered(draw, text, FIXED_AUTHOR, font, canvas_width=1080, canvas_height=1920, max_width=850) #[cite: 1]
    
    temp_image_path = f"temp_frame_{index}.jpg"
    canvas.save(temp_image_path, quality=85) #[cite: 1]
    return temp_image_path

def create_combined_video(news_items, output_path="politics_viral_short.mp4"):
    clips = []
    full_text_caption = ""
    
    for i, (text, img_url) in enumerate(news_items):
        full_text_caption += f"📰 {text}\n\n"
        
        # 1. Image Generate Karein
        img_path = create_image_frame(text, img_url, i)
        if not img_path:
            continue
            
        # 2. Voice Generate Karein (Female)
        audio_path = asyncio.run(generate_audio(text, i))
        
        # 3. Clip banayein aur transition add karein
        audio_clip = AudioFileClip(audio_path)
        # Audio length se 0.5 seconds extra time de rahe hain taki crossfade smooth ho
        img_clip = ImageClip(img_path).set_duration(audio_clip.duration + 0.5)
        video_clip = img_clip.set_audio(audio_clip)
        
        # Agar ye pehli news nahi hai, toh 0.5 sec ka fade transition lagayein
        if i > 0:
            video_clip = video_clip.crossfadein(0.5)
            
        clips.append(video_clip)

    print("Merging 3 News Clips together...")
    # method="compose" transitions ke liye zaruri hai
    final_video = concatenate_videoclips(clips, method="compose")
    
    # 4. Background Music (BGM) Add Karein
    try:
        # BGM file 'news_bgm.mp3' aapke folder me honi chahiye
        bgm = AudioFileClip("news_bgm.mp3").fx(volumex, 0.1) # Volume 10%
        # BGM ko loop karein pure video ki duration tak
        bgm_loop = audio_loop(bgm, duration=final_video.duration)
        
        # Voiceover aur BGM ko mix karein
        final_audio = CompositeAudioClip([final_video.audio, bgm_loop])
        final_video = final_video.set_audio(final_audio)
        print("BGM applied successfully.")
    except Exception as e:
        print("BGM file 'news_bgm.mp3' not found, proceeding without BGM.")

    # Render Karein
    print("Rendering Final Video...")
    final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac")
    return output_path, full_text_caption

def send_to_webhook(video_path, caption):
    print("Sending to Webhook...[cite: 1]")
    with open(video_path, 'rb') as f: #[cite: 1]
        payload = {"content": f"New Viral Short:\n\n{caption}"} #[cite: 1]
        files = {"file": (video_path, f, "video/mp4")} #[cite: 1]
        response = requests.post(WEBHOOK_URL, data=payload, files=files, timeout=30) #[cite: 1]
        
    if response.status_code in [200, 204]: #[cite: 1]
        print("Success! Video sent.[cite: 1]")
    else:
        print(f"Failed to send. Status: {response.status_code}[cite: 1]")

if __name__ == "__main__":
    print("Fetching News...")
    news_items = get_latest_news()
    
    if len(news_items) > 0:
        print(f"Found {len(news_items)} news items.")
        video_file, caption = create_combined_video(news_items)
        
        if os.path.exists(video_file):
            send_to_webhook(video_file, caption)
            
        # Cleanup temporary files
        for i in range(len(news_items)):
            if os.path.exists(f"temp_frame_{i}.jpg"): os.remove(f"temp_frame_{i}.jpg")
            if os.path.exists(f"temp_audio_{i}.mp3"): os.remove(f"temp_audio_{i}.mp3")
    else:
        print("No valid news with images found.[cite: 1]")
