@echo off
REM Backup for the Laragon (Windows) setup. Schedule with: Task Scheduler -> Create Basic Task -> Daily -> this file.
REM Edit MYSQLDUMP to match your Laragon MySQL version folder.
set MYSQLDUMP=C:\laragon\bin\mysql\mysql-8.4.3-winx64\bin\mysqldump.exe
set APP=C:\laragon\www\vihea
set OUT=D:\vihea_backups
for /f %%i in ('powershell -command "Get-Date -Format yyyy-MM-dd_HHmm"') do set STAMP=%%i
if not exist "%OUT%" mkdir "%OUT%"
"%MYSQLDUMP%" -u root --single-transaction moeys_attendance > "%OUT%\db_%STAMP%.sql"
powershell -command "Compress-Archive -Path '%APP%\backend\uploads' -DestinationPath '%OUT%\uploads_%STAMP%.zip' -Force"
REM delete backups older than 14 days
forfiles /p "%OUT%" /m *.* /d -14 /c "cmd /c del @path" 2>nul
echo Backup done: %OUT%
