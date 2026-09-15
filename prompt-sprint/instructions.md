# PromptSprint - final execution

I copy `.env.example` to `.env`, put the provider key in `.env` only, and set `provider` / `model` in `config.json` before I run.

When I want scoring in the same pass, I set `"scoring": true` and `"judge_model"` (OpenRouter id with the `openrouter/` prefix). The judge does not have to be in `available_models`. If I want to generate first and score later, I leave `"scoring": false` and run `python score.py` afterwards.

## Windows (PowerShell)

I work from the `prompt-sprint` folder:

```
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

I edit `.env` and `config.json`, then:

```
python test\connection.py
python main.py
```

If activation is blocked, I run:

```
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

then activate again.

Flags I use:

```
python main.py --task-id task_001 --overwrite
python main.py --provider openai --model openai/gpt-4o-mini --overwrite
python main.py --no-scoring
python score.py
python score.py --task-id task_001 --overwrite
```

I empty previous results before a fresh run with:

```
Remove-Item responses\*.json -ErrorAction SilentlyContinue
```

For the web UI I use two terminals. First the API:

```
uvicorn api:app --reload --port 8000 --reload-exclude ".venv" --reload-exclude "frontend" --reload-exclude "responses"
```

Then the frontend:

```
cd frontend
npm install
npm run dev
```

I open `http://localhost:5173`.

## EC2 Ubuntu

I terminate the instance when I am done so I am not billed for idle time. I launch a new Ubuntu AMI whenever I want to run again. Nothing in this repo needs a long-lived machine.

### 1. How I launch the instance

1. AMI: Ubuntu 24.04 LTS (or 22.04).
2. Type: `t3.small` or larger (Node + Python + a model run).
3. Storage: 20 GB is enough.
4. Key pair: the `.pem` I use with PuTTY (I convert it with PuTTYgen if I need a `.ppk`).
5. Security group inbound:
  - **22** from my IP (SSH / PuTTY).
  - I do not open 8000 or 5173 to `0.0.0.0/0`. I reach the UI through SSH tunnels (below).
6. Outbound **HTTPS (443)** must be allowed so LiteLLM can reach OpenRouter or other providers.



### 2. How I use PuTTY (one terminal)

I do not open `http://<ec2-public-ip>:5173`. Vite and the API listen only on the instance loopback. I reach them from my laptop with SSH tunnels, then I browse **localhost**.

**SSH**

- Host Name: `ubuntu@<ec2-ip>` (or `ec2-ip` with username `ubuntu`)
- Connection → SSH → Auth → Credentials: my `.ppk`

**Tunnels — I add these before I click Open**

Connection → SSH → Tunnels. For each row I leave **Local** selected, type Source port and Destination, click **Add**:


| Source port (laptop) | Destination (instance) |
| -------------------- | ---------------------- |
| `5173`               | `127.0.0.1:5173`       |
| `8000`               | `127.0.0.1:8000`       |


I should see `L5173` and `L8000` in the forwarded-ports list. I save the session, then Open. If I already had a session open without tunnels, I close it and Open again, tunnels only attach at connect time.

If I am only using the CLI, I skip the tunnels.

Equivalent OpenSSH:

```
ssh -i my-key.pem -L 5173:127.0.0.1:5173 -L 8000:127.0.0.1:8000 ubuntu@<ec2-ip>
```



### 3. How I set up a new instance

```
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv ca-certificates git nano tmux nodejs npm
sudo update-ca-certificates
```

If `node -v` is below 18, I install Node 22 and then continue:

```
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs
```

I clone the repo:

```
git clone <repo-url>
cd prompt-sprint
```

If the repo is already on the instance:

```
cd prompt-sprint
git pull
```

Python env:

```
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
nano .env
nano config.json
```

I set `OPENROUTER_API_KEY` (and `OPENROUTER_API_BASE` if I use OpenRouter). I confirm `provider` and `model` in `config.json`. For scoring I set `"scoring": true` and `"judge_model"` (for example `openrouter/inclusionai/ling-3.0-flash-fin-v1:free`).

Frontend packages (once per instance, or after `package.json` changes):

```
cd frontend
npm install
cd ..
```

I ping the model when I want a quick check:

```
source .venv/bin/activate
python3 test/connection.py
```



### 4. How I run the API and frontend in one PuTTY window

PuTTY gives me a single shell. I use tmux so both processes stay up and I can switch between them.

I start a session:

```
cd ~/prompt-sprint
tmux new -s promptsprint
```

**Window 0 — API**

```
source .venv/bin/activate
uvicorn api:app --host 127.0.0.1 --port 8000 --reload --reload-exclude ".venv" --reload-exclude "frontend" --reload-exclude "responses"
```

**Window 1 — frontend** (new window: `Ctrl+b` then `c`)

```
cd ~/prompt-sprint/frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

I switch windows with `Ctrl+b` then `0` or `1`. If I want a split instead: `Ctrl+b` then `%` (vertical) or `"` (horizontal), then `Ctrl+b` then arrow keys.

### 5. How I open the UI on my laptop

Vite and the API stay on EC2. My browser stays on the laptop. The PuTTY tunnels make instance ports look local.

1. API is running in tmux window 0 (port 8000).
2. Frontend is running in tmux window 1 (port 5173). Vite should print `Local: http://localhost:5173/`.
3. The PuTTY session that is still connected has both tunnels (I must not have closed that window).
4. On my **laptop** I open [http://localhost:5173](http://localhost:5173) — not the EC2 public DNS or IP.

Config, Tasks, and Results load through the 5173 tunnel. Run and Score need the 8000 tunnel because the page calls `http://127.0.0.1:8000` from my browser.

If the page does not load:

- I used `http://<ec2-ip>:5173` instead of `http://localhost:5173`.
- PuTTY was opened before I added the tunnels — I save tunnels and reconnect.
- Something on my laptop already uses 5173 or 8000 — I stop that process or pick other source ports in PuTTY (then I browse that source port).
- Vite or uvicorn is not running in tmux.

I detach and leave both running with `Ctrl+b` then `d`. After a new PuTTY login I reattach with:

```
tmux attach -t promptsprint
```

I list sessions with `tmux ls`. When I am done I kill the session:

```
tmux kill-session -t promptsprint
```

Then I terminate the EC2 instance.

### 6. How I run a CLI-only batch (no UI)

```
tmux new -s promptsprint
cd ~/prompt-sprint
source .venv/bin/activate
python3 main.py
```

I detach with `Ctrl+b` then `d`. I reattach with `tmux attach -t promptsprint`.

Flags I use:

```
python3 main.py --task-id task_001 --overwrite
python3 main.py --provider openai --model openai/gpt-4o-mini --overwrite
python3 main.py --no-scoring
python3 score.py
python3 score.py --task-id task_001 --overwrite
```

I empty previous results before a fresh run with:

```
rm -f responses/*.json
```

If I see `CERTIFICATE_VERIFY_FAILED`:

```
sudo apt-get install -y ca-certificates
sudo update-ca-certificates
source .venv/bin/activate
pip install certifi truststore
```



## Expected output

```
responses/
├── task_001.json
├── task_002.json
├── task_003.json
├── task_004.json
├── task_005.json
├── task_006.json
├── task_007.json
├── task_008.json
├── task_009.json
├── task_010.json
└── summary.json
```

Each `task_*.json` includes `"score"` (`0.0`–`10.0`, or `null` if scoring is off or the judge failed). `summary.json` includes `"score_stats"` (`mean`, `median`, `mode`, `max`, `median_range`, `p95`, `std_dev`) when scoring produced at least one value; otherwise `"score_stats"` is `null`.