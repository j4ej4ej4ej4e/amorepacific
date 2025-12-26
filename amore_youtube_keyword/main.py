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

from keyword_engine import (
    SeedKeywordGenerator,
    KeywordTreeExpander,
    DEFAULT_SEED_KEYWORDS,
)


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
        '--generate-seeds',
        action='store_true',
        help='템플릿 기반 시드 키워드 자동 생성'
    )
    
    parser.add_argument(
        '--seed-count',
        type=int,
        default=30,
        help='자동 생성할 시드 키워드 수 (기본: 30)'
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
    elif args.generate_seeds:
        # 템플릿 기반 자동 생성
        generator = SeedKeywordGenerator()
        seed_keywords = generator.generate_random(args.seed_count)
        if not args.quiet:
            print(f"\n📌 자동 생성 시드 키워드: {len(seed_keywords)}개")
    else:
        # 기본 시드 사용
        seed_keywords = DEFAULT_SEED_KEYWORDS
        if not args.quiet:
            print(f"\n📌 기본 시드 키워드: {len(seed_keywords)}개")
    
    if not args.quiet:
        print(f"   예시: {', '.join(seed_keywords[:5])}...")
    
    # 트리 확장기 초기화
    expander = KeywordTreeExpander(
        max_depth=args.depth,
        top_k_per_level=args.top_k,
        quiet=args.quiet
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
    
    if not args.quiet:
        print(f"\n📄 키워드 목록 저장: {keywords_only_path}")
        print(f"\n✅ 완료! 총 {len(expander.all_keywords)}개 키워드 발굴")
        print("=" * 60)
    
    return expander.get_query_strings(args.limit)


if __name__ == "__main__":
    keywords = main()
