# ClueGrid — Gujarati Edition

A responsive multilingual word-grid game with a Gujarati-English word bank, a static frontend, and an optional private-room syncing service. Players independently choose the language for the card and its single translation. Gujarati is the default.

## Run locally

Requires Python 3.11+. The static build needs no Python dependencies or frontend install. Live rooms use Flask and SQLite.

```sh
python build.py
python -m http.server 8000 --directory dist
```

Open http://localhost:8000. To run the frontend and live-room API together instead:

```sh
python -m pip install -r requirements.txt
python build.py
python server.py
```

The development server listens on http://127.0.0.1:8000. Room data lives in `instance/rooms.sqlite3` (override with `ROOM_DB`). Production uses Gunicorn; the Flask development server is for local use only.

Run game tests with `node --test tests/*.test.cjs` (Node 22+).

Optional browser checks require Playwright (`python -m pip install --target .test-deps playwright`) and installed Google Chrome. Serve `dist/` on port 8765 in another terminal, then run `python tests/browser.py`. Screenshots are saved under `test-artifacts/`.

## Mobile play

The five-column board adapts to narrow phones, large phones, tablets, and landscape screens. Red and blue counts above the grid show remaining words; players manage turns themselves. The swap button between the language selectors exchanges the word and meaning languages without changing progress or the active view. Controls have at least 44-pixel tap targets, seed fields use 16-pixel text, and pinch zoom remains enabled. Confirmation sheets show the selected term at a larger size with its translation when translations are enabled. Screen cutouts and bottom safe areas have dedicated spacing. Display and language preferences persist on the device.

Share game opens the native share sheet when supported on touch devices, otherwise copies the link or displays it for manual copying. Native sharing and clipboard availability depend on the browser and whether the site is served over HTTPS; the manual fallback also works on local HTTP.

Mobile browser checks run in Chromium, WebKit, and Firefox at 14 portrait/landscape sizes from 320 to 1,366 pixels. They cover tap targets, long Gujarati terms, score updates, spymaster mode, saved preferences, scrollable dialogs, and page overflow. These are browser-emulation checks, not physical-device certification.

```powershell
$env:PYTHONPATH='.test-deps'
python -m playwright install webkit firefox
$env:KODENAMES_TEST_URL='http://127.0.0.1:8917' # Point to your running server
python tests/mobile.py
```

## Play

**Share game** creates a private live room when a syncing service is configured. The browser that creates it is the host. Host reveals, remaining counts, restarts, and new boards sync to guests, usually within one second. Guests choose their own languages, fullscreen layout, and player/spymaster view, but only the host can change the shared board. Game-over announcements appear for three seconds on connected participants' screens. The dark grey card announces only "Game over"; completing a team's agents announces that team's win.

The shared URL contains a cryptographically random room capability in its `#room=` fragment. Anyone with that link can join or forward it. Separate rooms using the same seed remain independent, and there is no room directory. The separate host key is stored in the host browser and never added to the invitation or returned in guest snapshots. Refresh restores room state and host controls on the same browser; clearing the host browser's storage loses hosting access. If browser storage is blocked, hosting lasts only while that tab remains open. Guests can leave a room to play independently. If the sync service fails, the last known board becomes an independent local game. Hosts and guests can reveal cards, restart, and start new boards; failed host moves continue locally. The room link is removed from that tab, and local moves are never automatically merged into the old room. Cached room snapshots help restore the board when opening an invite during an outage. Use Share game again to create a fresh live room from local progress when the service returns. If sharing fails, a seed-only link still works without syncing.

A plain seed URL still reproduces the words and key, with device-local guesses. On static hosting without a configured service, Share game retains this seed-only behavior and labels it as local play. Old seed links remain supported. Spymaster view is trust-based, not a secure secret role: the seeded key is reproducible in every browser. Players handle clues and turns aloud.

Select the fullscreen button beside New game for fullscreen with the scores and a persistent exit icon above the fitted grid. Escape also exits. If native fullscreen is unavailable, the fitted layout uses the browser window. On touch devices, landscape orientation is requested when supported; rotate manually otherwise.

