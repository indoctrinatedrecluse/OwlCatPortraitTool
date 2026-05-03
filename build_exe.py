import argparse
import glob
import hashlib
import os
import shutil
import re
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
ICON_FILE = ASSETS_DIR / "app_icon.ico"
VERSION_FILE = PROJECT_ROOT / "version_info.txt"
SHA_VERIFIER_EXE = "sha256sum.exe"
SHA_CHECKSUMS_FILE = "SHA256SUMS.txt"
CODESIGN_CERT_FILE = ASSETS_DIR / "codesign.crt"
CODESIGN_KEY_FILE = ASSETS_DIR / "codesign.key"
# Password can be set as an environment variable for security
CODESIGN_KEY_PASSWORD = os.environ.get("CODESIGN_KEY_PASSWORD", "")
TIMESTAMP_SERVER = "http://timestamp.digicert.com"


def initialize_local_config():
    return LocalConfigService.ensure_config_file(
        GlobalsService.GAME_CONFIGS,
        GlobalsService.PATHFINDER_KINGMAKER,
        GlobalsService.get_builtin_appdata_locallow_folder,
        path=CONFIG_FILE,
    )


def get_app_version():
    """Reads the version string from UIQtRender.py."""
    version_file_content = (PROJECT_ROOT / "UIQtRender.py").read_text(encoding="utf-8")
    version_match = re.search(r"^APP_VERSION\s*=\s*['\"]([^'\"]*)['\"]", version_file_content, re.M)
    if not version_match:
        raise RuntimeError("Unable to find version string in UIQtRender.py.")
    return version_match.group(1)


def update_version_info_file(app_version):
    """Creates or updates version_info.txt with the current app version."""
    version_parts = list(map(int, app_version.split(".")))
    while len(version_parts) < 4:
        version_parts.append(0)
    version_tuple_str = str(tuple(version_parts[:4]))

    content = f"""
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={version_tuple_str},
    prodvers={version_tuple_str},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', 'Owlcat Portrait Tool'),
          StringStruct('FileDescription', 'Owlcat Portrait Tool'),
          StringStruct('FileVersion', '{app_version}'),
          StringStruct('InternalName', '{APP_NAME}'),
          StringStruct('OriginalFilename', '{APP_NAME}.exe'),
          StringStruct('ProductName', 'Owlcat Portrait Tool'),
          StringStruct('ProductVersion', '{app_version}')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    VERSION_FILE.write_text(content.strip(), encoding="utf-8")
    print(f"Updated {VERSION_FILE.name} with version {app_version}")


def _ensure_sha_verifier_exists():
    """Warn if the SHA verifier doesn't exist."""
    verifier_path = ASSETS_DIR / SHA_VERIFIER_EXE
    if not verifier_path.exists():
        print(f"Warning: SHA verifier '{verifier_path}' not found.")
        print("The release package will not include the verifier executable.")


def find_signtool():
    """Find signtool.exe in the Windows Kits directory."""
    if sys.platform != "win32":
        return None

    # Path for Windows 10/11 SDK
    base_path = Path(os.environ.get("ProgramFiles(x86)"), "Windows Kits", "10", "bin")
    if not base_path.exists():
        return None

    # Find the latest version of the SDK bin folder
    sdk_versions = sorted([p for p in base_path.glob("*.*.*.*") if p.is_dir()], reverse=True)
    if not sdk_versions:
        return None

    for version_path in sdk_versions:
        signtool_path = version_path / "x64" / "signtool.exe"
        if signtool_path.exists():
            return str(signtool_path)

    return None


