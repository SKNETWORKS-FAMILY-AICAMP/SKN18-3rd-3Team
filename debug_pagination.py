#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
적금 탭의 페이지네이션 구조 분석
"""
import asyncio
from playwright.async_api import async_playwright

async def analyze_pagination():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        page = await browser.new_page()
        
        print("📍 예금 페이지 로드 중...")
        await page.goto("https://obank.kbstar.com/quics?page=C016613", wait_until="domcontentloaded")
        await asyncio.sleep(3)
        
        print("\n🔍 적금 탭 클릭...")
        # 적금 탭 클릭
        await page.evaluate("""
            () => {
                const listItems = document.querySelectorAll('ul.tabMenu li, ul#tabMenutabMain li');
                for (const li of listItems) {
                    const aTag = li.querySelector('a');
                    if (!aTag) continue;
                    const text = aTag.textContent?.trim() || '';
                    if (text.includes('적금')) {
                        console.log(`Found 적금 tab: ${text}`);
                        aTag.click();
                        break;
                    }
                }
            }
        """)
        await asyncio.sleep(5)
        
        print("\n📊 페이지네이션 영역 분석...")
        
        # 페이지네이션 HTML 추출
        pagination_html = await page.evaluate("""
            () => {
                const paginateArea = document.querySelector('.pagenate, .paging');
                if (!paginateArea) return '페이지네이션 영역을 찾을 수 없음';
                return paginateArea.innerHTML;
            }
        """)
        
        print("\n=== 페이지네이션 HTML ===")
        print(pagination_html[:2000])  # 처음 2000자만
        print("\n" + "="*50)
        
        # 모든 input[type="submit"] 버튼 분석
        buttons_info = await page.evaluate("""
            () => {
                const paginateArea = document.querySelector('.pagenate, .paging');
                if (!paginateArea) return [];
                
                const buttons = paginateArea.querySelectorAll('input[type="submit"]');
                const info = [];
                
                buttons.forEach((btn, index) => {
                    info.push({
                        index: index,
                        value: btn.getAttribute('value'),
                        title: btn.getAttribute('title'),
                        name: btn.getAttribute('name'),
                        disabled: btn.disabled,
                        className: btn.className,
                        visible: btn.offsetParent !== null
                    });
                });
                
                return info;
            }
        """)
        
        print("\n=== 발견된 모든 버튼 ===")
        for btn in buttons_info:
            print(f"\n버튼 {btn['index']}:")
            print(f"  value: {btn['value']}")
            print(f"  title: {btn['title']}")
            print(f"  name: {btn['name']}")
            print(f"  disabled: {btn['disabled']}")
            print(f"  visible: {btn['visible']}")
            print(f"  className: {btn['className']}")
        
        print("\n" + "="*50)
        
        # hidden input "현재페이지" 값 확인
        current_page_value = await page.evaluate("""
            () => {
                const input = document.querySelector('input[name="현재페이지"]');
                return input ? input.value : 'not found';
            }
        """)
        
        print(f"\n현재 페이지 hidden input 값: {current_page_value}")
        
        # 총 상품 수 확인
        product_count = await page.evaluate("""
            () => {
                const products = document.querySelectorAll('ul li:has(a[onclick*="dtl"])');
                return products.length;
            }
        """)
        
        print(f"현재 페이지의 상품 수: {product_count}")
        
        print("\n\n⏸️ 브라우저를 열어두었습니다. 수동으로 확인해보세요.")
        print("종료하려면 Enter를 누르세요...")
        input()
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(analyze_pagination())
