import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('voice_checker', Path(__file__).resolve().parents[1] / 'check_wizard_md.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)

class VoiceNames(unittest.TestCase):
    def test_valid(self):
        for names in [[], ['Hello', 'hello world'], ['😀' * 40] * 8]:
            self.assertEqual(checker.voice_names({'voice_names': names}), names)
        self.assertEqual(checker.voice_names({}), [])

    def test_invalid(self):
        for names in [None, 'hello', {}, [True], [1], [''], [' '], ['x' * 41], ['x'] * 9, ['a\nb']]:
            with self.subTest(names=names), self.assertRaises(ValueError):
                checker.voice_names({'voice_names': names})
