import os
import requests
import feedparser
import subprocess
import string
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from io import BytesIO

# Webhook URL (GitHub Secrets se aayega)
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://webhook.site/2e349cff-2239-4307-b676-e6046b3a8fd1")
FIXED_AUTHOR = "USA Politics Daily"

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

def draw_quote_text_centered(draw, text, author, font, canvas_width, canvas_height, max_width=850):
    """Text ko quotes ke sath MoviePy jaisa 850px pe wrap aur center karta hai"""
    # MoviePy format logic: "Quote"
    quote_text = f'"{text}"'
    words = quote_text.split()
    
    clean_words = [w.translate(str.maketrans('', '', string.punctuation)) for w in words]
    longest_words = set(sorted(clean_words, key=len, reverse=True)[:3])
    
    space_width = font.getlength(" ")
    lines = []
    current_line = []
    current_line_width = 0
    
    # Text wrapping logic (Max width 850)
    for word in words:
        word_clean = word.translate(str.maketrans('', '', string.punctuation))
        is_highlight = word_clean in longest_words
        word_width = font.getlength(word)
        
        if current_line and current_line_width + space_width + word_width > max_width:
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
        
    # Niche 2 line ka gap aur Author name add karna (MoviePy \n\n logic)
    lines.append([]) # Khaali line
    lines.append([(f"- {author}", False)]) # Author name
    
    # Pure text ki total height nikalna aur screen ke center mein set karna
    font_size = getattr(font, 'size', 80)
    line_height = font_size * 1.3
    total_text_height = len(lines) * line_height
    
    start_y = (canvas_height - total_text_height) / 2 
    
    y = start_y
    for line in lines:
        if not line:
            y += line_height * 0.7 # Quotes aur Author ke beech thoda gap
            continue
            
        line_width = sum(font.getlength(w) for w, _ in line) + space_width * (len(line) - 1)
        x = (canvas_width - line_width) / 2 
        
        for word, is_highlight in line:
            color = "#FFA500" if is_highlight else "white"
            # Author text ko halka grey kar diya taaki professional lage
            if word.startswith("- "):
                color = "#E0E0E0"
                
            draw.text((x, y), word, font=font, fill=color)
            x += font.getlength(word) + space_width
        y += line_height

def create_video_with_ffmpeg(text, image_url):
    print("Downloading image...")
    response = requests.get(image_url, headers=HEADERS, timeout=10)
    
    if response.status_code != 200:
        print("Image download failed!")
        return None

    # 1. Base Canvas banana (1080x1920)
    canvas = Image.new("RGB", (1080, 1920), "black")
    img = Image.open(BytesIO(response.content)).convert("RGB")
    
    # 2. Image ko FULL SCREEN (1080x1920) ke hisaab se resize aur crop karna
    target_width = 1080
    target_height = 1920 
    
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
    
    # 3. Image ko 60% dark karna (Aapke MoviePy ke "image * 0.6" jaisa)
    enhancer = ImageEnhance.Brightness(img)
    img = enhancer.enhance(0.6)
    
    # 4. Canvas par paste karna
    canvas.paste(img, (0, 0))
    
    # 5. Text Draw karna
    draw = ImageDraw.Draw(canvas)
    try:
        # MoviePy wale logic ke hisaab se Arial-Bold aur size 80
        font = ImageFont.truetype("arialbd.ttf", 80) 
    except IOError:
        font = ImageFont.load_default()

    # Text ko max 850px width dekar pure 1920 screen ke center mein draw karna
    draw_quote_text_centered(draw, text, FIXED_AUTHOR, font, canvas_width=1080, canvas_height=1920, max_width=850)
    
    temp_image_path = "temp_frame.jpg"
    canvas.save(temp_image_path, quality=85)
    
    # 6. FFmpeg se 6 second ka video banana (Fast Mode barkarar)
    print("Generating video using FFmpeg (Fast Mode)...")
    video_path = "politics_short.mp4"
    
    ffmpeg_cmd = [
        "ffmpeg", "-y", 
        "-loop", "1", 
        "-framerate", "24", 
        "-i", temp_image_path,
        "-c:v", "libx264", 
        "-preset", "ultrafast",  
        "-tune", "stillimage",   
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
        response = requests.post(WEBHOOK_URL, data=payload, files=files, timeout=30)
        
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
