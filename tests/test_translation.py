import json
import unittest

class TestTranslationFulfillment(unittest.TestCase):
    def setUp(self):
        # Load expected translations
        with open('public/locales/en/expected.json') as f:
            self.expected_translations = json.load(f)
        
        # Load actual translations
        with open('public/locales/en/actual.json') as f:
            self.actual_translations = json.load(f)

    def test_missing_translations(self):
        # Check if all expected translations are fulfilled
        missing_keys = [key for key in self.expected_translations.keys() if key not in self.actual_translations]
        self.assertEqual(len(missing_keys), 0, f'Missing translations: {missing_keys}')

if __name__ == '__main__':
    unittest.main()
