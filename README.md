# 🤖 Hamza's AI Trading Agent

> Smart. Automated. Always Learning.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Last Update](https://img.shields.io/badge/Last%20Update-April%202026-orange.svg)](https://github.com/HamzahShoaib/ai-trading-agent/commits/main)
[![GitHub Pages](https://img.shields.io/badge/GitHub_Pages-Live-brightgreen.svg)](https://hamzashoaib.github.io/ai-trading-agent/)

---

## 📌 Project Overview

**Hamza's AI Trading Agent** is an intelligent, algorithmic trading system that uses machine learning to analyze market data, identify patterns, and execute trades automatically. Built for both beginners and advanced traders, it combines technical analysis with AI-driven decision-making.

---

## ✨ Features

- 📊 **Real-Time Market Analysis** — Fetches live data from major exchanges
- 🧠 **AI-Powered Predictions** — ML models trained on historical price data
- ⚡ **Automated Trading** — Executes buy/sell orders based on signals
- 🔒 **Risk Management** — Built-in stop-loss, position sizing, and drawdown limits
- 📈 **Backtesting Engine** — Test strategies against historical data before going live
- 🌙 **Dark/Light Mode Website** — Clean, responsive pitch site with embedded resources

---

## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/HamzahShoaib/ai-trading-agent.git
cd ai-trading-agent
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Your API Keys
```bash
cp .env.example .env
# Edit .env and add your exchange API keys
```

### 4. Run the Agent
```bash
python src/main.py
```

> ⚠️ **Always run in paper/simulation mode first.** Never deploy real capital without thorough backtesting.

---

## 📁 Project Structure

```
ai-trading-agent/
│
├── src/                  # Core AI Trading Agent Code
│   ├── main.py           # Entry point
│   ├── models/           # ML model definitions
│   ├── strategies/       # Trading strategies
│   └── utils/            # Helper functions
│
├── website/              # Project Website (Hosted on GitHub Pages)
│   ├── index.html        # Landing page
│   ├── css/              # Stylesheets
│   └── js/               # Scripts
│
├── docs/                 # Documentation
│   └── PitchDeck.pdf     # PDF Pitch Deck
│
├── assets/               # Images, logos, diagrams
│
├── requirements.txt      # Python dependencies
├── .env.example          # Environment variable template
├── .gitignore            # Ignored files
└── README.md             # This file
```

---

## 🚀 GitHub Pages Setup

To host the website on GitHub Pages:

1. Go to your repository on GitHub
2. Click **Settings** → **Pages**
3. Under **Build and deployment**:
   - **Source**: Select `Deploy from a branch`
   - **Branch**: Choose `main` (or `master`) and the folder `/website`
   - Click **Save**

Your site will be live at: `https://<username>.github.io/ai-trading-agent/` (may take a minute).

> **Important:** All links must be **relative** (as they are) for GitHub Pages to work correctly.

---

## 🌐 Hosted Website

The project website is hosted on GitHub Pages and includes:
- Project overview and features
- Embedded YouTube pitch walkthrough video
- Downloadable PDF pitch deck
- Contact information

🔗 **Live Site:** https://hamzashoaib.github.io/ai-trading-agent/

---

## 🎥 Pitch Resources

| Resource | Link |
|----------|------|
| 📄 PDF Pitch Deck | [Download Here](docs/PitchDeck.pdf) |
| ▶️ YouTube Walkthrough | [Watch on YouTube](https://youtube.com/watch?v=YOUR_VIDEO_ID) |

> To update the YouTube video or PDF, replace the links in `website/index.html`.

---

## 🔐 Security Notes

- 🔒 **Never commit real API keys** — use `.env` files and keep them out of version control
- 🧪 **Test in sandbox/paper mode** before connecting to live exchanges
- 📦 **Use virtual environments** to isolate dependencies
- 🛡️ **Review all automated trading logic** before deploying real funds

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

Made with ❤️ by **Hamza Shoaib**
