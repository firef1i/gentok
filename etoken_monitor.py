#!/usr/bin/env python3
"""
E-Token Generator for Marina East Staging Ground
Automates login, truck entry validation, and token generation.
Saves generated tokens to tokens.json.
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from playwright.async_api import async_playwright

# Load environment variables
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# Configuration from .env
ETOKEN_USERNAME = os.getenv("ETOKEN_USERNAME", "")
ETOKEN_PASSWORD = os.getenv("ETOKEN_PASSWORD", "")
TRUCK_NO = os.getenv("TRUCK_NO", "")
TRUCK_PASSWORD = os.getenv("TRUCK_PASSWORD", "")
MATERIAL = os.getenv("MATERIAL", "GOODEARTH")

# URLs
BASE_URL = "https://marinaeaststagingground.com.sg/etoken/index.php/etokenapp"
CHKENTRY_URL = f"{BASE_URL}/chkentry"
GENTOKEN_URL = f"{BASE_URL}/gentoken"

# Default geolocation for Marina East area, Singapore
DEFAULT_LAT = 1.341453
DEFAULT_LON = 103.906435

# File paths
TOKENS_FILE = Path(__file__).parent / "tokens.json"


def validate_env():
    """Check that all required env vars are set."""
    missing = []
    for name, val in [
        ("ETOKEN_USERNAME", ETOKEN_USERNAME),
        ("ETOKEN_PASSWORD", ETOKEN_PASSWORD),
        ("TRUCK_NO", TRUCK_NO),
        ("TRUCK_PASSWORD", TRUCK_PASSWORD),
    ]:
        if not val or val.startswith("your_"):
            missing.append(name)
    if missing:
        print(f"ERROR: Missing or placeholder values in .env for: {', '.join(missing)}")
        print(f"Please edit {env_path} with real credentials.")
        sys.exit(1)
    if MATERIAL not in ("GOODEARTH", "SOFTCLAY"):
        print(f"ERROR: MATERIAL must be GOODEARTH or SOFTCLAY, got '{MATERIAL}'")
        sys.exit(1)


def save_token(token_data: dict):
    """Append token data to tokens.json."""
    tokens = []
    if TOKENS_FILE.exists():
        try:
            tokens = json.loads(TOKENS_FILE.read_text())
        except (json.JSONDecodeError, ValueError):
            tokens = []
    tokens.append(token_data)
    TOKENS_FILE.write_text(json.dumps(tokens, indent=2))
    print(f"Token saved to {TOKENS_FILE}")


async def wait_and_check_login(page, timeout_sec=30):
    """Wait for the login to complete by checking for token generation page elements."""
    try:
        # After login, the page should have the frmgo form
        await page.wait_for_selector('form[name="frmgo"]', timeout=timeout_sec * 1000)
        return True
    except Exception:
        # Double-check: maybe the form is already there but wasn't detected
        frmgo = await page.query_selector('form[name="frmgo"]')
        if frmgo:
            return True
        return False


async def debug_page(page, label="debug"):
    """Save screenshot and HTML for debugging."""
    ts = datetime.now().strftime("%H%M%S")
    screenshot_path = Path(__file__).parent / f"debug_{label}_{ts}.png"
    html_path = Path(__file__).parent / f"debug_{label}_{ts}.html"
    await page.screenshot(path=str(screenshot_path), full_page=True)
    html_content = await page.content()
    html_path.write_text(html_content)
    print(f"DEBUG: Screenshot saved to {screenshot_path}")
    print(f"DEBUG: HTML saved to {html_path}")
    # Also print all form fields found on the page
    forms_info = await page.evaluate("""() => {
        const forms = document.querySelectorAll('form');
        return Array.from(forms).map(f => {
            const inputs = f.querySelectorAll('input, select, button, textarea');
            return {
                name: f.name || '(unnamed)',
                action: f.action,
                method: f.method,
                fields: Array.from(inputs).map(i => ({
                    tag: i.tagName,
                    name: i.name,
                    type: i.type,
                    id: i.id,
                }))
            };
        });
    }""")
    print(f"DEBUG: Forms on page: {json.dumps(forms_info, indent=2)}")


async def generate_token(headless=False):
    """Main flow: login, validate truck entry, generate token."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            geolocation={"latitude": DEFAULT_LAT, "longitude": DEFAULT_LON},
            permissions=["geolocation"],
        )
        page = await context.new_page()

        # --- Step 1: Login ---
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Navigating to {BASE_URL}")
        await page.goto(BASE_URL, wait_until="networkidle")

        # Determine if login is needed (check if frmgo already visible)
        on_token_page = await page.query_selector('form[name="frmgo"]')

        if not on_token_page:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Login page detected. Logging in...")

            # Debug: capture what the login page looks like
            await debug_page(page, "login_before")

            # Find all text-type inputs (exclude hidden/submit/reset)
            # Common login field names: username, user, login, email, uname
            username_selectors = [
                'input[name="username"]',
                'input[name="user"]',
                'input[name="uname"]',
                'input[name="login"]',
                'input[name="email"]',
                'input[type="text"]:not([name="vehno"])',
                'input:not([type="hidden"]):not([type="submit"]):not([type="password"]):not([type="reset"]):not([name="vehno"])',
            ]
            username_field = None
            for sel in username_selectors:
                loc = page.locator(sel).first
                if await loc.count() > 0:
                    username_field = loc
                    print(f"  Found username field via: {sel}")
                    break

            # Login page password field — use the password field inside the login form
            # (action contains '/login')
            password_field = page.locator('form[action*="login"] input[type="password"]').first

            if not username_field:
                print("ERROR: Could not find a username/login input field.")
                print("  Check debug_login_before_*.html to see the page structure.")
                await browser.close()
                return

            try:
                await username_field.fill(ETOKEN_USERNAME)
                await password_field.fill(ETOKEN_PASSWORD)
            except Exception as e:
                print(f"ERROR: Could not fill login fields: {e}")
                await debug_page(page, "login_fill_error")
                await browser.close()
                return

            # Submit the login form
            submit_btn = page.locator('input[type="submit"], button[type="submit"]').first
            try:
                await submit_btn.click(timeout=5000)
            except Exception:
                # Fallback: find the form and submit via JS
                print("  No submit button found, trying form.submit()...")
                await page.evaluate("""() => {
                    const forms = document.querySelectorAll('form');
                    for (const f of forms) {
                        const pw = f.querySelector('input[type="password"]');
                        if (pw) { f.submit(); return; }
                    }
                }""")

            # Wait for login to complete
            logged_in = await wait_and_check_login(page)
            if not logged_in:
                print("ERROR: Login may have failed. Could not reach token generation page.")
                await debug_page(page, "login_failed")
                await browser.close()
                return

            print(f"[{datetime.now().strftime('%H:%M:%S')}] Login successful.")
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Already on token page (session active).")

        # --- Step 2: Fill frmgo form (truck entry validation) ---
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Filling truck entry form...")
        print(f"  Truck No: {TRUCK_NO}")

        # The page may load form content via AJAX after login — wait for inputs
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Waiting for form fields to render...")
        await page.wait_for_selector('input[name="vehno"][type="text"]', timeout=15000)
        await page.wait_for_selector('input[name="passwd"]', timeout=5000)

        # Fill the vehno and passwd inputs (use page-level selectors since
        # the form structure may not contain the inputs due to table layout)
        vehno_input = page.locator('input[name="vehno"][type="text"]').first
        # Use page-level selector — the passwd input for the truck form is the one
        # that co-exists with the vehno input (not the login form passwd)
        passwd_input = page.locator('input[name="passwd"]').last

        await vehno_input.fill(TRUCK_NO)
        await passwd_input.fill(TRUCK_PASSWORD)

        # Also update the hidden vehno field (the server-generated one outside the form)
        await page.evaluate(
            """(truckNo) => {
            // Update all vehno hidden fields
            document.querySelectorAll('input[name="vehno"][type="hidden"]').forEach(el => {
                el.value = truckNo;
            });
        }""",
            TRUCK_NO,
        )

        # Submit frmgo — since the browser auto-closes form tags inside tables,
        # we need to manually POST using fetch to include all fields.
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Submitting truck entry form...")
        await page.evaluate(
            """() => {
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = 'https://marinaeaststagingground.com.sg/etoken/index.php/etokenapp/chkentry';

            // Gather all relevant fields from the page
            const fields = ['site', 'status', 'tknoff', 'minfo', 'vehno'];
            fields.forEach(name => {
                const inputs = document.querySelectorAll('input[name="' + name + '"]');
                inputs.forEach(input => {
                    if (input.type === 'hidden') {
                        const inp = document.createElement('input');
                        inp.type = 'hidden';
                        inp.name = name;
                        inp.value = input.value;
                        form.appendChild(inp);
                    }
                });
            });

            // Add passwd
            const passwd = document.querySelector('input[name="passwd"]');
            if (passwd) {
                const inp = document.createElement('input');
                inp.type = 'hidden';
                inp.name = 'passwd';
                inp.value = passwd.value;
                form.appendChild(inp);
            }

            document.body.appendChild(form);
            form.submit();
        }"""
        )

        # Wait for page update after chkentry
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Validating truck entry...")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(3)

        # Check for error messages via sweetalert (the error is in swal2-title)
        error_title = await page.query_selector("#swal2-title, .swal2-title")
        has_error_icon = await page.evaluate('() => document.querySelector(".swal2-icon.swal2-error") !== null')
        if error_title and has_error_icon:
            error_text = (await error_title.inner_text()).strip()
            if error_text:
                print(f"ERROR: Truck entry validation failed: {error_text}")
                await browser.close()
                return

        # --- Step 3: Fill frmgen form (token generation) ---
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Generating token...")
        print(f"  Material: {MATERIAL}")

        # Use page-level selector for material (may be outside form tag in table layout)
        material_select = page.locator('select[name="material"]').first
        await material_select.select_option(value=MATERIAL)

        # Set geolocation hidden fields
        await page.evaluate(
            """([lat, lon]) => {
            const latEl = document.getElementById('geolat');
            const lonEl = document.getElementById('geolon');
            if (latEl) latEl.value = lat;
            if (lonEl) lonEl.value = lon;
        }""",
            [str(DEFAULT_LAT), str(DEFAULT_LON)],
        )

        # Submit frmgen form — build a proper form since the original is empty
        # due to browser auto-closing form tags inside tables
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Submitting token generation form...")
        await page.evaluate(
            """() => {
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = 'https://marinaeaststagingground.com.sg/etoken/index.php/etokenapp/gentoken';

            // Gather all hidden fields for frmgen
            const fields = ['mnum', 'vehno', 'site', 'status', 'hcontractor',
                           'tknoff', 'entryrec', 'vehlatlon', 'vtsvendor', 'tknlat', 'tknlon'];
            fields.forEach(name => {
                const input = document.querySelector('input[name="' + name + '"]');
                if (input) {
                    const inp = document.createElement('input');
                    inp.type = 'hidden';
                    inp.name = name;
                    inp.value = input.value;
                    form.appendChild(inp);
                }
            });

            // Add material select value
            const material = document.querySelector('select[name="material"]');
            if (material) {
                const inp = document.createElement('input');
                inp.type = 'hidden';
                inp.name = 'material';
                inp.value = material.value;
                form.appendChild(inp);
            }

            document.body.appendChild(form);
            form.submit();
        }"""
        )

        # Wait for token generation response
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(3)

        # --- Step 4: Capture the result ---
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Capturing result...")

        # Extract fields from the result page
        result = await page.evaluate(
            """() => {
            const cells = document.querySelectorAll('table td em');
            const data = {};
            const labels = [];
            cells.forEach((em, i) => {
                const text = em.textContent.trim();
                // Every even index (0, 2, 4...) is a label, odd is a value
                if (i % 2 === 0) {
                    labels.push(text);
                } else {
                    data[labels[labels.length - 1]] = text;
                }
            });
            return data;
        }"""
        )

        print(f"\n{'=' * 60}")
        print("TOKEN GENERATION RESULT:")
        print(f"{'=' * 60}")
        for key, val in result.items():
            print(f"  {key} {val}")
        print(f"{'=' * 60}\n")

        # Build token record
        timestamp = datetime.now().isoformat(timespec="seconds")
        token_data = {
            "timestamp": timestamp,
            "truck_no": TRUCK_NO,
            "material": MATERIAL,
            "token": result.get("Last Token Generated:", ""),
            "site": result.get("Site Code:", "CR202"),
            "generated_at": result.get("E-Token Generated @", ""),
            "entry_record": result.get("Source Site Entry Record:", ""),
        }

        save_token(token_data)

        # Keep browser open briefly if not headless so user can see the result
        if not headless:
            print("Browser will close in 10 seconds...")
            await asyncio.sleep(10)

        await browser.close()


if __name__ == "__main__":
    validate_env()

    headless_mode = "--headless" in sys.argv

    try:
        asyncio.run(generate_token(headless=headless_mode))
    except KeyboardInterrupt:
        print("\nStopped by user.")
