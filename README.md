# leadlag-lab

Local lead-lag crypto trading platform — collector, batch analysis, backtest, paper trading, FastAPI UI. Python package + 8 HTML screens served by a single uvicorn process on `:8899`.

Full technical spec in [plan.md](plan.md); running implementation log in [PROGRESS.md](PROGRESS.md).

## Layout

```
leadlag-lab/
├── leadlag/                package (venues, collector, analysis, session,
│                           strategy, backtest, realtime, paper, monitor, api, ui)
├── config/venues.yaml      12-venue registry
├── data/                   runtime data (ticks/, bbo/, sessions/, strategies/,
│                           backtest/, paper/, .system_history.jsonl, ...)
├── deploy/                 systemd units + nginx snippet
├── index.html              VYV-dashboard gateway (redirects to /leadlag-lab/)
├── pyproject.toml
├── plan.md                 authoritative spec (2185 lines)
└── PROGRESS.md             session-by-session build log
```

---

## Запуск с нуля (первый раз)

### 1. Установить пакет в venv

```bash
/root/projects/leadlag/.venv/bin/pip install -e /root/projects/leadlag-lab/
```

Зависимости (ставятся автоматически): numpy, pandas, pyarrow, websockets, pyyaml, fastapi, uvicorn, psutil, tqdm.

### 2. Скопировать systemd-юниты

```bash
cp /root/projects/leadlag-lab/deploy/leadlag-lab.service     /etc/systemd/system/
cp /root/projects/leadlag-lab/deploy/leadlag-monitor.service /etc/systemd/system/
systemctl daemon-reload
```

### 3. Включить и запустить сервисы

```bash
systemctl enable --now leadlag-lab leadlag-monitor
```

Что запускается:
- **leadlag-lab** — FastAPI (uvicorn) на `127.0.0.1:8899`
- **leadlag-monitor** — демон, пишет `data/.system_history.jsonl` (каждые 5с) и `data/.ping_cache.json` (каждые 10с)

### 4. Добавить nginx location block

Открыть `/etc/nginx/sites-enabled/vyv_sites` и вставить **перед** блоком `location ~ ^/(?!api/)...`:

```nginx
location ^~ /leadlag-lab/ {
    proxy_pass http://127.0.0.1:8899/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    add_header Cache-Control "no-cache, no-store, must-revalidate";
    add_header Pragma "no-cache";
}
```

Применить:

```bash
nginx -t && systemctl reload nginx
```

### 5. Проверить

```bash
# Локально:
curl -s http://127.0.0.1:8899/api/system/stats | head -5

# Через nginx:
curl -sk https://vyv.ftp.sh/leadlag-lab/ -w "\nHTTP %{http_code}\n"

# Статус сервисов:
systemctl status leadlag-lab leadlag-monitor

# Логи:
journalctl -u leadlag-lab -n 50
journalctl -u leadlag-monitor -n 20
```

Открыть в браузере: `https://vyv.ftp.sh/leadlag-lab/`

---

## Перезапуск

### Перезапуск после изменений в коде Python

```bash
systemctl restart leadlag-lab
```

Пакет установлен в editable mode (`pip install -e`), поэтому повторный `pip install` **не нужен** — systemctl restart подхватит изменения.

### Перезапуск монитора

```bash
systemctl restart leadlag-monitor
```

### Перезапуск обоих сервисов

```bash
systemctl restart leadlag-lab leadlag-monitor
```

### После изменений в HTML/JS/CSS (без Python)

Перезапуск **не нужен** — uvicorn раздаёт статику из `leadlag/ui/` напрямую с диска. Достаточно обновить страницу в браузере (Ctrl+Shift+R — hard refresh, т.к. стоит `Cache-Control: no-cache`).

### После изменений в nginx конфиге

```bash
nginx -t && systemctl reload nginx
```

### После изменений в systemd unit-файлах

```bash
cp /root/projects/leadlag-lab/deploy/leadlag-lab.service     /etc/systemd/system/
cp /root/projects/leadlag-lab/deploy/leadlag-monitor.service /etc/systemd/system/
systemctl daemon-reload
systemctl restart leadlag-lab leadlag-monitor
```

### Полная остановка

```bash
systemctl stop leadlag-lab leadlag-monitor
```

### Полный перезапуск с нуля (если всё сломалось)

```bash
systemctl stop leadlag-lab leadlag-monitor
/root/projects/leadlag/.venv/bin/pip install -e /root/projects/leadlag-lab/
systemctl daemon-reload
systemctl start leadlag-lab leadlag-monitor
systemctl status leadlag-lab leadlag-monitor
```

---

## Запуск без nginx (локально)

Если nginx не нужен — можно запустить напрямую:

```bash
cd /root/projects/leadlag-lab
/root/projects/leadlag/.venv/bin/python -m leadlag.api              # UI на http://127.0.0.1:8899
/root/projects/leadlag/.venv/bin/python -m leadlag.monitor.daemon   # в отдельном терминале
```

Открыть `http://127.0.0.1:8899/` (редирект на dashboard).

---

## One-shot commands

```bash
# Коллектор (пишет data/ticks/YYYY-MM-DD/*.parquet + data/bbo/*)
/root/projects/leadlag/.venv/bin/python -m leadlag.collector --duration 3600

# Построить сессию из parquet (batch pipeline)
/root/projects/leadlag/.venv/bin/python -c "
from leadlag.session import Session
s = Session.build_from_raw('20260411_164417', 'data/ticks', 'data/bbo')
s.save()
print(s.session_id, s.events.count)
"

# Запустить бектест из CLI
/root/projects/leadlag/.venv/bin/python -c "
from leadlag import load_session, load_strategy, run_backtest
strat = load_strategy('data/strategies/lighter_c_v1.py')
sess  = load_session('20260411_164417_a3f2c1b0')
bt = run_backtest(strat, sess).save()
print(bt)
"
```

---

## Paths reference

| Что               | Где                                              |
|-------------------|--------------------------------------------------|
| Venv              | `/root/projects/leadlag/.venv/`                  |
| API порт          | `http://127.0.0.1:8899`                          |
| Публичный URL     | `https://vyv.ftp.sh/leadlag-lab/`                |
| Dashboard UI      | `/leadlag-lab/ui/dashboard.html`                 |
| Стратегии         | `data/strategies/*.py`                           |
| Сессии            | `data/sessions/{collection_id}_{params_hash}/`   |
| Бектесты          | `data/backtest/{strategy}_{timestamp}/`          |
| Paper trading     | `data/paper/{strategy}/`                         |
| Статус-файлы      | `data/.collector_status.json`, `.paper_status.json` |
| Systemd юниты     | `deploy/leadlag-lab.service`, `deploy/leadlag-monitor.service` |
| Nginx snippet     | `deploy/nginx-leadlag-lab.conf`                  |
| Логи API          | `journalctl -u leadlag-lab -f`                   |
| Логи монитора     | `journalctl -u leadlag-monitor -f`               |

---

## Phase status

| Phase                                  | Status        |
|----------------------------------------|---------------|
| 1. Python package scaffold             | done          |
| 2. Backtest engine (slip/spread/SL/TP) | done          |
| 3. FastAPI + UI                        | done          |
| 4. Dashboard + Collector UI + Quality  | done          |
| 5. Realtime + Paper trader             | done          |
| 6. Real trading                        | deferred      |

Acceptance criterion `s.events.filter(signal='C').count == 229` is still pending — the 12-hour reference parquet dataset has not yet been collected in this tree.
