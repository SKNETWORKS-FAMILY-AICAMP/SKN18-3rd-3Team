import pandas as pd

# CSV 로드
df = pd.read_csv('embedding/우리+국민_약관_semantic_chunks.csv', encoding='utf-8-sig')

print(f'원본 행 수: {len(df)}')
print(f'고유 chunk_id 수: {df["chunk_id"].nunique()}')

# 중복 확인
duplicates = df[df.duplicated(subset=['chunk_id'], keep=False)]
print(f'중복된 행 수: {len(duplicates)}')

# chunk_id를 재부여
# 방법: 각 행에 대해 순차적으로 고유한 ID 생성
new_chunk_ids = []

for idx, row in df.iterrows():
    # 기존 chunk_id에서 마지막 번호를 추출하거나 새로 생성
    base_id = row['chunk_id']
    
    # 이미 사용된 chunk_id인지 확인
    new_id = base_id
    counter = 0
    
    # 중복이 발생하면 뒤에 카운터를 추가
    while new_id in new_chunk_ids:
        # 기존 ID에 _1, _2, _3... 형태로 추가
        if ':' in base_id:
            parts = base_id.rsplit(':', 1)
            new_id = f"{parts[0]}:{parts[1]}_{counter}"
        else:
            new_id = f"{base_id}_{counter}"
        counter += 1
    
    new_chunk_ids.append(new_id)

# 새로운 chunk_id 할당
df['chunk_id'] = new_chunk_ids

print(f'\n재할당 후:')
print(f'총 행 수: {len(df)}')
print(f'고유 chunk_id 수: {df["chunk_id"].nunique()}')

# 중복 확인
remaining_dups = df[df.duplicated(subset=['chunk_id'], keep=False)]
print(f'남은 중복 행 수: {len(remaining_dups)}')

# 저장
output_path = 'embedding/우리+국민_약관_semantic_chunks_reassigned.csv'
df.to_csv(output_path, index=False, encoding='utf-8-sig')
print(f'\n[OK] 저장 완료: {output_path}')

# 샘플 출력
print('\n샘플 데이터 (처음 5개):')
print(df[['chunk_id', '은행명', '상품이름', '조항']].head())

