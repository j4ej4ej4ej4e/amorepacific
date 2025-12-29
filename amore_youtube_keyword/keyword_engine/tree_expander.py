"""
트리 확장 기반 키워드 발굴 모듈
BFS 방식으로 Seed 키워드에서 시작하여 관련 키워드를 확장해나갑니다.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple
from collections import deque
import json
import os
from datetime import datetime

from .seed_keywords import DEFAULT_SEED_KEYWORDS
from .youtube_searcher import YouTubeSearcher, VideoMeta
from .keyword_miner import KeywordMiner, ExtractedKeyword
from .query_scorer import QueryScorer, QueryScore


@dataclass
class RankedKeyword:
    """랭킹된 키워드"""
    keyword: str
    score: float
    depth: int  # 트리에서의 깊이 (0 = Seed)
    parent_keyword: Optional[str] = None  # 부모 키워드
    frequency: int = 1
    source_videos: int = 0
    
    def __hash__(self):
        return hash(self.keyword)
    
    def __eq__(self, other):
        if isinstance(other, RankedKeyword):
            return self.keyword == other.keyword
        return False


@dataclass
class KeywordTreeNode:
    """키워드 트리 노드"""
    keyword: str
    score: QueryScore
    depth: int
    children: List['KeywordTreeNode'] = field(default_factory=list)
    mined_keywords: List[ExtractedKeyword] = field(default_factory=list)
    videos: List[VideoMeta] = field(default_factory=list)


class KeywordTreeExpander:
    """
    트리 확장 기반 키워드 발굴
    
    Seed 키워드에서 시작하여 BFS 방식으로 관련 키워드를 확장합니다.
    각 레벨에서 상위 K개의 키워드만 선택하여 확장합니다.
    
    파이프라인:
    1. Seed 키워드 → 검색
    2. 검색 결과에서 키워드 채굴
    3. 채굴된 키워드 스코어링
    4. 상위 K개 선택 → 다음 레벨로 확장
    5. max_depth까지 반복
    """
    
    def __init__(self,
                 searcher: YouTubeSearcher = None,
                 miner: KeywordMiner = None,
                 scorer: QueryScorer = None,
                 max_depth: int = 3,
                 top_k_per_level: int = 10,
                 videos_per_search: int = 20,
                 detail_videos: int = 5,
                 quiet: bool = False):
        """
        Args:
            searcher: YouTube 검색기
            miner: 키워드 채굴기
            scorer: 쿼리 스코어러
            max_depth: 최대 확장 깊이 (기본 5)
            top_k_per_level: 레벨당 확장할 최대 키워드 수
            videos_per_search: 검색당 영상 수
            detail_videos: 상세 정보 수집할 영상 수
            quiet: 출력 억제 여부
        """
        self.searcher = searcher or YouTubeSearcher(quiet=quiet)
        self.miner = miner or KeywordMiner()
        self.scorer = scorer or QueryScorer()
        
        self.max_depth = max_depth
        self.top_k_per_level = top_k_per_level
        self.videos_per_search = videos_per_search
        self.detail_videos = detail_videos
        self.quiet = quiet
        
        # 상태
        self.tree_roots: List[KeywordTreeNode] = []
        self.all_keywords: Dict[str, RankedKeyword] = {}
        self.processed_queries: Set[str] = set()
        self.expansion_history: List[Dict] = []
    
    def expand(self, seed_keywords: List[str] = None) -> 'KeywordTreeExpander':
        """
        키워드 트리 확장 실행
        
        Args:
            seed_keywords: 시드 키워드 리스트 (None이면 기본값 사용)
            
        Returns:
            self (메서드 체이닝용)
        """
        if seed_keywords is None:
            seed_keywords = DEFAULT_SEED_KEYWORDS
        
        if not self.quiet:
            print("=" * 60)
            print("🌳 키워드 트리 확장 시작")
            print(f"  시드 키워드: {len(seed_keywords)}개")
            print(f"  최대 깊이: {self.max_depth}")
            print(f"  레벨당 확장: {self.top_k_per_level}개")
            print("=" * 60)
        
        # BFS 큐: (키워드, 깊이, 부모)
        queue = deque()
        for kw in seed_keywords:
            queue.append((kw, 0, None))
            self.all_keywords[kw] = RankedKeyword(
                keyword=kw, score=1.0, depth=0, parent_keyword=None
            )
        
        current_depth = 0
        level_keywords = []
        
        while queue:
            keyword, depth, parent = queue.popleft()
            
            # 깊이 변경 시 레벨 요약
            if depth > current_depth:
                self._log_level_summary(current_depth, level_keywords)
                current_depth = depth
                level_keywords = []
            
            # 최대 깊이 도달 시 중단
            if depth >= self.max_depth:
                continue
            
            # 이미 처리된 키워드 스킵
            if keyword in self.processed_queries:
                continue
            
            # 키워드 확장
            new_keywords = self._expand_keyword(keyword, depth)
            self.processed_queries.add(keyword)
            level_keywords.append(keyword)
            
            # 새 키워드를 큐에 추가
            for new_kw in new_keywords[:self.top_k_per_level]:
                if new_kw.keyword not in self.processed_queries:
                    queue.append((new_kw.keyword, depth + 1, keyword))
                    
                    # all_keywords 업데이트
                    if new_kw.keyword not in self.all_keywords:
                        self.all_keywords[new_kw.keyword] = new_kw
                    else:
                        # 더 높은 점수로 업데이트
                        existing = self.all_keywords[new_kw.keyword]
                        if new_kw.score > existing.score:
                            self.all_keywords[new_kw.keyword] = new_kw
        
        # 마지막 레벨 요약
        self._log_level_summary(current_depth, level_keywords)
        
        if not self.quiet:
            print("\n" + "=" * 60)
            print(f"✅ 확장 완료! 총 {len(self.all_keywords)}개 키워드 발굴")
            print("=" * 60)
        
        return self
    
    def _expand_keyword(self, keyword: str, depth: int) -> List[RankedKeyword]:
        """
        단일 키워드 확장
        
        1. YouTube 검색
        2. 메타데이터에서 키워드 채굴
        3. 스코어링
        4. 상위 키워드 반환
        """
        if not self.quiet:
            print(f"\n[깊이 {depth}] 🔍 '{keyword}' 확장 중...")
        
        # 1. YouTube 검색
        videos = self.searcher.search_with_details(
            keyword, 
            limit=self.videos_per_search,
            detail_limit=self.detail_videos
        )
        
        if not videos:
            if not self.quiet:
                print(f"  ⚠️ 검색 결과 없음")
            return []
        
        if not self.quiet:
            print(f"  📺 {len(videos)}개 영상 수집")
        
        # 2. 쿼리 스코어 계산
        query_score = self.scorer.score(keyword, videos)
        
        if not self.quiet:
            print(f"  📊 쿼리 점수: {query_score.total_score:.3f}")
        
        # 3. 메타데이터에서 키워드 채굴
        texts = [v.get_all_text() for v in videos]
        mined = self.miner.extract_hair_keywords(texts, top_k=30)
        
        # 중복 제거
        mined = self.miner.deduplicate(mined)
        
        if not self.quiet:
            print(f"  ⛏️ {len(mined)}개 키워드 채굴")
        
        # 4. 채굴된 키워드를 RankedKeyword로 변환
        ranked = []
        for extracted in mined:
            # 이미 있는 키워드 스킵
            if extracted.keyword in self.processed_queries:
                continue
            if extracted.keyword == keyword:
                continue
            
            # 점수 계산 (빈도 + 소스 수 + 쿼리 점수 반영)
            score = (
                0.4 * min(1.0, extracted.frequency / 10) +
                0.3 * min(1.0, extracted.source_count / 5) +
                0.3 * query_score.total_score
            )
            
            ranked.append(RankedKeyword(
                keyword=extracted.keyword,
                score=score,
                depth=depth + 1,
                parent_keyword=keyword,
                frequency=extracted.frequency,
                source_videos=extracted.source_count
            ))
        
        # 점수순 정렬
        ranked.sort(key=lambda x: x.score, reverse=True)
        
        # 확장 기록 저장
        self.expansion_history.append({
            'keyword': keyword,
            'depth': depth,
            'video_count': len(videos),
            'query_score': query_score.total_score,
            'mined_count': len(mined),
            'new_keywords': [r.keyword for r in ranked[:self.top_k_per_level]]
        })
        
        if not self.quiet and ranked:
            print(f"  ✨ 상위 키워드: {', '.join([r.keyword for r in ranked[:5]])}")
        
        return ranked
    
    def _log_level_summary(self, depth: int, keywords: List[str]):
        """레벨 완료 요약"""
        if not self.quiet and keywords:
            print(f"\n{'─' * 40}")
            print(f"📌 깊이 {depth} 완료: {len(keywords)}개 키워드 처리")
            print(f"   총 발굴 키워드: {len(self.all_keywords)}개")
    
    def get_top_keywords(self, limit: int = 50) -> List[RankedKeyword]:
        """
        상위 키워드 반환
        
        Args:
            limit: 반환할 최대 키워드 수
            
        Returns:
            점수순 정렬된 RankedKeyword 리스트
        """
        sorted_keywords = sorted(
            self.all_keywords.values(),
            key=lambda x: x.score,
            reverse=True
        )
        return sorted_keywords[:limit]
    
    def get_keywords_by_depth(self, depth: int) -> List[RankedKeyword]:
        """특정 깊이의 키워드만 반환"""
        return [kw for kw in self.all_keywords.values() if kw.depth == depth]
    
    def get_keyword_tree(self) -> Dict:
        """키워드 트리 구조 반환"""
        tree = {}
        
        for kw in self.all_keywords.values():
            if kw.depth == 0:
                tree[kw.keyword] = self._build_subtree(kw.keyword)
        
        return tree
    
    def _build_subtree(self, keyword: str) -> Dict:
        """서브트리 구축"""
        children = [
            kw for kw in self.all_keywords.values()
            if kw.parent_keyword == keyword
        ]
        
        if not children:
            return {}
        
        return {
            child.keyword: self._build_subtree(child.keyword)
            for child in children
        }
    
    def export_results(self, output_path: str = None) -> str:
        """
        결과를 JSON으로 내보내기
        
        Args:
            output_path: 저장 경로 (None이면 자동 생성)
            
        Returns:
            저장된 파일 경로
        """
        if output_path is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f"keyword_tree_{timestamp}.json"
        
        result = {
            'metadata': {
                'max_depth': self.max_depth,
                'top_k_per_level': self.top_k_per_level,
                'total_keywords': len(self.all_keywords),
                'processed_queries': len(self.processed_queries),
                'generated_at': datetime.now().isoformat(),
            },
            'keywords': [
                {
                    'keyword': kw.keyword,
                    'score': kw.score,
                    'depth': kw.depth,
                    'parent': kw.parent_keyword,
                    'frequency': kw.frequency,
                    'source_videos': kw.source_videos,
                }
                for kw in self.get_top_keywords(limit=None)
            ],
            'expansion_history': self.expansion_history,
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        if not self.quiet:
            print(f"\n💾 결과 저장: {output_path}")
        
        return output_path
    
    def get_query_strings(self, limit: int = 50) -> List[str]:
        """
        검색 쿼리로 사용할 문자열 리스트 반환
        
        기존 SEARCH_KEYWORDS 대체용
        """
        return [kw.keyword for kw in self.get_top_keywords(limit)]
    
    def print_summary(self):
        """결과 요약 출력"""
        print("\n" + "=" * 60)
        print("📊 키워드 트리 확장 결과 요약")
        print("=" * 60)
        
        # 깊이별 통계
        depth_stats = {}
        for kw in self.all_keywords.values():
            depth_stats[kw.depth] = depth_stats.get(kw.depth, 0) + 1
        
        print("\n📈 깊이별 키워드 수:")
        for depth in sorted(depth_stats.keys()):
            count = depth_stats[depth]
            bar = "█" * min(count // 2, 30)
            print(f"  깊이 {depth}: {count:3d}개 {bar}")
        
        # 상위 키워드
        print("\n🏆 상위 20개 키워드:")
        for i, kw in enumerate(self.get_top_keywords(20), 1):
            print(f"  {i:2d}. {kw.keyword} (점수: {kw.score:.3f}, 깊이: {kw.depth})")
        
        print("\n" + "=" * 60)


if __name__ == "__main__":
    # 테스트
    print("=== 키워드 트리 확장 테스트 ===")
    
    # 작은 규모로 테스트
    expander = KeywordTreeExpander(
        max_depth=2,  # 테스트용으로 낮춤
        top_k_per_level=5,
        quiet=False
    )
    
    # 소규모 시드로 테스트
    test_seeds = [
        "허쉬컷 스타일링",
        "지성두피 샴푸 추천",
    ]
    
    expander.expand(test_seeds)
    expander.print_summary()
    
    # 결과 내보내기
    expander.export_results("test_keywords.json")
