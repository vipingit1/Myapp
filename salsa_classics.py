"""
Salsa Classics Downloader
--------------------------
Downloads the greatest Salsa dance tracks of all time as high-quality MP3s.
Covers Golden Era (Fania/Cali), Salsa Romantica, Tropical, and modern hits.

Usage:
    python salsa_classics.py [--limit N] [--output DIR] [--no-download] [--era ERA]

Options:
    --limit N       Number of tracks to download (default: all)
    --output DIR    Output directory (default: ./salsa-classics)
    --no-download   List tracks only, do not download
    --era ERA       Filter by era: golden | romantica | tropical | modern | all (default: all)
"""

import argparse
import io
import json
import sys
from pathlib import Path

# Force UTF-8 output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

try:
    import yt_dlp
except ImportError:
    sys.exit("yt-dlp not installed.  Run:  pip install yt-dlp")

# ─────────────────────────────────────────────────────────────────────────────
# CURATED SALSA PLAYLIST — greatest tracks of all time, grouped by era
# ─────────────────────────────────────────────────────────────────────────────
SALSA_TRACKS = [
    # ── Golden Era / Fania Sound (1960s-1980s) ───────────────────────────────
    {"title": "Quítate Tú",              "artist": "Celia Cruz & Johnny Pacheco",  "era": "golden"},
    {"title": "El Día de Mi Suerte",     "artist": "Héctor Lavoe",                 "era": "golden"},
    {"title": "Mi Gente",                "artist": "Héctor Lavoe",                 "era": "golden"},
    {"title": "Periódico de Ayer",       "artist": "Héctor Lavoe",                 "era": "golden"},
    {"title": "Calle Luna Calle Sol",    "artist": "Willie Colón & Héctor Lavoe",  "era": "golden"},
    {"title": "El Malo",                 "artist": "Willie Colón",                  "era": "golden"},
    {"title": "Idilio",                  "artist": "Willie Colón",                  "era": "golden"},
    {"title": "Aguanile",                "artist": "Willie Colón & Héctor Lavoe",  "era": "golden"},
    {"title": "La Murga",                "artist": "Willie Colón",                  "era": "golden"},
    {"title": "Che Che Colé",            "artist": "Willie Colón",                  "era": "golden"},
    {"title": "Pedro Navaja",            "artist": "Rubén Blades & Willie Colón",  "era": "golden"},
    {"title": "Plástico",                "artist": "Rubén Blades & Willie Colón",  "era": "golden"},
    {"title": "Siembra",                 "artist": "Rubén Blades & Willie Colón",  "era": "golden"},
    {"title": "Pablo Pueblo",            "artist": "Rubén Blades",                  "era": "golden"},
    {"title": "Buscando Guayaba",        "artist": "Celia Cruz",                    "era": "golden"},
    {"title": "La Vida Es un Carnaval",  "artist": "Celia Cruz",                    "era": "golden"},
    {"title": "Guantanamera",            "artist": "Celia Cruz",                    "era": "golden"},
    {"title": "El Barbero",              "artist": "Ismael Rivera",                 "era": "golden"},
    {"title": "Las Caras Lindas",        "artist": "Ismael Rivera",                 "era": "golden"},
    {"title": "Sonido Bestial",          "artist": "Richie Ray & Bobby Cruz",       "era": "golden"},
    {"title": "Jala Jala",               "artist": "Richie Ray & Bobby Cruz",       "era": "golden"},
    {"title": "Oye Como Va",             "artist": "Tito Puente",                   "era": "golden"},
    {"title": "Para los Rumberos",       "artist": "Tito Puente",                   "era": "golden"},
    {"title": "El Negro Zumbón",         "artist": "Tito Puente",                   "era": "golden"},
    {"title": "Bilongo",                 "artist": "Roberto Roena",                 "era": "golden"},
    {"title": "Mi Desengaño",            "artist": "Cheo Feliciano",                "era": "golden"},
    {"title": "Anacaona",                "artist": "Cheo Feliciano",                "era": "golden"},

    # ── Salsa Romántica / Salsa Monga (1980s-1990s) ──────────────────────────
    {"title": "Evidencias",              "artist": "Juan Luis Guerra",              "era": "romantica"},
    {"title": "Burbujas de Amor",        "artist": "Juan Luis Guerra",              "era": "romantica"},
    {"title": "Ojalá Que Llueva Café",   "artist": "Juan Luis Guerra",              "era": "romantica"},
    {"title": "Me Enamora",              "artist": "Juan Luis Guerra",              "era": "romantica"},
    {"title": "Bachata Rosa",            "artist": "Juan Luis Guerra",              "era": "romantica"},
    {"title": "Sigo Pensando en Ti",     "artist": "José Alberto El Canario",       "era": "romantica"},
    {"title": "Con Tus Besos",           "artist": "Lalo Rodríguez",                "era": "romantica"},
    {"title": "Ven Devórame Otra Vez",   "artist": "Lalo Rodríguez",                "era": "romantica"},
    {"title": "Mi Libertad",             "artist": "Eddie Santiago",                "era": "romantica"},
    {"title": "Tú Me Quemas",            "artist": "Frankie Ruiz",                  "era": "romantica"},
    {"title": "Quiero Llenarte",         "artist": "Frankie Ruiz",                  "era": "romantica"},
    {"title": "Desnúdate Mujer",         "artist": "Frankie Ruiz",                  "era": "romantica"},
    {"title": "Un Nuevo Día",            "artist": "Jerry Rivera",                  "era": "romantica"},
    {"title": "Amores de Noche",         "artist": "Jerry Rivera",                  "era": "romantica"},
    {"title": "Cara de Niño",            "artist": "Jerry Rivera",                  "era": "romantica"},
    {"title": "Juego de Ajedrez",        "artist": "Marc Anthony",                  "era": "romantica"},
    {"title": "Hasta Que Me Olvides",    "artist": "Marc Anthony",                  "era": "romantica"},

    # ── Salsa Dura / Tropical / Cali Style (1990s-2000s) ────────────────────
    {"title": "La Rebelión",             "artist": "Joe Arroyo",                    "era": "tropical"},
    {"title": "En Barranquilla Me Quedo","artist": "Joe Arroyo",                    "era": "tropical"},
    {"title": "Yo le Llego",             "artist": "Joe Arroyo",                    "era": "tropical"},
    {"title": "A Las 6",                 "artist": "Grupo Niche",                   "era": "tropical"},
    {"title": "Cali Pachanguero",        "artist": "Grupo Niche",                   "era": "tropical"},
    {"title": "Buenaventura y Caney",    "artist": "Grupo Niche",                   "era": "tropical"},
    {"title": "Una Aventura",            "artist": "Grupo Niche",                   "era": "tropical"},
    {"title": "Déjame Entrar",           "artist": "Guayacán Orquesta",             "era": "tropical"},
    {"title": "Sólo Tú",                 "artist": "Guayacán Orquesta",             "era": "tropical"},
    {"title": "Oiga Mire Vea",           "artist": "Guayacán Orquesta",             "era": "tropical"},
    {"title": "El Preso",                "artist": "Fruko y Sus Tesos",             "era": "tropical"},
    {"title": "El Ausente",              "artist": "Fruko y Sus Tesos",             "era": "tropical"},
    {"title": "El Patillero",            "artist": "Fruko y Sus Tesos",             "era": "tropical"},
    {"title": "Timbalero",               "artist": "Oscar D'León",                  "era": "tropical"},
    {"title": "Llorarás",                "artist": "Oscar D'León",                  "era": "tropical"},
    {"title": "El Son de Alicia",        "artist": "Oscar D'León",                  "era": "tropical"},
    {"title": "No Me Llores",            "artist": "Victor Manuelle",               "era": "tropical"},
    {"title": "Soy Yo",                  "artist": "Victor Manuelle",               "era": "tropical"},
    {"title": "Se Me Va la Voz",         "artist": "Victor Manuelle",               "era": "tropical"},
    {"title": "Ella Lo Que Quiere",      "artist": "Víctor Manuelle",               "era": "tropical"},
    {"title": "Mi Historia Entre tus Dedos", "artist": "Tito Nieves",              "era": "tropical"},
    {"title": "I'll Always Love You",    "artist": "Tito Nieves",                   "era": "tropical"},
    {"title": "No Te Puedo Olvidar",     "artist": "Tito Nieves",                   "era": "tropical"},

    # ── Modern Salsa / Nueva Generación (2000s-Present) ──────────────────────
    {"title": "Vivir Mi Vida",           "artist": "Marc Anthony",                  "era": "modern"},
    {"title": "Flor Pálida",             "artist": "Marc Anthony",                  "era": "modern"},
    {"title": "Parecen Viernes",         "artist": "Marc Anthony",                  "era": "modern"},
    {"title": "Tu Amor Me Hace Bien",    "artist": "Marc Anthony",                  "era": "modern"},
    {"title": "Valio la Pena",           "artist": "Marc Anthony",                  "era": "modern"},
    {"title": "Aguanile (Live)",         "artist": "Marc Anthony",                  "era": "modern"},
    {"title": "La Cita",                 "artist": "Marc Anthony",                  "era": "modern"},
    {"title": "La Rebelión",             "artist": "Carlos Vives",                  "era": "modern"},
    {"title": "Fruta Fresca",            "artist": "Carlos Vives",                  "era": "modern"},
    {"title": "Carito",                  "artist": "Carlos Vives",                  "era": "modern"},
    {"title": "Beso en la Boca",         "artist": "Carlos Vives",                  "era": "modern"},
    {"title": "No Hay Nadie Más",        "artist": "El Gran Combo de Puerto Rico",  "era": "modern"},
    {"title": "Un Verano en Nueva York", "artist": "El Gran Combo de Puerto Rico",  "era": "modern"},
    {"title": "Juana La Cubana",         "artist": "El Gran Combo de Puerto Rico",  "era": "modern"},
    {"title": "Timbalero",               "artist": "Gilberto Santa Rosa",           "era": "modern"},
    {"title": "Que Manera de Quererte",  "artist": "Gilberto Santa Rosa",           "era": "modern"},
    {"title": "Perspectiva",             "artist": "Gilberto Santa Rosa",           "era": "modern"},
    {"title": "Te Propongo",             "artist": "Gilberto Santa Rosa",           "era": "modern"},
    {"title": "Llorarás (Salsa)",        "artist": "Romeo Santos",                  "era": "modern"},
    {"title": "Propuesta Indecente",     "artist": "Romeo Santos",                  "era": "modern"},
    {"title": "Cancioncitas de Amor",    "artist": "La India",                      "era": "modern"},
    {"title": "Mi Mayor Venganza",       "artist": "La India",                      "era": "modern"},
    {"title": "Seré Tuya",               "artist": "La India",                      "era": "modern"},
    {"title": "Nuestro Amor Eterno",     "artist": "Olga Tañón",                    "era": "modern"},
    {"title": "Bandida",                 "artist": "Olga Tañón",                    "era": "modern"},
    {"title": "Así Es la Vida",          "artist": "Tony Vega",                     "era": "modern"},
    {"title": "Amor Secreto",            "artist": "Tony Vega",                     "era": "modern"},
    {"title": "La Noche de Anoche",      "artist": "Bad Bunny & Rosalía",           "era": "modern"},
    {"title": "Latinoamérica",           "artist": "Calle 13",                      "era": "modern"},
    {"title": "Salsa y Control",         "artist": "Afrobeat Combo",                "era": "modern"},
]

