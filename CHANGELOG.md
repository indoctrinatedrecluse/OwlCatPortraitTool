# Changelog

All notable project changes are listed by commit.

## Commit 3 - Pending

### Added

- Added data-driven Owlcat game configuration through `GameConfig`, making future game support easier to add from one central config list.
- Added game options for `Warhammer 40k: Rogue Trader` and `Warhammer 40k: Dark Heresy`.
- Added per-game AppData folder handling for Pathfinder Kingmaker, Pathfinder Wrath of the Righteous, Rogue Trader, and Dark Heresy.
- Added `LocalConfigService.py` to manage local `OwlcatPortraitTool.dat` settings.
- Added automatic `.dat` initialization during executable builds.
- Added missing-folder validation for game export paths, with a warning popup and folder picker fallback.
- Added tests for local config creation, config normalization, game cycling, Warhammer game paths, build config initialization, and settings fallback behavior.

### Changed

- Replaced the settings game selector with a `Target Game` button that cycles through configured games.
- Updated export buttons to clearly separate local and game exports:
  - `Export To Local Output`
  - `Export To AppData/Portraits`
- Updated game settings to load and save per-game AppData paths from `OwlcatPortraitTool.dat`.
- Updated README documentation to mention local per-game settings storage.
- Updated `.gitignore` to exclude local `OwlcatPortraitTool.dat` files.

### Verified

- Full test suite passed with `62 passed`.

## Commit 2 - 4eec7b1

**Changed runnable to exe, added a couple error handling situations**

### Added

- Added PyInstaller build support through `build_exe.py`.
- Added `requirements.txt` as the standard dependency install file.
- Added `RequestHeaders.py` for shared image and JSON request headers.
- Added README instructions for building the Windows executable.
- Added async search preview loading with bounded concurrency.
- Added retry handling and failure messaging for image previews.
- Added stale-preview protection so old search results cannot update the current UI.
- Added unsaved-change tracking in the portrait editor.
- Added close and tab-change confirmation prompts for unsaved portrait edits.
- Added tests for build command generation, request headers, preview loading behavior, dirty editor state, and close/tab-change confirmations.

### Changed

- Updated `runproject.sh` to build and launch the packaged executable from `release/`.
- Updated URL and search image requests to use browser-like headers.
- Updated tag search preview rendering to load previews in worker threads instead of blocking the UI.
- Updated `.gitignore` to ignore generated executables, release packages, PyInstaller artifacts, build outputs, and local tool caches.

## Commit 1 - 17c015b

**First Commit**

### Added

- Added the initial PyQt portrait tool application.
- Added URL input and validation for HTTP/HTTPS image links.
- Added portrait loading, crop positioning, and export from the portrait editor.
- Added Small, Medium, and Fulllength portrait generation.
- Added local output folder export.
- Added game AppData portrait folder export.
- Added tag search support for supported booru APIs.
- Added global game settings for Pathfinder Kingmaker and Pathfinder Wrath of the Righteous.
- Added portrait dimension handling for supported Pathfinder games.
- Added setup scripts and dependency notes.
- Added pytest configuration and test coverage for globals, search, URL handling, and UI behavior.
