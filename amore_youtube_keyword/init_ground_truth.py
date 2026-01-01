"""
초기 Ground Truth 데이터 생성

optimize_threshold.py에 정의된 44개 테스트 데이터를
ground_truth.json 파일로 변환합니다.
"""

import json
import sys
sys.path.insert(0, '.')

from keyword_engine.hair_embedder import HairRelevanceChecker

# optimize_threshold.py의 테스트 데이터
INITIAL_DATA = {
    # 헤어 관련 키워드
    'hair_related': [
        # 1. 스타일/시술
        "허쉬컷 스타일링",
        "레이어드컷 튜토리얼",
        "볼륨펌 후기",
        "탈색 과정",
        "염색 셀프",
        "매직 클리닉",
        
        # 2. 제품/케어
        "두피 케어 루틴",
        "탈모 샴푸 추천",
        "손상모 트리트먼트",
        "헤어오일 사용법",
        "단백질 트리트먼트",
        
        # 3. 전문용어
        "미용실 추천",
        "헤어디자이너",
        "살롱케어",
        
        # 4. 상태/문제
        "곱슬머리 관리",
        "정수리 볼륨",
        "앞머리 셋팅",
        "가르마 고정",
        
        # 5. 니치/트렌드
        "셀프 히피펌",
        "애즈펌 스타일링",
        "시스루뱅 자르기",
        "찰랑이는 머릿결",
    ],
    
    # 경계 사례
    'boundary_cases': [
        ("볼륨감 살리기", True),
        ("윤기나는 방법", True),
        ("건강한 모발", True),
        ("푸석함 개선", True),
        ("건조함 해결", False),
        ("영양크림", False),
        ("수분 충전", False),
    ],
    
    # 비관련
    'non_related': [
        # 인접 뷰티
        "메이크업 루틴",
        "스킨케어 추천",
        "네일 아트",
        "속눈썹 펌",
        
        # 패션
        "패션 코디네이션",
        "악세서리 추천",
        "옷 스타일링",
        
        # 라이프스타일
        "맛집 추천",
        "카페 브이로그",
        "여행 일정",
        "홈트레이닝",
        
        # 기타
        "게임 리뷰",
        "주식 투자",
        "요리 레시피",
        "반려동물",
    ]
}


def create_initial_ground_truth(output_path='data/ground_truth.json'):
    """초기 Ground Truth 파일 생성"""
    print("\n🔧 초기 Ground Truth 생성 중...")
    
    # HairRelevanceChecker 초기화
    checker = HairRelevanceChecker()
    
    ground_truth = []
    
    # 헤어 관련
    print(f"\n1️⃣ 헤어 관련 키워드 처리 중...")
    for keyword in INITIAL_DATA['hair_related']:
        similarity = checker.get_similarity(keyword)
        ground_truth.append({
            'keyword': keyword,
            'is_hair_related': True,
            'similarity': float(similarity),
            'note': '초기 데이터 (헤어 관련)',
            'timestamp': '2025-12-27T00:00:00'
        })
    
    # 경계 사례
    print(f"2️⃣ 경계 사례 처리 중...")
    for keyword, is_hair in INITIAL_DATA['boundary_cases']:
        similarity = checker.get_similarity(keyword)
        ground_truth.append({
            'keyword': keyword,
            'is_hair_related': is_hair,
            'similarity': float(similarity),
            'note': '초기 데이터 (경계 사례)',
            'timestamp': '2025-12-27T00:00:00'
        })
    
    # 비관련
    print(f"3️⃣ 비관련 키워드 처리 중...")
    for keyword in INITIAL_DATA['non_related']:
        similarity = checker.get_similarity(keyword)
        ground_truth.append({
            'keyword': keyword,
            'is_hair_related': False,
            'similarity': float(similarity),
            'note': '초기 데이터 (비관련)',
            'timestamp': '2025-12-27T00:00:00'
        })
    
    # 저장
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(ground_truth, f, indent=2, ensure_ascii=False)
    
    # 통계
    hair_count = sum(1 for item in ground_truth if item['is_hair_related'])
    
    print("\n" + "="*70)
    print("✅ 초기 Ground Truth 생성 완료!")
    print("="*70)
    print(f"📁 저장 위치: {output_path}")
    print(f"📊 통계:")
    print(f"  - 총: {len(ground_truth)}개")
    print(f"  - 헤어 관련: {hair_count}개 ({hair_count/len(ground_truth):.1%})")
    print(f"  - 비관련: {len(ground_truth) - hair_count}개")
    print("\n💡 다음 단계:")
    print(f"  python expand_ground_truth.py --stats")
    print(f"  python expand_ground_truth.py --optimize")
    print("="*70)


if __name__ == "__main__":
    import os
    
    # data 디렉토리 생성
    os.makedirs('data', exist_ok=True)
    
    # 기존 파일 확인
    if os.path.exists('data/ground_truth.json'):
        response = input("\n⚠️ data/ground_truth.json이 이미 존재합니다. 덮어쓸까요? (y/n): ")
        if response.lower() != 'y':
            print("취소됨.")
            exit(0)
    
    # 생성
    create_initial_ground_truth()