ERA_LABELS = {
    "golden":    "Golden Era / Fania Sound (1960s-1980s)",
    "romantica": "Salsa Romántica / Salsa Monga (1980s-1990s)",
    "tropical":  "Salsa Dura / Tropical / Cali Style (1990s-2000s)",
    "modern":    "Modern Salsa / Nueva Generación (2000s-Present)",
}


# ─────────────────────────────────────────────────────────────────────────────
def separator(char="─", width=72):
    print(char * width)


def print_tracklist(tracks: list[dict]):
    current_era = None
    for i, t in enumerate(tracks, 1):
        if t["era"] != current_era:
            current_era = t["era"]
            print()
            separator()
            print(f"  🎺  {ERA_LABELS.get(current_era, current_era)}")
            separator()
            print(f"  {'#':<4} {'Title':<40} {'Artist'}")
            separator()
        title  = t["title"][:39]
        artist = t["artist"][:35]
        print(f"  {i:<4} {title:<40} {artist}")
    print()


def build_search_query(track: dict) -> str:
    return f"{track['title']} {track['artist']} salsa official audio"


def download_tracks(tracks: list[dict], output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(output_dir / "%(title)s.%(ext)s"),
        "default_search": "ytsearch1",   # pick the top YouTube result
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            },
            {"key": "FFmpegMetadata"},
            {"key": "EmbedThumbnail"},
        ],
        "writethumbnail": True,
        "embedthumbnail": True,
        "quiet": False,
        "no_warnings": False,
        "ignoreerrors": True,
        "retries": 3,
    }

    success, failed = [], []

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for i, track in enumerate(tracks, 1):
            query  = build_search_query(track)
            label  = f"[{i}/{len(tracks)}] {track['title']} — {track['artist']}"
            print(f"\n🎵  {label}")
            print(f"    Era    : {ERA_LABELS.get(track['era'], track['era'])}")
            print(f"    Search : {query}")

            try:
                ret = ydl.download([f"ytsearch1:{query}"])
                if ret == 0:
                    success.append(track["title"])
                    print(f"    ✅ Done")
                else:
                    failed.append(track["title"])
                    print(f"    ❌ yt-dlp returned non-zero for this track")
            except Exception as e:
                failed.append(track["title"])
                print(f"    ❌ Error: {e}")

    return success, failed


