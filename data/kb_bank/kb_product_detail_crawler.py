#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KB Bank 상품 상세 정보 JSON 저장 크롤러
예금: 유의사항 탭의 '상품내용의 변경에 관한 사항' 추출
대출: 상품안내/금리 및 이율/이용안내/유의사항 및 기타 탭의 모든 정보 추출
"""
import asyncio
import json
import re
import os
from pathlib import Path
from playwright.async_api import async_playwright
import time
from datetime import datetime

class KBProductDetailCrawler:
    def __init__(self):
        self.main_url = "https://www.kbstar.com"
        self.obank_url = "https://obank.kbstar.com"
        
        # JSON 저장 디렉토리
        self.json_dir = Path("./downloads/kb_complete/JSON")
        self._create_json_directories()
        
        # 수집된 데이터
        self.all_products = []
        self.failed_products = []
        
        # 크롤링 대상 정의
        self.navigation_paths = {
            "예금": {
                "direct_url": "https://obank.kbstar.com/quics?page=C016613",
                "categories": ["예금", "적금", "입출금자유", "주택청약"]
            },
            "대출": {
                "direct_url": "https://obank.kbstar.com/quics?page=C103429",
                "categories": ["신용대출", "담보대출", "전월세/반환보증", "자동차대출", 
                            "집단중도금/이주비대출", "주택도시기금대출", "개인사업자대출"]
            }
        }
    
    def _create_json_directories(self):
        """JSON 저장 디렉토리 생성"""
        # 예금 카테고리
        deposit_categories = ["예금", "적금", "입출금자유", "주택청약"]
        for category in deposit_categories:
            (self.json_dir / "예금" / category).mkdir(parents=True, exist_ok=True)
        
        # 대출 카테고리
        loan_categories = [
            "신용대출", "담보대출", "전월세/반환보증", "자동차대출",
            "집단중도금/이주비대출", "주택도시기금대출", "개인사업자대출"
        ]
        for category in loan_categories:
            (self.json_dir / "대출" / category).mkdir(parents=True, exist_ok=True)
        
        print(f"📁 JSON 저장 디렉토리 생성 완료: {self.json_dir}")
    
    async def crawl_all_products(self):
        """전체 상품 크롤링"""
        print("🏦 KB Bank 상품 상세 정보 크롤러 시작")
        print("=" * 80)
        
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=False,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox'
                ]
            )
            
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                viewport={'width': 1920, 'height': 1080}
            )
            
            # 자동화 탐지 우회
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
            """)
            
            page = await context.new_page()
            
            try:
                # 각 메인 카테고리 처리
                for main_category, nav_info in self.navigation_paths.items():
                    print(f"\n🎯 {main_category} 카테고리 크롤링 시작")
                    await self.process_main_category(page, main_category, nav_info)
                
                # 최종 요약
                print(f"\n🎉 크롤링 완료!")
                print(f"   - 수집된 상품: {len(self.all_products)}개")
                print(f"   - 실패한 상품: {len(self.failed_products)}개")
                
            except Exception as e:
                print(f"❌ 크롤링 오류: {e}")
                import traceback
                traceback.print_exc()
            
            finally:
                await asyncio.sleep(2)
                try:
                    await browser.close()
                except:
                    pass
    
    async def process_main_category(self, page, main_category, nav_info):
        """메인 카테고리 처리"""
        try:
            print(f"\n📍 {main_category} 페이지 접근")
            await page.goto(nav_info["direct_url"], wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(5)
            print(f"   ✅ 페이지 로드 완료")
            
            # 각 서브카테고리 처리
            for sub_category in nav_info["categories"]:
                print(f"\n   🎯 {sub_category} 서브카테고리 처리")
                await self.process_sub_category(page, main_category, sub_category)
                await asyncio.sleep(2)
                
        except Exception as e:
            print(f"   ❌ {main_category} 처리 오류: {e}")
    
    async def process_sub_category(self, page, main_category, sub_category):
        """서브카테고리 처리"""
        try:
            # 서브카테고리 탭 클릭
            if not await self.click_sub_category_tab(page, sub_category):
                print(f"     ⚠️ {sub_category} 탭을 찾을 수 없음")
                return
            
            await asyncio.sleep(2)
            
            # 전체 페이지 수 확인
            total_pages = await self.get_total_pages(page)
            print(f"     📚 총 {total_pages}개 페이지 발견")
            
            # 각 페이지 처리
            for current_page in range(1, total_pages + 1):
                print(f"\n     📄 페이지 {current_page}/{total_pages} 처리 중...")
                
                if current_page > 1:
                    if not await self.go_to_page(page, current_page):
                        continue
                    await asyncio.sleep(2)
                
                # 상품 목록 수집
                products = await self.collect_products(page, main_category, sub_category)
                print(f"     ✅ {len(products)}개 상품 발견")
                
                # 각 상품 처리
                for i, product in enumerate(products):
                    print(f"       📦 상품 {i+1}/{len(products)}: {product.get('name', '')[:40]}...")
                    await self.process_product(page, product, main_category, sub_category)
                    await asyncio.sleep(2)
                    
        except Exception as e:
            print(f"     ❌ {sub_category} 처리 오류: {e}")
    
    async def click_sub_category_tab(self, page, sub_category):
        """서브카테고리 탭 클릭"""
        try:
            clicked = await page.evaluate(f"""
                () => {{
                    const categoryName = '{sub_category}';
                    const listItems = document.querySelectorAll('ul.tabMenu li, ul#tabMenutabMain li');
                    
                    for (const li of listItems) {{
                        const aTag = li.querySelector('a');
                        if (!aTag) continue;
                        
                        const text = aTag.textContent?.trim() || '';
                        if (text.includes(categoryName)) {{
                            aTag.click();
                            return true;
                        }}
                    }}
                    return false;
                }}
            """)
            
            if clicked:
                print(f"       ✅ '{sub_category}' 탭 클릭 성공")
                return True
            return False
            
        except Exception as e:
            print(f"       ❌ 탭 클릭 오류: {e}")
            return False
    
    async def get_total_pages(self, page):
        """총 페이지 수 확인"""
        try:
            total_pages = await page.evaluate("""
                () => {
                    const paginateArea = document.querySelector('.pagenate, .paging');
                    if (!paginateArea) return 1;
                    
                    const buttons = paginateArea.querySelectorAll('input[type="submit"]');
                    if (buttons.length === 0) return 1;
                    
                    const pageNumbers = [];
                    buttons.forEach(btn => {
                        const value = btn.getAttribute('value');
                        if (value && !isNaN(value)) {
                            const pageNum = parseInt(value);
                            if (pageNum > 0) pageNumbers.push(pageNum);
                        }
                    });
                    
                    return pageNumbers.length > 0 ? Math.max(...pageNumbers) : 1;
                }
            """)
            return max(1, total_pages)
        except:
            return 1
    
    async def go_to_page(self, page, page_number):
        """특정 페이지로 이동"""
        try:
            result = await page.evaluate(f"""
                () => {{
                    const pageNum = {page_number};
                    const pageButtons = document.querySelectorAll('input[type="submit"]');
                    
                    for (const btn of pageButtons) {{
                        const value = btn.getAttribute('value');
                        const title = btn.getAttribute('title') || '';
                        
                        if (value == pageNum.toString() && !title.includes('현재')) {{
                            btn.click();
                            return 'clicked';
                        }}
                    }}
                    return 'notfound';
                }}
            """)
            
            if result == 'clicked':
                await page.wait_for_load_state('domcontentloaded', timeout=10000)
                await asyncio.sleep(2)
                print(f"       ➡️ 페이지 {page_number} 이동 완료")
                return True
            return False
            
        except Exception as e:
            print(f"       ❌ 페이지 이동 오류: {e}")
            return False
    
    async def collect_products(self, page, main_category, sub_category):
        """페이지에서 상품 목록 수집"""
        products = []
        
        try:
            # JavaScript로 상품 링크 찾기
            js_products = await page.evaluate("""
                () => {
                    const products = [];
                    const clickableElements = document.querySelectorAll('[onclick]');
                    
                    clickableElements.forEach(el => {
                        const onclick = el.getAttribute('onclick');
                        if (onclick && onclick.includes('dtl')) {
                            const text = el.innerText || el.textContent || '';
                            if (text.trim().length > 2) {
                                products.push({
                                    name: text.trim(),
                                    onclick: onclick,
                                    href: el.href || ''
                                });
                            }
                        }
                    });
                    return products;
                }
            """)
            
            for product in js_products:
                if len(product["name"]) > 3:
                    products.append({
                        "name": product["name"][:100],
                        "onclick": product["onclick"],
                        "href": product["href"],
                        "main_category": main_category,
                        "sub_category": sub_category
                    })
                    
        except Exception as e:
            print(f"         상품 수집 오류: {e}")
        
        return products
    
    async def process_product(self, page, product, main_category, sub_category):
        """개별 상품 처리"""
        try:
            original_url = page.url
            
            # 상품 상세 페이지로 이동
            if not await self.navigate_to_product_detail(page, product):
                print(f"         ❌ 상세 페이지 이동 실패")
                return False
            
            await asyncio.sleep(3)
            
            # 로그인 체크
            if "login" in page.url.lower():
                print(f"         ⚠️ 로그인 필요 - 건너뜀")
                await page.go_back(wait_until="domcontentloaded")
                return False
            
            # 상품 상세 정보 추출
            if main_category == "예금":
                product_details = await self.extract_deposit_product_tabs(page)
            elif main_category == "대출":
                product_details = await self.extract_loan_product_tabs(page)
            else:
                product_details = {}
            
            # JSON 저장
            if product_details:
                await self.save_product_json(product, product_details, main_category, sub_category, page.url)
                print(f"         ✅ JSON 저장 완료")
                self.all_products.append(product)
            else:
                print(f"         ⚠️ 추출된 정보 없음")
            
            # 뒤로 가기
            await page.go_back(wait_until="domcontentloaded")
            await asyncio.sleep(2)
            
            # 탭 재활성화
            await self.click_sub_category_tab(page, sub_category)
            
            return True
            
        except Exception as e:
            print(f"         ❌ 상품 처리 오류: {e}")
            self.failed_products.append(product)
            return False
    
    async def navigate_to_product_detail(self, page, product):
        """상품 상세 페이지로 이동"""
        try:
            # onclick 실행
            if product.get("onclick"):
                onclick_code = product["onclick"]
                clean_code = onclick_code.replace("return false;", "").strip()
                if clean_code.endswith(";"):
                    clean_code = clean_code[:-1]
                
                await page.evaluate(f"() => {{ {clean_code} }}")
                await page.wait_for_load_state("domcontentloaded", timeout=10000)
                return True
            
            # href 링크 사용
            if product.get("href") and product["href"] not in ["#none", "#", ""]:
                await page.goto(product["href"], wait_until="domcontentloaded")
                return True
            
            return False
            
        except Exception as e:
            print(f"         네비게이션 오류: {e}")
            return False
    
    async def extract_deposit_product_tabs(self, page):
        """예금 상품의 상세 탭 정보 추출 (유의사항 탭의 '상품내용의 변경에 관한 사항')"""
        try:
            print(f"         📝 예금 상품 상세 정보 추출 중...")
            
            # 유의사항 탭 (#uiProTabCon3) 클릭
            notice_tab_clicked = await page.evaluate("""
                () => {
                    // 유의사항 탭은 #uiProTabCon3을 가리키는 링크
                    const noticeTab = document.querySelector('a[href="#uiProTabCon3"]');
                    if (noticeTab) {
                        noticeTab.click();
                        return true;
                    }
                    return false;
                }
            """)
            
            if not notice_tab_clicked:
                print(f"         ⚠️ 유의사항 탭을 찾을 수 없음")
                return {}
            
            await asyncio.sleep(2)
            
            # #uiProTabCon3 컨테이너에서 모든 '상품내용의 변경에 관한 사항' 추출
            product_change_info = await page.evaluate("""
                () => {
                    const results = [];  // 배열로 변경
                    
                    // #uiProTabCon3 컨테이너 찾기
                    const tabContent = document.querySelector('#uiProTabCon3');
                    if (!tabContent) {
                        console.log('유의사항 탭 컨테이너를 찾을 수 없음');
                        return results;
                    }
                    
                    // 모든 strong.tit 태그 찾기 (class="tit"이 있는 strong)
                    const strongElements = tabContent.querySelectorAll('strong.tit, strong');
                    
                    for (const strong of strongElements) {
                        const text = strong.textContent?.trim() || '';
                        
                        // '상품내용 변경' 찾기 (다양한 형태 지원)
                        if (text.includes('상품내용 변경') || 
                            text.includes('상품내용변경') ||
                            text.includes('상품 내용 변경') ||
                            text.includes('상품내용의 변경') ||
                            text.includes('상품내용의변경')) {
                            
                            const item = {
                                title: text,
                                content: '',
                                html: ''
                            };
                            
                            // 내용 추출
                            // 1. strong 다음에 오는 div.infocon 찾기
                            let parentLi = strong.closest('li');
                            if (parentLi) {
                                let infoconDiv = parentLi.querySelector('div.infocon');
                                if (infoconDiv) {
                                    // div.infocon 안의 모든 내용 가져오기
                                    item.content = infoconDiv.textContent?.trim() || '';
                                    item.html = infoconDiv.innerHTML?.trim() || '';
                                }
                            }
                            
                            // 2. 찾지 못했으면 strong 다음 형제 요소들 가져오기
                            if (!item.content) {
                                let parentContainer = strong.parentElement;
                                if (parentContainer) {
                                    let contentParts = [];
                                    let nextElement = parentContainer.nextElementSibling;
                                    
                                    // 다음 형제들을 찾아서 추가 (다른 strong.tit이 나오기 전까지)
                                    while (nextElement) {
                                        // 다른 strong.tit가 나오면 중단
                                        if (nextElement.querySelector('strong.tit')) {
                                            break;
                                        }
                                        contentParts.push(nextElement.textContent?.trim() || '');
                                        nextElement = nextElement.nextElementSibling;
                                    }
                                    
                                    if (contentParts.length > 0) {
                                        item.content = contentParts.join(' ').trim();
                                    }
                                }
                            }
                            
                            // 3. 내용을 찾지 못했으면 부모 전체 텍스트
                            if (!item.content) {
                                const parent = strong.closest('div, section, li');
                                if (parent) {
                                    const fullText = parent.textContent?.trim() || '';
                                    const strongText = strong.textContent?.trim() || '';
                                    if (fullText.length > strongText.length) {
                                        item.content = fullText.replace(strongText, '').trim();
                                    }
                                }
                            }
                            
                            // 내용이 있으면 배열에 추가
                            if (item.content) {
                                results.push(item);
                            }
                        }
                    }
                    
                    return results;
                }
            """)
            
            # 배열로 반환되므로 처리
            if product_change_info and len(product_change_info) > 0:
                print(f"         ✅ 상품내용 변경 정보 추출 성공")
                print(f"            - 총 {len(product_change_info)}개 항목 발견")
                
                # 각 항목의 크기 출력
                for i, item in enumerate(product_change_info, 1):
                    print(f"            - 항목 {i}: {item.get('title', '')[:50]}... (텍스트 {len(item.get('content', ''))} 자)")
                
                return {
                    "notice_tab": {
                        "product_change_info": product_change_info  # 배열 전체를 저장
                    }
                }
            else:
                print(f"         ⚠️ 상품내용 변경 정보를 찾을 수 없음")
                return {}
                
        except Exception as e:
            print(f"         ❌ 예금 상품 탭 정보 추출 오류: {e}")
            return {}
    
    async def extract_loan_product_tabs(self, page):
        """대출 상품의 상세 탭 정보 추출 (상품안내/금리 및 이율/이용안내/유의사항 및 기타)"""
        try:
            print(f"         📝 대출 상품 상세 정보 추출 중...")
            
            tabs_data = {}
            
            # 추출할 탭 목록
            tab_configs = [
                {"name": "상품안내", "href": "#uiProTabCon1"},
                {"name": "금리 및 이율", "href": "#uiProTabCon2"},
                {"name": "이용안내", "href": "#uiProTabCon3"},
                {"name": "유의사항 및 기타", "href": "#uiProTabCon4"}
            ]
            
            for tab_config in tab_configs:
                tab_name = tab_config["name"]
                tab_href = tab_config["href"]
                
                # 탭 클릭
                tab_clicked = await page.evaluate(f"""
                    () => {{
                        const tab = document.querySelector('a[href="{tab_href}"]');
                        if (tab) {{
                            tab.click();
                            return true;
                        }}
                        return false;
                    }}
                """)
                
                if not tab_clicked:
                    print(f"         ⚠️ '{tab_name}' 탭을 찾을 수 없음")
                    continue
                
                await asyncio.sleep(1)
                
                # 탭 컨텐츠 추출
                tab_content = await page.evaluate(f"""
                    () => {{
                        const tabPane = document.querySelector('{tab_href}');
                        if (!tabPane) return null;
                        
                        return {{
                            html: tabPane.innerHTML,
                            text: tabPane.textContent?.trim() || ''
                        }};
                    }}
                """)
                
                if tab_content:
                    tabs_data[tab_name] = tab_content
                    print(f"         ✅ '{tab_name}' 탭 정보 추출 성공")
                else:
                    print(f"         ⚠️ '{tab_name}' 탭 컨텐츠를 찾을 수 없음")
            
            return tabs_data
                
        except Exception as e:
            print(f"         ❌ 대출 상품 탭 정보 추출 오류: {e}")
            return {}
    
    async def save_product_json(self, product, product_details, main_category, sub_category, page_url):
        """상품 상세 정보를 JSON 파일로 저장"""
        try:
            # 카테고리별 JSON 디렉토리 결정
            if main_category == "예금":
                json_dir = self.json_dir / "예금" / sub_category
            elif main_category == "대출":
                json_dir = self.json_dir / "대출" / sub_category
            else:
                json_dir = self.json_dir / main_category / sub_category
            
            json_dir.mkdir(parents=True, exist_ok=True)
            
            # 파일명 생성
            product_name = product.get("name", "unknown")
            safe_name = re.sub(r'[^\w\-_.]', '_', product_name)[:50]
            filename = f"{safe_name}_{int(time.time())}.json"
            
            # JSON 데이터 구성
            json_data = {
                "product_name": product_name,
                "main_category": main_category,
                "sub_category": sub_category,
                "page_url": page_url,
                "product_details": product_details,
                "extracted_at": datetime.now().isoformat()
            }
            
            # JSON 파일 저장
            json_file_path = json_dir / filename
            with open(json_file_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            
            print(f"         💾 저장: {json_file_path.name}")
            
        except Exception as e:
            print(f"         ❌ JSON 저장 오류: {e}")


# 실행 함수
async def main():
    crawler = KBProductDetailCrawler()
    await crawler.crawl_all_products()

if __name__ == "__main__":
    print("=" * 80)
    print("🚀 KB Bank 상품 상세 정보 JSON 저장 크롤러")
    print("   📁 저장 위치: downloads/kb_complete/JSON/")
    print("   📋 예금: 유의사항 탭의 '상품내용의 변경에 관한 사항'")
    print("   📋 대출: 상품안내/금리 및 이율/이용안내/유의사항 및 기타")
    print("=" * 80)
    asyncio.run(main())
