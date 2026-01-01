"""
간단한 전체 분석 방식 키워드 추출
DB 전체 영상 → SBERT 필터링 → 키워드 추출 → JSON 저장
"""
import sys
import time
import json
from datetime import datetime
from tqdm import tqdm  # 진행도 표시

from keyword_engine.db_video_loader import DBVideoLoader
from keyword_engine.keyword_miner import KeywordMiner

print("=" * 80)
print("🎯 전체 DB 분석 키워드 추출")
print("=" * 80)

# 설정
THRESHOLD = 0.35  # SBERT 헤어 관련도 임계값 (조절 가능!)

print(f"\n⚙️  설정:")
print(f"   - SBERT Threshold: {THRESHOLD}")
print(f"   - 데이터: TiDB 전체 영상\n")

start_time = time.time()

# 1. DB 로더 초기화
print("=" * 80)
print("1️⃣ DB에서 전체 영상 로드")
print("=" * 80)
loader = DBVideoLoader(quiet=False)
videos = loader.get_all_videos()  # 전체 로드!
loader.close()

print(f"\n✅ {len(videos)}개 영상 로드 완료")

# 2. 텍스트 추출
print("\n" + "=" * 80)
print("2️⃣ 텍스트 추출 (title + description + tags)")
print("=" * 80)

texts = []
for video in tqdm(videos, desc="텍스트 추출", unit="영상"):
    text_parts = [
        video.get('title', ''),
        video.get('description', ''),
        ' '.join(video.get('tags', [])),
    ]
    texts.append(' '.join(text_parts))

print(f"✅ {len(texts)}개 텍스트 추출 완료")

# 3. 키워드 추출 (SBERT 필터링 포함)
print("\n" + "=" * 80)
print("3️⃣ 키워드 추출 (SBERT 헤어 관련도 필터링)")
print("=" * 80)

miner = KeywordMiner(
    use_embedding=True,
    embedding_threshold=THRESHOLD  # 여기서 threshold 조절!
)

# 헤어 관련 키워드만 추출
print("키워드 마이닝 중... (SBERT 연산 포함, 시간이 걸릴 수 있습니다)")
keywords = miner.extract_hair_keywords(texts, top_k=200)

print(f"\n✅ {len(keywords)}개 키워드 추출 완료")

# 4. 결과 정리 및 저장
print("\n" + "=" * 80)
print("4️⃣ 결과 저장")
print("=" * 80)

# JSON 구조
result = {
    'metadata': {
        'total_videos': len(videos),
        'total_keywords': len(keywords),
        'sbert_threshold': THRESHOLD,
        'generated_at': datetime.now().isoformat(),
    },
    'keywords': []
}

# 키워드 상세 정보
for kw in tqdm(keywords, desc="유사도 계산", unit="키워드"):
    # 유사도 계산
    similarity = miner.get_hair_similarity(kw.keyword) if miner.hair_checker else 0.0
    
    result['keywords'].append({
        'keyword': kw.keyword,
        'frequency': kw.frequency,
        'source_count': kw.source_count,
        'is_hair_related': kw.is_hair_related,
        'hair_similarity': round(similarity, 4),
    })

# JSON 저장
output_path = "output/extracted_keywords.json"
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"💾 {output_path} 저장 완료")

# 5. 상위 키워드 출력
print("\n" + "=" * 80)
print("🏆 상위 30개 키워드")
print("=" * 80)

for i, kw_data in enumerate(result['keywords'][:30], 1):
    status = "✅" if kw_data['is_hair_related'] else "❌"
    print(f"{i:2d}. {status} {kw_data['keyword']:25s} "
          f"(유사도: {kw_data['hair_similarity']:.3f}, "
          f"빈도: {kw_data['frequency']})")

elapsed_time = time.time() - start_time

print("\n" + "=" * 80)
print(f"⏱️  소요 시간: {elapsed_time:.2f}초")
print(f"✅ 완료!")
print("=" * 80)

print(f"""
📝 다음 단계:
1. output/extracted_keywords.json 파일 확인
2. 키워드 직접 검토 (헤어 관련인지 확인)
3. Threshold 조정 필요 시:
   - 너무 많은 비관련 키워드 → THRESHOLD 올리기 (예: 0.40)
   - 놓친 키워드 많음 → THRESHOLD 낮추기 (예: 0.30)
   - 이 파일 상단 THRESHOLD 값 수정 후 재실행
""")
