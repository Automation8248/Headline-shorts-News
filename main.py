import os
import requests
import feedparser
import subprocess
import string
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

# Webhook URL (GitHub Secrets se aayega)
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "YOUR_WEBHOOK_URL_HERE")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_latest_news():
    """USA Politics ki latest news aur image fetch karta hai"""
    rss_url = "https://news.yahoo.com/rss/politics"
    feed = feedparser.parse(rss_url)
    
    for entry in feed.entries:
        title = entry.title
        clean_title = title.replace('#', '').replace('*', '').strip()
        
        image_url = None
        if 'media_content' in entry:
            image_url = entry.media_content[0]['url']
        
        if image_url:
            return clean_title, image_url
            
    return None, None

def draw_colored_text_centered(draw, text, font, canvas_width, top_y, bottom_y):
    """Text ko wrap karke Shorts ke bache hue black box mein vertically center align karta hai"""
    words = text.split()
    
    # Logic: Sabse lambe 3 words nikal lo taaki unko highlight (Orange) kar sakein
    clean_words = [w.translate(str.maketrans('', '', string.punctuation)) for w in words]
    longest_words = set(sorted(clean_words, key=len, reverse=True)[:3])
    
    space_width = font.getlength(" ")
    lines = []
    current_line = []
    current_line_width = 0
    max_line_width = 950 # Side padding ke liye (1080 canvas me margins safe rahenge)
    
    # Text ko lines mein todna (Wrapping)
    for word in words:
        word_clean = word.translate(str.maketrans('', '', string.punctuation))
        is_highlight = word_clean in longest_words
        
        word_width = font.getlength(word)
        if current_line and current_line_width + space_width + word_width > max_line_width:
            lines.append(current_line)
            current_line = [(word, is_highlight)]
            current_line_width = word_width
        else:
            current_line.append((word, is_highlight))
            if current_line_width == 0:
                current_line_width = word_width
            else:
                current_line_width += space_width + word_width
                
    if current_line:
        lines.append(current_line)

    # === DYNAMIC VERTICAL CENTERING LOGIC ===
    # Font height calculate karke usko exact center me place karna
    font_size = getattr(font, 'size', 65)
    line_height = font_size * 1.3
    total_text_height = len(lines) * line_height
    
    available_height = bottom_y - top_y
    # Yahan text automatically box ke beech mein set ho jayega
    start_y = top_y + (available_height - total_text_height) / 2 

    # Ab har line ko horizontally center mein draw karna
    y = start_y
    for line in lines:
        line_width = sum(font.getlength(w) for w, _ in line) + space_width * (len(line) - 1)
        x = (canvas_width - line_width) / 2 # Center X position
        
        for word, is_highlight in line:
            color = "#FFA500" if is_highlight else "white"
            draw.text((x, y), word, font=font, fill=color)
            x += font.getlength(word) + space_width
        y += line_height # Agli line ke liye gap

def create_video_with_ffmpeg(text, image_url):
    print("Downloading image...")
    response = requests.get(image_url, headers=HEADERS)
    
    if response.status_code != 200:
        print("Image download failed!")
        return None

    # 1. Base Canvas banana (1080x1920 - Pura Black Background)
    canvas = Image.new("RGB", (1080, 1920), "black")
    
    # 2. News Image ko load karna
    img = Image.open(BytesIO(response.content)).convert("RGB")
    
    # 3. Image ko Upar ke hisse (Top 70%) ke hisaab se resize karna
    target_width = 1080
    target_height = 1350 # Upar ka hissa image ke liye
    
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
        
    img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
    
    # 4. News image ko black canvas par paste karna (Top par)
    canvas.paste(img, (0, 0))
    
    # 5. Text Draw karna (Neeche wale black hisse mein)
    draw = ImageDraw.Draw(canvas)
    try:
        # Impact ya Arial Bold font ka use karne ki koshish karega
        font = ImageFont.truetype("impact.ttf", 60) # Text width balance ke liye size 65 se thoda 60 kiya
    except IOError:
        try:
            font = ImageFont.truetype("arialbd.ttf", 60)
        except IOError:
            font = ImageFont.load_default()

    # Yahan top_y = 1350 aur bottom_y = 1920 pass kiya gaya hai
    # Taki text in dono limits ke perfectly beech (center) me adjust ho.
    draw_colored_text_centered(draw, text, font, canvas_width=1080, top_y=1350, bottom_y=1920)
    
    temp_image_path = "temp_frame.jpg"
    canvas.save(temp_image_path)
    
    # 6. FFmpeg se 6 second ka video banana
    print("Generating video using FFmpeg...")
    video_path = "politics_short.mp4"
    
    ffmpeg_cmd = [
        "ffmpeg", "-y", 
        "-loop", "1", 
        "-framerate", "24", 
        "-i", temp_image_path,
        "-c:v", "libx264", 
        "-t", "6", 
        "-pix_fmt", "yuv420p", 
        video_path
    ]
    
    try:
        subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("Video generated successfully!")
        return video_path
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg Error: {e.stderr.decode('utf-8')}")
        return None

def send_to_webhook(video_path, text):
    print("Sending to Webhook...")
    with open(video_path, 'rb') as f:
        payload = {"content": f"New Viral Short: {text}"}
        files = {"file": (video_path, f, "video/mp4")}
        response = requests.post(WEBHOOK_URL, data=payload, files=files)
        
    if response.status_code in [200, 204]:
        print("Success! Video sent.")
    else:
        print(f"Failed to send. Status: {response.status_code}")

if __name__ == "__main__":
    news_text, img_url = get_latest_news()
    
    if news_text and img_url:
        print(f"Found News: {news_text}")
        video_file = create_video_with_ffmpeg(news_text, img_url)
        
        if video_file:
            send_to_webhook(video_file, news_text)
    else:
        print("No valid news with image found.")
