import sys
import os
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from main import SignalProcessorMainWindow
    print("Import successful")
    w = SignalProcessorMainWindow()
    print("Window created successfully")
except Exception as e:
    traceback.print_exc()
    print(f'\nError: {e}')