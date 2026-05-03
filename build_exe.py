import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import GlobalsService
import LocalConfigService


PROJECT_ROOT = Path(__file__).resolve().parent
ENTRYPOINT = PROJECT_ROOT / "UIQtRender.py"
APP_NAME = "OwlcatPortraitTool"
BUILD_DIR = PROJECT_ROOT / "build"
DIST_DIR = PROJECT_ROOT / "dist"
RELEASE_DIR = PROJECT_ROOT / "release"
SPEC_FILE = PROJECT_ROOT / f"{APP_NAME}.spec"
CONFIG_FILE = PROJECT_ROOT / LocalConfigService.CONFIG_FILE_NAME
ASSETS_DIR = PROJECT_ROOT / "assets"
ICON_FILE = ASSETS_DIR / "OwlcatPortraitTool.ico"
VERSION_FILE = PROJECT_ROOT / "version_info.txt"
RELEASE_PACKAGE = RELEASE_DIR / f"{APP_NAME}.zip"


def initialize_local_config():
    return LocalConfigService.ensure_config_file(
        GlobalsService.GAME_CONFIGS,
        GlobalsService.PATHFINDER_KINGMAKER,
        GlobalsService.get_builtin_appdata_locallow_folder,
        path=CONFIG_FILE,
    )


def build_pyinstaller_command(onefile=False):
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        APP_NAME,
        "--windowed",
        "--noconfirm",
        "--clean",
        "--distpath",
        str(RELEASE_DIR),
        "--workpath",
        str(BUILD_DIR),
        "--specpath",
        str(PROJECT_ROOT),
        "--add-data",
        f"{CONFIG_FILE}{';' if sys.platform == 'win32' else ':'}.",
    ]
    if ICON_FILE.exists():
        command.extend(["--icon", str(ICON_FILE)])
    if VERSION_FILE.exists():
        command.extend(["--version-file", str(VERSION_FILE)])

    if onefile:
        command.append("--onefile")
    else:
        command.extend(["--contents-directory", "."])

    command.append(str(ENTRYPOINT))
    return command


def remove_build_outputs():
    for path in (BUILD_DIR, DIST_DIR, RELEASE_DIR):
        if path.exists():
            shutil.rmtree(path)

    if SPEC_FILE.exists():
        SPEC_FILE.unlink()


def get_built_executable_path(onefile=False):
    if onefile:
        return RELEASE_DIR / f"{APP_NAME}.exe"

    return RELEASE_DIR / APP_NAME / f"{APP_NAME}.exe"


def package_release(onefile=False):
    executable_path = get_built_executable_path(onefile=onefile)
    if not executable_path.exists():
        raise FileNotFoundError(f"Built executable not found: {executable_path}")

    if RELEASE_PACKAGE.exists():
        RELEASE_PACKAGE.unlink()

    if onefile:
        package_root = executable_path.parent
        base_name = executable_path.stem
    else:
        package_root = executable_path.parent.parent
        base_name = executable_path.parent.name

    archive_base = RELEASE_DIR / base_name
    created_archive = shutil.make_archive(
        str(archive_base),
        "zip",
        root_dir=package_root,
        base_dir=base_name if not onefile else executable_path.name,
    )
    return Path(created_archive)


def smoke_test_executable(onefile=False):
    executable_path = get_built_executable_path(onefile=onefile)
    if not executable_path.exists():
        raise FileNotFoundError(f"Built executable not found: {executable_path}")

    subprocess.run([str(executable_path), "--smoke-test"], check=True)


def run_build(onefile=False, clean=True, dry_run=False, package=False, smoke_test=False):
    if not ENTRYPOINT.exists():
        raise FileNotFoundError(f"Application entrypoint not found: {ENTRYPOINT}")

    initialize_local_config()

    if clean:
        remove_build_outputs()

    command = build_pyinstaller_command(onefile=onefile)
    if dry_run:
        print(" ".join(command))
        return 0

    try:
        subprocess.run(command, cwd=PROJECT_ROOT, check=True)
    except ModuleNotFoundError as error:
        raise SystemExit(
            "PyInstaller is not installed. Run "
            f'"{sys.executable} -m pip install -r requirements.txt" first.'
        ) from error
    except subprocess.CalledProcessError as error:
        return error.returncode

    output_path = get_built_executable_path(onefile=onefile)

    if smoke_test:
        smoke_test_executable(onefile=onefile)

    if package:
        package_path = package_release(onefile=onefile)
        print(f"Packaged release: {package_path}")

    print(f"Built executable: {output_path}")
    return 0


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build Owlcat Portrait Tool into a Windows executable."
    )
    parser.add_argument(
        "--onefile",
        action="store_true",
        help="Build a single exe. Startup is usually slower than the default folder build.",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Reuse existing PyInstaller build folders instead of deleting them first.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the PyInstaller command without running it.",
    )
    parser.add_argument(
        "--package",
        action="store_true",
        help="Create a release zip after building.",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Run the packaged executable smoke test after building.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    raise SystemExit(
        run_build(
            onefile=args.onefile,
            clean=not args.no_clean,
            dry_run=args.dry_run,
            package=args.package,
            smoke_test=args.smoke_test,
        )
    )
