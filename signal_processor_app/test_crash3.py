import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Testing import of main module...")
try:
    import main
    print("Import main successful")
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f'\nError: {e}')