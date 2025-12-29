"""
자연어 기반 인플루언서 검색 (LLM 활용)
사용법: python search_influencer.py "검색어"
예시: python search_influencer.py "구독자 10만 이상인 남자 뷰티 유튜버 찾아줘"
"""
import sys
import os
import re
from dotenv import load_dotenv
import mysql.connector

# 현재 파일의 디렉토리를 기준으로 .env 로드
current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, '.env')
load_dotenv(env_path)
try:
    from db_connection import execute_query
except ImportError:
    # db_connection.py가 같은 디렉토리에 없는 경우 처리
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from db_connection import execute_query

load_dotenv()

# Gemini API 클라이언트 설정
try:
    import google.generativeai as genai
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[오류] GEMINI_API_KEY가 환경 변수에 설정되지 않았습니다.")
        # sys.exit(1)
    else:
        genai.configure(api_key=api_key)
        
except ImportError:
    print("[오류] google-generativeai 패키지가 설치되지 않았습니다.")
    print("pip install google-generativeai 명령어로 설치해주세요.")
    sys.exit(1)

# DB 스키마 정보 (프롬프트 제공용)
DB_SCHEMA = """
[테이블 구조]
1. influencers (인플루언서 기본 정보)
   - influencer_id (INT, PK): 고유 ID
   - name (VARCHAR): 이름
   - confidence_score (INT): 신뢰도 점수

2. yt_channels (유튜브 채널 정보)
   - channel_id (VARCHAR, PK): 유튜브 채널 ID
   - influencer_id (INT, FK): 인플루언서 ID
   - title (VARCHAR): 채널명
   - description (TEXT): 채널 설명
   - subscriber_count (INT): 구독자 수
   - video_count (INT): 동영상 수
   - total_view_count (BIGINT): 총 조회수
   - topic_categories (TEXT): 채널 주제 카테고리 (예: Beauty, Lifestyle)

3. yt_videos (유튜브 동영상 정보)
   - video_id (VARCHAR, PK): 비디오 ID
   - channel_id (VARCHAR, FK): 채널 ID
   - title (VARCHAR): 영상 제목
   - description (TEXT): 영상 설명
   - published_at (DATETIME): 게시일
   - duration (VARCHAR): 영상 길이
   - category_id (INT): 카테고리 ID (26: Using & Style, 22: People & Blogs 등)

4. ig_accounts (인스타그램 계정 정보)
   - ig_username (VARCHAR, PK): 인스타 ID
   - influencer_id (INT, FK): 인플루언서 ID
   - follower_count (INT): 팔로워 수
   - following_count (INT): 팔로잉 수
   - is_private (BOOLEAN): 비공개 여부

[검색 팁]
- '남성', '남자' 검색 시: yt_videos.title 또는 yt_channels.description에 '남자', '남성', '맨즈', 'Mens' 등이 포함되는지 LIKE 검색
- 특정 제품(예: '컬크림') 검색 시: yt_videos.title 또는 yt_videos.description에 해당 키워드 포함 여부 확인
- 뷰티/헤어채널 필터링: yt_videos.category_id IN (22, 26) 또는 topic_categories에 'Beauty', 'Hair' 포함
"""

def generate_sql(user_query):
    """LLM을 사용하여 자연어를 SQL로 변환"""
    if not api_key:
        return None

    system_prompt = f"""
    당신은 TiDB(MySQL 호환) 데이터베이스 전문가입니다.
    사용자의 자연어 요청을 해석하여 적절한 SQL 쿼리를 작성해주세요.
    
    {DB_SCHEMA}
    
    [규칙]
    1. 오직 SQL 쿼리문만 출력하세요. (Markdown 코드 블록 없이)
    2. 읽기 전용(SELECT) 쿼리만 작성하세요. DELETE, UPDATE, DROP 금지.
    3. 검색 결과에는 최소한 인플루언서 이름(name), 채널명(title), 구독자수(subscriber_count)가 포함되어야 합니다.
    4. 결과를 보기 좋게 정렬(ORDER BY)하세요. (기본: 구독자순)
    5. LIMIT 20을 기본적으로 적용하세요.
    6. JOIN을 적절히 사용하여 필요한 정보를 조합하세요.
    7. 검색어 매칭은 LIKE '%keyword%' 패턴을 사용하세요.
    
    사용자 요청: {user_query}
    """

    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(system_prompt)
        return response.text
    except Exception as e:
        print(f"[LLM 호출 오류] {e}")
        return None

def main():
    if len(sys.argv) < 2:
        # 테스트용 기본 검색
        query_text = "남성 헤어 스타일링 관련 유튜버 찾아줘"
        print(f"검색어를 입력하지 않아 기본 예시로 검색합니다: '{query_text}'")
    else:
        query_text = " ".join(sys.argv[1:])

    print(f"\n🔍 분석 중: '{query_text}'...")
    
    # 1. SQL 생성
    sql = generate_sql(query_text)
    
    if not sql:
        print("❌ SQL 생성에 실패했습니다. API 키를 확인하거나 잠시 후 다시 시도해주세요.")
        # LLM 없이 테스트할 수 있도록 더미 로직 (실제로는 LLM이 필수)
        if "컬크림" in query_text:
            sql = """
            SELECT DISTINCT i.name, c.title, c.subscriber_count, v.title as video_example
            FROM influencers i
            JOIN yt_channels c ON i.influencer_id = c.influencer_id
            JOIN yt_videos v ON c.channel_id = v.channel_id
            WHERE v.title LIKE '%컬크림%' OR v.description LIKE '%컬크림%'
            ORDER BY c.subscriber_count DESC
            LIMIT 10
            """
            print("(대체 쿼리 실행)")
        else:
            return

    # SQL 정제 (Markdown 제거 등)
    sql = re.sub(r'```sql\s*', '', sql)
    sql = re.sub(r'```', '', sql)
    sql = sql.strip()

    print(f"\n[생성된 SQL]\n{sql}\n")
    
    # 2. SQL 실행
    try:
        results = execute_query(sql)
        
        if not results:
            print("검색 결과가 없습니다.")
            return

        print(f"✅ 검색 결과 ({len(results)}건):")
        print("-" * 60)
        
        # 동적 헤더 출력
        if len(results) > 0:
            headers = list(results[0].keys())
            # 중요 컬럼 우선 출력 (name, title, subscriber_count)
            priority_cols = ['name', 'title', 'subscriber_count']
            other_cols = [c for c in headers if c not in priority_cols]
            display_cols = priority_cols + other_cols[:2] # 너무 많으면 자름
            
            print(" | ".join(display_cols))
            print("-" * 60)
            
            for row in results:
                values = [str(row.get(col, ''))[:20] for col in display_cols]
                print(" | ".join(values))
                
    except Exception as e:
        print(f"❌ 쿼리 실행 오류: {e}")

if __name__ == "__main__":
    main()
