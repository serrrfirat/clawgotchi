
import sys
import os

print(f"CWD: {os.getcwd()}")
print(f"Path: {sys.path}")

try:
    import utils.session_cost_tracker
    print("Direct import utils.session_cost_tracker SUCCESS!")
except Exception as e:
    print(f"Direct import ERROR: {e}")
