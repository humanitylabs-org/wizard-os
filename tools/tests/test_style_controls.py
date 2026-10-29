"""The shell's no-global-reset controls are generated, not another authored kit."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]

class StyleControlSubsetTests(unittest.TestCase):
    def test_generated_controls_match_the_self_contained_kit(self):
        subprocess.run([sys.executable, str(ROOT / 'style/generate_controls.py'), '--check'], check=True)

if __name__ == '__main__':
    unittest.main()
