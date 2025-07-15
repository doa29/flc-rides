@echo off
IF NOT EXIST venv (
    python -m venv venv
)
CALL venv\Scripts\activate
pip install -r requirements.txt
python downloader.py %*