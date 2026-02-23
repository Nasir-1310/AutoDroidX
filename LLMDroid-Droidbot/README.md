# LLMDroid-Droidbot

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