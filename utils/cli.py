import sys
import os
import logging
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
)
from rich.logging import RichHandler

from main import (
    run_server,
    run_autodetect,
    is_port_in_use,
    download_path as default_download_path,
)

app = typer.Typer(
    name="vault",
    help="Vault - Video Archive App",
    no_args_is_help=False,
    invoke_without_command=True,
)

console = Console()


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    port: Annotated[int, typer.Option("--port", "-p", help="Sunucu portu", rich_help_panel="Global Seçenekler")] = 8000,
    verbose: Annotated[bool, typer.Option("--verbose", help="Detaylı log çıktısı", rich_help_panel="Global Seçenekler")] = False,
):
    if verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(message)s",
            datefmt="[%X]",
            handlers=[RichHandler(rich_tracebacks=True)],
        )
    else:
        logging.basicConfig(level=logging.WARNING)

    if ctx.invoked_subcommand is None:
        run_autodetect(port=port)
    else:
        ctx.obj = {"port": port, "verbose": verbose}


# ── run ──────────────────────────────────────────────────────────────

@app.command()
def run(
    ctx: typer.Context,
    web: Annotated[bool, typer.Option("--web", help="Sadece sunucuyu başlat")] = False,
    desktop: Annotated[bool, typer.Option("--desktop", help="Sunucuyu başlat ve tarayıcıda aç")] = False,
    mobile: Annotated[bool, typer.Option("--mobile", help="Sunucuyu başlat ve Flet WebView ile aç")] = False,
):
    """Vault sunucusunu başlatır."""
    if not any([web, desktop, mobile]):
        typer.echo("Hata: --web, --desktop veya --mobile flag'lerinden biri gereklidir.", err=True)
        raise typer.Exit(1)

    mode = "web"
    if desktop:
        mode = "desktop"
    elif mobile:
        mode = "mobile"

    port = ctx.obj["port"]
    host = "127.0.0.1"
    while is_port_in_use(port):
        port += 1

    run_server(host=host, port=port, mode=mode)


# ── download ─────────────────────────────────────────────────────────

def _get_format_string(fmt: str) -> str:
    mapping = {
        "best": "bestvideo+bestaudio/best",
        "1080p": "bestvideo[height<=1080][vcodec^=avc1]+bestaudio[ext=m4a]/best",
        "720p": "bestvideo[height<=720][vcodec^=avc1]+bestaudio[ext=m4a]/best",
        "480p": "bestvideo[height<=480]+bestaudio[ext=m4a]/best",
        "360p": "bestvideo[height<=360]+bestaudio[ext=m4a]/best",
        "bestvideo+bestaudio": "bestvideo+bestaudio",
    }
    return mapping.get(fmt, fmt)


@app.command()
def download(
    url: Annotated[str, typer.Argument(help="Video veya oynatma listesi URL'si")],
    format: Annotated[str, typer.Option("--format", "-f", help="Video formatı: best, 1080p, 720p, 480p, 360p, bestvideo+bestaudio")] = "best",
    output: Annotated[Path, typer.Option("--output", "-o", help="Çıktı dizini", file_okay=False, dir_okay=True)] = Path(default_download_path),
    audio_only: Annotated[bool, typer.Option("--audio-only", help="Sadece ses indir (MP3)")] = False,
    no_merge: Annotated[bool, typer.Option("--no-merge", help="Video ve ses ayrı dosyalar olarak kalsın")] = False,
):
    """Video veya oynatma listesi indirir."""
    import yt_dlp

    output_dir = str(output.expanduser().resolve())
    os.makedirs(output_dir, exist_ok=True)

    if audio_only:
        ydl_opts = {
            "format": "bestaudio",
            "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
            }],
        }
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("[yellow]Ses indiriliyor...", total=None)
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            progress.update(task, completed=True)

        typer.echo(f"✔ Ses indirildi: {output_dir}")
        return

    fmt_str = _get_format_string(format)

    video_tmp = os.path.join(output_dir, ".tmp_video.mp4")
    audio_tmp = os.path.join(output_dir, ".tmp_audio.m4a")

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        info_task = progress.add_task("[cyan]Bilgiler alınıyor...", total=None)
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            info = ydl.extract_info(url, download=False)
            safe_title = info.get("title", "video")
        progress.update(info_task, completed=True)

        output_file = os.path.join(output_dir, f"{safe_title}.mp4")

        if no_merge:
            ydl_opts = {
                "format": fmt_str,
                "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
                "quiet": True,
                "no_warnings": True,
                "noprogress": True,
            }
            dl_task = progress.add_task(f"[green]İndiriliyor: {safe_title}", total=100)
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            progress.update(dl_task, completed=100)
        else:
            vid_opts = {
                "format": "bestvideo[height<=1080][vcodec^=avc1]/bestvideo[height<=1080]/bestvideo",
                "outtmpl": video_tmp,
                "quiet": True,
                "no_warnings": True,
                "noprogress": True,
            }
            dl_task = progress.add_task(f"[green]Video: {safe_title}", total=100)
            with yt_dlp.YoutubeDL(vid_opts) as ydl:
                ydl.download([url])
            progress.update(dl_task, completed=100)

            aud_opts = {
                "format": "bestaudio[ext=m4a]/bestaudio",
                "outtmpl": audio_tmp,
                "quiet": True,
                "no_warnings": True,
                "noprogress": True,
            }
            aud_task = progress.add_task(f"[blue]Ses: {safe_title}", total=100)
            with yt_dlp.YoutubeDL(aud_opts) as ydl:
                ydl.download([url])
            progress.update(aud_task, completed=100)

            merge_task = progress.add_task(f"[magenta]Birleştiriliyor...", total=None)
            try:
                from utils.ffmpeg import ffmpeg
                ret = ffmpeg(
                    [
                        "-loglevel", "warning",
                        "-i", os.path.basename(video_tmp),
                        "-i", os.path.basename(audio_tmp),
                        "-c:v", "copy",
                        "-c:a", "aac",
                        "-movflags", "+faststart",
                        "-y",
                        os.path.basename(output_file),
                    ],
                    workspace_dir=output_dir,
                )
                if ret != 0:
                    typer.echo(f"⚠ FFmpeg birleştirme başarısız (kod: {ret})", err=True)
                else:
                    for f in [video_tmp, audio_tmp]:
                        try:
                            os.remove(f)
                        except OSError:
                            pass
            except Exception as e:
                typer.echo(f"⚠ Birleştirme hatası: {e}", err=True)

            progress.update(merge_task, completed=True)

    typer.echo(f"✔ İndirme tamamlandı: {output_file}")


