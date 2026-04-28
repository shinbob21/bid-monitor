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
    options = Options()
    options.add_argument("--headless")  # GitHub Actions 호환
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def send_alert_email(subject, content, screenshot_path=None):
    try:
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
        log
