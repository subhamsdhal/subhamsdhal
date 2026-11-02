#!/usr/bin/env python3
"""Maintain a public-only project index in the profile README.

This script reads public metadata from GitHub's public API.
It never opens or changes any project repository.
Only the marked section of this profile README may be rewritten.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
import json

OWNER = "subhamsdhal"
README = Path("README.md")
START = "<!-- AUTO-PUBLIC-PROJECTS:START -->"
END = "<!-- AUTO-PUBLIC-PROJECTS:END -->"
FEATURED = {"urbangraph-intelligence", "ams-asset-management-system"}
# Encoded to keep excluded institution names out of repository text.
EXCLUDED_NAME_HEX = (
    "706d6563",
    "696974207061746e61",
    "706172616c61206d61686172616a61",
)
EXCLUDED_TERMS = tuple(bytes.fromhex(value).decode("ascii") for value in EXCLUDED_NAME_HEX)


def permitted_title(name: str) -> bool:
    """Keep unwanted institution references out of the rendered profile."""
    normalized = re.sub(r"[^a-z0-9]+", " ", name.casefold()).strip()
    return not any(term in normalized for term in EXCLUDED_TERMS)


def public_repositories() -> list[dict]:
    """Use the public-user API; do not request private repository access."""
    results: list[dict] = []
    page = 1
    while True:
        address = (
            f"https://api.github.com/users/{OWNER}/repos"
            f"?type=public&sort=updated&direction=desc&per_page=100&page={page}"
        )
        request = Request(
            address,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "public-portfolio-profile-updater",
            },
        )
        with urlopen(request, timeout=25) as response:
            batch = json.load(response)
        if not isinstance(batch, list):
            raise RuntimeError("GitHub returned an unexpected repository response.")
        results.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return results


def additional_projects(repositories: list[dict]) -> list[dict]:
    accepted: list[dict] = []
    seen: set[str] = set()
    for repo in repositories:
        name = repo.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        key = name.casefold()
        if (
            repo.get("private") is not False
            or repo.get("visibility", "public") != "public"
            or repo.get("fork", False)
            or repo.get("archived", False)
            or key in FEATURED
            or key == OWNER
            or key in seen
            or not permitted_title(name)
        ):
            continue
        seen.add(key)
        accepted.append(repo)
    return accepted


def build_section(repositories: list[dict]) -> str:
    projects = additional_projects(repositories)
    if not projects:
        return f"{START}\n{END}"

    rows = [
        "### 🌐 More public projects",
        "",
        "Additional projects are listed automatically as they become public.",
        "",
        "| Project | Primary language |",
        "| --- | --- |",
    ]
    for repo in projects:
        name = repo["name"]
        url = f"https://github.com/{OWNER}/{quote(name, safe='')}"
        display_name = html.escape(name, quote=True)
        language = repo.get("language")
        display_language = html.escape(language, quote=True) if isinstance(language, str) else "—"
        rows.append(f"| <a href=\"{url}\">{display_name}</a> | {display_language} |")

    return f"{START}\n" + "\n".join(rows) + f"\n{END}"


def main() -> None:
    original = README.read_text(encoding="utf-8")
    if original.count(START) != 1 or original.count(END) != 1:
        raise RuntimeError("Profile README is missing unique update markers.")
    begin = original.index(START)
    finish = original.index(END, begin) + len(END)

    section = build_section(public_repositories())
    updated = original[:begin] + section + original[finish:]
    if updated != original:
        README.write_text(updated, encoding="utf-8")
        print("Updated the public projects section.")
    else:
        print("Public project list already up to date.")


if __name__ == "__main__":
    main()
