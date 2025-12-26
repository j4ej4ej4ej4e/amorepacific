"""
YouTube 헤어 인플루언서 데이터 수집 메인 스크립트
수집된 데이터는 JSON 형식으로 저장됩니다.
"""
import json
import os
from datetime import datetime
from collector import YouTubeCollector
from filters import filter_channels, calculate_relevance_score


def main():
    # ============================================
    # 설정
    # ============================================
    # ============================================
    # 검색 키워드 전략
    # ============================================
    # Strategy A: 고민/리뷰 키워드 (Reviewer Targeting)
    # - 인플루언서는 '제품'과 '방법'을 공유
    REVIEW_KEYWORDS = [
        "셀프 염색 후기",
        "셀프 헤어 스타일링",
        "고데기 추천",
        "드라이기 추천",
        "헤어오일 추천",
    ]
    
    # Strategy B: 경쟁사/브랜드 키워드 (Competitor Targeting)
    # - 이미 헤어 브랜드와 협업 경험이 있는 인플루언서
    BRAND_KEYWORDS = [
        "다이슨 에어랩 후기",
        "아모스 헤어",
        "모레모 추천",
        "미쟝센 헤어",
    ]
    
    # Strategy C: 스타일/무드 키워드 (Style Targeting)
    # - 인물 중심 + 헤어 조합
    STYLE_KEYWORDS = [
        "데일리 헤어 루틴",
        "출근 헤어 스타일링",
    ]
    
    SEARCH_KEYWORDS = REVIEW_KEYWORDS + BRAND_KEYWORDS + STYLE_KEYWORDS
    SEARCH_LIMIT_PER_KEYWORD = 5  # 키워드당 검색할 영상 수
    VIDEOS_PER_CHANNEL = 5         # 채널당 수집할 최근 영상 수
    OUTPUT_DIR = "output"
    
    # ============================================
    # 수집 시작
    # ============================================
    print("=" * 60)
    print("YouTube 인플루언서 데이터 수집기")
    print(f"시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print(f"검색 키워드: {SEARCH_KEYWORDS}")
    print(f"키워드당 스캔 영상 수: {SEARCH_LIMIT_PER_KEYWORD}")
    print(f"채널당 수집 영상 수: {VIDEOS_PER_CHANNEL}")
    print("=" * 60 + "\n")
    
    # 출력 디렉토리 생성
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    collector = YouTubeCollector()
    all_data = []
    processed_channel_ids = set()
    
    # 키워드별 검색
    for keyword in SEARCH_KEYWORDS:
        print(f"\n{'─' * 40}")
        print(f"🔍 키워드: {keyword}")
        print('─' * 40)
        
        # 채널 검색
        channels = collector.search_channels(keyword, limit=SEARCH_LIMIT_PER_KEYWORD)
        
        for ch in channels:
            channel_id = ch['channel_id']
            
            # 중복 채널 스킵
            if channel_id in processed_channel_ids:
                continue
            
            processed_channel_ids.add(channel_id)
            
            # 채널 데이터 수집
            try:
                channel_data = collector.collect_channel_data(
                    ch['channel_url'],
                    video_limit=VIDEOS_PER_CHANNEL
                )
                
                if channel_data:
                    all_data.append(channel_data)
                    
            except Exception as e:
                print(f"  ❌ 수집 실패: {ch.get('channel_title', 'Unknown')} - {e}")
    
    # ============================================
    # 필터링 적용
    # ============================================
    if all_data:
        print("\n" + "=" * 60)
        print("🔎 헤어 관련 채널 필터링 중...")
        print("=" * 60)
        
        filtered_data = filter_channels(all_data, min_score=15)
        
        if not filtered_data:
            print("\n❌ 필터링 후 헤어 관련 채널이 없습니다.")
            return
        
        # JSON 저장 (필터링된 데이터만)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        json_path = os.path.join(OUTPUT_DIR, f"hair_influencers_{timestamp}.json")
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(filtered_data, f, ensure_ascii=False, indent=2)
        
        # 요약 출력
        print("\n" + "=" * 60)
        print("✅ 수집 및 필터링 완료!")
        print("=" * 60)
        print(f"수집된 전체 채널: {len(all_data)}개")
        print(f"필터링된 채널: {len(filtered_data)}개")
        total_videos = sum(len(ch['recent_videos']) for ch in filtered_data)
        print(f"총 영상 수: {total_videos}개")
        print(f"저장 위치: {os.path.abspath(json_path)}")
        print("=" * 60)
        
        # 채널 목록 출력 (점수 포함)
        print("\n📋 헤어 인플루언서 목록 (관련성 점수순):")
        for i, ch in enumerate(filtered_data, 1):
            info = ch['channel_info']
            relevance = ch.get('relevance', {})
            subs = info.get('subscriber_count')
            subs_str = f"{subs:,}" if subs else "N/A"
            score = relevance.get('total_score', 0)
            keywords = ', '.join(relevance.get('matched_keywords', [])[:5])
            print(f"  {i:2d}. {info['channel_title']}")
            print(f"      구독자: {subs_str} | 점수: {score} | 키워드: {keywords}")
    else:
        print("\n❌ 수집된 데이터가 없습니다.")


if __name__ == "__main__":
    main()
