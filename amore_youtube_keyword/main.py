"""
동적 키워드 추출 파이프라인 메인 스크립트

트리 확장 기반으로 헤어 관련 트렌드 키워드를 자동으로 수집합니다.

사용법:
    python main.py                    # 기본 설정으로 실행
    python main.py --depth 3          # 깊이 3으로 실행
    python main.py --seeds "허쉬컷,레이어드컷"  # 커스텀 시드
"""
import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Tuple, List

from keyword_engine import (
    KeywordTreeExpander,
    DEFAULT_SEED_KEYWORDS,
    KeywordMiner,
)


DEFAULT_THRESHOLD = 0.35


def load_threshold(threshold_arg: float, threshold_file: str) -> float:
    """
    명시적 인자 → 파일 → 기본값 순으로 임계값을 로드
    """
    if threshold_arg is not None:
        return float(threshold_arg)
    
    if threshold_file:
        try:
            with open(threshold_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # 다양한 구조 지원
            if isinstance(data, dict):
                for key in ("optimal_threshold", "threshold"):
                    if key in data:
                        return float(data[key])
                # optimize 결과 형태
                if "metrics" in data and isinstance(data["metrics"], dict):
                    if "threshold" in data["metrics"]:
                        return float(data["metrics"]["threshold"])
            # 리스트일 경우 첫 항목 threshold 사용 시도
            if isinstance(data, list) and data and "threshold" in data[0]:
                return float(data[0]["threshold"])
        except FileNotFoundError:
            print(f"[경고] threshold 파일이 없어 기본값({DEFAULT_THRESHOLD})을 사용합니다: {threshold_file}")
        except Exception as e:
            print(f"[경고] threshold 파일 로드 실패, 기본값 사용: {e}")
    
    return DEFAULT_THRESHOLD


def parse_range(raw: str, default: Tuple[float, float]) -> Tuple[float, float]:
    try:
        parts = [float(x.strip()) for x in raw.split(',')]
        if len(parts) != 2:
            return default
        low, high = parts
        if low > high:
            low, high = high, low
        return low, high
    except Exception:
        return default


def export_boundary_candidates(expander: KeywordTreeExpander,
                               output_path: str,
                               threshold_value: float,
                               mode: str,
                               range_tuple: Tuple[float, float],
                               limit: int = 200,
                               percent: float = 0.05,
                               min_count: int = 50,
                               max_count: int = 200,
                               balanced: bool = True):
    """임계값 경계 구간 또는 임계값 근접 상위 N 키워드를 파일로 저장"""
    miner = expander.miner
    all_items: List[Tuple[str, float, float, int]] = []  # keyword, sim, score, depth
    for kw in expander.all_keywords.values():
        sim = miner.get_hair_similarity(kw.keyword)
        all_items.append((kw.keyword, sim, kw.score, kw.depth))
    
    if not all_items:
        print("[경고] 경계 후보를 만들 키워드가 없습니다.")
        return
    
    # 중복 제거
    dedup = {}
    for keyword, sim, score, depth in all_items:
        if keyword not in dedup:
            dedup[keyword] = (sim, score, depth)
    all_items = [(k, *v) for k, v in dedup.items()]
    
    candidates = []
    if mode == 'range':
        low, high = range_tuple
        mid = (low + high) / 2
        for keyword, sim, score, depth in all_items:
            if low <= sim <= high:
                distance = abs(mid - sim)
                candidates.append((distance, sim, score, depth, keyword))
        candidates.sort(key=lambda x: (x[0], -x[1]))
        candidates = candidates[:limit]
    else:
        # 임계값 근접 상위 N (auto)
        total = len(all_items)
        target = int(total * percent)
        target = max(min_count, target)
        target = min(max_count, target, total)
        
        lower = []
        upper = []
        for keyword, sim, score, depth in all_items:
            distance = abs(sim - threshold_value)
            record = (distance, sim, score, depth, keyword)
            if sim < threshold_value:
                lower.append(record)
            else:
                upper.append(record)
        
        lower.sort(key=lambda x: (x[0], -x[1]))
        upper.sort(key=lambda x: (x[0], -x[1]))
        
        if balanced:
            half = target // 2
            candidates = lower[:half] + upper[:target - half]
            # 부족한 쪽이 있으면 반대쪽에서 보충
            if len(candidates) < target:
                remainder = target - len(candidates)
                pool = lower[half:] + upper[target - half:]
                pool.sort(key=lambda x: (x[0], -x[1]))
                candidates.extend(pool[:remainder])
        else:
            pool = lower + upper
            pool.sort(key=lambda x: (x[0], -x[1]))
            candidates = pool[:target]
    
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        f.write("# keyword\tsimilarity\tscore\tdepth\n")
        for _, sim, score, depth, keyword in candidates:
            f.write(f"{keyword}\t{sim:.4f}\t{score:.4f}\t{depth}\n")
    
    print(f"\n🏷️ 경계/근접 키워드 저장: {path} (총 {len(candidates)}개)")


def main():
    parser = argparse.ArgumentParser(
        description='헤어 관련 트렌드 키워드 자동 수집 (트리 확장 방식)'
    )
    
    parser.add_argument(
        '--depth', '-d',
        type=int,
        default=5,
        help='트리 확장 최대 깊이 (기본: 5)'
    )
    
    parser.add_argument(
        '--top-k', '-k',
        type=int,
        default=10,
        help='레벨당 확장할 최대 키워드 수 (기본: 10)'
    )
    
    parser.add_argument(
        '--seeds', '-s',
        type=str,
        default=None,
        help='커스텀 시드 키워드 (쉼표로 구분)'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='결과 저장 경로 (기본: output/keyword_tree_YYYYMMDD_HHMMSS.json)'
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        default=100,
        help='최종 출력할 키워드 수 (기본: 100)'
    )
    
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='출력 최소화'
    )
    parser.add_argument(
        '--threshold',
        type=float,
        default=None,
        help=f'헤어 관련성 임계값 직접 지정 (기본: 파일→{DEFAULT_THRESHOLD})'
    )
    parser.add_argument(
        '--threshold-file',
        type=str,
        default='data/latest_threshold.json',
        help='임계값을 읽어올 JSON 파일 경로 (optimal_threshold/threshold 키 지원)'
    )
    parser.add_argument(
        '--boundary-output',
        type=str,
        default=None,
        help='경계 구간 키워드 저장 경로 (기본: output/..._boundary_candidates.txt)'
    )
    parser.add_argument(
        '--boundary-mode',
        type=str,
        choices=['auto', 'range'],
        default='auto',
        help='auto: 임계값 근접 상위 N, range: 지정 구간 포함 키워드'
    )
    parser.add_argument(
        '--boundary-range',
        type=str,
        default='0.25,0.45',
        help='경계 구간 유사도 범위 (예: 0.25,0.45)'
    )
    parser.add_argument(
        '--boundary-limit',
        type=int,
        default=200,
        help='경계 구간으로 저장할 최대 키워드 수 (기본: 200)'
    )
    parser.add_argument(
        '--boundary-percent',
        type=float,
        default=0.05,
        help='auto 모드에서 전체 중 몇 %를 후보로 뽑을지 (기본: 5%)'
    )
    parser.add_argument(
        '--boundary-min',
        type=int,
        default=50,
        help='auto 모드 최소 후보 수'
    )
    parser.add_argument(
        '--boundary-max',
        type=int,
        default=200,
        help='auto 모드 최대 후보 수'
    )
    parser.add_argument(
        '--boundary-unbalanced',
        action='store_true',
        help='auto 모드에서 상/하위 균형을 맞추지 않고 거리순으로만 선택'
    )
    parser.add_argument(
        '--skip-boundary',
        action='store_true',
        help='경계 구간 키워드 파일 생성을 건너뜀'
    )
    parser.add_argument(
        '--parallel-workers',
        type=int,
        default=1,
        help='키워드 확장 병렬 작업자 수 (기본: 1=직렬)'
    )
    
    args = parser.parse_args()
    
    # 출력 디렉토리 생성
    os.makedirs('output', exist_ok=True)
    
    # 시작 메시지
    if not args.quiet:
        print("=" * 60)
        print("🎯 헤어 키워드 자동 수집 파이프라인")
        print(f"   시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
    
    # 시드 키워드 준비
    if args.seeds:
        # 커스텀 시드
        seed_keywords = [s.strip() for s in args.seeds.split(',')]
        if not args.quiet:
            print(f"\n📌 커스텀 시드 키워드: {len(seed_keywords)}개")
    else:
        # 기본 시드 사용
        seed_keywords = DEFAULT_SEED_KEYWORDS
        if not args.quiet:
            print(f"\n📌 기본 시드 키워드: {len(seed_keywords)}개")
    
    if not args.quiet:
        print(f"   예시: {', '.join(seed_keywords[:5])}...")
    
    # 임계값 로드
    threshold_value = load_threshold(args.threshold, args.threshold_file)
    if not args.quiet:
        print(f"\n🎚️ 사용 임계값: {threshold_value:.3f} (파일: {args.threshold_file if args.threshold is None else '직접 지정'})")
    
    # 트리 확장기 초기화 (Kiwi/임계값 반영한 Miner 사용)
    miner = KeywordMiner(embedding_threshold=threshold_value)
    expander = KeywordTreeExpander(
        max_depth=args.depth,
        top_k_per_level=args.top_k,
        quiet=args.quiet,
        miner=miner,
        parallel_workers=args.parallel_workers
    )
    
    # 키워드 트리 확장 실행
    if not args.quiet:
        print(f"\n🌳 트리 확장 시작 (깊이: {args.depth}, 레벨당: {args.top_k}개)")
    
    expander.expand(seed_keywords)
    
    # 결과 요약
    if not args.quiet:
        expander.print_summary()
    
    # 결과 저장
    if args.output:
        output_path = args.output
    else:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = f"output/keyword_tree_{timestamp}.json"
    
    expander.export_results(output_path)
    
    # 최종 키워드 목록 별도 저장
    top_keywords = expander.get_top_keywords(args.limit)
    keywords_only_path = output_path.replace('.json', '_keywords.txt')
    
    with open(keywords_only_path, 'w', encoding='utf-8') as f:
        for kw in top_keywords:
            f.write(f"{kw.keyword}\t{kw.score:.4f}\t{kw.depth}\n")
    
    # 경계 구간 키워드 추출 (라벨링용)
    if not args.skip_boundary:
        boundary_range = parse_range(args.boundary_range, (0.25, 0.45))
        if args.boundary_output:
            boundary_output_path = args.boundary_output
        else:
            base = Path(output_path)
            boundary_output_path = base.with_name(base.stem + "_boundary_candidates.txt")
        export_boundary_candidates(
            expander,
            output_path=boundary_output_path,
            threshold_value=threshold_value,
            mode=args.boundary_mode,
            range_tuple=boundary_range,
            limit=args.boundary_limit,
            percent=args.boundary_percent,
            min_count=args.boundary_min,
            max_count=args.boundary_max,
            balanced=not args.boundary_unbalanced
        )
    
    if not args.quiet:
        print(f"\n📄 키워드 목록 저장: {keywords_only_path}")
        print(f"\n✅ 완료! 총 {len(expander.all_keywords)}개 키워드 발굴")
        print("=" * 60)
    
    return expander.get_query_strings(args.limit)


if __name__ == "__main__":
    keywords = main()