## Seeding

Uses upstream's bundled seedrandom 2.3.10, selection without replacement, Fisher–Yates team shuffle, 980-entry base-list parity rule, and column-first card ordering. Seeds are trimmed and lowercased. Gujarati words differ from the English vocabulary, but the seeded generation procedure and team key match upstream for the same normalized seed.

New games use `gu-v2`: **2,150 unique Gujarati terms**, expanded from 180. Invite URLs include the version. Links with `v=gu-v1` still use the original frozen 180-word bank (`data/words-v1.tsv`) and retain their local saved progress. Restart keeps the current version; New game switches to the latest bank. Unversioned links use the latest bank. Unknown versions show a warning and use the latest bank. Future vocabulary changes must introduce another version and retain the old dataset to preserve existing links.

Under independent uniform selection, two 25-card boards share about `625 / vocabulary_size` words on average: **3.47** with 180 words versus **0.29** with 2,150 words. Repeats across games are still possible. Selection never depends on local play history, so shared seeds stay reproducible across devices.

## Vocabulary and Python

`data/words.tsv` is the current vocabulary source. Its header specifies one column per language, such as `gu<TAB>en`; every row contains exactly one Gujarati term and one English equivalent. Standard compounds may be written as multiple parts; synonym lists and alternate meanings are not allowed. To add a language, add its code, English name, and native-script label to `data/languages.tsv`, then add one translation column to the vocabulary. Seeded words and team keys stay identical when players change display languages. Language selections are saved on each device and included in invite links. See [vocabulary notes](data/README.md).

`build.py` checks Unicode-normalized Gujarati uniqueness, language codes, one complete translation per language, and minimum bank size. It generates versioned banks and language labels in `data/words.js`, then copies the static site into `dist/`. For the Pages frontend, Python runs at build time; the optional room API runs on a separate Python host. The browser runs the game in plain JavaScript. Fonts are bundled locally under `styles/fonts/`, including their OFL licenses, so page loading does not depend on external requests. `scripts/vendor_fonts.py` is an optional network-based font refresh utility, not part of the normal build.

## Deploy

Push this project to a GitHub repository on the `main` branch. Under **Settings → Pages → Build and deployment**, select **GitHub Actions**. The included workflow tests, builds with Python, and deploys `dist/`. Relative asset paths support project Pages URLs. For a different default branch, update `.github/workflows/pages.yml`.

### GitHub Pages + a separate room service

Keep the existing Pages workflow and deploy **`render-sync.yaml`** as a new Render Blueprint (choose that file as the Blueprint path). It creates a Python service named `cluegrid-sync`; `render.yaml` still describes the original static-site option. The sync service uses:

- Build: `pip install -r requirements.txt && python build.py`
- Start: `gunicorn 'server:create_app()' --bind 0.0.0.0:$PORT --workers 1 --threads 8`
- Health check: `/health`
- `ALLOWED_ORIGINS=https://ramobadha.github.io` (change this if using a custom Pages domain; comma-separate multiple exact origins, without paths or trailing slashes).
- `ROOM_DB=/tmp/cluegrid/rooms.sqlite3` in the example free service.

After Render supplies the service URL, add a GitHub repository **Actions variable** named `CLUEGRID_API_URL`, with a value such as `https://YOUR-SERVICE.onrender.com`. Run the **Deploy GitHub Pages** workflow again. `build.py` writes this public address to `dist/scripts/config.js` and includes it in asset fingerprinting. Do not put credentials in this URL. The service permits cross-origin requests only from the configured website origins; host changes also require the private host key.

