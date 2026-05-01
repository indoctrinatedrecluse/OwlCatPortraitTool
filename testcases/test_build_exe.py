import sys

import build_exe


def test_build_command_targets_current_entrypoint_and_default_folder_build():
    command = build_exe.build_pyinstaller_command()

    assert command[:3] == [sys.executable, "-m", "PyInstaller"]
    assert "--windowed" in command
    assert "--clean" in command
    assert "--distpath" in command
    assert str(build_exe.RELEASE_DIR) in command
    assert "--add-data" in command
    assert any(str(build_exe.CONFIG_FILE) in part for part in command)
    assert "--contents-directory" in command
    assert "." in command
    assert "--onefile" not in command
    assert command[-1] == str(build_exe.ENTRYPOINT)


def test_build_command_supports_onefile_builds():
    command = build_exe.build_pyinstaller_command(onefile=True)

    assert "--onefile" in command
    assert "--contents-directory" not in command


def test_clean_removes_release_outputs(tmp_path, monkeypatch):
    build_dir = tmp_path / "build"
    dist_dir = tmp_path / "dist"
    release_dir = tmp_path / "release"
    spec_file = tmp_path / "OwlcatPortraitTool.spec"

    for path in (build_dir, dist_dir, release_dir):
        path.mkdir()
        (path / "old.txt").write_text("old")

    spec_file.write_text("old")

    monkeypatch.setattr(build_exe, "BUILD_DIR", build_dir)
    monkeypatch.setattr(build_exe, "DIST_DIR", dist_dir)
    monkeypatch.setattr(build_exe, "RELEASE_DIR", release_dir)
    monkeypatch.setattr(build_exe, "SPEC_FILE", spec_file)

    build_exe.remove_build_outputs()

    assert not build_dir.exists()
    assert not dist_dir.exists()
    assert not release_dir.exists()
    assert not spec_file.exists()


def test_initialize_local_config_creates_dat_file(tmp_path, monkeypatch):
    config_file = tmp_path / "OwlcatPortraitTool.dat"
    monkeypatch.setattr(build_exe, "CONFIG_FILE", config_file)

    build_exe.initialize_local_config()

    assert config_file.exists()
    assert "Pathfinder Kingmaker" in config_file.read_text(encoding="utf-8")
