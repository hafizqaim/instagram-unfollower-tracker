# Instagram Unfollower Tracker 🔍

A clean, dark-mode desktop app that analyzes your Instagram data export to reveal:

- 👻 **Not Following Back** — accounts you follow that don't follow you
- ❤️ **Your Fans** — accounts that follow you but you don't follow back
- 🤝 **Mutual Follows** — accounts you both follow each other
- 📋 All Following / All Followers lists with search and copy

No third-party APIs. No scraping. No ToS violations. Just your own data. ✅

---

## Screenshots

<img width="1920" height="1020" alt="image" src="https://github.com/user-attachments/assets/a1efd522-66fc-47ec-82c6-92bdddae5503" />

---

## Setup

```bash
git clone https://github.com/hafizqaim/instagram-unfollower-tracker
cd instagram-unfollower-tracker
pip install -r requirements.txt
python app.py
```

**Python 3.9+** required.

---

## How to Get Your Instagram Data

1. Open Instagram → **Settings** → **Your Activity**
2. Tap **Download Your Information**
3. Select **JSON** format (not HTML)
4. Request the download — Instagram emails you a link within 24–48 hours
5. Download the ZIP

Inside the ZIP, you'll find:
```
connections/
  followers_and_following/
    followers_1.json
    following.json
```

---

## Usage

**Option A — Load ZIP directly:**
Click **"📦 Load ZIP Export"** and select the downloaded `.zip` file.

**Option B — Load individual files:**
1. Click 📂 next to *Followers File* → select `followers_1.json`
2. Click 📂 next to *Following File* → select `following.json`

Then click **Analyze →** and explore the results!

---

## Features

- 🎨 Dark mode UI built with `ttkbootstrap`
- 🔍 Real-time username search/filter
- ⧉ One-click copy usernames to clipboard
- 💾 Export results as `.txt` or `.json`
- 📦 Supports both ZIP and individual JSON file import
- ⚡ Fast — works entirely offline, no API calls

---

## Tech Stack

- Python 3.9+
- [ttkbootstrap](https://ttkbootstrap.readthedocs.io/) for the UI
- Standard library only beyond that (`json`, `tkinter`, `zipfile`, `threading`)

---

## Privacy

Your data **never leaves your machine**. The app reads local files only.

---

## License

MIT
