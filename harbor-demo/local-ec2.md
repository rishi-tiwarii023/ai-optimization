# Running harbor-demo on an EC2 instance

## What happened locally

`OpenHands.bat` is a Windows helper used to start the OpenHands Docker UI. The experiments call the headless CLI with `openhands --headless --task ...`.

It pulls from GHCR and starts the official OpenHands app:

- `ghcr.io/openhands/openhands:latest`
- `ghcr.io/openhands/agent-server:1.27.0-python`

The 403 error occurred because `ghcr.io/openhands/openhands` was not publicly accessible. I logged out and retried the pull:

```powershell
docker logout ghcr.io
.\openhands.bat pull
```

The bytes still come from GitHub Container Registry’s CDN. Docker Desktop on this machine was using the containerd image store, which commonly causes the `httpReadSeeker` 403 issue on signed blob URLs.

Fix applied:

1. Open Docker Desktop → **Settings** → **General**.
2. Uncheck **Use containerd for pulling and storing images**.
3. Apply, and wait for Docker to restart.
4. From `harbor-demo/`:

```powershell
.\openhands.bat pull
```

The network was blocking `pkg-containers.githubusercontent.com` because of corporate proxy restrictions. The image catalog was reachable, but the layer downloads were blocked.

Docker image pulls for the local development tool, OpenHands, were blocked by Zscaler. The registry catalog was reachable, but layer downloads failed with a 403 error and the Zscaler page showed D22: “Sorry, you don’t have permission to visit this site.”

Allowlist request for HTTPS/port 443:

- `pkg-containers.githubusercontent.com`
- `ghcr.io`
- `docker.openhands.dev`

## Cleanup performed locally

```powershell
pip freeze | Where-Object { $_ -and $_ -notmatch '^(pip|setuptools|wheel)==' -and $_ -notmatch '^\s*#' } | Set-Content $env:TEMP\venv-all.txt
pip uninstall -y -r $env:TEMP\venv-all.txt
pip install -r requirements.txt
pip freeze
```

## On EC2

### Setup

The five models listed in `src/experiments/models.yaml` are called through a local LiteLLM/Laguna proxy (`LLM_MODEL=litellm_proxy/...`) using `LAGUNA_API_ENDPOINT` and `LAGUNA_PROXY_URL` so HTTP is not blocked by corporate firewalls. The EC2 instance only runs Python, Docker Compose for task verification, and the OpenHands CLI.

### Specifications

1. AMI — Ubuntu Server 24.04 LTS, x86_64 (amd64)
2. Instance type — t3.xlarge (4 vCPU, 16 GiB)
3. Root volume — 80 GB gp3
4. Security group — SSH 22 from my IP (currently from anywhere)

### SSH access using PuTTY

- IP: `65.1.94.2`
- Login user: `ubuntu`

### Preparing the Ubuntu instance

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git python3.12 python3.12-venv python3-pip

# Docker Engine + Compose plugin
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker "$USER"
newgrp docker
# or log out and back in
docker version
docker compose version
```

Docker and Docker Compose were verified after installation.

### Cloning the repository and setting up the virtual environment

```bash
git clone https://github.com/rishi-tiwarii023/ai-optimization.git
cd ai-optimization
cd harbor-demo
python3.12 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

The repository was cloned, the project directory was opened, and the Python virtual environment was created and activated.

### Configuring secrets

```bash
cp .env.example .env
nano .env
# Paste the required values, then press Ctrl+O to save and Ctrl+X to exit.
```

### Pre-pulling images used by nested Docker

```bash
docker pull docker.openhands.dev/openhands/openhands:1.8
docker pull ghcr.io/openhands/agent-server:1.26.0-python
```

### Warming the task image

```bash
export TRIAL_ID=warmup
docker compose -f datasets/internal-core/health-api/environment/docker-compose.yml build
```

### Verifying and running the full experiment

```bash
python -m pytest -q
python -m arms.cli.run_experiment
```

### Serving the dashboard

```bash
source .venv/bin/activate
ls -l reports/index.html
python -m http.server 8080 --bind 0.0.0.0 --directory reports
```

Download the dashboard from the folder where the key is stored:

```bash
scp -i openhands-ec2.pem ubuntu@65.1.94.2:~/ai-optimization/harbor-demo/reports/index.html .
```

### Deleting artifacts after failed runs

```bash
rm -rf ./artifacts/run_* ./artefacts ./artifacts/metrics.json
```

### Installing the OpenHands CLI on EC2

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"
uv tool install openhands --python 3.12
export PATH="$HOME/.local/bin:$PATH"
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc

# Confirm
openhands --version
# which works but the experiment still cannot see it
export OPENHANDS_BIN="$(which openhands)"
# persist for later SSH sessions
echo "export OPENHANDS_BIN=$(which openhands)" >> ~/.bashrc

# rerun from same shell
source .venv/bin/activate
export PATH="$HOME/.local/bin:$PATH"
python -m arms.cli.run_experiment

# If which openhands is empty, print uv’s bin dir and put that on PATH instead:
uv tool dir
ls "$(uv tool dir --bin 2>/dev/null || echo "$HOME/.local/share/uv/tools")"
export PATH="$(dirname "$(find "$HOME" -name openhands -type f 2>/dev/null | head -n 1)"):$PATH"
export OPENHANDS_BIN="$(which openhands)"
python -m arms.cli.run_experiment

# Keep path after we disconnect
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On EC2 Linux, I placed the OpenHands CLI on the `PATH` using `OPENHANDS_BIN` and ran the Python experiment. The Windows batch file is not required on EC2.
