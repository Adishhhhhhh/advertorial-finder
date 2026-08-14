"""
pdf_save.py  —  Save a live advertorial as a clean, popup-free full-page PDF
Usage:
    py pdf_save.py <URL> <niche_slug>
Example:
    py pdf_save.py "https://puplabs.com/pages/miracle-joint-drops" "pet-joint"

Requirements: playwright  (py -m pip install playwright && py -m playwright install chromium)
"""

import sys, os, re, asyncio
from pathlib import Path
from typing import Optional
from datetime import date
from urllib.parse import urlparse

try:
    from playwright.async_api import async_playwright
except ImportError:
    sys.exit(
        "pdf_save.py needs Playwright, which is the only dependency in this repo.\n"
        "\n"
        "    pip install -r requirements.txt\n"
        "    python -m playwright install chromium\n"
        "\n"
        "Everything else (sitemap_sweep, qualify, ledger, resolve_domains) runs\n"
        "on the standard library and needs none of this."
    )

SCRIPT_DIR = Path(__file__).resolve().parent
REPO       = SCRIPT_DIR / "Advertorial-Repo"

# ── Surgical JS that removes ONLY genuine overlay elements ───────────────────
# Criteria: position fixed/sticky + high z-index + covers a large viewport area
# This avoids broad CSS wildcards that accidentally hide page content.
# NOTE: in print, position:fixed elements repeat on EVERY PDF page — one missed
# popup ruins the whole document. Popups often fire on scroll or a delayed
# timer, so this must run again AFTER the scroll pass, right before printing.
NUKE_OVERLAYS_JS = """
() => {
    const removed = [];
    document.querySelectorAll('*').forEach(el => {
        const s = window.getComputedStyle(el);
        const z = parseInt(s.zIndex, 10) || 0;
        if (s.position === 'fixed' || s.position === 'sticky') {
            const r = el.getBoundingClientRect();
            const covW = r.width  / window.innerWidth;
            const covH = r.height / window.innerHeight;
            // modal/banner: high z-index covering >30% of viewport in either dimension,
            // OR any fixed element blanketing the screen (backdrops can have low z)
            const isModal    = z > 99 && (covW > 0.30 || covH > 0.30);
            const isBackdrop = covW > 0.85 && covH > 0.85;
            if (isModal || isBackdrop) {
                el.style.setProperty('display',    'none', 'important');
                el.style.setProperty('visibility', 'hidden', 'important');
                removed.push(el.tagName + '.' + String(el.className).substring(0,40));
            }
        }
    });
    // Also unlock body scroll (some sites set overflow:hidden when modal is open)
    document.body.style.setProperty('overflow', 'auto', 'important');
    document.documentElement.style.setProperty('overflow', 'auto', 'important');
    return removed;
}
"""

# Specific close-button selectors — tried one by one, errors silently skipped
CLOSE_SELECTORS = [
    "button[aria-label*='close'   i]",
    "button[aria-label*='dismiss' i]",
    "[data-testid*='close'        i]",
    "[data-testid*='dismiss'      i]",
    ".modal__close",
    ".klaviyo-close-form",
    ".privy-dismiss-button",
    "#onetrust-accept-btn-handler",   # cookie consent
    ".cc-dismiss",                    # cookieconsent
]


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[\s_]+", "-", text).strip("-")[:60]

def url_to_slug(url: str) -> str:
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "").split(".")[0]
    path   = parsed.path.strip("/").replace("/", "-")
    return slugify(f"{domain}-{path}")[:80]


DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)
MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.5 Mobile/15E148 Safari/604.1"
)


