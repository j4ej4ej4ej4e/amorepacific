"""
임베딩 기반 헤어 관련성 판단 모듈
사전학습된 한국어 Sentence-BERT 모델을 사용하여 
키워드가 헤어/미용 도메인과 의미적으로 유사한지 판단합니다.
"""
import numpy as np
from typing import List, Optional, Tuple

# Sentence Transformers 임포트 (설치 필요)
try:
    from sentence_transformers import SentenceTransformer
    SBERT_AVAILABLE = True
except ImportError:
    SBERT_AVAILABLE = False
    print("[경고] sentence-transformers가 설치되지 않았습니다.")
    print("       pip install sentence-transformers 실행 필요.")


class HairRelevanceChecker:
    """
    임베딩 기반 헤어 관련성 판단기
    
    사전학습된 한국어 SBERT 모델을 사용하여
    주어진 텍스트가 헤어/미용 도메인과 의미적으로 유사한지 판단합니다.
    
    장점:
    - 미리 정의하지 않은 키워드도 판단 가능
    - 문맥을 고려한 의미적 유사도 비교
    - 신조어, 트렌드 용어에도 대응
    """
    
    # 헤어/미용 개념을 정의하는 대표 문장들
    HAIR_CONCEPT_TEXTS = [
        # 기본 헤어 개념
        "헤어 미용 스타일링 머리카락",
        "펌 염색 커트 드라이 스타일",
        "샴푸 트리트먼트 두피케어 헤어케어",
        
        # 미용실/전문가
        "미용실 헤어샵 살롱 디자이너 원장",
        
        # 시술
        "펌 염색 탈색 클리닉 매직 셋팅",
        "레이어드컷 허쉬컷 볼륨펌 다운펌",
        
        # 제품
        "헤어오일 에센스 왁스 무스 세럼",
        "고데기 드라이기 헤어롤",
        
        # 상태/문제
        "손상모 탈모 두피 건조 지성 민감",
        "머릿결 볼륨 윤기 찰랑",
    ]
    
    def __init__(self, 
                 model_name: str = 'jhgan/ko-sbert-nli',
                 threshold: float = 0.35,
                 use_fallback: bool = True):
        """
        Args:
            model_name: 사용할 SBERT 모델 (기본: 한국어 SBERT)
            threshold: 헤어 관련 판단 임계값 (0~1)
            use_fallback: 모델 로드 실패 시 키워드 매칭으로 대체
        """
        self.threshold = threshold
        self.use_fallback = use_fallback
        self.model = None
        self.hair_embedding = None
        
        # 폴백용 키워드 셋
        self._fallback_keywords = {
            "헤어", "머리", "두피", "모발", "펌", "염색", "커트", "컷",
            "스타일링", "드라이", "샴푸", "트리트먼트", "린스", "에센스",
            "미용", "미용실", "살롱", "탈모", "손상", "볼륨",
        }
        
        if SBERT_AVAILABLE:
            try:
                print(f"[임베딩] 모델 로딩 중: {model_name}")
                self.model = SentenceTransformer(model_name)
                self._init_hair_embedding()
                print(f"[임베딩] ✅ 모델 로드 완료!")
            except Exception as e:
                print(f"[임베딩] ⚠️ 모델 로드 실패: {e}")
                if not use_fallback:
                    raise
    
    def _init_hair_embedding(self):
        """헤어 개념의 대표 임베딩 벡터 생성"""
        if self.model is None:
            return
        
        # 여러 헤어 관련 문장의 임베딩을 평균
        embeddings = self.model.encode(self.HAIR_CONCEPT_TEXTS)
        self.hair_embedding = np.mean(embeddings, axis=0)
        
        # 정규화 (코사인 유사도 계산 최적화)
        self.hair_embedding = self.hair_embedding / np.linalg.norm(self.hair_embedding)
    
    def get_similarity(self, text: str) -> float:
        """
        텍스트와 헤어 개념 간의 코사인 유사도 계산
        
        Args:
            text: 판단할 텍스트
            
        Returns:
            유사도 (0~1, 높을수록 헤어 관련)
        """
        if self.model is None or self.hair_embedding is None:
            return self._fallback_similarity(text)
        
        try:
            # 텍스트 임베딩
            text_embedding = self.model.encode(text)
            
            # 정규화
            text_embedding = text_embedding / np.linalg.norm(text_embedding)
            
            # 코사인 유사도 (정규화된 벡터의 내적)
            similarity = float(np.dot(text_embedding, self.hair_embedding))
            
            return similarity
            
        except Exception as e:
            print(f"[임베딩] 유사도 계산 실패: {e}")
            return self._fallback_similarity(text)
    
    def _fallback_similarity(self, text: str) -> float:
        """폴백: 키워드 매칭 기반 유사도"""
        text_lower = text.lower()
        matched = sum(1 for kw in self._fallback_keywords if kw in text_lower)
        # 매칭된 키워드 수를 0~1로 정규화
        return min(1.0, matched * 0.3)
    
    def is_hair_related(self, text: str, threshold: float = None) -> bool:
        """
        텍스트가 헤어 관련인지 판단
        
        Args:
            text: 판단할 텍스트
            threshold: 커스텀 임계값 (None이면 기본값 사용)
            
        Returns:
            헤어 관련 여부
        """
        threshold = threshold or self.threshold
        similarity = self.get_similarity(text)
        return similarity >= threshold
    
    def classify_batch(self, texts: List[str]) -> List[Tuple[str, float, bool]]:
        """
        여러 텍스트를 배치로 분류
        
        Args:
            texts: 텍스트 리스트
            
        Returns:
            [(텍스트, 유사도, 헤어관련여부), ...] 리스트
        """
        results = []
        
        for text in texts:
            similarity = self.get_similarity(text)
            is_related = similarity >= self.threshold
            results.append((text, similarity, is_related))
        
        return results
    
    def filter_hair_related(self, texts: List[str]) -> List[str]:
        """
        헤어 관련 텍스트만 필터링
        
        Args:
            texts: 텍스트 리스트
            
        Returns:
            헤어 관련 텍스트만 포함된 리스트
        """
        return [text for text in texts if self.is_hair_related(text)]
    
    def rank_by_relevance(self, texts: List[str]) -> List[Tuple[str, float]]:
        """
        텍스트를 헤어 관련성 순으로 정렬
        
        Args:
            texts: 텍스트 리스트
            
        Returns:
            [(텍스트, 유사도), ...] 유사도 내림차순 정렬
        """
        scored = [(text, self.get_similarity(text)) for text in texts]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored
    
    def adjust_threshold(self, new_threshold: float):
        """임계값 조정"""
        self.threshold = new_threshold
        print(f"[임베딩] 임계값 변경: {new_threshold}")


