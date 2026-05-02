from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _requirement_names(path):
    names = set()
    for line in (REPO_ROOT / path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        names.add(line.split("==", 1)[0].split(">=", 1)[0].split(";", 1)[0])
    return names


def test_desktop_runtime_requirements_do_not_include_packaging_tools():
    runtime_names = _requirement_names("requirements-desktop.txt")
    build_names = _requirement_names("requirements-desktop-build.txt")

    assert "pyinstaller" not in runtime_names
    assert "pyinstaller-hooks-contrib" not in runtime_names
    assert "pyinstaller" in build_names
    assert "pyinstaller-hooks-contrib" in build_names


def test_flatpak_installs_only_runtime_requirements_into_app_prefix():
    manifest = (
        REPO_ROOT / "desktop/flatpak/app.simpleaircraft.Manager.yml"
    ).read_text(encoding="utf-8")

    assert (
        "python3 -m pip install --prefix=/app -r requirements.txt "
        "-r requirements-desktop.txt"
    ) in manifest
    assert "--prefix=/app -r requirements-build.txt" not in manifest
    assert "requirements-desktop-build.txt" not in manifest
    assert "python3 -m pip install --target=/tmp/sam-build-tools" in manifest
