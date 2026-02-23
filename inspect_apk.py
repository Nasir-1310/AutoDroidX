import zipfile, re

apk_path = r'D:\Nasir\LLMDroid\LLMDroid-v2\LLMDroid-Droidbot\droidbot\resources\droidbotApp.apk'
with zipfile.ZipFile(apk_path, 'r') as z:
    for name in z.namelist():
        if name.endswith('.dex'):
            data = z.read(name)
            text = data.decode('ascii', errors='ignore')
            keywords = ['content_description', 'resource_id', 'is_password', 'editable',
                        'scrollable', 'clickable', 'long_clickable', 'checkable', 'visible',
                        'focusable', 'focused', 'hint', 'package', 'text', 'class',
                        'checked', 'selected', 'enabled', 'bounds', 'children', 'root_node',
                        'AccEvent']
            for keyword in keywords:
                # Find all occurrences
                start_pos = 0
                count = 0
                while True:
                    idx = text.find(keyword, start_pos)
                    if idx < 0:
                        break
                    count += 1
                    if count <= 3:
                        s = max(0, idx - 30)
                        e = min(len(text), idx + len(keyword) + 30)
                        context = repr(text[s:e])
                        print(f'  [{name}] "{keyword}" at {idx}: {context}')
                    start_pos = idx + 1
                if count > 3:
                    print(f'  [{name}] "{keyword}" found {count} total times')
                elif count == 0:
                    print(f'  [{name}] "{keyword}" NOT FOUND')
