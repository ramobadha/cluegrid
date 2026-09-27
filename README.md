# ClueGrid — Gujarati Edition

A static, responsive multilingual word-grid game with a Gujarati-English word bank. Players independently choose the language for the card and its single translation. Gujarati is the default.

## Run locally

Requires Python 3.11+; no Python dependencies or frontend install needed.

```sh
python build.py
python -m http.server 8000 --directory dist
```

Open http://localhost:8000. Run game tests with `node --test tests/*.test.cjs` (Node 22+).

Optional browser checks require Playwright (`python -m pip install --target .test-deps playwright`) and installed Google Chrome. Serve `dist/` on port 8765 in another terminal, then run `python tests/browser.py`. Screenshots are saved under `test-artifacts/`.

## Mobile play

The five-column board adapts to narrow phones, large phones, tablets, and landscape screens. On phones, a fixed bottom bar keeps the current turn, remaining agents, and End turn within reach. Controls have at least 44-pixel tap targets, seed fields use 16-pixel text, and pinch zoom remains enabled. Confirmation sheets show the selected term at a larger size with its translation when translations are enabled. Screen cutouts and bottom safe areas have dedicated spacing. Display and language preferences persist on the device.

Share game opens the native share sheet when supported on touch devices, otherwise copies the link or displays it for manual copying. Native sharing and clipboard availability depend on the browser and whether the site is served over HTTPS; the manual fallback also works on local HTTP.

Mobile browser checks run in Chromium, WebKit, and Firefox at 14 portrait/landscape sizes from 320 to 1,366 pixels. They cover tap targets, long Gujarati terms, score updates, spymaster mode, saved preferences, scrollable dialogs, and page overflow. These are browser-emulation checks, not physical-device certification.

```powershell
$env:PYTHONPATH='.test-deps'
python -m playwright install webkit firefox
$env:KODENAMES_TEST_URL='http://127.0.0.1:8917' # Point to your running server
python tests/mobile.py
```

## Play

Share the seed or invite URL. Everyone using the same seed and vocabulary version gets identical words and team keys. Each device tracks its own guesses: this is not a realtime multiplayer server. Use one shared guesser screen or mirror guesses manually. Spymasters view the key on a separate screen. Clues are spoken; players enforce the clue-number guess limit. Wrong guesses switch turns, the assassin ends the game, and finding every agent wins. Refresh restores local progress; Restart clears it. Spymaster visibility always resets on refresh. Once the seed and languages are set, select the ⛶ button beside New game for a focused play screen; use Exit full screen or the Escape key to return to setup.

## Seeding

Uses upstream's bundled seedrandom 2.3.10, selection without replacement, Fisher–Yates team shuffle, 980-entry base-list parity rule, and column-first card ordering. Seeds are trimmed and lowercased. Gujarati words differ from the English vocabulary, but the seeded generation procedure and team key match upstream for the same normalized seed.

New games use `gu-v2`: **2,150 unique Gujarati terms**, expanded from 180. Invite URLs include the version. Links with `v=gu-v1` still use the original frozen 180-word bank (`data/words-v1.tsv`) and retain their local saved progress. Restart keeps the current version; New game switches to the latest bank. Unversioned links use the latest bank. Unknown versions show a warning and use the latest bank. Future vocabulary changes must introduce another version and retain the old dataset to preserve existing links.

Under independent uniform selection, two 25-card boards share about `625 / vocabulary_size` words on average: **3.47** with 180 words versus **0.29** with 2,150 words. Repeats across games are still possible. Selection never depends on local play history, so shared seeds stay reproducible across devices.

## Vocabulary and Python

`data/words.tsv` is the current vocabulary source. Its header specifies one column per language, such as `gu<TAB>en`; every row contains exactly one Gujarati term and one English equivalent. Standard compounds may be written as multiple parts; synonym lists and alternate meanings are not allowed. To add a language, add its code, English name, and native-script label to `data/languages.tsv`, then add one translation column to the vocabulary. Seeded words and team keys stay identical when players change display languages. Language selections are saved on each device and included in invite links. See [vocabulary notes](data/README.md).

`build.py` checks Unicode-normalized Gujarati uniqueness, language codes, one complete translation per language, and minimum bank size. It generates versioned banks and language labels in `data/words.js`, then copies the static site into `dist/`. Python runs at build time because GitHub Pages cannot host a Python server. The browser runs the game in plain JavaScript. Fonts are bundled locally under `styles/fonts/`, including their OFL licenses, so page loading does not depend on external requests. `scripts/vendor_fonts.py` is an optional network-based font refresh utility, not part of the normal build.

## Deploy

Push this project to a GitHub repository on the `main` branch. Under **Settings → Pages → Build and deployment**, select **GitHub Actions**. The included workflow tests, builds with Python, and deploys `dist/`. Relative asset paths support project Pages URLs. For a different default branch, update `.github/workflows/pages.yml`.

### Render

`render.yaml` configures ClueGrid as a Render static site. Push the project to a GitHub or GitLab repository, then in Render choose **New → Blueprint**, connect that repository, and apply the `cluegrid` service. Render runs `python build.py` and publishes `dist/`; no server process or start command is needed. You can also create a **Static Site** manually with the same build command and publish directory. See [Render's static-site guide](https://render.com/docs/static-sites).

## Attribution

Board-generation logic adapted from KodeNames (MIT); see `THIRD_PARTY_LICENSE.md`. Bundled `scripts/seedrandom.js` includes David Bau's MIT license. No original analytics or backend services are included.

DM Sans, Noto Sans Gujarati, and Playfair Display are bundled under their SIL Open Font Licenses in `styles/fonts/`.
