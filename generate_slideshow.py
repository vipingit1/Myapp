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
      background: #000;
      color: #eee;
      font-family: sans-serif;
      width: 100vw;
      height: 100vh;
      overflow: hidden;
    }}
    /* Full-frame image fills entire viewport */
    #slide-container {{
      position: fixed;
      inset: 0;
      z-index: 0;
    }}
    #slide-img {{
      width: 100%;
      height: 100%;
      object-fit: contain;
      object-position: center;
      transition: opacity 0.6s ease;
    }}
    #slide-img.fade {{ opacity: 0; }}
    /* Arrows */
    .arrow {{
      position: fixed;
      top: 50%;
      transform: translateY(-50%);
      background: rgba(0,0,0,0.35);
      border: none;
      color: white;
      font-size: 2.5rem;
      padding: 14px 18px;
      cursor: pointer;
      border-radius: 6px;
      z-index: 20;
      transition: background 0.2s;
      user-select: none;
      opacity: 0;
      transition: opacity 0.2s, background 0.2s;
    }}
    body:hover .arrow {{ opacity: 1; }}
    .arrow:hover {{ background: rgba(0,0,0,0.65); }}
    #btn-prev {{ left: 12px; }}
    #btn-next {{ right: 12px; }}
    /* Info bar — overlaid at bottom, auto-hides */
    #info-bar {{
      position: fixed;
      bottom: 0; left: 0; right: 0;
      z-index: 20;
      display: flex;
      align-items: center;
      gap: 14px;
      padding: 10px 20px;
      background: linear-gradient(transparent, rgba(0,0,0,0.75));
      font-size: 0.85rem;
      color: #ccc;
      opacity: 0;
      transition: opacity 0.3s;
    }}
    body:hover #info-bar {{ opacity: 1; }}
    #counter {{ font-weight: bold; color: #fff; white-space: nowrap; }}
    #caption {{ flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    #btn-play {{
      background: rgba(255,255,255,0.2);
      border: none;
      color: white;
      padding: 6px 14px;
      border-radius: 20px;
      cursor: pointer;
      font-size: 0.85rem;
      white-space: nowrap;
      transition: background 0.2s;
    }}
    #btn-play:hover {{ background: rgba(255,255,255,0.4); }}
    #speed-label {{ color: #aaa; font-size: 0.8rem; white-space: nowrap; }}
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

    /* ── Slide scrubber bar ── */
    #scrubber-wrap {{
      position: fixed;
      bottom: 52px; left: 0; right: 0;
      z-index: 25;
      padding: 0 20px;
      opacity: 0;
      transition: opacity 0.3s;
    }}
    body:hover #scrubber-wrap {{ opacity: 1; }}
    #scrubber {{
      width: 100%;
      accent-color: #fff;
      cursor: pointer;
      height: 4px;
    }}

    /* ── Jump / Go-to input ── */
    #goto-wrap {{
      display: flex;
      align-items: center;
      gap: 4px;
      white-space: nowrap;
    }}
    #goto-input {{
      width: 56px;
      background: rgba(255,255,255,0.15);
      border: 1px solid rgba(255,255,255,0.3);
      color: #fff;
      border-radius: 6px;
      padding: 3px 6px;
      font-size: 0.8rem;
      text-align: center;
    }}
    #goto-input:focus {{ outline: none; border-color: #fff; }}
    #btn-goto {{
      background: rgba(255,255,255,0.2);
      border: none; color: #fff;
      padding: 4px 9px; border-radius: 6px;
      cursor: pointer; font-size: 0.8rem;
    }}
    #btn-goto:hover {{ background: rgba(255,255,255,0.4); }}

    /* ── Thumbnail filmstrip panel ── */
    #filmstrip {{
      display: none;
      position: fixed;
      left: 0; right: 0; bottom: 0;
      height: 110px;
      z-index: 30;
      background: rgba(0,0,0,0.85);
      backdrop-filter: blur(6px);
      overflow-x: auto;
      overflow-y: hidden;
      white-space: nowrap;
      padding: 8px 12px;
      gap: 8px;
      scroll-behavior: smooth;
    }}
    #filmstrip.open {{ display: flex; align-items: center; }}
    .thumb {{
      flex-shrink: 0;
      width: 80px;
      height: 90px;
      object-fit: cover;
      border-radius: 4px;
      cursor: pointer;
      border: 2px solid transparent;
      opacity: 0.65;
      transition: opacity 0.2s, border-color 0.2s;
    }}
    .thumb:hover {{ opacity: 1; }}
    .thumb.active {{ border-color: #fff; opacity: 1; }}
    #btn-filmstrip {{
      background: rgba(255,255,255,0.2);
      border: none; color: #fff;
      padding: 6px 10px; border-radius: 20px;
      cursor: pointer; font-size: 0.85rem;
      white-space: nowrap;
    }}
    #btn-filmstrip:hover {{ background: rgba(255,255,255,0.4); }}
  </style>
