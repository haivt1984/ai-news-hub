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

# Nguồn RSS tin tức sức khỏe tổng hợp
FEEDS = [
    {"source": "VnExpress Sức Khỏe", "url": "https://vnexpress.net/rss/suc-khoe.rss", "cat": "Y học đời sống"},
    {"source": "Dân Trí Sức Khỏe", "url": "https://dantri.com.vn/rss/suc-khoe.rss", "cat": "Y học đời sống"},
    {"source": "VietnamNet Sức Khỏe", "url": "https://vietnamnet.vn/rss/suc-khoe.rss", "cat": "Dinh dưỡng"}
]

ARTICLES_PER_FEED = 3
RECIPES_LIMIT = 5

SUPABASE_ENDPOINT = f"{SUPABASE_URL}/rest/v1/articles"
SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
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
    """Bóc tách bài viết từ các trang tin tức thông thường."""
    try:
        res = requests.get(url, headers=REQUEST_HEADERS, timeout=12)
        if res.status_code != 200:
            return "", ""

        soup = BeautifulSoup(res.text, 'html.parser')
        image_url = ""
        meta_img = soup.find('meta', property='og:image') or soup.find('meta', attrs={'name': 'twitter:image'})
        if meta_img and meta_img.get('content'):
            image_url = meta_img['content'].strip()

        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe', 'figure']):
            tag.decompose()

        content_box = None
        if "dantri.com.vn" in url:
            content_box = soup.select_one(".singular-content")
        elif "vnexpress.net" in url:
            content_box = soup.select_one("article.fck_detail")
        elif "vietnamnet.vn" in url:
            content_box = soup.select_one("#maincontent, .maincontent")

        target = content_box if content_box else soup.body
        if not target:
            return "", image_url

        paragraphs = target.find_all('p')
        valid_texts = [clean_html(p.get_text()) for p in paragraphs if len(clean_html(p.get_text())) > 35]

        return "\n\n".join(valid_texts), image_url
    except Exception as e:
        print(f"      [!] Lỗi bóc tách bài tin: {e}")
        return "", ""

def scrape_mon_ngon_detail(url):
    """Trích xuất chi tiết công thức nấu ăn từ monngonmoingay.com."""
    try:
        res = requests.get(url, headers=REQUEST_HEADERS, timeout=12)
        if res.status_code != 200:
            return "", "", "", ""

        soup = BeautifulSoup(res.text, 'html.parser')

        # 1. Tiêu đề món ăn
        title_el = soup.find('h1') or soup.select_one('.entry-title')
        title = clean_html(title_el.get_text()) if title_el else ""

        # 2. Ảnh đại diện món ăn
        image_url = ""
        meta_img = soup.find('meta', property='og:image')
        if meta_img and meta_img.get('content'):
            image_url = meta_img['content'].strip()

        # 3. Lời khuyên / Mẹo thực hiện
        tips = "Mẹo làm bếp: Chuẩn bị đầy đủ gia vị và sơ chế kỹ nguyên liệu để món ăn chuẩn vị và dậy mùi thơm ngon."
        tip_box = soup.select_one('.mach-nho, .tip-box, .recipe-tips')
        if tip_box:
            tips = clean_html(tip_box.get_text())

        # 4. Trích xuất Nguyên liệu & Các bước thực hiện
        sections = []

        # Bóc tách phần Nguyên Liệu
        nguyen_lieu_box = soup.select_one('.nguyen-lieu, .ingredients, .recipe-ingredients')
        if nguyen_lieu_box:
            lines = [clean_html(li.get_text()) for li in nguyen_lieu_box.find_all(['li', 'p']) if clean_html(li.get_text())]
            if lines:
                sections.append("### NGUYÊN LIỆU CHUẨN BỊ:\n" + "\n".join([f"- {l}" for l in lines]))

        # Bóc tách phần Sơ Chế / Thực Hiện
        cach_lam_box = soup.select_one('.cach-lam, .instructions, .recipe-directions, .entry-content')
        if cach_lam_box:
            steps = []
            for item in cach_lam_box.find_all(['p', 'li']):
                txt = clean_html(item.get_text())
                if len(txt) > 20 and not txt.startswith("Từ khóa:") and not txt.startswith("Chia sẻ:"):
                    steps.append(txt)
            if steps:
                sections.append("### CÁCH THỰC HIỆN:\n" + "\n\n".join(steps))

        full_content = "\n\n".join(sections)
        summary = f"Hướng dẫn công thức chi tiết và cách làm món {title} chuẩn vị, bổ dưỡng cho thực đơn bữa cơm gia đình mỗi ngày."

        return title, summary, full_content, image_url, tips
    except Exception as e:
        print(f"      [!] Lỗi lấy chi tiết monngonmoingay: {e}")
        return "", "", "", "", ""

