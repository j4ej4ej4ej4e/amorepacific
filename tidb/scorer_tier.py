"""
티어별 인플루언서 점수 시스템
- 기업 홍보 관점: 마이크로/나노 인플루언서 우대
- 티어별 TOP N 출력
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import mysql.connector
from dotenv import load_dotenv
import os
import math

load_dotenv()

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

# 티어 정의
TIERS = {
    'nano': (1000, 10000, '나노 (1K~10K)'),
    'micro': (10000, 100000, '마이크로 (10K~100K)'),
    'mid': (100000, 500000, '중형 (100K~500K)'),
    'macro': (500000, float('inf'), '대형 (500K+)')
}

# 뷰티/헤어 관련 키워드
BEAUTY_KEYWORDS = [
    '헤어', '펌', '염색', '컷', '미용', '살롱', '두피', '탈모',
    '메이크업', '뷰티', '스타일링', '샴푸', '트리트먼트',
    'hair', 'beauty', 'makeup', 'salon', 'styling',
    '디자이너', '원장', '고데기', '드라이', '컬러'
]

# 제외할 키워드 (의사/병원/의료 등)
EXCLUDE_KEYWORDS = [
    '의사', '병원', '의원', '클리닉', '피부과', '성형', '시술',
    '의학', 'doctor', 'clinic', '전문의', '약사', '한의원',
    '치료', '진료', '수술', '약', '건강', '의료', '모발이식',
    '닥터', 'Dr.', '원장님', '기능의학', '내과'
]


def is_beauty_related(text):
    if not text:
        return False
    text_lower = text.lower()
    for keyword in BEAUTY_KEYWORDS:
        if keyword.lower() in text_lower:
            return True
    return False


def is_excluded(text):
    if not text:
        return False
    text_lower = text.lower()
    for keyword in EXCLUDE_KEYWORDS:
        if keyword.lower() in text_lower:
            return True
    return False


def get_tier(subscriber_count):
    """구독자 수로 티어 판단"""
    for tier_name, (min_sub, max_sub, label) in TIERS.items():
        if min_sub <= subscriber_count < max_sub:
            return tier_name, label
    return 'nano', TIERS['nano'][2]  # 기본값


class TierScorer:
    def __init__(self):
        print("[연결 중...]")
        self.conn = mysql.connector.connect(**DB_CONFIG)
        self.conn.autocommit = True
        self.cursor = self.conn.cursor(dictionary=True, buffered=True)
        print("[연결 완료]")
    
    def query(self, sql, params=None):
        self.cursor.execute(sql, params)
        return self.cursor.fetchall()
    
    def calculate_score(self, channel_data, ig_data):
        """티어 기반 점수 계산"""
        score = 0
        reasons = []
        
        subscriber_count = channel_data.get('subscriber_count', 0) or 0
        description = channel_data.get('description', '') or ''
        title = channel_data.get('title', '') or ''
        video_count = channel_data.get('video_count', 0) or 0
        total_view_count = channel_data.get('total_view_count', 0) or 0
        avg_views = channel_data.get('avg_views', 0) or 0
        recent_count = channel_data.get('recent_count', 0) or 0
        days_since_last = channel_data.get('days_since_last', 999) or 999
        
        tier, tier_label = get_tier(subscriber_count)
        
        # 1. 도메인 적합성 (가장 중요: 0~40점)
        is_beauty = is_beauty_related(description) or is_beauty_related(title)
        is_doctor = is_excluded(description) or is_excluded(title)
        
        if is_doctor:
            return 0, ["의사/병원 제외"], tier  # 바로 제외
        
        if is_beauty:
            score += 40
            reasons.append("뷰티/헤어")
        else:
            return 0, ["도메인 불일치"], tier  # 비뷰티 채널 제외
        
        # 2. 인게이지먼트 - 조회율 (0~30점, 가중치 높임)
        if subscriber_count > 0 and avg_views > 0:
            view_rate = (avg_views / subscriber_count) * 100
            if view_rate > 100:  # 구독자보다 조회수 많음 = 바이럴
                score += 30
                reasons.append(f"조회율 {view_rate:.0f}%")
            elif view_rate > 50:
                score += 25
                reasons.append(f"조회율 {view_rate:.0f}%")
            elif view_rate > 20:
                score += 20
            elif view_rate > 10:
                score += 15
            elif view_rate > 5:
                score += 10
        
        # 3. 티어 보너스 (마이크로/나노 우대)
        if tier == 'nano':
            score += 20
            reasons.append("나노")
        elif tier == 'micro':
            score += 25  # 마이크로 가장 우대
            reasons.append("마이크로")
        elif tier == 'mid':
            score += 15
            reasons.append("중형")
        else:  # macro
            score += 5
            reasons.append("대형")
        
        # 4. 최근 활동성 (0~15점)
        if recent_count > 0:
            if days_since_last <= 7:
                score += 15
                reasons.append("최근활동")
            elif days_since_last <= 30:
                score += 10
            elif days_since_last <= 90:
                score += 5
        
        # 5. 꾸준한 활동 - 영상 개수 (0~10점)
        if 20 <= video_count <= 500:  # 적정 범위
            score += 10
        elif 10 <= video_count < 20:
            score += 7
        elif video_count > 500:  # 너무 많으면 기업 채널일 수 있음
            score += 3
        
        # 6. 인스타그램 연동 (0~10점)
        if ig_data:
            ig_followers = ig_data.get('follower_count', 0) or 0
            is_private = ig_data.get('is_private', 0)
            
            if not is_private:
                score += 10
                reasons.append("인스타 공개")
            else:
                score -= 20  # 비공개는 감점
        
        return max(0, score), reasons, tier
    
    def run(self, top_n=10):
        """티어별 TOP N 출력"""
        print("=" * 80)
        print(" 티어별 인플루언서 점수 분석 (기업 홍보 최적화)")
        print("=" * 80)
        
        # 데이터 조회
        data = self.query("""
            SELECT 
                i.influencer_id, i.name,
                c.channel_id, c.subscriber_count, c.title, c.description,
                c.video_count,
                c.total_view_count,
                recent.recent_count,
                recent.days_since_last,
                recent.avg_recent_views,
                MAX(ig.ig_username) as ig_username, 
                MAX(ig.follower_count) as ig_followers,
                MAX(ig.following_count) as ig_following, 
                MAX(ig.is_private) as is_private
            FROM influencers i
            JOIN yt_channels c ON i.influencer_id = c.influencer_id
            LEFT JOIN (
                SELECT 
                    v.channel_id,
                    COUNT(*) as recent_count,
                    DATEDIFF(NOW(), MAX(v.published_at)) as days_since_last,
                    AVG(vs.view_count) as avg_recent_views
                FROM yt_videos v
                LEFT JOIN yt_video_stats vs ON v.video_id = vs.video_id
                WHERE v.published_at >= DATE_SUB(NOW(), INTERVAL 90 DAY)
                GROUP BY v.channel_id
            ) recent ON c.channel_id = recent.channel_id
            LEFT JOIN ig_accounts ig ON i.influencer_id = ig.influencer_id
            GROUP BY i.influencer_id, i.name, c.channel_id, c.subscriber_count, 
                     c.title, c.description, c.video_count, c.total_view_count,
                     recent.recent_count, recent.days_since_last, recent.avg_recent_views
        """)
        
        print(f"\n전체 채널: {len(data)}개")
        
        # 티어별 결과 저장
        tier_results = {tier: [] for tier in TIERS.keys()}
        excluded = {'doctor': 0, 'domain': 0}
        
        for row in data:
            video_count = int(row['video_count'] or 0)
            total_views = int(row['total_view_count'] or 0)
            avg_views = total_views / video_count if video_count > 0 else 0
            
            channel_data = {
                'subscriber_count': row['subscriber_count'],
                'title': row['title'],
                'description': row['description'],
                'avg_views': avg_views,
                'total_view_count': total_views,
                'video_count': video_count,
                'recent_count': int(row['recent_count'] or 0),
                'days_since_last': int(row['days_since_last'] or 999),
            }
            
            ig_data = None
            if row['ig_username']:
                ig_data = {
                    'follower_count': row['ig_followers'],
                    'following_count': row['ig_following'],
                    'is_private': row['is_private']
                }
            
            score, reasons, tier = self.calculate_score(channel_data, ig_data)
            
            if "의사/병원 제외" in reasons:
                excluded['doctor'] += 1
                continue
            if "도메인 불일치" in reasons:
                excluded['domain'] += 1
                continue
            
            tier_results[tier].append({
                'influencer_id': row['influencer_id'],
                'name': row['name'],
                'channel_id': row['channel_id'],
                'subscriber_count': row['subscriber_count'] or 0,
                'ig_username': row['ig_username'],
                'score': score,
                'reasons': reasons
            })
        
        print(f"제외: 의사/병원 {excluded['doctor']}개, 도메인 불일치 {excluded['domain']}개\n")
        
        # 티어별 정렬 및 출력
        for tier_name, tier_label in [(k, v[2]) for k, v in TIERS.items()]:
            results = tier_results[tier_name]
            results.sort(key=lambda x: x['score'], reverse=True)
            
            print("=" * 80)
            print(f" 🏆 {tier_label} TOP {min(top_n, len(results))}")
            print("=" * 80)
            
            if not results:
                print("  (해당 티어 인플루언서 없음)")
                continue
            
            print(f"{'순위':>3} | {'점수':>5} | {'채널명':20} | {'구독자':>10} | 분석")
            print("-" * 80)
            
            for i, r in enumerate(results[:top_n], 1):
                reason = ', '.join(r['reasons'][:4])
                name = (r['name'] or '-')[:18]
                ig = f"@{r['ig_username'][:10]}" if r['ig_username'] else ""
                print(f"{i:3} | {r['score']:5.0f} | {name:20} | {r['subscriber_count']:>10,} | {reason[:30]} {ig}")
            
            print()
        
        # 전체 통계
        total_beauty = sum(len(v) for v in tier_results.values())
        print(f"\n✅ 뷰티/헤어 인플루언서 총 {total_beauty}명")
        for tier_name, tier_label in [(k, v[2]) for k, v in TIERS.items()]:
            print(f"   - {tier_label}: {len(tier_results[tier_name])}명")
    
    def close(self):
        self.cursor.close()
        self.conn.close()


if __name__ == "__main__":
    top_n = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    scorer = TierScorer()
    try:
        scorer.run(top_n)
    finally:
        scorer.close()
