@echo off
rem A1 II (firmware 4.00): apply the open-gate state without the XAVC S-I 4K step (XAVC HS 4K and XAVC S 4K only).
rem WRITES into the camera's memory (not firmware, not settings). A cold boot (battery out for 10 seconds) returns it to stock; whether the power switch alone does on the A1 II is not known.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Python environment missing: run setup.cmd first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -I -B "tools\camera_tests\CT6_memory_read_check\a1m2_apply.py" apply --no-si %*
echo.
pause
