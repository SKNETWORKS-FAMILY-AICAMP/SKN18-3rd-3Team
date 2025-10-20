@echo off
chcp 65001 >nul
echo 대출 PDF 추출기를 실행합니다...
echo 입력 폴더: ./crawling/downloads/kb_complete/pdfs/대출
echo 출력 폴더: ./output_only_txt2
echo.
python OCR\extract2.py --in-dir "./crawling/downloads/kb_complete/pdfs/대출" --out-dir "./output_only_txt2"
echo.
echo 처리가 완료되었습니다.
pause