def sign_executable(executable_path):
    """Sign the given executable with the self-signed certificate."""
    if not CODESIGN_CERT_FILE.exists() or not CODESIGN_KEY_FILE.exists():
        print("Info: Code signing certificate/key not found. Skipping signing.")
        return

    signtool_path = find_signtool()
    if not signtool_path:
        print("Warning: signtool.exe not found. Cannot sign the executable.")
        print("         Please install the Windows SDK.")
        return

    print(f"Signing executable: {executable_path}")

    # signtool requires a .pfx file. We'll create one from the .crt and .key.
    pfx_file = ASSETS_DIR / "codesign.pfx"
    openssl_command = [
        "openssl", "pkcs12", "-export",
        "-out", str(pfx_file),
        "-inkey", str(CODESIGN_KEY_FILE),
        "-in", str(CODESIGN_CERT_FILE),
        "-passout", "pass:",  # Use an empty password for the PFX file
    ]

    try:
        subprocess.run(openssl_command, check=True, capture_output=True, text=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print("Error: Failed to create PFX file using openssl.")
        print("       Please ensure openssl is installed and in your PATH.")
        if isinstance(e, subprocess.CalledProcessError):
            print(f"       Stderr: {e.stderr}")
        return

    sign_command = [
        signtool_path, "sign", "/f", str(pfx_file), "/p", "", "/tr",
        TIMESTAMP_SERVER, "/td", "sha256", "/fd", "sha256", str(executable_path),
    ]

    try:
        subprocess.run(sign_command, check=True, capture_output=True, text=True)
        print("Successfully signed the executable.")
    except subprocess.CalledProcessError as e:
        print(f"Error: Failed to sign the executable.\n{e.stderr}")
    finally:
        if pfx_file.exists():
            pfx_file.unlink()


def copy_verifier_to_release(release_content_path):
    """Copy the SHA verifier from assets to the release folder if it exists."""
    source_path = ASSETS_DIR / SHA_VERIFIER_EXE
    if not source_path.exists():
        print(f"Info: SHA verifier not found at {source_path}. Skipping copy.")
        return
 
    dest_path = release_content_path / SHA_VERIFIER_EXE
    shutil.copy(source_path, dest_path)
    print(f"Copied SHA verifier to {dest_path}")

def calculate_and_write_sha(release_content_path):
    """Calculate SHA256 for all files in the release and write to a checksum file."""
    checksums = []
    checksum_file_path = RELEASE_DIR / SHA_CHECKSUMS_FILE
    files_to_hash = sorted(
        [p for p in release_content_path.rglob("*") if p.is_file() and p.name != SHA_CHECKSUMS_FILE]
    )

    for file_path in files_to_hash:
        sha256_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
        relative_path = file_path.relative_to(release_content_path)
        checksums.append(f"{sha256_hash} *{relative_path.as_posix()}")

    checksum_file_path.write_text("\n".join(checksums) + "\n", encoding="utf-8")
    print(f"Generated SHA256 checksums at {checksum_file_path}")


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
        f"{CONFIG_FILE.name}{';' if sys.platform == 'win32' else ':'}.",
    ]
    if ASSETS_DIR.is_dir():
        command.extend([
            "--add-data",
            f"{ASSETS_DIR.name}{';' if sys.platform == 'win32' else ':'}assets",
        ])
    if ICON_FILE.is_file():
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


def package_release(app_version, onefile=False):
    executable_path = get_built_executable_path(onefile=onefile)
    if not executable_path.exists():
        raise FileNotFoundError(f"Built executable not found: {executable_path}")

    archive_base_name = f"{APP_NAME}-v{app_version}-windows"
    archive_base_path = RELEASE_DIR / archive_base_name

    if archive_base_path.with_suffix(".zip").exists():
        archive_base_path.with_suffix(".zip").unlink()

    if onefile:
        # This logic is simple and primarily supports the folder build used by CI.
        package_root = RELEASE_DIR
        base_dir_to_archive = "."
    else:
        package_root = RELEASE_DIR
        base_dir_to_archive = APP_NAME

    created_archive = shutil.make_archive(
        str(archive_base_path),
        "zip",
        root_dir=package_root,
        base_dir=base_dir_to_archive,
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

    app_version = get_app_version()
    update_version_info_file(app_version)
    initialize_local_config()

    if not ASSETS_DIR.is_dir():
        print(f"Warning: Assets directory not found at '{ASSETS_DIR}'.")
        print("The application icon and other assets will be missing from the build.")
    else:
        _ensure_sha_verifier_exists()

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

    if sys.platform == "win32":
        sign_executable(output_path)

    if onefile:
        release_content_path = RELEASE_DIR
    else:
        release_content_path = RELEASE_DIR / APP_NAME

    copy_verifier_to_release(release_content_path)
    calculate_and_write_sha(release_content_path)

    if smoke_test:
        smoke_test_executable(onefile=onefile)

    if package:
        package_path = package_release(app_version, onefile=onefile)
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
