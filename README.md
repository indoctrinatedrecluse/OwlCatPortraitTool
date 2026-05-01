This will be a portrait tool for Pathfinder games, with planned support for other Owlcat Games (Warhammer + Starfinder).

Current features include:

1. URL input for HTTP/HTTPS image links, with image validation before loading.
2. Drag-to-position portrait cropping against the required full-length frame.
3. Export of Small, Medium, and Fulllength portrait files to a local output folder or the selected game's AppData portraits folder.
4. Tag search across supported booru APIs, with asynchronous preview loading and clickable results.
5. Settings for switching between supported Owlcat game portrait dimensions and AppData paths.
6. Unsaved-change confirmation before leaving the portrait editor or closing the app.

Per-game folder settings are stored locally in `OwlcatPortraitTool.dat`. The
build script initializes this file with default Owlcat AppData paths, and the
app updates it when you choose a custom game folder.

## Building the Windows exe

Install or refresh dependencies:

```powershell
.\OwlcatPortraitToolVenv\Scripts\python.exe -m pip install -r requirements.txt
```

Build the app:

```powershell
.\OwlcatPortraitToolVenv\Scripts\python.exe build_exe.py
```

The default build creates:

```text
release\OwlcatPortraitTool\OwlcatPortraitTool.exe
```

The default folder build places the required Python, PyQt, Pillow, requests,
and Windows runtime files in the same release folder as the exe. Keep the full
`release\OwlcatPortraitTool` folder together when moving the app.

After source changes, run `build_exe.py` again to rebuild the exe. The build
cleans old `build`, `dist`, and `release` outputs before creating a fresh
release folder. Use `--onefile` if you specifically want a single executable,
though the folder build usually starts faster for PyQt apps.

Useful build options:

```powershell
.\OwlcatPortraitToolVenv\Scripts\python.exe build_exe.py --onefile
.\OwlcatPortraitToolVenv\Scripts\python.exe build_exe.py --no-clean
.\OwlcatPortraitToolVenv\Scripts\python.exe build_exe.py --dry-run
```
