@echo off
chcp 65001 > nul
python merge_csv_final.py "ocr_output\대출_unique_csv" "ocr_output\merged_all_대출.csv"
pause




