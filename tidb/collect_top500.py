"""
YouTube 카테고리 26번 (Howto & Style) 상위 영상 수집기
- yt-dlp 기반 (API 할당량 제한 없음)
- 인기 영상에서 채널/인플루언서 정보 수집
"""
import re
import yt_dlp
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import os
import time

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

# 카테고리 26번 (Howto & Style) 인기 영상 URL
CATEGORY_URL = "https://www.youtube.com/feed/trending?bp=6gQJRkVleHBsb3Jl"
# 한국 뷰티/헤어 관련 채널 찾기 위한 검색어들
SEARCH_QUERIES = [
    "헤어 스타일링", "펌 추천", "염색 추천", "헤어 케어",
    "샴푸 추천", "탈모 관리", "두피 케어", "헤어 드라이",
    "고데기 사용법", "남자 헤어", "여자 헤어"
]


def extract_instagram_id(text):
    """텍스트에서 인스타그램 ID 추출"""
    if not text:
        return None
    patterns = [
        r"instagram\.com/([a-zA-Z0-9._]+)",
        r"인스타\s*:\s*@?([a-zA-Z0-9._]+)",
        r"Instagram\s*:\s*@?([a-zA-Z0-9._]+)",
        r"@([a-zA-Z0-9._]+)"
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            uid = match.group(1)
            if uid not in ['p', 'reels', 'explore', 'stories', 'tv', 'gmail', 'naver', 'kakao']:
                return uid
    return None


class CategoryCollector:
    """YouTube 카테고리별 인기 영상 수집기"""
    
    def __init__(self):
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        self.collected_channels = set()
        try:
            self.conn = mysql.connector.connect(**DB_CONFIG)
            self.conn.autocommit = True
            self.cursor = self.conn.cursor(dictionary=True, buffered=True)
            print("[OK] TiDB Cloud connected!")
        except Error as err:
            print(f"[ERROR] DB connection failed: {err}")
            exit(1)
    
    def search_and_collect(self, query, max_results=50):
        """검색어로 영상 수집"""
        print(f"\n[Searching] '{query}' (max {max_results})")
        try:
            opts = {**self.ydl_opts, 'extract_flat': True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                results = ydl.extract_info(
                    f"ytsearch{max_results}:{query}",
                    download=False
                )
                entries = results.get('entries', [])
                print(f"  Found {len(entries)} videos")
                return entries
        except Exception as e:
            print(f"  [ERROR] Search failed: {e}")
            return []
    
    def get_video_info(self, video_id):
        """영상 상세 정보 가져오기"""
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(
                    f"https://www.youtube.com/watch?v={video_id}",
                    download=False
                )
                return info
        except Exception as e:
            return None
    
    def collect_top_videos(self, total_count=500):
        """상위 영상 수집"""
        collected = 0
        per_query = total_count // len(SEARCH_QUERIES) + 1
        
        for query in SEARCH_QUERIES:
            if collected >= total_count:
                break
            
            videos = self.search_and_collect(query, max_results=per_query)
            
            for video in videos:
                if collected >= total_count:
                    break
                
                video_id = video.get('id') or video.get('url', '').split('=')[-1]
                if not video_id or len(video_id) != 11:
                    continue
                
                # 채널 중복 체크
                channel_id = video.get('channel_id')
                if channel_id and channel_id in self.collected_channels:
                    continue
                
                # 영상 상세 정보 가져오기
                print(f"  [{collected+1}] Processing: {video.get('title', '')[:40]}...")
                info = self.get_video_info(video_id)
                if not info:
                    continue
                
                channel_id = info.get('channel_id')
                channel_name = info.get('channel') or info.get('uploader')
                
                if not channel_id or not channel_name:
                    continue
                
                if channel_id in self.collected_channels:
                    continue
                
                self.collected_channels.add(channel_id)
                
                # 인플루언서 저장
                inf_id = self._get_or_create_influencer(channel_name)
                
                # 채널 정보 저장
                self._save_channel(info, inf_id)
                
                # 영상 정보 저장
                self._save_video(info)
                
                # 인스타그램 ID 추출
                description = info.get('description', '')
                ig_id = extract_instagram_id(description)
                if ig_id:
                    self._save_instagram(ig_id, inf_id)
                
                collected += 1
                
                # 속도 조절
                time.sleep(0.5)
        
        print(f"\n[DONE] Collected {collected} unique channels!")
    
    def _get_or_create_influencer(self, name):
        """인플루언서 조회 또는 생성"""
        self.cursor.execute(
            "SELECT influencer_id FROM influencers WHERE name = %s", 
            (name,)
        )
        row = self.cursor.fetchone()
        if row:
            return row['influencer_id']
        
        self.cursor.execute(
            "INSERT INTO influencers (name, category) VALUES (%s, 'hair')",
            (name,)
        )
        return self.cursor.lastrowid
    
    def _save_channel(self, info, inf_id):
        """채널 정보 저장"""
        channel_id = info.get('channel_id')
        title = info.get('channel') or info.get('uploader')
        description = (info.get('description', '') or '')[:1000]
        subscriber_count = info.get('channel_follower_count', 0) or 0
        
        self.cursor.execute("""
            INSERT INTO yt_channels (channel_id, influencer_id, title, description, subscriber_count)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                subscriber_count = VALUES(subscriber_count),
                description = VALUES(description)
        """, (channel_id, inf_id, title, description, subscriber_count))
    
    def _save_video(self, info):
        """영상 정보 저장"""
        video_id = info.get('id')
        channel_id = info.get('channel_id')
        title = (info.get('title', '') or '')[:255]
        description = (info.get('description', '') or '')[:2000]
        tags = ','.join(info.get('tags', [])[:10]) if info.get('tags') else None
        duration = info.get('duration_string') or str(info.get('duration', 0))
        
        self.cursor.execute("""
            INSERT INTO yt_videos (video_id, channel_id, title, description, tags, duration)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                tags = VALUES(tags),
                duration = VALUES(duration)
        """, (video_id, channel_id, title, description, tags, duration))
        
        # 영상 통계 저장
        view_count = info.get('view_count', 0) or 0
        like_count = info.get('like_count', 0) or 0
        comment_count = info.get('comment_count', 0) or 0
        
        self.cursor.execute("""
            INSERT INTO yt_video_stats (video_id, view_count, like_count, comment_count)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                view_count = VALUES(view_count),
                like_count = VALUES(like_count),
                comment_count = VALUES(comment_count)
        """, (video_id, view_count, like_count, comment_count))
    
    def _save_instagram(self, ig_username, inf_id):
        """인스타그램 계정 저장"""
        self.cursor.execute(
            "INSERT IGNORE INTO ig_accounts (ig_username, influencer_id) VALUES (%s, %s)",
            (ig_username, inf_id)
        )
        self.cursor.execute(
            "UPDATE influencers SET confidence_score = confidence_score + 40 WHERE influencer_id = %s",
            (inf_id,)
        )
    
    def close(self):
        """연결 종료"""
        if hasattr(self, 'cursor'):
            self.cursor.close()
        if hasattr(self, 'conn'):
            self.conn.close()


if __name__ == "__main__":
    import sys
    
    # 수집할 개수 (기본 200)
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    
    collector = CategoryCollector()
    try:
        collector.collect_top_videos(total_count=count)
    except KeyboardInterrupt:
        print("\n[STOPPED] Interrupted by user")
    finally:
        collector.close()
