@echo off
echo 🔧 Fixing Protobuf Version Conflict...
echo.

echo Step 1: Upgrading protobuf to latest version...
pip install --upgrade protobuf

echo.
echo Step 2: Reinstalling TensorFlow and DeepFace with compatible versions...
pip install --upgrade tensorflow
pip install --upgrade deepface

echo.
echo ✅ Done! Try running subscriber.py again.
echo.
pause
