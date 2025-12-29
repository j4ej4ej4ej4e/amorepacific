# HairMatch AI v2.0 - 실전 배포 버전

## 🎯 개요

**실제 TiDB 데이터베이스 스키마**에 맞춰 개발된 인플루언서 추천 시스템입니다.
- Instagram + YouTube 통합 데이터 분석
- LLM 기반 동적 점수 계산
- 자연어 요구사항 처리
- 실시간 추천 결과 제공

---

## 📦 데이터베이스 구조

### 실제 TiDB 테이블

```
amore (Database)
│
├── influencers (인플루언서 기본 정보)
│   ├── influencer_id (PK)
│   ├── name
│   ├── category (hair)
│   ├── confidence_score
│   └── created_at
│
├── ig_accounts (Instagram 계정)
│   ├── ig_username (PK)
│   ├── influencer_id (FK)
│   ├── follower_count
│   ├── following_count
│   ├── media_count
│   ├── is_private
│   ├── profile_biography
│   ├── avg_likes
│   ├── avg_comments
│   ├── engagement_rate
│   └── last_updated
│
├── yt_channels (YouTube 채널)
│   ├── channel_id (PK)
│   ├── influencer_id (FK)
│   ├── title
│   ├── subscriber_count
│   ├── video_count
│   ├── total_view_count
│   └── last_updated
│
├── yt_videos (YouTube 비디오)
│   ├── video_id (PK)
│   ├── channel_id (FK)
│   ├── title
│   ├── description
│   ├── duration
│   ├── content_hash
│   └── published_at
│
├── yt_video_stats (YouTube 통계)
│   ├── stat_id (PK)
│   ├── video_id (FK)
│   ├── view_count
│   ├── like_count
│   ├── comment_count
│   └── captured_at
│
└── analysis_results (분석 결과 저장)
    ├── analysis_id (PK)
    ├── influencer_id (FK)
    ├── is_fake_candidate
    ├── bot_comment_ratio
    ├── duplicate_content_ratio
    ├── final_score
    ├── filter_reason
    └── analyzed_at
```

---

## 🚀 실행 방법

### 1. 환경 설정

```bash
# 패키지 설치
pip install anthropic pymysql streamlit pandas

# API 키 설정
export ANTHROPIC_API_KEY='your-api-key-here'
```

### 2. CLI 버전 실행

```bash
python hairmatch_ai_system.py
```

**입력 예시:**
```
💬 원하는 인플루언서 조건을 입력하세요: 
Instagram 팔로워 5만명 이상이고 참여율 3% 이상인 헤어 인플루언서 5명

💾 분석 결과를 DB에 저장하시겠습니까? (y/n, 기본=n): y
```

### 3. 웹 UI 실행 (추천!)

```bash
streamlit run hairmatch_streamlit_app.py
```

브라우저에서 http://localhost:8501 자동 오픈

---

## 💡 시스템 동작 원리

### 1단계: 사용자 요구사항 입력
```
"Instagram 팔로워 5만 이상, 참여율 3% 이상인 인플루언서 5명"
```

### 2단계: LLM이 자동 생성

**SQL 쿼리:**
```sql
SELECT 
    i.influencer_id,
    i.name,
    i.confidence_score,
    ig.ig_username,
    ig.follower_count,
    ig.engagement_rate,
    ig.avg_likes,
    ig.avg_comments,
    yc.title as yt_channel_title,
    yc.subscriber_count
FROM influencers i
LEFT JOIN ig_accounts ig ON i.influencer_id = ig.influencer_id
LEFT JOIN yt_channels yc ON i.influencer_id = yc.influencer_id
WHERE i.category = 'hair'
  AND ig.follower_count >= 50000
  AND ig.engagement_rate >= 3
  AND ig.is_private = 0
ORDER BY ig.engagement_rate DESC
```

**점수 계산 함수:**
```python
def calculate_score(data):
    score = 0
    
    # Instagram 점수 (50%)
    if data.get('follower_count'):
        score += min(data['follower_count'] / 2000, 30)
    
    if data.get('engagement_rate'):
        score += data['engagement_rate'] * 5  # 최대 20점
    
    # YouTube 점수 (30%)
    if data.get('subscriber_count'):
        score += min(data['subscriber_count'] / 10000, 30)
    
    # 신뢰도 (20%)
    if data.get('confidence_score'):
        score += data['confidence_score'] * 0.2
    
    return max(0, min(100, score))
```

