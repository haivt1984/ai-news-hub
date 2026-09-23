import os
import json
import time
import feedparser
import requests

# Tự động lấy từ biến môi trường của GitHub Actions, nếu chạy ở máy local thì lấy giá trị mặc định
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AQ.Ab8RN6Kj1xNA69K9pKnN6b8v8bbl63wp3f2u51xZtkafuB2g6Q")
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://lleeibzegmnycuingzgx.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxsZWVpYnplZ21ueWN1aW5nemd4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTAxMjc5OTUsImV4cCI6MjEwNTcwMzk5NX0.KrO8Y8qoKh0NIPYDL6wki7zGb-Lxi1xwWgQrX9xSXxE")

FEEDS = [
    {"source": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/"},
    {"source": "The Verge AI", "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"},
    {"source": "MIT Tech Review", "url": "https://www.technologyreview.com/feed/"},
    {"source": "Wired AI", "url": "https://www.wired.com/feed/tag/ai/latest/rss"},
    {"source": "Microsoft AI", "url": "https://blogs.microsoft.com/ai/feed/"}
]

ARTICLES_PER_FEED = 3

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

# Giả lập trình duyệt để tránh bị chặn RSS
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
        res = requests.post(GEMINI_ENDPOINT, headers=GEMINI_HEADERS, json=payload)
        if res.status_code == 200:
            return res.json()
        elif res.status_code == 429:
            # Nghẽn Rate Limit: Chờ 25s để Google xả giới hạn
            wait_time = 25 + (attempt * 10)
            print(f"      [!] Vuot han muc Google (429). Tam nghi {wait_time}s roi chay tiep...")
            time.sleep(wait_time)
        elif res.status_code == 503:
            wait_time = (attempt + 1) * 5
            print(f"      [!] May chu ban (503). Thu lai sau {wait_time}s...")
            time.sleep(wait_time)
        else:
            res.raise_for_status()
    raise Exception("Khong the hoan tat sau cac luot retry.")

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
            print(f"    [-] Da luu truoc do: {original_title[:45]}...")
            continue

        prompt = f"""
        Ban la bien tap vien cong nghe AI. Hay doc noi dung va tom tat thanh ban tin tieng Viet chuan JSON:
        Nguon: {source_name}
        Tieu de: {original_title}
        Mo ta: {description}

        Dinh dang JSON:
        {{
          "title": "Tieu de tieng Viet ngan gon, hap dan",
          "summary": "Tom tat tu 2 den 3 cau de hieu",
          "tips": "Mot meo ung dung hoac nhan dinh thuc te",
          "category": "Chon 1 trong: LLM, Coding, Business, Robot, Cong cu moi"
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
                "category": parsed_data.get("category", "Tin tức chung"),
                "original_url": original_url
            }

            db_res = requests.post(SUPABASE_ENDPOINT, headers=SUPABASE_HEADERS, json=record)
            if db_res.status_code in [200, 201]:
                print(f"    [+] Da luu: {record['title'][:50]}...")
            else:
                print(f"    [x] Loi Supabase: {db_res.status_code}")

        except Exception as e:
            print(f"    [x] Bo qua bai do loi: {e}")

        # Nghi 8 giay giua cac bai de an toan han muc
        time.sleep(8)

print("\nHoan tat toan bo tien trinh!")
