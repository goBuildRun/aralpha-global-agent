#!/usr/bin/env python3
"""
Automated 1080p Demo Video Recorder & English Voiceover Synthesizer for AlphaNexus (Aralpha × AlphaRadar).
Produces:
1. `/Users/aronezhang-mini/buildrun-agent-engineering-platform/products/hackathon/submissions/aralpha-demo-1080p.mp4`
2. 4 high-res 1080p gallery screenshots under `submissions/screenshots-aralpha/`
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

FFMPEG_BIN = "/opt/homebrew/bin/ffmpeg"
FFPROBE_BIN = "/opt/homebrew/bin/ffprobe"
SAY_BIN = "/usr/bin/say"
PORT = 8766
BASE_URL = f"http://127.0.0.1:{PORT}"

ADAPTER_DIR = Path(__file__).resolve().parent
SUBMISSIONS_DIR = ADAPTER_DIR.parent.parent / "submissions"
SCREENSHOTS_DIR = SUBMISSIONS_DIR / "screenshots-aralpha"
OUTPUT_MP4 = SUBMISSIONS_DIR / "aralpha-demo-1080p.mp4"

SCENES = [
    {
        "id": "scene1_golden_window_and_free_ride",
        "caption": "Scene 1 · Aralpha Golden Window [support, +22%] (Strips 1s Fake Wick) & 2.5x Principal Recovery ('Free-Ride')",
        "narration": (
            "Meet AlphaNexus, combining Aralpha and AlphaRadar into an autonomous on-chain alpha hunter and anti-rug sentinel. "
            "New token listings often print a fake one-second opening wick, like DNA at four cents versus real washout support at seventeen-point-five cents. "
            "AlphaNexus strips opening wick anomalies to pinpoint the T-plus-twelve to seventy-two hour Golden Buy Zone, executes a three-hundred-dollar BNB Chain DCA buy on DNA, "
            "and triggers a four-tier alert when COAI surges past two-point-five-X, selling forty percent to recover one hundred percent of principal while riding a zero-cost moonbag."
        ),
    },
    {
        "id": "scene2_anti_rug_sentinel",
        "caption": "Scene 2 · Web3 for Social Good: Fail-Closed Anti-Rug Sentinel & Fake Clone Contract Interceptor (INV-06)",
        "narration": (
            "Switching to the Anti-Rug Sentinel tab for Web3 Social Good, retail traders lose millions to counterfeit clone tokens launched minutes after TGE. "
            "AlphaNexus cross-verifies every candidate contract against our six-hundred-eighty-four-token official registry and GoPlus honeypot guard. "
            "When we simulate a counterfeit DNA honeypot contract, our Fail-Closed circuit breaker immediately halts execution and dispatches a structured scam abuse report."
        ),
    },
    {
        "id": "scene3_alpharadar_macro_bridge",
        "caption": "Scene 3 · AlphaRadar 4-Layer Macro-to-OnChain Evidence Chain (Nebius NVIDIA Nemotron-70B × Tavily)",
        "narration": (
            "In the Macro-to-OnChain Bridge tab, AlphaRadar links global macro and industrial catalysts to on-chain execution under a Zero-Hallucination Evidence Contract. "
            "Clicking Synthesize Live Signal invokes Nebius NVIDIA Nemotron Seventy-B and Tavily Search across four layers: "
            "macro catalyst verification, technology route mapping, value-chain margin analysis, and direct mapping to BNB Chain AI tokens and tokenized tech equities like Four-Stock."
        ),
    },
    {
        "id": "scene4_backtest_and_invariants",
        "caption": "Scene 4 · 576-Token Empirical Backtest (+725.82% Return, 4.11% Max DD) & 9 Global Safety Invariants",
        "narration": (
            "Finally, in our Empirical Backtest tab across five hundred seventy-six tokens, chasing the first-hour pump suffers a ninety percent max drawdown and negative seventy percent median ROI. "
            "In contrast, our optimal C-Zero-Six Golden Window and two-point-five-X Free-Ride strategy achieves a seven hundred twenty-five percent return "
            "while compressing max drawdown to just four-point-one-one percent, governed by nine institutional safety invariants and a one-click operator KillSwitch."
        ),
    },
]


def get_audio_duration(path: Path) -> float:
    cmd = [
        FFPROBE_BIN,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    out = subprocess.check_output(cmd, text=True).strip()
    return float(out)


def build_voiceover_tracks(work_dir: Path) -> tuple[Path, list[float]]:
    wav_files = []
    durations = []
    for idx, scene in enumerate(SCENES):
        aiff_path = work_dir / f"{idx:02d}_{scene['id']}.aiff"
        wav_path = work_dir / f"{idx:02d}_{scene['id']}.wav"
        subprocess.run(
            [SAY_BIN, "-v", "Samantha", "-r", "182", "-o", str(aiff_path), scene["narration"]],
            check=True,
        )
        subprocess.run(
            [
                FFMPEG_BIN,
                "-y",
                "-i",
                str(aiff_path),
                "-af",
                "apad=pad_dur=0.6",
                "-ar",
                "44100",
                "-ac",
                "2",
                str(wav_path),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        dur = get_audio_duration(wav_path)
        wav_files.append(wav_path)
        durations.append(dur)
        print(f"  [TTS] {scene['id']}: {dur:.2f}s")

    concat_list = work_dir / "concat_audio.txt"
    concat_list.write_text("\n".join(f"file '{w.as_posix()}'" for w in wav_files), encoding="utf-8")
    full_audio = work_dir / "full_voiceover.wav"
    subprocess.run(
        [
            FFMPEG_BIN,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-c",
            "copy",
            str(full_audio),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return full_audio, durations


def set_caption(page, text: str) -> None:
    page.evaluate(
        """(captionText) => {
            let banner = document.getElementById('judge-caption-banner');
            if (!banner) {
                banner = document.createElement('div');
                banner.id = 'judge-caption-banner';
                banner.style.cssText = [
                    'position: fixed',
                    'bottom: 16px',
                    'left: 50%',
                    'transform: translateX(-50%)',
                    'z-index: 9999',
                    'background: rgba(9, 13, 22, 0.95)',
                    'border: 1.5px solid #F59E0B',
                    'box-shadow: 0 8px 30px rgba(0,0,0,0.75)',
                    'color: #F3F6FC',
                    'padding: 10px 22px',
                    'border-radius: 999px',
                    'font-size: 14.5px',
                    'font-weight: 700',
                    'letter-spacing: 0.2px',
                    'white-space: nowrap'
                ].join(';');
                document.body.appendChild(banner);
            }
            banner.textContent = captionText;
        }""",
        text,
    )


def highlight_and_click(page, selector: str, wait_after: float = 1.2) -> None:
    loc = page.locator(selector).first
    loc.scroll_into_view_if_needed()
    loc.evaluate(
        """(el) => {
            const prevOutline = el.style.outline;
            const prevShadow = el.style.boxShadow;
            el.style.outline = '2.5px solid #F59E0B';
            el.style.boxShadow = '0 0 24px rgba(245, 158, 11, 0.85)';
            setTimeout(() => {
                el.style.outline = prevOutline;
                el.style.boxShadow = prevShadow;
            }, 1400);
        }"""
    )
    time.sleep(0.45)
    loc.click()
    time.sleep(wait_after)


def ensure_server_running() -> subprocess.Popen | None:
    try:
        with urllib.request.urlopen(f"{BASE_URL}/api/state", timeout=1.5) as resp:
            if resp.status == 200:
                return None
    except Exception:
        pass

    proc = subprocess.Popen(
        [sys.executable, str(ADAPTER_DIR / "server.py"), "--port", str(PORT)],
        cwd=str(ADAPTER_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(20):
        try:
            with urllib.request.urlopen(f"{BASE_URL}/api/state", timeout=1.0) as resp:
                if resp.status == 200:
                    return proc
        except Exception:
            time.sleep(0.25)
    return proc


def record_browser_walkthrough(work_dir: Path, durations: list[float]) -> Path:
    video_dir = work_dir / "pw_video"
    video_dir.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=1,
            record_video_dir=str(video_dir),
            record_video_size={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        page.goto(BASE_URL, wait_until="networkidle")
        time.sleep(0.6)

        # --- SCENE 1: Golden Window DCA Buy & 2.5x Free-Ride Trigger ---
        t0 = time.monotonic()
        set_caption(page, SCENES[0]["caption"])
        time.sleep(2.0)
        highlight_and_click(page, "button:has-text('BNB Chain AI Agent & RWA Stocks')", wait_after=1.5)
        highlight_and_click(page, "button:has-text('Execute BSC Golden Window DCA Buy')", wait_after=2.2)
        highlight_and_click(page, "button:has-text('Simulate 2.5x Surge & 4-Tier Sell Trigger')", wait_after=2.5)
        page.screenshot(path=str(SCREENSHOTS_DIR / "01_golden_window_free_ride.png"))
        elapsed = time.monotonic() - t0
        time.sleep(max(0.2, durations[0] - elapsed))

        # --- SCENE 2: Anti-Rug Sentinel & Fake Clone Contract Interceptor ---
        t0 = time.monotonic()
        set_caption(page, SCENES[1]["caption"])
        highlight_and_click(page, "button:has-text('SMU Web3 Social Good (Anti-Rug)')", wait_after=1.8)
        highlight_and_click(page, "button:has-text('Simulate Fake Clone Attack')", wait_after=2.5)
        highlight_and_click(page, "button:has-text('Verify Official DNA Contract')", wait_after=2.2)
        page.screenshot(path=str(SCREENSHOTS_DIR / "02_anti_rug_sentinel.png"))
        elapsed = time.monotonic() - t0
        time.sleep(max(0.2, durations[1] - elapsed))

        # --- SCENE 3: AlphaRadar 4-Layer Macro-to-OnChain Bridge ---
        t0 = time.monotonic()
        set_caption(page, SCENES[2]["caption"])
        highlight_and_click(page, "button:has-text('MDBA Blockchain AI (Macro Bridge)')", wait_after=1.8)
        highlight_and_click(page, "button:has-text('Synthesize Live Macro-to-OnChain Signal')", wait_after=3.0)
        page.screenshot(path=str(SCREENSHOTS_DIR / "03_alpharadar_macro_bridge.png"))
        elapsed = time.monotonic() - t0
        time.sleep(max(0.2, durations[2] - elapsed))

        # --- SCENE 4: 576-Token Empirical Backtest & 9 Safety Invariants ---
        t0 = time.monotonic()
        set_caption(page, SCENES[3]["caption"])
        highlight_and_click(page, "button.tab-btn:has-text('4. 规律与回测')", wait_after=2.2)
        page.mouse.wheel(0, 320)
        time.sleep(2.2)
        highlight_and_click(page, "button:has-text('Toggle Operator KillSwitch')", wait_after=2.2)
        page.screenshot(path=str(SCREENSHOTS_DIR / "04_empirical_backtest_invariants.png"))
        highlight_and_click(page, "button:has-text('Toggle Operator KillSwitch')", wait_after=1.2)
        page.mouse.wheel(0, -320)
        elapsed = time.monotonic() - t0
        time.sleep(max(0.2, durations[3] - elapsed))

        context.close()
        browser.close()

    webm_files = list(video_dir.glob("*.webm"))
    if not webm_files:
        raise RuntimeError("No Playwright video recorded!")
    return webm_files[0]


def mux_video_and_audio(webm_path: Path, wav_path: Path, output_mp4: Path) -> None:
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            FFMPEG_BIN,
            "-y",
            "-i",
            str(webm_path),
            "-i",
            str(wav_path),
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(output_mp4),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main() -> None:
    print("🎬 [1/4] Starting AlphaNexus server & synthesizing English TTS narration...")
    server_proc = ensure_server_running()
    try:
        with tempfile.TemporaryDirectory(prefix="aralpha_demo_") as tmp:
            work_dir = Path(tmp)
            full_audio, durations = build_voiceover_tracks(work_dir)
            total_dur = sum(durations)
            print(f"🔊 [2/4] Total English narration duration: {total_dur:.2f}s ({total_dur/60:.2f} min)")
            print("🎥 [3/4] Recording 1920x1080 interactive Playwright walkthrough & 4 gallery screenshots...")
            webm_file = record_browser_walkthrough(work_dir, durations)
            print("⚙️  [4/4] Muxing 1080p H.264 MP4 + AAC English voiceover...")
            mux_video_and_audio(webm_file, full_audio, OUTPUT_MP4)
            final_dur = get_audio_duration(OUTPUT_MP4)
            size_mb = OUTPUT_MP4.stat().st_size / (1024 * 1024)
            print(f"✅ Done! Video saved to: {OUTPUT_MP4} ({final_dur:.1f}s, {size_mb:.2f} MB)")
            print(f"🖼️  Screenshots saved to: {SCREENSHOTS_DIR}")
    finally:
        if server_proc is not None:
            server_proc.terminate()


if __name__ == "__main__":
    main()
