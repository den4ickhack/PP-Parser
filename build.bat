@echo off
echo pyinstaller --windowed --name PP-Parser --add-data "service-providers.txt;." --exclude-module matplotlib --exclude-module pandas --exclude-module numpy --exclude-module scipy --strip --noupx PP-Parser.py --icon=C:\Users\Denis\Downloads\1.icoecho Готово! EXE файл находится в папке dist\
pause