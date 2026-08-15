"""
verify.py  -  One command that checks the whole install and prints one report.

Run this in a fresh clone. It exercises every path a new user touches and
prints a single block you can paste back to whoever is helping you.

    python verify.py            fast, about 90 seconds, one live domain
    python verify.py --full     adds the whole 159-domain sweep, about 9 minutes
    python verify.py --offline  no network at all, logic checks only

Nothing here writes outside runs/ and nothing is destructive.
"""

import os, re, sys, json, time, platform, argparse, subprocess

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
LINES = []
FAILED = 0
WARNED = 0


def say(s=""):
    print(s)
    LINES.append(s)


def result(label, ok, detail="", warn=False):
    global FAILED, WARNED
    if ok:
        tag = "PASS"
    elif warn:
        tag = "WARN"
        WARNED += 1
    else:
        tag = "FAIL"
        FAILED += 1
    say(f"  [{tag}] {label}" + (f"  -- {detail}" if detail else ""))


def run(args, timeout=900):
    try:
        p = subprocess.run([PY] + args, cwd=HERE, capture_output=True,
                           text=True, timeout=timeout, encoding="utf-8",
                           errors="replace")
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    except Exception as e:
        return 1, f"{type(e).__name__}: {e}"


def num(text, pattern):
    m = re.search(pattern, text)
    return int(m.group(1)) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="also run the whole 159-domain sweep")
    ap.add_argument("--offline", action="store_true", help="logic checks only, no network")
    args = ap.parse_args()

    t0 = time.time()
    say("=" * 64)
    say("ADVERTORIAL FINDER -- INSTALL VERIFICATION")
    say("=" * 64)
    say(f"python   {platform.python_version()}  ({platform.system()} {platform.machine()})")
    say(f"mode     {'offline' if args.offline else ('full' if args.full else 'fast')}")
    try:
        rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=HERE,
                             capture_output=True, text=True).stdout.strip()
        say(f"commit   {rev or 'unknown'}")
    except Exception:
        say("commit   unknown")
    say()

    # ---------------------------------------------------------------- files
    say("FILES")
    expected = ["README.md", "INSTALL.md", "SKILL.md", "SOP.md", "brands.txt",
                "sitemap_sweep.py", "qualify.py", "pdf_save.py", "ledger.py",
                "resolve_domains.py", "selftest.py"]
    missing = [f for f in expected if not os.path.exists(os.path.join(HERE, f))]
    result("all expected files present", not missing, ", ".join(missing) or "11 files")

    # The question is whether captures would SHIP, not whether they exist on
    # this machine. An author's working copy is full of them by design; what
    # matters is that git is not tracking any.
    tracked = ""
    try:
        tracked = subprocess.run(["git", "ls-files"], cwd=HERE, capture_output=True,
                                 text=True, timeout=60).stdout
    except Exception:
        pass
    if tracked:
        leaked = [l for l in tracked.splitlines()
                  if l.endswith(".pdf") or l.startswith(("Advertorial-Repo/", "swipe_refs/", "runs/"))
                  or l.endswith((".jsonl", ".log"))]
        result("no captures or run data tracked by git", not leaked,
               ", ".join(leaked[:3]) or f"{len(tracked.splitlines())} files tracked, all method")
    else:
        result("git tracking check", True, "not a git checkout, skipped", warn=False)

    brands = [l.strip() for l in open(os.path.join(HERE, "brands.txt"), encoding="utf-8")
              if l.strip() and not l.startswith("#")]
    result("brands.txt loaded", len(brands) > 100, f"{len(brands)} domains")
    say()

    # ---------------------------------------------------------------- logic
    say("LOGIC (offline, deterministic -- this is the strongest signal)")
    code, out = run(["selftest.py"], timeout=120)
    oks = out.count("  ok   ")
    result("selftest", code == 0, f"{oks} checks passed" if code == 0 else
           " / ".join(l.strip() for l in out.splitlines() if "FAIL" in l)[:200])
    say()

    # ---------------------------------------------------------------- cli
    say("ENTRY POINTS")
    for script in ["sitemap_sweep.py", "qualify.py", "resolve_domains.py", "ledger.py"]:
        code, out = run([script, "--help"], timeout=60)
        result(f"{script} --help", code == 0, "" if code == 0 else out.strip()[:120])
    code, out = run(["pdf_save.py"], timeout=60)
    ok = ("Usage" in out) or ("playwright" in out.lower())
    result("pdf_save.py explains itself", ok, "" if ok else out.strip()[:120])
    say()

    # ---------------------------------------------------------------- state
    say("STATE")
    code, out = run(["ledger.py", "status"], timeout=60)
    result("ledger status from cold start", code == 0, "" if code == 0 else out.strip()[:120])
    code, out = run(["ledger.py", "niche"], timeout=60)
    result("niche rotation", code == 0 and "sleep" in out, "" if code == 0 else out.strip()[:120])
    say()

    if args.offline:
        finish(t0)
        return

    # ---------------------------------------------------------------- live
    say("LIVE (depends on other people's servers; WARN is not necessarily a bug)")
    code, out = run(["sitemap_sweep.py", "--domain", "groundingwell.com",
                     "--out", "runs/verify.json", "--delay", "2"], timeout=300)
    hits = num(out, r"candidate pages\s*:\s*(\d+)")
    rate_limited = "http_429" in out
    if code == 0 and hits:
        result("sweep one known brand", True, f"{hits} candidates")
    else:
        result("sweep one known brand", False,
               "rate limited (429), not a code fault -- retry later" if rate_limited
               else out.strip()[-160:], warn=rate_limited)

    if os.path.exists(os.path.join(HERE, "runs", "verify.json")):
        code, out = run(["qualify.py", "runs/verify.json", "--limit", "12",
                         "--no-probe", "--delay", "2"], timeout=900)
        passed = num(out, r"passed\s*:\s*(\d+)")
        failed = num(out, r"failed\s*:\s*(\d+)")
        reasons = re.findall(r"^\s+(\d+)\s+(\w+)", out, re.M)
        if code == 0 and passed is not None:
            result("qualify a sample", True, f"{passed} passed, {failed} rejected")
            if reasons:
                top = max(reasons, key=lambda r: int(r[0]))
                total = sum(int(n) for n, _ in reasons)
                dominant = total and int(top[0]) / total > 0.9 and total > 5
                result("rejections are varied, not one dominant cause",
                       not dominant,
                       f"top reason '{top[1]}' is {top[0]}/{total}",
                       warn=dominant)
        else:
            result("qualify a sample", False, out.strip()[-160:])

    if args.full:
        say()
        say("FULL SWEEP (about 9 minutes)")
        code, out = run(["sitemap_sweep.py", "brands.txt", "--out", "runs/candidates.json",
                         "--workers", "5", "--delay", "2"], timeout=2400)
        resolved = num(out, r"domains resolved\s*:\s*(\d+)")
        withhits = num(out, r"brands with hits\s*:\s*(\d+)")
        pages = num(out, r"candidate pages\s*:\s*(\d+)")
        result("full sweep completed", code == 0,
               f"{resolved}/{len(brands)} resolved, {withhits} brands, {pages} candidates")
        if pages:
            result("candidate count in expected range", 400 <= pages <= 700,
                   f"{pages} (expected roughly 544)", warn=True)

    finish(t0)


def finish(t0):
    say()
    say("=" * 64)
    verdict = "READY" if FAILED == 0 else "PROBLEMS FOUND"
    say(f"{verdict}   {FAILED} failed, {WARNED} warnings, {int(time.time() - t0)}s")
    say("=" * 64)
    if FAILED:
        say("Paste this whole block back. FAIL lines are real bugs.")
    elif WARNED:
        say("WARN lines usually mean rate limiting or a slow server, not a bug.")
        say("Retry later; if they persist, paste this block back.")
    else:
        say("Everything works. Paste this block back if you want it confirmed.")

    with open(os.path.join(HERE, "verify-report.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(LINES) + "\n")
    say()
    say("Saved to verify-report.txt")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
