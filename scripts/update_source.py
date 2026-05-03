"""Fetch upstream GitHub releases and update source.json for AltStore.
doc: https://faq.altstore.io/developers/make-a-source
repo: https://github.com/bggRGjQaUbCoE/PiliPlus
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SOURCE_REPO = "bggRGjQaUbCoE/PiliPlus"
SOURCE_JSON = Path("source.json")

REPO_NAME = "PiliPlus"
REPO_SUBTITLE = "Unofficial PiliPlus AltStore source"
REPO_DESCRIPTION = "Auto-updated AltStore source for PiliPlus"
REPO_ICON_URL = "https://github.com/bggRGjQaUbCoE/PiliPlus/raw/main/assets/images/logo/logo.png"
REPO_SCREENSHOT1 = "https://raw.githubusercontent.com/bggRGjQaUbCoE/PiliPlus/refs/heads/main/assets/screenshots/home.png"
REPO_SCREENSHOT2 = "https://raw.githubusercontent.com/bggRGjQaUbCoE/PiliPlus/refs/heads/main/assets/screenshots/bangumi.png"
REPO_SCREENSHOT3 = "https://raw.githubusercontent.com/bggRGjQaUbCoE/PiliPlus/refs/heads/main/assets/screenshots/dynamic.png"
REPO_WEBSITE = "https://github.com/bebound/PiliPlus-AltStore-Repo"
REPO_TINT_COLOR = "#00AEEF"

APP_NAME = "PiliPlus"
APP_BUNDLE_ID = "com.bggRGjQaUbCoE.PiliPlus"
APP_DEVELOPER = "bggRGjQaUbCoE"
APP_SUBTITLE = "Latest PiliPlus release"
APP_DESCRIPTION = "PiliPlus iOS app builds from GitHub releases"
APP_TINT_COLOR = "#00AEEF"
APP_MIN_OS = "14.0"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def iso_datetime(value: str) -> str:
    """Return an ISO-8601 datetime string; fall back to *now* if empty."""
    if not value:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return value.replace(".000", "")


def short_date(value: str) -> str:
    """Return only the date portion (YYYY-MM-DD) of an ISO datetime."""
    return iso_datetime(value).split("T", 1)[0]


def extract_build_version(filename: str) -> str:
    """Extract build number from IPA filename like ``PiliPlus_ios_2.0.6+4915.ipa``."""
    if not filename:
        return ""
    match = re.search(r"\+(\d+)\.ipa$", filename, re.IGNORECASE)
    return match.group(1) if match else ""


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def init() -> dict:
    """Load existing ``source.json`` or bootstrap a fresh skeleton."""
    return {
        "name": REPO_NAME,
        "subtitle": REPO_SUBTITLE,
        "description": REPO_DESCRIPTION,
        "iconURL": REPO_ICON_URL,
        "website": REPO_WEBSITE,
        "tintColor": REPO_TINT_COLOR,
        "apps": [],
        "news": [],
    }


def new_app_entry() -> dict:
    """Return a fresh app dict with no versions."""
    return {
        "name": APP_NAME,
        "bundleIdentifier": APP_BUNDLE_ID,
        "developerName": APP_DEVELOPER,
        "subtitle": APP_SUBTITLE,
        "localizedDescription": APP_DESCRIPTION,
        "iconURL": REPO_ICON_URL,
        "screenshots": [REPO_SCREENSHOT1, REPO_SCREENSHOT2, REPO_SCREENSHOT3],
        "tintColor": APP_TINT_COLOR,
        "versions": [],
        "news": [],
    }


# ---------------------------------------------------------------------------
# GitHub Releases API
# ---------------------------------------------------------------------------

def fetch_releases() -> list[dict]:
    """Return all releases from the upstream repo, paginating through all pages."""
    releases: list[dict] = []
    url: str | None = f"https://api.github.com/repos/{SOURCE_REPO}/releases?per_page=100"

    while url:
        resp = requests.get(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "altstore-repo-updater",
            },
            timeout=30,
        )
        resp.raise_for_status()
        releases.extend(resp.json())

        # Follow the "next" link if present.
        url = resp.links.get("next", {}).get("url")

    return releases


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    data = init()

    data["apps"].append(new_app_entry())

    app = data["apps"][0]

    added = 0
    for release in fetch_releases():
        if release.get("draft") or release.get("prerelease"):
            continue

        tag = release.get("tag_name") or ""
        version = tag[1:] if tag.startswith("v") else tag
        if not version:
            continue

        assets = release.get("assets") or []
        ipa_assets = [
            a for a in assets if (a.get("name") or "").lower().endswith(".ipa")
        ]
        if not ipa_assets:
            continue

        for asset in ipa_assets:
            download_url = asset.get("browser_download_url", "")

            release_body = (
                    (release.get("body") or "").strip() or APP_DESCRIPTION
            )
            build_version = extract_build_version(asset.get("name") or "")

            version_item: dict = {
                "version": version,
                "date": short_date(release.get("published_at", "")),
                "localizedDescription": release_body,
                "downloadURL": download_url,
                "size": asset.get("size", 0),
                "minOSVersion": APP_MIN_OS,
            }
            if build_version:
                # Insert buildVersion right after version.
                version_item = {
                    "version": version,
                    "buildVersion": build_version,
                    "date": version_item["date"],
                    "localizedDescription": release_body,
                    "downloadURL": download_url,
                    "size": version_item["size"],
                    "minOSVersion": APP_MIN_OS,
                }

            app.setdefault("versions", []).append(version_item)
            added += 1

        # Add a news entry for this release.
        data.setdefault("news", []).append({
            "title": f"{APP_NAME} {version}",
            "identifier": f"release-{version}",
            "caption": release.get("name") or f"Version {version} released",
            "date": short_date(release.get("published_at", "")),
            "tintColor": APP_TINT_COLOR,
            "notify": True,
            "appID": APP_BUNDLE_ID,
            "url": f"https://github.com/{SOURCE_REPO}/releases/tag/{tag}",
        })

    # Sort versions by date (desc), then version string (desc).
    app["versions"] = sorted(
        app.get("versions", []),
        key=lambda v: (v.get("date", ""), v.get("version", "")),
        reverse=True,
    )

    # Sort news by date (desc).
    data["news"] = sorted(
        data.get("news", []),
        key=lambda n: n.get("date", ""),
        reverse=True,
    )

    SOURCE_JSON.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f'lasest version is {app["versions"][0]["version"]}')


if __name__ == "__main__":
    main()
