
# Notifier

## Flow

### Chat

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
4. Ther user requests storage a reminder with a script formated.
5. The bot stores the request in MySQL.
   1. Columns:
      1. ID
      2. Cant of units
      3. Units
      4. Message
      5. Datetime of request
6. Schedule the message.

## Tasks

- #1 Check if is possible host the bot in Google Cloud Platform.

- #2 Check if is possible to schedule messages as a bot.

- #3 Check if is possible to read scheduled messages.

## Documentation

[Getting Started](https://telegram-bot-sdk.readme.io/docs/getting-started)

### Getting Started

1. Clone the repository.

   ```powershell
   git clone https://github.com/NihilMaster/notifier-telegram-bot.git
   cd telegram-bot-sdk
   ```

2. Create a `.env` file with the following variables:

   ```text
   TELEGRAM_TOKEN=<token>
   BOT_PASSWORD=<password>
   ```

3. Create a virtual environment.
4. Install requirements.
5. Run the bot:

   ```powershell

   # Create virtual environment
   python -m venv venv

   # Activate virtual environment
   .\venv\Scripts\activate

   # Install requirements
   cd venv
   pip install -r ..\requirements.txt

   # Run
   cd ..
   python main.py

   ```
