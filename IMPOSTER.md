# Imposter: how the game works

Play at https://ramobadha.github.io/imposter/ or choose **Games → Imposter** from either existing game. For local development, run `python build.py` and `python server.py`, then open `/imposter/`.

## What the app does

The app gathers players in a private room, randomly selects imposters, and deals private words. Clues, discussion, voting, elimination, and deciding the winner happen verbally. There is no automated vote or score system.

Each person needs their own browser/device. The host is a player too. All words and their short explanatory meanings are currently in English; there are 60 original related-word pairs. Words are assigned on the server and the bank is not downloaded by the browser.

## The two modes

1. **Different word:** ordinary players all get the same word and meaning. All imposters get the other word from a related pair, such as two kinds of drink. Nobody is explicitly told whether they are ordinary or an imposter. They discover the difference through the conversation. The pair's direction is randomized.
2. **No word:** ordinary players all get the same word and meaning. Imposters get no word or meaning and see “You are the imposter.” They must listen and bluff. No category hint is given.

## Player counts and research

The supported range is **3–20 players**, including the host. Try **4–10** for your first game so everyone gets time to speak.

| Players | Recommended imposters |
| --- | --- |
| 3–6 | 1 |
| 7–11 | 2 |
| 12–20 | 3 |

These thresholds are our configurable starting defaults, not published official ratios or a guarantee of balance. The host may choose any positive number below half the player count. Recommendation updates when people join or are removed.

Research: [Yanstar Studio's official Undercover rules](https://www.yanstarstudio.com/undercover-how-to-play), checked 2026-10-02, supports 3–20 players, related secret words, a no-word role, and adjusting role counts. That game supplies a close precedent for both requested modes. Its exact role-count algorithm is not published there. We use only the two requested modes and keep play verbal.

## From invitation to next round

1. The host enters a name and chooses **Host a room**. A private link is created and the host joins automatically.
2. The host selects **Copy invite** and sends the link. Each guest opens it, enters a unique display name, and joins. If clipboard access is unavailable, a selectable link appears.
3. The lobby lists everyone. Names are 1–30 characters. Duplicate names are rejected, ignoring case. The host can remove an accidental/absent entry before dealing; a removed player can rejoin with the invitation, so removal is not a ban.
4. With at least three players, the host chooses a mode and count, then selects **Deal the secrets**. Joining and removing players are now locked. A random subset becomes imposters. A new related pair is selected, without repeating a pair within that room until all 60 have been used.
5. Every joined device starts with a face-down card. **Show my secret** displays only that player's assignment; **Hide my secret** covers it again. Switching browser tabs or hiding the page covers the card. Refreshing the original room URL restores the same assignment and starts covered.
6. Players give short clues, discuss, and vote aloud. The app doesn't record eliminated players. They should stop speaking/voting according to your group's rules.
7. When the group is finished, the host chooses **End round & reveal everyone** and confirms. All devices see each name, role, and assigned word, plus the word meanings. There is no automatic winner announcement because the app did not track your votes.
8. **Reopen lobby · next round** clears the previous round's assignments from room state, keeps the players and invitation, and allows new joins/removals. Deal again for fresh random roles and words. Unlike Empire, there is no three-minute timer or automatic deletion after reveal.

## Suggested verbal house rules

Go around the table once giving a short clue without saying the secret word. Discuss, then vote out one person. On a tie, give another clue and vote again. Repeat until the group believes the round is over. Suggested win conditions: ordinary players eliminate all imposters; imposters survive until their remaining number equals that of ordinary players. For no-word mode, optionally agree before starting that an eliminated imposter gets one last chance to guess the ordinary word. These are house rules; the website cannot verify or enforce them. Reveal on the host's screen only when all voting is finished, because the reveal exposes everyone at once.

## Privacy, rooms, and failures

- The invitation permits access to that room, not host controls. Only the host's separate browser key can start, end, reopen, or remove players. Never share your browser storage keys.
- During play, even the host receives only their own word. Other players' keys, words, and roles are excluded from responses. Different-word mode also omits your role from your own response.
- Browser storage identifies participants; there are no accounts. Another browser or cleared storage counts as another person. Anyone with the invite can forward it or join while the lobby is open. This is intended for trusted groups.
- Refresh preserves membership and hosting if browser storage is available. If storage is blocked, keys last only for the current visit. Save your invite before leaving; the Games menu opens each game's home page and does not carry rooms between games.
- A connection failure hides the visible secret, keeps the latest assignment in memory, and disables host controls until reconnection. It does not create new local roles. A failed response may have followed a successful action; the next state refresh reconciles it. Round revisions prevent a duplicate deal from rerandomizing an active round.
- The separate Render service is required. The first request after idle may take a minute. Rooms expire seven days after creation, and the free server's temporary storage can lose rooms on restart/deployment. An unavailable room needs a new invitation. Expired data is inaccessible and is purged when a new Imposter room is created.
- ClueGrid and Empire rooms remain separate. Switching games does not automatically close any room.

## Maintainer notes

Frontend: `imposter/`. API: `imposter_api.py`. Server-only words: `imposter_words.py`. API and existing games share the Flask service and SQLite file, with a separate Imposter table. The `ramobadha/imposter` repository deploys `dist/imposter/` using `deploy/imposter-pages.yml`, building source from this repository. Rerun its workflow for frontend updates and Empire's workflow after navigation edits. No new backend service or root options page is required.

Run `python -m unittest discover -s tests -p "test_*.py"` for API authorization, private responses, validation, room isolation, expiration, and concurrency checks. `python tests/imposter_browser.py` exercises separate host/guest devices and both modes against a local server on port 8896 (override `IMPOSTER_TEST_URL`).
