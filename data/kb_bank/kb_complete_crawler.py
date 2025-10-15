#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KB Bank 완전한 크롤러
실제 웹사이트 메뉴 구조를 따라가는 방식으로 구현
메인페이지 -> 금융상품 -> 예금/대출 -> 각 서브카테고리 -> 상품들 -> 약관/상품설명서 -> PDF 다운로드
"""
import asyncio
import json
import re
import os
from pathlib import Path
from playwright.async_api import async_playwright
import time
from datetime import datetime
import urllib.parse

class KBBankCompleteCrawler:
    def __init__(self):
        self.main_url = "https://www.kbstar.com"
        self.obank_url = "https://obank.kbstar.com"
        
        # 수집된 데이터
        self.all_products = []
        self.pdfs_downloaded = []
        self.failed_products = []
        self.navigation_errors = []
        
        # 디렉토리 설정
        self.output_dir = Path("./downloads/kb_complete")
        self.products_dir = self.output_dir / "products"
        self.pdfs_dir = self.output_dir / "pdfs"
        self.screenshots_dir = self.output_dir / "screenshots"
        
        # 디렉토리 생성
        for dir_path in [self.output_dir, self.products_dir, self.pdfs_dir, self.screenshots_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
            
        # 직접 URL 및 카테고리 정의
        self.navigation_paths = {
            "예금": {
                "direct_url": "https://obank.kbstar.com/quics?page=C016613",
                "categories": ["예금", "적금", "입출금자유", "주택청약"]
            },
            "대출": {
                "direct_url": "https://obank.kbstar.com/quics?page=C103429",
                "categories": ["신용대출", "담보대출", "전월세/반환보증", "자동차대출", "집단중도금/이주비대", "주택도시기금대출"]
            }
        }

    async def crawl_complete_website(self):
        """완전한 웹사이트 크롤링"""
        print("🏦 KB Bank 완전한 크롤러 시작 (실제 메뉴 네비게이션)")
        print("=" * 80)
        
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=False,  # 디버깅을 위해 브라우저를 보이게 함
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor'
                ]
            )
            
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080}
            )
            
            # 자동화 탐지 우회
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
                
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
                
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['ko-KR', 'ko', 'en-US', 'en'],
                });
                
                window.chrome = {
                    runtime: {}
                };
            """)
            
            page = await context.new_page()
            
            try:
                # 각 주요 카테고리 처리 (직접 URL로)
                for main_category, nav_info in self.navigation_paths.items():
                    print(f"\n🎯 {main_category} 카테고리 크롤링 시작")
                    await self.process_main_category(page, main_category, nav_info)
                
                # 최종 요약 저장
                await self.save_final_summary()
                
                print(f"\n🎉 전체 크롤링 완료!")
                print(f"   - 수집된 상품: {len(self.all_products)}개")
                print(f"   - 다운로드된 PDF: {len(self.pdfs_downloaded)}개")
                print(f"   - 실패한 상품: {len(self.failed_products)}개")
                print(f"   - 네비게이션 오류: {len(self.navigation_errors)}개")
                
            except Exception as e:
                print(f"❌ 전체 크롤링 오류: {e}")
                import traceback
                traceback.print_exc()
            
            finally:
                # 잠시 대기 후 종료 (디버깅용)
                await asyncio.sleep(3)
                await browser.close()

    async def go_to_main_page(self, page):
        """메인 페이지로 이동"""
        print("📍 메인 페이지 접속 중...")
        await page.goto(self.main_url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)
        
        # 스크린샷 저장
        await page.screenshot(path=str(self.screenshots_dir / "01_main_page.png"))
        print(f"   ✅ 메인 페이지 로드 완료: {page.url}")

    async def process_main_category(self, page, category_name, nav_info):
        """메인 카테고리 처리 (직접 URL로 접근)"""
        try:
            print(f"\n📍 {category_name} 직접 페이지 접근")
            
            # 1. 직접 URL로 이동
            direct_url = nav_info["direct_url"]
            print(f"   🔗 URL: {direct_url}")
            await page.goto(direct_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(5)
            
            # 스크린샷 저장
            await page.screenshot(path=str(self.screenshots_dir / f"{category_name}_page.png"))
            print(f"   ✅ {category_name} 페이지 로드 완료")
            
            # 2. 각 서브카테고리 처리
            for sub_category in nav_info["categories"]:
                print(f"\n   🎯 {sub_category} 서브카테고리 처리")
                await self.process_sub_category(page, category_name, sub_category)
                
                # 서브카테고리 간 대기
                await asyncio.sleep(3)
                
        except Exception as e:
            error_info = {
                "category": category_name,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            self.navigation_errors.append(error_info)
            print(f"   ❌ {category_name} 카테고리 처리 오류: {e}")

    # 불필요한 네비게이션 함수들 제거 (직접 URL 사용)
    # async def click_financial_products_menu(self, page): - 제거됨
    # async def click_category_menu(self, page, category): - 제거됨  
    # async def click_target_page(self, page, target): - 제거됨

    async def process_sub_category(self, page, main_category, sub_category):
        """서브카테고리 처리 (페이지네이션 포함)"""
        try:
            # 1. li class로 서브카테고리 찾기 (탭 클릭 없이)
            sub_category_found = await self.find_sub_category_by_li_class(page, sub_category)
            
            if not sub_category_found:
                print(f"     ⚠️ {sub_category} 서브카테고리를 찾을 수 없음")
                return
            
            await asyncio.sleep(2)
            
            # 2. 페이지네이션 처리 - 모든 페이지 파악 후 순차 처리
            total_pages = await self.get_total_pages(page)
            print(f"\n     📚 총 {total_pages}개 페이지 발견")
            
            total_products_processed = 0
            
            for current_page in range(1, total_pages + 1):
                print(f"\n     📚 페이지 {current_page}/{total_pages} 처리 중...")
                
                # 현재 페이지가 아니면 해당 페이지로 이동
                if current_page > 1:
                    moved = await self.go_to_page(page, current_page)
                    if not moved:
                        print(f"     ❌ 페이지 {current_page} 이동 실패")
                        continue
                    await asyncio.sleep(3)
                
                # 3. 현재 페이지의 상품 목록 수집
                products = await self.collect_products_from_page(page, main_category, sub_category)
                print(f"     ✅ {sub_category} (페이지 {current_page}/{total_pages}): {len(products)}개 상품 발견")
                
                # 4. 각 상품 처리
                for i, product in enumerate(products):
                    print(f"       📄 상품 {i+1}/{len(products)}: {product.get('name', 'Unknown')[:30]}...")
                    success = await self.process_individual_product(page, product, main_category, sub_category)
                    
                    if success:
                        print(f"       ✅ 성공: {product.get('name', '')[:30]}")
                        total_products_processed += 1
                    else:
                        print(f"       ❌ 실패: {product.get('name', '')[:30]}")
                        self.failed_products.append(product)
                    
                    await asyncio.sleep(2)
            
            print(f"\n     🎯 {sub_category} 전체 완료: 총 {total_products_processed}개 상품 처리")
                    
        except Exception as e:
            print(f"     ❌ {sub_category} 처리 오류: {e}")

    async def find_sub_category_by_li_class(self, page, sub_category):
        """서브카테고리 li 내의 a 탭 클릭하여 상품 목록 로드"""
        print(f"       🔍 '{sub_category}' 탭 찾는 중...")
        
        try:
            # li > a 태그를 찾아서 클릭
            clicked = await page.evaluate(f"""
                () => {{
                    const categoryName = '{sub_category}';
                    // ul.tabMenu 내의 li 요소들 찾기
                    const listItems = document.querySelectorAll('ul.tabMenu li, ul#tabMenutabMain li');
                    
                    for (const li of listItems) {{
                        const aTag = li.querySelector('a');
                        if (!aTag) continue;
                        
                        const text = aTag.textContent?.trim() || '';
                        const onclick = aTag.getAttribute('onclick') || '';
                        
                        // 텍스트에 카테고리명이 포함되어 있으면 클릭
                        if (text.includes(categoryName)) {{
                            console.log(`Found tab: ${{text}}, onclick: ${{onclick}}`);
                            aTag.click();
                            return true;
                        }}
                    }}
                    return false;
                }}
            """)
            
            if clicked:
                print(f"       ✅ '{sub_category}' 탭 클릭 성공")
                await asyncio.sleep(3)  # 상품 목록 로드 대기
                return True
            else:
                print(f"       ⚠️ '{sub_category}' 탭을 찾을 수 없음")
                return False
                
        except Exception as e:
            print(f"       ❌ 탭 클릭 오류: {e}")
            return False
    
    async def ensure_sub_category_tab_active(self, page, sub_category):
        """서브카테고리 탭이 활성화되어 있는지 확인하고, 필요시 다시 클릭"""
        try:
            # 현재 활성화된 탭 확인
            is_active = await page.evaluate(f"""
                () => {{
                    const categoryName = '{sub_category}';
                    const listItems = document.querySelectorAll('ul.tabMenu li, ul#tabMenutabMain li');
                    
                    for (const li of listItems) {{
                        const aTag = li.querySelector('a');
                        if (!aTag) continue;
                        
                        const text = aTag.textContent?.trim() || '';
                        if (text.includes(categoryName)) {{
                            // 'on' 클래스나 'selected' 클래스가 있는지 확인
                            return li.classList.contains('on') || li.classList.contains('selected') || 
                                   aTag.classList.contains('on') || aTag.classList.contains('selected');
                        }}
                    }}
                    return false;
                }}
            """)
            
            # 활성화되어 있지 않으면 다시 클릭
            if not is_active:
                print(f"         🔄 '{sub_category}' 탭 재활성화 중...")
                await self.find_sub_category_by_li_class(page, sub_category)
                
        except Exception as e:
            print(f"         ⚠️ 탭 상태 확인 오류: {e}")
    
    async def get_total_pages(self, page):
        """.pagenate 영역에서 총 페이지 수 파악"""
        try:
            total_pages = await page.evaluate("""
                () => {
                    // .pagenate 또는 .paging 영역에서 실제 페이지 번호 버튼들 찾기
                    const paginateArea = document.querySelector('.pagenate, .paging');
                    if (!paginateArea) return 1;
                    
                    // input[type="submit"] 버튼들 찾기
                    const buttons = paginateArea.querySelectorAll('input[type="submit"]');
                    if (buttons.length === 0) return 1;
                    
                    // 실제 페이지 번호들만 추출 (value가 숫자인 것들)
                    const pageNumbers = [];
                    buttons.forEach(btn => {
                        const value = btn.getAttribute('value');
                        if (value && !isNaN(value)) {
                            const pageNum = parseInt(value);
                            if (pageNum > 0 && !pageNumbers.includes(pageNum)) {
                                pageNumbers.push(pageNum);
                            }
                        }
                    });
                    
                    // 가장 큰 페이지 번호를 총 페이지 수로 반환
                    return pageNumbers.length > 0 ? Math.max(...pageNumbers) : 1;
                }
            """)
            
            return max(1, total_pages)
            
        except Exception as e:
            print(f"     ⚠️ 페이지 수 파악 오류: {e}")
            return 1
    
    async def go_to_page(self, page, page_number):
        """특정 페이지로 이동"""
        try:
            # 먼저 현재 페이지가 목표 페이지인지 확인
            result = await page.evaluate(f"""
                () => {{
                    const pageNum = {page_number};
                    
                    // input[type="submit"] 타입의 페이지 버튼들 찾기
                    const pageButtons = document.querySelectorAll('input[type="submit"]');
                    
                    for (const btn of pageButtons) {{
                        const value = btn.getAttribute('value');
                        const title = btn.getAttribute('title') || '';
                        
                        // 현재 페이지 확인
                        if (value == pageNum.toString() && title.includes('현재')) {{
                            console.log(`Already on page ${{pageNum}}`);
                            return 'already';
                        }}
                        
                        // 클릭 가능한 페이지 버튼 찾기
                        if (value == pageNum.toString() && !title.includes('현재')) {{
                            console.log(`Clicking page ${{pageNum}}, title: ${{title}}`);
                            btn.click();
                            return 'clicked';
                        }}
                    }}
                    
                    return 'notfound';
                }}
            """)
            
            if result == 'already':
                print(f"     ✅ 이미 페이지 {page_number}에 있음")
                return True
            elif result == 'clicked':
                print(f"     ➡️ 페이지 {page_number}로 이동 중...")
                # 페이지 재로드 대기 (hidden input "현재페이지" 값이 변경되고 페이지가 reload됨)
                await page.wait_for_load_state('domcontentloaded', timeout=10000)
                await asyncio.sleep(2)  # 추가 안정화 대기
                print(f"     ✅ 페이지 {page_number} 로드 완료")
                return True
            else:
                print(f"     ❌ 페이지 {page_number} 버튼을 찾을 수 없음")
                return False
            
        except Exception as e:
            print(f"     ❌ 페이지 이동 오류: {e}")
            return False

    # 조회 버튼 클릭 함수 제거
    # async def click_search_button(self, page): - 제거됨

    async def collect_products_from_page(self, page, main_category, sub_category):
        """페이지에서 상품 목록 수집"""
        products = []
        
        try:
            # 다양한 상품 선택자 시도
            product_selectors = [
                ".product-list li",
                ".prod-list li", 
                ".list-item",
                "ul li:has(a[onclick*='dtl'])",
                "li:has(a.title)",
                "[class*='product']:has(a)",
                "div:has(strong):has(a)"
            ]
            
            for selector in product_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        print(f"         ✓ {selector}: {len(elements)}개 요소 발견")
                        
                        for i, element in enumerate(elements):
                            product_info = await self.extract_product_info_from_element(
                                element, i, main_category, sub_category
                            )
                            if product_info and self.is_valid_product(product_info):
                                # 중복 제거
                                existing_names = [p.get("name", "") for p in products]
                                if product_info["name"] not in existing_names:
                                    products.append(product_info)
                        
                        if products:
                            break  # 상품을 찾았으면 중단
                except:
                    continue
            
            # JavaScript로 onclick 요소들 찾기
            if not products:
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
                
                for i, js_product in enumerate(js_products):
                    if self.is_valid_product_name(js_product["name"]):
                        product_info = {
                            "index": i,
                            "name": js_product["name"][:100],
                            "link_onclick": js_product["onclick"],
                            "link_href": js_product["href"],
                            "main_category": main_category,
                            "sub_category": sub_category,
                            "found_method": "javascript"
                        }
                        products.append(product_info)
                        
        except Exception as e:
            print(f"         상품 수집 오류: {e}")
        
        return products

    async def extract_product_info_from_element(self, element, index, main_category, sub_category):
        """요소에서 상품 정보 추출"""
        try:
            product_info = {
                "index": index,
                "name": "",
                "link_onclick": "",
                "link_href": "",
                "main_category": main_category,
                "sub_category": sub_category,
                "text_content": ""
            }
            
            # 상품명 추출
            name_selectors = ["a.title", "a", "strong", ".title", "h3", "h4", ".product-name"]
            
            for selector in name_selectors:
                try:
                    name_el = await element.query_selector(selector)
                    if name_el:
                        name_text = await name_el.inner_text()
                        if name_text and 2 < len(name_text.strip()) < 200:
                            product_info["name"] = name_text.strip()
                            
                            # 링크 정보 추출
                            href = await name_el.get_attribute("href")
                            onclick = await name_el.get_attribute("onclick")
                            
                            if href:
                                product_info["link_href"] = href
                            if onclick:
                                product_info["link_onclick"] = onclick
                            
                            break
                except:
                    continue
            
            # 전체 텍스트 추출
            try:
                full_text = await element.inner_text()
                product_info["text_content"] = full_text[:500] if full_text else ""
            except:
                pass
            
            return product_info if product_info["name"] else None
            
        except:
            return None

    def is_valid_product(self, product_info):
        """유효한 상품인지 확인"""
        name = product_info.get("name", "").strip()
        return self.is_valid_product_name(name)

    def is_valid_product_name(self, name):
        """유효한 상품명인지 확인"""
        if not name or len(name) < 3:
            return False
        
        # 필터링할 키워드들
        invalid_keywords = [
            "로그인", "회원가입", "메뉴", "전체", "닫기", "이전", "다음", "HOME",
            "죄송합니다", "Sorry", "Error", "404", "Not Found", "[확인]", "[OK]",
            "클릭", "버튼", "링크", "페이지"
        ]
        
        return not any(keyword in name for keyword in invalid_keywords)

    async def process_individual_product(self, page, product, main_category, sub_category):
        """개별 상품 처리"""
        try:
            original_url = page.url
            
            # 상품 상세 페이지로 이동
            if not await self.navigate_to_product_detail(page, product):
                return False
            
            await asyncio.sleep(3)
            
            # 로그인 체크
            if "login" in page.url.lower():
                print("         ⚠️ 로그인 필요 - 건너뜀")
                await page.go_back(wait_until="domcontentloaded")
                await asyncio.sleep(2)
                return False
            
            # 상세 정보 수집
            detailed_info = await self.extract_detailed_product_info(page, product, main_category, sub_category)
            
            # PDF 다운로드
            if detailed_info.get("pdf_links"):
                pdf_count = await self.download_product_pdfs(page, detailed_info, main_category, sub_category)
                print(f"         📄 PDF {pdf_count}개 다운로드")
            
            # 데이터 저장
            await self.save_product_data(detailed_info, main_category, sub_category)
            self.all_products.append(detailed_info)
            
            # 뒤로 가기로 원래 페이지로 돌아가기 (탭 상태 유지)
            await page.go_back(wait_until="domcontentloaded")
            await asyncio.sleep(2)
            
            # 서브카테고리 탭이 여전히 활성화되어 있는지 확인하고, 아니면 다시 클릭
            await self.ensure_sub_category_tab_active(page, sub_category)
            
            return True
            
        except Exception as e:
            print(f"         상품 처리 오류: {e}")
            # 오류 발생 시 원래 URL로 돌아가기
            try:
                if page.url != original_url:
                    await page.goto(original_url, wait_until="domcontentloaded")
                    await asyncio.sleep(2)
                    await self.ensure_sub_category_tab_active(page, sub_category)
            except:
                pass
            return False

    async def navigate_to_product_detail(self, page, product):
        """상품 상세 페이지로 이동"""
        try:
            # 1. onclick JavaScript 실행
            if product.get("link_onclick"):
                onclick_code = product["link_onclick"]
                try:
                    clean_code = onclick_code.replace("return false;", "").strip()
                    if clean_code.endswith(";"):
                        clean_code = clean_code[:-1]
                    
                    await page.evaluate(f"() => {{ {clean_code} }}")
                    await page.wait_for_load_state("domcontentloaded", timeout=10000)
                    return True
                except Exception as e:
                    print(f"         JavaScript 실행 실패: {e}")
            
            # 2. href 링크 사용
            if product.get("link_href") and product["link_href"] not in ["#none", "#", ""]:
                href = product["link_href"]
                try:
                    await page.goto(href, wait_until="domcontentloaded")
                    return True
                except Exception as e:
                    print(f"         링크 이동 실패: {e}")
            
            # 3. 상품명으로 클릭 시도
            product_name = product.get("name", "")
            if product_name:
                try:
                    await page.get_by_text(product_name, exact=True).first.click()
                    await page.wait_for_load_state("domcontentloaded", timeout=10000)
                    return True
                except:
                    pass
            
            return False
            
        except Exception as e:
            print(f"         네비게이션 오류: {e}")
            return False

    async def extract_detailed_product_info(self, page, product, main_category, sub_category):
        """상세 상품 정보 추출"""
        detailed_info = {
            "basic_info": product,
            "main_category": main_category,
            "sub_category": sub_category,
            "page_url": page.url,
            "page_title": await page.title(),
            "pdf_links": [],
            "tables": [],
            "interest_rates": [],
            "extracted_at": datetime.now().isoformat()
        }
        
        try:
            # PDF 링크 찾기
            await self.find_pdf_links(page, detailed_info)
            
            # 테이블 데이터 수집
            tables = await page.query_selector_all("table")
            for i, table in enumerate(tables):
                table_data = await self.extract_table_data(table, i)
                if table_data:
                    detailed_info["tables"].append(table_data)
            
            # 금리 정보 추출
            page_text = await page.inner_text("body")
            rate_patterns = [r'(\d+\.\d+)%', r'연\s*(\d+\.\d+)%', r'(\d+\.?\d*)%']
            
            found_rates = []
            for pattern in rate_patterns:
                matches = re.findall(pattern, page_text)
                found_rates.extend(matches)
            
            if found_rates:
                detailed_info["interest_rates"] = list(set(found_rates))
                
        except Exception as e:
            print(f"         상세 정보 추출 오류: {e}")
        
        return detailed_info

    async def find_pdf_links(self, page, detailed_info):
        """약관 탭에서 모든 PDF 링크 찾기"""
        try:
            # 1. 약관·상품설명서 탭 클릭
            terms_tab_clicked = await self.click_terms_tab(page)
            
            if not terms_tab_clicked:
                print("         ⚠️ 약관 탭을 찾을 수 없음")
                return
            
            await asyncio.sleep(2)
            
            # 2. 약관 탭 내의 모든 PDF 링크 찾기
            pdf_links = await page.evaluate("""
                () => {
                    const pdfLinks = [];
                    
                    // 방법 1: href="#none"이고 hidden input이 있는 링크들 찾기
                    const noneLinks = document.querySelectorAll('a[href="#none"][title*="새창열림"]');
                    noneLinks.forEach((link, index) => {
                        const text = link.textContent?.trim() || '';
                        const hiddenInputs = link.querySelectorAll('input[type="hidden"]');
                        
                        const inputs = {};
                        hiddenInputs.forEach(input => {
                            const name = input.getAttribute('name') || '';
                            const value = input.getAttribute('value') || '';
                            if (name && value) {
                                inputs[name] = value;
                            }
                        });
                        
                        if (Object.keys(inputs).length > 0 && text.length > 0) {
                            pdfLinks.push({
                                type: 'hidden_input',
                                text: text,
                                href: '#none',
                                hiddenInputs: inputs,
                                index: index,
                                element_id: 'pdf_link_' + index
                            });
                        }
                    });
                    
                    // 방법 2: 약관 관련 키워드가 있는 링크들 찾기 (단, 탭 링크는 제외)
                    const keywords = ['약관', '상품설명서', 'PDF', '설명서', '특약', '기준서', '안내서'];
                    const allLinks = document.querySelectorAll('a');
                    
                    allLinks.forEach((link, index) => {
                        const text = link.textContent?.trim() || '';
                        const href = link.getAttribute('href') || '';
                        const onclick = link.getAttribute('onclick') || '';
                        const title = link.getAttribute('title') || '';
                        
                        // 탭 링크나 내부 네비게이션 링크는 제외
                        const isTabLink = href.startsWith('#ui') || href.startsWith('#tab');
                        const isNavLink = text === '약관 · 상품설명서' || text === '약관·상품설명서';
                        const hasNoAction = href === '' && onclick === '';
                        
                        // 키워드를 포함하는지 확인
                        const hasKeyword = keywords.some(keyword => text.includes(keyword));
                        
                        // PDF 링크로 추가할 조건: 키워드 포함 AND (href=#none OR onclick 있음) AND 탭/네비게이션 링크 아님
                        if (hasKeyword && text.length > 0 && !isTabLink && !isNavLink && !hasNoAction) {
                            // 중복 제거
                            const existing = pdfLinks.find(p => p.text === text);
                            if (!existing) {
                                const matchedKeyword = keywords.find(keyword => text.includes(keyword));
                                pdfLinks.push({
                                    type: 'keyword',
                                    text: text,
                                    href: href,
                                    onclick: onclick,
                                    title: title,
                                    keyword: matchedKeyword,
                                    index: pdfLinks.length,
                                    element_id: 'keyword_link_' + pdfLinks.length
                                });
                            }
                        }
                    });
                    
                    return pdfLinks;
                }
            """)
            
            print(f"         🔍 발견된 PDF 링크: {len(pdf_links)}개")
            
            detailed_info["pdf_links"] = pdf_links
            
            # PDF 링크 정보 출력
            for i, pdf_link in enumerate(pdf_links):
                print(f"           {i+1}. {pdf_link.get('text', '')[:50]}... ({pdf_link.get('type', 'unknown')})")
                
        except Exception as e:
            print(f"         PDF 링크 찾기 오류: {e}")
    
    async def click_terms_tab(self, page):
        """약관·상품설명서 탭 클릭"""
        try:
            # 다양한 패턴으로 약관 탭 찾기
            tab_selectors = [
                'a[href="#uiProTabCon5"]',
                'a:has-text("약관")',
                'a:has-text("상품설명서")',
                'a:has-text("약관·상품설명서")',
                'a:has-text("약관 · 상품설명서")',
                'a[href*="uiProTabCon"]',
                '*:has-text("약관"):has-text("상품설명서")',
                'li:has(a:has-text("약관"))',
            ]
            
            for selector in tab_selectors:
                try:
                    tab_element = await page.query_selector(selector)
                    if tab_element and await tab_element.is_visible():
                        await tab_element.click()
                        print("         ✅ 약관 탭 클릭 성공")
                        await asyncio.sleep(2)
                        return True
                except:
                    continue
            
            # JavaScript로 직접 찾기
            clicked = await page.evaluate("""
                () => {
                    const elements = Array.from(document.querySelectorAll('*'));
                    const termsTab = elements.find(el => {
                        const text = el.textContent?.trim() || '';
                        const href = el.getAttribute('href') || '';
                        return (
                            (text.includes('약관') && (text.includes('상품설명서') || text.includes('설명서'))) ||
                            href.includes('uiProTabCon5') ||
                            (el.tagName === 'A' && href.includes('uiProTabCon'))
                        ) && el.offsetParent !== null;
                    });
                    
                    if (termsTab) {
                        termsTab.click();
                        return true;
                    }
                    return false;
                }
            """)            
            
            if clicked:
                print("         ✅ JavaScript로 약관 탭 클릭 성공")
                return True
            
            return False
            
        except Exception as e:
            print(f"         약관 탭 클릭 오류: {e}")
            return False

    async def download_product_pdfs(self, page, product_info, main_category, sub_category):
        """상품별 모든 PDF 다운로드 (순차적 처리)"""
        download_count = 0
        
        # PDF 디렉토리 생성
        product_name = product_info.get("basic_info", {}).get("name", "unknown")
        safe_product_name = re.sub(r'[^\w\-_.]', '_', product_name)[:30]
        
        pdf_dir = self.pdfs_dir / main_category / sub_category / safe_product_name
        pdf_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            pdf_links = product_info.get("pdf_links", [])
            # hidden_input 타입만 필터링 (실제 PDF 파일이 있는 것들)
            pdf_links = [link for link in pdf_links if link.get('type') == 'hidden_input']
            print(f"           📄 처리할 PDF: {len(pdf_links)}개")
            
            for i, pdf_info in enumerate(pdf_links):
                popup = None
                try:
                    print(f"           🔍 PDF {i+1}/{len(pdf_links)}: {pdf_info.get('text', '')[:40]}...")
                    
                    # hidden input에서 파일 정보 추출
                    hidden_inputs = pdf_info.get('hiddenInputs', {})
                    if '서식물리파일명' not in hidden_inputs:
                        print(f"             ❌ 파일 정보 없음")
                        continue
                    
                    file_path = hidden_inputs['서식물리파일명']
                    print(f"             📂 파일: {file_path}")
                    
                    # 팝업 대기 설정
                    async with page.expect_popup() as popup_info:
                        # 링크 클릭
                        clicked = await page.evaluate(f"""
                            () => {{
                                const links = Array.from(document.querySelectorAll('a[href="#none"]'));
                                const targetLink = links.find(link => {{
                                    const inputs = link.querySelectorAll('input[type="hidden"]');
                                    let hasTargetFile = false;
                                    inputs.forEach(input => {{
                                        if (input.getAttribute('value') === '{file_path}') {{
                                            hasTargetFile = true;
                                        }}
                                    }});
                                    return hasTargetFile;
                                }});
                                
                                if (targetLink) {{
                                    targetLink.click();
                                    return true;
                                }}
                                return false;
                            }}
                        """)
                        
                        if not clicked:
                            print(f"             ❌ 링크 클릭 실패")
                            continue
                    
                    # 팝업 창 얻기
                    popup = await popup_info.value
                    await popup.wait_for_load_state('load')
                    print(f"             ✅ 팝업 창 열림")
                    await asyncio.sleep(2)
                    
                    # 팝업에서 PDF 다운로드
                    if await self.download_pdf_from_popup(popup, pdf_info, pdf_dir, i):
                        download_count += 1
                        print(f"             ✅ PDF 다운로드 성공")
                    else:
                        print(f"             ❌ PDF 다운로드 실패")
                    
                    # 팝업 닫기
                    if popup and not popup.is_closed():
                        await popup.close()
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    print(f"           PDF 처리 오류: {e}")
                    if popup and not popup.is_closed():
                        await popup.close()
                    continue
                    
        except Exception as e:
            print(f"         PDF 다운로드 전체 오류: {e}")
        
        print(f"         📊 총 {download_count}개 PDF 다운로드 완료")
        return download_count
    
    async def download_pdf_from_popup(self, popup, pdf_info, pdf_dir, index):
        """팝업 창에서 PDF 다운로드"""
        try:
            # 1단계: 다운로드 버튼 찾기
            download_selectors = [
                '#btnDownload',  # 제공된 예제의 ID
                'button.btn-down',  # 제공된 예제의 클래스
                'button:has-text("다운로드")',
                'button[title*="pdf"]',
                'button[title*="PDF"]',
            ]
            
            download_btn = None
            for selector in download_selectors:
                try:
                    btn = await popup.query_selector(selector)
                    if btn and await btn.is_visible():
                        download_btn = btn
                        print(f"             🎯 다운로드 버튼 발견: {selector}")
                        break
                except:
                    continue
            
            if not download_btn:
                print(f"             ❌ 다운로드 버튼을 찾을 수 없음")
                return False
            
            # 2단계: 다운로드 버튼 클릭 (메뉴 표시)
            await download_btn.click()
            await asyncio.sleep(1)
            print(f"             📝 다운로드 메뉴 열림")
            
            # 3단계: 다운로드 메뉴에서 실제 다운로드 링크 찾기
            download_link_selectors = [
                'a[id^="page-DP"]',  # 예제: <a id="page-DP01000938">
                'a:has-text("약관")',
                'a:has-text("설명서")',
                'a:has-text("다운로드")',
                '.download-item a',
                '.pdf-download a'
            ]
            
            download_link = None
            for selector in download_link_selectors:
                try:
                    links = await popup.query_selector_all(selector)
                    for link in links:
                        if await link.is_visible():
                            download_link = link
                            print(f"             🔗 다운로드 링크 발견: {selector}")
                            break
                    if download_link:
                        break
                except:
                    continue
            
            if not download_link:
                print(f"             ❌ 다운로드 링크를 찾을 수 없음")
                return False
            
            # 4단계: 다운로드 링크 클릭하여 실제 다운로드
            async with popup.expect_download(timeout=30000) as download_info:
                await download_link.click()
            
            download = await download_info.value
            
            # 파일명 생성
            if 'hiddenInputs' in pdf_info and '서식명' in pdf_info['hiddenInputs']:
                form_name = pdf_info['hiddenInputs']['서식명'][:50]
                safe_form_name = re.sub(r'[^\w\-_.]', '_', form_name)
                filename = f"{safe_form_name}_{int(time.time())}.pdf"
            else:
                pdf_text = pdf_info.get('text', 'unknown')[:30]
                safe_text = re.sub(r'[^\w\-_.]', '_', pdf_text)
                filename = f"{safe_text}_{int(time.time())}.pdf"
            
            file_path = pdf_dir / filename
            await download.save_as(file_path)
            
            # 다운로드 정보 저장
            pdf_download_info = {
                "original_filename": download.suggested_filename or filename,
                "saved_filename": filename,
                "file_path": str(file_path),
                "pdf_info": pdf_info,
                "downloaded_at": datetime.now().isoformat()
            }
            self.pdfs_downloaded.append(pdf_download_info)
            
            print(f"             💾 저장완료: {filename}")
            return True
            
        except Exception as e:
            print(f"             PDF 다운로드 오류: {e}")
            return False
    

    async def extract_table_data(self, table, index):
        """테이블 데이터 추출"""
        try:
            table_data = {"index": index, "headers": [], "rows": []}
            
            # 헤더 추출
            headers = await table.query_selector_all("th")
            for header in headers:
                text = await header.inner_text()
                if text.strip():
                    table_data["headers"].append(text.strip())
            
            # 행 추출
            rows = await table.query_selector_all("tr")
            for row in rows:
                cells = await row.query_selector_all("td")
                if cells:
                    row_data = []
                    for cell in cells:
                        text = await cell.inner_text()
                        row_data.append(text.strip())
                    if any(cell for cell in row_data):
                        table_data["rows"].append(row_data)
            
            return table_data if table_data["headers"] or table_data["rows"] else None
            
        except:
            return None

    async def save_product_data(self, product_info, main_category, sub_category):
        """상품 데이터 저장"""
        try:
            product_dir = self.products_dir / main_category / sub_category
            product_dir.mkdir(parents=True, exist_ok=True)
            
            product_name = product_info.get("basic_info", {}).get("name", "unknown")
            safe_name = re.sub(r'[^\w\-_.]', '_', product_name)
            
            filename = f"{safe_name}_{int(time.time())}.json"
            file_path = product_dir / filename
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(product_info, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"         데이터 저장 오류: {e}")

    async def save_final_summary(self):
        """최종 요약 저장"""
        summary = {
            "crawl_info": {
                "crawled_at": datetime.now().isoformat(),
                "total_products": len(self.all_products),
                "total_pdfs": len(self.pdfs_downloaded),
                "failed_products": len(self.failed_products),
                "navigation_errors": len(self.navigation_errors)
            },
            "products_by_category": {},
            "failed_products": self.failed_products,
            "navigation_errors": self.navigation_errors,
            "pdfs_downloaded": self.pdfs_downloaded
        }
        
        # 카테고리별 집계
        for product in self.all_products:
            main_cat = product.get("main_category", "unknown")
            sub_cat = product.get("sub_category", "unknown")
            
            if main_cat not in summary["products_by_category"]:
                summary["products_by_category"][main_cat] = {}
            
            if sub_cat not in summary["products_by_category"][main_cat]:
                summary["products_by_category"][main_cat][sub_cat] = []
            
            summary["products_by_category"][main_cat][sub_cat].append({
                "name": product.get("basic_info", {}).get("name", ""),
                "pdf_count": len(product.get("pdf_links", []))
            })
        
        summary_path = self.output_dir / "complete_summary.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 최종 요약 저장: {summary_path}")

# 실행 함수
async def main():
    crawler = KBBankCompleteCrawler()
    await crawler.crawl_complete_website()

if __name__ == "__main__":
    print("🚀 KB Bank 완전한 크롤러 실행 (단순화된 버전)")
    print("   - 예금 페이지: https://obank.kbstar.com/quics?page=C016613")
    print("   - 대출 페이지: https://obank.kbstar.com/quics?page=C103429")
    print("   - 조회 버튼 클릭 제거")
    print("=" * 60)
    asyncio.run(main())
