import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Testing TIME_FREQ_METHODS access...")
try:
    from main import TIME_FREQ_METHODS
    print(f"TIME_FREQ_METHODS keys: {list(TIME_FREQ_METHODS.keys())}")
    print(f"First method info: {TIME_FREQ_METHODS.get(list(TIME_FREQ_METHODS.keys())[0], {})}")
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f'\nError: {e}')