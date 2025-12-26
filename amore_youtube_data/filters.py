"""
헤어 인플루언서 필터링 모듈
채널과 영상의 관련성을 분석하여 점수를 계산합니다.
"""

# 헤어 관련 키워드 (가중치별 분류)
HAIR_KEYWORDS = {
    # 핵심 키워드 (높은 가중치)
    'core': [
        '헤어', '미용', '머리', '헤어스타일', '미용실', '헤어샵',
        '디자이너', '원장', '스타일리스트', '미용사',
        'hair', 'hairstyle', 'haircut', 'salon',
    ],
    # 시술 키워드 (중간 가중치)
    'treatment': [
        '펌', '염색', '탈색', '커트', '컷', '드라이',
        '레이어드', '볼륨', '셋팅', '매직',
        '빌드펌', '히피펌', '애즈펌', '다운펌',
        '투블럭', '숏컷', '단발', '장발',
        'perm', 'color', 'cut', 'styling',
    ],
    # 제품/도구 키워드 (낮은 가중치)
    'product': [
        '왁스', '젤', '스프레이', '에센스', '트리트먼트',
        '고데기', '드라이기', '아이롱',
        '샴푸', '린스', '헤어오일',
    ],
}

# 제외 키워드 (관련 없는 채널 필터링)
EXCLUDE_KEYWORDS = [
    '게임', '먹방', '축구', '야구', '음악', '노래', '댄스',
    '코딩', '프로그래밍', '주식', '부동산', '정치',
    'gaming', 'music', 'dance', 'sports',
]


def calculate_relevance_score(channel_data: dict) -> dict:
    """
    채널의 헤어 관련성 점수 계산
    
    Returns:
        {
            'total_score': int,
            'channel_score': int,
            'video_score': int,
            'is_relevant': bool,
            'matched_keywords': list
        }
    """
    channel_info = channel_data.get('channel_info', {})
    recent_videos = channel_data.get('recent_videos', [])
    
    matched_keywords = set()
    channel_score = 0
    video_score = 0
    
    # 1. 채널 정보 분석
    channel_text = ' '.join([
        channel_info.get('channel_title') or '',
        channel_info.get('channel_description') or '',
        ' '.join(channel_info.get('channel_keywords') or []),
    ]).lower()
    
    # 제외 키워드 체크
    for keyword in EXCLUDE_KEYWORDS:
        if keyword.lower() in channel_text:
            # 채널명에 헤어 키워드가 없으면서 제외 키워드가 있으면 관련 없음
            has_core = any(k.lower() in (channel_info.get('channel_title') or '').lower() 
                         for k in HAIR_KEYWORDS['core'])
            if not has_core:
                return {
                    'total_score': 0,
                    'channel_score': 0,
                    'video_score': 0,
                    'is_relevant': False,
                    'matched_keywords': [],
                    'exclude_reason': f"제외 키워드 발견: {keyword}"
                }
    
    # 핵심 키워드 (가중치 10)
    for keyword in HAIR_KEYWORDS['core']:
        if keyword.lower() in channel_text:
            channel_score += 10
            matched_keywords.add(keyword)
    
    # 시술 키워드 (가중치 5)
    for keyword in HAIR_KEYWORDS['treatment']:
        if keyword.lower() in channel_text:
            channel_score += 5
            matched_keywords.add(keyword)
    
    # 제품 키워드 (가중치 2)
    for keyword in HAIR_KEYWORDS['product']:
        if keyword.lower() in channel_text:
            channel_score += 2
            matched_keywords.add(keyword)
    
    # 2. 영상 정보 분석
    hair_video_count = 0
    
    for video in recent_videos:
        video_text = ' '.join([
            video.get('video_title', ''),
            ' '.join(video.get('video_tags', [])),
        ]).lower()
        
        video_has_hair = False
        
        for keyword in HAIR_KEYWORDS['core'] + HAIR_KEYWORDS['treatment']:
            if keyword.lower() in video_text:
                video_score += 3
                matched_keywords.add(keyword)
                video_has_hair = True
        
        if video_has_hair:
            hair_video_count += 1
    
    # 헤어 관련 영상 비율 보너스
    if recent_videos:
        hair_ratio = hair_video_count / len(recent_videos)
        if hair_ratio >= 0.6:  # 60% 이상이 헤어 관련
            video_score += 20
    
    total_score = channel_score + video_score
    
    # 관련성 판단 (최소 점수 기준)
    is_relevant = total_score >= 15  # 최소 15점 이상
    
    return {
        'total_score': total_score,
        'channel_score': channel_score,
        'video_score': video_score,
        'is_relevant': is_relevant,
        'matched_keywords': list(matched_keywords),
        'hair_video_ratio': hair_video_count / len(recent_videos) if recent_videos else 0,
    }


def filter_channels(all_data: list, min_score: int = 15) -> list:
    """
    채널 목록에서 헤어 관련 채널만 필터링
    
    Args:
        all_data: 수집된 채널 데이터 리스트
        min_score: 최소 관련성 점수 (기본 15)
    
    Returns:
        필터링된 채널 데이터 리스트 (점수 높은 순 정렬)
    """
    filtered = []
    excluded = []
    
    for channel_data in all_data:
        score_info = calculate_relevance_score(channel_data)
        
        # 점수 정보 추가
        channel_data['relevance'] = score_info
        
        if score_info['is_relevant'] and score_info['total_score'] >= min_score:
            filtered.append(channel_data)
        else:
            excluded.append(channel_data)
    
    # 점수 높은 순 정렬
    filtered.sort(key=lambda x: x['relevance']['total_score'], reverse=True)
    
    # 필터링 결과 출력
    print(f"\n📊 필터링 결과:")
    print(f"   ✅ 헤어 관련 채널: {len(filtered)}개")
    print(f"   ❌ 제외된 채널: {len(excluded)}개")
    
    if excluded:
        print(f"\n   제외된 채널 목록:")
        for ch in excluded[:5]:  # 상위 5개만 표시
            info = ch['channel_info']
            score = ch['relevance']['total_score']
            print(f"      - {info.get('channel_title', 'Unknown')} (점수: {score})")
        if len(excluded) > 5:
            print(f"      ... 외 {len(excluded) - 5}개")
    
    return filtered
