import re
import mysql.connector
from googleapiclient.discovery import build
from mysql.connector import Error
from dotenv import load_dotenv
import os

load_dotenv()

# 1. 설정 및 API 키 (.env에서 로드)
API_KEY = os.getenv('API_KEY')
YOUTUBE = build('youtube', 'v3', developerKey=API_KEY)

# TiDB Cloud 접속 정보 (.env에서 로드)
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

# 2. 고도화된 타겟 쿼리 리스트 (셀프 스타일링 & 제품 리뷰 집중)
TARGET_QUERIES = [
    # [Group 1] 셀프 스타일링 & 툴 실전
    "봉고데기 하는법 | 판고데기 스타일링 | 다이슨 에어랩 튜토리얼",
    "단발 셀프 스타일링 | 긴머리 웨이브 넣는법 | 남자 가일컷 드라이",
    "앞머리 자르기 | 셀프 레이어드컷 | 집에서 하는 헤어컨설팅",
    "젖은머리 스타일링 | 웨트헤어 하는법 | 헤어 왁스 스프레이 사용법",
    
    # [Group 2] 제품 리뷰 & 추천 (커머스 중심)
    "올리브영 헤어템 추천 | 삶의 질 수직상승 헤어제품 | 내돈내산 샴푸 리뷰",
    "헤어에센스 순위 | 헤어오일 비교분석 | 인생 트리트먼트 추천",
    "향기 좋은 샴푸 | 퍼퓸 샴푸 추천 | 정수리 냄새 제거 샴푸",
    "셀프 염색약 리뷰 | 탈색약 추천 | 쿨톤 웜톤 염색약 비교",
    "헤어드라이기 비교 | 가성비 드라이기 추천 | 전문가용 드라이기 리뷰"
]

# 3. [고도화] 무효한 아이디(노이즈) 판별 함수
def is_valid_ig_handle(handle):
    if not handle: return False
    handle = handle.lower().strip()
    
    # 이메일 도메인 및 웹사이트 주소 차단
    if any(ext in handle for ext in ['.com', '.net', '.kr', '.co.kr', '.org', '.io', '.tv', '@']):
        return False
    
    # 블랙리스트 (MCN, 시스템 용어, 이메일 서비스)
    blacklist = [
        'gmail', 'naver', 'daum', 'kakao', 'hanmail', 'outlook', 'icloud',
        'aicompany', 'sandboxnetwork', 'leferi', 'videovillage', 'bgsworks', 'dmil',
        'reels', 'p', 'explore', 'stories', 'direct', 'profile', 'shop', 'tv',
        'mail', 'link', 'blog', 'youtube', 'bit.ly', 'linktr', 'p-k'
    ]
    if any(b in handle for b in blacklist):
        return False
        
    # 최소 3자 이상이며 영문자가 포함되어야 함
    if len(handle) < 3 or not re.search(r'[a-z]', handle):
        return False
    
    return True

# 4. [고도화] 텍스트에서 인스타 ID 추출 함수
def extract_instagram_id(text_or_list):
    if not text_or_list: return None
    
    search_text = " ".join(text_or_list) if isinstance(text_or_list, list) else str(text_or_list)
    
    patterns = [
        r"instagram\.com/([a-zA-Z0-9._]+)",
        r"instagr\.am/([a-zA-Z0-9._]+)",
        r"(?:인스타|Instagram|ig|insta)\s*[:]\s*@?([a-zA-Z0-9._]+)",
        r"@([a-zA-Z0-9._]+)" 
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, search_text, re.IGNORECASE)
        for candidate in matches:
            clean_id = candidate.strip('.')
            if is_valid_ig_handle(clean_id):
                return clean_id
    return None