def harvest_mon_ngon_moi_ngay():
    """Thu thập danh sách công thức mới nhất từ monngonmoingay.com."""
    print("\n[*] Đang quét nguồn: monngonmoingay.com (Món ngon mỗi ngày)")
    target_url = "https://monngonmoingay.com/tim-kiem-mon-ngon/"
    
    try:
        res = requests.get(target_url, headers=REQUEST_HEADERS, timeout=12)
        if res.status_code != 200:
            print(f"    [x] Không thể truy cập trang danh mục: Status {res.status_code}")
            return

        soup = BeautifulSoup(res.text, 'html.parser')
        
        # Tìm các liên kết bài viết công thức nấu ăn
        recipe_links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            # Đường dẫn bài viết món ăn thường có đuôi kết thúc dạng slug
            if "monngonmoingay.com/" in href and not any(x in href for x in ['/tag/', '/category/', '/video/', '/tac-gia/', '/lien-he/']):
                if href != "https://monngonmoingay.com/" and href not in recipe_links and href.count('/') >= 4:
                    recipe_links.append(href)

        links_to_crawl = recipe_links[:RECIPES_LIMIT]
        print(f"    Tìm thấy {len(recipe_links)} công thức. Xử lý {len(links_to_crawl)} món mới:")

        for url in links_to_crawl:
            if is_article_exists(url):
                print(f"    [-] Đã có trong DB: {url}")
                continue

            title, summary, content, image_url, tips = scrape_mon_ngon_detail(url)
            if not title or not content:
                continue

            print(f"    -> Đang nạp công thức: {title[:45]}...")

            record = {
                "title": title,
                "summary": summary,
                "content": content,
                "image_url": image_url,
                "tips": tips,
                "category": "Ẩm thực & Món ngon",
                "original_url": url
            }

            try:
                db_res = requests.post(SUPABASE_ENDPOINT, headers=SUPABASE_HEADERS, json=record, timeout=10)
                if db_res.status_code in [200, 201]:
                    print(f"       ✔ Đã lưu công thức: [{record['title'][:35]}] (Có ảnh: {bool(image_url)})")
                else:
                    print(f"       ✖ Lỗi Supabase: {db_res.status_code} - {db_res.text[:80]}")
            except Exception as e:
                print(f"       ✖ Lỗi kết nối DB: {e}")

            time.sleep(1)

    except Exception as e:
        print(f"    [x] Lỗi quét monngonmoingay.com: {e}")

print("=== BẮT ĐẦU TIẾN TRÌNH THU THẬP MÓN NGON & SỨC KHỎE ===")

# 1. Cào công thức chuyên sâu từ monngonmoingay.com
harvest_mon_ngon_moi_ngay()

# 2. Cào bài viết sức khỏe từ các nguồn báo
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
        original_title = clean_html(entry.title)
        original_url = entry.link
        description = clean_html(entry.description if hasattr(entry, 'description') else entry.get('summary', ''))

        if is_article_exists(original_url):
            print(f"    [-] Đã có trong DB: {original_title[:40]}...")
            continue

        print(f"    -> Đang nạp: {original_title[:45]}...")

        full_content, image_url = scrape_article_data(original_url)

        summary = description if len(description) > 20 else original_title
        tips = "Nên tham khảo ý kiến chuyên gia y tế hoặc cân đối dinh dưỡng khoa học hàng ngày."

        record = {
            "title": original_title,
            "summary": summary,
            "content": full_content if full_content else summary,
            "image_url": image_url,
            "tips": tips,
            "category": feed_info["cat"],
            "original_url": original_url
        }

        try:
            db_res = requests.post(SUPABASE_ENDPOINT, headers=SUPABASE_HEADERS, json=record, timeout=10)
            if db_res.status_code in [200, 201]:
                print(f"       ✔ Đã lưu bài viết: [{feed_info['cat']}]")
            else:
                print(f"       ✖ Lỗi Supabase: {db_res.status_code} - {db_res.text[:80]}")
        except Exception as e:
            print(f"       ✖ Lỗi kết nối DB: {e}")

        time.sleep(1)

print("\n=== HOÀN TẤT! WEBSITE ĐÃ SẴN SÀNG XEM TIN ===")
