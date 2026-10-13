#!/usr/bin/env python3
"""Check diagram claims against source code and write evidence.json.

Usage: evidence.py <claims.json> <out evidence.json> [--scope "origin/main; no production access"]
       evidence.py --selfcheck          (needs git >= 2.24)

evidence.json = {"date", "scope", "heads": {label: sha}, "sources": [claim + status, sha256, reason?]}.
Non-ok claims are also printed one per line, so you can fix them without opening the file.

claims.json: [{"claim": "gateway drops pickup_days",
               "file": "/abs/path/in/repo/handler.go", "line": 69, "needle": "PickupDays",
               "ref": "origin/main"}, ...]

`ref` is optional. With it, the file is read via `git show <ref>:<path>` and that ref's SHA is
pinned — no checkout needed. Without it, the working tree is read and HEAD is pinned; a file with
uncommitted changes is marked "dirty", because HEAD would not contain what was checked.

Code outside git is accepted: its head is "no-git" and the per-file sha256 is the pin.

Status per claim: "ok"; "moved" (needle found elsewhere — `found_line` is the nearest, fix the
reference); "missing" (file or needle absent — the claim is wrong); "dirty"; "untracked"
(gitignored or never committed — HEAD does not contain it). A malformed claim is "missing" with a
`reason`; the rest still run. A needle that also matches other lines gets `also_at`. Anything but "ok"
exits 1. Each file's sha256 is recorded so a later reader can tell whether the code changed.
"""
import datetime
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def git(repo_dir, *args, text=True):
    r = subprocess.run(["git", "-C", str(repo_dir), *args], capture_output=True, text=text)
    if r.returncode:
        return None
    return r.stdout.strip() if text else r.stdout


MARKERS = ("package.json", "pyproject.toml", "go.mod", "Cargo.toml", "composer.json", "pom.xml", "build.gradle")


# Fallback for code with no package manifest (plain script folders, installed skills).
DOC_MARKERS = ("README.md", "README", "LICENSE", "SKILL.md")


def project_dir(directory):
    """Nearest ancestor with a project manifest (else a README/LICENSE) — names non-git code by
    project, not by subfolder."""
    for markers in (MARKERS, DOC_MARKERS):
        for d in (directory, *directory.parents):
            if any((d / m).exists() for m in markers):
                return d
    return directory


def main_repo(root):
    # Relative ('.git') in a main checkout, absolute in worktrees/submodules; -C root makes both resolvable.
    common = (Path(root) / (git(root, "rev-parse", "--git-common-dir") or ".git")).resolve()
    # Submodules keep their git dir in <super>/.git/modules/<name>; their own root is the repo.
    return common.parent if common.name == ".git" else Path(root)


def repo_label(directory):
    """'api' for the main checkout, 'api:TICKET-1' for a worktree — worktree dirs share names across repos."""
    root = git(directory, "rev-parse", "--show-toplevel")
    if not root:
        return project_dir(directory).name, None
    main = main_repo(root)
    name = main.name if main == Path(root) else f"{main.name}:{Path(root).name}"
    return name, root


def bad_shape(c):
    """Reason a claim can't be checked at all, or None. Checked before any path or git call."""
    if not isinstance(c, dict):
        return "claim is not an object"
    if not isinstance(c.get("file"), str) or not c["file"]:
        return "no file"
    line = c.get("line")
    if isinstance(line, bool) or not isinstance(line, (int, float, str)) or not str(line).strip().isdecimal():
        return "no line" if line is None else f"line {line!r} is not a number"
    if not isinstance(c.get("needle", ""), str):
        return "needle is not a string"
    if c.get("ref") is not None and not isinstance(c["ref"], str):
        return "ref is not a string"  # a typo'd ref must not quietly pin HEAD
    return None


