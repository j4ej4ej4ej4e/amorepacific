# 동적 키워드 추출 엔진
from .seed_keywords import SeedKeywordGenerator, SEED_TEMPLATES, TEMPLATE_VARS, DEFAULT_SEED_KEYWORDS
from .youtube_searcher import YouTubeSearcher, VideoMeta
from .keyword_miner import KeywordMiner
from .query_scorer import QueryScorer, QueryScore
from .tree_expander import KeywordTreeExpander, RankedKeyword

# 임베딩 기반 헤어 판단 (선택적)
try:
    from .hair_embedder import HairRelevanceChecker, get_hair_checker
except ImportError:
    HairRelevanceChecker = None
    get_hair_checker = None

__all__ = [
    'SeedKeywordGenerator',
    'YouTubeSearcher',
    'KeywordMiner',
    'QueryScorer',
    'KeywordTreeExpander',
    'VideoMeta',
    'QueryScore',
    'RankedKeyword',
    'SEED_TEMPLATES',
    'TEMPLATE_VARS',
    'DEFAULT_SEED_KEYWORDS',
    'HairRelevanceChecker',
    'get_hair_checker',
]
