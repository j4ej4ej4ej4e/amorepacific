import re
import mysql.connector
from googleapiclient.discovery import build
from mysql.connector import Error

# 1. 설정 및 API 키
API_KEY = 'AIzaSyAyJ91YXQDM1WxkDmhz8vpnjeHpi1pv_98' 
YOUTUBE = build('youtube', 'v3', developerKey=API_KEY)

# TiDB Cloud 접속 정보 반영
DB_CONFIG = {
    'host': 'gateway01.ap-northeast-1.prod.aws.tidbcloud.com',
    'port': 4000,
    'user': '3L6DrudtY9pp6uz.root',
    'password': 'G3kCbZSpzthPGm1Q',
    'database': 'amore',
    'ssl_verify_cert': True  # TiDB Cloud는 SSL 연결이 필수입니다.
}

# 2. 키워드 셋 정의
KEYWORDS_SET = {
    "female_trends": ["허쉬컷 스타일링", "레이어드컷 드라이", "태슬컷 관리법"],
    "male_trends": ["아이비리그컷 스타일링", "가일컷 하는법", "리프컷 드라이"],
    "product_reviews": ["인생 샴푸 추천", "트리트먼트 순위 비교"],
    "pro_tips": ["상한 머리 복구 꿀팁", "옆머리 누르기 비법"]
}

# 3. 인스타 ID 추출 유틸리티 (기존과 동일)
def extract_instagram_id(text):
    if not text: return None
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

# 4. 데이터 수집 에이전트 클래스
class AmoreAgent:
    def __init__(self):
        try:
            # TiDB에 연결 시도
            self.conn = mysql.connector.connect(**DB_CONFIG)
            self.cursor = self.conn.cursor(dictionary=True)
            print("✅ TiDB Cloud 연결 성공!")
        except Error as err:
            print(f"❌ DB 연결 에러: {err}")
            exit(1)

    def run_full_curation(self, keyword_dict):
        for category, keywords in keyword_dict.items():
            print(f"\n🚀 카테고리 [{category}] 수집 시작...")
            for kw in keywords:
                self.collect_by_keyword(kw)
        self.conn.commit()
        print("\n✨ 모든 데이터 TiDB 동기화 완료!")

    def collect_by_keyword(self, keyword):
        print(f"🔍 '{keyword}' 검색 중...")
        # '26'은 Howto & Style 카테고리입니다.
        search_res = YOUTUBE.search().list(
            q=keyword, part='snippet', type='video', 
            videoCategoryId='26', maxResults=2 
        ).execute()

        for item in search_res.get('items', []):
            channel_id = item['snippet']['channelId']
            channel_title = item['snippet']['channelTitle']
            
            inf_id = self._get_or_create_inf(channel_title)
            self._sync_channel(channel_id, inf_id)
            self._sync_videos(channel_id, inf_id)

    def _get_or_create_inf(self, name):
        self.cursor.execute("SELECT influencer_id FROM influencers WHERE name = %s", (name,))
        row = self.cursor.fetchone()
        if row: return row['influencer_id']
        self.cursor.execute("INSERT INTO influencers (name) VALUES (%s)", (name,))
        return self.cursor.lastrowid

    def _sync_channel(self, ch_id, inf_id):
        res = YOUTUBE.channels().list(part='snippet,statistics', id=ch_id).execute()['items'][0]
        desc = res['snippet']['description']
        ig_id = extract_instagram_id(desc)
        
        self.cursor.execute("""
            INSERT INTO yt_channels (channel_id, influencer_id, title, profile_biography, subscriber_count)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE subscriber_count=%s
        """, (ch_id, inf_id, res['snippet']['title'], desc, 
                res['statistics'].get('subscriberCount', 0), 
                res['statistics'].get('subscriberCount', 0)))

        if ig_id:
            # 중복 방지를 위한 INSERT IGNORE
            self.cursor.execute("INSERT IGNORE INTO ig_accounts (ig_username, influencer_id) VALUES (%s, %s)", (ig_id, inf_id))
            # 신뢰도 점수 업데이트 (간이 분석 로직)
            self.cursor.execute("UPDATE influencers SET confidence_score = confidence_score + 40 WHERE influencer_id = %s", (inf_id,))

    def _sync_videos(self, ch_id, inf_id):
        res = YOUTUBE.channels().list(part='contentDetails', id=ch_id).execute()
        playlist_id = res['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        v_items = YOUTUBE.playlistItems().list(playlistId=playlist_id, part='snippet', maxResults=3).execute().get('items', [])

        for v in v_items:
            vid_id = v['snippet']['resourceId']['videoId']
            v_res = YOUTUBE.videos().list(part='snippet,statistics,contentDetails', id=vid_id).execute()['items'][0]
            
            v_snippet = v_res['snippet']
            v_content = v_res['contentDetails']
            v_stats = v_res['statistics']
            
            tags_list = v_snippet.get('tags', [])
            tags_str = ",".join(tags_list) if tags_list else None
            
            # TiDB/MySQL 포맷에 맞게 시간 변환
            published_at = v_snippet['publishedAt'].replace('Z', '').replace('T', ' ')

            sql_video = """
                INSERT INTO yt_videos (video_id, channel_id, title, description, tags, duration) 
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE tags = VALUES(tags), duration = VALUES(duration)
            """
            self.cursor.execute(sql_video, (
                vid_id, ch_id, v_snippet['title'], v_snippet['description'],
                tags_str, v_content.get('duration')
            ))
            
            self.cursor.execute("""
                INSERT INTO yt_video_stats (video_id, view_count, like_count, comment_count)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    view_count = VALUES(view_count), 
                    like_count = VALUES(like_count), 
                    comment_count = VALUES(comment_count)
            """, (vid_id, v_stats.get('viewCount', 0), v_stats.get('likeCount', 0), v_stats.get('commentCount', 0)))

    def close(self):
        if hasattr(self, 'cursor'): self.cursor.close()
        if hasattr(self, 'conn'): self.conn.close()

# 5. 실행부
if __name__ == "__main__":
    agent = AmoreAgent()
    try:
        agent.run_full_curation(KEYWORDS_SET)
    except KeyboardInterrupt:
        print("\n🛑 사용자에 의해 중단되었습니다.")
    finally:
        agent.close()
