import pandas as pd
from pathlib import Path
import sys
import os

# Set console encoding to handle Korean characters
if sys.platform == "win32":
    os.system("chcp 65001 > nul")

def merge_csv_files(source_dir, output_file):
    """
    지정된 폴더와 그 하위 폴더의 모든 CSV 파일을 찾아 하나의 파일로 병합합니다.
    """
    source_path = Path(source_dir)
    output_path = Path(output_file)

    # 1. 원본 폴더 유효성 검사
    if not source_path.is_dir():
        print(f"Error: Source folder not found.")
        return

    # 2. 모든 CSV 파일 재귀적으로 찾기
    print(f"Searching for CSV files...")
    csv_files = sorted(list(source_path.rglob("*.csv")))

    if not csv_files:
        print("No CSV files found in the specified folder.")
        return

    # 3. 각 CSV 파일을 DataFrame으로 읽어 리스트에 추가
    df_list = []
    print("\n--- Starting file merge ---")
    for file_path in csv_files:
        try:
            print(f"Processing: {file_path.name}")
            df = pd.read_csv(file_path)
            # 파일 내용이 비어있지 않은 경우에만 추가
            if not df.empty:
                df_list.append(df)
        except Exception as e:
            print(f"Error reading file: {e}")
    print("--- File merge completed ---\n")

    # 4. 읽어온 DataFrame이 있는지 확인 후 병합
    if not df_list:
        print("No CSV files with data found to merge.")
        return

    # 모든 DataFrame을 하나로 합치기
    combined_df = pd.concat(df_list, ignore_index=True)

    # 5. 결과 파일 저장
    try:
        # 출력 폴더가 없으면 생성
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # CSV 파일로 저장 (인덱스 제외, Excel 호환성을 위해 utf-8-sig 인코딩 사용)
        combined_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        
        print("Task completed successfully")
        print(f"Total {len(csv_files)} files processed, {len(combined_df)} rows created.")
        print(f"Output file: {output_path.resolve()}")
    except Exception as e:
        print(f"Error saving final file: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python merge_csv_final.py <source_folder> <output_file>")
        sys.exit(1)
    
    source_dir = sys.argv[1]
    output_file = sys.argv[2]
    merge_csv_files(source_dir, output_file)


