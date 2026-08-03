import os
import re
import json
import urllib.request
import asyncio
from playwright.async_api import async_playwright

ASSETS_DIR = os.path.join("assets", "amazon_photos")

# Fetch products directly from the JS file
def get_products():
    url = 'https://deviceshopbo.com/productos.js'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    content = urllib.request.urlopen(req).read().decode('utf-8')
    
    products = []
    for m in re.finditer(r'id:\s*"([^"]+)",\s*nombre:\s*"([^"]+)"', content):
        products.append({'id': m.group(1), 'nombre': m.group(2)})
    return products

async def download_image(url, filepath):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        data = urllib.request.urlopen(req).read()
        with open(filepath, "wb") as f:
            f.write(data)
        print(f"Downloaded: {filepath}")
    except Exception as e:
        print(f"Failed to download {url}: {e}")

async def scrape_amazon_for_product(page, product_id, product_name):
    print(f"\n--- Processing: {product_name} ---")
    
    folder = os.path.join(ASSETS_DIR, product_id)
    os.makedirs(folder, exist_ok=True)
    
    # Check if we already have files
    if len(os.listdir(folder)) > 0:
        print(f"Already scraped {product_id}, skipping.")
        return

    # Go to amazon
    await page.goto("https://www.amazon.com/")
    
    # Wait for search box, if captcha, we might need to wait for user to solve it manually
    try:
        await page.wait_for_selector("#twotabsearchtextbox", timeout=5000)
    except:
        print("Captcha or block detected! Please solve it in the browser.")
        await page.wait_for_selector("#twotabsearchtextbox", timeout=60000)

    # Search for product
    search_query = product_name
    await page.fill("#twotabsearchtextbox", search_query)
    await page.click("input#nav-search-submit-button")
    
    # Wait for results
    try:
        await page.wait_for_selector("a[href*='/dp/']", timeout=10000)
    except:
        print("Timeout waiting for search results.")
        return
    
    # Click the first relevant result
    first_product_link = await page.locator("a[href*='/dp/']").first.get_attribute("href")
    
    if not first_product_link:
        print("Could not find product link.")
        return
        
    product_url = "https://www.amazon.com" + first_product_link if not first_product_link.startswith("http") else first_product_link
    print(f"Found product URL: {product_url}")
    await page.goto(product_url)
    
    # Wait for the page to load
    try:
        await page.wait_for_selector("#dp-container", timeout=10000)
    except:
        print("Timeout waiting for product page to load. Looking for images anyway...")
    
    # Extract hiRes and large URLs from the entire page content
    # This avoids the issue where regex stops at the first closing brace of the JSON
    content = await page.content()
    try:
        hi_res_urls = re.findall(r'"hiRes"\s*:\s*"([^"]+)"', content)
        large_urls = re.findall(r'"large"\s*:\s*"([^"]+)"', content)
        
        # Combine and deduplicate (keeping order)
        all_urls = []
        for url in (hi_res_urls + large_urls):
            if url and url not in all_urls and url.startswith("http"):
                all_urls.append(url)
                
        for idx, img_url in enumerate(all_urls):
            filepath = os.path.join(folder, f"{idx+1}.jpg")
            await download_image(img_url, filepath)
            
        if not all_urls:
            print("No images found in the page source.")
            
    except Exception as e:
        print(f"Error parsing images: {e}")
        
    # Wait a bit before next search
    await asyncio.sleep(2)

async def main():
    products = get_products()
    
    os.makedirs(ASSETS_DIR, exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        for p_info in products:
            await scrape_amazon_for_product(page, p_info['id'], p_info['nombre'])
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
