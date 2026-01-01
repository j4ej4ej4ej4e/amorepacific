"""
DB 기반 영상 데이터 로더
TiDB의 yt_videos 테이블에서 영상 데이터를 읽어옵니다.
"""
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import os
from typing import List, Dict

load_dotenv()

# TiDB Cloud 접속 정보
DB_CONFIG = {
    'host': os.getenv('TIDB_HOST'),
    'port': int(os.getenv('TIDB_PORT', 4000)),
    'user': os.getenv('TIDB_USER'),
    'password': os.getenv('TIDB_PASSWORD'),
    'database': os.getenv('TIDB_DATABASE', 'amore'),
    'ssl_disabled': False,
    'ssl_verify_cert': False,
    'ssl_verify_identity': False
}


class DBVideoLoader:
    """
    DB에서 영상 데이터를 로드하는 클래스
    title, description, tags만 반환 (간단한 딕셔너리)
    """
    
    def __init__(self, quiet: bool = False):
        """
        Args:
            quiet: 출력 억제 여부
        """
        self.quiet = quiet
        self.conn = None
        self.cursor = None
        self._connect()
    
    def _connect(self):
        """DB 연결"""
        try:
            self.conn = mysql.connector.connect(**DB_CONFIG)
            self.cursor = self.conn.cursor(dictionary=True, buffered=True)
            if not self.quiet:
                print(f"[DB] ✅ TiDB 연결 성공!")
        except Error as err:
            print(f"[DB] ❌ 연결 실패: {err}")
            raise
    
    def search_by_keywords(self, keywords: str, limit: int = 100) -> List[Dict]:
        """
        키워드로 영상 검색
        
        Args:
            keywords: 검색 키워드 (띄어쓰기로 구분)
            limit: 최대 결과 수
            
        Returns:
            딕셔너리 리스트 [{title, description, tags}, ...]
        """
        # 키워드를 공백으로 분리
        keyword_list = keywords.split()
        
        # LIKE 조건 생성
        like_conditions = []
        params = []
        for kw in keyword_list:
            like_conditions.append(
                "(v.title LIKE %s OR v.description LIKE %s OR v.tags LIKE %s)"
            )
            like_pattern = f"%{kw}%"
            params.extend([like_pattern, like_pattern, like_pattern])
        
        where_clause = " AND ".join(like_conditions)
        
        query = f"""
            SELECT 
                v.title,
                v.description,
                v.tags,
                s.view_count
            FROM yt_videos v
            LEFT JOIN yt_video_stats s ON v.video_id = s.video_id
            WHERE {where_clause}
            ORDER BY s.view_count DESC
            LIMIT %s
        """
        
        params.append(limit)
        
        try:
            self.cursor.execute(query, params)
            rows = self.cursor.fetchall()
            
            videos = []
            for row in rows:
                # tags 처리 (문자열 -> 리스트)
                tags = []
                if row.get('tags'):
                    tags = [t.strip() for t in str(row['tags']).split(',')]
                
                video = {
                    'title': row.get('title', ''),
                    'description': row.get('description', '') or '',
                    'tags': tags,
                }
                videos.append(video)
            
            if not self.quiet:
                print(f"[DB] 🔍 '{keywords}' 검색: {len(videos)}개 영상 발견")
            
            return videos
            
        except Error as err:
            print(f"[DB] ❌ 검색 실패: {err}")
            return []
    
    def get_all_videos(self, limit: int = None) -> List[Dict]:
        """
        DB의 모든 영상 데이터 가져오기
        
        Args:
            limit: 최대 개수 (None이면 전체)
            
        Returns:
            딕셔너리 리스트 [{title, description, tags}, ...]
        """
        query = """
            SELECT 
                v.title,
                v.description,
                v.tags
            FROM yt_videos v
            ORDER BY v.video_id
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        try:
            self.cursor.execute(query)
            rows = self.cursor.fetchall()
            
            videos = []
            for row in rows:
                # tags 처리 (문자열 -> 리스트)
                tags = []
                if row.get('tags'):
                    tags = [t.strip() for t in str(row['tags']).split(',')]
                
                video = {
                    'title': row.get('title', ''),
                    'description': row.get('description', '') or '',
                    'tags': tags,
                }
                videos.append(video)
            
            if not self.quiet:
                print(f"[DB] 📺 {len(videos)}개 영상 로드 완료")
            
            return videos
            
        except Error as err:
            print(f"[DB] ❌ 로드 실패: {err}")
            return []
    
    
    def get_total_video_count(self) -> int:
        """DB에 저장된 총 영상 개수"""
        try:
            self.cursor.execute("SELECT COUNT(*) as cnt FROM yt_videos")
            result = self.cursor.fetchone()
            return result['cnt'] if result else 0
        except:
            return 0
    
    def close(self):
        """연결 종료"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        if not self.quiet:
            print("[DB] 연결 종료")


if __name__ == "__main__":
    # 테스트
    loader = DBVideoLoader(quiet=False)
    
    print(f"\n📊 DB 총 영상 수: {loader.get_total_video_count():,}개\n")
    
    # 키워드 검색 테스트
    print("=" * 60)
    print("🔍 키워드 검색 테스트: '허쉬컷 스타일링'")
    print("=" * 60)
    
    videos = loader.search_by_keywords("허쉬컷 스타일링", limit=10)
    
    for i, v in enumerate(videos, 1):
        print(f"\n{i}. {v['title']}")
        print(f"   설명: {v['description'][:100]}...")
        print(f"   태그: {', '.join(v['tags'][:5])}")
    
    loader.close()
