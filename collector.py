import os
import re
import html
import time
import feedparser
import requests
import sys
from bs4 import BeautifulSoup

sys.stdout.reconfigure(line_buffering=True)

# ================= CẤU HÌNH THÔNG TIN =================
RAW_SUPABASE = os.getenv("SUPABASE_URL", "https://lleeibzegmnycuingzgx.supabase.co")[cite: 1]
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
).strip("[]'\" \t\n\r")[cite: 1]
# ======================================================

# Bổ sung nguồn cấp RSS chuyên biệt cho Món ngon / Cách nấu
FEEDS = [
    {"source": "VnExpress Ẩm Thực", "url": "https://vnexpress.net/rss/du-lich/am-thuc.rss", "cat": "Ẩm thực & Món ngon"},
    {"source": "Tuổi Trẻ Ẩm Thực", "url": "https://tuoitre.vn/rss/du-lich/am-thuc.rss", "cat": "Ẩm thực & Món ngon"},
    {"source": "Thanh Niên Ẩm Thực", "url": "https://thanhnien.vn/rss/gioi-tre/am-thuc.rss", "cat": "Ẩm thực & Món ngon"},
    {"source": "VnExpress Sức Khỏe", "url": "https://vnexpress.net/rss/suc-khoe.rss", "cat": "Y học đời sống"},
    {"source": "Dân Trí Đời Sống & Ẩm Thực", "url": "https://dantri.com.vn/rss/doi-song.rss", "cat": "Ẩm thực & Món ngon"},
    {"source": "VietnamNet Sức Khỏe", "url": "https://vietnamnet.vn/rss/suc-khoe.rss", "cat": "Dinh dưỡng"}
]

ARTICLES_PER_FEED = 5

SUPABASE_ENDPOINT = f"{SUPABASE_URL}/rest/v1/articles"
SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "vi,en-US;q=0.9,en;q=0.8"
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

def scrape_article_data(url):
    """Truy cập đường dẫn và bóc tách toàn bộ bài viết cùng link ảnh cover."""
    try:
        res = requests.get(url, headers=REQUEST_HEADERS, timeout=12)
        if res.status_code != 200:
            return "", ""

        soup = BeautifulSoup(res.text, 'html.parser')

        # 1. Tìm ảnh đại diện bài viết
        image_url = ""
        meta_img = soup.find('meta', property='og:image') or soup.find('meta', attrs={'name': 'twitter:image'})
        if meta_img and meta_img.get('content'):
            image_url = meta_img['content'].strip()

        # 2. Loại bỏ các thành phần rác
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe', 'figure']):
            tag.decompose()

        # 3. Định danh vùng nội dung theo từng đầu báo
        content_box = None
        if "dantri.com.vn" in url:
            content_box = soup.select_one(".singular-content")
        elif "vnexpress.net" in url:
            content_box = soup.select_one("article.fck_detail")
        elif "tuoitre.vn" in url:
            content_box = soup.select_one(".detail-cmain, #main-detail-body")
        elif "thanhnien.vn" in url:
            content_box = soup.select_one(".detail-content, #abody")
        elif "vietnamnet.vn" in url:
            content_box = soup.select_one("#maincontent, .maincontent")

        target = content_box if content_box else soup.body
        if not target:
            return "", image_url

        paragraphs = target.find_all('p')
        valid_texts = []
        for p in paragraphs:
            p_text = clean_html(p.get_text())
            if len(p_text) > 35:
                valid_texts.append(p_text)

        full_content = "\n\n".join(valid_texts)
        return full_content, image_url
    except Exception as e:
        print(f"      [!] Lỗi bóc tách chi tiết: {e}")
        return "", ""

def generate_tips_and_summary(title, desc, default_cat):
    title_clean = clean_html(title)
    desc_clean = clean_html(desc)
    
    content_lower = f"{title_clean} {desc_clean}".lower()
    category = default_cat
    
    # Từ khóa chuyên biệt nhận diện công thức, chế biến món ăn ngon
    cook_keywords = [
        "cách nấu", "cách làm", "món ngon", "chế biến", "nấu nướng", "nguyên liệu", 
        "hướng dẫn làm", "thực đơn", "món xào", "món kho", "món canh", "món nướng", 
        "hầm", "luộc", "ẩm thực", "bí quyết nấu", "bữa cơm", "món ăn"
    ]
    
    if any(k in content_lower for k in cook_keywords) or default_cat == "Ẩm thực & Món ngon":
        category = "Ẩm thực & Món ngon"
    elif any(k in content_lower for k in ["dinh dưỡng", "calo", "vitamin", "khoáng chất", "uống", "giảm cân"]):
        category = "Dinh dưỡng"
    elif any(k in content_lower for k in ["bệnh", "ung thư", "vi khuẩn", "ngộ độc", "bác sĩ", "thuốc", "y tế"]):
        category = "Y học đời sống"
    elif any(k in content_lower for k in ["tập", "ngủ", "mẹo", "thói quen", "sống khỏe", "da"]):
        category = "Mẹo sống khỏe"

    summary = desc_clean if len(desc_clean) > 20 else title_clean
    tips = "Nên lựa chọn nguyên liệu tươi sạch và nêm nếm vừa phải để đảm bảo sức khỏe cả gia đình."

    # Lời khuyên/mẹo bếp núc cho món ngon
    if category == "Ẩm thực & Món ngon":
        tips = "Mẹo làm bếp: Chuẩn bị đầy đủ nguyên liệu trước khi bật bếp và kiểm soát nhiệt độ lửa để món ăn dậy mùi thơm tự nhiên."
    elif "ngộ độc" in content_lower or "vi khuẩn" in content_lower:
        tips = "Lưu ý ăn chín uống sôi, kiểm tra kỹ nguồn gốc thực phẩm để phòng ngừa nhiễm khuẩn tiêu hóa."
    elif "calo" in content_lower or "béo" in content_lower or "cân" in content_lower:
        tips = "Kiểm soát khẩu phần ăn khoa học, giảm dầu mỡ tinh luyện và duy trì tập luyện đều đặn."

    return title_clean, summary, tips, category

print("=== BẮT ĐẦU TIẾN TRÌNH THU THẬP MÓN NGON & SỨC KHỎE ===")

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

        full_content, image_url = scrape_article_data(original_url)

        title, summary, tips, category = generate_tips_and_summary(
            original_title, description, feed_info["cat"]
        )

        record = {
            "title": title,
            "summary": summary,
            "content": full_content if full_content else summary,
            "image_url": image_url,
            "tips": tips,
            "category": category,
            "original_url": original_url
        }

        try:
            db_res = requests.post(SUPABASE_ENDPOINT, headers=SUPABASE_HEADERS, json=record, timeout=10)
            if db_res.status_code in [200, 201]:
                print(f"       ✔ Đã lưu: [{category}] (Dài: {len(record['content'])} ký tự | Có ảnh: {bool(image_url)})")
            else:
                print(f"       ✖ Lỗi Supabase: {db_res.status_code} - {db_res.text[:80]}")
        except Exception as e:
            print(f"       ✖ Lỗi kết nối DB: {e}")

        time.sleep(1)

print("\n=== HOÀN TẤT! WEBSITE ĐÃ SẴN SÀNG XEM TIN ===")
