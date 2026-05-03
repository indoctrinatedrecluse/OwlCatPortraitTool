import hashlib
import subprocess
import zipfile

import pytest

import build_exe


@pytest.mark.parametrize("onefile", [True, False])
def test_build_script_packages_sha_files(onefile, monkeypatch, tmp_path):
    # --- Setup a fake project structure ---
    project_root = tmp_path
    monkeypatch.setattr(build_exe, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(build_exe, "RELEASE_DIR", project_root / "release")
    monkeypatch.setattr(build_exe, "ASSETS_DIR", project_root / "assets")
    monkeypatch.setattr(build_exe, "APP_NAME", "TestApp")
    monkeypatch.setattr(build_exe, "RELEASE_PACKAGE", build_exe.RELEASE_DIR / "TestApp.zip")

    # Create fake assets
    build_exe.ASSETS_DIR.mkdir()
    sha_verifier_path = build_exe.ASSETS_DIR / build_exe.SHA_VERIFIER_EXE
    sha_verifier_path.write_text("fake verifier")

    # Create a fake entrypoint
    (project_root / "UIQtRender.py").write_text("print('hello')")

    # --- Mock external processes ---
    def fake_subprocess_run(*args, **kwargs):
        # Simulate PyInstaller creating the output
        build_exe.RELEASE_DIR.mkdir(parents=True, exist_ok=True)
        if onefile:
            (build_exe.RELEASE_DIR / f"{build_exe.APP_NAME}.exe").write_text("fake onefile exe")
        else:
            release_app_dir = build_exe.RELEASE_DIR / build_exe.APP_NAME
            release_app_dir.mkdir(parents=True)
            (release_app_dir / f"{build_exe.APP_NAME}.exe").write_text("fake folder exe")
            (release_app_dir / "somedll.dll").write_text("fake dll")
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(build_exe.subprocess, "run", fake_subprocess_run)
    monkeypatch.setattr(build_exe, "remove_build_outputs", lambda: None)
    monkeypatch.setattr(build_exe, "initialize_local_config", lambda: None)
    monkeypatch.setattr(build_exe, "_ensure_sha_verifier_exists", lambda: None)

    # --- Run the build ---
    return_code = build_exe.run_build(onefile=onefile, package=True)
    assert return_code == 0

    # --- Assertions ---
    if onefile:
        release_content_path = build_exe.RELEASE_DIR
        expected_files_in_dir = [
            f"{build_exe.APP_NAME}.exe",
            build_exe.SHA_VERIFIER_EXE,
            build_exe.SHA_CHECKSUMS_FILE,
        ]
        expected_files_in_zip = expected_files_in_dir
    else:
        release_content_path = build_exe.RELEASE_DIR / build_exe.APP_NAME
        expected_files_in_dir = [
            f"{build_exe.APP_NAME}.exe",
            "somedll.dll",
            build_exe.SHA_VERIFIER_EXE,
            build_exe.SHA_CHECKSUMS_FILE,
        ]
        expected_files_in_zip = [f"{build_exe.APP_NAME}/{f}" for f in expected_files_in_dir]

    # 1. Assert SHA verifier was copied
    copied_verifier = release_content_path / build_exe.SHA_VERIFIER_EXE
    assert copied_verifier.exists()
    assert copied_verifier.read_text() == "fake verifier"

    # 2. Assert SHA checksums file was created and is correct
    checksum_file = release_content_path / build_exe.SHA_CHECKSUMS_FILE
    assert checksum_file.exists()

    lines = checksum_file.read_text().strip().split("\n")
    assert len(lines) == len(expected_files_in_dir) - 1

    hashes = {name: sha for sha, name in (line.split(" *") for line in lines)}

    for f in expected_files_in_dir:
        if f == build_exe.SHA_CHECKSUMS_FILE:
            continue
        expected_hash = hashlib.sha256((release_content_path / f).read_bytes()).hexdigest()
        assert hashes[f] == expected_hash

    # 3. Assert ZIP package was created and contains all files
    zip_path = build_exe.RELEASE_DIR / "TestApp.zip"
    assert zip_path.exists()

    with zipfile.ZipFile(zip_path, "r") as zf:
        zip_contents = zf.namelist()
        assert sorted(zip_contents) == sorted(expected_files_in_zip)