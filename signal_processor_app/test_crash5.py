import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication

app = QApplication(sys.argv)

print("Testing BackgroundSubtractionTab with QApplication...")
try:
    from main import BackgroundSubtractionTab
    print("Import BackgroundSubtractionTab successful")
    tab = BackgroundSubtractionTab()
    print("BackgroundSubtractionTab created successfully")
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f'\nError: {e}')