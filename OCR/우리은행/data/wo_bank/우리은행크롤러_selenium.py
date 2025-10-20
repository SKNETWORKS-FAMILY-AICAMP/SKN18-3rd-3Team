import os
import re
import time
import urllib.parse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import requests

# 크롤링 대상 정의
CRAWL_TARGETS = {
    "1": {
        "name": "우리예금약관",
        "url": "https://spot.wooribank.com/pot/Dream?withyou=CQFNT0016",
        "folder": "./우리예금약관"
    },
    "2": {
        "name": "우리예금상품설명",
        "url": "https://spot.wooribank.com/pot/Dream?withyou=CQFNT0017",
        "folder": "./우리예금상품설명"
    },
    "3": {
        "name": "우리예금필요서류",
        "url": "https://spot.wooribank.com/pot/Dream?withyou=CQFNT0046",
        "folder": "./우리예금필요서류"
    },
    "4": {
        "name": "우리대출약관",
        "url": "https://spot.wooribank.com/pot/Dream?withyou=CQFNT0022",
        "folder": "./우리대출약관"
    },
    "5": {
        "name": "우리대출상품설명",
        "url": "https://spot.wooribank.com/pot/Dream?withyou=CQFNT0023",
        "folder": "./우리대출상품설명"
    },
    "6": {
        "name": "우리대출필요서류",
        "url": "https://spot.wooribank.com/pot/Dream?withyou=CQFNT0048",
        "folder": "./우리대출필요서류"
    }
}

SLEEP_SEC = 0.1

def normalize_filename(name: str) -> str:
    name = urllib.parse.unquote(name)
    name = re.sub(r'[\\/:*?"<>|]+', "_", name)
    name = re.sub(r'\s+', " ", name).strip()
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name

def guess_filename_from_url(url: str) -> str:
    q = urllib.parse.urlparse(url).query
    params = urllib.parse.parse_qs(q)
    cand = params.get("PLM_ATFL_NM", [None])[0] or params.get("PLM_ANX_SAVE_FILE_NM", [None])[0]
    if cand:
        return normalize_filename(cand)
    last = url.split("/")[-1].split("?")[0]
    return normalize_filename(last or "download.pdf")

def download_file(url: str, out_dir: str, current: int, total: int):
    os.makedirs(out_dir, exist_ok=True)
    fn = guess_filename_from_url(url)
    path = os.path.join(out_dir, fn)
    
    if os.path.exists(path):
        print(f"  [{current}/{total}] 이미 존재: {fn}")
        return
    
    print(f"  [{current}/{total}] 다운로드 중: {fn}")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    with requests.get(url, stream=True, timeout=40, headers=headers) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(1 << 14):
                if chunk:
                    f.write(chunk)
    print(f"  [{current}/{total}] 완료: {fn}")

def setup_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    driver = webdriver.Chrome(options=options)
    return driver

def extract_download_links(driver):
    links = []
    try:
        elements = driver.find_elements(By.CSS_SELECTOR, "a[href*='download.jsp']")
        for elem in elements:
            href = elem.get_attribute("href")
            if href and "download.jsp" in href:
                links.append(href)
    except Exception as e:
        print(f"  ! 링크 추출 오류: {e}")
    
    return sorted(set(links))

