"""
Ground Truth 점진적 확장 도구

작업 흐름:
1. 초기: optimize_threshold.py의 44개 데이터
2. 파이프라인 실행 → 새 키워드 생성
3. 이 도구로 대화형 라벨링
4. 재최적화 → 더 정확한 threshold
5. 반복

사용법:
  python expand_ground_truth.py --keywords output/keywords.txt --batch 20
"""

import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple
import sys

from keyword_engine.hair_embedder import HairRelevanceChecker
from optimize_threshold import ThresholdOptimizer


class GroundTruthManager:
    """Ground Truth 데이터 관리"""
    
    def __init__(self, data_path: str = 'data/ground_truth.json'):
        self.data_path = Path(data_path)
        self.data_path.parent.mkdir(exist_ok=True)
        self.data = self._load()
        
    def _load(self) -> List[Dict]:
        """기존 데이터 로드"""
        if self.data_path.exists():
            with open(self.data_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    def save(self):
        """데이터 저장"""
        with open(self.data_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        print(f"\n💾 저장 완료: {self.data_path} ({len(self.data)}개)")
    
    def add(self, keyword: str, is_hair_related: bool, similarity: float, 
            note: str = ""):
        """새 데이터 추가"""
        self.data.append({
            'keyword': keyword,
            'is_hair_related': is_hair_related,
            'similarity': similarity,
            'note': note,
            'timestamp': datetime.now().isoformat()
        })
    
    def get_keywords(self) -> List[str]:
        """이미 라벨링된 키워드 목록"""
        return [item['keyword'] for item in self.data]
    
    def get_statistics(self) -> Dict:
        """통계 정보"""
        if not self.data:
            return {
                'total': 0, 
                'hair_related': 0, 
                'non_related': 0,
                'ratio': 0.0
            }
        
        hair_count = sum(1 for item in self.data if item['is_hair_related'])
        return {
            'total': len(self.data),
            'hair_related': hair_count,
            'non_related': len(self.data) - hair_count,
            'ratio': hair_count / len(self.data)
        }


class InteractiveLabelingTool:
    """대화형 라벨링 도구"""
    
    def __init__(self, manager: GroundTruthManager):
        self.manager = manager
        self.checker = HairRelevanceChecker()
        self.session_stats = {'labeled': 0, 'skipped': 0, 'quit': False}
        
    def load_keywords_from_file(self, file_path: str) -> List[str]:
        """파일에서 키워드 로드"""
        path = Path(file_path)
        
        if not path.exists():
            print(f"❌ 파일 없음: {file_path}")
            return []
        
        keywords = []
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                # 헤더/주석 스킵
                if line.startswith("#"):
                    continue
                # 탭 구분일 경우 첫 컬럼만 사용
                if "\t" in line:
                    line = line.split("\t", 1)[0]
                if line:
                    keywords.append(line)
        
        # 이미 라벨링된 것 제외
        existing = set(self.manager.get_keywords())
        new_keywords = [kw for kw in keywords if kw not in existing]
        
        print(f"\n📂 파일 로드: {file_path}")
        print(f"  - 전체: {len(keywords)}개")
        print(f"  - 기존 라벨: {len(keywords) - len(new_keywords)}개 (스킵)")
        print(f"  - 새 키워드: {len(new_keywords)}개")
        
        return new_keywords
    
    def label_batch(self, keywords: List[str], batch_size: int = None):
        """배치 라벨링"""
        if batch_size:
            keywords = keywords[:batch_size]
        
        if not keywords:
            print("\n⚠️ 라벨링할 키워드가 없습니다.")
            return
        
        print("\n" + "="*70)
        print("🏷️ 대화형 키워드 라벨링")
        print("="*70)
        print(f"\n📝 라벨링할 키워드: {len(keywords)}개")
        print(f"📊 현재 Ground Truth: {len(self.manager.data)}개")
        print("\n사용법:")
        print("  y    : 헤어 관련")
        print("  n    : 비관련")
        print("  s    : 스킵 (나중에)")
        print("  q    : 종료")
        print("  ?    : 도움말")
        print("="*70)
        
        for i, keyword in enumerate(keywords, 1):
            if self.session_stats['quit']:
                break
            
            self._label_single_keyword(keyword, i, len(keywords))
        
        # 세션 요약
        self._print_session_summary()
        
        # 자동 저장
        if self.session_stats['labeled'] > 0:
            self.manager.save()
    
    def _label_single_keyword(self, keyword: str, index: int, total: int):
        """단일 키워드 라벨링"""
        print(f"\n{'─'*70}")
        print(f"[{index}/{total}] '{keyword}'")
        
        # 유사도 계산 및 힌트
        similarity = self.checker.get_similarity(keyword)
        current_threshold = self.checker.threshold
        prediction = "✅ 헤어 관련" if similarity >= current_threshold else "❌ 비관련"
        
        print(f"  💡 유사도: {similarity:.3f} (현재 threshold: {current_threshold:.3f})")
        print(f"  🤖 AI 예측: {prediction}")
        
        # 유사 키워드 힌트 (선택적)
        self._show_similarity_hints(keyword)
        
        while True:
            response = input(f"\n  판단 (y/n/s/q/?): ").lower().strip()
            
            if response == 'y':
                self.manager.add(keyword, True, similarity)
                self.session_stats['labeled'] += 1
                print(f"  ✅ 헤어 관련으로 저장")
                break
            
            elif response == 'n':
                self.manager.add(keyword, False, similarity)
                self.session_stats['labeled'] += 1
                print(f"  ❌ 비관련으로 저장")
                break
            
            elif response == 's':
                self.session_stats['skipped'] += 1
                print(f"  ⏭️ 스킵")
                break
            
            elif response == 'q':
                print(f"\n  ⏹️ 종료합니다.")
                self.session_stats['quit'] = True
                break
            
            elif response == '?':
                self._show_help()
            
            else:
                print(f"  ⚠️ 잘못된 입력입니다. (y/n/s/q/?)")
    
    def _show_similarity_hints(self, keyword: str):
        """유사도 힌트 표시"""
        # 구현 생략: 기존 라벨과의 유사도를 보여줄 수 있음
        pass
    
    def _show_help(self):
        """도움말"""
        print("\n  📖 도움말:")
        print("    - 헤어 관련: 머리, 두피, 스타일, 시술, 제품 등")
        print("    - 비관련: 메이크업, 스킨케어, 패션, 라이프스타일 등")
        print("    - 애매한 경우: 문맥상 헤어에 더 가까우면 y")
    
    def _print_session_summary(self):
        """세션 요약"""
        print("\n" + "="*70)
        print("📊 세션 요약")
        print("="*70)
        print(f"  라벨링: {self.session_stats['labeled']}개")
        print(f"  스킵: {self.session_stats['skipped']}개")
        
        # 전체 통계
        stats = self.manager.get_statistics()
        print(f"\n📈 전체 Ground Truth:")
        print(f"  총: {stats['total']}개")
        print(f"  헤어 관련: {stats['hair_related']}개 ({stats['ratio']:.1%})")
        print(f"  비관련: {stats['non_related']}개")
        print("="*70)


class ProgressiveOptimizer:
    """점진적 최적화"""
    
    def __init__(self, manager: GroundTruthManager):
        self.manager = manager
    
    def optimize(self) -> Tuple[float, Dict]:
        """현재 데이터로 최적화"""
        stats = self.manager.get_statistics()
        
        if stats['total'] < 20:
            print(f"\n⚠️ 데이터가 부족합니다. (최소 20개 필요, 현재 {stats['total']}개)")
            print(f"   더 많이 라벨링 후 최적화하세요.")
            return None, None
        
        print("\n" + "="*70)
        print(f"🔍 최적화 시작 (데이터: {stats['total']}개)")
        print("="*70)
        
        # ThresholdOptimizer에 데이터 로드
        optimizer = ThresholdOptimizer()
        
        for item in self.manager.data:
            optimizer.add_test_data(item['keyword'], item['is_hair_related'])
        
        # ROC-AUC
        roc_auc = optimizer.print_roc_analysis()
        
        # Precision-Recall
        avg_precision, suggested_threshold = optimizer.print_pr_analysis()
        
        # 최적 threshold 탐색
        optimal_threshold, best_result, all_results = optimizer.find_optimal_threshold()
        
        # 결과 요약
        print("\n" + "="*70)
        print("🏆 최적화 결과")
        print("="*70)
        print(f"\n📊 데이터셋: {stats['total']}개")
        print(f"  - 헤어 관련: {stats['hair_related']}개")
        print(f"  - 비관련: {stats['non_related']}개")
        print(f"\n🎯 최적 Threshold: {optimal_threshold:.3f}")
        print(f"  - F1-Score: {best_result['f1_score']:.3f}")
        print(f"  - Precision: {best_result['precision']:.1%}")
        print(f"  - Recall: {best_result['recall']:.1%}")
        print(f"  - ROC-AUC: {roc_auc:.3f}")
        print("="*70)
        
        # 상세 분석
        optimizer.print_detailed_analysis(optimal_threshold)
        
        # 결과 저장
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        result_path = f'data/optimization_result_{timestamp}.json'
        
        result_data = {
            'timestamp': timestamp,
            'dataset_size': stats['total'],
            'optimal_threshold': optimal_threshold,
            'metrics': best_result,
            'roc_auc': roc_auc,
            'all_results': all_results
        }
        
        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 결과 저장: {result_path}")
        
        # 최신 임계값 파일로도 기록해 파이프라인에서 바로 사용
        latest_path = Path('data/latest_threshold.json')
        latest_payload = {
            'timestamp': timestamp,
            'optimal_threshold': optimal_threshold,
            'metrics': best_result,
            'roc_auc': roc_auc,
        }
        with open(latest_path, 'w', encoding='utf-8') as f:
            json.dump(latest_payload, f, indent=2, ensure_ascii=False)
        print(f"   최신 임계값 갱신: {latest_path}")
        
        return optimal_threshold, best_result
    
    def compare_with_previous(self, current_threshold: float):
        """이전 결과와 비교"""
        # 구현: 이전 최적화 결과들과 비교하여 개선 추이 표시
        pass


def main():
    parser = argparse.ArgumentParser(
        description='Ground Truth 점진적 확장 및 최적화'
    )
    
    parser.add_argument(
        '--keywords', '-k',
        type=str,
        help='라벨링할 키워드 파일 경로 (예: output/keywords.txt)'
    )
    
    parser.add_argument(
        '--batch', '-b',
        type=int,
        default=20,
        help='한 번에 라벨링할 개수 (기본: 20)'
    )
    
    parser.add_argument(
        '--optimize', '-o',
        action='store_true',
        help='라벨링 후 자동으로 최적화 실행'
    )
    
    parser.add_argument(
        '--data-path', '-d',
        type=str,
        default='data/ground_truth.json',
        help='Ground Truth 저장 경로'
    )
    
    parser.add_argument(
        '--stats',
        action='store_true',
        help='현재 통계만 표시'
    )
    
    args = parser.parse_args()
    
    # Manager 초기화
    manager = GroundTruthManager(args.data_path)
    
    # 통계만 표시
    if args.stats:
        stats = manager.get_statistics()
        print("\n" + "="*70)
        print("📊 Ground Truth 현황")
        print("="*70)
        print(f"  총: {stats['total']}개")
        print(f"  헤어 관련: {stats['hair_related']}개 ({stats['ratio']:.1%})")
        print(f"  비관련: {stats['non_related']}개")
        print("="*70)
        return
    
    # 라벨링
    if args.keywords:
        tool = InteractiveLabelingTool(manager)
        keywords = tool.load_keywords_from_file(args.keywords)
        
        if keywords:
            tool.label_batch(keywords, args.batch)
    
    # 최적화
    if args.optimize:
        optimizer = ProgressiveOptimizer(manager)
        optimal_threshold, result = optimizer.optimize()
        
        if optimal_threshold:
            print("\n" + "="*70)
            print("💡 다음 단계")
            print("="*70)
            print(f"\n1️⃣ hair_embedder.py 수정:")
            print(f"   threshold: float = {optimal_threshold:.3f}")
            print(f"\n2️⃣ 파이프라인 재실행:")
            print(f"   python main.py")
            print(f"\n3️⃣ 더 라벨링하려면:")
            print(f"   python expand_ground_truth.py -k output/keywords.txt -b 20")
            print("="*70)


if __name__ == "__main__":
    main()
