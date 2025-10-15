#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KB Bank 약관 탭 링크 디버깅 크롤러
약관·상품설명서 탭을 클릭한 후 모든 링크를 상세히 조사
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

class KBDebugCrawler:
    def __init__(self):
        self.main_url = "https://www.kbstar.com"
        self.obank_url = "https://obank.kbstar.com"

    async def debug_terms_links(self):
        """약관 탭의 모든 링크 상세 분석"""
        print("🔍 KB Bank 약관 탭 링크 디버깅 시작")
        print("="*80)
        
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage", 
                    "--no-sandbox"
                ]
            )
            
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )
            
            page = await context.new_page()
            
            try:
                # 1. 금융상품 페이지로 이동
                financial_url = f"{self.obank_url}/quics?page=C016613"
                print(f"📍 금융상품 페이지 접속: {financial_url}")
                await page.goto(financial_url, wait_until="domcontentloaded")
                await asyncio.sleep(3)
                
                # 2. 예금 탭 클릭
                await self.click_category_tab(page, "예금")
                await asyncio.sleep(3)
                
                # 3. 첫 번째 상품 클릭
                product_clicked = await self.click_first_product(page)
                if not product_clicked:
                    print("   ⚠️  상품 클릭에 실패했지만 현재 페이지에서 링크 분석을 계속합니다.")
                await asyncio.sleep(3)
                
                # 4. 약관상품사용설명서 탭 클릭
                terms_clicked = await self.click_terms_tab(page)
                if not terms_clicked:
                    print("   ⚠️  약관 탭 클릭에 실패했지만 현재 페이지에서 링크 분석을 계속합니다.")
                await asyncio.sleep(3)
                
                # 5. 모든 링크 상세 분석 (실패해도 분석은 진행)
                await self.analyze_all_links(page)
                
            finally:
                # 분석 완료 후 5초 대기 (수동 확인용)
                print("\n⏰ 5초 후 브라우저가 닫힙니다. 페이지를 확인하세요...")
                await asyncio.sleep(5)
                await browser.close()

    async def click_category_tab(self, page, category):
        """카테고리 탭 클릭"""
        js_code = f"""
        () => {{
            const elements = Array.from(document.querySelectorAll('*'));
            const target = elements.find(el => 
                el.textContent && el.textContent.trim() === '{category}' && 
                el.offsetParent !== null &&
                (el.tagName === 'A' || el.tagName === 'BUTTON' || el.tagName === 'LI')
            );
            if (target) {{
                target.click();
                return true;
            }}
            return false;
        }}
        """
        clicked = await page.evaluate(js_code)
        if clicked:
            print(f"   ✅ {category} 탭 클릭 성공")
        else:
            print(f"   ❌ {category} 탭 클릭 실패")

    async def click_first_product(self, page):
        """첫 번째 상품 클릭"""
        try:
            # 먼저 페이지에 있는 모든 상품 링크 조사 (더 넓은 범위로)
            debug_links_js = """
            () => {
                const allElements = Array.from(document.querySelectorAll('*'));
                const productElements = allElements.filter(el => {
                    const onclick = el.getAttribute('onclick') || '';
                    const href = el.getAttribute('href') || '';
                    const text = el.textContent?.trim() || '';
                    const className = el.className || '';
                    
                    // 다양한 패턴으로 상품 링크 찾기
                    return (
                        (
                            onclick.includes('joinDeposit') ||
                            onclick.includes('prcode') || 
                            onclick.includes('상품상세') || 
                            onclick.includes('가입하기') ||
                            href.includes('prcode') ||
                            className.includes('btn') ||
                            text.includes('가입하기') ||
                            text.includes('KB Star') ||
                            text.includes('정기예금') ||
                            text.includes('적금')
                        ) &&
                        text.length > 0 &&
                        el.offsetParent !== null &&
                        (el.tagName === 'A' || el.tagName === 'BUTTON' || onclick !== '')
                    );
                });
                
                return productElements.map((el, idx) => ({
                    index: idx,
                    text: el.textContent.trim().substring(0, 50),
                    onclick: el.getAttribute('onclick') || '',
                    href: el.getAttribute('href') || '',
                    className: el.className || '',
                    tagName: el.tagName
                }));
            }
            """
            
            available_products = await page.evaluate(debug_links_js)
            print(f"   📋 발견된 상품 링크: {len(available_products)}개")
            
            if available_products:
                for i, prod in enumerate(available_products[:5]):  # 상위 5개만 출력
                    print(f"      {i+1}. {prod['text'][:40]} | onclick: {prod['onclick'][:50]}")
            
            # 첫 번째 상품 클릭 시도 (가입하기 버튼 우선 탐색)
            first_product_js = """
            () => {
                const allElements = Array.from(document.querySelectorAll('*'));
                
                // 1순위: 가입하기 버튼 찾기
                let productElement = allElements.find(el => {
                    const text = el.textContent?.trim() || '';
                    const onclick = el.getAttribute('onclick') || '';
                    return (
                        text === '가입하기' &&
                        onclick.includes('joinDeposit') &&
                        el.offsetParent !== null
                    );
                });
                
                // 2순위: onclick에 joinDeposit이 있는 요소
                if (!productElement) {
                    productElement = allElements.find(el => {
                        const onclick = el.getAttribute('onclick') || '';
                        return (
                            onclick.includes('joinDeposit') &&
                            el.offsetParent !== null
                        );
                    });
                }
                
                // 3순위: 상품명 링크 (KB Star, 정기예금 등)
                if (!productElement) {
                    productElement = allElements.find(el => {
                        const text = el.textContent?.trim() || '';
                        const onclick = el.getAttribute('onclick') || '';
                        const href = el.getAttribute('href') || '';
                        return (
                            (text.includes('KB Star') || text.includes('정기예금')) &&
                            (onclick || href) &&
                            el.offsetParent !== null &&
                            el.tagName === 'A'
                        );
                    });
                }
                
                if (productElement) {
                    const onclick = productElement.getAttribute('onclick');
                    const href = productElement.getAttribute('href');
                    
                    // onclick이 있으면 실행, 없으면 클릭
                    if (onclick) {
                        if (onclick.includes('joinDeposit')) {
                            // joinDeposit 함수 직접 실행
                            eval(onclick);
                        } else {
                            let clean_code = onclick.replace('return false;', '').trim();
                            if (clean_code.endsWith(';')) {
                                clean_code = clean_code.slice(0, -1);
                            }
                            eval(clean_code);
                        }
                    } else {
                        productElement.click();
                    }
                    
                    return {
                        success: true,
                        name: productElement.textContent.trim(),
                        onclick: onclick,
                        href: href,
                        tagName: productElement.tagName
                    };
                }
                return { success: false };
            }
            """
            
            result = await page.evaluate(first_product_js)
            if result['success']:
                await asyncio.sleep(2)  # 페이지 로딩 대기
                await page.wait_for_load_state("domcontentloaded", timeout=10000)
                print(f"   ✅ 첫 번째 상품 클릭 성공: {result['name'][:40]}")
                return True
            else:
                print(f"   ❌ 첫 번째 상품 찾기 실패")
                return False
                
        except Exception as e:
            print(f"   ❌ 첫 번째 상품 클릭 오류: {e}")
            return False

    async def click_terms_tab(self, page):
        """약관상품사용설명서 탭 클릭"""
        try:
            # 먼저 페이지에 있는 모든 탭 조사
            debug_tabs_js = """
            () => {
                const allLinks = Array.from(document.querySelectorAll('a'));
                const tabLinks = allLinks.filter(a => {
                    const href = a.getAttribute('href') || '';
                    const text = a.textContent?.trim() || '';
                    const onclick = a.getAttribute('onclick') || '';
                    return (
                        href.startsWith('#') || 
                        text.includes('약관') || 
                        text.includes('상품설명서') ||
                        text.includes('설명서') ||
                        onclick.includes('tab') ||
                        a.getAttribute('role') === 'tab'
                    );
                });
                
                return tabLinks.map((link, idx) => ({
                    index: idx,
                    text: link.textContent.trim(),
                    href: link.getAttribute('href') || '',
                    onclick: link.getAttribute('onclick') || '',
                    className: link.className || '',
                    isVisible: link.offsetParent !== null
                }));
            }
            """
            
            available_tabs = await page.evaluate(debug_tabs_js)
            print(f"   📋 발견된 탭 링크: {len(available_tabs)}개")
            
            if available_tabs:
                for i, tab in enumerate(available_tabs[:8]):  # 상위 8개만 출력
                    visible = "(보임)" if tab['isVisible'] else "(숨김)"
                    print(f"      {i+1}. {tab['text'][:30]} -> {tab['href']} {visible}")
            
            # 약관 탭 찾기 및 클릭 (더 넓은 범위로 탐색)
            terms_js = """
            () => {
                const links = Array.from(document.querySelectorAll('a'));
                
                // 여러 패턴으로 약관 탭 찾기
                let termsTab = links.find(a => a.getAttribute('href') === '#uiProTabCon5');
                
                if (!termsTab) {
                    termsTab = links.find(a => {
                        const text = a.textContent?.trim() || '';
                        const href = a.getAttribute('href') || '';
                        return (
                            (text.includes('약관') && text.includes('상품')) ||
                            text.includes('약관상품사용설명서') ||
                            href.includes('uiProTabCon5') ||
                            href.includes('#tab5')
                        ) && a.offsetParent !== null;
                    });
                }
                
                // 더 넓은 범위로 탐색 (버튼이나 다른 요소일 수도 있음)
                if (!termsTab) {
                    const allElements = Array.from(document.querySelectorAll('*'));
                    termsTab = allElements.find(el => {
                        const text = el.textContent?.trim() || '';
                        const onclick = el.getAttribute('onclick') || '';
                        return (
                            (text.includes('약관') && text.includes('상품')) ||
                            text === '약관·상품사용설명서' ||
                            onclick.includes('uiProTabCon5')
                        ) && el.offsetParent !== null;
                    });
                }
                
                if (termsTab) {
                    termsTab.click();
                    return {
                        success: true,
                        text: termsTab.textContent.trim(),
                        href: termsTab.getAttribute('href') || '',
                        tagName: termsTab.tagName
                    };
                }
                return { success: false };
            }
            """
            
            result = await page.evaluate(terms_js)
            if result['success']:
                await asyncio.sleep(2)  # 탭 전환 대기
                print(f"   ✅ 약관 탭 클릭 성공: {result['text']} ({result['tagName']})")
                return True
            else:
                print(f"   ❌ 약관 탭 찾기 실패")
                return False
                
        except Exception as e:
            print(f"   ❌ 약관 탭 클릭 오류: {e}")
            return False

    async def analyze_all_links(self, page):
        """페이지의 모든 링크 상세 분석"""
        print("\n🔬 약관 탭 내 모든 링크 상세 분석:")
        print("-" * 80)
        
        try:
            all_links_data = await page.evaluate("""
                () => {
                    const allLinks = Array.from(document.querySelectorAll('a'));
                    const linkData = [];
                    
                    allLinks.forEach((link, index) => {
                        const text = link.textContent || link.innerText || '';
                        const href = link.getAttribute('href') || '';
                        const title = link.getAttribute('title') || '';
                        const className = link.className || '';
                        const isVisible = link.offsetParent !== null;
                        
                        // hidden input 정보 수집
                        const hiddenInputs = Array.from(link.querySelectorAll('input[type="hidden"]'));
                        const hiddenData = {};
                        hiddenInputs.forEach(input => {
                            const name = input.getAttribute('name') || '';
                            const value = input.getAttribute('value') || '';
                            if (name && value) {
                                hiddenData[name] = value;
                            }
                        });
                        
                        // PDF 관련 여부 판단
                        const isPDFCandidate = (
                            href === '#none' && 
                            title.includes('새창열림') && 
                            isVisible &&
                            (text.includes('상품설명서') || 
                             text.includes('약관') || 
                             text.includes('기준서') ||
                             text.includes('설명서') ||
                             text.includes('안내서') ||
                             Object.values(hiddenData).some(v => v.includes('.pdf')))
                        );
                        
                        if (isVisible && (text.trim().length > 0 || isPDFCandidate)) {
                            linkData.push({
                                index: index,
                                text: text.trim(),
                                href: href,
                                title: title,
                                className: className,
                                isVisible: isVisible,
                                isPDFCandidate: isPDFCandidate,
                                hiddenInputs: hiddenData,
                                hasHiddenInputs: Object.keys(hiddenData).length > 0
                            });
                        }
                    });
                    
                    return linkData;
                }
            """)
            
            # 결과 출력
            pdf_candidates = []
            regular_links = []
            
            for link in all_links_data:
                if link['isPDFCandidate']:
                    pdf_candidates.append(link)
                else:
                    regular_links.append(link)
            
            print(f"📄 PDF 후보 링크: {len(pdf_candidates)}개")
            for i, link in enumerate(pdf_candidates, 1):
                print(f"  {i}. 📎 '{link['text'][:50]}'")
                print(f"     - href: {link['href']}")
                print(f"     - title: {link['title']}")
                if link['hiddenInputs']:
                    print(f"     - hidden inputs:")
                    for name, value in link['hiddenInputs'].items():
                        print(f"       * {name}: {value[:60]}")
                print()
            
            print(f"🔗 일반 링크: {len(regular_links)}개 (상위 10개만 표시)")
            for i, link in enumerate(regular_links[:10], 1):
                print(f"  {i}. '{link['text'][:40]}' -> {link['href']}")
            
            # JSON 파일로 저장
            debug_data = {
                'analyzed_at': datetime.now().isoformat(),
                'total_links': len(all_links_data),
                'pdf_candidates': pdf_candidates,
                'regular_links': regular_links[:20]  # 상위 20개만 저장
            }
            
            debug_file = Path("kb_debug_links.json")
            with open(debug_file, 'w', encoding='utf-8') as f:
                json.dump(debug_data, f, ensure_ascii=False, indent=2)
                
            print(f"\n💾 상세 분석 결과 저장: {debug_file}")
            
        except Exception as e:
            print(f"❌ 링크 분석 오류: {e}")

async def main():
    crawler = KBDebugCrawler()
    await crawler.debug_terms_links()

if __name__ == "__main__":
    asyncio.run(main())