def check(claims, scope):
    heads, sources, bad = {}, [], 0
    for c in claims:
        reason = bad_shape(c)
        if reason:
            sources.append({"claim": c.get("claim") if isinstance(c, dict) else str(c)[:80],
                            "file": c.get("file") if isinstance(c, dict) else None, "line": None,
                            "status": "missing", "reason": reason})
            bad += 1
            continue
        # resolve(): git reports symlink-free roots (/tmp → /private/tmp on macOS).
        path = Path(c["file"]).expanduser().resolve()
        line, ref, needle = int(str(c["line"]).strip()), (c.get("ref") or "").strip(), c.get("needle", "")
        entry = {**c, "file": str(path), "line": line}
        label, root = repo_label(path.parent)
        raw = None
        if not needle.strip():
            reason = "empty needle verifies nothing"
        elif ref.startswith("-"):
            reason = f"ref {ref!r} looks like a git option"
        elif ref and not root:
            reason = f"ref {ref!r} given but the file is not in a git repo"
        elif ref:
            # Content comes from the ref, so label by repo, not by the worktree it was read through.
            label = f"{main_repo(root).name}@{ref}"
            # --end-of-options: a ref from claims.json must never be parsed as a git flag.
            sha = git(root, "rev-parse", "--short", "--end-of-options", f"{ref}^{{commit}}")
            if not sha:
                reason = f"ref {ref!r} does not resolve to a commit"
            else:
                heads.setdefault(label, sha)
                # as_posix(): git tree paths use '/', also on Windows.
                raw = git(root, "show", "--end-of-options", f"{ref}:{path.relative_to(root).as_posix()}", text=False)
                if raw is None:
                    reason = f"not in {ref}"
        elif path.is_file():
            raw = path.read_bytes()
            # Not a git repo → no SHA to pin; the per-file sha256 is the only pin.
            heads.setdefault(label, (git(root, "rev-parse", "--short", "HEAD") or "no-commits") if root else "no-git")
        else:
            reason = "no such file"
        entry["repo"] = label
        if raw is None:
            entry["status"] = "missing"
        else:
            entry["sha256"] = hashlib.sha256(raw).hexdigest()
            # split("\n"), not splitlines(): editors, grep -n and git count only \n (not \f, \x85, U+2028).
            hits = [i + 1 for i, l in enumerate(raw.decode("utf-8", "replace").split("\n")) if needle in l]
            if not hits:
                entry["status"], reason = "missing", "needle not in file"
            else:
                if len(hits) > 1:
                    # A generic needle can pin the wrong function; the author decides whether to tighten it.
                    entry["also_at"] = [h for h in hits if h != line]
                if line not in hits:
                    entry["status"] = "moved"
                    entry["found_line"] = min(hits, key=lambda h: abs(h - line))
                elif not ref and root and not git(root, "ls-files", "--", str(path)):
                    entry["status"] = "untracked"  # ignored or new: HEAD says nothing about this file
                elif not ref and root and git(root, "status", "--porcelain", "--", str(path)):
                    entry["status"] = "dirty"
                else:
                    entry["status"] = "ok"
        if reason:
            entry["reason"] = reason
        bad += entry["status"] != "ok"
        sources.append(entry)
    return {"date": datetime.date.today().isoformat(), "scope": scope,
            "heads": heads, "sources": sources}, bad


def load_claims(path):
    # utf-8-sig: editors on Windows save JSON with a BOM.
    claims = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(claims, list):
        sys.exit("claims.json must be a JSON list of claims")
    return claims

