#!/bin/bash
set -euo pipefail

PROJECT=/root/projects/leadlag-lab
JUPYTER_USER=leadlag-lab
ENV_FILE="$PROJECT/config/jupyter.env"
ENV_EXAMPLE="$PROJECT/config/jupyter.env.example"

echo "=== LeadLag Lab Jupyter secure setup ==="

if ! id -u "$JUPYTER_USER" >/dev/null 2>&1; then
  echo "[+] Creating system user: $JUPYTER_USER"
  useradd --system --create-home --shell /usr/sbin/nologin "$JUPYTER_USER"
else
  echo "[=] User exists: $JUPYTER_USER"
fi

echo "[+] Ensuring notebook/data directories"
mkdir -p \
  "$PROJECT/notebooks" \
  "$PROJECT/data" \
  "$PROJECT/data/jupyter_home/runtime" \
  "$PROJECT/data/jupyter_home/data" \
  "$PROJECT/data/strategies" \
  "$PROJECT/data/backtest"

if [ ! -f "$ENV_FILE" ]; then
  echo "[+] Creating $ENV_FILE"

  if command -v openssl >/dev/null 2>&1; then
    TOKEN="$(openssl rand -hex 32)"
  else
    TOKEN="$(python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
)"
  fi

  cp "$ENV_EXAMPLE" "$ENV_FILE"
  sed -i "s|^JUPYTER_TOKEN=.*|JUPYTER_TOKEN=$TOKEN|" "$ENV_FILE"
fi

if ! grep -q '^JUPYTER_BASE_URL=' "$ENV_FILE"; then
  echo "JUPYTER_BASE_URL=/leadlag-lab/lab/" >> "$ENV_FILE"
fi

echo "[+] Applying ownership and permissions"
chown -R "$JUPYTER_USER:$JUPYTER_USER" \
  "$PROJECT/notebooks" \
  "$PROJECT/data/jupyter_home" \
  "$PROJECT/data/strategies" \
  "$PROJECT/data/backtest"
chown "root:$JUPYTER_USER" "$PROJECT/data"

chmod 750 "$PROJECT/notebooks"
chmod 775 "$PROJECT/data"
chmod 775 "$PROJECT/data/strategies"
chmod 775 "$PROJECT/data/backtest"

chown "root:$JUPYTER_USER" "$ENV_FILE"
chmod 640 "$ENV_FILE"

echo ""
echo "[ok] Setup complete."
echo "Next steps:"
echo "  1) cp $PROJECT/deploy/leadlag-lab-jupyter.service /etc/systemd/system/"
echo "  2) systemctl daemon-reload"
echo "  3) systemctl enable --now leadlag-lab-jupyter"
echo "  4) journalctl -u leadlag-lab-jupyter -n 50 --no-pager"
echo "  5) bash $PROJECT/scripts/smoke_jupyter.sh"