def crawl_with_selenium(start_url: str, out_dir: str, category_name: str):
    driver = setup_driver()
    total_files = 0
    page_idx = 1
    
    print(f"\n{'='*60}")
    print(f"[{category_name}] 크롤링 시작")
    print(f"URL: {start_url}")
    print(f"저장 폴더: {out_dir}")
    print(f"{'='*60}\n")
    
    try:
        driver.get(start_url)
        time.sleep(2)
        
        while True:
            print(f"\n[페이지 {page_idx}] 처리 중...")
            
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(1)
            
            download_links = extract_download_links(driver)
            print(f"[페이지 {page_idx}] {len(download_links)}개 파일 발견")
            
            for idx, url in enumerate(download_links, 1):
                try:
                    download_file(url, out_dir, total_files + idx, total_files + len(download_links))
                    time.sleep(SLEEP_SEC)
                except Exception as e:
                    print(f"  ! 다운로드 오류: {e}")
            
            total_files += len(download_links)
            
            next_button_found = False
            
            selectors = [
                "a:contains('다음')",
                "a:contains('▶')",
                "a.next",
                "a[onclick*='page']",
                "//a[contains(text(), '다음')]",
                "//a[contains(text(), '▶')]",
                "//a[contains(@onclick, 'page') and contains(text(), '다음')]",
            ]
            
            for selector in selectors:
                try:
                    if selector.startswith("//"):
                        buttons = driver.find_elements(By.XPATH, selector)
                    else:
                        buttons = driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    for button in buttons:
                        text = button.text.strip()
                        onclick = button.get_attribute("onclick") or ""
                        
                        if any(kw in text for kw in ["다음", "▶", "next"]) or "page" in onclick.lower():
                            print(f"  [다음 페이지 버튼 발견: '{text}']")
                            
                            current_url = driver.current_url
                            driver.execute_script("arguments[0].click();", button)
                            time.sleep(2)
                            
                            new_url = driver.current_url
                            if new_url != current_url:
                                print(f"  [페이지 이동 성공]")
                                next_button_found = True
                                break
                            else:
                                print(f"  [URL 변경 없음, 다른 버튼 시도]")
                    
                    if next_button_found:
                        break
                        
                except Exception as e:
                    continue
            
            if not next_button_found:
                try:
                    next_page_num = page_idx + 1
                    page_links = driver.find_elements(By.XPATH, f"//a[text()='{next_page_num}']")
                    
                    if page_links:
                        print(f"  [페이지 번호 {next_page_num} 클릭]")
                        driver.execute_script("arguments[0].click();", page_links[0])
                        time.sleep(2)
                        next_button_found = True
                except Exception as e:
                    pass
            
            if not next_button_found:
                print(f"  [마지막 페이지]")
                break
            
            page_idx += 1
            time.sleep(SLEEP_SEC)
    
    finally:
        driver.quit()
    
    print(f"\n{'='*60}")
    print(f"[{category_name}] 크롤링 완료!")
    print(f"총 {page_idx}개 페이지, {total_files}개 파일 처리")
    print(f"저장 위치: {os.path.abspath(out_dir)}")
    print(f"{'='*60}\n")

def show_menu():
    print("\n" + "="*60)
    print("우리은행 문서 크롤러")
    print("="*60)
    print("\n크롤링할 카테고리를 선택하세요:")
    print()
    
    for key, target in CRAWL_TARGETS.items():
        print(f"  {key}. {target['name']}")
    
    print(f"  7. 전체 크롤링")
    print(f"  0. 종료")
    print()

def main():
    while True:
        show_menu()
        choice = input("선택 (번호 입력): ").strip()
        
        if choice == "0":
            print("\n프로그램을 종료합니다.")
            break
        
        elif choice == "7":
            print("\n전체 카테고리 크롤링을 시작합니다...\n")
            for key, target in CRAWL_TARGETS.items():
                try:
                    crawl_with_selenium(target["url"], target["folder"], target["name"])
                    time.sleep(2)
                except Exception as e:
                    print(f"\n! [{target['name']}] 크롤링 중 오류 발생: {e}\n")
            
            print("\n" + "="*60)
            print("전체 크롤링 완료!")
            print("="*60 + "\n")
            break
        
        elif choice in CRAWL_TARGETS:
            target = CRAWL_TARGETS[choice]
            try:
                crawl_with_selenium(target["url"], target["folder"], target["name"])
            except Exception as e:
                print(f"\n! 크롤링 중 오류 발생: {e}\n")
            
            cont = input("\n다른 카테고리를 크롤링하시겠습니까? (y/n): ").strip().lower()
            if cont != 'y':
                break
        
        else:
            print("\n잘못된 선택입니다. 다시 선택해주세요.")

if __name__ == "__main__":
    main()
