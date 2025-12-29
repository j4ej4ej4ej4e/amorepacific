"""
인플루언서 점수 시스템 (유튜브 기준 + 인스타 가점)
- 유튜브 데이터 기반 점수 계산
- 인스타그램 연동 시 가점
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
    """의사/병원 관련 채널인지 확인"""
    if not text:
        return False
    text_lower = text.lower()
    for keyword in EXCLUDE_KEYWORDS:
        if keyword.lower() in text_lower:
            return True
    return False


class InfluencerScorer:
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
        """유튜브 기준 점수 계산 + 인스타 가점"""
        score = 0
        reasons = []
        
        # ===== 유튜브 기반 점수 =====
        
        subscriber_count = channel_data.get('subscriber_count', 0) or 0
        description = channel_data.get('description', '') or ''
        title = channel_data.get('title', '') or ''
        avg_views = channel_data.get('avg_views', 0) or 0
        total_view_count = channel_data.get('total_view_count', 0) or 0
        video_count = channel_data.get('video_count', 0) or 0
        
        # 1. 구독자 수 (0~30점) - log 스케일
        if subscriber_count > 0:
            sub_score = min(30, math.log10(subscriber_count) * 5)
            score += sub_score
            if subscriber_count > 100000:
                reasons.append(f"구독자 {subscriber_count:,}")
        
        # 2. 조회율 (0~20점)
        if subscriber_count > 0 and avg_views > 0:
            view_rate = (avg_views / subscriber_count) * 100
            if view_rate > 50:
                score += 20
                reasons.append(f"조회율 {view_rate:.0f}%")
            elif view_rate > 20:
                score += 15
            elif view_rate > 10:
                score += 10
            elif view_rate > 5:
                score += 5
        
        # 3. 총 조회수 규모 (0~15점)
        if total_view_count > 0:
            if total_view_count > 100000000:  # 1억 이상
                score += 15
                reasons.append(f"총조회 {total_view_count//1000000}M")
            elif total_view_count > 10000000:  # 1천만 이상
                score += 10
            elif total_view_count > 1000000:  # 100만 이상
                score += 5
        
        # 4. 영상 개수 (0~10점)
        if video_count >= 20:
            score += 10
            reasons.append(f"영상 {video_count}개")
        elif video_count >= 10:
            score += 7
        elif video_count >= 5:
            score += 5
        elif video_count >= 3:
            score += 3
        
        # 5. 최근 활동성 (0~15점)
        recent_count = channel_data.get('recent_count', 0) or 0
        days_since_last = channel_data.get('days_since_last', 999) or 999
        avg_recent_views = channel_data.get('avg_recent_views', 0) or 0
        
        # 최근 90일 내 영상 있으면 가점
        if recent_count > 0:
            if days_since_last <= 7:  # 7일 이내
                score += 10
                reasons.append("최근활동")
            elif days_since_last <= 30:  # 30일 이내
                score += 7
            elif days_since_last <= 90:  # 90일 이내
                score += 3
            
            # 최근 영상 평균 조회수 가점
            if avg_recent_views > 100000:
                score += 5
                reasons.append(f"최근조회 {int(avg_recent_views):,}")
            elif avg_recent_views > 10000:
                score += 3
        
        # 6. 도메인 판단 (채널 Topic + 영상 카테고리 조합)
        topic_categories = channel_data.get('topic_categories', '') or ''
        beauty_category_ratio = channel_data.get('beauty_category_ratio', 0) or 0
        is_doctor = is_excluded(description) or is_excluded(title)
        
        # 뷰티 관련 Topic 키워드
        beauty_topics = ['beauty', 'fashion', 'hairstyle', 'cosmetics', 'lifestyle']
        has_beauty_topic = any(bt in topic_categories.lower() for bt in beauty_topics)
        
        # 영상 카테고리 22/26 비율 50% 이상
        has_beauty_category = beauty_category_ratio >= 0.5
        
        if is_doctor:
            score -= 50
            reasons.append("의사/병원 제외")
        elif has_beauty_topic and has_beauty_category:
            # Topic + 카테고리 둘 다 만족
            score += 35
            topic_name = topic_categories.split(',')[0][:10] if topic_categories else ''
            reasons.append(f"Topic+카테:{topic_name}")
        elif has_beauty_topic:
            # Topic만 만족
            score += 25
            topic_name = topic_categories.split(',')[0][:12] if topic_categories else ''
            reasons.append(f"Topic:{topic_name}")
        elif has_beauty_category:
            # 카테고리만 만족
            score += 20
            reasons.append(f"카테고리 {beauty_category_ratio*100:.0f}%")
        else:
            score -= 70
            reasons.append("도메인 불일치")
        
        # ===== 인스타그램 가점 =====
        
        if ig_data:
            ig_followers = ig_data.get('follower_count', 0) or 0
            ig_following = ig_data.get('following_count', 0) or 0
            is_private = ig_data.get('is_private', 0)
            
            # 인스타 연동 기본 가점
            score += 10
            reasons.append("인스타 연동")
            
            # 인스타 팔로워 가점 (0~15점)
            if ig_followers > 100000:
                score += 15
                reasons.append(f"인스타 {ig_followers:,}")
            elif ig_followers > 50000:
                score += 10
            elif ig_followers > 10000:
                score += 5
            
            # 팔로워/팔로잉 비율 가점 (0~5점)
            if ig_following > 0:
                ratio = ig_followers / ig_following
                if ratio > 10:
                    score += 5
            
            # 비공개 감점
            if is_private:
                score -= 50
                reasons.append("인스타 비공개")
        
        return max(0, score), reasons
    
    def run(self, top_n=10):
        """메인 실행"""
        print("=" * 70)
        print(" 인플루언서 점수 분석 (유튜브 기준 + 인스타 가점)")
        print("=" * 70)
        
        # [점수 초기화] 계산 시작 전 모든 점수를 0으로 리셋 (과거 점수 잔존 방지)
        print("[초기화] 기존 점수(confidence_score, bot_score)를 모두 0으로 초기화합니다...")
        self.cursor.execute("UPDATE influencers SET confidence_score = 0")
        self.cursor.execute("UPDATE analysis_results SET bot_score = 0")
        print("✅ 초기화 완료. 점수 재계산 중...")
        
        # 유튜브 채널 + 최근 영상 통계 + Topic + 카테고리 + 인스타 조회
        data = self.query("""
            SELECT 
                i.influencer_id, i.name,
                c.channel_id, c.subscriber_count, c.title, c.description,
                c.video_count,
                c.total_view_count,
                c.topic_categories,
                recent.recent_count,
                recent.days_since_last,
                recent.avg_recent_views,
                recent.avg_recent_likes,
                recent.avg_recent_comments,
                cat.beauty_category_ratio,
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
                    AVG(vs.view_count) as avg_recent_views,
                    AVG(vs.like_count) as avg_recent_likes,
                    AVG(vs.comment_count) as avg_recent_comments
                FROM yt_videos v
                LEFT JOIN yt_video_stats vs ON v.video_id = vs.video_id
                WHERE v.published_at >= DATE_SUB(NOW(), INTERVAL 90 DAY)
                GROUP BY v.channel_id
            ) recent ON c.channel_id = recent.channel_id
            LEFT JOIN (
                SELECT 
                    channel_id,
                    SUM(CASE WHEN category_id IN (22, 26) THEN 1 ELSE 0 END) / COUNT(*) as beauty_category_ratio
                FROM yt_videos
                WHERE category_id IS NOT NULL
                GROUP BY channel_id
            ) cat ON c.channel_id = cat.channel_id
            LEFT JOIN ig_accounts ig ON i.influencer_id = ig.influencer_id
            GROUP BY i.influencer_id, i.name, c.channel_id, c.subscriber_count, 
                     c.title, c.description, c.video_count, c.total_view_count,
                     c.topic_categories,
                     recent.recent_count, recent.days_since_last, recent.avg_recent_views, recent.avg_recent_likes, recent.avg_recent_comments,
                     cat.beauty_category_ratio
            ORDER BY c.subscriber_count DESC
        """)
        
        total = len(data)
        print(f"\n유튜브 채널: {total}개")
        
        results = []
        beauty_count = 0
        ig_count = 0
        
        for idx, row in enumerate(data, 1):
            if idx % 50 == 0:
                print(f"  진행: {idx}/{total}")
            
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
                'avg_recent_views': float(row['avg_recent_views'] or 0),
                'avg_recent_likes': float(row['avg_recent_likes'] or 0),
                'avg_recent_comments': float(row['avg_recent_comments'] or 0),
                'topic_categories': row['topic_categories'] or '',
                'beauty_category_ratio': float(row['beauty_category_ratio'] or 0)
            }
            
            ig_data = None
            if row['ig_username']:
                ig_count += 1
                ig_data = {
                    'follower_count': row['ig_followers'],
                    'following_count': row['ig_following'],
                    'is_private': row['is_private']
                }
            
            score, reasons = self.calculate_score(channel_data, ig_data)

            # [봇 패턴 감지]
            bot_score = 0
            
            # 1. Engagement Mismatch (조회수 높지만 반응 저조)
            # 조건: 최근 평균 조회수 > 1000 AND (좋아요+댓글)/조회수 < 0.1%
            # 예외: 좋아요가 0이면(숨김 설정) 판단하지 않음 (건너뜀)
            if channel_data['avg_recent_views'] > 1000:
                likes = channel_data['avg_recent_likes']
                comments = channel_data['avg_recent_comments']
                views = channel_data['avg_recent_views']
                
                # 좋아요가 0이면(숨김) 무조건 PASS
                if likes > 0:
                    engagement = likes + comments
                    if engagement / views < 0.001:
                        bot_score += 50
                        reasons.append("봇의심:반응저조")

            # 2. Silent Viewers (유령 구독자)
            # 조건: 구독자 > 10,000 AND 조회수/구독자 < 0.5% (기존 1%에서 완화)
            # 예외: avg_recent_views가 0이면(수집된 최근 영상 없음) 판단하지 않음
            sub_count = channel_data['subscriber_count'] or 0
            avg_views = channel_data['avg_recent_views']
            
            if avg_views > 0 and sub_count > 10000:
                if avg_views / sub_count < 0.005:
                    bot_score += 30
                    reasons.append("봇의심:유령구독자")

            # 3. Content Factory (공장형 업로드)
            if channel_data['recent_count'] > 300:
                bot_score += 20
                reasons.append("봇의심:공장형")
            
            # bot_score 저장 (analysis_results 테이블)
            if bot_score > 0:
                try:
                   self.cursor.execute("""
                       INSERT INTO analysis_results (influencer_id, bot_score) 
                       VALUES (%s, %s)
                       ON DUPLICATE KEY UPDATE bot_score = VALUES(bot_score)
                   """, (row['influencer_id'], bot_score))
                except Exception as e:
                    pass # 이미 존재하는 등 에러 무시

            if "뷰티/헤어" in reasons:
                beauty_count += 1
            
            results.append({
                'influencer_id': row['influencer_id'],
                'name': row['name'],
                'channel_id': row['channel_id'],
                'subscriber_count': row['subscriber_count'] or 0,
                'ig_username': row['ig_username'],
                'score': score,
                'reasons': reasons
            })
        
        print(f"  완료! (뷰티/헤어: {beauty_count}, 인스타 연동: {ig_count})")
        
        # 점수순 정렬
        results.sort(key=lambda x: x['score'], reverse=True)
        
        # 전체 순위 출력
        print(f"\n{'=' * 70}")
        print(f" 🏆 전체 순위 ({len(results)}명)")
        print("=" * 70)
        print(f"{'순위':>3} | {'점수':>5} | {'채널명':20} | {'구독자':>10} | 분석")
        print("-" * 70)
        
        for i, r in enumerate(results, 1):
            reason = ', '.join(r['reasons'][:3]) if r['reasons'] else '-'
            name = r['name'][:20] if r['name'] else '-'
            print(f"{i:3} | {r['score']:5.0f} | {name:20} | {r['subscriber_count']:>10,} | {reason[:25]}")
        
        # DB 업데이트
        print("\n[점수 저장 중...]")
        for r in results:
            self.cursor.execute(
                "UPDATE influencers SET confidence_score = %s WHERE influencer_id = %s",
                (r['score'], r['influencer_id'])
            )
        print("[저장 완료]")
        
        # 통계
        beauty_results = [r for r in results if "뷰티/헤어" in r['reasons']]
        if beauty_results:
            scores = [r['score'] for r in beauty_results]
            print(f"\n뷰티/헤어 {len(beauty_results)}명 | 점수: {min(scores):.0f} ~ {max(scores):.0f}")
        
        return results[:top_n]
    
    def close(self):
        self.cursor.close()
        self.conn.close()


if __name__ == "__main__":
    top_n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    scorer = InfluencerScorer()
    try:
        scorer.run(top_n)
    finally:
        scorer.close()
