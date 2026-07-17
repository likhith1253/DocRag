import ast, os

base = 'd:/Document_RAG/eval/external_benchmark/repos/textual/src/textual'

# Widget: look for add_class directly (it might be in DOMNode not Widget)
with open(base+'/widget.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Scan for call_after_refresh, add_class, set_timer, run_worker
keywords = ['call_after_refresh', 'call_later', 'add_class', 'remove_class', 'set_timer', 'run_worker']
for i, line in enumerate(lines, 1):
    stripped = line.strip()
    for kw in keywords:
        if f'def {kw}' in stripped or f'async def {kw}' in stripped:
            print(f'widget.py L{i}: {stripped}')
            break

# app.py
with open(base+'/app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines, 1):
    stripped = line.strip()
    for kw in keywords:
        if f'def {kw}' in stripped or f'async def {kw}' in stripped:
            print(f'app.py L{i}: {stripped}')
            break

# message_pump.py
with open(base+'/message_pump.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines, 1):
    stripped = line.strip()
    for kw in keywords:
        if f'def {kw}' in stripped or f'async def {kw}' in stripped:
            print(f'msg_pump.py L{i}: {stripped}')
            break