def _selfcheck():
    import os
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        repo = Path(d).resolve() / "my repo"
        repo.mkdir()
        # Isolated from the user's git config (commit signing, hooks).
        env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
        run = lambda *a: subprocess.run(["git", "-C", str(repo), *a], capture_output=True, check=True, env=env)
        run("init", "-q")
        run("config", "user.email", "t@t")
        run("config", "user.name", "t")
        (repo / "pre.txt").write_text("x\n")
        empty = check([{"claim": "c", "file": str(repo / "pre.txt"), "line": 1, "needle": "x"}], "s")[0]
        assert "no-commits" in empty["heads"].values(), empty["heads"]
        (repo / "a.py").write_text("def f():\n    return 1\n\x0c\ndef g():\n    return 1\n")
        (repo / ".gitignore").write_text("ign.py\n")
        (repo / "ign.py").write_text("x = 1\n")
        run("add", "a.py", ".gitignore")
        run("commit", "-qm", "c")
        a = str(repo / "a.py")
        claims = [
            {"claim": "ok", "file": a, "line": 4, "needle": "def g"},          # after a form feed
            {"claim": "moved", "file": a, "line": 1, "needle": "return 1"},
            {"claim": "missing", "file": a, "line": 1, "needle": "nope"},
            {"claim": "ambiguous", "file": a, "line": 2, "needle": "return 1"},
            {"claim": "ref", "file": a, "line": 4, "needle": "def g", "ref": " HEAD"},
            {"claim": "tree", "file": a, "line": 4, "needle": "def g", "ref": "HEAD^{tree}"},
            {"claim": "untracked", "file": str(repo / "ign.py"), "line": 1, "needle": "x = 1"},
            "not a dict",
            {"claim": "no file", "line": 1, "needle": "x"},
            {"claim": "bad line", "file": a, "line": "abc", "needle": "def"},
            {"claim": "bool line", "file": a, "line": True, "needle": "def"},
            {"claim": "int needle", "file": a, "line": 1, "needle": 5},
            {"claim": "superscript line", "file": a, "line": "\u00b2", "needle": "def"},
            {"claim": "falsy ref", "file": a, "line": 1, "needle": "def", "ref": 0},
        ]
        res, bad = check(claims, "s")
        st = [e["status"] for e in res["sources"]]
        assert st == ["ok", "moved", "missing", "ok", "ok", "missing", "untracked",
                      "missing", "missing", "missing", "missing", "missing", "missing", "missing"], st
        assert res["sources"][1]["found_line"] == 2 and res["sources"][1]["also_at"] == [2, 5]
        assert res["sources"][0]["line"] == 4 and res["sources"][3]["also_at"] == [5]
        assert "commit" in res["sources"][5]["reason"]
        assert any(k.endswith("@HEAD") for k in res["heads"]), res["heads"]
        assert bad == 11
        run("worktree", "add", "-q", str(Path(d) / "wt-T1"))
        wt = check([{"claim": "c", "file": str(Path(d) / "wt-T1" / "a.py"), "line": 4, "needle": "def g"}], "s")[0]
        assert "my repo:wt-T1" in wt["heads"], wt["heads"]
        plain = Path(d) / "plain-tool"                 # not git, no package manifest, only a README
        (plain / "scripts").mkdir(parents=True)
        (plain / "README.md").write_text("# tool\n")
        (plain / "scripts" / "run.py").write_text("print(1)\n")
        labels = check([{"claim": "c", "file": str(plain / "scripts" / "run.py"), "line": 1, "needle": "print"}], "s")[0]
        assert list(labels["heads"]) == ["plain-tool"], labels["heads"]
        (Path(d) / "claims.json").write_bytes("\ufeff[]".encode())   # BOM
        assert load_claims(Path(d) / "claims.json") == []
    print("selfcheck ok")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("claims", nargs="?")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--scope", default="local checkout; no production access")
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    if a.selfcheck:
        _selfcheck()
        sys.exit()
    if not (a.claims and a.out):
        ap.error("claims and out are required")
    result, bad = check(load_claims(a.claims), a.scope)
    Path(a.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = {s: sum(e["status"] == s for e in result["sources"]) for s in ("ok", "moved", "missing", "dirty", "untracked")}
    print(json.dumps({"evidence": a.out, "heads": result["heads"], **counts}, ensure_ascii=False))
    ambiguous = sum("also_at" in e for e in result["sources"])
    if ambiguous:
        print(f"ambiguous: {ambiguous} claim(s) have needles on other lines too (see also_at) — "
              "tighten only where another hit is in a different function")
    for e in result["sources"]:
        if e["status"] != "ok":
            hint = e.get("reason") or (f"found at line {e['found_line']}" if "found_line" in e else "")
            print(f"{e['status']}: {e.get('claim', '?')} — {e.get('file')}:{e['line'] if e['line'] is not None else '?'} {hint}".rstrip())
    sys.exit(1 if bad else 0)
