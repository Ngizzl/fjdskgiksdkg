# 📡 Discord Webhook Sender

A Python CLI tool that **zips a directory** and **sends it to Discord** via a webhook, along with a rich embed displaying your **PC's system information**.

![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python)
![License](https://img.shields.io/badge/License-MIT-green)

---

## ✨ Features

- **📦 Directory Zipping** — Compresses any directory into a `.zip` archive
- **✂️ Auto-Splitting** — Splits archives exceeding Discord's 8 MB upload limit into multiple parts
- **🖥️ System Info Embed** — Sends a formatted Discord embed with:
  - 🧠 CPU (model, cores, usage)
  - 🎮 GPU (name, VRAM)
  - 💾 RAM (used / total)
  - 📀 Disk (used / total)
  - 🌐 Public & Local IP
  - 💻 OS & Python version
- **🔒 Spoiler-tagged IP** — Public IP is hidden behind a Discord spoiler tag
- **💾 Webhook Persistence** — Optionally saves webhook URL to `config.json` for reuse
- **🎨 Colored CLI Output** — Clean, color-coded terminal output

---

## 📸 Preview

The Discord embed looks like this:

```
┌─────────────────────────────────────┐
│  📦 Directory Zip Upload            │
│                                     │
│  📁 Directory: C:\my\folder         │
│  🗜️ Archive Size: 12.5 MB (2 parts) │
│  🖥️ Hostname: MY-PC                 │
│  💻 OS: Windows 10                  │
│  🧠 CPU: Intel i7-12700K           │
│  🎮 GPU: RTX 3080 — 10240 MB VRAM  │
│  💾 RAM: 12.3 GB / 32.0 GB (38%)   │
│  📀 Disk: 420 GB / 1 TB (42%)      │
│  🌐 Public IP: ||hidden||          │
│  🏠 Local IP: 192.168.1.100        │
└─────────────────────────────────────┘
```

---

## 🚀 Getting Started

### Prerequisites

- Python **3.8+**
- A [Discord Webhook URL](https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks)

### Installation

```bash
# Clone the repo
git clone https://github.com/yourusername/discord-webhook-sender.git
cd discord-webhook-sender

# (Recommended) Create a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/macOS

# Install dependencies
pip install -r requirements.txt
```

### Usage

```bash
python sender.py
```

You will be prompted to:

1. **Enter your Discord Webhook URL** (or it loads from `config.json` if saved previously)
2. **Enter the full path** of the directory you want to zip & send

The tool will then:
- Zip the directory
- Split into parts if > 8 MB
- Gather your system info
- Send a rich embed + file(s) to your Discord channel

---

## 📁 Project Structure

```
discord-webhook-sender/
├── sender.py           # Main script
├── config.json         # Auto-generated webhook config (gitignored)
├── requirements.txt    # Python dependencies
├── .gitignore
└── README.md
```

---

## 📦 Dependencies

| Package | Purpose |
|---------|---------|
| `requests` | HTTP requests to Discord API |
| `psutil` | CPU, RAM, disk metrics |
| `GPUtil` | GPU information |
| `py-cpuinfo` | Detailed CPU model info |
| `colorama` | Colored terminal output |

---

## ⚠️ Notes

- Discord's free-tier file upload limit is **8 MB**. Files larger than this are automatically split into parts.
- To reassemble split parts, concatenate them in order:
  - **Windows:** `copy /b archive.zip.part001 + archive.zip.part002 archive.zip`
  - **Linux/macOS:** `cat archive.zip.part* > archive.zip`
- The `config.json` file is gitignored by default to protect your webhook URL.
- GPU detection requires NVIDIA drivers; AMD/Intel GPUs may show as N/A.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
