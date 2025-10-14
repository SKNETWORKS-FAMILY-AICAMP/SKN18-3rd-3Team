#쿠팡 고객센터 FAQ 크롤링
#실행시 자동으로 고객센터 크롤링 하도록 만들어 놨음(전부 끌어옴)
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException
import time
import pandas as pd
import re

def setup_driver():
    """크롬 드라이버 설정"""
    chrome_options = Options()
    # chrome_options.add_argument('--headless')  # 디버깅 시에는 주석 처리
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def extract_category_and_question(text):
    """텍스트에서 카테고리와 질문 분리"""
    # "Q[카테고리] 질문..." 형태 파싱
    match = re.match(r'Q\[(.*?)\]\s*(.*)', text)
    if match:
        category = match.group(1)
        question = match.group(2)
        return category, question
    return "", text

def click_all_load_more_buttons(driver):
    """모든 '더보기' 버튼을 클릭하여 FAQ 전체 로드"""
    print("\n[더보기 버튼 클릭 중...]")
    
    click_count = 0
    max_attempts = 50  # 최대 50번 클릭 시도
    
    for attempt in range(max_attempts):
        try:
            # 다양한 '더보기' 버튼 선택자
            load_more_selectors = [
                "button:contains('더보기')",
                "a:contains('더보기')",
                "button[class*='more']",
                "a[class*='more']",
                "button[class*='load']",
                "div[class*='more']",
                "*[class*='loadMore']",
                "*[class*='load-more']"
            ]
            
            button_found = False
            
            # 각 선택자로 버튼 찾기
            for selector in load_more_selectors:
                try:
                    # 텍스트로 찾기
                    buttons = driver.find_elements(By.XPATH, "//*[contains(text(), '더보기') or contains(text(), '더 보기') or contains(text(), 'more') or contains(text(), 'More')]")
                    
                    if buttons:
                        for btn in buttons:
                            try:
                                if btn.is_displayed() and btn.is_enabled():
                                    # 스크롤하여 버튼이 보이도록
                                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                                    time.sleep(0.5)
                                    
                                    # 클릭
                                    try:
                                        btn.click()
                                    except:
                                        driver.execute_script("arguments[0].click();", btn)
                                    
                                    click_count += 1
                                    print(f"  더보기 버튼 클릭: {click_count}번째")
                                    time.sleep(1.5)  # 로딩 대기
                                    button_found = True
                                    break
                            except:
                                continue
                    
                    if button_found:
                        break
                        
                except:
                    continue
            
            # 더 이상 버튼을 찾을 수 없으면 종료
            if not button_found:
                print(f"  ✓ 더보기 버튼을 모두 클릭했습니다. (총 {click_count}번)")
                break
                
        except Exception as e:
            print(f"  더보기 클릭 중단: {e}")
            break
    
    # 페이지가 완전히 로드되도록 추가 대기
    time.sleep(2)
    return click_count

