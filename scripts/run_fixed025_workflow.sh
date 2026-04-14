#!/usr/bin/env bash
set -euo pipefail

# Run the primary fixed-0.25 verification workflow:
# - native forecast on 0.25 grid vs 0.25 altimetry
# - 1 degree forecast remapped to 0.25 grid vs 0.25 altimetry
# - 3 degree forecast remapped to 0.25 grid vs 0.25 altimetry
# Then generate skill plots and difference plots.
#
# Examples:
#   bash scripts/run_fixed025_workflow.sh
#   DOMAIN=pacific_small MAX_STARTS=4 bash scripts/run_fixed025_workflow.sh
#   DOMAIN=global bash scripts/run_fixed025_workflow.sh
#
# Recommended background usage:
#   nohup bash scripts/run_fixed025_workflow.sh > logs/workflow.out 2>&1 &

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

DOMAIN="${DOMAIN:-pacific_small}"
MAX_STARTS="${MAX_STARTS:-}"
START_MONTH="${START_MONTH:-}"
RESULTS_DIR="${RESULTS_DIR:-results}"
LOG_DIR="${LOG_DIR:-logs}"

VENV_PYTHON="${VENV_PYTHON:-${PROJECT_ROOT}/.venv/bin/python}"
MAMBA_PYTHON="${MAMBA_PYTHON:-${PROJECT_ROOT}/.mamba/envs/esmpy-891/bin/python}"

mkdir -p "${RESULTS_DIR}" "${LOG_DIR}"

# Keep each worker to one thread so that three concurrent jobs do not oversubscribe BLAS/OpenMP.
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export NUMEXPR_NUM_THREADS="${NUMEXPR_NUM_THREADS:-1}"
export VECLIB_MAXIMUM_THREADS="${VECLIB_MAXIMUM_THREADS:-1}"
export MPLCONFIGDIR="${MPLCONFIGDIR:-/tmp/mpl}"
mkdir -p "${MPLCONFIGDIR}"

case "${DOMAIN}" in
  pacific_small)
    DOMAIN_LABEL="central_pacific"
    DOMAIN_ARGS=(--lon-min 180 --lon-max 195 --lat-min -7.5 --lat-max 7.5)
    ;;
  global)
    DOMAIN_LABEL="global"
    DOMAIN_ARGS=()
    ;;
  *)
    echo "Unsupported DOMAIN=${DOMAIN}. Use pacific_small or global." >&2
    exit 1
    ;;
esac

EXTRA_ARGS=()
if [[ -n "${MAX_STARTS}" ]]; then
  EXTRA_ARGS+=(--max-starts "${MAX_STARTS}")
fi
if [[ -n "${START_MONTH}" ]]; then
  EXTRA_ARGS+=(--start-month "${START_MONTH}")
fi

NATIVE_NC="${RESULTS_DIR}/skill_025deg_${DOMAIN_LABEL}_fixed025.nc"
ONE_NC="${RESULTS_DIR}/skill_1deg_on025_${DOMAIN_LABEL}.nc"
THREE_NC="${RESULTS_DIR}/skill_3deg_on025_${DOMAIN_LABEL}.nc"

NATIVE_PNG="${RESULTS_DIR}/skill_025deg_${DOMAIN_LABEL}_fixed025.png"
ONE_PNG="${RESULTS_DIR}/skill_1deg_on025_${DOMAIN_LABEL}.png"
THREE_PNG="${RESULTS_DIR}/skill_3deg_on025_${DOMAIN_LABEL}.png"

ONE_DIFF_PNG="${RESULTS_DIR}/skill_diff_1deg_minus_native_${DOMAIN_LABEL}.png"
THREE_DIFF_PNG="${RESULTS_DIR}/skill_diff_3deg_minus_native_${DOMAIN_LABEL}.png"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

run_native() {
  "${MAMBA_PYTHON}" scripts/run_skill_analysis.py run \
    --resolution 0.25 \
    "${DOMAIN_ARGS[@]}" \
    "${EXTRA_ARGS[@]}" \
    --output "${NATIVE_NC}"
}

run_one_degree() {
  "${VENV_PYTHON}" scripts/run_skill_analysis.py run \
    --resolution 1 \
    --verification fixed_025 \
    "${DOMAIN_ARGS[@]}" \
    "${EXTRA_ARGS[@]}" \
    --output "${ONE_NC}"
}

