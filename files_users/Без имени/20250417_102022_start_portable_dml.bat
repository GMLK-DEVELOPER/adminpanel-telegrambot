@echo off
set pypath=home = %~dp0python_310
set venvpath=_ENV=%~dp0venv_dml
if exist venv_dml (powershell -command "$text = (gc venv_dml\pyvenv.cfg) -replace 'home = .*', $env:pypath; $Utf8NoBomEncoding = New-Object System.Text.UTF8Encoding($False);[System.IO.File]::WriteAllLines('venv_dml\pyvenv.cfg', $text, $Utf8NoBomEncoding);$text = (gc venv_dml\scripts\activate.bat) -replace '_ENV=.*', $env:venvpath; $Utf8NoBomEncoding = New-Object System.Text.UTF8Encoding($False);[System.IO.File]::WriteAllLines('venv_dml\scripts\activate.bat', $text, $Utf8NoBomEncoding);")

set appdata=%~dp0tmp
set userprofile=%~dp0tmp
set temp=%~dp0tmp
REM set HF_HUB_OFFLINE=True
set PATH=%PATH%;git\cmd;python;venv_dml\scripts;ffmpeg

call venv_dml\Scripts\activate.bat
cd instantid
python gradio_demo\app_lcm_dml.py --pretrained_model_name_or_path "./models/zavychromaxl_v40.safetensors"
pause

REM Упаковано и собрано телеграм каналом Neurogen News: https://t.me/neurogen_news
