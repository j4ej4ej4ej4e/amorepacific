"""
TiDB 데이터베이스 조회 도구
사용법: python query.py [테이블명] [옵션]
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from db_connection import execute_query


def print_table(data, title=None):
    """데이터를 테이블 형식으로 출력"""
    if not data:
        print("  (데이터 없음)")
        return
    
    if title:
        print(f"\n{'=' * 70}")
        print(f" {title}")
        print('=' * 70)
    
    # 컬럼 너비 계산
    columns = list(data[0].keys())
    widths = {}
    for col in columns:
        max_len = len(str(col))
        for row in data:
            val_len = len(str(row[col])[:25])
            if val_len > max_len:
                max_len = val_len
        widths[col] = min(max_len, 25)
    
    # 헤더 출력
    header = " | ".join(str(col).ljust(widths[col])[:widths[col]] for col in columns)
    print(header)
    print("-" * len(header))
    
    # 데이터 출력
    for row in data:
        line = " | ".join(str(row[col])[:widths[col]].ljust(widths[col]) for col in columns)
        print(line)


def show_tables():
    """테이블 목록 조회"""
    tables = execute_query("SHOW TABLES")
    print("\n[테이블 목록]")
    for t in tables:
        table_name = list(t.values())[0]
        count = execute_query(f"SELECT COUNT(*) as cnt FROM {table_name}")
        print(f"  - {table_name}: {count[0]['cnt']} rows")
    return tables


def describe_table(table_name):
    """테이블 구조 조회"""
    columns = execute_query(f"DESCRIBE {table_name}")
    print_table(columns, f"{table_name}")


def describe_all_tables():
    """모든 테이블 구조 조회"""
    tables = execute_query("SHOW TABLES")
    
    print("\n" + "=" * 70)
    print(" 전체 테이블 구조")
    print("=" * 70)
    
    for t in tables:
        table_name = list(t.values())[0]
        count = execute_query(f"SELECT COUNT(*) as cnt FROM {table_name}")
        columns = execute_query(f"DESCRIBE {table_name}")
        
        print(f"\n[{table_name}] - {count[0]['cnt']} rows")
        print("-" * 50)
        for col in columns:
            nullable = "" if col['Null'] == 'YES' else " NOT NULL"
            key = f" ({col['Key']})" if col['Key'] else ""
            print(f"  {col['Field']:20} {col['Type']}{nullable}{key}")


def select_table(table_name, limit=10):
    """테이블 데이터 조회"""
    data = execute_query(f"SELECT * FROM {table_name} LIMIT {limit}")
    print_table(data, f"{table_name} (상위 {limit}개)")


def run_sql(sql):
    """SQL 직접 실행"""
    data = execute_query(sql)
    print_table(data, "쿼리 결과")


def show_overview():
    """DB 개요 출력"""
    print("\n" + "=" * 70)
    print(" TiDB 데이터베이스 조회 도구")
    print("=" * 70)
    
    # 테이블 목록 + 구조
    describe_all_tables()
    
    print("\n" + "-" * 70)
    print(" 명령어:")
    print("   tables          - 테이블 목록")
    print("   desc [테이블]   - 테이블 구조")
    print("   schema          - 전체 테이블 구조")
    print("   select [테이블] - 데이터 조회 (상위 10개)")
    print("   sql [쿼리]      - SQL 직접 실행")
    print("   exit            - 종료")
    print("-" * 70)


def interactive_mode():
    """인터랙티브 모드"""
    show_overview()
    
    while True:
        try:
            cmd = input("\n> ").strip()
            
            if not cmd:
                continue
            elif cmd == "exit":
                print("종료합니다.")
                break
            elif cmd == "tables":
                show_tables()
            elif cmd == "schema":
                describe_all_tables()
            elif cmd.startswith("desc "):
                table = cmd.split(" ", 1)[1]
                describe_table(table)
            elif cmd.startswith("select "):
                table = cmd.split(" ", 1)[1]
                select_table(table)
            elif cmd.startswith("sql "):
                sql = cmd.split(" ", 1)[1]
                run_sql(sql)
            else:
                # SQL 직접 입력으로 처리
                run_sql(cmd)
                
        except KeyboardInterrupt:
            print("\n종료합니다.")
            break
        except Exception as e:
            print(f"[오류] {e}")


if __name__ == "__main__":
    args = sys.argv[1:]
    
    if not args:
        interactive_mode()
    elif args[0] == "tables":
        show_tables()
    elif args[0] == "schema":
        describe_all_tables()
    elif args[0] == "desc" and len(args) > 1:
        describe_table(args[1])
    elif args[0] == "select" and len(args) > 1:
        limit = int(args[2]) if len(args) > 2 else 10
        select_table(args[1], limit)
    elif args[0] == "sql" and len(args) > 1:
        run_sql(" ".join(args[1:]))
    else:
        select_table(args[0])
