import os
import time
import smtplib
from email.mime.text import MIMEText
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# --- 설정 정보 ---
KEYWORDS = ["기프티콘", "모바일 쿠폰", "상품권"]
EMAIL_RECEIVER = "SHIN.CHULWOOK@eland-partner.co.kr"
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PW = os.environ.get("EMAIL_PW")
STARBILL_ID = os.environ.get("STARBILL_ID")
STARBILL_PW = os.environ.get("STARBILL_PW")

UNIVERSITY_URLS = {
    "아주대": "https://ajou.ac.kr",
    "인하대": "https://inha.ac.kr",
    "인천대": "https://inu.ac.kr",
    "강남대": "https://kangnam.ac.kr",
    "유한대": "https://yuhan.ac.kr"
}

def get_driver():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def send_alert_email(subject, content):
    try:
        msg = MIMEText(content)
        msg['Subject'] = subject
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECEIVER
        with smtplib.SMTP_SSL('smtp.naver.com', 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PW)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
    except Exception as e:
        print(f"이메일 발송 실패: {e}")

def check_starbill(driver):
    found = []
    try:
        driver.get("https://starbill.co.kr")
        time.sleep(2)
        driver.find_element(By.NAME, "loginId").send_keys(STARBILL_ID)
        driver.find_element(By.NAME, "password").send_keys(STARBILL_PW)
        driver.find_element(By.ID, "btn_login").click()
        time.sleep(3)

        for kw in KEYWORDS:
            # 실제 input name은 사이트에서 확인 필요
            search_input = driver.find_element(By.NAME, "KEYWORDS")
            search_input.clear()
            search_input.send_keys(kw)
            search_input.send_keys(Keys.ENTER)
            time.sleep(2)

            if "데이터가 없습니다" not in driver.page_source:
                found.append(f"[스타빌] '{kw}' 검색 결과 발견")

    except Exception as e:
        print(f"스타빌 확인 중 오류: {e}")

    return found

def run_job():
    print("입찰 추적 시작...")
    driver = get_driver()
    all_results = []

    # 대학 사이트 검색
    for school, url in UNIVERSITY_URLS.items():
        try:
            driver.get(url)
            time.sleep(2)
            for kw in KEYWORDS:
                if kw in driver.page_source:
                    all_results.append(f"[{school}] {kw} 관련 공고 의심 - {url}")
        except Exception as e:
            print(f"{school} 접속 실패: {e}")

    # 스타빌 검색
    starbill_results = check_starbill(driver)
    all_results.extend(starbill_results)

    driver.quit()

    if all_results:
        send_alert_email("[입찰 알림] 새로운 공고가 발견되었습니다.", "\n".join(all_results))
    else:
        print("발견된 공고 없음.")

    print("작업 완료.")

if __name__ == "__main__":
    run_job()
