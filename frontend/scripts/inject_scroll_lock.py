import os
import re

hook_import = 'import { useScrollLock } from "@/hooks/useScrollLock";'
hook_call = '  useScrollLock(isOpen);'

components_dir = r'd:\moldesign-build\frontend\components'

for root, dirs, files in os.walk(components_dir):
    for f in files:
        if f.endswith('Modal.tsx'):
            path = os.path.join(root, f)
            with open(path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            if 'isOpen' in content and 'useScrollLock' not in content:
                if '"use client";' in content or "'use client';" in content:
                    content = re.sub(r'("use client";|\'use client\';)\n', r'\1\n' + hook_import + '\n', content, count=1)
                else:
                    content = hook_import + '\n' + content
                
                # Match function name(...) { where ... contains isOpen
                pattern = r'(function\s+\w+\s*\([^\)]*\bisOpen\b[^\)]*\)(?:\s*:\s*\w+)?\s*{)'
                content = re.sub(pattern, r'\1\n' + hook_call, content, count=1)
                
                with open(path, 'w', encoding='utf-8') as file:
                    file.write(content)
                print(f'Patched {f}')