async def save_pdf_async(url: str, niche_slug: str, mobile: bool = False) -> Optional[Path]:
    """Capture a live advertorial as a PDF.

    Defaults to DESKTOP, because these captures are read on a desktop while
    working in Claude Code, and the copy is identical either way. Mobile
    changes layout, not words: sticky CTA bars, collapsed sections, and the
    scroll pacing between a claim and its button. Use --mobile when the
    question is about layout or CTA placement, and --both on a page you plan
    to tear down properly.
    """
    REPO.mkdir(parents=True, exist_ok=True)

    today    = date.today().isoformat()
    suffix   = "_mobile" if mobile else ""
    filename = f"{today}_{slugify(niche_slug)}_{url_to_slug(url)}{suffix}.pdf"
    out_path = REPO / filename

    width = 390 if mobile else 1440

    print(f"[pdf_save] URL    : {url}")
    print(f"[pdf_save] View   : {'mobile 390px' if mobile else 'desktop 1440px'}")
    print(f"[pdf_save] Output : {out_path}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            viewport={"width": width, "height": 844 if mobile else 900},
            user_agent=MOBILE_UA if mobile else DESKTOP_UA,
            is_mobile=mobile,
            has_touch=mobile,
            device_scale_factor=3 if mobile else 1,
        )
        page = await context.new_page()

        # ── 1. Load page ──────────────────────────────────────────────────────
        print("[pdf_save] Loading page...")
        await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        await page.wait_for_timeout(4_000)

        # ── 2. Press Escape (closes most modal/popup widgets) ─────────────────
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(800)

        # ── 3. Try clicking specific close buttons ────────────────────────────
        for sel in CLOSE_SELECTORS:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=300):
                    await el.click(timeout=300)
                    await page.wait_for_timeout(400)
            except Exception:
                pass

        # ── 4. Surgically remove large fixed/sticky overlays via JS ───────────
        print("[pdf_save] Removing overlays...")
        removed = await page.evaluate(NUKE_OVERLAYS_JS)
        if removed:
            print(f"[pdf_save]   Removed {len(removed)} overlay element(s)")
        await page.wait_for_timeout(800)

        # ── 5. Scroll full page to trigger lazy-load images ───────────────────
        print("[pdf_save] Scrolling for lazy-load images...")
        await page.evaluate("""async () => {
            await new Promise(resolve => {
                let scrolled = 0;
                const step = 900;
                const timer = setInterval(() => {
                    window.scrollBy(0, step);
                    scrolled += step;
                    if (scrolled >= document.body.scrollHeight) {
                        clearInterval(timer);
                        window.scrollTo(0, 0);
                        resolve();
                    }
                }, 100);
            });
        }""")
        await page.wait_for_timeout(2_000)

        # ── 5b. SECOND popup pass — scroll/timer-triggered popups appear late ──
        # (e.g. Klaviyo "subscribe" modals fired at scroll-depth %). Without this
        # pass a late popup prints repeated on every PDF page.
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(500)
        for sel in CLOSE_SELECTORS:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=300):
                    await el.click(timeout=300)
                    await page.wait_for_timeout(300)
            except Exception:
                pass
        removed2 = await page.evaluate(NUKE_OVERLAYS_JS)
        if removed2:
            print(f"[pdf_save]   Second pass removed {len(removed2)} late overlay(s)")
        await page.wait_for_timeout(500)

        # ── 6. Emulate screen media so CSS renders exactly as in a browser ──────
        # Without this, Playwright uses print stylesheets which strip backgrounds,
        # flatten layouts, and make advertorials ugly and hard to read.
        await page.emulate_media(media="screen")

        # ── 7. Print PDF — get bytes, write with Python (avoids Windows path bugs) ──
        print("[pdf_save] Printing PDF...")
        pdf_bytes = await page.pdf(
            print_background=True,
            width=f"{width}px",   # match viewport — preserves the layout as rendered
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
        )
        out_path.write_bytes(pdf_bytes)
        await browser.close()

    if out_path.exists() and out_path.stat().st_size > 50_000:
        kb = out_path.stat().st_size // 1024
        print(f"[pdf_save] SUCCESS -- {kb} KB -- {filename}")
        return out_path
    else:
        sz = out_path.stat().st_size if out_path.exists() else 0
        print(f"[pdf_save] FAILED  -- file size {sz} bytes (expected >50 KB)")
        print( "           Confirm the URL loads in a browser, then retry.")
        return None


def save_pdf(url: str, niche_slug: str, mobile: bool = False):
    return asyncio.run(save_pdf_async(url, niche_slug, mobile))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}

    if len(args) < 2:
        print("Usage  : py pdf_save.py <URL> <niche_slug> [--mobile] [--both]")
        print('Example: py pdf_save.py "https://puplabs.com/pages/miracle-joint-drops" "pet-joint"')
        print("         Desktop by default. --mobile for layout and CTA-placement questions.")
        sys.exit(1)

    url, niche = args[0], args[1]
    if "--both" in flags:
        save_pdf(url, niche, mobile=False)
        save_pdf(url, niche, mobile=True)
    else:
        save_pdf(url, niche, mobile="--mobile" in flags)
