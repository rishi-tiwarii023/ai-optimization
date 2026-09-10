@echo off
setlocal EnableExtensions

if /I "%~1"=="--help" goto :help
if /I "%~1"=="-h" goto :help
if /I "%~1"=="/?" goto :help

where docker >nul 2>&1
if errorlevel 1 (
  echo docker is not on PATH.
  exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
  echo Docker daemon is not running.
  exit /b 1
)

if not defined OPENHANDS_IMAGE set "OPENHANDS_IMAGE=docker.openhands.dev/openhands/openhands:1.8"
if not defined AGENT_SERVER_IMAGE_REPOSITORY set "AGENT_SERVER_IMAGE_REPOSITORY=ghcr.io/openhands/agent-server"
if not defined AGENT_SERVER_IMAGE_TAG set "AGENT_SERVER_IMAGE_TAG=1.26.0-python"
if not defined OPENHANDS_PORT set "OPENHANDS_PORT=3000"
if not defined OPENHANDS_NAME set "OPENHANDS_NAME=harbor-demo-openhands"
if not defined OPENHANDS_WORKDIR set "OPENHANDS_WORKDIR=%~dp0"
if "%OPENHANDS_WORKDIR:~-1%"=="\" set "OPENHANDS_WORKDIR=%OPENHANDS_WORKDIR:~0,-1%"

set "CONFIG_DIR=%USERPROFILE%\.openhands"
if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%" >nul 2>&1

set "ENV_FILE=%~dp0.env"
set "ENV_FILE_FLAG="
set "ENV_FILE_PATH="
if exist "%ENV_FILE%" (
  set "ENV_FILE_FLAG=--env-file"
  set "ENV_FILE_PATH=%ENV_FILE%"
)

set "SANDBOX_VOLUMES=%OPENHANDS_WORKDIR:\=/%:/workspace:rw"
set "AGENT_SERVER_IMAGE=%AGENT_SERVER_IMAGE_REPOSITORY%:%AGENT_SERVER_IMAGE_TAG%"

if /I "%~1"=="pull" goto :pull_only

call :pull_images
if errorlevel 1 exit /b 1

docker rm -f "%OPENHANDS_NAME%" >nul 2>&1
echo http://127.0.0.1:%OPENHANDS_PORT%
docker run --rm -it --name "%OPENHANDS_NAME%" --add-host host.docker.internal:host-gateway -p "%OPENHANDS_PORT%:3000" -e AGENT_SERVER_IMAGE_REPOSITORY="%AGENT_SERVER_IMAGE_REPOSITORY%" -e AGENT_SERVER_IMAGE_TAG="%AGENT_SERVER_IMAGE_TAG%" -e LOG_ALL_EVENTS=true -e SANDBOX_VOLUMES="%SANDBOX_VOLUMES%" -v /var/run/docker.sock:/var/run/docker.sock -v "%CONFIG_DIR%:/.openhands" %ENV_FILE_FLAG% %ENV_FILE_PATH% "%OPENHANDS_IMAGE%"
exit /b %ERRORLEVEL%

:pull_only
call :pull_images
exit /b %ERRORLEVEL%

:pull_images
docker pull "%OPENHANDS_IMAGE%"
if errorlevel 1 exit /b 1
docker pull "%AGENT_SERVER_IMAGE%"
exit /b %ERRORLEVEL%

:help
echo .\openhands.bat
echo .\openhands.bat pull
exit /b 0
