# PromptSprint — final execution



Copy `.env.example` to `.env`, put the provider key in `.env` only, and set `provider` / `model` in `config.json` before you run.



## Windows (PowerShell)



From the `prompt-sprint` folder:



```

python -m venv .venv

.venv\Scripts\Activate.ps1

pip install -r requirements.txt

copy .env.example .env

```



Edit `.env` and `config.json`, then:



```

python test\connection.py

python main.py

```



If activation is blocked, run:



```

Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

```



then activate again.



Optional flags:



```

python main.py --task-id task_001 --overwrite

python main.py --provider openai --model openai/gpt-4o-mini --overwrite

```
Empty previous results before a fresh run:

```
Remove-Item responses\*.json -ErrorAction SilentlyContinue
```




## EC2 Ubuntu



Use an Ubuntu AMI. Open inbound **22** for SSH. Outbound **HTTPS (443)** must be allowed so LiteLLM can reach OpenRouter or other providers. No extra inbound ports are required for this CLI.



SSH in:



```

ssh -i your-key.pem ubuntu@<ec2-public-dns-or-ip>

```



Install Python and helpers:



```

sudo apt-get update

sudo apt-get install -y python3 python3-pip python3-venv ca-certificates git nano tmux

```



Go to the project (clone first if the repo is not already on the instance):



```

cd prompt-sprint

```



Create the venv and install dependencies:



```

python3 -m venv .venv

source .venv/bin/activate

pip install --upgrade pip

pip install -r requirements.txt

cp .env.example .env

nano .env

nano config.json

```

Set `OPENROUTER_API_KEY` (and `OPENROUTER_API_BASE` if you use OpenRouter). Confirm `provider` and `model` in `config.json`.

Ping, then run the batch:

```
python3 test/connection.py
python3 main.py
```

Optional flags:

```
python3 main.py --task-id task_001 --overwrite
python3 main.py --provider openai --model openai/gpt-4o-mini --overwrite
```

Keep a long run alive after you disconnect SSH:

```
tmux new -s promptsprint
source .venv/bin/activate
python3 main.py
```

Detach with `Ctrl+b` then `d`. Reattach with `tmux attach -t promptsprint`.

If you see `CERTIFICATE_VERIFY_FAILED`:

```
sudo apt-get install -y ca-certificates
sudo update-ca-certificates
```

Empty previous results before a fresh run:

```
rm -f responses/*.json
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