The included Render blueprint uses a free service. Its local filesystem is ephemeral: **rooms disappear when that service restarts or redeploys**. For rooms that survive service restarts, use a paid service with a persistent disk and set `ROOM_DB` to a file under its mount path (for example `/var/data/rooms.sqlite3`). See [Render's disk documentation](https://render.com/docs/disks). This SQLite deployment supports one service instance; multiple Gunicorn threads share transactional state safely. Rooms expire seven days after creation regardless of activity. No paid resources are provisioned by building the project.

### Verify separate frontend/API hosting locally

Start `server.py` with `PORT=8879`, `ALLOWED_ORIGINS=http://127.0.0.1:8878`, and a test `ROOM_DB`. Build with `CLUEGRID_API_URL=http://127.0.0.1:8879`, then serve `dist/` with `python -m http.server 8878 --directory dist`. In another terminal:

```powershell
$env:KODENAMES_TEST_URL='http://127.0.0.1:8878'
$env:CLUEGRID_API_URL='http://127.0.0.1:8879'
python tests/rooms_browser.py
python -m unittest discover -s tests -p 'test_*.py'
```

The room browser checks use separate browser contexts for host, two guests, and an unrelated room. They exercise late joins, refresh, local outage fallback, cached snapshots, failed host writes, private-room isolation, results, resets, and new boards. The Python tests additionally check host authorization, simultaneous writes, expiration, validation, and CORS. Rebuild without `CLUEGRID_API_URL` to restore the default same-origin/local configuration.

## Empire

Empire is a second game at **https://ramobadha.github.io/empire/**. Its source is in `empire/`, and its room API is in `empire_api.py`, registered on the same Render service as ClueGrid. Locally, run the Flask server and open `/empire/`. `python build.py` also produces a standalone `dist/empire/` site.

The host creates a private room and copies the invitation. Each player browser can submit one word or short name (up to 80 characters); duplicate words from different players are allowed. The host may also submit a word. Player identity is a browser capability, not an account: clearing storage or using another browser can create another participant.

**Show words** atomically closes submissions and shuffles the list, displaying one word per line only to the host tab that first requested it. A three-minute countdown starts at that moment. At zero, the server deletes the room, submitted entries, and revealed list; connected host and player screens clear automatically. Neither players nor other host tabs receive the word list through room state. A separate viewer key stored in session storage lets that original tab retry or refresh during those three minutes. Closing that tab or clearing its storage may lose access; there is no reveal transfer. The list is never placed in an invitation. The UI renders submissions as text, not HTML.

Empire requires the room service for collection and reveal. Connection failures retain the current draft and report unconfirmed actions; retries cannot create duplicate submissions. Rooms expire after seven days and are lost on a free Render restart/redeploy, like ClueGrid rooms. Up to 100 submissions are accepted per room.

The `ramobadha/empire` repository deploys the standalone frontend using `deploy/empire-pages.yml`. Its workflow builds the current `main` source from this repository. After pushing Empire changes here, run **Deploy Empire** in that repository; API changes also require a Render deployment. No additional paid service is needed.

Checks: `python -m unittest discover -s tests -p "test_*.py"` covers authorization, room isolation, idempotency, simultaneous show/submit requests, validation, and private snapshots. With the Flask server at port 8877, `python tests/empire_browser.py` covers separate host/player devices, tab ownership, refresh, failed submission retry, safe rendering, and phone/desktop layouts.

## Imposter

Imposter is available at **https://ramobadha.github.io/imposter/** with private shared rooms for 3–20 players, different-word and no-word modes, and host-controlled rounds. Read [IMPOSTER.md](IMPOSTER.md) for the full player guide, researched setup recommendations, privacy behavior, and deployment details. Its frontend lives in `imposter/` and its server logic in `imposter_api.py`; `imposter_words.py` stays server-only. The separate Pages repository uses `deploy/imposter-pages.yml` and the existing Render API.

## Attribution

Board-generation logic adapted from KodeNames (MIT); see `THIRD_PARTY_LICENSE.md`. Bundled `scripts/seedrandom.js` includes David Bau's MIT license. No original analytics or backend services are included.

DM Sans, Noto Sans Gujarati, and Playfair Display are bundled under their SIL Open Font Licenses in `styles/fonts/`.
