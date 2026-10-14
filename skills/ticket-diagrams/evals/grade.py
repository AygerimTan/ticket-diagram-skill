#!/usr/bin/env python3
"""Grade pack runs: grade.py <iteration-dir> [--evals evals.json]. Writes grading.json per run.

Run layout: <iteration-dir>/eval-<id>-<name>/<config>/run-<n>/outputs/ (skill-creator's layout).
The eval id in the dir name selects `index_mode` (tabs | bundle | any) from evals.json.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

DISCLAIMER = re.compile(r"not a statement about|production|не подтвержд|не прод|не утвержден", re.I)
# International numbers only; add your country's local format if your data uses it.
# Also hits semver build tags (1.0.0+2024…) — check the evidence before failing a pack on it.
PHONE = re.compile(r"\+(?:[\s()-]*\d){10,}")
SOURCE = re.compile(r"\.[a-z0-9]{1,5}:\d+")


def grade(run, index_mode):
    out = run / "outputs"
    idx = out / "index.html"
    index = idx.read_text(encoding="utf-8", errors="replace") if idx.is_file() else ""
    exp = []

    def add(text, passed, evidence):
        exp.append({"text": text, "passed": bool(passed), "evidence": evidence})

    add("index.html exists", idx.is_file(), str(idx) if idx.is_file() else "missing")

    evs = [json.loads(e.read_text(encoding="utf-8")) for e in out.glob("evidence*.json")]
    srcs = [s for e in evs for s in e.get("sources", [])]
    bad = [s for s in srcs if s.get("status") != "ok"]
    add("evidence.json pins ≥5 claims to file:line, all ok", len(srcs) >= 5 and not bad,
        f"{len(srcs)} claims in {len(evs)} file(s), {len(bad)} not ok" if evs else "no evidence.json")

    specs = [p for p in out.glob("*.json") if '"diagram_type"' in p.read_text(errors="replace")[:400]]
    # A receipt counts only for the HTML as it is now: stale receipts from earlier rounds stay in checks/.
    passed_sha = set()
    for r in out.rglob("*.finalize-summary.json"):
        try:
            s = json.loads(r.read_text(encoding="utf-8"))
        except ValueError:  # a broken receipt must not stop grading of other runs
            continue
        if s.get("status") == "pass":
            passed_sha.add((s.get("artifact") or {}).get("sha256"))
    pages = [out / (json.loads(p.read_text(encoding="utf-8")).get("meta", {}).get("output")
                    or p.name.split(".")[0] + ".html") for p in specs]
    ok = [h for h in pages if h.is_file() and hashlib.sha256(h.read_bytes()).hexdigest() in passed_sha]
    add("every diagram's current HTML has a passing archify finalize", pages and len(ok) == len(pages),
        f"{len(ok)}/{len(pages)} pages")

    with_src = [p for p in specs if SOURCE.search(p.read_text(errors="replace"))]
    add("every diagram spec cites path:line itself", specs and len(with_src) == len(specs),
        f"{len(with_src)}/{len(specs)} specs cite path:line")

    # A bundle inlines whole pages, so read the note from the manifest when there is one.
    man = out / "manifest.json"
    try:
        manifest = json.loads(man.read_text(encoding="utf-8")) if man.is_file() else None
    except ValueError:
        manifest = None
    if not isinstance(manifest, dict):
        manifest = None
    note = str(manifest.get("note") or "") if manifest else index
    eras = manifest and manifest.get("eras")
    shas = re.findall(r"\b[0-9a-f]{7,12}\b", note)
    # Code outside git has head "no-git" (pinned by file hashes); read it from evidence, not prose.
    nogit = any(v in ("no-git", "no-commits") for e in evs for v in e.get("heads", {}).values())
    add("index note names commit SHAs (or code is pinned by file hashes)", bool(shas) or nogit,
        ", ".join(sorted(set(shas))[:4]) or ("no-git" if nogit else "none"))
    add("index note disclaims production/runs", DISCLAIMER.search(note),
        "found" if DISCLAIMER.search(note) else "no disclaimer")

    hits = [p.name for p in out.rglob("*") if p.suffix in (".json", ".html")
            and PHONE.search(p.read_text(errors="replace"))]
    add("no phone numbers copied into the pack", not hits, ", ".join(hits[:3]) or "none")

    if index_mode == "bundle":
        # "srcdoc"/"data-era" also sit in the tabs index's script; only the era buttons and the
        # missing docs=null tell a bundle apart.
        add("single-file bundle index" + (" with era switch" if eras else ""),
            index and "docs=null" not in index and (not eras or "<button data-era=" in index),
            f"{len(index)} bytes, inlined={'docs=null' not in index}, eras={bool(eras)}")
    elif index_mode == "tabs":
        add("light tabs index (iframe src, small file)", "docs=null" in index and len(index) < 50_000,
            f"{len(index)} bytes, inlined={'docs=null' not in index}")
    passed = sum(e["passed"] for e in exp)
    return {"expectations": exp, "summary": {"passed": passed, "failed": len(exp) - passed,
                                             "total": len(exp), "pass_rate": round(passed / len(exp), 2)}}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("iteration")
    ap.add_argument("--evals", default=Path(__file__).with_name("evals.json"))
    a = ap.parse_args()
    modes = {e["id"]: e["index_mode"] for e in json.loads(Path(a.evals).read_text(encoding="utf-8"))["evals"]}
    if not set(modes.values()) <= {"tabs", "bundle", "any"}:
        raise SystemExit(f"index_mode must be tabs, bundle or any: {sorted(set(modes.values()))}")
    for ev_dir in sorted(p for p in Path(a.iteration).iterdir() if p.is_dir()):
        m = re.match(r"eval-(\d+)", ev_dir.name)
        if not m or int(m.group(1)) not in modes:
            raise SystemExit(f"{ev_dir.name}: no eval id matching {a.evals}")
        for run in sorted(ev_dir.glob("*/run-*")):
            g = grade(run, modes[int(m.group(1))])
            (run / "grading.json").write_text(json.dumps(g, ensure_ascii=False, indent=1), encoding="utf-8")
            print(ev_dir.name, run.parent.name, run.name, g["summary"]["passed"], "/", g["summary"]["total"])
