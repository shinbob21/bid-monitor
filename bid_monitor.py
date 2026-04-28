import os
import time
import smtplib
import requests
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime

# -----------------------------
# 설정
# -----------------------------

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
    "인하대": "https://www.inha.ac.kr/kr/951/subview.do",
    "인천대": "https://www.inu.ac.kr/inu/1528/subview.do",
    "강남대": "https://gumae.kangnam.ac.kr/gumae/board/board_list.jsp?board_id=2",
    "부천대": "https://www.bc.ac.kr/bcu/pr/notice04.do?mode=list&&articleLimit=10&article.offset=0"
}

# -----------------------------
# 공통 함수
# -----------------------------

def log(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now()}] {msg}\n")
    print(msg)

def load_seen():
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f.readlines())

def save_seen(url):
    with open(SEEN_FILE, "a", encoding="utf-8") as f:
        f.write(url + "\n")

def get_driver():
    """Selenium 웹드라이버 초기화 (에러 처리 포함)"""
    try:
        options = Options()
        options.add_argument("--headless")  # GitHub Actions 호환
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), 
            options=options
        )
        log("✅ 웹드라이버 초기화 성공")
        return driver
    except Exception as e:
        log(f"❌ 웹드라이버 초기화 실패: {e}")
        raise

def send_alert_email(subject, content, screenshot_path=None):
    """이메일 발송 (환경변수 검증 포함)"""
    try:
        # 환경변수 검증
        if not EMAIL_SENDER or not EMAIL_PW:
            log("⚠️ 이메일 환경변수 미설정: EMAIL_SENDER 또는 EMAIL_PW 확인 필요")
            return

        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"] = EMAIL_SENDER
        msg["To"] = ", ".join(EMAIL_RECEIVERS)

        msg.attach(MIMEText(content, "plain"))

        if screenshot_path and os.path.exists(screenshot_path):
            with open(screenshot_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename={os.path.basename(screenshot_path)}"
                )
                msg.attach(part)

        with smtplib.SMTP_SSL("smtp.naver.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PW)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVERS, msg.as_string())

        log("📧 이메일 발송 완료")

    except Exception as e:
        log(f"❌ 이메일 발송 실패: {e}")

def extract_text_safe(elem):
    """텍스트 추출 (안전)"""
    try:
        return elem.text.strip()
    except:
        return ""

def handle_alert_if_any(driver):
    """알림창 처리"""
    try:
        alert = driver.switch_to.alert
        text = alert.text
        log(f"⚠️ 알럿 감지됨: {text}")
        alert.dismiss()
        time.sleep(1)
    except:
        pass

# -----------------------------
# 아주대 전용 (requests 기반)
# -----------------------------

def crawl_ajou_requests():
    """아주대 크롤링 (requests 기반)"""
    results = []
    seen = load_seen()

    url = "https://www.ajou.ac.kr/kr/guide/bidding.do?mode=list&articleLimit=100"
    log("=== [아주대] requests 기반 크롤링 시작 ===")

    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
    except Exception as e:
        log(f"[아주대] 목록 요청 실패: {e}")
        return results

    try:
        soup = BeautifulSoup(res.text, "html.parser")
        links = soup.select("a")

        for a in links:
            title = a.get_text(strip=True)
            href = a.get("href")

            if not title or not href:
                continue

            if href.startswith("/"):
                href = "https://www.ajou.ac.kr" + href

            if href in seen:
                continue

            try:
                detail = requests.get(href, timeout=10)
                detail.raise_for_status()
                detail_text = detail.text
            except:
                continue

            for kw in KEYWORDS:
                if kw in title or kw in detail_text:
                    results.append(("아주대", title, href, None))
                    save_seen(href)
                    log(f"🎯 [아주대] 키워드 매칭: {title}")
                    break

    except Exception as e:
        log(f"[아주대] 크롤링 중 오류: {e}")

    return results

# -----------------------------
# Selenium 기반 대학 크롤링
# -----------------------------

def crawl_university(driver, name, url, title_selector):
    """대학 입찰 공고 크롤링 (Selenium 기반)"""
    results = []
    seen = load_seen()

    log(f"=== [{name}] 크롤링 시작 ===")
    
    try:
        driver.get(url)
        time.sleep(2)

        handle_alert_if_any(driver)

        titles = driver.find_elements(By.CSS_SELECTOR, title_selector)
        log(f"[{name}] 발견된 링크 수: {len(titles)}")

        for t in titles:
            try:
                title = extract_text_safe(t)
                if not title:
                    continue

                link = t.get_attribute("href")
                if not link or link in seen:
                    continue

                driver.execute_script("window.open(arguments[0]);", link)
                driver.switch_to.window(driver.window_handles[-1])
                time.sleep(1)

                handle_alert_if_any(driver)

                page_text = driver.page_source

                screenshot_name = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                driver.save_screenshot(screenshot_name)

                driver.close()
                driver.switch_to.window(driver.window_handles[0])

                for kw in KEYWORDS:
                    if kw in title or kw in page_text:
                        results.append((name, title, link, screenshot_name))
                        save_seen(link)
                        log(f"🎯 [{name}] 키워드 매칭: {title}")
                        break

            except Exception as e:
                log(f"[{name}] 개별 링크 처리 중 오류: {e}")
                # 창 정리
                try:
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                except:
                    pass
                continue

    except Exception as e:
        log(f"❌ [{name}] 크롤링 중 오류: {e}")

    return results

# -----------------------------
# 메인 실행
# -----------------------------

def run_job():
    """메인 작업 실행"""
    log("=" * 50)
    log("입찰 추적 시작...")
    log("=" * 50)

    driver = None
    try:
        driver = get_driver()
        all_results = []

        # 아주대는 오직 requests 버전만 사용
        all_results.extend(crawl_ajou_requests())

        # 나머지 대학만 Selenium 사용
        all_results.extend(crawl_university(driver, "인하대", UNIVERSITY_URLS["인하대"], ".board-list a"))
        all_results.extend(crawl_university(driver, "인천대", UNIVERSITY_URLS["인천대"], ".board-list a"))
        all_results.extend(crawl_university(driver, "강남대", UNIVERSITY_URLS["강남대"], "td.subject a"))
        all_results.extend(crawl_university(driver, "부천대", UNIVERSITY_URLS["부천대"], ".board_list a"))

        if all_results:
            log(f"\n📢 총 {len(all_results)}개 공고 발견! 이메일 발송 중...")
            for name, title, link, screenshot in all_results:
                content = f"[{name}] 새로운 공고 발견\n\n제목: {title}\n링크: {link}"
                send_alert_email("[입찰 알림] 새로운 공고 발견", content, screenshot)
        else:
            log("✅ 발견된 공고 없음.")

    except Exception as e:
        log(f"❌ 작업 중 오류 발생: {e}")
        
    finally:
        # 드라이버 안전하게 종료
        if driver:
            try:
                driver.quit()
                log("✅ 웹드라이버 종료")
            except Exception as e:
                log(f"⚠️ 드라이�� 종료 중 오류: {e}")

    log("=" * 50)
    log("작업 완료.")
    log("=" * 50)

if __name__ == "__main__":
    run_job()
