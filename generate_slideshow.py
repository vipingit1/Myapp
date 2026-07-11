"""
Scans the C drive for image files and generates a self-contained HTML slideshow.
Run: python generate_slideshow.py
Output: slideshow.html (open in any browser)
"""

import os
import sys
from pathlib import Path

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif'}
SCAN_ROOT = "C:\\"
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "slideshow.html")

SKIP_DIRS = {
    "Windows", "Program Files", "Program Files (x86)",
    "$Recycle.Bin", "System Volume Information", "ProgramData",
    "AppData", "node_modules", ".git"
}


def scan_images(root):
    images = []
    print(f"Scanning {root} for images (this may take a moment)...")
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip system/noisy directories
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS and not d.startswith('.')
        ]
        for filename in filenames:
            if Path(filename).suffix.lower() in IMAGE_EXTENSIONS:
                full_path = os.path.join(dirpath, filename)
                # Convert to file:// URL with forward slashes for the browser
                file_url = "file:///" + full_path.replace("\\", "/")
                images.append((file_url, filename))

    print(f"Found {len(images)} images.")
    return images


def generate_html(images, output_path):
    if not images:
        print("No images found. Exiting.")
        sys.exit(1)

    image_js_array = ",\n    ".join(
        f'{{"src": "{src}", "name": "{name.replace(chr(34), chr(39))}"}}'
        for src, name in images
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Photo Slideshow</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      background: #111;
      color: #eee;
      font-family: sans-serif;
      height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      overflow: hidden;
    }}
    #slide-container {{
      position: relative;
      width: 100vw;
      height: 90vh;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    #slide-img {{
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
      border-radius: 4px;
      transition: opacity 0.5s ease;
    }}
    #slide-img.fade {{ opacity: 0; }}
    .arrow {{
      position: absolute;
      top: 50%;
      transform: translateY(-50%);
      background: rgba(255,255,255,0.15);
      border: none;
      color: white;
      font-size: 2.5rem;
      padding: 12px 18px;
      cursor: pointer;
      border-radius: 6px;
      z-index: 10;
      transition: background 0.2s;
      user-select: none;
    }}
    .arrow:hover {{ background: rgba(255,255,255,0.35); }}
    #btn-prev {{ left: 12px; }}
    #btn-next {{ right: 12px; }}
    #info-bar {{
      height: 10vh;
      display: flex;
      align-items: center;
      gap: 16px;
      font-size: 0.85rem;
      color: #aaa;
    }}
    #counter {{ font-weight: bold; color: #fff; }}
    #caption {{ max-width: 60vw; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    #btn-play {{
      background: rgba(255,255,255,0.15);
      border: none;
      color: white;
      padding: 6px 14px;
      border-radius: 20px;
      cursor: pointer;
      font-size: 0.85rem;
      transition: background 0.2s;
    }}
    #btn-play:hover {{ background: rgba(255,255,255,0.3); }}
    #speed-label {{ color: #888; font-size: 0.8rem; }}
    input[type=range] {{ accent-color: #fff; cursor: pointer; }}
  </style>
</head>
<body>
  <div id="slide-container">
    <button class="arrow" id="btn-prev" onclick="move(-1)">&#8592;</button>
    <img id="slide-img" src="" alt="slide" />
    <button class="arrow" id="btn-next" onclick="move(1)">&#8594;</button>
  </div>
  <div id="info-bar">
    <span id="counter"></span>
    <span id="caption"></span>
    <button id="btn-play" onclick="togglePlay()">&#9654; Play</button>
    <span id="speed-label">Speed:</span>
    <input type="range" id="speed" min="1" max="10" value="4" title="Slide interval (seconds)" />
    <span id="speed-val">4s</span>
  </div>

  <script>
    const images = [
    {image_js_array}
    ];

    let current = 0;
    let playing = false;
    let timer = null;
    const img = document.getElementById("slide-img");
    const counter = document.getElementById("counter");
    const caption = document.getElementById("caption");
    const speedInput = document.getElementById("speed");
    const speedVal = document.getElementById("speed-val");
    const playBtn = document.getElementById("btn-play");

    function showSlide(index) {{
      img.classList.add("fade");
      setTimeout(() => {{
        current = ((index % images.length) + images.length) % images.length;
        img.src = images[current].src;
        img.alt = images[current].name;
        counter.textContent = `${{current + 1}} / ${{images.length}}`;
        caption.textContent = images[current].name;
        img.classList.remove("fade");
      }}, 300);
    }}

    function move(dir) {{
      showSlide(current + dir);
    }}

    function togglePlay() {{
      playing = !playing;
      playBtn.textContent = playing ? "⏸ Pause" : "▶ Play";
      if (playing) {{
        timer = setInterval(() => move(1), parseInt(speedInput.value) * 1000);
      }} else {{
        clearInterval(timer);
      }}
    }}

    speedInput.addEventListener("input", () => {{
      speedVal.textContent = speedInput.value + "s";
      if (playing) {{
        clearInterval(timer);
        timer = setInterval(() => move(1), parseInt(speedInput.value) * 1000);
      }}
    }});

    document.addEventListener("keydown", (e) => {{
      if (e.key === "ArrowRight" || e.key === "ArrowDown") move(1);
      if (e.key === "ArrowLeft" || e.key === "ArrowUp") move(-1);
      if (e.key === " ") {{ e.preventDefault(); togglePlay(); }}
    }});

    showSlide(0);
  </script>
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Slideshow saved to: {output_path}")


if __name__ == "__main__":
    images = scan_images(SCAN_ROOT)
    generate_html(images, OUTPUT_FILE)
    print("Open slideshow.html in your browser to view it.")
