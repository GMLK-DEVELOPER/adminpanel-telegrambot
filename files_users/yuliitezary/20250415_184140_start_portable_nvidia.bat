@echo off
set pypath=home = %~dp0python
set venvpath=_ENV=%~dp0venv
if exist venv (powershell -command "$text = (gc venv\pyvenv.cfg) -replace 'home = .*', $env:pypath; $Utf8NoBomEncoding = New-Object System.Text.UTF8Encoding($False);[System.IO.File]::WriteAllLines('venv\pyvenv.cfg', $text, $Utf8NoBomEncoding);$text = (gc venv\scripts\activate.bat) -replace '_ENV=.*', $env:venvpath; $Utf8NoBomEncoding = New-Object System.Text.UTF8Encoding($False);[System.IO.File]::WriteAllLines('venv\scripts\activate.bat', $text, $Utf8NoBomEncoding);")

set appdata=%~dp0tmp
set userprofile=%~dp0tmp
set temp=%~dp0tmp
REM set HF_HUB_OFFLINE=True
set PATH=%PATH%;git\cmd;python;venv\scripts;ffmpeg;venv\Lib\site-packages\torch\lib;cuda;cuda\lib;cuda\bin;tensorrt;tensorrt\bin;tensorrt\lib

set CUDA_MODULE_LOADING=LAZY
set CUDA_PATH=venv\Lib\site-packages\torch\lib

call venv\Scripts\activate.bat
cd instantid
python gradio_demo\app_lcm.py --pretrained_model_name_or_path "./models/zavychromaxl_v40-8-bit.safetensors"
pause

REM Упаковано и собрано телеграм каналом Neurogen News: https://t.me/neurogen_news