run_three_degree() {
  "${VENV_PYTHON}" scripts/run_skill_analysis.py run \
    --resolution 3 \
    --verification fixed_025 \
    "${DOMAIN_ARGS[@]}" \
    "${EXTRA_ARGS[@]}" \
    --output "${THREE_NC}"
}

plot_skill() {
  local input_path="$1"
  local output_path="$2"
  local title="$3"
  "${VENV_PYTHON}" scripts/plot_skill_maps.py \
    --input "${input_path}" \
    --output "${output_path}" \
    --title "${title}"
}

plot_difference() {
  local experiment_path="$1"
  local output_path="$2"
  local title="$3"
  "${VENV_PYTHON}" scripts/plot_skill_differences.py \
    --baseline "${NATIVE_NC}" \
    --experiment "${experiment_path}" \
    --output "${output_path}" \
    --title "${title}"
}

echo "Starting fixed-0.25 workflow"
echo "Project root: ${PROJECT_ROOT}"
echo "Domain: ${DOMAIN}"
echo "Results dir: ${RESULTS_DIR}"
echo "Logs dir: ${LOG_DIR}"
if [[ -n "${MAX_STARTS}" ]]; then
  echo "Max starts: ${MAX_STARTS}"
else
  echo "Max starts: all available"
fi
if [[ -n "${START_MONTH}" ]]; then
  echo "Start month filter: ${START_MONTH}"
fi

run_native > "${LOG_DIR}/${TIMESTAMP}_native.log" 2>&1 &
PID_NATIVE=$!
run_one_degree > "${LOG_DIR}/${TIMESTAMP}_1deg.log" 2>&1 &
PID_ONE=$!
run_three_degree > "${LOG_DIR}/${TIMESTAMP}_3deg.log" 2>&1 &
PID_THREE=$!

echo "Analysis PIDs: native=${PID_NATIVE} 1deg=${PID_ONE} 3deg=${PID_THREE}"

wait "${PID_NATIVE}"
wait "${PID_ONE}"
wait "${PID_THREE}"

echo "Analysis complete. Starting plotting."

plot_skill "${NATIVE_NC}" "${NATIVE_PNG}" "SEAS5 Native Forecast Skill vs 0.25° Altimetry (${DOMAIN_LABEL})" \
  > "${LOG_DIR}/${TIMESTAMP}_plot_native.log" 2>&1 &
PID_PLOT_NATIVE=$!

plot_skill "${ONE_NC}" "${ONE_PNG}" "SEAS5 1° Forecast Skill vs 0.25° Altimetry (${DOMAIN_LABEL})" \
  > "${LOG_DIR}/${TIMESTAMP}_plot_1deg.log" 2>&1 &
PID_PLOT_ONE=$!

plot_skill "${THREE_NC}" "${THREE_PNG}" "SEAS5 3° Forecast Skill vs 0.25° Altimetry (${DOMAIN_LABEL})" \
  > "${LOG_DIR}/${TIMESTAMP}_plot_3deg.log" 2>&1 &
PID_PLOT_THREE=$!

wait "${PID_PLOT_NATIVE}"
wait "${PID_PLOT_ONE}"
wait "${PID_PLOT_THREE}"

echo "Skill plots complete. Starting difference plots."

plot_difference "${ONE_NC}" "${ONE_DIFF_PNG}" "1° Forecast Minus Native Forecast Skill vs 0.25° Altimetry (${DOMAIN_LABEL})" \
  > "${LOG_DIR}/${TIMESTAMP}_diff_1deg.log" 2>&1 &
PID_DIFF_ONE=$!

plot_difference "${THREE_NC}" "${THREE_DIFF_PNG}" "3° Forecast Minus Native Forecast Skill vs 0.25° Altimetry (${DOMAIN_LABEL})" \
  > "${LOG_DIR}/${TIMESTAMP}_diff_3deg.log" 2>&1 &
PID_DIFF_THREE=$!

wait "${PID_DIFF_ONE}"
wait "${PID_DIFF_THREE}"

echo "Workflow complete."
echo "Outputs:"
echo "  ${NATIVE_NC}"
echo "  ${ONE_NC}"
echo "  ${THREE_NC}"
echo "  ${NATIVE_PNG}"
echo "  ${ONE_PNG}"
echo "  ${THREE_PNG}"
echo "  ${ONE_DIFF_PNG}"
echo "  ${THREE_DIFF_PNG}"
