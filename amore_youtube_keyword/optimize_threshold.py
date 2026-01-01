"""
헤어 키워드 관련성 Threshold 최적화 프레임워크

이론적 배경:
-----------
1. Semantic Similarity (의미적 유사도)
   - Sentence-BERT를 사용한 임베딩 기반 유사도 측정
   - 코사인 유사도: cos(θ) = (A·B) / (||A|| ||B||)
   - 범위: [-1, 1], 실제로는 [0, 1] 정규화

2. Binary Classification (이진 분류)
   - 헤어 관련(1) vs 비관련(0)
   - Threshold τ를 기준으로 결정 경계 설정
   - sim(keyword, hair_concept) >= τ → 헤어 관련

3. Performance Metrics (성능 지표)
   - Precision: TP / (TP + FP)  # 정확도 (찾은 것 중 맞는 비율)
   - Recall: TP / (TP + FN)     # 재현율 (전체 중 찾은 비율)
   - F1-Score: 2PR / (P+R)      # 정확도와 재현율의 조화평균
   - Accuracy: (TP+TN) / Total  # 전체 정확도

4. Threshold Optimization (임계값 최적화)
   - Precision-Recall Trade-off 고려
   - F1-Score 최대화를 목표로 설정
   - ROC-AUC로 모델 성능 평가

작성자: Antigravity
날짜: 2025-12-27
"""

import numpy as np
from typing import List, Tuple, Dict
from sklearn.metrics import (
    precision_score, recall_score, f1_score, accuracy_score,
    confusion_matrix, roc_curve, auc, precision_recall_curve
)
import json
from keyword_engine.hair_embedder import HairRelevanceChecker


