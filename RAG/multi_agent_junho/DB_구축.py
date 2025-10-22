import pandas as pd
from sqlalchemy import create_engine

# 1. DB 연결 정보
user = "admin"
password = "admin123"
host = "localhost"
port = "5432"
database = "multiagent_db"

# 2. CSV 로드
df = pd.read_csv("merged.csv")

# 3. DB 연결 생성
engine = create_engine(f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}")

# 4. 테이블에 데이터 저장
df.to_sql("merged_table", engine, if_exists="replace", index=False)

# 5. 확인
result = pd.read_sql("SELECT * FROM merged_table;", engine)
print(result)