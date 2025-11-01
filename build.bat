@echo off
chcp 65001
echo ===============================================
echo    Сборка Payport SP Parser
echo ===============================================

echo Установка зависимостей...
pip install selenium==4.15.0 beautifulsoup4==4.12.2 lxml==4.9.3

echo Очистка предыдущих сборок...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist __pycache__ rmdir /s /q __pycache__

echo Сборка приложения...
pyinstaller --windowed ^
--name "PP-Parser" ^
--add-data "service_providers.txt;." ^
--add-data "employee_groups.json;." ^
--hidden-import=selenium.webdriver.common.by ^
--hidden-import=selenium.webdriver.chrome.service ^
--hidden-import=selenium.webdriver.support.ui ^
--hidden-import=selenium.webdriver.support.expected_conditions ^
--hidden-import=bs4 ^
--hidden-import=lxml ^
--hidden-import=urllib.parse ^
--exclude-module=matplotlib ^
--exclude-module=pandas ^
--exclude-module=numpy ^
--icon=C:\Users\Denis\Downloads\1.ico ^
--clean ^
PP-Parser.py

echo ===============================================
echo    Сборка завершена!
echo    Исполняемый файл: dist\PayportSPParser.exe
echo ===============================================
echo Не забудьте скопировать в папку dist:
echo   - service_providers.txt
echo   - employee_groups.json
echo ===============================================
pause