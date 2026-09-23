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
            # Search for createAccount function and its fetch/post call
            content = await page.evaluate("""async (url) => {
                try {
                    const resp = await fetch(url);
                    const text = await resp.text();
                    const results = [];
                    
                    // Find createAccount function context
                    let idx = text.indexOf('createAccount');
                    while (idx >= 0) {
                        results.push("createAccount_CTX: " + text.substring(Math.max(0, idx-100), Math.min(text.length, idx+300)));
                        idx = text.indexOf('createAccount', idx + 1);
                        if (results.length > 5) break;
                    }
                    
                    // Find sign-up/create context
                    idx = text.indexOf('sign-up/create');
                    if (idx >= 0) {
                        results.push("signup_create_CTX: " + text.substring(Math.max(0, idx-200), idx+200));
                    }
                    
                    // Find all fetch( calls with auth/sign-up
                    const fetches = text.match(/fetch\\(["'][^"']*sign-up[^"']*["']/g) || [];
                    results.push(...fetches.slice(0, 5));
                    
                    // Find all POST or api calls near "complete" or "create"
                    const posts = text.match(/["'](?:POST|PUT)["'].{0,200}/g) || [];
                    results.push(...posts.filter(p => p.toLowerCase().includes('sign') || p.toLowerCase().includes('create') || p.toLowerCase().includes('complete')).slice(0, 5));
                    
                    return results.length > 0 ? results.slice(0, 15) : null;
                } catch(e) { return null; }
            }""", url)
            
            if content:
                for item in content:
                    print(f"[{url[-25:]}] {item[:250]}")
        
        await browser.close()

asyncio.run(search())
