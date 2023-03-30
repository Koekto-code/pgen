@echo off

set BL_RAWPATH=%ProgramFiles%\Blender Foundation

rem Pick the last blender subdirectory
for /f "tokens=*" %%i in ('dir /B "%BL_RAWPATH%"') do set BL_SUBDIR=%%i

rem Parse version number from string like "Blender 3.4"
for /f "tokens=1,* delims= " %%a in ("%BL_SUBDIR%") do set BL_VER=%%b

rem The python directly from blender can't be used bec. it lacks development headers
if not defined BL_PYTHON_PATH (
  set BL_PYTHON_PATH=%BL_RAWPATH%\%BL_SUBDIR%\%BL_VER%\python
)
if not defined BL_DATA_PATH (
  set BL_DATA_PATH=%APPDATA%\Blender Foundation\Blender\%BL_VER%
)

rem Get the native blender python version eg. 3.10.8
for /f "tokens=1,* delims= " %%a in ('"%BL_PYTHON_PATH%\bin\python" -V') do set BL_NATIVE_PYTHON=%%b

rem Discard the revision segment
for /f "tokens=1,2 delims=." %%a in ("%BL_NATIVE_PYTHON%") do (
    set BL_NATIVE_PYTHON=%%a.%%b
)

echo Blender python path  : %BL_PYTHON_PATH%
echo Blender data path    : %BL_DATA_PATH%
echo Blender native python: %BL_NATIVE_PYTHON%
pause

if not exist build mkdir build
git submodule update --init

rem Call the same python version as blender native
rem Add --compiler=mingw-w64 for building with GCC
cd noise
py -%BL_NATIVE_PYTHON% setup.py install --prefix=..\build
cd ..

xcopy pgen "%BL_DATA_PATH%\scripts\addons\pgen" /e /h /i /y /q
xcopy "build\lib\site-packages" "%BL_DATA_PATH%\scripts\addons\pgen" /e /h /i /y /q

pause
