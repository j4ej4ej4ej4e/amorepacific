"""데이터 조회 테스트"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from db_connection import execute_query

print("=" * 50)
print("TiDB 데이터 조회 테스트")
print("=" * 50)

# 테이블 목록
print("\n[테이블 목록]")
tables = execute_query("SHOW TABLES")
for t in tables:
    print(f"  - {list(t.values())[0]}")

# 각 테이블 레코드 수
print("\n[테이블별 레코드 수]")
for t in tables:
    table_name = list(t.values())[0]
    count = execute_query(f"SELECT COUNT(*) as cnt FROM {table_name}")
    print(f"  - {table_name}: {count[0]['cnt']} rows")

# influencers 테이블 상세
print("\n[influencers 테이블 - 상위 5개]")
data = execute_query("SELECT * FROM influencers LIMIT 5")
for row in data:
    print(f"  {row}")

# yt_channels 테이블 구조 확인
print("\n[yt_channels 테이블 구조]")
columns = execute_query("DESCRIBE yt_channels")
for col in columns:
    print(f"  - {col['Field']}: {col['Type']}")

# yt_channels 테이블 상세
print("\n[yt_channels 테이블 - 상위 5개]")
data = execute_query("SELECT * FROM yt_channels LIMIT 5")
for row in data:
    print(f"  {row}")

# ig_accounts 테이블 상세
print("\n[ig_accounts 테이블 - 상위 5개]")
data = execute_query("SELECT * FROM ig_accounts LIMIT 5")
for row in data:
    print(f"  {row}")

print("\n" + "=" * 50)
print("조회 완료!")