# ── search ───────────────────────────────────────────────────────────

@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Arama sorgusu")],
    type: Annotated[str, typer.Option("--type", "-t", help="Arama tipi: video, channel, playlist, shorts")] = "video",
    sort: Annotated[str, typer.Option("--sort", "-s", help="Sıralama: relevance, date, views, likes")] = "relevance",
    date: Annotated[str, typer.Option("--date", "-d", help="Tarih filtresi: any, today, week, month, year")] = "any",
    limit: Annotated[int, typer.Option("--limit", "-l", help="Gösterilecek sonuç sayısı")] = 10,
):
    """YouTube'da video, kanal veya oynatma listesi arar."""
    from utils.search_engine import search_youtube

    with console.status("[cyan]Aranıyor...", spinner="dots"):
        results = search_youtube(query=query, type_filter=type, date_filter=date, sort_filter=sort)

    items = results[:limit]

    if not items:
        typer.echo("Sonuç bulunamadı.")
        return

    if type == "channel":
        table = Table(title=f"Kanallar: {query}")
        table.add_column("Kanal", style="cyan")
        table.add_column("Abone", style="yellow")
        table.add_column("Video", style="green")
        table.add_column("Doğrulandı", style="blue")
        for item in items:
            table.add_row(
                item.get("title", "?"),
                item.get("subscriber_count", "?"),
                str(item.get("video_count", "?")),
                "✓" if item.get("verified") else "✗",
            )
    elif type == "playlist":
        table = Table(title=f"Oynatma Listeleri: {query}")
        table.add_column("Başlık", style="cyan")
        table.add_column("Kanal", style="yellow")
        table.add_column("Video Sayısı", style="green")
        for item in items:
            table.add_row(
                item.get("title", "?"),
                item.get("channel", "?"),
                str(item.get("video_count", "?")),
            )
    else:
        table = Table(title=f"Videolar: {query}")
        table.add_column("Başlık", style="cyan")
        table.add_column("Kanal", style="yellow")
        table.add_column("Süre", style="green")
        table.add_column("Görüntülenme", style="blue")
        table.add_column("Link", style="dim")
        for item in items:
            table.add_row(
                item.get("title", "?"),
                item.get("channel", "?"),
                str(item.get("duration", "?")),
                str(item.get("view_count", "?")),
                item.get("url", "?"),
            )

    console.print(table)
    typer.echo(f"\nToplam {len(items)} sonuç gösteriliyor (--limit ile değiştirebilirsiniz).")


# ── info ─────────────────────────────────────────────────────────────

@app.command()
def info(
    url: Annotated[str, typer.Argument(help="Video, kanal veya oynatma listesi URL'si")],
):
    """Video/kanal/playlist hakkında detaylı bilgi gösterir."""
    import yt_dlp

    with console.status("[cyan]Bilgiler alınıyor...", spinner="dots"):
        ydl_opts = {"quiet": True, "no_warnings": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            meta = ydl.extract_info(url, download=False)

    console.print_json(data=meta)


# ── Entry Point ──────────────────────────────────────────────────────

def main():
    app()


if __name__ == "__main__":
    main()