class ThresholdOptimizer:
    """
    이론 기반 Threshold 최적화기
    
    Information Retrieval의 Precision-Recall Trade-off를 고려하여
    최적의 threshold를 찾습니다.
    
    최적화 목표:
    - F1-Score 최대화 (Precision과 Recall의 균형)
    - 도메인 특성 반영 (헤어 키워드 필터링)
    """
    
    def __init__(self, checker: HairRelevanceChecker = None):
        self.checker = checker or HairRelevanceChecker()
        self.test_data = []
        self.similarities = []
        self.labels = []
        
    def add_test_data(self, keyword: str, is_hair_related: bool):
        """
        테스트 데이터 추가
        
        Args:
            keyword: 테스트할 키워드
            is_hair_related: Ground Truth (헤어 관련 여부)
        """
        self.test_data.append((keyword, is_hair_related))
        similarity = self.checker.get_similarity(keyword)
        self.similarities.append(similarity)
        self.labels.append(1 if is_hair_related else 0)
    
    def load_default_test_data(self):
        """
        기본 테스트 데이터 로드
        
        카테고리별로 균형 잡힌 데이터셋 구성:
        - Positive (헤어 관련): 다양한 하위 카테고리 커버
        - Negative (비관련): 인접 도메인 포함하여 변별력 테스트
        - Boundary Cases (경계): 애매한 경우 명시적 판단
        """
        
        # 헤어 관련 키워드 (Ground Truth = True)
        hair_related = [
            # 1. 스타일/시술 (명확)
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
            
            # 5. 니치/트렌드 (낮은 유사도 예상되지만 관련 있음)
            "셀프 히피펌",
            "애즈펌 스타일링",
            "시스루뱅 자르기",
            "찰랑이는 머릿결",
        ]
        
        # 경계 사례 (도메인 지식 필요)
        boundary_cases = [
            # 헤어로 판단해야 함
            ("볼륨감 살리기", True),     # 헤어 볼륨
            ("윤기나는 방법", True),     # 헤어 윤기
            ("건강한 모발", True),       # 헤어 건강
            ("푸석함 개선", True),       # 헤어 상태
            
            # 비관련으로 판단해야 함
            ("건조함 해결", False),      # 피부 관련 가능성
            ("영양크림", False),         # 스킨케어
            ("수분 충전", False),        # 스킨케어
        ]
        
        # 명확히 비관련 키워드
        non_hair = [
            # 1. 인접 뷰티 도메인
            "메이크업 루틴",
            "스킨케어 추천",
            "네일 아트",
            "속눈썹 펌",
            
            # 2. 패션
            "패션 코디네이션",
            "악세서리 추천",
            "옷 스타일링",
            
            # 3. 라이프스타일
            "맛집 추천",
            "카페 브이로그",
            "여행 일정",
            "홈트레이닝",
            
            # 4. 기타
            "게임 리뷰",
            "주식 투자",
            "요리 레시피",
            "반려동물",
        ]
        
        # 데이터 추가
        for kw in hair_related:
            self.add_test_data(kw, True)
        
        for kw, label in boundary_cases:
            self.add_test_data(kw, label)
        
        for kw in non_hair:
            self.add_test_data(kw, False)
        
        print(f"✅ 테스트 데이터 로드 완료:")
        print(f"   - 헤어 관련: {sum(self.labels)}개")
        print(f"   - 비관련: {len(self.labels) - sum(self.labels)}개")
        print(f"   - 총: {len(self.labels)}개")
    
    def evaluate_threshold(self, threshold: float) -> Dict[str, float]:
        """
        특정 threshold의 성능 평가
        
        Args:
            threshold: 평가할 임계값
            
        Returns:
            성능 지표 딕셔너리
        """
        predictions = [1 if sim >= threshold else 0 for sim in self.similarities]
        
        # Confusion Matrix
        tn, fp, fn, tp = confusion_matrix(self.labels, predictions).ravel()
        
        # 성능 지표 계산
        precision = precision_score(self.labels, predictions, zero_division=0)
        recall = recall_score(self.labels, predictions, zero_division=0)
        f1 = f1_score(self.labels, predictions, zero_division=0)
        accuracy = accuracy_score(self.labels, predictions)
        
        # Specificity (True Negative Rate)
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0
        
        return {
            'threshold': threshold,
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1_score': f1,
            'specificity': specificity,
            'tp': int(tp),
            'fp': int(fp),
            'tn': int(tn),
            'fn': int(fn),
        }
    
    def find_optimal_threshold(self, 
                              metric: str = 'f1_score',
                              threshold_range: Tuple[float, float] = (0.15, 0.60),
                              num_points: int = 46) -> Tuple[float, Dict]:
        """
        최적 threshold 탐색
        
        이론적 근거:
        - F1-Score는 Precision과 Recall의 조화평균으로,
          두 지표의 균형을 최적화합니다.
        - 헤어 키워드 필터링에서는:
          * High Precision: 노이즈 최소화 (허수 인플루언서 방지)
          * High Recall: 커버리지 최대화 (관련 인플루언서 놓치지 않기)
        
        Args:
            metric: 최적화할 지표 ('f1_score', 'accuracy', etc.)
            threshold_range: 탐색 범위
            num_points: 탐색 포인트 수
            
        Returns:
            (최적_threshold, 성능_지표)
        """
        thresholds = np.linspace(threshold_range[0], threshold_range[1], num_points)
        results = []
        
        for threshold in thresholds:
            result = self.evaluate_threshold(threshold)
            results.append(result)
        
        # 최적 threshold 선택
        best_result = max(results, key=lambda x: x[metric])
        return best_result['threshold'], best_result, results
    
    def plot_results(self, results: List[Dict], save_path: str = None):
        """
        결과 시각화 (텍스트 기반)
        
        Args:
            results: evaluate_threshold 결과 리스트
            save_path: 저장 경로 (옵션)
        """
        print("\n" + "=" * 80)
        print("📊 Threshold 최적화 결과")
        print("=" * 80)
        
        # 헤더
        print(f"\n{'Threshold':>10} | {'Accuracy':>10} | {'Precision':>10} | "
              f"{'Recall':>10} | {'F1-Score':>10} | {'Marker':>6}")
        print("-" * 80)
        
        # 최고 F1 찾기
        best_f1 = max(r['f1_score'] for r in results)
        
        # 결과 출력
        for r in results:
            marker = "⭐ 최적" if abs(r['f1_score'] - best_f1) < 0.001 else ""
            
            print(f"{r['threshold']:10.3f} | "
                  f"{r['accuracy']:9.1%} | "
                  f"{r['precision']:9.1%} | "
                  f"{r['recall']:9.1%} | "
                  f"{r['f1_score']:10.3f} | "
                  f"{marker:>10}")
        
        print("=" * 80)
        
        # JSON 저장
        if save_path:
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"\n💾 결과 저장: {save_path}")
    
    def print_roc_analysis(self):
        """
        ROC-AUC 분석 (이론적 설명 포함)
        
        ROC (Receiver Operating Characteristic):
        - TPR (True Positive Rate) vs FPR (False Positive Rate)
        - AUC (Area Under Curve): 모델의 전반적 성능 지표
        - AUC = 1.0: 완벽한 분류기
        - AUC = 0.5: 랜덤 분류기
        """
        fpr, tpr, thresholds_roc = roc_curve(self.labels, self.similarities)
        roc_auc = auc(fpr, tpr)
        
        print("\n" + "=" * 80)
        print("📈 ROC-AUC 분석")
        print("=" * 80)
        print(f"\n🎯 AUC (Area Under Curve): {roc_auc:.4f}")
        print(f"\n해석:")
        if roc_auc >= 0.9:
            print(f"  ✅ 우수 (Excellent): 모델이 헤어 관련성을 매우 잘 구분합니다.")
        elif roc_auc >= 0.8:
            print(f"  ✅ 양호 (Good): 모델이 헤어 관련성을 잘 구분합니다.")
        elif roc_auc >= 0.7:
            print(f"  ⚠️ 보통 (Fair): 모델 성능이 수용 가능한 수준입니다.")
        else:
            print(f"  ❌ 부족 (Poor): 모델 개선이 필요합니다.")
        
        print(f"\n💡 의미:")
        print(f"  - 랜덤하게 선택한 헤어 관련 키워드가")
        print(f"    비관련 키워드보다 높은 점수를 받을 확률: {roc_auc:.1%}")
        print("=" * 80)
        
        return roc_auc
    
    def print_pr_analysis(self):
        """
        Precision-Recall 분석
        
        이론적 배경:
        - 불균형 데이터셋에서 ROC보다 유용
        - Precision-Recall Trade-off 시각화
        """
        precision, recall, thresholds_pr = precision_recall_curve(
            self.labels, self.similarities
        )
        
        # Average Precision
        from sklearn.metrics import average_precision_score
        avg_precision = average_precision_score(self.labels, self.similarities)
        
        print("\n" + "=" * 80)
        print("📉 Precision-Recall 분석")
        print("=" * 80)
        print(f"\n🎯 Average Precision: {avg_precision:.4f}")
        print(f"\n해석:")
        print(f"  - Precision-Recall 곡선 아래 면적")
        print(f"  - 모든 threshold에서의 평균적인 성능")
        
        # F1이 최대인 지점 찾기
        f1_scores = 2 * (precision * recall) / (precision + recall + 1e-10)
        best_idx = np.argmax(f1_scores)
        
        print(f"\n📍 F1 최대 지점:")
        print(f"  - Threshold: {thresholds_pr[best_idx]:.3f}")
        print(f"  - Precision: {precision[best_idx]:.1%}")
        print(f"  - Recall: {recall[best_idx]:.1%}")
        print(f"  - F1-Score: {f1_scores[best_idx]:.3f}")
        print("=" * 80)
        
        return avg_precision, thresholds_pr[best_idx]
    
    def print_detailed_analysis(self, threshold: float):
        """
        특정 threshold의 상세 분석
        
        Args:
            threshold: 분석할 임계값
        """
        result = self.evaluate_threshold(threshold)
        
        print("\n" + "=" * 80)
        print(f"🔍 Threshold = {threshold:.3f} 상세 분석")
        print("=" * 80)
        
        # Confusion Matrix
        print(f"\n📊 Confusion Matrix:")
        print(f"                    Predicted")
        print(f"                Positive  Negative")
        print(f"  Actual Positive    {result['tp']:4d}      {result['fn']:4d}   (Total: {result['tp'] + result['fn']})")
        print(f"         Negative    {result['fp']:4d}      {result['tn']:4d}   (Total: {result['fp'] + result['tn']})")
        
        # 성능 지표
        print(f"\n📈 성능 지표:")
        print(f"  - Accuracy   : {result['accuracy']:.1%}  (전체 정확도)")
        print(f"  - Precision  : {result['precision']:.1%}  (찾은 것 중 맞는 비율)")
        print(f"  - Recall     : {result['recall']:.1%}  (전체 중 찾은 비율)")
        print(f"  - F1-Score   : {result['f1_score']:.3f}  (Precision-Recall 조화평균)")
        print(f"  - Specificity: {result['specificity']:.1%}  (비관련을 정확히 거른 비율)")
        
        # 실전 의미
        print(f"\n💼 실전 적용 시 예상:")
        total_keywords = 1000  # 가정
        hair_ratio = sum(self.labels) / len(self.labels)
        expected_hair = int(total_keywords * hair_ratio)
        
        found_hair = int(expected_hair * result['recall'])
        found_total = int(found_hair / result['precision']) if result['precision'] > 0 else 0
        false_positives = found_total - found_hair
        
        print(f"  - 전체 키워드 {total_keywords}개 중")
        print(f"  - 실제 헤어 관련: ~{expected_hair}개")
        print(f"  - 시스템이 찾을 것: ~{found_total}개")
        print(f"    * 정확: {found_hair}개")
        print(f"    * 오탐: {false_positives}개")
        print(f"    * 놓침: {expected_hair - found_hair}개")
        
        print("=" * 80)
        
        return result


