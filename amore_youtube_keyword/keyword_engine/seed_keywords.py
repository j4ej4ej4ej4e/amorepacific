"""
Seed 키워드 생성 모듈
헤어 도메인에 특화된 초기 검색 키워드를 템플릿 기반으로 생성합니다.
"""
from typing import List, Dict, Set
from itertools import product
import random


# 헤어 도메인별 시드 키워드 템플릿
SEED_TEMPLATES = {
    # 헤어 케어 관련
    "hair_care": [
        "{hair_type} 샴푸 추천",
        "{hair_type} 트리트먼트",
        "{hair_type} 케어 방법",
        "손상모 복구 {method}",
        "{hair_type} 관리 {method}",
        "두피 케어 {method}",
        "탈모 예방 {method}",
    ],
    # 헤어 스타일 관련
    "hair_style": [
        "{style_name} 스타일링",
        "{style_name} 하는법",
        "{style_name} 드라이",
        "셀프 {treatment}",
        "{treatment} 후기",
        "홈케어 {treatment}",
        "{gender} {style_name}",
    ],
    # 헤어 제품 관련
    "hair_product": [
        "{brand} 헤어 후기",
        "{product} 비교",
        "{product} 추천",
        "헤어오일 추천",
        "헤어에센스 추천",
        "{product} 순위",
        "인생 {product}",
    ],
    # 헤어 트렌드 관련
    "hair_trend": [
        "2024 {gender} 헤어 트렌드",
        "요즘 유행하는 {style_name}",
        "{season} {gender} 헤어",
        "연예인 {style_name}",
        "{style_name} 변천사",
    ],
}

# 템플릿 변수 치환용 사전 (헤어 도메인 특화)
TEMPLATE_VARS = {
    "hair_type": [
        "지성두피", "건성두피", "민감성두피", "탈모", "손상모",
        "염색모", "탈색모", "곱슬머리", "가는머리", "굵은머리",
        "힘없는머리", "푸석푸석한머리"
    ],
    "style_name": [
        # 여성 스타일
        "허쉬컷", "레이어드컷", "태슬컷", "히메컷", "울프컷",
        "보브컷", "단발", "중단발", "장발", "레이어",
        # 남성 스타일
        "아이비리그컷", "가일컷", "리프컷", "투블럭", "댄디컷",
        "포마드", "쉐도우펌", "가르마펌", "다운펌", "애즈펌"
    ],
    "treatment": [
        "염색", "펌", "탈색", "매직", "클리닉",
        "셋팅", "볼륨펌", "히피펌", "빌드펌", "S컬펌"
    ],
    "method": [
        "루틴", "꿀팁", "방법", "비법", "노하우", "관리법"
    ],
    "brand": [
        "다이슨", "아모스", "모레모", "미쟝센", "려",
        "케라시스", "닥터포헤어", "TS샴푸", "헤드앤숄더", "팬틴",
        "아베다", "로레알", "케라스타즈"
    ],
    "product": [
        "샴푸", "트리트먼트", "린스", "헤어오일", "에센스",
        "고데기", "드라이기", "헤어롤", "왁스", "젤",
        "헤어스프레이", "무스", "세럼"
    ],
    "gender": [
        "여자", "남자", "여성", "남성"
    ],
    "season": [
        "봄", "여름", "가을", "겨울"
    ],
}

# 헤어 관련 핵심 키워드 (필터링용)
HAIR_CORE_KEYWORDS = {
    # 기본 헤어 관련
    "헤어", "머리", "머리카락", "두피", "모발",
    # 스타일
    "컷", "펌", "염색", "탈색", "스타일링", "드라이",
    # 제품
    "샴푸", "트리트먼트", "린스", "에센스", "오일",
    # 전문용어
    "미용", "미용실", "헤어샵", "살롱", "디자이너",
    # 영문
    "hair", "perm", "cut", "dye", "shampoo",
}


