"""
yt-dlp 기반 YouTube 데이터 수집기
- API 할당량 제한 없음
- YouTube 검색, 채널/영상 정보 수집
"""
import re
import yt_dlp
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import os

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

# 키워드 셋 정의
KEYWORDS_SET = {
    "female_trends": [
        "히피펌 스타일링", "레이어드컷 드라이", "허쉬컷 자르기",
        "태슬컷 스타일링", "C컬펌 관리", "물결펌 하는법"
    ],
    "male_trends": [
        "아이비리그컷 스타일링", "리프컷 드라이", "가일컷 하는법",
        "투블럭 다운펌", "댄디컷 스타일링", "크롭컷 관리"
    ],
    "product_reviews": [
        "샴푸 추천 순위", "트리트먼트 비교", "컬크림 추천",
        "헤어오일 비교", "두피샴푸 추천", "염색약 추천"
    ],
    "hair_tips": [
        "손상모 복구", "탈색 관리법", "염색 유지 꿀팁",
        "곱슬머리 관리", "볼륨 살리기", "앞머리 드라이"
    ],
    "scalp_care": [
        "탈모 예방법", "두피케어 루틴", "지성두피 관리",
        "각질 제거", "두피 마사지"
    ],
    "hair_tools": [
        "고데기 추천", "드라이기 비교", "헤어롤 사용법",
        "매직기 추천", "브러쉬 추천"
    ]
}


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
            if uid not in ['p', 'reels', 'explore', 'stories', 'tv']:
                return uid
    return None


class YtDlpCollector:
    """yt-dlp 기반 YouTube 데이터 수집기"""
    
    def __init__(self):
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        try:
            self.conn = mysql.connector.connect(**DB_CONFIG)
            self.conn.autocommit = True  # 자동 커밋 활성화
            self.cursor = self.conn.cursor(dictionary=True, buffered=True)
            print("[OK] TiDB Cloud connected!")
        except Error as err:
            print(f"[ERROR] DB connection failed: {err}")
            exit(1)
    
    def search_youtube(self, keyword, max_results=3):
        """YouTube 검색"""
        print(f"  Searching: '{keyword}'")
        try:
            opts = {**self.ydl_opts, 'extract_flat': True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                results = ydl.extract_info(
                    f"ytsearch{max_results}:{keyword}",
                    download=False
                )
                return results.get('entries', [])
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
            print(f"  [ERROR] Video info failed: {e}")
            return None
    
    def get_channel_info(self, channel_id):
        """채널 정보 가져오기 (외부 링크 포함)"""
        try:
            opts = {**self.ydl_opts, 'extract_flat': True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(
                    f"https://www.youtube.com/channel/{channel_id}",
                    download=False
                )
                return info
        except Exception as e:
            print(f"  [ERROR] Channel info failed: {e}")
            return None
    
    def extract_instagram_from_channel(self, channel_id):
        """채널 외부 링크에서 인스타그램 ID 추출"""
        try:
            opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'skip_download': True,
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                url = f"https://www.youtube.com/channel/{channel_id}"
                info = ydl.extract_info(url, download=False)
                
                # 외부 링크에서 인스타그램 찾기
                # yt-dlp는 채널의 uploader_url, channel_url 등을 제공
                # 또한 웹페이지에서 추출한 링크가 있을 수 있음
                
                ig_id = None
                
                # 1. 채널 설명에서 추출
                description = info.get('description', '') or ''
                ig_id = extract_instagram_id(description)
                if ig_id:
                    return ig_id
                
                # 2. uploader_url에서 추출 (드물지만 가능)
                uploader_url = info.get('uploader_url', '') or ''
                if 'instagram.com' in uploader_url:
                    ig_id = extract_instagram_id(uploader_url)
                    if ig_id:
                        return ig_id
                
                # 3. 채널 페이지의 webpage_url_domain 체크
                # (yt-dlp가 외부 링크를 직접 제공하진 않음)
                
                return None
        except Exception as e:
            return None
    
    def run_collection(self, keywords_dict):
        """전체 수집 실행"""
        for category, keywords in keywords_dict.items():
            print(f"\n[Category] {category}")
            for keyword in keywords:
                self.collect_by_keyword(keyword)
        
        self.conn.commit()
        print("\n[DONE] All data synced to TiDB!")
    
    def collect_by_keyword(self, keyword):
        """키워드로 데이터 수집"""
        videos = self.search_youtube(keyword, max_results=3)
        
        for video in videos:
            if not video:
                continue
            
            video_id = video.get('id') or video.get('url', '').split('=')[-1]
            if not video_id or len(video_id) != 11:
                continue
            
            # 영상 상세 정보 가져오기
            info = self.get_video_info(video_id)
            if not info:
                continue
            
            channel_id = info.get('channel_id')
            channel_name = info.get('channel') or info.get('uploader')
            
            if not channel_id or not channel_name:
                continue
            
            # 인플루언서 저장/조회
            inf_id = self._get_or_create_influencer(channel_name)
            
            # 채널 정보 저장
            self._save_channel(info, inf_id)
            
            # 영상 정보 저장
            self._save_video(info)
            
            # 인스타그램 ID 추출 및 저장
            # 1. 영상 설명에서 추출
            description = info.get('description', '')
            ig_id = extract_instagram_id(description)
            
            # 2. 없으면 채널 외부 링크에서 추출 시도
            if not ig_id:
                ig_id = self.extract_instagram_from_channel(channel_id)
            
            if ig_id:
                self._save_instagram(ig_id, inf_id)
    
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
        description = info.get('description', '')[:1000]
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
        title = info.get('title', '')[:255]
        description = info.get('description', '')[:2000]
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
        # 신뢰도 점수 추가
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
    collector = YtDlpCollector()
    try:
        collector.run_collection(KEYWORDS_SET)
    except KeyboardInterrupt:
        print("\n[STOPPED] Interrupted by user")
    finally:
        collector.close()
