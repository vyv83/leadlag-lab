#!/bin/bash
set -euo pipefail

PROJECT=/root/projects/leadlag-lab
ENV_FILE="$PROJECT/config/jupyter.env"
NOTEBOOK="$PROJECT/notebooks/explore.ipynb"
EXEC_DIR="$PROJECT/notebooks/_executed"
REPORT_DIR="$PROJECT/notebooks/_reports"
JUPYTER_BIN="/root/projects/leadlag/.venv/bin/jupyter"

if [ ! -f "$ENV_FILE" ]; then
  echo "[error] Missing $ENV_FILE"
  exit 1
fi

if [ ! -x "$JUPYTER_BIN" ]; then
  echo "[error] Missing jupyter binary: $JUPYTER_BIN"
  exit 1
fi

source "$ENV_FILE"
: "${JUPYTER_PORT:?JUPYTER_PORT is required in jupyter.env}"
: "${JUPYTER_BASE_URL:?JUPYTER_BASE_URL is required in jupyter.env}"
: "${JUPYTER_TOKEN:?JUPYTER_TOKEN is required in jupyter.env}"

BASE_URL="$JUPYTER_BASE_URL"
if [[ "$BASE_URL" != /* ]]; then BASE_URL="/$BASE_URL"; fi
if [[ "$BASE_URL" != */ ]]; then BASE_URL="$BASE_URL/"; fi

TS="$(date -u +%Y%m%d_%H%M%S)"
EXEC_OUT="explore_${TS}.ipynb"
HTML_OUT="explore_${TS}.html"
LOCAL_API_URL="http://127.0.0.1:${JUPYTER_PORT}${BASE_URL}api?token=${JUPYTER_TOKEN}"

echo "[1/4] Checking service state"
STATE="$(systemctl is-active leadlag-lab-jupyter || true)"
echo "       state=${STATE}"
if [ "$STATE" != "active" ]; then
  echo "[error] leadlag-lab-jupyter is not active"
  exit 1
fi

echo "[2/4] Checking local Jupyter API"
for i in $(seq 1 30); do
  if curl -fsS "$LOCAL_API_URL" >/dev/null 2>&1; then
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "[error] Jupyter API is not reachable after waiting"
    exit 1
  fi
  sleep 1
done
echo "       api=ok"

echo "[3/4] Executing notebook"
mkdir -p "$EXEC_DIR" "$REPORT_DIR"
"$JUPYTER_BIN" nbconvert \
  --to notebook \
  --execute "$NOTEBOOK" \
  --output "$EXEC_OUT" \
  --output-dir "$EXEC_DIR" \
  --ExecutePreprocessor.timeout=120 >/dev/null
echo "       executed=$EXEC_DIR/$EXEC_OUT"

echo "[4/4] Exporting HTML report"
"$JUPYTER_BIN" nbconvert \
  --to html "$EXEC_DIR/$EXEC_OUT" \
  --output "$HTML_OUT" \
  --output-dir "$REPORT_DIR" >/dev/null
echo "       report=$REPORT_DIR/$HTML_OUT"

echo "[ok] Jupyter smoke check passed."
