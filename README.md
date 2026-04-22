# leadlag-lab

Local lead-lag crypto trading platform — collector, batch analysis, backtest, paper trading, FastAPI UI. Python package + 8 HTML screens served by a single uvicorn process on `:8899`.

Full technical spec in [plan.md](plan.md); documentation order in [00_DOCS_PIPELINE.md](00_DOCS_PIPELINE.md); running implementation log in [90_PROGRESS_LOG.md](90_PROGRESS_LOG.md).

## Layout

```
leadlag-lab/
├── leadlag/                package (venues, collector, analysis,
│                           strategy, backtest, realtime, paper, monitor, api, ui)
├── config/
│   ├── venues.yaml         12-venue registry
│   ├── jupyter.env         Jupyter token + port (git-ignored, создаётся setup_jupyter.sh)
│   └── jupyter.env.example шаблон для jupyter.env
├── data/                   runtime data (ticks/, bbo/, analyses/, strategies/,
│                           backtest/, paper/, jupyter_home/, .system_history.jsonl, ...)
├── deploy/                 systemd units + nginx snippets
│   ├── leadlag-lab.service
│   ├── leadlag-monitor.service
│   ├── leadlag-lab-jupyter.service
│   ├── nginx-leadlag-lab.conf
│   └── nginx-leadlag-lab-jupyter.conf
├── scripts/
│   ├── setup_jupyter.sh    первоначальная настройка JupyterLab
│   └── smoke_jupyter.sh    smoke-тест сервиса
├── notebooks/              Jupyter notebooks
├── index.html              VYV-dashboard gateway (redirects to /leadlag-lab/)
├── pyproject.toml
├── 00_DOCS_PIPELINE.md     ordered documentation map
├── plan.md                 authoritative spec (2185 lines)
├── 05_PRE_FLUTTER_STABILIZATION_PLAN.md
│                           active pre-Flutter stabilization plan
├── 06_FLUTTER_UI_REWORK_PLAN.md
│                           Flutter UI migration plan
└── 90_PROGRESS_LOG.md      session-by-session build log
```

---

## Запуск с нуля (первый раз)

### 1. Установить пакет в venv

```bash
/root/projects/leadlag/.venv/bin/pip install -e /root/projects/leadlag-lab/
```

Зависимости (ставятся автоматически): numpy, pandas, pyarrow, websockets, pyyaml, fastapi, uvicorn, psutil, tqdm.

### 2. Настроить JupyterLab

```bash
sudo bash /root/projects/leadlag-lab/scripts/setup_jupyter.sh
```

Скрипт создаёт системного пользователя `leadlag-lab`, директории и генерирует случайный токен в `config/jupyter.env`.

### 3. Скопировать systemd-юниты

```bash
cp /root/projects/leadlag-lab/deploy/leadlag-lab.service         /etc/systemd/system/
cp /root/projects/leadlag-lab/deploy/leadlag-monitor.service     /etc/systemd/system/
cp /root/projects/leadlag-lab/deploy/leadlag-lab-jupyter.service /etc/systemd/system/
systemctl daemon-reload
```

### 4. Включить и запустить сервисы

```bash
systemctl enable --now leadlag-lab leadlag-monitor leadlag-lab-jupyter
```

Что запускается:
- **leadlag-lab** — FastAPI (uvicorn) на `127.0.0.1:8899`
- **leadlag-monitor** — демон, пишет `data/.system_history.jsonl` (каждые 5с) и `data/.ping_cache.json` (каждые 10с)
- **leadlag-lab-jupyter** — JupyterLab на `127.0.0.1:8889`, токен из `config/jupyter.env`

Важно:
- отдельного `leadlag-collector.service` для `leadlag-lab` нет;
- collector в этой архитектуре запускается из API через `POST /api/collector/start` как subprocess, а не как постоянный systemd daemon.

### 5. Добавить nginx location blocks

**Jupyter snippet** (скопировать в `/etc/nginx/snippets/`):

```bash
cp /root/projects/leadlag-lab/deploy/nginx-leadlag-lab-jupyter.conf \
   /etc/nginx/snippets/leadlag-lab-jupyter-location.conf
```

Открыть `/etc/nginx/sites-enabled/vyv_sites` и добавить include **перед** блоком `location ^~ /leadlag-lab/`:

```nginx
# leadlag-lab JupyterLab (:8889) — должен быть ПЕРЕД /leadlag-lab/
include /etc/nginx/snippets/leadlag-lab-jupyter-location.conf;
```

**Основной UI** (`/leadlag-lab/`) уже должен быть в конфиге. Если нет — вставить перед блоком `location ~ ^/(?!api/)...`:

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

### 6. Проверить

