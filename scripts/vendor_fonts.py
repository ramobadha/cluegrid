"""Refresh locally hosted Google Fonts and their OFL licenses (not needed for builds)."""
from pathlib import Path
import re
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
URL = ('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700'
       '&family=Noto+Sans+Gujarati:wght@400;500;600;700'
       '&family=Playfair+Display:ital,wght@0,500;0,600;1,500&display=swap')


def fetch(url):
    request = urllib.request.Request(url, headers={
        'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36')
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def main():
    target = ROOT / 'styles/fonts'
    target.mkdir(exist_ok=True)
    css = fetch(URL).decode('utf-8')
    # Keep only the scripts used by the English interface and Gujarati matrix.
    blocks = re.findall(r'/\* (?:latin|gujarati) \*/\s*@font-face\s*\{[^}]+\}', css)
    if not blocks:
        # Some download clients receive unsplit TTF faces instead of WOFF2 subsets.
        blocks = re.findall(r'@font-face\s*\{[^}]+\}', css)
    if not blocks:
        raise ValueError('Expected font-face rules')
    css = '\n\n'.join(blocks) + '\n'
    urls = sorted(set(re.findall(r'https://fonts\.gstatic\.com/[^)\s]+', css)))
    for number, url in enumerate(urls):
        suffix = Path(url).suffix
        if suffix not in {'.woff2', '.woff', '.ttf'}:
            raise ValueError(f'Unexpected font format: {suffix}')
        filename = f'font-{number}{suffix}'
        (target / filename).write_bytes(fetch(url))
        css = css.replace(url, f'fonts/{filename}')
    for family in ['dmsans', 'notosansgujarati', 'playfairdisplay']:
        license_url = f'https://raw.githubusercontent.com/google/fonts/main/ofl/{family}/OFL.txt'
        (target / f'{family}-OFL.txt').write_bytes(fetch(license_url))
    (ROOT / 'styles/fonts.css').write_text(css, encoding='utf-8')
    print(f'Vendored {len(urls)} font files and three OFL licenses.')


if __name__ == '__main__':
    main()
