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
      padding-top: 42px;
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
    #music-bar {{
      position: fixed;
      top: 0; left: 0; right: 0;
      background: rgba(0,0,0,0.75);
      backdrop-filter: blur(8px);
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 7px 14px;
      font-size: 0.8rem;
      color: #ccc;
      z-index: 100;
      flex-wrap: wrap;
    }}
    .music-btn {{
      background: rgba(255,255,255,0.12);
      border: 1px solid rgba(255,255,255,0.2);
      color: #eee;
      padding: 4px 12px;
      border-radius: 20px;
      cursor: pointer;
      white-space: nowrap;
      font-size: 0.8rem;
      transition: background 0.2s;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 5px;
    }}
    .music-btn:hover {{ background: rgba(255,255,255,0.25); }}
    #yt-btn {{ border-color: #ff4444; color: #ff9999; }}
    #yt-btn:hover {{ background: rgba(255,60,60,0.25); }}
    #music-file {{ display: none; }}
    #track-name {{ max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #aef; }}
    #btn-mute {{
      background: none; border: none; color: #eee;
      font-size: 1.2rem; cursor: pointer; padding: 2px 4px;
    }}
    #vol-slider {{ width: 70px; accent-color: #aef; }}
    #music-progress {{ width: 120px; accent-color: #aef; cursor: pointer; }}
    #music-time {{ color: #888; font-size: 0.75rem; white-space: nowrap; }}
    #btn-prev-track, #btn-next-track {{
      background: none; border: none; color: #ccc;
      font-size: 1rem; cursor: pointer; padding: 2px 4px;
    }}
    #btn-prev-track:hover, #btn-next-track:hover {{ color: #fff; }}
    #playlist-count {{ color: #888; font-size: 0.75rem; white-space: nowrap; }}
    #drop-overlay {{
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(100,180,255,0.18);
      border: 4px dashed #aef;
      z-index: 999;
      align-items: center;
      justify-content: center;
      font-size: 2rem;
      color: #aef;
      pointer-events: none;
    }}
    #drop-overlay.active {{ display: flex; }}
  </style>
</head>
<body>
  <!-- Drag-and-drop overlay -->
  <div id="drop-overlay">🎵 Drop audio files here</div>

  <!-- Music bar -->
  <div id="music-bar">
    <a id="yt-btn" class="music-btn"
       href="https://studio.youtube.com/channel/UCmusiclib/music"
       target="_blank" rel="noopener" title="Download free tracks, then drag them in">
      ▶ YouTube Audio Library
    </a>
    <label for="music-file" class="music-btn" title="Pick audio files from your computer">
      🎵 Add Tracks
    </label>
    <input type="file" id="music-file" accept="audio/*" multiple onchange="addTracks(this.files)" />
    <button id="btn-prev-track" onclick="prevTrack()" title="Previous track">⏮</button>
    <span id="track-name">Drop audio files or click Add Tracks</span>
    <button id="btn-next-track" onclick="nextTrack()" title="Next track">⏭</button>
    <span id="playlist-count"></span>
    <button id="btn-mute" onclick="toggleMute()" title="Mute (M)">🔊</button>
    <input type="range" id="vol-slider" min="0" max="1" step="0.02" value="0.7"
           title="Volume" oninput="setVolume(this.value)" />
    <input type="range" id="music-progress" min="0" max="100" value="0"
           title="Seek" oninput="seekMusic(this.value)" />
    <span id="music-time">0:00 / 0:00</span>
  </div>
  <audio id="bg-music"></audio>

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
      if (e.key === "m" || e.key === "M") toggleMute();
    }});

    showSlide(0);

    // ── Music ──────────────────────────────────────────────
    const audio = document.getElementById("bg-music");
    const trackName = document.getElementById("track-name");
    const muteBtn = document.getElementById("btn-mute");
    const volSlider = document.getElementById("vol-slider");
    const progressSlider = document.getElementById("music-progress");
    const musicTime = document.getElementById("music-time");
    const playlistCount = document.getElementById("playlist-count");
    const dropOverlay = document.getElementById("drop-overlay");

    audio.volume = 0.7;
    let playlist = [];
    let trackIndex = 0;

    function addTracks(files) {{
      const audioFiles = Array.from(files).filter(f => f.type.startsWith("audio/"));
      audioFiles.forEach(f => playlist.push({{ url: URL.createObjectURL(f), name: f.name.replace(/\\.[^.]+$/, "") }}));
      updatePlaylistCount();
      if (playlist.length === audioFiles.length) playTrack(0);
    }}

    function playTrack(index) {{
      if (!playlist.length) return;
      trackIndex = ((index % playlist.length) + playlist.length) % playlist.length;
      audio.src = playlist[trackIndex].url;
      trackName.textContent = playlist[trackIndex].name;
      audio.play();
      updatePlaylistCount();
    }}

    function prevTrack() {{ playTrack(trackIndex - 1); }}
    function nextTrack() {{ playTrack(trackIndex + 1); }}

    audio.addEventListener("ended", () => nextTrack());

    function updatePlaylistCount() {{
      playlistCount.textContent = playlist.length > 1
        ? `${{trackIndex + 1}}/${{playlist.length}} tracks` : "";
    }}

    function toggleMute() {{
      audio.muted = !audio.muted;
      muteBtn.textContent = audio.muted ? "🔇" : "🔊";
    }}

    function setVolume(val) {{
      audio.volume = parseFloat(val);
      audio.muted = false;
      muteBtn.textContent = "🔊";
    }}

    function seekMusic(val) {{
      if (audio.duration) audio.currentTime = (val / 100) * audio.duration;
    }}

    function fmtTime(s) {{
      const m = Math.floor(s / 60);
      const sec = Math.floor(s % 60).toString().padStart(2, "0");
      return `${{m}}:${{sec}}`;
    }}

    audio.addEventListener("timeupdate", () => {{
      if (!audio.duration) return;
      const pct = (audio.currentTime / audio.duration) * 100;
      progressSlider.value = pct;
      musicTime.textContent = `${{fmtTime(audio.currentTime)}} / ${{fmtTime(audio.duration)}}`;
    }});

    // Drag-and-drop
    let dragCounter = 0;
    document.addEventListener("dragenter", (e) => {{
      if (Array.from(e.dataTransfer.items).some(i => i.type.startsWith("audio/"))) {{
        dragCounter++;
        dropOverlay.classList.add("active");
      }}
    }});
    document.addEventListener("dragleave", () => {{
      dragCounter--;
      if (dragCounter <= 0) {{ dragCounter = 0; dropOverlay.classList.remove("active"); }}
    }});
    document.addEventListener("dragover", (e) => e.preventDefault());
    document.addEventListener("drop", (e) => {{
      e.preventDefault();
      dragCounter = 0;
      dropOverlay.classList.remove("active");
      addTracks(e.dataTransfer.files);
    }});
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
