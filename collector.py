import os
import json
import time
import feedparser
import requests
import sys

# Bật in log tức thì trên console GitHub Actions
sys.stdout.reconfigure(line_buffering=True)

# ================= CẤU HÌNH THÔNG TIN =================
RAW_KEY = os.getenv("GEMINI_API_KEY", "AQ.Ab8RN6KYtas-QV6fRTan1ggI_xUbns8DZCpyp3_kLGs2W58CEg")
GEMINI_API_KEY = RAW_KEY.strip("[]'\" \t\n\r")

RAW_SUPABASE = os.getenv("SUPABASE_URL", "https://lleeibzegmnycuingzgx.supabase.co").strip("[]'\" \t\n\r")
if not RAW_SUPABASE.startswith("http"):
    SUPABASE_URL = f"https://{RAW_SUPABASE}"
else:
    SUPABASE_URL = RAW_SUPABASE

SUPABASE_KEY = os.getenv(
    "SUPABASE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxsZWVpYnplZ21ueWN1aW5nemd4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTAxMjc5OTUsImV4cCI6MjEwNTcwMzk5NX0.KrO8Y8qoKh0NIPYDL6wki7zGb-Lxi1xwWgQrX9xSXxE"
).strip("[]'\" \t\n\r")
# ======================================================

FEEDS = [
    {"source": "VnExpress Sức Khỏe", "url": "https://vnexpress.net/rss/suc-khoe.rss"},
    {"source": "Tuổi Trẻ Sức Khỏe", "url": "https://tuoitre.vn/rss/suc-khoe.rss"},
    {"source": "Thanh Niên Sức Khỏe", "url": "https://thanhnien.vn/rss/suc-khoe.rss"},
    {"source": "Dân Trí Sức Khỏe", "url": "https://dantri.com.vn/rss/suc-khoe.rss"},
    {"source": "VietnamNet Sức Khỏe", "url": "https://vietnamnet.vn/rss/suc-khoe.rss"}
]

ARTICLES_PER_FEED = 2

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
GEMINI_HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {GEMINI_API_KEY}",
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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def is_article_exists(url):
    try:
        check_url = f"{SUPABASE_ENDPOINT}?original_url=eq.{requests.utils.quote(url)}&select=id"
        res = requests.get(check_url, headers=SUPABASE_HEADERS, timeout=8)
        if res.status_code == 200 and len(res.json()) > 0:
            return True
    except Exception as e:
        print(f"      [!] Kiểm tra trùng lặp thất bại: {e}")
    return False

def call_gemini(payload, max_retries=3):
    for attempt in range(max_retries):
        try:
            res = requests.post(GEMINI_ENDPOINT, headers=GEMINI_HEADERS, json=payload, timeout=30)
            if res.status_code == 200:
                return res.json()
            elif res.status_code == 429:
                print(f"      [!] Nghẽn rate limit (429), đợi 15s...")
                time.sleep(15)
            else:
                print(f"      [!] HTTP {res.status_code}: {res.text[:120]}")
                time.sleep(5)
        except requests.exceptions.Timeout:
            print(f"      [!] Quá thời gian 30s...")
            time.sleep(5)
        except Exception:
            time.sleep(5)
            
    raise Exception("Không thể kết nối tới Gemini.")

print("=== BẮT ĐẦU TIẾN TRÌNH THU THẬP ẨM THỰC & SỨC KHỎE ===")

for feed_info in FEEDS:
    source_name = feed_info["source"]
    print(f"\n[*] Đang quét: {source_name}")

    try:
        raw_xml = requests.get(feed_info["url"], headers=REQUEST_HEADERS, timeout=10).content
        parsed_feed = feedparser.parse(raw_xml)
    except Exception as e:
        print(f"    [x] Không thể tải RSS {source_name}: {e}")
        continue

    entries = parsed_feed.entries[:ARTICLES_PER_FEED]
    print(f"    Tìm thấy {len(parsed_feed.entries)} bài. Xử lý {len(entries)} bài:")

    for entry in entries:
        original_title = entry.title
        original_url = entry.link
        description = entry.description if hasattr(entry, 'description') else entry.get('summary', '')

        if is_article_exists(original_url):
            print(f"    [-] Đã có trong DB: {original_title[:40]}...")
            continue

        print(f"    -> Đang xử lý: {original_title[:45]}...")

        prompt = f"""
        Bạn là biên tập viên về Dinh dưỡng, Ẩm thực và Sức khỏe.
        Hãy tóm tắt bài báo sau và trả về DUY NHẤT định dạng JSON hợp lệ:

        Nguồn: {source_name}
        Tiêu đề: {original_title}
        Nội dung: {description}

        Định dạng JSON:
        {{
          "title": "Tiêu đề hấp dẫn",
          "summary": "Tóm tắt từ 2-3 câu",
          "tips": "1 lời khuyên thực tế",
          "category": "Dinh dưỡng | Ẩm thực | Y học đời sống | Mẹo sức khỏe | Món ngon"
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
                print(f"       ✔ Đã nạp thành công vào website!")
            else:
                print(f"       ✖ Lỗi Supabase: {db_res.status_code}")

        except Exception as e:
            print(f"       ✖ Bỏ qua bài: {e}")

        time.sleep(3)

print("\n=== HOÀN TẤT! WEBSITE ĐÃ SẴN SÀNG XEM TIN ===")
