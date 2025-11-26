# Striive Job Monitor

A Python script that monitors Striive job listings and sends email notifications for new engineer/data jobs.

## Features

- Monitors Striive job listings every day at 15:00 UTC via GitHub Actions
- Filters jobs containing "engineer" or "data" in the title
- Sends email notifications via Postmark API
- Tracks seen job IDs to avoid duplicate notifications
- Production-ready with error handling, logging, and retry logic

## Setup

### Local Development

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv env
   source env/bin/activate  # On Windows: env\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy the example environment file and fill in your values:
   ```bash
   cp .env.example .env
   ```
   Then edit `.env` with your actual values:
   ```
   POSTMARK_API_KEY=your_postmark_api_key
   POSTMARK_FROM_EMAIL=your_sender_email@example.com
   EMAIL_TO=your_recipient_email@example.com
   STRIIVE_COOKIE=your_striive_cookie_string
   STRIIVE_INBOX_URL=https://freelancer.striive.com/inbox/all
   ```
5. Run the script:
   ```bash
   python main.py
   ```

### GitHub Actions Setup

1. Go to your repository on GitHub
2. Navigate to Settings → Secrets and variables → Actions
3. Add the following secrets:
   - `POSTMARK_API_KEY`: Your Postmark API key
   - `POSTMARK_FROM_EMAIL`: The email address to send from (must be verified in Postmark)
   - `EMAIL_TO`: The email address to receive notifications
   - `STRIIVE_COOKIE`: Your Striive session cookie (get this from your browser's developer tools)
   - `STRIIVE_INBOX_URL`: (Optional) The Striive inbox URL, defaults to `https://freelancer.striive.com/inbox/all`
4. The workflow will automatically run once per day at 15:00 UTC


## How It Works

1. Fetches job listings from the Striive API
2. Filters jobs containing "engineer" or "data" in the title
3. Compares against previously seen job IDs
4. Sends email notifications for new jobs via Postmark
5. Saves seen job IDs to persist state between runs

## Logging

The script logs all activities with timestamps:
- INFO: Normal operations (fetching jobs, sending emails, etc.)
- WARNING: Non-critical issues (missing job IDs, file errors)
- ERROR: Critical failures (API errors, email failures)

## Error Handling

- Automatic retry logic for API requests (3 attempts with 5-second delays)
- Graceful handling of missing or invalid JSON responses
- Continues processing even if individual email sends fail
- Proper error logging for debugging


