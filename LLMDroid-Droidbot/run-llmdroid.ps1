# run-llmdroid.ps1

# Activate venv (adjust path if needed)
# python -m venv venv
# .\venv\Scripts\Activate.ps1
# $env:PYTHONUTF8=1
# pip install -r requirements.txt

# change in droid/app.py at line numbet 28 
form from androguard.core.apk import APK to from androguard.core.bytecodes.apk import APK
# after run :
pip install httpx==0.27.2 --force-reinstall
# thern paste on powerslall


python start.py -d emulator-5554 `
  -a "D:\Nasir\LLMDroid\LLMDroid\apks\newpipe.apk" `
  -o "D:\Nasir\LLMDroid\results\newpipe-test-v2" `
  -timeout 3600 `
  -interval 3 `
  -count 10000000 `
  -keep_app `
  -keep_env `
  -policy dfs_greedy `
  -grant_perm `
  -is_emulator


# Set Groq variables
$env:OPENAI_BASE_URL = "https://api.groq.com/openai/v1"
$env:OPENAI_API_KEY  = "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"

# Run LLMDroid (adjust parameters as needed)
python start.py -d emulator-5554 `
  -a "D:\Nasir\LLMDroid\LLMDroid\apks\newpipe.apk" `
  -o "D:\Nasir\LLMDroid\results\newpipe-test-v2" `
  -timeout 3600 `
  -interval 3 `
  -count 10000000 `
  -keep_app `
  -keep_env `
  -policy dfs_greedy `
  -grant_perm


  #to stop running scipt on terminal: 
  # Find running Python processes
tasklist | findstr python

# Kill by Process ID (replace XXXX with actual PID)
taskkill /PID XXXX /F

# OR kill all Python processes at once
taskkill /IM python.exe /F

#Run in PowerShell
cd D:\Nasir\LLMDroid\LLMDroid-v2\LLMDroid-Droidbot; ..\venv\Scripts\python.exe start.py -d emulator-5554 -a "D:\Nasir\LLMDroid\LLMDroid-v2\apks\non_instrumented\app-debug.apk" -o "D:\Nasir\LLMDroid\LLMDroid v1\LLMDroid\results\final-test-v12" -timeout 3600 -interval 3 -count 1000000 -keep_app -keep_env -policy dfs_greedy -grant_perm -cv
#Or
cd D:\Nasir\LLMDroid\LLMDroid-v2\LLMDroid-Droidbot
..\venv\Scripts\python.exe start.py -d emulator-5554 -a "D:\Nasir\LLMDroid\LLMDroid-v2\apks\non_instrumented\app-debug.apk" -o "D:\Nasir\LLMDroid\LLMDroid v1\LLMDroid\results\final-test-v12" -timeout 3600 -interval 3 -count 1000000 -keep_app -keep_env -policy dfs_greedy -grant_perm -cv
#Run in CMD
cd /d D:\Nasir\LLMDroid\LLMDroid-v2\LLMDroid-Droidbot && ..\venv\Scripts\python.exe start.py -d emulator-5554 -a "D:\Nasir\LLMDroid\LLMDroid-v2\apks\non_instrumented\app-debug.apk" -o "D:\Nasir\LLMDroid\LLMDroid v1\LLMDroid\results\final-test-v12" -timeout 3600 -interval 3 -count 1000000 -keep_app -keep_env -policy dfs_greedy -grant_perm -cv