```bash
# Локально API:
curl -s http://127.0.0.1:8899/api/system/stats | head -5

# Через nginx:
curl -sk https://vyv.ftp.sh/leadlag-lab/ -w "\nHTTP %{http_code}\n"

# Статус сервисов:
systemctl status leadlag-lab leadlag-monitor leadlag-lab-jupyter

# Логи:
journalctl -u leadlag-lab -n 50
journalctl -u leadlag-monitor -n 20
journalctl -u leadlag-lab-jupyter -n 50

# Smoke-тест Jupyter:
bash /root/projects/leadlag-lab/scripts/smoke_jupyter.sh
```

Открыть в браузере:
- UI: `https://vyv.ftp.sh/leadlag-lab/`
- JupyterLab: `https://vyv.ftp.sh/leadlag-lab/lab/` (токен в `config/jupyter.env`)

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

### Перезапуск всего runtime этой репы

```bash
systemctl restart leadlag-lab leadlag-monitor leadlag-lab-jupyter
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

### Operational note: collector runtime

На 2026-04-22 внешний `leadlag-collector.service`, который смотрел в `/root/projects/leadlag`, был отключён и удалён из systemd-конфигурации, потому что он противоречил архитектуре `leadlag-lab` и тащил старый runtime/status-контракт.

Теперь правило одно:
- `leadlag-lab`, `leadlag-monitor`, `leadlag-lab-jupyter` живут как systemd services;
- collector для `leadlag-lab` живёт только как subprocess, который стартует из API;
- `GET /api/collector/status` без файла `data/.collector_status.json` честно возвращает `{"running": false, ...}` без legacy-полей.

Быстрая проверка после рестарта:

```bash
curl -s http://127.0.0.1:8899/api/analyses
curl -s http://127.0.0.1:8899/api/collector/status
```

Если когда-нибудь понадобится отдельный daemon-collector, его нужно проектировать заново уже под контракт `analysis/recording`, а не возвращать старый unit из другого checkout.

### Перезапуск JupyterLab

```bash
systemctl restart leadlag-lab-jupyter
```

### После изменений в systemd unit-файле Jupyter

```bash
cp /root/projects/leadlag-lab/deploy/leadlag-lab-jupyter.service /etc/systemd/system/
systemctl daemon-reload
systemctl restart leadlag-lab-jupyter
```

### Полная остановка

```bash
systemctl stop leadlag-lab leadlag-monitor leadlag-lab-jupyter
```

### Полный перезапуск с нуля (если всё сломалось)

```bash
systemctl stop leadlag-lab leadlag-monitor leadlag-lab-jupyter
/root/projects/leadlag/.venv/bin/pip install -e /root/projects/leadlag-lab/
systemctl daemon-reload
systemctl start leadlag-lab leadlag-monitor leadlag-lab-jupyter
systemctl status leadlag-lab leadlag-monitor leadlag-lab-jupyter
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

# Построить analysis из raw parquet (batch pipeline)
/root/projects/leadlag/.venv/bin/python -c "
from leadlag.session import Analysis
s = Analysis.build_from_raw('20260411_164417', 'data/ticks', 'data/bbo')
s.save()
print(s.analysis_id, s.events.count)
"

# Запустить бектест из CLI
/root/projects/leadlag/.venv/bin/python -c "
from leadlag import load_analysis, load_strategy, run_backtest
strat = load_strategy('data/strategies/lighter_c_v1.py')
analysis = load_analysis('20260411_164417_a3f2c1b0')
bt = run_backtest(strat, analysis).save()
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
| Analyses          | `data/analyses/{collection_id}_{params_hash}/`   |
| Бектесты          | `data/backtest/{strategy}_{timestamp}/`          |
| Paper trading     | `data/paper/{strategy}/`                         |
| Статус-файлы      | `data/.collector_status.json`, `.paper_status.json` |
| Systemd юниты     | `deploy/leadlag-lab.service`, `deploy/leadlag-monitor.service`, `deploy/leadlag-lab-jupyter.service` |
| Nginx snippets    | `deploy/nginx-leadlag-lab.conf`, `deploy/nginx-leadlag-lab-jupyter.conf` |
| Jupyter порт      | `http://127.0.0.1:8889`                          |
| Jupyter URL       | `https://vyv.ftp.sh/leadlag-lab/lab/`            |
| Jupyter токен     | `config/jupyter.env` (JUPYTER_TOKEN)             |
| Jupyter setup     | `scripts/setup_jupyter.sh`                       |
| Jupyter smoke     | `scripts/smoke_jupyter.sh`                       |
| Логи API          | `journalctl -u leadlag-lab -f`                   |
| Логи монитора     | `journalctl -u leadlag-monitor -f`               |
| Логи Jupyter      | `journalctl -u leadlag-lab-jupyter -f`           |

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
