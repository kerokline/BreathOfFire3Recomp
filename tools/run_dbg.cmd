@echo off
rem Launch the build-dbg runtime under a classic conhost window, detached from
rem whatever terminal you typed this in (a Windows Terminal crash took a
rem 74-minute session with it on 2026-09-02), with stderr kept in
rem build-dbg\stderr.log so a startup failure is readable afterwards.
rem
rem   tools\run_dbg.cmd                 -> --no-launcher, debug port 4370
rem   tools\run_dbg.cmd --launcher      -> go through the launcher instead
rem   tools\run_dbg.cmd relprof         -> same for build-relprof
rem Any extra arguments are passed to the runtime.
setlocal
set "ROOT=%~dp0.."
set "TREE=build-dbg"
set "MODE=--no-launcher"
:args
if "%~1"=="" goto run
if /I "%~1"=="relprof"    ( set "TREE=build-relprof" & shift & goto args )
if /I "%~1"=="dbg"        ( set "TREE=build-dbg"     & shift & goto args )
if /I "%~1"=="--launcher" ( set "MODE="              & shift & goto args )
set "EXTRA=%EXTRA% %1"
shift
goto args
:run
set "EXE=%ROOT%\%TREE%\BreathOfFire3_Recompiled.exe"
set "LOG=%ROOT%\%TREE%\stderr.log"
if not exist "%EXE%" ( echo run_dbg: %EXE% not found & exit /b 1 )
echo run_dbg: %TREE% %MODE% --debug-port 4370%EXTRA%  (stderr -> %LOG%)
rem conhost.exe forces a legacy console; cmd /c inside it does the redirect and
rem holds the window open when the game exits non-zero so the reason is visible.
start "" conhost.exe cmd.exe /c ""%EXE%" --game game.toml %MODE% --debug-port 4370%EXTRA% 2>"%LOG%" || (type "%LOG%" & echo. & echo run_dbg: exited with error - see %LOG% & pause)"
endlocal
