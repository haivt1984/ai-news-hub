import os
import json
import time
import feedparser
import requests
import sys

# Đảm bảo in log trực tiếp lên GitHub Actions
sys.stdout.reconfigure(line_buffering=True)

# ================= CẤU HÌNH THÔNG TIN =================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AQ.Ab8RN6IhpENXaokc_b-nEkmHEA_hGRyA0-6WXSdPY7XCWhaQJA").strip()
RAW_SUPABASE_URL = os.getenv("SUPABASE_URL", "https://lleeibzegmnycuingzgx.supabase.co").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxsZWVpYnplZ21ueWN1aW5nemd4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTAxMjc5OTUsImV4cCI6MjEwNTcwMzk5NX0.KrO8Y8qoKh0NIPYDL6wki7zGb-Lxi1xwWgQrX9xSXxE").strip()

# Đảm bảo SUPABASE_URL luôn có https://
if not RAW_SUPABASE_URL.startswith("http://") and not RAW_SUPABASE_URL.startswith("https://"):
    SUPABASE_URL = f"https://{RAW_SUPABASE_URL}"
else:
    SUPABASE_URL = RAW_SUPABASE_URL
# ======================================================

FEEDS = [
    {"source": "VnExpress Sức Khỏe", "url": "https://vnexpress.net/rss/suc-khoe.rss"},
    {"source": "Tuổi Trẻ Sức Khỏe", "url": "https://tuoitre.vn/rss/suc-khoe.rss"},
    {"source": "Thanh Niên Sức Khỏe", "url": "https://thanhnien.vn/rss/suc-khoe.rss"},
    {"source": "Dân Trí Sức Khỏe", "url": "https://dantri.com.vn/rss/suc-khoe.rss"},
    {"source": "VietnamNet Sức Khỏe", "url": "https://vietnamnet.vn/rss/suc-khoe.rss"}
]

ARTICLES_PER_FEED = 2

# Đổi lại model chuẩn gemini-3.6-flash (hoặc fallback sang gemini-1.5-flash)
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent"
GEMINI_HEADERS = {
    "Content-Type": "application/json",
    "x-goog-api-key": GEMINI_API_KEY
}

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
        res = requests.get(check_url, headers=SUPABASE_HEADERS, timeout=8)
        if res.status_code == 200 and len(res.json()) > 0:
            return True
    except Exception as e:
        print(f"      [!] Khong kiem tra duoc trung lap: {e}")
    return False

def call_gemini(payload, max_retries=3):
    for attempt in range(max_retries):
        try:
            res = requests.post(GEMINI_ENDPOINT, headers=GEMINI_HEADERS, json=payload, timeout=30)
            if res.status_code == 200:
                return res.json()
            elif res.status_code == 429:
                wait_time = 15 + (attempt * 10)
                print(f"      [!] Rate limit (429), cho {wait_time}s...")
                time.sleep(wait_time)
            elif res.status_code == 404:
                # Nếu model 3.6-flash báo 404, tự động đổi sang 1.5-flash để chạy ngay
                alt_endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
                alt_res = requests.post(alt_endpoint, headers=GEMINI_HEADERS, json=payload, timeout=30)
                if alt_res.status_code == 200:
                    return alt_res.json()
                print(f"      [!] HTTP 404 ca 2 model: {res.text[:80]}")
                time.sleep(5)
            else:
                print(f"      [!] HTTP {res.status_code}: {res.text[:100]}")
                time.sleep(5)
        except requests.exceptions.Timeout:
            print(f"      [!] Gemini timeout sau 30s. Thu lai...")
            time.sleep(5)
        except Exception as err:
            time.sleep(5)
            
    raise Exception("Vuot qua so lan thu goi Gemini.")

print("=== BAT DAU TIEN TRINH THU THAP AM THUC & SUC KHOE ===")

for feed_info in FEEDS:
    source_name = feed_info["source"]
    print(f"\n[*] Dang quet: {source_name}")

    try:
        raw_xml = requests.get(feed_info["url"], headers=REQUEST_HEADERS, timeout=10).content
        parsed_feed = feedparser.parse(raw_xml)
    except Exception as e:
        print(f"    [x] Khong tai duoc RSS {source_name}: {e}")
        continue

    entries = parsed_feed.entries[:ARTICLES_PER_FEED]
    print(f"    Tim thay {len(parsed_feed.entries)} bai. Tien hanh xu ly {len(entries)} bai moi nhat:")

    for entry in entries:
        original_title = entry.title
        original_url = entry.link
        description = entry.description if hasattr(entry, 'description') else entry.get('summary', '')

        if is_article_exists(original_url):
            print(f"    [-] Da ton tai: {original_title[:40]}...")
            continue

        print(f"    -> Dang xu ly: {original_title[:45]}...")

        prompt = f"""
        Ban la bien tap vien ve Dinh duong, Am thuc va Suc khoe.
        Hay tom tat bai bao sau va tra ve DUY NHAT dinh dang JSON:

        Nguon: {source_name}
        Tieu de: {original_title}
        Noi dung: {description}

        Dinh dang JSON:
        {{
          "title": "Tieu de hap dan, chuan suc khoe/am thuc",
          "summary": "Tom tat 2-3 cau ve loi ich hoac kien thuc",
          "tips": "1 loi khuyen/meo thuc te de ap dung ngay",
          "category": "Dinh duong | Am thuc | Y hoc doi song | Meo suc khoe | Mon ngon"
        }}
        """

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.2
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
                "category": parsed_data.get("category", "Sức khỏe"),
                "original_url": original_url
            }

            db_res = requests.post(SUPABASE_ENDPOINT, headers=SUPABASE_HEADERS, json=record, timeout=10)
            if db_res.status_code in [200, 201]:
                print(f"       ✔ Da nap thanh cong vao website!")
            else:
                print(f"       ✖ Loi Supabase: {db_res.status_code} - {db_res.text}")

        except Exception as e:
            print(f"       ✖ Bo qua bai: {e}")

        time.sleep(3)

print("\n=== HOAN TAT! WEBSITE DA SAN SANG XEM TIN ===")