def main():
    """메인 실행 함수"""
    print("\n" + "🎯" * 40)
    print("헤어 키워드 관련성 Threshold 최적화 프레임워크")
    print("🎯" * 40)
    
    # 1. 초기화
    print("\n[1/5] 🔧 초기화 중...")
    optimizer = ThresholdOptimizer()
    
    # 2. 테스트 데이터 로드
    print("\n[2/5] 📥 테스트 데이터 로드 중...")
    optimizer.load_default_test_data()
    
    # 3. ROC-AUC 분석
    print("\n[3/5] 📊 ROC-AUC 분석 중...")
    roc_auc = optimizer.print_roc_analysis()
    
    # 4. Precision-Recall 분석
    print("\n[4/5] 📉 Precision-Recall 분석 중...")
    avg_precision, suggested_threshold = optimizer.print_pr_analysis()
    
    # 5. 최적 threshold 탐색
    print("\n[5/5] 🔍 최적 Threshold 탐색 중...")
    optimal_threshold, best_result, all_results = optimizer.find_optimal_threshold(
        metric='f1_score',
        threshold_range=(0.15, 0.60),
        num_points=46
    )
    
    # 결과 출력
    optimizer.plot_results(all_results, 'threshold_optimization_results.json')
    
    # 상세 분석
    print(f"\n{'='*80}")
    print(f"🏆 최종 권장 Threshold")
    print(f"{'='*80}")
    print(f"\n1️⃣ F1-Score 기준 최적값: {optimal_threshold:.3f}")
    optimizer.print_detailed_analysis(optimal_threshold)
    
    print(f"\n2️⃣ PR Curve 기준 권장값: {suggested_threshold:.3f}")
    if abs(optimal_threshold - suggested_threshold) < 0.05:
        print(f"   ✅ 두 방법의 결과가 일치합니다. (차이: {abs(optimal_threshold - suggested_threshold):.3f})")
    else:
        print(f"   ⚠️ 차이가 있습니다. 도메인 특성을 고려하여 선택하세요.")
        optimizer.print_detailed_analysis(suggested_threshold)
    
    # 현재 기본값 비교
    print(f"\n3️⃣ 현재 기본값 (0.35) 비교:")
    optimizer.print_detailed_analysis(0.35)
    
    # 최종 권장사항
    print("\n" + "=" * 80)
    print("💡 최종 권장사항")
    print("=" * 80)
    print(f"\n✅ 권장 Threshold: {optimal_threshold:.3f}")
    print(f"\n📝 근거:")
    print(f"  1. ROC-AUC ({roc_auc:.3f}): 모델의 변별력이 {'우수' if roc_auc >= 0.9 else '양호'}합니다.")
    print(f"  2. F1-Score ({best_result['f1_score']:.3f}): Precision-Recall 균형이 최적입니다.")
    print(f"  3. Precision ({best_result['precision']:.1%}): 노이즈 제거 능력이 {'우수' if best_result['precision'] >= 0.9 else '양호'}합니다.")
    print(f"  4. Recall ({best_result['recall']:.1%}): 커버리지가 {'우수' if best_result['recall'] >= 0.9 else '양호'}합니다.")
    print(f"\n🔧 적용 방법:")
    print(f"  hair_embedder.py의 threshold 파라미터를 {optimal_threshold:.3f}로 변경")
    print("=" * 80)


if __name__ == "__main__":
    main()
