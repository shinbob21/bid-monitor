import gc  # 추가
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

# ... (기존 설정 코드 동일)

def get_driver():
    """Selenium 웹드라이버 초기화 (메모리 최적화)"""
    try:
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--single-process")  # 추가
        options.add_argument("--disable-images")  # 추가
        options.add_argument("--disable-extensions")  # 추가
        options.add_argument("--disable-plugins")  # 추가
        
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), 
            options=options
        )
        log("✅ 웹드라이버 초기화 성공")
        return driver
    except Exception as e:
        log(f"❌ 웹드라이버 초기화 실패: {e}")
        raise

def cleanup_driver(driver):
    """드라이버 안전 정리"""
    if driver:
        try:
            driver.quit()
            log("✅ 웹드라이버 종료")
        except Exception as e:
            log(f"⚠️ 드라이버 종료 중 오류: {e}")
    gc.collect()  # 가비지 컬렉션

def run_job():
    """메인 작업 실행"""
    log("=" * 50)
    log("입찰 추적 시작...")
    log("=" * 50)

    driver = None
    try:
        all_results = []
        
        # 아주대는 requests만 사용
        all_results.extend(crawl_ajou_requests())
        
        # 각 대학별로 새 드라이버 생성 (메모리 누수 방지)
        for uni_name, url, selector in [
            ("인하대", UNIVERSITY_URLS["인하대"], ".board-list a"),
            ("인천대", UNIVERSITY_URLS["인천대"], ".board-list a"),
            ("강남대", UNIVERSITY_URLS["강남대"], "td.subject a"),
            ("부천대", UNIVERSITY_URLS["부천대"], ".board_list a"),
        ]:
            driver = get_driver()
            try:
                all_results.extend(crawl_university(driver, uni_name, url, selector))
            except Exception as e:
                log(f"❌ [{uni_name}] 크롤링 중 오류: {e}")
            finally:
                cleanup_driver(driver)
                driver = None
                gc.collect()

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
        if driver:
            cleanup_driver(driver)
        gc.collect()

    log("=" * 50)
    log("작업 완료.")
    log("=" * 50)

if __name__ == "__main__":
    run_job()
