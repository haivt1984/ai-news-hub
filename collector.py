import os
import json
import time
import feedparser
import requests

# ================= CẤU HÌNH THÔNG TIN =================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AQ.Ab8RN6Kj1xNA69K9pKnN6b8v8bbl63wp3f2u51xZtkafuB2g6Q").strip()
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://lleeibzegmnycuingzgx.supabase.co").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxsZWVpYnplZ21ueWN1aW5nemd4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTAxMjc5OTUsImV4cCI6MjEwNTcwMzk5NX0.KrO8Y8qoKh0NIPYDL6wki7zGb-Lxi1xwWgQrX9xSXxE").strip()
# ======================================================

# Nguồn RSS chuẩn hóa
FEEDS = [
    {"source": "VnExpress Sức Khỏe", "url": "https://vnexpress.net/rss/suc-khoe.rss"},
    {"source": "Tuổi Trẻ Sức Khỏe", "url": "https://tuoitre.vn/rss/suc-khoe.rss"},
    {"source": "Thanh Niên Sức Khỏe", "url": "https://thanhnien.vn/rss/suc-khoe.rss"},
    {"source": "Dân Trí Sức Khỏe", "url": "https://dantri.com.vn/rss/suc-khoe.rss"},
    {"source": "VietnamNet Sức Khỏe", "url": "https://vietnamnet.vn/rss/suc-khoe.rss"}
]

ARTICLES_PER_FEED = 3

# Đưa trực tiếp API Key vào tham số URL để tránh lỗi Header 401
GEMINI_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={GEMINI_API_KEY}"

SUPABASE_ENDPOINT = f"{SUPABASE_URL}/rest/v1/articles"
SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def is_article_exists(url):
    try:
        check_url = f"{SUPABASE_ENDPOINT}?original_url=eq.{requests.utils.quote(url)}&select=id"
        res = requests.get(check_url, headers=SUPABASE_HEADERS, timeout=10)
        if res.status_code == 200 and len(res.json()) > 0:
            return True
    except Exception:
        pass
    return False

def call_gemini(payload, max_retries=4):
    for attempt in range(max_retries):
        res = requests.post(GEMINI_ENDPOINT, json=payload)
        if res.status_code == 200:
            return res.json()
        elif res.status_code == 429:
            wait_time = 25 + (attempt * 10)
            print(f"      [!] Rate limit Google (429). Tam nghi {wait_time}s...")
            time.sleep(wait_time)
        elif res.status_code == 503:
            time.sleep((attempt + 1) * 5)
        else:
            res.raise_for_status()
    raise Exception("Loi ket noi Gemini API.")

for feed_info in FEEDS:
    source_name = feed_info["source"]
    print(f"\n==================================================")
    print(f"[*] Dang quet: {source_name}")

    try:
        raw_xml = requests.get(feed_info["url"], headers=REQUEST_HEADERS, timeout=15).content
        parsed_feed = feedparser.parse(raw_xml)
    except Exception as e:
        print(f"    [x] Khong the tai RSS {source_name}: {e}")
        continue

    entries = parsed_feed.entries[:ARTICLES_PER_FEED]
    print(f"    Tim thay {len(parsed_feed.entries)} bai. Xu ly {len(entries)} bai:")

    for entry in entries:
        original_title = entry.title
        original_url = entry.link
        description = entry.description if hasattr(entry, 'description') else entry.get('summary', '')

        if is_article_exists(original_url):
            print(f"    [-] Da co trong DB: {original_title[:45]}...")
            continue

        prompt = f"""
        Ban la chuyen gia bien tap tap chi ve Suc khoe, Dinh duong va Am thuc doi song.
        Hay doc bai bao sau va bien tap thanh ban tin tinh gon, thuc te theo dinh dang JSON:

        Nguon: {source_name}
        Tieu de goc: {original_title}
        Noi dung mo ta: {description}

        Yeu cau JSON:
        {{
          "title": "Tieu de giat tit hap dan, trang nha, danh dung tam ly nguoi doc",
          "summary": "Tom tat tu 2-3 cau ve kien thuc y khoa, dinh duong hoac net doc dao am thuc",
          "tips": "Loi khuyen suc khoe thuc chien, meo an uong, cong thuc che bien hoac luu y phong benh",
          "category": "Chon 1 trong cac nhan: Dinh duong, Am thuc, Y hoc doi song, Meo suc khoe, Mon ngon"
        }}
        """

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.3
            }
        }

        try:
            ai_data = call_gemini(payload)
            raw_text = ai_data["candidates"][0]["content"]["parts"][0]["text"]
            parsed_data = json.loads(raw_text)

            record = {
                "title": parsed_data.get("title", original_title),
                "summary": parsed_data.get("summary", ""),
                "tips": parsed_data.get("tips", ""),
                "category": parsed_data.get("category", "Đời sống"),
                "original_url": original_url
            }

            db_res = requests.post(SUPABASE_ENDPOINT, headers=SUPABASE_HEADERS, json=record)
            if db_res.status_code in [200, 201]:
                print(f"    [+] Luu thanh cong: {record['title'][:50]}...")
            else:
                print(f"    [x] Loi Supabase: {db_res.status_code}")

        except Exception as e:
            print(f"    [x] Bo qua bai do loi: {e}")

        time.sleep(6)

print("\nHoan tat quet tin Am thuc & Suc khoe!")
