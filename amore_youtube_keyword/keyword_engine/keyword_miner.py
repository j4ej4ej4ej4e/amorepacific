"""
키워드 채굴 모듈
수집된 메타데이터에서 N-gram 키워드를 추출합니다.
konlpy(Okt)를 사용하여 형태소 분석을 수행합니다.
"""
from typing import List, Dict, Set, Tuple, Optional
from collections import Counter
from dataclasses import dataclass
import re
from pathlib import Path

# konlpy 임포트 (설치 필요)
try:
    from konlpy.tag import Okt
    KONLPY_AVAILABLE = True
except ImportError:
    KONLPY_AVAILABLE = False
    print("[경고] konlpy가 설치되지 않았습니다. pip install konlpy 실행 필요.")

# Kiwi 형태소 분석기 (신조어에 강함)
try:
    from kiwipiepy import Kiwi
    KIWIPIE_AVAILABLE = True
except ImportError:
    KIWIPIE_AVAILABLE = False
    print("[경고] kiwipiepy가 설치되지 않았습니다. pip install kiwipiepy 실행 필요.")

# soynlp (신조어 후보 발굴용, 선택)
try:
    from soynlp.noun import LRNounExtractor_v2
    SOYNLP_AVAILABLE = True
except ImportError:
    SOYNLP_AVAILABLE = False

# 임베딩 기반 헤어 관련성 체커 (선택적)
try:
    from .hair_embedder import HairRelevanceChecker, get_hair_checker
    EMBEDDER_AVAILABLE = True
except ImportError:
    EMBEDDER_AVAILABLE = False


# 헤어 관련 핵심 키워드 (관련성 필터링용)
HAIR_DOMAIN_KEYWORDS = {
    # 기본 헤어 관련
    "헤어", "머리", "머리카락", "두피", "모발", "머릿결",
    # 스타일
    "컷", "펌", "염색", "탈색", "스타일링", "드라이", "세팅",
    "레이어드", "레이어", "볼륨", "웨이브", "컬",
    # 시술명
    "허쉬컷", "태슬컷", "히메컷", "울프컷", "보브컷",
    "아이비리그", "가일컷", "리프컷", "투블럭", "댄디컷",
    "다운펌", "애즈펌", "빌드펌", "히피펌", "볼륨펌",
    "가르마펌", "쉐도우펌", "매직", "셋팅펌",
    # 제품
    "샴푸", "트리트먼트", "린스", "에센스", "오일", "왁스", "젤",
    "스프레이", "무스", "세럼", "앰플", "팩",
    # 도구
    "고데기", "드라이기", "헤어롤", "빗", "브러쉬",
    # 상태/문제
    "탈모", "손상", "푸석", "건조", "지성", "민감", "각질",
}

# 불용어 (제외할 단어들)
STOPWORDS = {
    # 일반 불용어
    "있다", "하다", "되다", "이다", "않다", "없다", "같다",
    "그리고", "그러나", "하지만", "또한", "그래서", "때문",
    "위해", "통해", "대해", "관해", "따라", "의해",
    # 대명사
    "저", "나", "우리", "너", "당신", "그", "그녀", "이것", "저것",
    # 숫자/시간
    "오늘", "내일", "어제", "지금", "아까", "나중",
    # 유튜브 관련 불용어
    "구독", "좋아요", "알림", "댓글", "영상", "채널", "링크",
    "협찬", "광고", "제공", "문의", "연락", "클릭",
    # 일반 형용사/부사
    "정말", "진짜", "너무", "매우", "완전", "엄청", "최고",
    "좋은", "나쁜", "예쁜", "멋진",
}


@dataclass
class ExtractedKeyword:
    """추출된 키워드"""
    keyword: str
    frequency: int
    is_hair_related: bool
    source_count: int  # 몇 개의 소스에서 발견되었는지


