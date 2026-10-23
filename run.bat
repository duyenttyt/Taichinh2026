@echo off
title HomeFinance - Quan Ly Tai Chinh Ca Nhan Gia Dinh
chcp 65001 > nul
cls

echo ======================================================================
echo    UNG DUNG QUAN LY TAI CHINH CA NHAN & GIA DINH - HOMEFINANCE
echo ======================================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [LOI] Khong tim thay Python tren he thong!
    echo Vui long cai dat Python 3.9+ tu https://www.python.org/
    pause
    exit /b
)

echo [1/3] Dang kiem tra thu vien phu thuoc...
python -m pip install -q flask openpyxl

echo [2/3] Dang khoi tao co so du lieu & du lieu mau...
python sample_data.py

echo [3/3] Dang khoi dong may chu web tai http://127.0.0.1:5000 ...
echo.
echo ======================================================================
echo    MAY CHU DANG CHAY TAI: http://127.0.0.1:5000
echo    Nhan Ctrl + C trong cua so nay de tat ung dung.
echo ======================================================================
echo.

start "" "http://127.0.0.1:5000"
python app.py

pause
