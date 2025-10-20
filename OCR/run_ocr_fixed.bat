@echo off
chcp 65001 >nul
echo KB 특약 PDF 파서를 실행합니다...
echo 입력 폴더: ./crawling/downloads/kb_complete/pdfs/예금 (모든 하위 폴더 포함)
echo 출력 폴더: ./output
echo.
python OCR\ocr_fixed.py --in-dir "./crawling/downloads/kb_complete/pdfs/예금" --out-dir "./output" --exclude-description 1 --use-ocr 1 --ocr-lang kor
echo.
echo 처리가 완료되었습니다. 결과는 ./output 폴더를 확인하세요.
pause