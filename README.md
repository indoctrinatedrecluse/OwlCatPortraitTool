# Owlcat Portrait Tool

This will be a portrait tool for Pathfinder games, with planned support for other Owlcat Games (Warhammer + Starfinder).

Current features include:

1. **Image Loading**:
    - Load from a direct image URL.
    - Load a local image file using the `File > Open Image...` menu or by dragging it onto the window.
    - Search for images by tags on a user-selectable booru site (Safebooru, Danbooru, etc.).
2. **Portrait Editor**:
    - Drag and zoom the image to position it within the required crop frame.
    - Export Small, Medium, and Fulllength portraits to a local folder or directly to the selected game's AppData portraits folder.
3. **Game Support**:
    - Switch between supported Owlcat games (Pathfinder, Warhammer) to use the correct portrait dimensions and save paths.
4. **Usability**:
    - Unsaved-change confirmation before leaving the portrait editor or closing the app.
    - "About" dialog with version info, author credit, and usage instructions.

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

### Code Signing (Optional)

The build script supports self-signing the Windows executable. While this does not grant "trusted publisher" status, it is better than an unsigned file.

1. **Generate Certificate**: Run the `generate_cert.sh` script inside the `assets` folder. This requires `openssl` to be installed.

    ```bash
    cd assets
    ./generate_cert.sh
    ```

    This creates `codesign.crt` (the certificate) and `codesign.key` (the private key).

2. **IMPORTANT**: Add the private key to your `.gitignore` file. It should never be committed to version control.
    `assets/codesign.key`

## Creating a Release (Automated)

The project includes a GitHub Actions workflow to automatically build and publish releases. Helper scripts are provided to make this process simple.

Your release workflow is:

1. **Update Changelog**: Add a new version header (e.g., `## v0.8.0`) and release notes to the top of `CHANGELOG.md`.

1. **Commit Changes**: Commit the updated changelog and any other code changes with your desired message.

    ```bash
    git add .
    git commit -m "feat: Add new feature for v0.8.0"
    ```

1. **Push and Release**: Run the `push_upstream.sh` script. This will automatically tag the release based on the changelog and push it to GitHub, triggering the automated build.

    ```bash
    ./push_upstream.sh
    ```

A few minutes after pushing, a new release with the packaged `.zip` file and release notes will appear in the Releases section of the repository.

After source changes, run `build_exe.py` again to rebuild the exe. The build
cleans old `build`, `dist`, and `release` outputs before creating a fresh
release folder. Use `--onefile` if you specifically want a single executable,
though the folder build usually starts faster for PyQt apps.

### Creating a Release Package

To create a distributable `.zip` file, use the `--package` flag:

```powershell
.\OwlcatPortraitToolVenv\Scripts\python.exe build_exe.py --package
```

This creates `release\OwlcatPortraitTool.zip`, which includes the application, a SHA256 verifier (`sha256sum.exe`), and a checksums file (`SHA256SUMS.txt`). You can use these to verify the integrity of the application files.

Useful build options:

```powershell
.\OwlcatPortraitToolVenv\Scripts\python.exe build_exe.py --onefile
.\OwlcatPortraitToolVenv\Scripts\python.exe build_exe.py --package
.\OwlcatPortraitToolVenv\Scripts\python.exe build_exe.py --no-clean
.\OwlcatPortraitToolVenv\Scripts\python.exe build_exe.py --dry-run
.\OwlcatPortraitToolVenv\Scripts\python.exe build_exe.py --smoke-test
```
