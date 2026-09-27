"""Vocabulary integrity and immutable legacy-bank regression checks."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import build


class VocabularyTests(unittest.TestCase):
    def test_large_bank_preserves_original_terms(self):
        current = build.load_words()
        legacy = build.load_words('words-v1.tsv')
        self.assertGreaterEqual(len(current), 2000)
        self.assertEqual(len(legacy), 180)
        self.assertEqual(current[:180], legacy)
        self.assertEqual(set(current[0]['translations']), {'gu', 'en'})
        self.assertTrue(all(all(word['translations'].values()) for word in current))
        self.assertFalse(any(';' in value or '|' in value for word in current
                             for value in word['translations'].values()))

    def test_legacy_bank_is_frozen(self):
        # Normalize line endings so Git's CRLF/LF checkout settings cannot change this fixture.
        text = (build.ROOT / 'data/words-v1.tsv').read_text(encoding='utf-8')
        self.assertEqual(hashlib.sha256(text.encode('utf-8')).hexdigest(),
                         '245bf91f4f24a74f4894c0e0867e64b09314a2b8093c64f438b6eb6420b59e0e')

    def test_bad_edits_are_rejected(self):
        valid = (build.ROOT / 'data/words-v1.tsv').read_text(encoding='utf-8')
        for bad in ['સૂર્ય\tSun again\n', 'English\tMeaning\n', 'મેઘ\t\n', 'મેઘ\tવાદળ\n', 'મેઘ\textra\tcolumn\n']:
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / 'data').mkdir()
                (root / 'data/languages.tsv').write_bytes((build.ROOT / 'data/languages.tsv').read_bytes())
                (root / 'data/words.tsv').write_text(valid + bad, encoding='utf-8')
                with patch.object(build, 'ROOT', root), self.assertRaises(ValueError):
                    build.load_words()

    def test_future_languages_are_data_driven(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'data').mkdir()
            language_file = (build.ROOT / 'data/languages.tsv').read_text(encoding='utf-8')
            (root / 'data/languages.tsv').write_text(language_file + 'es\tSpanish\tEspañol\n', encoding='utf-8')
            rows = (build.ROOT / 'data/words.tsv').read_text(encoding='utf-8').splitlines()
            (root / 'data/words.tsv').write_text(
                rows[0] + '\tes\n' + '\n'.join(row + '\tpalabra' + str(i) for i, row in enumerate(rows[1:51])) + '\n',
                encoding='utf-8')
            with patch.object(build, 'ROOT', root):
                translated = build.load_words()
                languages = build.load_languages()
            self.assertEqual(languages['es']['native'], 'Español')
            self.assertEqual(len(translated), 50)
            self.assertTrue(all(set(word['translations']) == {'gu', 'en', 'es'} for word in translated))


if __name__ == '__main__':
    unittest.main()