def crawl_coupang_faq(url, max_items=None):
    """쿠팡 FAQ 크롤링"""
    driver = setup_driver()
    faq_data = []
    
    try:
        print(f"페이지 접속 중: {url}")
        driver.get(url)
        
        print("페이지 로딩 대기 중 (5초)...")
        time.sleep(5)
        
        # 모든 더보기 버튼 클릭
        click_all_load_more_buttons(driver)
        
        print("\n[FAQ 항목 찾는 중...]")
        
        # li 태그 중에서 "Q["로 시작하는 항목만 필터링
        list_items = driver.find_elements(By.TAG_NAME, "li")
        faq_items = []
        
        for item in list_items:
            try:
                text = item.text.strip()
                if text.startswith("Q["):
                    faq_items.append(item)
            except:
                continue
        
        print(f"✓ 총 {len(faq_items)}개의 FAQ 항목 발견")
        
        if max_items:
            faq_items = faq_items[:max_items]
            print(f"  (최대 {max_items}개만 처리합니다)")
        
        # 각 FAQ 항목 처리
        for idx, item in enumerate(faq_items, 1):
            try:
                # 스크롤하여 요소를 화면 중앙에 위치
                driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", item)
                time.sleep(0.3)
                
                # 질문 텍스트 가져오기
                question_full = item.text.strip()
                category, question = extract_category_and_question(question_full)
                
                print(f"\n[{idx}/{len(faq_items)}] [{category}] {question[:60]}...")
                
                # 클릭 가능한 요소 찾기 (a, button, div 등)
                clickable = None
                for selector in ["a", "button", "div[role='button']", "div"]:
                    try:
                        clickable = item.find_element(By.CSS_SELECTOR, selector)
                        if clickable:
                            break
                    except:
                        continue
                
                if not clickable:
                    clickable = item
                
                # 클릭하여 답변 열기
                try:
                    clickable.click()
                except ElementClickInterceptedException:
                    # JavaScript로 클릭 시도
                    driver.execute_script("arguments[0].click();", clickable)
                
                time.sleep(1.5)
                
                # 답변 찾기 - 여러 방법 시도
                answer_text = ""
                
                # 방법 1: 형제 요소에서 답변 찾기
                try:
                    siblings = driver.find_elements(By.XPATH, f"//li[contains(text(), '{question[:30]}')]/following-sibling::*")
                    for sibling in siblings[:3]:
                        text = sibling.text.strip()
                        if text and not text.startswith("Q[") and len(text) > 20:
                            answer_text = text
                            break
                except:
                    pass
                
                # 방법 2: 부모의 다음 형제에서 찾기
                if not answer_text:
                    try:
                        parent = item.find_element(By.XPATH, "./..")
                        next_element = parent.find_element(By.XPATH, "./following-sibling::*[1]")
                        answer_text = next_element.text.strip()
                    except:
                        pass
                
                # 방법 3: 확장된 콘텐츠 영역 찾기
                if not answer_text:
                    try:
                        # 일반적인 답변 영역 클래스명들
                        for selector in [
                            "div[class*='answer']",
                            "div[class*='content']",
                            "div[class*='detail']",
                            "div[class*='description']",
                            "p",
                            "div"
                        ]:
                            try:
                                answer_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                                for el in answer_elements:
                                    text = el.text.strip()
                                    # 질문이 아니고, 충분히 긴 텍스트
                                    if (text and not text.startswith("Q[") and 
                                        text != question and len(text) > 20 and
                                        text not in question_full):
                                        # 화면에 보이는 요소인지 확인
                                        if el.is_displayed():
                                            answer_text = text
                                            break
                                if answer_text:
                                    break
                            except:
                                continue
                    except:
                        pass
                
                # 결과 저장
                if answer_text:
                    # 질문과 동일한 텍스트가 포함되어 있으면 제거
                    if question_full in answer_text:
                        answer_text = answer_text.replace(question_full, "").strip()
                    
                    print(f"  ✓ 답변 추출 성공 ({len(answer_text)}자)")
                    faq_data.append({
                        '번호': idx,
                        '카테고리': category,
                        '질문': question,
                        '답변': answer_text
                    })
                else:
                    print(f"  ✗ 답변을 찾을 수 없음")
                    # 답변이 없어도 질문은 저장
                    faq_data.append({
                        '번호': idx,
                        '카테고리': category,
                        '질문': question,
                        '답변': '답변을 찾을 수 없음'
                    })
                
                # 다시 클릭하여 닫기 (선택적)
                try:
                    clickable.click()
                    time.sleep(0.3)
                except:
                    pass
                    
            except Exception as e:
                print(f"  ✗ 오류: {e}")
                continue
        
        print(f"\n✓ 총 {len(faq_data)}개 항목 처리 완료")
            
    except Exception as e:
        print(f"\n크롤링 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        print("\n5초 후 브라우저를 닫습니다...")
        time.sleep(5)
        driver.quit()
    
    return faq_data

def save_to_csv(data, filename='coupang_faq.csv'):
    """데이터를 CSV 파일로 저장"""
    if data:
        df = pd.DataFrame(data)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"\n{'='*60}")
        print(f"✓ 데이터가 '{filename}' 파일로 저장되었습니다.")
        print(f"✓ 총 {len(data)}개의 FAQ가 수집되었습니다.")
        
        # 카테고리별 통계
        if '카테고리' in df.columns:
            print(f"\n[카테고리별 통계]")
            category_counts = df['카테고리'].value_counts()
            for cat, count in category_counts.head(10).items():
                print(f"  {cat}: {count}개")
        
        return True
    else:
        print("\n✗ 저장할 데이터가 없습니다.")
        return False

def save_to_excel(data, filename='coupang_faq.xlsx'):
    """데이터를 Excel 파일로 저장"""
    if data:
        df = pd.DataFrame(data)
        df.to_excel(filename, index=False, engine='openpyxl')
        print(f"✓ Excel 파일도 '{filename}'로 저장되었습니다.")

def main():
    url = "https://mc.coupang.com/ssr/desktop/contact/faq"
    
    print("=" * 60)
    print("쿠팡 FAQ 크롤링 시작")
    print("=" * 60)
    
    # 전체 FAQ 수집
    print("\n※ 모든 FAQ를 수집합니다. (더보기 버튼 자동 클릭)\n")
    
    faq_data = crawl_coupang_faq(url, max_items=None)
    
    if faq_data:
        save_to_csv(faq_data)
        
        # Excel 저장 시도 (openpyxl이 설치되어 있으면)
        try:
            save_to_excel(faq_data)
        except:
            pass
        
        # 결과 미리보기
        print("\n" + "=" * 60)
        print("[수집된 데이터 미리보기]")
        print("=" * 60)
        for item in faq_data[:3]:
            print(f"\n[{item['번호']}] 카테고리: {item['카테고리']}")
            print(f"질문: {item['질문']}")
            print(f"답변: {item['답변'][:200]}...")
            print("-" * 60)
    else:
        print("\n" + "=" * 60)
        print("FAQ 데이터 수집 실패")
        print("=" * 60)

if __name__ == "__main__":
    main()