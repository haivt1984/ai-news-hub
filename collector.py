import os
import re
import html
import time
import feedparser
import requests
import sys

sys.stdout.reconfigure(line_buffering=True)

# ================= CẤU HÌNH THÔNG TIN =================
RAW_SUPABASE = os.getenv("SUPABASE_URL", "https://lleeibzegmnycuingzgx.supabase.co")
if "](" in RAW_SUPABASE:
    RAW_SUPABASE = RAW_SUPABASE.split("](")[-1].replace(")", "")
RAW_SUPABASE = RAW_SUPABASE.strip("[]'\" \t\n\r")

if not RAW_SUPABASE.startswith("http"):
    SUPABASE_URL = f"https://{RAW_SUPABASE}"
else:
    SUPABASE_URL = RAW_SUPABASE

SUPABASE_KEY = os.getenv(
    "SUPABASE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxsZWVpYnplZ21ueWN1aW5nemd4Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc5MDEyNzk5NSwiZXhwIjoyMTA1NzAzOTk1fQ.HvOv3jwDbnc0mf89L8H2orG-g19Xg4AR7jMyXXTI_M8"
).strip("[]'\" \t\n\r")
# ======================================================

FEEDS = [
    {"source": "VnExpress Sức Khỏe", "url": "https://vnexpress.net/rss/suc-khoe.rss", "cat": "Y học đời sống"},
    {"source": "Tuổi Trẻ Sức Khỏe", "url": "https://tuoitre.vn/rss/suc-khoe.rss", "cat": "Dinh dưỡng"},
    {"source": "Thanh Niên Sức Khỏe", "url": "https://thanhnien.vn/rss/suc-khoe.rss", "cat": "Mẹo sống khỏe"},
    {"source": "Dân Trí Sức Khỏe", "url": "https://dantri.com.vn/rss/suc-khoe.rss", "cat": "Y học đời sống"},
    {"source": "VietnamNet Sức Khỏe", "url": "https://vietnamnet.vn/rss/suc-khoe.rss", "cat": "Dinh dưỡng"}
]

ARTICLES_PER_FEED = 3

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

def clean_html(text):
    if not text:
        return ""
    text = html.unescape(text)
    clean = re.compile(r'<[^>]+>')
    text = re.sub(clean, '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def is_article_exists(url):
    try:
        check_url = f"{SUPABASE_ENDPOINT}?original_url=eq.{requests.utils.quote(url)}&select=id"
        res = requests.get(check_url, headers=SUPABASE_HEADERS, timeout=8)
        if res.status_code == 200 and len(res.json()) > 0:
            return True
    except Exception as e:
        print(f"      [!] Lỗi kiểm tra trùng lặp: {e}")
    return False

def generate_tips_and_summary(title, desc, default_cat):
    title_clean = clean_html(title)
    desc_clean = clean_html(desc)
    
    # Phân loại thông minh dựa theo từ khóa bài báo
    content_lower = f"{title_clean} {desc_clean}".lower()
    category = default_cat
    if any(k in content_lower for k in ["món", "ẩm thực", "nấu", "bánh", "ăn", "thực đơn", "thịt", "cá"]):
        category = "Ẩm thực & Món ngon"
    elif any(k in content_lower for k in ["dinh dưỡng", "calo", "vitamin", "khoáng chất", "uống", "giảm cân"]):
        category = "Dinh dưỡng"
    elif any(k in content_lower for k in ["bệnh", "ung thư", "vi khuẩn", "ngộ độc", "bác sĩ", "thuốc", "y tế"]):
        category = "Y học đời sống"
    elif any(k in content_lower for k in ["tập", "ngủ", "mẹo", "thói quen", "sống khỏe", "da"]):
        category = "Mẹo sống khỏe"

    # Tạo tóm tắt và lời khuyên thiết thực
    summary = desc_clean if len(desc_clean) > 20 else title_clean
    tips = "Nên tham khảo ý kiến chuyên gia y tế hoặc điều chỉnh chế độ ăn uống khoa học, cân đối dinh dưỡng hàng ngày."

    if "ngộ độc" in content_lower or "vi khuẩn" in content_lower:
        tips = "Lưu ý ăn chín uống sôi, kiểm tra kỹ nguồn gốc và hạn sử dụng thực phẩm để phòng ngừa nhiễm khuẩn."
    elif "calo" in content_lower or "béo" in content_lower or "cân" in content_lower:
        tips = "Kiểm soát khẩu phần ăn hợp lý, hạn chế đường tinh luyện và tăng cường vận động ít nhất 30 phút mỗi ngày."
    elif "món" in content_lower or "ẩm thực" in content_lower:
        tips = "Lựa chọn nguyên liệu tươi sống, kết hợp hài hòa rau xanh và gia vị tự nhiên để món ăn thơm ngon, bổ dưỡng."

    return title_clean, summary, tips, category

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

        print(f"    -> Đang nạp: {original_title[:45]}...")

        title, summary, tips, category = generate_tips_and_summary(
            original_title, description, feed_info["cat"]
        )

        record = {
            "title": title,
            "summary": summary,
            "tips": tips,
            "category": category,
            "original_url": original_url
        }

        try:
            db_res = requests.post(SUPABASE_ENDPOINT, headers=SUPABASE_HEADERS, json=record, timeout=10)
            if db_res.status_code in [200, 201]:
                print(f"       ✔ Đã lưu thành công: [{category}]")
            else:
                print(f"       ✖ Lỗi Supabase: {db_res.status_code} - {db_res.text[:80]}")
        except Exception as e:
            print(f"       ✖ Lỗi kết nối DB: {e}")

        time.sleep(1)

print("\n=== HOÀN TẤT! WEBSITE ĐÃ SẴN SÀNG XEM TIN ===")
