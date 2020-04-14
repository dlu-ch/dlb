@call "%VCINSTALLDIR%\VC\Auxiliary\Build\vcvars64.bat"
if %errorlevel% neq 0 exit
cd %1
python -m dlb_contrib.exportenv
