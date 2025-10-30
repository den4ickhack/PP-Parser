@echo off
echo Очистка предыдущих сборок...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

echo Сборка PP-Parser...
pyinstaller --onefile ^
            --windowed ^
            --name "PP-Parser" ^
            --add-data "service_providers.txt;." ^
            --icon=icon.ico ^
            --clean ^
            --noconfirm ^
            PP-Parser.py

echo Готово! EXE файл находится в папке dist
pause