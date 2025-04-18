# Twitter Sarcastic Bot

Flask & Tweepy powered bot that generates sarcastic Portuguese tweets, publishes them instantly or schedules them.

## Setup

```bash
git clone <repo-url>
cd twitter_bot
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the project root with:

```
API_KEY=...
API_SECRET=...
ACCESS_TOKEN=...
ACCESS_TOKEN_SECRET=...
PORT=5000  # optional
```

## Running locally

```bash
python bot.py
# Visit http://localhost:5000
```

## Deploying

- Use a production WSGI server (eg. Gunicorn) and set `PORT`.
- Make sure environment variables are set in your hosting service.