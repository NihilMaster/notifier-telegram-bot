
# Notifier

A Telegram bot to notify users about scheduled messages.

## Technical Specification

![Static Badge](https://img.shields.io/badge/Google_Cloud_Platform-Run-4182ed?logo=google-cloud&logoColor=white) ![Static Badge](https://img.shields.io/badge/Google_Cloud_Platform-Firestore-FFCA28?logo=google-cloud&logoColor=white) ![Static Badge](https://img.shields.io/badge/Python-3.13--slim-f2d343?logo=python&logoColor=ffffff) ![python-telegram-bot Badge](https://img.shields.io/badge/Python-python--telegram--bot-2CA5E0?logo=telegram&logoColor=ffffff) ![Static Badge](https://img.shields.io/badge/Flask-2.3.3-000000?logo=flask&logoColor=000000) ![Gunicorn Badge](https://img.shields.io/badge/Gunicorn-23.0.0-499848?logo=gunicorn&logoColor=ffffff) ![Requests Badge](https://img.shields.io/badge/requests-2.32.4-1565C0?logo=zap&logoColor=white)

## Flow

### Chat - User Interaction

```text
User: /start
Bot: Please provide the password to continue.
User: ****
Bot: Password correct! You now have access.
User: Recordar en [#-unit]: [message].
Bot: Ok, te recordaré en [#-unit].
```

### Background

1. The bot is activated with "/start"
2. Log-in of the user is checked.
   1. If the user is verified, pass.
   2. If the user isn't verified, a password is asked.
      1. The password provided by the user is checked.
3. Check scheduled reminders in DB.
   1. If there are some reminders in DB, check the scheduled messages.
4. The user requests a reminder to be stored with a specific format.
5. The bot stores the request in index from Firestore and the message is scheduled.

```mermaid
graph LR
A[Telegram User] --> B[Telegram Servers]
B --> C[Cloud Run Endpoint]
C --> D[Firestore Database]
E[Background Worker] --> D
D --> F[Reminder Delivery]
F --> A
```

### Features

1. Host the bot-service on Google Cloud Run
2. Schedule messages using Firestore and polling
3. Password authentication system
4. Interactive menu of commands
5. Verified accounts storage
6. Implement reminder management (list, delete)

### TODO

-[ ] #1 Migrate to Google Cloud Scheduler+Functions+Firestore

-[ ] #2 Support for different time units (hours, days)

-[ ] #3 Support for different time zones

-[ ] #4 Support for different languages

### Commands

```text
/start
/help
/listar
/eliminar
/status
```

---

## Documentation

### Google Cloud Platform Deployment

1. Create a GCP project with a billing account and the following APIs enabled:
    1. [Cloud Run API](https://console.cloud.google.com/apis/library/run.googleapis.com)
    2. [Cloud Firestore API](https://console.cloud.google.com/apis/library/firestore.googleapis.com)
2. Create a Cloud Firestore database in Native Mode.
3. Create the required composite index for Firestore:
   - Collection: `reminders`
   - Fields: `status` (Ascending), `trigger_time` (Ascending)
   - Or use the automatic link from error [logs](https://console.cloud.google.com/logs/query;storageScope=project)
4. Grant permissions to the service account of the Cloud Run service:
   - Role: `roles/firestore.user`.
   - Service account name: `[PROJECT-NUMBER]-compute@developer.gserviceaccount.com`.
5. Deploy the bot to Cloud Run:

   ```powershell
   # Deploy
   gcloud run deploy telegram-bot `
    --source . `
    --platform managed `
    --region us-central1 `
    --allow-unauthenticated `
    --memory 1Gi `
    --cpu 1 `
    --port 8080 `
    --set-env-vars=BOT_TOKEN=<your-bot-token> `
    --set-env-vars=BOT_PASSWORD=<random-password> `
    --max-instances=1 `
    --timeout=60s

   # Verify
   ## Test Cloud Run endpoint
   curl -X POST (gcloud run services describe telegram-bot --region us-central1 --format="value(status.url)") -H "Content-Type: application/json" -d '{"test": "health"}'

   ## Variables
   gcloud run services describe telegram-bot `
    --region us-central1 `
    --format="yaml(spec.template.spec.containers[0].env)"
   ```

    Otherwise, you can check the [logs](https://console.cloud.google.com/logs/query;storageScope=project) for verify the deployment.

### Firestore Database Structure

**Collection**: `reminders`

**Document fields**:

- `chat_id` (string): Telegram chat ID
- `minutes` (number): Minutes until reminder
- `message` (string): Reminder message content  
- `trigger_time` (number): Unix timestamp for reminder
- `created_time` (number): Unix timestamp of creation
- `status` (string): 'pending' or 'completed'
- `completed_time` (number): Unix timestamp of completion (optional)

**Collection**: `verified_users`

**Document fields**:

- `chat_id` (string): Telegram chat ID
- `last_activity` (number): Unix timestamp of last activity
- `verification_date` (number): Unix timestamp of verification

**Required Index**:

- Composite index on: `status` (ASC), `trigger_time` (ASC)
