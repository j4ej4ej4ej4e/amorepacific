#!/usr/bin/env bash
set -euo pipefail

# 간단 자동화 루프:
# 1) 키워드 확장 + 경계 구간 후보 생성
# 2) 경계 후보 라벨링 (대화형)
# 3) 임계값 최적화 → latest_threshold.json 갱신
#
# 사용 예시:
#   bash run_cycle.sh --depth 5 --top-k 10 --batch 50
#
# 옵션:
#   --depth N              트리 확장 깊이 (기본 5)
#   --top-k N              레벨당 확장 수 (기본 10)
#   --batch N              라벨링 개수 (기본 50)
#   --boundary-percent P   전체의 P 비율을 경계 후보로 선택 (기본 0.05)
#   --boundary-min N       경계 후보 최소 개수 (기본 50)
#   --boundary-max N       경계 후보 최대 개수 (기본 200)
#   --workers N            병렬 확장 작업자 수 (기본 4)

DEPTH=5
TOPK=10
BATCH=50
BOUNDARY_PERCENT=0.05
BOUNDARY_MIN=50
BOUNDARY_MAX=200
WORKERS=4

while [[ $# -gt 0 ]]; do
  case "$1" in
    --depth) DEPTH="$2"; shift 2;;
    --top-k) TOPK="$2"; shift 2;;
    --batch) BATCH="$2"; shift 2;;
    --boundary-percent) BOUNDARY_PERCENT="$2"; shift 2;;
    --boundary-min) BOUNDARY_MIN="$2"; shift 2;;
    --boundary-max) BOUNDARY_MAX="$2"; shift 2;;
    --workers) WORKERS="$2"; shift 2;;
    *) echo "알 수 없는 옵션: $1"; exit 1;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${ROOT}/output"
DATA_DIR="${ROOT}/data"
mkdir -p "$OUT_DIR" "$DATA_DIR"

TS="$(date +%Y%m%d_%H%M%S)"
OUT_JSON="${OUT_DIR}/keyword_tree_${TS}.json"
BOUNDARY_TXT="${OUT_DIR}/keyword_tree_${TS}_boundary_candidates.txt"

echo "=== [1/3] 키워드 확장 실행 ==="
python "${ROOT}/main.py" \
  --depth "$DEPTH" \
  --top-k "$TOPK" \
  --parallel-workers "$WORKERS" \
  --output "$OUT_JSON" \
  --threshold-file "${DATA_DIR}/latest_threshold.json" \
  --boundary-output "$BOUNDARY_TXT" \
  --boundary-mode auto \
  --boundary-percent "$BOUNDARY_PERCENT" \
  --boundary-min "$BOUNDARY_MIN" \
  --boundary-max "$BOUNDARY_MAX"

echo
echo "=== [2/3] 경계 구간 라벨링 (대화형) ==="
echo "파일: $BOUNDARY_TXT"
echo "개수: $(wc -l < "$BOUNDARY_TXT") (헤더 포함)"
echo "원치 않으면 Ctrl+C 로 건너뛰세요."
python "${ROOT}/expand_ground_truth.py" -k "$BOUNDARY_TXT" -b "$BATCH"

echo
echo "=== [3/3] 임계값 최적화 ==="
python "${ROOT}/expand_ground_truth.py" --optimize

echo
echo "완료: 최신 임계값은 ${DATA_DIR}/latest_threshold.json 에 저장됩니다."