# ─────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Download the greatest Salsa dance tracks of all time"
    )
    parser.add_argument("--limit",       type=int,  default=0,
                        help="Max tracks to download, 0 = all (default: 0)")
    parser.add_argument("--output",      type=str,  default="salsa-classics",
                        help="Output folder (default: salsa-classics)")
    parser.add_argument("--no-download", action="store_true",
                        help="List tracks only, do not download")
    parser.add_argument("--era",         type=str,  default="all",
                        choices=["all", "golden", "romantica", "tropical", "modern"],
                        help="Filter by era (default: all)")
    args = parser.parse_args()

    print()
    separator("═")
    print("  💃  Salsa Classics Downloader — Greatest Tracks of All Time  🕺")
    separator("═")

    # Filter by era
    tracks = [t for t in SALSA_TRACKS if args.era == "all" or t["era"] == args.era]

    # Apply limit
    if args.limit and args.limit > 0:
        tracks = tracks[: args.limit]

    print(f"\n  Era filter : {args.era}")
    print(f"  Tracks     : {len(tracks)}")
    print()

    print_tracklist(tracks)

    # Save metadata
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    meta_file = out_dir / "salsa_metadata.json"
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(tracks, f, indent=2, ensure_ascii=False)
    print(f"📄  Metadata saved → {meta_file}\n")

    if args.no_download:
        print("ℹ️   --no-download flag set.  Listing complete, no files downloaded.")
        return

    print(f"⬇️   Downloading {len(tracks)} tracks to: {out_dir.resolve()}\n")
    success, failed = download_tracks(tracks, out_dir)

    print()
    separator("═")
    print(f"  ✅  Downloaded : {len(success)}")
    print(f"  ❌  Failed     : {len(failed)}")
    if failed:
        print()
        for title in failed:
            print(f"       • {title}")
    separator("═")
    print(f"\n📂  Files saved to: {out_dir.resolve()}")
    print()


if __name__ == "__main__":
    main()
