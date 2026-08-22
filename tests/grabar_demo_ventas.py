import asyncio, os, subprocess, sys, time

URL = None
with open("/app/frontend/.env") as f:
    for line in f:
        if line.startswith("REACT_APP_BACKEND_URL="):
            URL = line.strip().split("=", 1)[1]

async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir="/tmp/demo_rec_v",
            record_video_size={"width": 1280, "height": 720})
        page = await ctx.new_page()
        t0 = time.time()
        await page.goto(URL, wait_until="networkidle")
        await page.fill('[data-testid="login-rut"]', "administrador")
        await page.fill('[data-testid="login-password"]', "141617575")
        await page.click('[data-testid="login-submit"]', force=True)
        for _ in range(30):
            await page.wait_for_timeout(3000)
            if not await page.query_selector('[data-testid="login-submit"]'):
                break
        await page.evaluate("window.location.hash='#demo-ventas'")
        await page.wait_for_selector('[data-testid="demo-ventas"]', timeout=30000)
        t_demo = time.time() - t0
        print(f"demo ventas visible a los {t_demo:.1f}s", flush=True)
        await page.wait_for_selector('[data-testid="demo-ventas-total"]', timeout=110000)
        await page.wait_for_timeout(9000)
        video = page.video
        await ctx.close()
        webm = await video.path()
        await browser.close()
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
        r = subprocess.run([ff, "-y", "-ss", str(max(0, t_demo - 0.4)), "-i", webm,
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
                            "-pix_fmt", "yuv420p", "-movflags", "+faststart", "/tmp/demo_ventas_raw.mp4"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print("FFMPEG ERROR:", r.stderr[-400:])
            sys.exit(1)
        print("raw mp4:", os.path.getsize("/tmp/demo_ventas_raw.mp4"), flush=True)

asyncio.run(main())