</head>
<body>
  <!-- Drag-and-drop overlay -->
  <div id="drop-overlay">🎵 Drop audio files here</div>

  <!-- Music bar (top) -->
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

  <!-- Full-frame slide -->
  <div id="slide-container">
    <img id="slide-img" src="" alt="slide" />
  </div>

  <!-- Slide progress scrubber -->
  <div id="scrubber-wrap">
    <input type="range" id="scrubber" min="0" max="100" value="0" title="Jump to slide" />
  </div>

  <!-- Nav arrows -->
  <button class="arrow" id="btn-prev" onclick="move(-1)">&#8592;</button>
  <button class="arrow" id="btn-next" onclick="move(1)">&#8594;</button>

  <!-- Info / controls bar (bottom overlay) -->
  <div id="info-bar">
    <span id="counter"></span>
    <span id="caption"></span>
    <div id="goto-wrap">
      <input type="number" id="goto-input" min="1" placeholder="#" title="Go to slide number" />
      <button id="btn-goto" onclick="gotoSlide()">Go</button>
    </div>
    <button id="btn-filmstrip" onclick="toggleFilmstrip()" title="Thumbnail browser (T)">🎞 Thumbnails</button>
    <button id="btn-play" onclick="togglePlay()">&#9654; Play</button>
    <span id="speed-label">Speed:</span>
    <input type="range" id="speed" min="1" max="10" value="4" title="Slide interval (seconds)" />
    <span id="speed-val">4s</span>
    <button id="btn-fs" onclick="toggleFullscreen()" title="Fullscreen (F)" style="background:rgba(255,255,255,0.2);border:none;color:#fff;padding:6px 10px;border-radius:20px;cursor:pointer;font-size:0.85rem;">⛶ Fullscreen</button>
  </div>

  <!-- Thumbnail filmstrip -->
  <div id="filmstrip"></div>

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
    const scrubber = document.getElementById("scrubber");
    const filmstrip = document.getElementById("filmstrip");
    const gotoInput = document.getElementById("goto-input");

    scrubber.max = images.length - 1;

    function showSlide(index) {{
      img.classList.add("fade");
      setTimeout(() => {{
        current = ((index % images.length) + images.length) % images.length;
        img.src = images[current].src;
        img.alt = images[current].name;
        counter.textContent = `${{current + 1}} / ${{images.length}}`;
        caption.textContent = images[current].name;
        img.classList.remove("fade");
        scrubber.value = current;
        updateActiveThumb();
      }}, 300);
    }}

    scrubber.addEventListener("input", () => showSlide(parseInt(scrubber.value)));

    function gotoSlide() {{
      const n = parseInt(gotoInput.value);
      if (!isNaN(n) && n >= 1 && n <= images.length) {{
        showSlide(n - 1);
        gotoInput.value = "";
      }}
    }}
    gotoInput.addEventListener("keydown", (e) => {{ if (e.key === "Enter") gotoSlide(); }});

    // ── Filmstrip ──
    let filmstripBuilt = false;

    function toggleFilmstrip() {{
      filmstrip.classList.toggle("open");
      document.getElementById("btn-filmstrip").textContent =
        filmstrip.classList.contains("open") ? "✕ Close" : "🎞 Thumbnails";
      if (!filmstripBuilt) buildFilmstrip();
      scrollToActiveThumb();
    }}

    function buildFilmstrip() {{
      filmstripBuilt = true;
      images.forEach((im, i) => {{
        const t = document.createElement("img");
        t.className = "thumb" + (i === current ? " active" : "");
        t.src = im.src;
        t.title = `[${{i+1}}] ${{im.name}}`;
        t.loading = "lazy";
        t.onclick = () => {{ showSlide(i); }};
        filmstrip.appendChild(t);
      }});
    }}

    function updateActiveThumb() {{
      if (!filmstripBuilt) return;
      filmstrip.querySelectorAll(".thumb").forEach((t, i) => {{
        t.classList.toggle("active", i === current);
      }});
      scrollToActiveThumb();
    }}

    function scrollToActiveThumb() {{
      if (!filmstripBuilt) return;
      const active = filmstrip.querySelector(".thumb.active");
      if (active) active.scrollIntoView({{ behavior: "smooth", block: "nearest", inline: "center" }});
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
      if (e.target === gotoInput) return;
      if (e.key === "ArrowRight" || e.key === "ArrowDown") move(1);
      if (e.key === "ArrowLeft" || e.key === "ArrowUp") move(-1);
      if (e.key === " ") {{ e.preventDefault(); togglePlay(); }}
      if (e.key === "m" || e.key === "M") toggleMute();
      if (e.key === "f" || e.key === "F") toggleFullscreen();
      if (e.key === "t" || e.key === "T") toggleFilmstrip();
    }});

    function toggleFullscreen() {{
      if (!document.fullscreenElement) {{
        document.documentElement.requestFullscreen();
        document.getElementById("btn-fs").textContent = "✕ Exit";
      }} else {{
        document.exitFullscreen();
        document.getElementById("btn-fs").textContent = "⛶ Fullscreen";
      }}
    }}

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
