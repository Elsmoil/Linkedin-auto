# Linkedin-auto

Linkedin-auto is a Python automation project for LinkedIn workflows. It combines browser automation with AI-powered text generation to support profile analysis, content drafting, engagement routines, job discovery, and application tracking.

## What this project includes

- Profile analysis from LinkedIn page HTML with AI-generated recommendations
- Content generation for posts, comments, connection messages, headlines, and summaries
- Scheduled automation using cron expressions and timezone support
- Multi-channel notifications (email, Discord, Slack)
- Session and activity tracking with JSON logs
- Job scraping and job application workflow modules

## Repository structure

- `/home/runner/work/Linkedin-auto/Linkedin-auto/main.py` - Main entry point and automation orchestrator
- `/home/runner/work/Linkedin-auto/Linkedin-auto/ai_modules/linkedin_reader.py` - LinkedIn page reading and AI interaction
- `/home/runner/work/Linkedin-auto/Linkedin-auto/content_generator.py` - Content generation logic
- `/home/runner/work/Linkedin-auto/Linkedin-auto/scheduler.py` - Scheduling and automation timing
- `/home/runner/work/Linkedin-auto/Linkedin-auto/notifier.py` - Notification delivery
- `/home/runner/work/Linkedin-auto/Linkedin-auto/linkedin_bot/` - Auth, engagement, profile update, job scraping, and application modules

## Requirements

- Python 3.10+
- A LinkedIn account
- An API key compatible with the configured OpenAI/OpenRouter endpoint
- Playwright browser binaries installed locally

## Installation

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Install Playwright Chromium:

```bash
python -m playwright install chromium
```

## Configuration

Create a `.env` file in the repository root and set the values you need.

### Core credentials

- `OPENROUTER_API_KEY` or `OPENAI_API_KEY`
- `OPENAI_API_BASE_URL` (optional, defaults to `https://openrouter.ai/api/v1`)
- `LINKEDIN_EMAIL` and `LINKEDIN_PASSWORD`, or `LINKEDIN_COOKIE`
- `LINKEDIN_TIMEOUT` (optional, default `30000`)
- `LINKEDIN_HEADLESS` (optional, default `true`)

### Automation and scheduling

- `AUTOMATION_ENABLED`
- `SAFE_MODE`
- `DRY_RUN`
- `MAX_DAILY_ACTIONS`
- `ACTION_DELAY_MIN`
- `ACTION_DELAY_MAX`
- `SCHEDULE_PROFILE_UPDATE`
- `SCHEDULE_ENGAGEMENT`
- `TIMEZONE`

### Notifications

- `NOTIFY_EMAIL_ENABLED`
- `NOTIFY_EMAIL_FROM`
- `NOTIFY_EMAIL_TO`
- `NOTIFY_EMAIL_PASSWORD` or `EMAIL_APP_PASSWORD`
- `SMTP_SERVER`
- `SMTP_PORT`
- `DISCORD_WEBHOOK_URL`
- `SLACK_WEBHOOK_URL`

### Job search and applications

- `JOB_SEARCH_KEYWORDS`
- `JOB_SEARCH_LOCATIONS`
- `JOB_EXPERIENCE_LEVELS`
- `JOB_TYPES`
- `MAX_RESULTS_PER_SEARCH`
- `MAX_DAILY_APPLICATIONS`
- `AUTO_APPLY_ENABLED`
- `CV_PATH`
- `COVER_LETTER_TEMPLATE`
- `APPLY_DELAY_MIN`
- `APPLY_DELAY_MAX`

## Usage

Run from the repository root:

```bash
python main.py
```

Available modes:

```bash
python main.py                # interactive mode (default)
python main.py scheduled      # scheduler loop
python main.py daily          # one daily automation run
python main.py analyze        # profile analysis only
```

You can also run individual modules directly for isolated testing, for example:

```bash
python content_generator.py
python scheduler.py
python notifier.py
```

## Runtime output

The project writes runtime state and history to the `logs/` directory (ignored by git), including:

- Profile analysis outputs
- Generated content files
- Scheduler state
- Session/authentication history
- Engagement and job tracking data

## Notes and caution

- Use `DRY_RUN=true` when validating setup to avoid unintended live actions.
- Keep rate limits conservative to reduce account risk.
- Store credentials only in environment variables or `.env`, never in source files.
