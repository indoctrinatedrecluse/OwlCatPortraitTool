# Changelog

All notable project changes are listed by commit.

## v0.5.1

### feat: Improve release automation and fix build script

- **Added**
  - **Build & Release**:
    - Added `push_upstream.sh` to fully automate the release tagging and push process. The script reads the version from the changelog, creates a Git tag, and pushes to GitHub to trigger the release workflow.
- **Changed**
  - **Documentation**:
    - Updated `README.md` to reflect the new, simplified, single-script release process and fix several Markdown formatting issues.
- **Fixed**
  - **Build**:
    - Fixed a `SyntaxError` in `build_exe.py` caused by a corrupted docstring, which was breaking the local build process.

## v0.5.0

### feat: Major UI/UX and backend overhaul

- **Added**
  - **UI/UX**:
    - Added a "File" menu with "Open Image...", "Recent Files", and "Exit" actions.
    - Added a "Help" menu with "Check for Updates" and "About" actions.
    - Added keyboard shortcuts: `Ctrl+O` (Open), `Ctrl+Q` (Exit), `Ctrl+P` (Paste Image).
    - Added a "Copy to Clipboard" button for the exported portrait path.
    - Added a "Clear" button to the Search tab.
    - Added a visual overlay for drag-and-drop image loading.
    - Added a colored asterisk `*` to the Portrait Editor tab to indicate unsaved changes.
  - **Search**:
    - Added pagination controls (Previous/Next buttons) to the Search tab.
    - Added support for more booru sites: Gelbooru, Yande.re, Derpibooru, HypnoHub, Tbib.
  - **Build & Release**:
    - Added a GitHub Actions workflow (`.github/workflows/create-release.yml`) to automate builds and releases.
    - The build script now generates a `SHA256SUMS.txt` file and includes a verifier (`sha256sum.exe`) in the release package.
- **Changed**
  - **Search**:
    - Refactored `SearchService` to use a modular, handler-based architecture for easier integration of new APIs.
    - Fixed tag search functionality for several booru sites by improving URL encoding and handling API-specific rules.
  - **Build**:
    - Fixed an import cycle that caused build failures.
    - Improved the build script's smoke test to catch startup errors.
    - Fixed `runproject.sh` to always rebuild the application, ensuring the latest changes are launched.
  - **UI**:
    - Refactored the Search tab's input area to use a `QFormLayout` for better alignment.

## v0.4.0

### feat: Add booru site switcher

- **Added**
  - Added a dropdown to the Search tab to allow selecting a specific booru site for tag searches.
  - The last-selected booru site is now saved in `OwlcatPortraitTool.dat` and restored on application start.
- **Changed**
  - Updated `SearchService` to query a single booru API instead of all of them simultaneously.
  - Updated tests to account for the new booru selection mechanism.

## v0.3.0

### feat: Add data-driven game config and Warhammer support

- **Added**
  - Added data-driven Owlcat game configuration through `GameConfig`, making future game support easier to add from one central config list.
  - Added game options for `Warhammer 40k: Rogue Trader` and `Warhammer 40k: Dark Heresy`.
  - Added per-game AppData folder handling for Pathfinder Kingmaker, Pathfinder Wrath of the Righteous, Rogue Trader, and Dark Heresy.
  - Added `LocalConfigService.py` to manage local `OwlcatPortraitTool.dat` settings.
  - Added automatic `.dat` initialization during executable builds.
  - Added missing-folder validation for game export paths, with a warning popup and folder picker fallback.
  - Added tests for local config creation, config normalization, game cycling, Warhammer game paths, build config initialization, and settings fallback behavior.
- **Changed**
  - Replaced the settings game selector with a `Target Game` button that cycles through configured games.
  - Updated export buttons to clearly separate local and game exports:
    - `Export To Local Output`
    - `Export To AppData/Portraits`
  - Updated game settings to load and save per-game AppData paths from `OwlcatPortraitTool.dat`.
  - Updated README documentation to mention local per-game settings storage.
  - Updated `.gitignore` to exclude local `OwlcatPortraitTool.dat` files.
- **Verified**
  - Full test suite passed with `62 passed`.

## Commit 2 - 4eec7b1

### Changed runnable to exe, added a couple error handling situations

- **Added**
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
- **Changed**
  - Updated `runproject.sh` to build and launch the packaged executable from `release/`.
  - Updated URL and search image requests to use browser-like headers.
  - Updated tag search preview rendering to load previews in worker threads instead of blocking the UI.
  - Updated `.gitignore` to ignore generated executables, release packages, PyInstaller artifacts, build outputs, and local tool caches.

## Commit 1 - 17c015b

### First Commit

- **Added**
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