class SeedKeywordGenerator:
    """
    템플릿 기반 Seed 키워드 생성기
    
    헤어 도메인에 특화된 초기 검색 키워드를 생성합니다.
    """
    
    def __init__(self, 
                 templates: Dict[str, List[str]] = None,
                 variables: Dict[str, List[str]] = None):
        """
        Args:
            templates: 카테고리별 키워드 템플릿
            variables: 템플릿 변수 치환 사전
        """
        self.templates = templates or SEED_TEMPLATES
        self.variables = variables or TEMPLATE_VARS
        
    def generate_all(self, max_per_category: int = None) -> List[str]:
        """
        모든 카테고리에서 키워드 생성
        
        Args:
            max_per_category: 카테고리당 최대 키워드 수 (None이면 전체)
            
        Returns:
            생성된 키워드 리스트 (중복 제거됨)
        """
        all_keywords = set()
        
        for category, templates in self.templates.items():
            category_keywords = self._generate_from_templates(templates)
            
            if max_per_category:
                category_keywords = list(category_keywords)[:max_per_category]
                
            all_keywords.update(category_keywords)
            
        return list(all_keywords)
    
    def generate_by_category(self, category: str, limit: int = None) -> List[str]:
        """
        특정 카테고리에서 키워드 생성
        
        Args:
            category: 카테고리명 (hair_care, hair_style, hair_product, hair_trend)
            limit: 최대 키워드 수
            
        Returns:
            생성된 키워드 리스트
        """
        if category not in self.templates:
            raise ValueError(f"Unknown category: {category}. Available: {list(self.templates.keys())}")
            
        keywords = list(self._generate_from_templates(self.templates[category]))
        
        if limit:
            keywords = keywords[:limit]
            
        return keywords
    
    def generate_random(self, count: int = 50) -> List[str]:
        """
        랜덤하게 키워드 선택
        
        Args:
            count: 선택할 키워드 수
            
        Returns:
            랜덤 선택된 키워드 리스트
        """
        all_keywords = self.generate_all()
        random.shuffle(all_keywords)
        return all_keywords[:count]
    
    def _generate_from_templates(self, templates: List[str]) -> Set[str]:
        """
        템플릿 리스트에서 변수를 치환하여 키워드 생성
        """
        keywords = set()
        
        for template in templates:
            # 템플릿에 포함된 변수 찾기
            var_names = self._extract_variables(template)
            
            if not var_names:
                # 변수가 없으면 템플릿 그대로 사용
                keywords.add(template)
                continue
                
            # 변수 값들의 조합 생성
            var_values = []
            for var_name in var_names:
                if var_name in self.variables:
                    var_values.append(self.variables[var_name])
                else:
                    # 알 수 없는 변수는 빈 문자열로
                    var_values.append([''])
            
            # 모든 조합에 대해 키워드 생성
            for combination in product(*var_values):
                keyword = template
                for var_name, value in zip(var_names, combination):
                    keyword = keyword.replace(f"{{{var_name}}}", value)
                keywords.add(keyword)
                
        return keywords
    
    def _extract_variables(self, template: str) -> List[str]:
        """
        템플릿에서 변수명 추출 (예: {hair_type} -> hair_type)
        """
        import re
        return re.findall(r'\{(\w+)\}', template)
    
    def add_custom_keywords(self, keywords: List[str]) -> List[str]:
        """
        직접 지정한 키워드를 추가
        
        Args:
            keywords: 추가할 키워드 리스트
            
        Returns:
            기존 + 추가 키워드 리스트
        """
        all_keywords = set(self.generate_all())
        all_keywords.update(keywords)
        return list(all_keywords)


# 직접 사용할 수 있는 기본 Seed 키워드 (50개)
DEFAULT_SEED_KEYWORDS = [
    # 헤어 케어
    "지성두피 샴푸 추천", "건성두피 트리트먼트", "손상모 복구 루틴",
    "탈모 예방 방법", "두피 케어 꿀팁", "염색모 관리법",
    
    # 여성 헤어 스타일
    "허쉬컷 스타일링", "레이어드컷 드라이", "태슬컷 관리법",
    "울프컷 하는법", "단발 스타일링", "히메컷 드라이",
    
    # 남성 헤어 스타일
    "아이비리그컷 스타일링", "가일컷 하는법", "리프컷 드라이",
    "투블럭 다운펌", "가르마펌 스타일링", "댄디컷 드라이",
    
    # 시술
    "셀프 염색 후기", "홈케어 펌", "셀프 탈색 방법",
    "볼륨펌 후기", "애즈펌 스타일링", "매직 관리법",
    
    # 제품 리뷰
    "인생 샴푸 추천", "트리트먼트 순위 비교", "헤어오일 추천",
    "다이슨 에어랩 후기", "고데기 추천", "드라이기 비교",
    
    # 프로 팁
    "상한 머리 복구 꿀팁", "옆머리 누르기 비법", "앞머리 스타일링",
    "볼륨 살리기 방법", "곱슬머리 관리법", "가는머리 볼륨",
    
    # 트렌드
    "2025 여자 헤어 트렌드", "2025 남자 헤어 트렌드",
    "요즘 유행하는 펌", "연예인 헤어스타일",
]


if __name__ == "__main__":
    # 테스트
    generator = SeedKeywordGenerator()
    
    print("=== 카테고리별 키워드 생성 ===")
    for category in SEED_TEMPLATES.keys():
        keywords = generator.generate_by_category(category, limit=5)
        print(f"\n[{category}] ({len(keywords)}개)")
        for kw in keywords[:5]:
            print(f"  - {kw}")
    
    print(f"\n=== 전체 키워드 수: {len(generator.generate_all())}개 ===")
    print(f"\n=== 랜덤 50개 ===")
    for kw in generator.generate_random(50)[:10]:
        print(f"  - {kw}")
