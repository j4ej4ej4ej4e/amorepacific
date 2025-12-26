"""
빠른 테스트용 스크립트
작은 규모로 실행하여 파이프라인이 잘 동작하는지 확인합니다.
"""
import sys
sys.path.insert(0, '.')

print("=" * 60)
print("🧪 키워드 파이프라인 테스트")
print("=" * 60)

# 1. Seed 키워드 테스트
print("\n[1/5] 📌 Seed 키워드 생성 테스트")
print("-" * 40)
try:
    from keyword_engine.seed_keywords import SeedKeywordGenerator, DEFAULT_SEED_KEYWORDS
    
    generator = SeedKeywordGenerator()
    sample_seeds = generator.generate_by_category("hair_care", limit=5)
    
    print(f"✅ 성공! 기본 시드 {len(DEFAULT_SEED_KEYWORDS)}개 로드됨")
    print(f"   생성된 예시 (hair_care):")
    for kw in sample_seeds[:3]:
        print(f"     - {kw}")
except Exception as e:
    print(f"❌ 실패: {e}")
    sys.exit(1)

# 2. YouTube 검색 테스트
print("\n[2/5] 🔍 YouTube 검색 테스트")
print("-" * 40)
try:
    from keyword_engine.youtube_searcher import YouTubeSearcher
    
    searcher = YouTubeSearcher(quiet=True)
    test_query = "허쉬컷 스타일링"
    
    print(f"   검색어: '{test_query}'")
    videos = searcher.search(test_query, limit=5)
    
    print(f"✅ 성공! {len(videos)}개 영상 수집")
    for v in videos[:3]:
        print(f"     - [{v.channel_title}] {v.title[:30]}...")
        print(f"       조회수: {v.view_count:,}")
except Exception as e:
    print(f"❌ 실패: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 3. 키워드 채굴 테스트
print("\n[3/5] ⛏️ 키워드 채굴 테스트")
print("-" * 40)
try:
    from keyword_engine.keyword_miner import KeywordMiner
    
    miner = KeywordMiner()
    
    # 영상 제목들에서 키워드 추출
    texts = [v.title for v in videos]
    print(f"   분석할 텍스트 {len(texts)}개")
    
    keywords = miner.extract_hair_keywords(texts, top_k=10)
    
    print(f"✅ 성공! {len(keywords)}개 키워드 채굴")
    for kw in keywords[:5]:
        print(f"     - {kw.keyword} (빈도: {kw.frequency})")
except Exception as e:
    print(f"❌ 실패: {e}")
    import traceback
    traceback.print_exc()
    # 이건 실패해도 계속 진행 (konlpy 없을 수 있음)

# 4. 스코어링 테스트
print("\n[4/5] 📊 스코어링 테스트")
print("-" * 40)
try:
    from keyword_engine.query_scorer import QueryScorer
    
    scorer = QueryScorer()
    score = scorer.score(test_query, videos)
    
    print(f"✅ 성공! 쿼리 '{test_query}' 스코어링 완료")
    print(f"   - 다양성: {score.diversity_score:.2f}")
    print(f"   - 최신성: {score.freshness_score:.2f}")
    print(f"   - 전문성: {score.expertise_score:.2f}")
    print(f"   - 성과: {score.performance_score:.2f}")
    print(f"   - 관련성: {score.relevance_score:.2f}")
    print(f"   ─────────────────")
    print(f"   📈 총점: {score.total_score:.2f}")
    print(f"   🔄 확장 여부: {'예' if score.should_expand else '아니오'}")
except Exception as e:
    print(f"❌ 실패: {e}")
    import traceback
    traceback.print_exc()

# 5. 미니 트리 확장 테스트 (깊이 1만)
print("\n[5/5] 🌳 미니 트리 확장 테스트 (깊이 1)")
print("-" * 40)
try:
    from keyword_engine.tree_expander import KeywordTreeExpander
    
    expander = KeywordTreeExpander(
        max_depth=1,      # 깊이 1만 (빠른 테스트)
        top_k_per_level=3, # 레벨당 3개만
        videos_per_search=5,
        quiet=False
    )
    
    # 시드 1개로만 테스트
    mini_seeds = ["허쉬컷 스타일링"]
    
    print(f"   시드: {mini_seeds}")
    print(f"   설정: 깊이 1, 레벨당 3개")
    print()
    
    expander.expand(mini_seeds)
    
    print(f"\n✅ 성공! {len(expander.all_keywords)}개 키워드 발굴")
    print(f"\n   발굴된 키워드:")
    for kw in expander.get_top_keywords(10):
        print(f"     - {kw.keyword} (점수: {kw.score:.2f}, 깊이: {kw.depth})")
        
except Exception as e:
    print(f"❌ 실패: {e}")
    import traceback
    traceback.print_exc()

# 결과 요약
print("\n" + "=" * 60)
print("🎉 테스트 완료!")
print("=" * 60)
print("""
다음 단계:
  1. 위 테스트가 모두 성공했다면, 전체 파이프라인을 실행하세요:
     python main.py --depth 2 --top-k 5
  
  2. 더 큰 규모로 실행:
     python main.py --depth 5 --top-k 10
     (약 30분~1시간 소요)

  3. 결과 확인:
     output/ 폴더의 JSON 파일
""")
