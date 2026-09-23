#!/usr/bin/env python3
import asyncio, json

async def search():
    from patchright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False, executable_path="/usr/bin/chromium",
            args=["--no-sandbox","--disable-gpu","--disable-dev-shm-usage"]
        )
        ctx = await browser.new_context(
            viewport={"width":1920,"height":1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = await ctx.new_page()
        await page.goto("https://accounts.x.ai/sign-up?redirect=grok-com", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)
        
        js_urls = await page.evaluate("""() => {
            return performance.getEntriesByType('resource')
                .filter(r => r.name.endsWith('.js') || r.name.includes('.js?'))
                .map(r => r.name).slice(0, 60);
        }""")
        
        for url in js_urls:
            content = await page.evaluate("""async (url) => {
                try {
                    const resp = await fetch(url);
                    const text = await resp.text();
                    const results = [];
                    // Find all gRPC method references
                    const grpc = text.match(/auth_mgmt\\.\\w+\\.\\w+|AuthManagement\\/\\w+/g) || [];
                    results.push(...grpc);
                    // Find ValidatePassword context
                    const idx = text.indexOf('ValidatePassword');
                    if (idx >= 0) {
                        results.push("CTX: " + text.substring(Math.max(0, idx-150), idx+150));
                    }
                    // Find signup-related method names
                    const signup = text.match(/(?:CompleteSignUp|CreateAccount|SignUp|Register|sign-up\\/\\w+|signup\\/\\w+)/gi) || [];
                    results.push(...new Set(signup).values());
                    // Find continue-sso context
                    const sso = text.indexOf('continue-sso');
                    if (sso >= 0) {
                        results.push("SSO_CTX: " + text.substring(Math.max(0, sso-100), sso+100));
                    }
                    return results.length > 0 ? results.slice(0, 15) : null;
                } catch(e) { return null; }
            }""", url)
            
            if content:
                print(f"\n=== {url[-40:]} ===")
                for item in content:
                    print(f"  {item[:200]}")
        
        await browser.close()

asyncio.run(search())
