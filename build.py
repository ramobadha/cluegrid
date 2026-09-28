"""Validate the versioned Gujarati word bank and build a GitHub Pages site."""
import json
import hashlib
from pathlib import Path
import shutil
import unicodedata
import re
import os
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent

def load_languages():
    languages = {}
    for number, line in enumerate((ROOT / 'data/languages.tsv').read_text(encoding='utf-8').splitlines(), 1):
        parts = line.split('\t')
        if len(parts) != 3:
            raise ValueError(f'languages.tsv, line {number}: expected code, English name, and native name')
        code, name, native = (part.strip() for part in parts)
        if (not re.fullmatch(r'[a-z]{2,3}', code) or not name or not native or code in languages
                or not all(c.isalpha() or unicodedata.category(c) in {'Mn', 'Mc', 'Me'}
                           or c.isspace() or c in '·-()' for c in native)):
            raise ValueError(f'languages.tsv, line {number}: invalid or duplicate language')
        languages[code] = {'name': name, 'native': native}
    if 'gu' not in languages or 'en' not in languages:
        raise ValueError('Gujarati (gu) and English (en) are required')
    return languages

def load_words(filename='words.tsv'):
    words = []
    seen = set()
    available_languages = load_languages()
    languages = ['gu', 'en']
    lines = (ROOT / 'data' / filename).read_text(encoding='utf-8').splitlines()
    if filename == 'words.tsv' and lines and lines[0].split('\t')[:2] == ['gu', 'en']:
        languages = lines[0].split('\t')
        lines = lines[1:]
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        parts = line.split('\t')
        if len(parts) != len(languages):
            raise ValueError(f'{filename}, line {number}: expected {len(languages)} language columns')
        translations = {code: unicodedata.normalize('NFC', value.strip())
                        for code, value in zip(languages, parts)}
        term = translations.get('gu', '')
        meaning = translations.get('en', '')
        valid_codes = (len(set(languages)) == len(languages)
                       and all(re.fullmatch(r'[a-z]{2,3}', code) for code in languages))
        valid_gujarati = (bool(term) and all('\u0a80' <= c <= '\u0aff' or c == ' ' for c in term)
                          and any('\u0a80' <= c <= '\u0aff' for c in term))
        valid_terms = all(value and ';' not in value and '|' not in value
                          and any(c.isalpha() for c in value) for value in translations.values())
        if (not valid_codes or not set(languages).issubset(available_languages)
                or not valid_gujarati or not valid_terms
                or ('en' in translations and not meaning.isascii())
                or term in seen):
            raise ValueError(f'{filename}, line {number}: invalid or duplicate term')
        seen.add(term)
        words.append({'term': term, 'meaning': meaning, 'translations': translations})
    if len(words) < 25:
        raise ValueError('At least 25 unique words are required')
    return words

def main():
    api_url = os.environ.get('CLUEGRID_API_URL', '').strip().rstrip('/')
    if api_url:
        parsed = urlsplit(api_url)
        local = parsed.scheme == 'http' and parsed.hostname in ('localhost', '127.0.0.1', '::1')
        if (not parsed.hostname or (parsed.scheme != 'https' and not local)
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError('CLUEGRID_API_URL must be an HTTPS service URL (HTTP is allowed for localhost).')
    words = load_words()
    banks = {'gu-v1': load_words('words-v1.tsv'), 'gu-v2': words}
    languages = load_languages()
    payload = 'window.WORD_BANKS = ' + json.dumps(banks, ensure_ascii=False, indent=2) + ';\n'
    payload += 'window.LANGUAGES = ' + json.dumps(languages, ensure_ascii=False, indent=2) + ';\n'
    payload += 'window.LANGUAGE_CODES = ' + json.dumps(list(languages)) + ';\n'
    bank_languages = {code: list(bank[0]['translations']) for code, bank in banks.items()}
    payload += 'window.WORD_BANK_LANGUAGES = ' + json.dumps(bank_languages) + ';\n'
    payload += 'window.GUJARATI_WORD_BANKS = window.WORD_BANKS;\n'
    payload += "window.GUJARATI_WORDS = window.GUJARATI_WORD_BANKS['gu-v2'];\n"
    (ROOT / 'data/words.js').write_text(payload, encoding='utf-8')
    output = ROOT / 'dist'
    output.mkdir(exist_ok=True)
    for name in ('index.html', 'THIRD_PARTY_LICENSE.md'):
        shutil.copy2(ROOT / name, output / name)
    for name in ('scripts', 'styles', 'data'):
        shutil.copytree(ROOT / name, output / name, dirs_exist_ok=True)
    (output / 'scripts/config.js').write_text('window.CLUEGRID_API_URL = ' + json.dumps(api_url) + ';\n', encoding='utf-8')
    # A deployment must not combine new markup with cached scripts or styles.
    html = (output / 'index.html').read_text(encoding='utf-8')
    def version_asset(match):
        attribute, asset = match.groups()
        digest = hashlib.sha256((output / asset).read_bytes()).hexdigest()[:16]
        return f'{attribute}="{asset}?v={digest}"'
    html = re.sub(r'(src|href)="((?:scripts|styles|data)/[^"?]+\.(?:js|css))"', version_asset, html)
    (output / 'index.html').write_text(html, encoding='utf-8')
    (output / '.nojekyll').touch()
    empire = output / 'empire'
    shutil.copytree(ROOT / 'empire', empire, dirs_exist_ok=True)
    shutil.copy2(output / 'scripts/config.js', empire / 'config.js')
    shutil.copy2(ROOT / 'styles/fonts.css', empire / 'fonts.css')
    shutil.copytree(ROOT / 'styles/fonts', empire / 'fonts', dirs_exist_ok=True)
    shutil.copy2(ROOT / 'THIRD_PARTY_LICENSE.md', empire / 'THIRD_PARTY_LICENSE.md')
    empire_html = (empire / 'index.html').read_text(encoding='utf-8')
    def empire_asset(match):
        attribute, asset = match.groups()
        digest = hashlib.sha256((empire / asset).read_bytes()).hexdigest()[:16]
        return f'{attribute}="{asset}?v={digest}"'
    empire_html = re.sub(r'(src|href)="([^"/?]+\.(?:js|css))"', empire_asset, empire_html)
    (empire / 'index.html').write_text(empire_html, encoding='utf-8')
    (empire / '.nojekyll').touch()
    print(f'Built dist/ with {len(words)} validated Gujarati terms (gu-v2); retained {len(banks["gu-v1"])} legacy terms (gu-v1).')

if __name__ == '__main__':
    main()