### 3단계: 데이터 조회 및 점수 계산
- TiDB에서 조건에 맞는 인플루언서 조회
- 각 인플루언서별 점수 계산
- 점수 기준 내림차순 정렬

### 4단계: TOP N 추천
```
🏆 #1 - 점수: 87.5/100
  📌 이름: 김헤어 디자이너
  📱 Instagram: @hair_designer_kim
     • 팔로워: 75,000명
     • 참여율: 5.2%
  🎬 YouTube: 헤어스타일링 채널
     • 구독자: 45,000명
```

---

## 🎪 해커톤 데모 시나리오

### 시나리오 1: 기본 기능 (3분)

**준비:**
```bash
streamlit run hairmatch_streamlit_app.py
```

**시연 순서:**
1. "Instagram 팔로워 5만 이상, 참여율 높은 인플루언서 5명" 입력
2. AI가 2-3초 내 SQL + 점수 계산 로직 생성
3. 실시간 데이터 조회 (실제 TiDB 연결)
4. TOP 5 인플루언서 표시
5. 각 인플루언서의 Instagram/YouTube 정보 확인

### 시나리오 2: 유연성 시연 (2분)

**조건 변경:**
```
1차: "Instagram 중심 인플루언서"
→ 결과 확인

2차: "YouTube 구독자가 많은 인플루언서"
→ 즉시 다른 로직 생성, 다른 결과

3차: "멀티 플랫폼 운영하는 인플루언서"
→ Instagram + YouTube 모두 있는 인플루언서만 추천
```

### 시나리오 3: 데이터 탐색 (1분)

**데이터 탐색 탭:**
- Instagram 팔로워 TOP 10 표시
- YouTube 구독자 TOP 10 표시
- 실제 데이터베이스 현황 확인

---

## 📊 주요 기능

### ✅ 멀티 플랫폼 통합
- Instagram + YouTube 데이터 동시 분석
- LEFT JOIN으로 한쪽만 있어도 포함
- 플랫폼별 가중치 조정 가능

### ✅ LLM 기반 동적 로직
- 요구사항마다 최적의 SQL 쿼리 생성
- 맞춤형 점수 계산 함수 자동 생성
- NULL 값 처리 자동화

### ✅ 실시간 분석
- 4-5초 내 결과 제공
- 실제 TiDB 데이터 조회
- 대규모 데이터 처리 가능

### ✅ 분석 결과 저장
- analysis_results 테이블에 저장
- 가짜 계정 판단 결과 포함
- 필터링 사유 기록

---

## 🔧 고급 기능

### 1. 분석 결과 저장

```python
system = HairMatchAI(api_key)
result = system.recommend(
    "Instagram 팔로워 많은 인플루언서", 
    save_results=True  # DB에 저장
)
```

저장되는 정보:
- `is_fake_candidate`: 가짜 계정 의심 여부
- `bot_comment_ratio`: 봇 댓글 비율
- `final_score`: 최종 점수
- `filter_reason`: 필터링 사유

### 2. 커스텀 쿼리

직접 SQL 작성도 가능:
```python
conn = pymysql.connect(**DB_CONFIG)
cursor = conn.cursor()

query = """
SELECT i.name, ig.follower_count, yc.subscriber_count
FROM influencers i
LEFT JOIN ig_accounts ig ON i.influencer_id = ig.influencer_id
LEFT JOIN yt_channels yc ON i.influencer_id = yc.influencer_id
WHERE ig.engagement_rate > 5
"""

cursor.execute(query)
results = cursor.fetchall()
```

### 3. 통계 조회

```python
# 평균 팔로워 수
SELECT AVG(follower_count) FROM ig_accounts WHERE follower_count > 0

# 평균 참여율
SELECT AVG(engagement_rate) FROM ig_accounts WHERE engagement_rate > 0

# 플랫폼별 분포
SELECT 
    COUNT(DISTINCT CASE WHEN ig.ig_username IS NOT NULL THEN i.influencer_id END) as ig_count,
    COUNT(DISTINCT CASE WHEN yc.channel_id IS NOT NULL THEN i.influencer_id END) as yt_count,
    COUNT(DISTINCT CASE WHEN ig.ig_username IS NOT NULL AND yc.channel_id IS NOT NULL THEN i.influencer_id END) as both_count
FROM influencers i
LEFT JOIN ig_accounts ig ON i.influencer_id = ig.influencer_id
LEFT JOIN yt_channels yc ON i.influencer_id = yc.influencer_id
```

