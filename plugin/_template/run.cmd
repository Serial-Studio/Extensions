@echo off
cd /d "%~dp0"

if not exist ".venv" python -m venv .venv
call .venv\Scripts\activate.bat
python -c "import grpc" 2>nul || pip install --quiet grpcio protobuf

python plugin.py %*