class KeywordMiner:
    """
    메타데이터 기반 키워드 채굴기
    
    konlpy(Okt)를 사용하여 형태소 분석 후 N-gram 키워드를 추출합니다.
    임베딩 기반 헤어 관련성 판단을 지원합니다.
    """
    
    def __init__(self, 
                 n_range: Tuple[int, int] = (2, 4),
                 min_frequency: int = 2,
                 hair_keywords: Set[str] = None,
                 stopwords: Set[str] = None,
                 use_embedding: bool = True,
                 embedding_threshold: float = 0.35,
                 use_kiwi: bool = True,
                 user_dict_path: Optional[str] = None,
                 additional_user_words: Optional[List[str]] = None,
                 use_soynlp_candidates: bool = False,
                 soynlp_min_score: float = 0.3,
                 soynlp_min_freq: int = 2):
        """
        Args:
            n_range: N-gram 범위 (최소, 최대)
            min_frequency: 최소 빈도수
            hair_keywords: 헤어 관련 키워드 셋 (폴백용)
            stopwords: 불용어 셋
            use_embedding: 임베딩 기반 판단 사용 여부 (기본 True)
            embedding_threshold: 임베딩 유사도 임계값
            use_kiwi: Kiwi 형태소 분석 사용 여부 (기본 True, 실패 시 Okt 폴백)
            user_dict_path: Kiwi 사용자 사전 파일 경로 (단어별 한 줄)
            additional_user_words: 코드에서 바로 넣을 사용자 단어 리스트
            use_soynlp_candidates: soynlp로 신조어 후보를 추가할지 여부
            soynlp_min_score: soynlp 후보 최소 점수
            soynlp_min_freq: soynlp 후보 최소 빈도
        """
        self.n_range = n_range
        self.min_frequency = min_frequency
        self.hair_keywords = hair_keywords or HAIR_DOMAIN_KEYWORDS
        self.stopwords = stopwords or STOPWORDS
        self.use_embedding = use_embedding
        self.embedding_threshold = embedding_threshold
        self.use_kiwi = use_kiwi and KIWIPIE_AVAILABLE
        self.user_dict_path = user_dict_path
        self.user_words = set(additional_user_words or [])
        self.use_soynlp_candidates = use_soynlp_candidates and SOYNLP_AVAILABLE
        self.soynlp_min_score = soynlp_min_score
        self.soynlp_min_freq = soynlp_min_freq
        
        # 형태소 분석기 초기화 (Kiwi 우선, 실패 시 Okt)
        self.kiwi = None
        self.okt = None
        if self.use_kiwi:
            try:
                self.kiwi = Kiwi()
                self._load_user_dict(self.user_dict_path)
                for word in self.user_words:
                    # 명사 태그로 추가 (신조어/도메인어)
                    self.kiwi.add_user_word(word, tag='NNG')
                if self.user_words:
                    print(f"[KeywordMiner] ✅ Kiwi 사용자 사전 등록: {len(self.user_words)}개")
            except Exception as e:
                print(f"[KeywordMiner] ⚠️ Kiwi 초기화 실패, Okt로 폴백: {e}")
                self.kiwi = None
                self.use_kiwi = False
        
        if self.kiwi is None and KONLPY_AVAILABLE:
            self.okt = Okt()
        elif self.kiwi is None and not KONLPY_AVAILABLE:
            print("[KeywordMiner] ⚠️ 형태소 분석기를 찾을 수 없습니다. raw 패턴만 사용합니다.")

        if self.use_soynlp_candidates and not SOYNLP_AVAILABLE:
            print("[KeywordMiner] ⚠️ soynlp가 없어 신조어 후보 추가를 비활성화합니다.")
            self.use_soynlp_candidates = False
        
        # 임베딩 체커 초기화
        self.hair_checker = None
        if use_embedding and EMBEDDER_AVAILABLE:
            try:
                self.hair_checker = get_hair_checker()
                self.hair_checker.threshold = embedding_threshold
                print(f"[KeywordMiner] ✅ 임베딩 기반 헤어 판단 활성화 (threshold={embedding_threshold})")
            except Exception as e:
                print(f"[KeywordMiner] ⚠️ 임베딩 로드 실패, 키워드 매칭으로 대체: {e}")
                self.use_embedding = False

    def _load_user_dict(self, path: Optional[str]):
        """Kiwi 사용자 사전 파일 로드 (한 줄 한 단어)"""
        if not path:
            return
        p = Path(path)
        if not p.exists():
            print(f"[KeywordMiner] ⚠️ 사용자 사전 파일을 찾을 수 없습니다: {path}")
            return
        try:
            words = [line.strip() for line in p.read_text(encoding='utf-8').splitlines() if line.strip()]
            for word in words:
                self.user_words.add(word)
            if self.kiwi:
                for word in words:
                    self.kiwi.add_user_word(word, tag='NNG')
            print(f"[KeywordMiner] ✅ 사용자 사전 로드: {len(words)}개")
        except Exception as e:
            print(f"[KeywordMiner] ⚠️ 사용자 사전 로드 실패 ({path}): {e}")
    
    def extract_from_texts(self, texts: List[str]) -> Dict[str, ExtractedKeyword]:
        """
        텍스트 리스트에서 키워드 추출
        
        하이브리드 방식:
        1. 형태소 분석 기반 N-gram
        2. 원본 텍스트 패턴 매칭 (신조어/복합어 보존)
        
        Args:
            texts: 분석할 텍스트 리스트
            
        Returns:
            {키워드: ExtractedKeyword} 딕셔너리
        """
        all_ngrams = Counter()
        source_counts = Counter()  # 각 키워드가 몇 개 소스에서 나왔는지
        
        # tqdm 임포트 (선택적)
        try:
            from tqdm import tqdm
            texts_iter = tqdm(texts, desc="키워드 마이닝", unit="텍스트")
        except ImportError:
            texts_iter = texts
        
        for text in texts_iter:
            if not text:
                continue
            
            # 1. 원본 텍스트에서 직접 패턴 추출 (신조어 보존)
            raw_patterns = self._extract_raw_patterns(text)
            for pattern in raw_patterns:
                all_ngrams[pattern] += 1
            for pattern in set(raw_patterns):
                source_counts[pattern] += 1
            
            # 2. 형태소 분석 기반 N-gram (기존 방식)
            cleaned_text = self._preprocess(text)
            tokens = self._tokenize(cleaned_text)
            text_ngrams = self._generate_ngrams(tokens)
            
            for ngram in text_ngrams:
                all_ngrams[ngram] += 1
            for ngram in set(text_ngrams):
                source_counts[ngram] += 1
        
        # 4. 결과 구성 (헤어 관련성 판단 - SBERT 연산 포함, 시간 소요)
        results = {}
        
        # tqdm으로 진행도 표시
        try:
            from tqdm import tqdm
            ngrams_iter = tqdm(all_ngrams.items(), desc="헤어 관련성 판단 (SBERT)", unit="키워드")
        except ImportError:
            ngrams_iter = all_ngrams.items()
        
        for ngram, freq in ngrams_iter:
            if freq < self.min_frequency:
                continue
            
            is_hair = self._is_hair_related(ngram)  # ← SBERT 연산, 느림!
            
            results[ngram] = ExtractedKeyword(
                keyword=ngram,
                frequency=freq,
                is_hair_related=is_hair,
                source_count=source_counts[ngram]
            )
        
        return results
    
    def _extract_soynlp_candidates(self, texts: List[str]) -> List[str]:
        """soynlp로 신조어/도메인어 후보 추출 (선택적)"""
        if not SOYNLP_AVAILABLE:
            return []
        
        try:
            extractor = LRNounExtractor_v2(verbose=False)
            scores = extractor.train_extract(texts)
        except Exception as e:
            print(f"[KeywordMiner] ⚠️ soynlp 후보 추출 실패: {e}")
            return []
        
        candidates = set()
        for word, score_obj in scores.items():
            try:
                score_val = float(score_obj)
            except Exception:
                score_val = float(getattr(score_obj, 'score', getattr(score_obj, 'confidence', 0.0)) or 0.0)
            freq = getattr(score_obj, 'frequency', getattr(score_obj, 'freq', 0))
            
            if len(word) < 2:
                continue
            if freq and freq < self.soynlp_min_freq:
                continue
            if score_val < self.soynlp_min_score:
                continue
            candidates.add(word)
        
        if candidates:
            print(f"[KeywordMiner] ✅ soynlp 후보 {len(candidates)}개 선반영")
        return list(candidates)
    
    def _extract_raw_patterns(self, text: str) -> List[str]:
        """
        원본 텍스트에서 직접 한글 복합어 패턴 추출
        
        신조어나 복합어 보존:
        - "아이롱펌" → ["아이롱펌"] (원본 보존)
        - "볼륨펌" → ["볼륨펌"]
        - "허쉬컷" → ["허쉬컷"]
        
        Returns:
            복합어 패턴 리스트
        """
        patterns = []
        
        # 전처리
        cleaned = self._preprocess(text)
        
        # 한글 복합어 패턴 (2~8글자)
        # 패턴: 한글만, 또는 한글+영문 조합
        import re
        
        # 패턴 1: 순수 한글 단어 (2~8자)
        korean_words = re.findall(r'[가-힣]{2,8}', cleaned)
        patterns.extend(korean_words)
        
        # 패턴 2: 한글+영문 조합 (예: "S컬펌")
        mixed_words = re.findall(r'[가-힣a-zA-Z]{2,10}', cleaned)
        patterns.extend(mixed_words)
        
        # 중복 제거 및 불용어 필터링
        filtered = []
        seen = set()
        for pattern in patterns:
            # 불용어 제외
            if pattern in self.stopwords:
                continue
            # 너무 짧은 것 제외 (1글자)
            if len(pattern) < 2:
                continue
            if pattern in seen:
                continue
            filtered.append(pattern)
            seen.add(pattern)
        
        # 사용자 사전에 등록된 도메인어가 원문에 포함되면 우선 추가
        for word in self.user_words:
            if word in cleaned and word not in seen:
                filtered.append(word)
                seen.add(word)
        
        return filtered

    
    def extract_hair_keywords(self, texts: List[str], 
                               top_k: int = 50) -> List[ExtractedKeyword]:
        """
        헤어 관련 키워드만 추출 (상위 K개)
        
        Args:
            texts: 분석할 텍스트 리스트
            top_k: 반환할 최대 키워드 수
            
        Returns:
            빈도순 정렬된 ExtractedKeyword 리스트
        """
        all_keywords = self.extract_from_texts(texts)
        
        # 헤어 관련 키워드만 필터링
        hair_keywords = [
            kw for kw in all_keywords.values()
            if kw.is_hair_related
        ]
        
        # 빈도 + 소스 수 기반 정렬
        hair_keywords.sort(
            key=lambda x: (x.frequency * 0.7 + x.source_count * 0.3),
            reverse=True
        )
        
        return hair_keywords[:top_k]
    
    def _preprocess(self, text: str) -> str:
        """텍스트 전처리"""
        # URL 제거
        text = re.sub(r'https?://\S+', '', text)
        # 이메일 제거
        text = re.sub(r'\S+@\S+', '', text)
        # 특수문자 정리 (한글, 영문, 숫자, 공백만 유지)
        text = re.sub(r'[^\w\s가-힣a-zA-Z0-9]', ' ', text)
        # 연속 공백 제거
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _tokenize(self, text: str) -> List[str]:
        """
        형태소 분석 및 토큰화
        명사, 형용사, 동사 어근 추출
        """
        if self.kiwi:
            tokens = self._tokenize_with_kiwi(text)
            if tokens:
                return tokens
        
        if self.okt:
            return self._tokenize_with_okt(text)
        
        # 최후 폴백: 단순 공백 토크나이즈 + 필터
        return [
            token for token in text.split()
            if len(token) >= 2 and token not in self.stopwords
        ]

    def _tokenize_with_okt(self, text: str) -> List[str]:
        """Okt 기반 토크나이즈 (폴백)"""
        tokens = []
        pos_tags = self.okt.pos(text, norm=True, stem=True)
        
        for word, pos in pos_tags:
            if word in self.stopwords:
                continue
            if len(word) < 2:
                continue
            if pos in ['Noun', 'Adjective', 'Verb', 'Alpha']:
                tokens.append(word)
        return tokens

    def _tokenize_with_kiwi(self, text: str) -> List[str]:
        """Kiwi 기반 토크나이즈 (신조어/사용자 사전 우선)"""
        tokens = []
        try:
            for token in self.kiwi.tokenize(text, normalize_coda=True):
                word = token.form
                if word in self.stopwords:
                    continue
                if len(word) < 2:
                    continue
                if token.tag in ('NNG', 'NNP', 'VA', 'VV', 'XR', 'SL'):
                    tokens.append(word)
        except Exception as e:
            print(f"[KeywordMiner] ⚠️ Kiwi 토크나이즈 실패, Okt로 폴백: {e}")
            if self.okt:
                return self._tokenize_with_okt(text)
        return tokens
    
    def _generate_ngrams(self, tokens: List[str]) -> List[str]:
        """N-gram 생성"""
        ngrams = []
        
        for n in range(self.n_range[0], self.n_range[1] + 1):
            for i in range(len(tokens) - n + 1):
                ngram = ' '.join(tokens[i:i+n])
                ngrams.append(ngram)
        
        # 단일 토큰도 포함 (헤어 관련 핵심 단어)
        for token in tokens:
            if token in self.hair_keywords:
                ngrams.append(token)
        
        return ngrams
    
    def _is_hair_related(self, text: str) -> bool:
        """
        헤어 관련 키워드인지 확인
        
        우선순위:
        1. 임베딩 기반 판단 (use_embedding=True이고 모델 로드됨)
        2. 키워드 매칭 (폴백)
        """
        # 1. 임베딩 기반 판단 시도
        if self.use_embedding and self.hair_checker:
            try:
                return self.hair_checker.is_hair_related(text)
            except Exception:
                pass  # 실패 시 키워드 매칭으로 폴백
        
        # 2. 키워드 매칭 (폴백)
        text_lower = text.lower()
        for keyword in self.hair_keywords:
            if keyword.lower() in text_lower:
                return True
        
        return False
    
    def get_hair_similarity(self, text: str) -> float:
        """
        텍스트의 헤어 관련 유사도 반환 (0~1)
        임베딩 사용 시 실제 유사도, 아니면 0 또는 1
        """
        if self.use_embedding and self.hair_checker:
            return self.hair_checker.get_similarity(text)
        return 1.0 if self._is_hair_related(text) else 0.0
    
    def filter_by_relevance(self, keywords: List[ExtractedKeyword],
                            min_relevance: float = 0.3) -> List[ExtractedKeyword]:
        """
        관련성 점수로 필터링
        
        헤어 관련 키워드 포함 비율이 높은 것만 선택
        """
        if not keywords:
            return []
        
        total = len(keywords)
        hair_count = sum(1 for kw in keywords if kw.is_hair_related)
        
        if hair_count / total < min_relevance:
            # 관련성이 낮으면 헤어 관련만 반환
            return [kw for kw in keywords if kw.is_hair_related]
        
        return keywords
    
    def deduplicate(self, keywords: List[ExtractedKeyword],
                    similarity_threshold: float = 0.8) -> List[ExtractedKeyword]:
        """
        유사 키워드 중복 제거
        
        - 부분 문자열 관계: 짧은 것 제거
        - 어순만 다른 경우: 빈도 높은 것 유지
        """
        if not keywords:
            return []
        
        # 빈도순 정렬
        sorted_kws = sorted(keywords, key=lambda x: x.frequency, reverse=True)
        
        result = []
        seen_texts = set()
        
        for kw in sorted_kws:
            # 이미 유사한 키워드가 있는지 확인
            is_duplicate = False
            
            for seen in seen_texts:
                # 부분 문자열 체크
                if kw.keyword in seen or seen in kw.keyword:
                    is_duplicate = True
                    break
                
                # 단어 집합 유사도 체크
                kw_words = set(kw.keyword.split())
                seen_words = set(seen.split())
                
                if kw_words and seen_words:
                    intersection = len(kw_words & seen_words)
                    union = len(kw_words | seen_words)
                    similarity = intersection / union
                    
                    if similarity >= similarity_threshold:
                        is_duplicate = True
                        break
            
            if not is_duplicate:
                result.append(kw)
                seen_texts.add(kw.keyword)
        
        return result


if __name__ == "__main__":
    # 테스트
    miner = KeywordMiner()
    
    test_texts = [
        "지성두피를 위한 샴푸 추천합니다. 두피 케어가 중요해요.",
        "허쉬컷 스타일링 방법을 알려드릴게요. 레이어드컷과 비슷해요.",
        "손상모 복구를 위한 트리트먼트 순위입니다.",
        "탈모 예방에 좋은 두피 케어 루틴을 소개합니다.",
        "염색 후 머릿결 관리법, 트리트먼트 추천까지!",
    ]
    
    print("=== 키워드 채굴 테스트 ===")
    keywords = miner.extract_hair_keywords(test_texts, top_k=20)
    
    print(f"\n추출된 헤어 관련 키워드 ({len(keywords)}개):")
    for kw in keywords:
        print(f"  - {kw.keyword} (빈도: {kw.frequency}, 소스: {kw.source_count})")
