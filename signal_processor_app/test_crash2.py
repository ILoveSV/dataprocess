import sys
import os
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Testing BackgroundSubtractionTab directly...")
try:
    from main import BackgroundSubtractionTab
    print("Import BackgroundSubtractionTab successful")
    tab = BackgroundSubtractionTab()
    print("BackgroundSubtractionTab created successfully")
except Exception as e:
    traceback.print_exc()
    print(f'\nError: {e}')