"""
쿼리 스코어링 모듈
검색 결과를 분석하여 쿼리의 품질을 평가합니다.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional
from datetime import datetime, timedelta
import math

# VideoMeta 임포트
from .youtube_searcher import VideoMeta


# 헤어 전문성 신호 키워드
EXPERTISE_SIGNALS = {
    # 리뷰/비교
    "리뷰", "후기", "비교", "순위", "랭킹", "추천", "best", "top",
    # 튜토리얼
    "방법", "하는법", "하는방법", "튜토리얼", "강의", "레슨",
    "how to", "tutorial",
    # 루틴/팁
    "루틴", "routine", "꿀팁", "팁", "tip", "노하우", "비법",
    # 전문가
    "원장", "디자이너", "미용사", "전문가", "프로",
    # 분석
    "분석", "성분", "원리", "과학", "테스트",
}

# 헤어 도메인 키워드 (관련성 체크용)
HAIR_DOMAIN_KEYWORDS = {
    "헤어", "머리", "두피", "모발", "컷", "펌", "염색", "탈색",
    "스타일링", "드라이", "샴푸", "트리트먼트", "에센스", "오일",
    "미용", "미용실", "살롱", "hair", "perm", "cut", "styling",
}


@dataclass
class QueryScore:
    """쿼리 품질 점수"""
    query: str
    
    # 개별 점수 (0~1)
    diversity_score: float = 0.0      # 채널 다양성
    freshness_score: float = 0.0      # 최신성
    expertise_score: float = 0.0      # 전문성 신호
    performance_score: float = 0.0    # 성과 (조회수 등)
    relevance_score: float = 0.0      # 헤어 관련성
    
    # 집계
    total_score: float = 0.0
    should_expand: bool = False
    
    # 메타 정보
    video_count: int = 0
    unique_channels: int = 0
    avg_view_count: float = 0.0
    recent_video_ratio: float = 0.0
    
    # 추출된 정보
    top_channels: List[str] = field(default_factory=list)
    matched_expertise_signals: List[str] = field(default_factory=list)


class QueryScorer:
    """
    쿼리 품질 스코어링
    
    검색 결과를 분석하여 해당 쿼리가 키워드 확장에 적합한지 평가합니다.
    """
    
    def __init__(self,
                 # 가중치 (옵션 B: 헤어 관련성 강화)
                 diversity_weight: float = 0.15,
                 freshness_weight: float = 0.10,
                 expertise_weight: float = 0.20,
                 performance_weight: float = 0.15,
                 relevance_weight: float = 0.40,  # ↑ 40%로 강화
                 # 임계값
                 expansion_threshold: float = 0.5,  # ↑ 0.5로 상향
                 freshness_days: int = 180,
                 min_videos: int = 5):
        """
        Args:
            diversity_weight: 채널 다양성 가중치
            freshness_weight: 최신성 가중치
            expertise_weight: 전문성 가중치
            performance_weight: 성과 가중치
            relevance_weight: 관련성 가중치
            expansion_threshold: 확장 여부 결정 임계값
            freshness_days: 최신으로 간주할 일수
            min_videos: 스코어링에 필요한 최소 영상 수
        """
        self.weights = {
            'diversity': diversity_weight,
            'freshness': freshness_weight,
            'expertise': expertise_weight,
            'performance': performance_weight,
            'relevance': relevance_weight,
        }
        self.expansion_threshold = expansion_threshold
        self.freshness_days = freshness_days
        self.min_videos = min_videos
    
    def score(self, query: str, videos: List[VideoMeta]) -> QueryScore:
        """
        쿼리와 검색 결과를 분석하여 점수 계산
        
        Args:
            query: 검색 쿼리
            videos: 검색 결과 VideoMeta 리스트
            
        Returns:
            QueryScore 객체
        """
        result = QueryScore(query=query)
        
        if not videos or len(videos) < self.min_videos:
            return result
        
        result.video_count = len(videos)
        
        # 1. 채널 다양성 점수
        result.diversity_score, result.unique_channels, result.top_channels = \
            self._calculate_diversity(videos)
        
        # 2. 최신성 점수
        result.freshness_score, result.recent_video_ratio = \
            self._calculate_freshness(videos)
        
        # 3. 전문성 신호 점수
        result.expertise_score, result.matched_expertise_signals = \
            self._calculate_expertise(videos)
        
        # 4. 성과 점수
        result.performance_score, result.avg_view_count = \
            self._calculate_performance(videos)
        
        # 5. 헤어 관련성 점수
        result.relevance_score = self._calculate_relevance(query, videos)
        
        # 6. 총점 계산
        result.total_score = (
            result.diversity_score * self.weights['diversity'] +
            result.freshness_score * self.weights['freshness'] +
            result.expertise_score * self.weights['expertise'] +
            result.performance_score * self.weights['performance'] +
            result.relevance_score * self.weights['relevance']
        )
        
        # 7. 확장 여부 결정
        result.should_expand = result.total_score >= self.expansion_threshold
        
        return result
    
    def _calculate_diversity(self, videos: List[VideoMeta]) -> tuple:
        """
        채널 다양성 계산
        
        서로 다른 채널 수 / 전체 영상 수
        """
        channels = set()
        channel_counts = {}
        
        for video in videos:
            ch = video.channel_title or video.channel_id
            if ch:
                channels.add(ch)
                channel_counts[ch] = channel_counts.get(ch, 0) + 1
        
        unique_channels = len(channels)
        total_videos = len(videos)
        
        # 다양성 점수: 채널당 평균 영상 수가 적을수록 높음
        diversity = unique_channels / total_videos if total_videos > 0 else 0
        
        # 상위 채널 추출
        top_channels = sorted(channel_counts.keys(), 
                             key=lambda x: channel_counts[x], 
                             reverse=True)[:5]
        
        return diversity, unique_channels, top_channels
    
    def _calculate_freshness(self, videos: List[VideoMeta]) -> tuple:
        """
        최신성 계산
        
        최근 N일 내 업로드 영상 비율
        """
        recent_count = 0
        has_date_count = 0
        
        for video in videos:
            days = video.days_since_upload
            if days is not None:
                has_date_count += 1
                if days <= self.freshness_days:
                    recent_count += 1
        
        if has_date_count == 0:
            # 날짜 정보가 없으면 중립적 점수
            return 0.5, 0.5
        
        ratio = recent_count / has_date_count
        return ratio, ratio
    
    def _calculate_expertise(self, videos: List[VideoMeta]) -> tuple:
        """
        전문성 신호 계산
        
        전문성 키워드 포함 비율
        """
        matched_signals = set()
        videos_with_expertise = 0
        
        for video in videos:
            text = video.get_all_text().lower()
            has_expertise = False
            
            for signal in EXPERTISE_SIGNALS:
                if signal.lower() in text:
                    matched_signals.add(signal)
                    has_expertise = True
            
            if has_expertise:
                videos_with_expertise += 1
        
        ratio = videos_with_expertise / len(videos) if videos else 0
        return ratio, list(matched_signals)
    
    def _calculate_performance(self, videos: List[VideoMeta]) -> tuple:
        """
        성과 점수 계산
        
        조회수 기반 (로그 스케일)
        """
        view_counts = [v.view_count for v in videos if v.view_count and v.view_count > 0]
        
        if not view_counts:
            return 0.5, 0  # 데이터 없으면 중립적
        
        avg_views = sum(view_counts) / len(view_counts)
        
        # 로그 스케일 정규화 (1천~1백만 범위)
        # log10(1000) = 3, log10(1000000) = 6
        log_views = math.log10(max(avg_views, 1))
        normalized = (log_views - 3) / 3  # 0~1 범위로 정규화
        
        # 클리핑
        score = max(0, min(1, normalized))
        
        return score, avg_views
    
    def _calculate_relevance(self, query: str, videos: List[VideoMeta]) -> float:
        """
        헤어 관련성 계산
        
        쿼리와 영상에 헤어 키워드 포함 비율
        """
        # 쿼리 관련성
        query_lower = query.lower()
        query_has_hair = any(kw.lower() in query_lower for kw in HAIR_DOMAIN_KEYWORDS)
        
        # 영상 관련성
        videos_with_hair = 0
        for video in videos:
            text = video.get_all_text().lower()
            if any(kw.lower() in text for kw in HAIR_DOMAIN_KEYWORDS):
                videos_with_hair += 1
        
        video_ratio = videos_with_hair / len(videos) if videos else 0
        
        # 쿼리에 헤어 키워드가 있으면 보너스
        if query_has_hair:
            return min(1.0, video_ratio + 0.2)
        
        return video_ratio
    
    def batch_score(self, query_videos: Dict[str, List[VideoMeta]]) -> Dict[str, QueryScore]:
        """
        여러 쿼리를 배치로 스코어링
        
        Args:
            query_videos: {쿼리: VideoMeta 리스트} 딕셔너리
            
        Returns:
            {쿼리: QueryScore} 딕셔너리
        """
        results = {}
        
        for query, videos in query_videos.items():
            results[query] = self.score(query, videos)
        
        return results
    
    def rank_queries(self, scores: Dict[str, QueryScore]) -> List[QueryScore]:
        """
        쿼리들을 점수순으로 정렬
        
        Args:
            scores: {쿼리: QueryScore} 딕셔너리
            
        Returns:
            점수순 정렬된 QueryScore 리스트
        """
        return sorted(scores.values(), key=lambda x: x.total_score, reverse=True)
    
    def filter_expandable(self, scores: Dict[str, QueryScore]) -> List[QueryScore]:
        """
        확장 가능한 쿼리만 필터링
        
        Args:
            scores: {쿼리: QueryScore} 딕셔너리
            
        Returns:
            should_expand=True인 QueryScore 리스트 (점수순)
        """
        expandable = [s for s in scores.values() if s.should_expand]
        return sorted(expandable, key=lambda x: x.total_score, reverse=True)


if __name__ == "__main__":
    # 테스트
    from youtube_searcher import YouTubeSearcher
    
    searcher = YouTubeSearcher(quiet=True)
    scorer = QueryScorer()
    
    test_queries = [
        "허쉬컷 스타일링",
        "지성두피 샴푸 추천",
    ]
    
    print("=== 쿼리 스코어링 테스트 ===")
    
    for query in test_queries:
        print(f"\n검색: {query}")
        videos = searcher.search(query, limit=20)
        score = scorer.score(query, videos)
        
        print(f"  총점: {score.total_score:.3f}")
        print(f"  다양성: {score.diversity_score:.3f} (채널 {score.unique_channels}개)")
        print(f"  최신성: {score.freshness_score:.3f}")
        print(f"  전문성: {score.expertise_score:.3f}")
        print(f"  성과: {score.performance_score:.3f} (평균 {score.avg_view_count:,.0f} 조회)")
        print(f"  관련성: {score.relevance_score:.3f}")
        print(f"  확장: {'예' if score.should_expand else '아니오'}")
