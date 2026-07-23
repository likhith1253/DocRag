import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import eval.generate_dataset as gen

# Mock input to always return 'y'
original_input = __builtins__.input
__builtins__.input = lambda prompt="": print(prompt + "y") or "y"

try:
    gen.main()
finally:
    __builtins__.input = original_input