# 5. 데이터 수집 에이전트 클래스
class AmoreAgent:
    def __init__(self):
        try:
            self.conn = mysql.connector.connect(**DB_CONFIG)
            self.cursor = self.conn.cursor(dictionary=True)
            print("✅ TiDB Cloud 연결 성공!")
        except Error as err:
            print(f"❌ DB 연결 에러: {err}")
            exit(1)

    def run_domain_curation(self, query, results_count=20):
        print(f"\n🚀 검색 쿼리 실행: [{query}]")
        
        search_res = YOUTUBE.search().list(
            q=query, 
            part='snippet', 
            type='video', 
            videoCategoryId='26', 
            order='relevance',    
            maxResults=results_count 
        ).execute()

        for item in search_res.get('items', []):
            channel_id = item['snippet']['channelId']
            channel_title = item['snippet']['channelTitle']
            
            inf_id = self._get_or_create_inf(channel_title)
            
            # [Step 1] 채널 메타데이터에서 인스타 탐색
            ig_id = self._sync_channel(channel_id, inf_id)
            
            # [Step 2] 채널에서 못 찾았다면 비디오 설명란에서 2차 탐색 (Waterfall 탐색)
            video_ig_id = self._sync_videos_and_find_ig(channel_id, inf_id)
            
            final_ig_id = ig_id if ig_id else video_ig_id
            
            if final_ig_id:
                self._link_instagram(final_ig_id, inf_id, channel_title)
            
        self.conn.commit()

    def _get_or_create_inf(self, name):
        self.cursor.execute("SELECT influencer_id FROM influencers WHERE name = %s", (name,))
        row = self.cursor.fetchone()
        if row: return row['influencer_id']
        self.cursor.execute("INSERT INTO influencers (name) VALUES (%s)", (name,))
        return self.cursor.lastrowid

    def _sync_channel(self, ch_id, inf_id):
        res_list = YOUTUBE.channels().list(
            part='snippet,statistics,brandingSettings', 
            id=ch_id
        ).execute().get('items', [])
        
        if not res_list: return None
        
        res = res_list[0]
        snippet = res['snippet']
        desc = snippet['description']
        
        # 인스타 ID 탐색 우선순위: 1.공식링크 -> 2.커스텀URL -> 3.채널설명
        ig_id = None
        if 'links' in res.get('brandingSettings', {}).get('channel', {}):
            links = res['brandingSettings']['channel']['links']
            ig_id = extract_instagram_id([l.get('channelLinkUrl', '') for l in links])
        
        if not ig_id:
            ig_id = extract_instagram_id(snippet.get('customUrl', ''))
            
        if not ig_id:
            ig_id = extract_instagram_id(desc)

        # 채널 정보 저장
        self.cursor.execute("""
            INSERT INTO yt_channels (channel_id, influencer_id, title, description, subscriber_count)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE subscriber_count=%s, description=%s
        """, (ch_id, inf_id, snippet['title'], desc, 
                res['statistics'].get('subscriberCount', 0), 
                res['statistics'].get('subscriberCount', 0), desc))
        
        return ig_id

    def _sync_videos_and_find_ig(self, ch_id, inf_id):
        found_ig = None
        try:
            ch_res = YOUTUBE.channels().list(part='contentDetails', id=ch_id).execute()
            playlist_id = ch_res['items'][0]['contentDetails']['relatedPlaylists']['uploads']
            v_items = YOUTUBE.playlistItems().list(playlistId=playlist_id, part='snippet', maxResults=3).execute().get('items', [])

            for v in v_items:
                vid_id = v['snippet']['resourceId']['videoId']
                v_res_list = YOUTUBE.videos().list(part='snippet,statistics,contentDetails', id=vid_id).execute().get('items', [])
                if not v_res_list: continue
                
                v_res = v_res_list[0]
                v_desc = v_res['snippet']['description']
                
                # 비디오 설명란에서 아이디 추출 시도
                if not found_ig:
                    found_ig = extract_instagram_id(v_desc)

                # 비디오 정보 저장
                self.cursor.execute("""
                    INSERT INTO yt_videos (video_id, channel_id, title, description, tags, duration) 
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE tags = VALUES(tags), duration = VALUES(duration)
                """, (vid_id, ch_id, v_res['snippet']['title'], v_desc, ",".join(v_res['snippet'].get('tags', [])), v_res['contentDetails'].get('duration')))
                
                v_stats = v_res['statistics']
                self.cursor.execute("""
                    INSERT INTO yt_video_stats (video_id, view_count, like_count, comment_count)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE view_count = VALUES(view_count), like_count = VALUES(like_count), comment_count = VALUES(comment_count)
                """, (vid_id, v_stats.get('viewCount', 0), v_stats.get('likeCount', 0), v_stats.get('commentCount', 0)))
        except Exception:
            pass
            
        return found_ig

    def _link_instagram(self, ig_id, inf_id, title):
        self.cursor.execute("INSERT IGNORE INTO ig_accounts (ig_username, influencer_id) VALUES (%s, %s)", (ig_id, inf_id))
        self.cursor.execute("UPDATE influencers SET confidence_score = confidence_score + 40 WHERE influencer_id = %s", (inf_id,))
        print(f"✅ 인스타 연결 성공: {title} -> @{ig_id}")

    def close(self):
        if hasattr(self, 'cursor'): self.cursor.close()
        if hasattr(self, 'conn'): self.conn.close()

# 6. 실행부
if __name__ == "__main__":
    agent = AmoreAgent()
    try:
        for q in TARGET_QUERIES:
            agent.run_domain_curation(q, results_count=20)
        print("\n✨ 모든 타겟 키워드에 대한 수집이 완료되었습니다!")
    except KeyboardInterrupt:
        print("\n🛑 사용자에 의해 중단되었습니다.")
    finally:
        agent.close()