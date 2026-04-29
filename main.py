import os
import requests
import feedparser
import textwrap
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip
from io import BytesIO

# Webhook URL (Discord ya Make.com ka Webhook yahan dalein)
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "YOUR_WEBHOOK_URL_HERE")

# Browser headers taaki websites humein bot samajh kar block na karein
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
}

def get_latest_news():
    """USA Politics ki latest news aur image fetch karta hai"""
    # Yahoo News ya CNN ka feed use karna better hai kyuki isme direct images hoti hain
    rss_url = "https://news.yahoo.com/rss/politics"
    feed = feedparser.parse(rss_url)
    
    for entry in feed.entries:
        title = entry.title
        # Text ko clean karna: Koi bhi extra symbols remove karein
        clean_title = title.replace('#', '').replace('*', '').strip()
        
        # Image URL nikalna (RSS feed structure ke hisaab se)
        image_url = None
        if 'media_content' in entry:
            image_url = entry.media_content[0]['url']
        
        if image_url:
            return clean_title, image_url
            
    return None, None

def create_video(text, image_url):
    """Image download karke uspe yellow background aur text lagata hai"""
    print("Downloading image...")
    response = requests.get(image_url, headers=HEADERS)
    
    if response.status_code != 200:
        print("Image download failed!")
        return None

    # Image load aur resize karna (1080x1920 for Shorts)
    img = Image.open(BytesIO(response.content)).convert("RGB")
    
    # Aspect ratio maintain karte hue crop/resize logic
    img_ratio = img.width / img.height
    target_ratio = 1080 / 1920
    
    if img_ratio > target_ratio:
        new_width = int(target_ratio * img.height)
        offset = (img.width - new_width) // 2
        img = img.crop((offset, 0, offset + new_width, img.height))
    else:
        new_height = int(img.width / target_ratio)
        offset = (img.height - new_height) // 2
        img = img.crop((0, offset, img.width, offset + new_height))
        
    img = img.resize((1080, 1920), Image.Resampling.LANCZOS)
    
    # Drawing start
    draw = ImageDraw.Draw(img)
    
    # Font setup (Default font load kar rahe hain, aap custom .ttf file use kar sakte hain)
    try:
        font = ImageFont.truetype("arial.ttf", 60)
    except IOError:
        font = ImageFont.load_default()

    # Text formatting (Text ko multiple lines mein break karna)
    wrapped_text = textwrap.fill(text, width=25)
    
    # Yellow background box coordinates
    box_x1, box_y1 = 50, 150
    box_x2, box_y2 = 1030, 450
    
    # Draw Yellow Box
    draw.rectangle([box_x1, box_y1, box_x2, box_y2], fill="yellow", outline="black", width=3)
    
    # Draw Black Text inside the box
    draw.text((box_x1 + 30, box_y1 + 30), wrapped_text, fill="black", font=font)
    
    # Save temporary image
    temp_image_path = "temp_frame.jpg"
    img.save(temp_image_path)
    
    # Video Generation using MoviePy
    print("Generating video...")
    video_path = "politics_short.mp4"
    clip = ImageClip(temp_image_path).set_duration(6) # 6 seconds ka short
    clip.write_videofile(video_path, fps=24, codec="libx264")
    
    return video_path

def send_to_webhook(video_path, text):
    """Video ko webhook par bhejna"""
    print("Sending to Webhook...")
    with open(video_path, 'rb') as f:
        payload = {"content": f"New Short Generated: {text}"}
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
        video_file = create_video(news_text, img_url)
        
        if video_file:
            send_to_webhook(video_file, news_text)
    else:
        print("No valid news with image found.")
