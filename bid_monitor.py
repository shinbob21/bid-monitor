import os
import time
import smtplib
import requests
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from urllib.parse import urljoin
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 세션 설정 (재사용으로 성능 향상)
SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})

# 설정
KEYWORDS = [
    "기프티콘", "모바일 쿠폰", "상품권",
    "쇼핑백", "종이 쇼핑백", "점보롤",
    "정수기", "공기청정기"
]

EMAIL_RECEIVERS = [
    "SHIN.CHULWOOK@eland-partner.co.kr",
    "kang.eunmi01@eland-partner.co.kr",
]

EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PW = os.environ.get("EMAIL_PW")

LOG_FILE = "crawl_log.txt"
SEEN_FILE = "seen_notices.txt"

UNIVERSITY_URLS = {
    "아주대": "https://www.ajou.ac.kr/kr/guide/bidding.do?mode=list&articleLimit=100",
    "인하대": "https://www.inha.ac.kr/kr/951/subview.do",
    "인천대": "https://www.inu.ac.kr/inu/1528/subview.do",
    "강남대": "https://gumae.kangnam.ac.kr/gumae/board/board_list.jsp?board_id=2",
    "부천대": "https://www.bc.ac.kr/bcu/pr/notice04.do?mode=list&&articleLimit=10&article.offset=0"
}

# ============================
# 공통 함수
# ============================

def log(msg):
    """로그 출력 및 파일 저장"""
    logger.info(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now()}] {msg}\n")

def load_seen():
    """이전에 본 공고 로드"""
    if not os.path.exists(SEEN_FILE):
        return set()
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f.readlines() if line.strip())
    except:
        return set()

def save_seen(url):
    """본 공고 저장"""
    try:
        with open(SEEN_FILE, "a", encoding="utf-8") as f:
            f.write(url + "\n")
    except:
        pass

def send_alert_email(subject, content):
    """이메일 발송"""
    try:
        if not EMAIL_SENDER or not EMAIL_PW:
            log("⚠️ 이메일 환경변수 미설정")
            return False

        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"] = EMAIL_SENDER
        msg["To"] = ", ".join(EMAIL_RECEIVERS)
        msg.attach(MIMEText(content, "plain"))

        with smtplib.SMTP_SSL("smtp.naver.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PW)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVERS, msg.as_string())

        log(f"📧 이메일 발송 완료: {subject}")
        return True

    except Exception as e:
        log(f"❌ 이메일 발송 실패: {e}")
        return False

def fetch_with_retry(url, timeout=10, max_retries=3):
    """재시도 로직이 있는 HTTP 요청"""
    for attempt in range(max_retries):
        try:
            response = SESSION.get(url, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.Timeout:
            log(f"⏱️ [{url}] 타임아웃 (시도 {attempt + 1}/{max_retries})")
        except requests.exceptions.ConnectionError:
            log(f"🔗 [{url}] 연결 오류 (시도 {attempt + 1}/{max_retries})")
        except Exception as e:
            log(f"❌ [{url}] 요청 실패: {e} (시도 {attempt + 1}/{max_retries})")
        
        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)  # 지수 백오프
    
    return None

def parse_html_safe(html_content):
    """안전한 HTML 파싱"""
    try:
        return BeautifulSoup(html_content, "lxml")
    except:
        try:
            return BeautifulSoup(html_content, "html.parser")
        except:
            return None

def has_keyword(text):
    """키워드 확인"""
    if not text:
        return False
    text_lower = text.lower()
    for kw in KEYWORDS:
        if kw.lower() in text_lower:
            return True
    return False

# ============================
# 크롤링 함수
# ============================

def crawl_university(name, base_url, selector):
    """대학 입찰 공고 크롤링 (requests 기반)"""
    results = []
    seen = load_seen()
    
    log(f"\n=== [{name}] 크롤링 시작 ===")
    
    response = fetch_with_retry(base_url)
    if not response:
        log(f"❌ [{name}] 페이지 조회 실패")
        return results
    
    soup = parse_html_safe(response.text)
    if not soup:
        log(f"❌ [{name}] HTML 파싱 실패")
        return results
    
    try:
        links = soup.select(selector)
        log(f"[{name}] 발견된 링크 수: {len(links)}")
        
        for a in links:
            try:
                title = a.get_text(strip=True)
                href = a.get("href", "")
                
                if not title or not href or len(title) < 3:
                    continue
                
                # URL 정규화
                if href.startswith("/"):
                    href = urljoin(base_url, href)
                elif not href.startswith("http"):
                    continue
                
                if href in seen:
                    continue
                
                # 키워드 확인
                if has_keyword(title):
                    results.append((name, title, href))
                    save_seen(href)
                    log(f"🎯 [{name}] 키워드 매칭: {title}")
            
            except Exception as e:
                continue
    
    except Exception as e:
        log(f"❌ [{name}] 크롤링 중 오류: {e}")
    
    return results

# ============================
# 메인 실행
# ============================

def run_job():
    """메인 작업 실행"""
    log("\n" + "=" * 50)
    log("입찰 추적 시작...")
    log("=" * 50)
    
    all_results = []
    
    try:
        # 모든 대학 크롤링 (requests 기반)
        all_results.extend(crawl_university("아주대", UNIVERSITY_URLS["아주대"], "a[href*='bidding']"))
        all_results.extend(crawl_university("인하대", UNIVERSITY_URLS["인하대"], ".board-list a, table a"))
        all_results.extend(crawl_university("인천대", UNIVERSITY_URLS["인천대"], ".board-list a, table a"))
        all_results.extend(crawl_university("강남대", UNIVERSITY_URLS["강남대"], "td.subject a, a[href*='board_view']"))
        all_results.extend(crawl_university("부천대", UNIVERSITY_URLS["부천대"], ".board_list a, table a"))
        
        if all_results:
            log(f"\n📢 총 {len(all_results)}개 공고 발견! 이메일 발송 중...")
            for name, title, link in all_results:
                content = f"[{name}] 새로운 공고 발견\n\n제목: {title}\n링크: {link}"
                send_alert_email(f"[입찰 알림] {name} - {title[:40]}...", content)
        else:
            log("✅ 발견된 공고 없음.")
    
    except Exception as e:
        log(f"❌ 작업 중 오류 발생: {e}")
        send_alert_email("[입찰 알림] 크롤링 중 오류 발생", f"오류 내용: {str(e)}")
    
    finally:
        log("=" * 50)
        log("작업 완료.")
        log("=" * 50)

if __name__ == "__main__":
    run_job()
