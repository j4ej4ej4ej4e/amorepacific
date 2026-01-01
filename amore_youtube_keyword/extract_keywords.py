"""
간단한 전체 분석 방식 키워드 추출
DB 전체 영상 → SBERT 필터링 → 키워드 추출 → JSON 저장
"""
import sys
import os
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
THRESHOLD = 0.50  # SBERT 헤어 관련도 임계값 (조절 가능!)
MIN_SIMILARITY = 0.50  # JSON 저장용 최소 유사도

print(f"\n⚙️  설정:")
print(f"   - SBERT Threshold: {THRESHOLD}")
print(f"   - 최소 유사도: {MIN_SIMILARITY}")
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

# 3. 키워드 추출 (ALL keywords, no top_k limit)
print("\n" + "=" * 80)
print("3️⃣ 키워드 추출 (전체)")
print("=" * 80)

miner = KeywordMiner(
    use_embedding=True,
    embedding_threshold=THRESHOLD  # 여기서 threshold 조절!
)

# 모든 키워드 추출 (빈도 제한 없음)
print("키워드 마이닝 중... (형태소 분석 + N-gram 추출)")
all_keywords_dict = miner.extract_from_texts(texts)

# dict -> list 변환
all_keywords = list(all_keywords_dict.values())
print(f"✅ 전체 {len(all_keywords)}개 키워드 추출 완료")

# 헤어 관련 키워드만 필터링 (SBERT는 이미 extract_from_texts 내부에서 실행됨)
hair_keywords = [kw for kw in all_keywords if kw.is_hair_related]
print(f"✅ 헤어 관련 키워드: {len(hair_keywords)}개 (SBERT threshold {THRESHOLD})")

# 4. 결과 정리 및 저장
print("\n" + "=" * 80)
print("4️⃣ 유사도 재계산 & 필터링")
print("=" * 80)

# JSON 구조
result = {
    'metadata': {
        'total_videos': len(videos),
        'total_keywords': 0,  # 나중에 업데이트
        'sbert_threshold': THRESHOLD,
        'min_similarity': MIN_SIMILARITY,
        'generated_at': datetime.now().isoformat(),
    },
    'keywords': []
}

# 키워드 상세 정보 (유사도 필터링 포함)
filtered_keywords = []
for kw in tqdm(hair_keywords, desc="유사도 재계산 & 필터링", unit="키워드"):
    # 유사도 계산
    similarity = miner.get_hair_similarity(kw.keyword) if miner.hair_checker else 0.0
    
    # 최소 유사도 미달 시 제외
    if similarity < MIN_SIMILARITY:
        continue
    
    filtered_keywords.append({
        'keyword': kw.keyword,
        'frequency': kw.frequency,
        'source_count': kw.source_count,
        'is_hair_related': kw.is_hair_related,
        'hair_similarity': round(similarity, 4),
    })

# 유사도 순으로 정렬
filtered_keywords.sort(key=lambda x: x['hair_similarity'], reverse=True)

# 메타데이터 업데이트
result['metadata']['total_keywords'] = len(filtered_keywords)
result['metadata']['min_similarity'] = MIN_SIMILARITY
result['keywords'] = filtered_keywords

print(f"\n✅ 필터링 완료: {len(hair_keywords)}개 → {len(filtered_keywords)}개 (유사도 {MIN_SIMILARITY} 이상)")

# JSON 저장
output_path = "output/extracted_keywords.json"
os.makedirs(os.path.dirname(output_path), exist_ok=True)  # 폴더 자동 생성
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
