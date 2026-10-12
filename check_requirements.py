"""Check every pinned line of a requirements.txt against PyPI.

Usage:
    python check_requirements.py [path/to/requirements.txt]

Reports:
  1. Dependencies checked  - number of dependency lines in the file
  2. Packages not on PyPI  - the package name does not exist
  3. Versions not on PyPI  - the package exists, but the pinned version does not
  4. Oldest pinned release - among lines where package and version both exist,
                             by the upload_time of the first file under "urls"
"""

import json
import re
import sys
import urllib.error
import urllib.request

PYPI_URL = "https://pypi.org/pypi/{}/json"
PYPI_VERSION_URL = "https://pypi.org/pypi/{}/{}/json"

# name[extras] == version   (env markers after ";" and comments after "#" are stripped first)
LINE_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*(?:==\s*([^\s,]+))?")


def fetch_json(url):
    """Return parsed JSON, or None if PyPI answers 404."""
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return None
        raise


def parse_line(line):
    """Return (name, version-or-None) for a dependency line, or None to skip it."""
    line = line.split("#", 1)[0].split(";", 1)[0].strip()
    if not line or line.startswith("-"):  # blank, comment, or pip option like -r / -e
        return None
    match = LINE_RE.match(line)
    if not match:
        return None
    return match.group(1), match.group(2)


def listing(items):
    """Name the offending lines after the count, e.g. " (pyyam)"."""
    return f" ({', '.join(items)})" if items else ""


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "requirements.txt"
    with open(path, encoding="utf-8") as f:
        deps = [d for d in map(parse_line, f) if d]

    missing_packages = []
    missing_versions = []
    oldest = None  # (upload_time, name, version)

    for name, version in deps:
        # Step 1: https://pypi.org/pypi/<name>/json -> the package, 404 if it does not exist.
        if fetch_json(PYPI_URL.format(name)) is None:
            missing_packages.append(name)
            continue
        if version is None:  # unpinned line: nothing more to check
            continue

        # Step 2: https://pypi.org/pypi/<name>/<version>/json -> one release, 404 if it does not exist.
        release = fetch_json(PYPI_VERSION_URL.format(name, version))
        if release is None:
            missing_versions.append(f"{name}=={version}")
            continue

        # "urls" lists the release's files, each with an upload_time; use the first one.
        urls = release.get("urls") or []
        if urls:
            upload_time = urls[0]["upload_time"]
            if oldest is None or upload_time < oldest[0]:
                oldest = (upload_time, name, version)

    print(f"Dependencies Checked:{len(deps)}")
    print(f"Packages not on PyPI: {len(missing_packages)}" + listing(missing_packages))
    print(f"Versions not on PyPI: {len(missing_versions)}" + listing(missing_versions))
    if oldest:
        upload_time, name, version = oldest
        print(f"Oldest pinned release: {name}=={version} ({upload_time[:4]})")
    else:
        print("Oldest pinned release: none")


if __name__ == "__main__":
    main()