# 싱글톤 인스턴스 (전역에서 재사용)
_global_checker: Optional[HairRelevanceChecker] = None


def get_hair_checker(force_reload: bool = False) -> HairRelevanceChecker:
    """
    전역 HairRelevanceChecker 인스턴스 반환
    
    모델 로딩이 오래 걸리므로 싱글톤으로 재사용
    """
    global _global_checker
    
    if _global_checker is None or force_reload:
        _global_checker = HairRelevanceChecker()
    
    return _global_checker


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 임베딩 기반 헤어 관련성 테스트")
    print("=" * 60)
    
    checker = HairRelevanceChecker()
    
    # 테스트 키워드들
    test_keywords = [
        # 헤어 관련 (높은 유사도 예상)
        "허쉬컷 스타일링",
        "두피 케어 루틴",
        "손상모 트리트먼트",
        "염색 후 관리",
        "탈모 예방 샴푸",
        
        # 애매한 것들
        "볼륨감 살리기",
        "윤기나는 방법",
        "건조함 해결",
        
        # 헤어 무관 (낮은 유사도 예상)
        "맛집 추천",
        "게임 리뷰",
        "주식 투자",
        "코딩 강의",
    ]
    
    print("\n📊 유사도 결과:")
    print("-" * 50)
    
    for keyword in test_keywords:
        similarity = checker.get_similarity(keyword)
        is_related = checker.is_hair_related(keyword)
        
        status = "✅ 헤어" if is_related else "❌ 비관련"
        bar = "█" * int(similarity * 20)
        
        print(f"{status} [{similarity:.3f}] {bar:20} {keyword}")
    
    print("\n" + "=" * 60)
