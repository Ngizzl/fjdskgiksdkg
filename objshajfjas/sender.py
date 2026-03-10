import os
import sys
import json
import zipfile
import socket
import platform
import math
import tempfile
import shutil
from datetime import datetime, timezone

import requests
import psutil
import cpuinfo
from colorama import Fore, Style, init

try:
    import GPUtil
    GPU_AVAILABLE = True
except Exception:
    GPU_AVAILABLE = False

init(autoreset=True)

# ─── Constants ────────────────────────────────────────────────────────────────
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
DISCORD_MAX_FILE_SIZE = 8 * 1024 * 1024  # 8 MB (free tier limit)
SPLIT_CHUNK_SIZE = DISCORD_MAX_FILE_SIZE - (512 * 1024)  # leave small margin


# ─── Helpers ──────────────────────────────────────────────────────────────────
def banner():
    print(f"""
{Fore.CYAN}╔══════════════════════════════════════════════════╗
║  {Fore.WHITE}📡  Discord Webhook Sender  📡{Fore.CYAN}                  ║
║  {Fore.WHITE}Zip & send directories + PC info via webhook{Fore.CYAN}    ║
╚══════════════════════════════════════════════════╝{Style.RESET_ALL}
""")


def load_or_ask_webhook() -> str:
    """Load webhook URL from config or ask user."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
            url = data.get("webhook_url", "")
            if url:
                print(f"{Fore.GREEN}[✓] Webhook loaded from config.json{Style.RESET_ALL}")
                return url

    url = input(f"{Fore.YELLOW}[?] Enter Discord Webhook URL: {Style.RESET_ALL}").strip()
    if not url.startswith("https://discord.com/api/webhooks/"):
        print(f"{Fore.RED}[✗] Invalid webhook URL.{Style.RESET_ALL}")
        sys.exit(1)

    save = input(f"{Fore.YELLOW}[?] Save webhook for future use? (y/n): {Style.RESET_ALL}").strip().lower()
    if save == "y":
        with open(CONFIG_FILE, "w") as f:
            json.dump({"webhook_url": url}, f, indent=2)
        print(f"{Fore.GREEN}[✓] Webhook saved to config.json{Style.RESET_ALL}")
    return url


# ─── System Info ──────────────────────────────────────────────────────────────
def get_public_ip() -> str:
    try:
        return requests.get("https://api.ipify.org", timeout=5).text
    except Exception:
        return "N/A"


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "N/A"


def get_gpu_info() -> str:
    if not GPU_AVAILABLE:
        return "N/A (GPUtil not available)"
    try:
        gpus = GPUtil.getGPUs()
        if not gpus:
            return "No dedicated GPU detected"
        lines = []
        for g in gpus:
            lines.append(f"{g.name} — {g.memoryTotal:.0f} MB VRAM ({g.memoryUsed:.0f} MB used)")
        return "\n".join(lines)
    except Exception:
        return "N/A"


def bytes_to_human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.2f} {unit}"
        n /= 1024
    return f"{n:.2f} PB"


def gather_system_info() -> dict:
    cpu = cpuinfo.get_cpu_info()
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage("/") if platform.system() != "Windows" else psutil.disk_usage("C:\\")

    return {
        "hostname": socket.gethostname(),
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "cpu": cpu.get("brand_raw", "Unknown CPU"),
        "cpu_cores": f"{psutil.cpu_count(logical=False)}C / {psutil.cpu_count(logical=True)}T",
        "cpu_usage": f"{psutil.cpu_percent(interval=1):.1f}%",
        "ram_total": bytes_to_human(vm.total),
        "ram_used": bytes_to_human(vm.used),
        "ram_pct": f"{vm.percent}%",
        "disk_total": bytes_to_human(disk.total),
        "disk_used": bytes_to_human(disk.used),
        "disk_pct": f"{disk.percent}%",
        "gpu": get_gpu_info(),
        "public_ip": get_public_ip(),
        "local_ip": get_local_ip(),
        "python": platform.python_version(),
    }


# ─── Zip Logic ────────────────────────────────────────────────────────────────
def zip_directory(dir_path: str, output_zip: str) -> str:
    """Zip an entire directory into a single .zip file."""
    print(f"{Fore.CYAN}[⏳] Zipping directory: {dir_path}{Style.RESET_ALL}")
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(dir_path):
            for file in files:
                full_path = os.path.join(root, file)
                arcname = os.path.relpath(full_path, dir_path)
                try:
                    zf.write(full_path, arcname)
                except PermissionError:
                    print(f"{Fore.YELLOW}  [⚠] Skipped (permission denied): {arcname}{Style.RESET_ALL}")
    size = os.path.getsize(output_zip)
    print(f"{Fore.GREEN}[✓] Zip created: {bytes_to_human(size)}{Style.RESET_ALL}")
    return output_zip


def split_file(filepath: str, chunk_size: int) -> list[str]:
    """Split a file into parts of chunk_size bytes. Returns list of part paths."""
    file_size = os.path.getsize(filepath)
    num_parts = math.ceil(file_size / chunk_size)
    parts = []
    base = filepath

    print(f"{Fore.CYAN}[⏳] Splitting into {num_parts} parts (~{bytes_to_human(chunk_size)} each){Style.RESET_ALL}")

    with open(filepath, "rb") as f:
        for i in range(num_parts):
            part_path = f"{base}.part{i + 1:03d}"
            with open(part_path, "wb") as pf:
                pf.write(f.read(chunk_size))
            parts.append(part_path)
            print(f"{Fore.GREEN}  [✓] Part {i + 1}/{num_parts}: {os.path.basename(part_path)}{Style.RESET_ALL}")

    return parts


# ─── Discord Sending ─────────────────────────────────────────────────────────
def build_embed(info: dict, dir_path: str, zip_size: str, num_parts: int) -> dict:
    """Build a rich Discord embed with system info."""
    embed = {
        "title": "📦 Directory Zip Upload",
        "color": 0x5865F2,  # Discord blurple
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": "Discord Webhook Sender • github.com"},
        "thumbnail": {"url": "https://i.imgur.com/J6LeoUb.png"},
        "fields": [
            {
                "name": "📁 Directory",
                "value": f"```{dir_path}```",
                "inline": False,
            },
            {
                "name": "🗜️ Archive Size",
                "value": f"`{zip_size}`  •  **{num_parts}** part(s)",
                "inline": False,
            },
            {
                "name": "🖥️ Hostname",
                "value": f"`{info['hostname']}`",
                "inline": True,
            },
            {
                "name": "💻 OS",
                "value": f"`{info['os']}`",
                "inline": False,
            },
            {
                "name": "🧠 CPU",
                "value": f"`{info['cpu']}`\n{info['cpu_cores']}  •  Usage: **{info['cpu_usage']}**",
                "inline": False,
            },
            {
                "name": "🎮 GPU",
                "value": f"```{info['gpu']}```",
                "inline": False,
            },
            {
                "name": "💾 RAM",
                "value": f"{info['ram_used']} / {info['ram_total']}  (**{info['ram_pct']}**)",
                "inline": True,
            },
            {
                "name": "📀 Disk",
                "value": f"{info['disk_used']} / {info['disk_total']}  (**{info['disk_pct']}**)",
                "inline": True,
            },
            {
                "name": "🌐 Public IP",
                "value": f"||`{info['public_ip']}`||",
                "inline": True,
            },
            {
                "name": "🏠 Local IP",
                "value": f"`{info['local_ip']}`",
                "inline": True,
            },
            {
                "name": "🐍 Python",
                "value": f"`{info['python']}`",
                "inline": True,
            },
        ],
    }
    return embed


def send_webhook(webhook_url: str, embed: dict, file_paths: list[str]):
    """Send embed + files to Discord webhook."""
    # 1) Send the embed first
    print(f"\n{Fore.CYAN}[⏳] Sending system info embed...{Style.RESET_ALL}")
    payload = {"embeds": [embed]}
    r = requests.post(webhook_url, json=payload)
    if r.status_code in (200, 204):
        print(f"{Fore.GREEN}[✓] Embed sent!{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}[✗] Failed to send embed: {r.status_code} — {r.text}{Style.RESET_ALL}")

    # 2) Send each file part
    for i, fpath in enumerate(file_paths, 1):
        fname = os.path.basename(fpath)
        fsize = bytes_to_human(os.path.getsize(fpath))
        print(f"{Fore.CYAN}[⏳] Uploading part {i}/{len(file_paths)}: {fname} ({fsize}){Style.RESET_ALL}")

        with open(fpath, "rb") as f:
            r = requests.post(
                webhook_url,
                files={"file": (fname, f)},
                data={"content": f"📎 **Part {i}/{len(file_paths)}** — `{fname}`"},
            )

        if r.status_code in (200, 204):
            print(f"{Fore.GREEN}[✓] Uploaded: {fname}{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}[✗] Failed: {r.status_code} — {r.text}{Style.RESET_ALL}")


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    banner()

    # Webhook
    webhook_url = load_or_ask_webhook()

    # Directory to zip
    dir_path = input(f"\n{Fore.YELLOW}[?] Enter full path of directory to ZIP: {Style.RESET_ALL}").strip().strip('"')
    if not os.path.isdir(dir_path):
        print(f"{Fore.RED}[✗] Directory does not exist: {dir_path}{Style.RESET_ALL}")
        sys.exit(1)

    dir_name = os.path.basename(os.path.normpath(dir_path))

    # Create temp workspace
    tmp_dir = tempfile.mkdtemp(prefix="webhook_sender_")

    try:
        # Zip
        zip_path = os.path.join(tmp_dir, f"{dir_name}.zip")
        zip_directory(dir_path, zip_path)
        zip_size_bytes = os.path.getsize(zip_path)
        zip_size_human = bytes_to_human(zip_size_bytes)

        # Split if needed
        if zip_size_bytes > DISCORD_MAX_FILE_SIZE:
            print(f"{Fore.YELLOW}[!] Zip exceeds 8 MB limit — splitting...{Style.RESET_ALL}")
            parts = split_file(zip_path, SPLIT_CHUNK_SIZE)
        else:
            parts = [zip_path]

        # Gather system info
        print(f"\n{Fore.CYAN}[⏳] Gathering system info...{Style.RESET_ALL}")
        info = gather_system_info()
        print(f"{Fore.GREEN}[✓] System info collected!{Style.RESET_ALL}")

        # Build embed & send
        embed = build_embed(info, dir_path, zip_size_human, len(parts))
        send_webhook(webhook_url, embed, parts)

        print(f"\n{Fore.GREEN}{'═' * 50}")
        print(f"  ✅  All done! Check your Discord channel.")
        print(f"{'═' * 50}{Style.RESET_ALL}\n")

    finally:
        # Cleanup temp files
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