---

## 📈 성능 최적화

### 인덱스 추가 (권장)

```sql
-- Instagram 검색 최적화
CREATE INDEX idx_ig_follower ON ig_accounts(follower_count);
CREATE INDEX idx_ig_engagement ON ig_accounts(engagement_rate);

-- YouTube 검색 최적화
CREATE INDEX idx_yt_subscriber ON yt_channels(subscriber_count);

-- 분석 결과 검색
CREATE INDEX idx_analysis_score ON analysis_results(final_score);
CREATE INDEX idx_analysis_influencer ON analysis_results(influencer_id);
```

---

## 🎯 사용 예시

### 예시 1: Instagram 중심 추천
```
입력: "Instagram 팔로워 5만 이상, 참여율 3% 이상인 헤어 인플루언서 5명"

결과:
🏆 #1 - 점수: 89.2/100
  • Instagram: @hair_master_kim (팔로워 75K, 참여율 5.2%)
  • YouTube: 헤어튜토리얼 채널 (구독자 45K)
```

### 예시 2: YouTube 중심 추천
```
입력: "YouTube 구독자 10만 이상, 조회수가 높은 인플루언서"

결과:
🏆 #1 - 점수: 92.5/100
  • YouTube: 프로헤어스타일리스트 (구독자 150K, 총 조회수 5M)
  • Instagram: @pro_hairstylist (팔로워 35K)
```

### 예시 3: 멀티 플랫폼
```
입력: "Instagram과 YouTube를 모두 운영하는 인플루언서"

결과:
→ 양쪽 플랫폼 모두 있는 인플루언서만 추천
→ 플랫폼 간 시너지 점수 가산
```

---

## 🛡️ 가짜 계정 필터링

### 자동 필터링 기준

1. **비공개 계정**: `is_private = 1`
2. **낮은 참여율**: `engagement_rate < 1%`
3. **팔로워 대비 낮은 참여**: 팔로워는 많은데 좋아요/댓글 적음
4. **의심스러운 패턴**: 팔로잉/팔로워 비율 이상

### 신뢰도 점수

```python
# confidence_score 기반 평가
if confidence_score > 80:  # 높은 신뢰도
    score += 20
elif confidence_score > 50:  # 중간 신뢰도
    score += 10
else:  # 낮은 신뢰도
    score += 0
```

---

## 🚧 향후 개발 계획

### Phase 1: 기능 고도화
- [ ] 실제 봇 댓글 패턴 분석
- [ ] 중복 콘텐츠 감지 (content_hash 활용)
- [ ] 시계열 분석 (성장 추이)

### Phase 2: 플랫폼 확장
- [ ] TikTok 데이터 통합
- [ ] 네이버 블로그 분석
- [ ] 크로스 플랫폼 영향력 분석

### Phase 3: AI 고도화
- [ ] 이미지 분석 (멀티모달)
- [ ] 트렌드 예측
- [ ] 자동 리포트 생성

---

## 📞 문의

**프로젝트:** HairMatch AI v2.0  
**개발자:** 이재윤  
**목적:** 해커톤 경진대회  
**기술스택:** Python, TiDB Cloud, Claude API, Streamlit

---

## 📄 파일 구조

```
├── hairmatch_ai_system.py          # CLI 메인 시스템
├── hairmatch_streamlit_app.py      # Streamlit 웹 앱
├── requirements.txt                # 패키지 의존성
└── README.md                       # 이 문서
```

---

## ✨ 특징

1. **실전 배포 가능**: 실제 TiDB 스키마 기반
2. **확장 가능**: 새 플랫폼 추가 용이
3. **유지보수 용이**: LLM이 로직 자동 생성
4. **사용자 친화적**: 자연어 인터페이스

**"말로 하면, AI가 알아서 해줍니다."**

🚀 HairMatch AI v2.0 - The Future of Influencer Marketing