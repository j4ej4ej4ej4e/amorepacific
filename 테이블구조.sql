-- 테이블 구조 확인용 쿼리
SHOW TABLES;

-- 특정 테이블(예: influencers) 구조 상세 보기
DESCRIBE influencers;


1. influencers (메인 부모 테이블)
모든 인플루언서의 기본 정보를 관리합니다.

influencer_id (PK): 인플루언서 고유 식별자 (자동 증가)

name: 인플루언서 이름 또는 활동명

category: 활동 분야 (기본값: 'hair')

confidence_score: 신뢰도 점수

created_at: 데이터 생성 일시

2. ig_accounts (인스타그램 계정 정보)
인플루언서와 1:1 또는 1:N 관계로 연결된 인스타그램 계정입니다.

ig_username (PK): 인스타그램 아이디

influencer_id (FK): influencers 테이블 참조

follower_count / following_count: 팔로워/팔로잉 수

media_count: 게시물 수

avg_reels_view: 릴스 평균 조회수

profile_biography: 프로필 소개글

3. yt_channels (유튜브 채널 정보)
인플루언서와 연결된 유튜브 채널 정보입니다.

channel_id (PK): 유튜브 고유 채널 ID

influencer_id (FK): influencers 테이블 참조

title: 채널명

subscriber_count: 구독자 수

video_count: 총 영상 개수

total_view_count: 채널 총 조회수

4. yt_videos (유튜브 개별 영상)
유튜브 채널에 업로드된 개별 영상들의 리스트입니다.

video_id (PK): 영상 고유 ID

channel_id (FK): yt_channels 테이블 참조 (삭제 시 동시 삭제 설정)

title / description: 영상 제목 및 설명

tags: 설정된 태그 목록

duration: 영상 재생 시간

5. yt_video_stats (영상별 실시간 통계)
특정 시점에 캡처된 영상의 성과 데이터입니다.

stat_id (PK): 통계 기록 고유 ID

video_id (FK): yt_videos 테이블 참조

view_count / like_count / comment_count: 조회수, 좋아요, 댓글 수

captured_at: 데이터 수집 시점

6. analysis_results (데이터 분석 결과)
인플루언서 영향력 및 가짜 계정 여부 분석 결과입니다.

analysis_id (PK): 분석 기록 고유 ID

influencer_id (FK): influencers 테이블 참조

is_fake_candidate: 가짜 계정 의심 여부 (Boolean)

bot_comment_ratio: 봇 댓글 비율

final_score: 최종 평가 점수
