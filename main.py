import os
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from flask import Flask, request

# Cargar variables desde el archivo .env
load_dotenv()

# Obtener las variables de entorno
TOKEN = os.getenv('TELEGRAM_TOKEN')
PASSWORD = os.getenv('BOT_PASSWORD')

# Crear aplicación Flask
app = Flask(__name__)

# Diccionario para almacenar los usuarios autorizados
authorized_users = {}

# Crear el scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# Crear aplicación de Telegram
application = ApplicationBuilder().token(TOKEN).build()

# Función para enviar notificaciones
async def send_notification(bot, user_id, message):
    try:
        await bot.send_message(chat_id=user_id, text=message)
    except Exception as e:
        print(f"Error sending message: {e}")

def schedule_reminder(user_id, message):
    asyncio.run(send_notification(application.bot, user_id, message))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id in authorized_users:
        await update.message.reply_text(f"Welcome back, {update.effective_user.first_name}!")
        context.user_data['awaiting_password'] = False
    else:
        await update.message.reply_text("Please provide the password to continue.")
        context.user_data['awaiting_password'] = True
    
    context.user_data['receive_reminder'] = True

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if context.user_data.get('awaiting_password'):
        user_input = update.message.text

        if user_input == PASSWORD:
            authorized_users[user_id] = True
            await update.message.reply_text("Password correct! You now have access.")
            context.user_data['awaiting_password'] = False
        else:
            await update.message.reply_text("Incorrect password. Please try again.")

    elif context.user_data.get('receive_reminder'):
        message_text = update.message.text
        
        parts = message_text.split(":")
        if len(parts) != 2:
            await update.message.reply_text("Formato incorrecto. Usa: Recordar en X minutos: Mensaje")
            return

        time_part = parts[0].strip().split()
        reminder_message = parts[1].strip()

        if len(time_part) < 4:
            await update.message.reply_text("Formato incorrecto. Usa: Recordar en X minutos: Mensaje")
            return

        try:
            delay = int(time_part[2])
        except ValueError:
            await update.message.reply_text("El tiempo debe ser un número entero de minutos.")
            return

        run_time = datetime.now() + timedelta(minutes=delay)
        scheduler.add_job(schedule_reminder, 'date', run_date=run_time, 
                         args=[user_id, reminder_message])
        await update.message.reply_text(f"Ok, te recordaré en {delay} minutos.")

# Añadir manejadores
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Webhook para Cloud Run
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        # Procesar la actualización
        update = Update.de_json(request.get_json(), application.bot)
        application.process_update(update)
        return 'OK', 200
    except Exception as e:
        print(f"Error processing update: {e}")
        return 'Error', 500

@app.route('/health', methods=['GET'])
def health_check():
    return 'OK', 200

@app.route('/')
def home():
    return 'Telegram Bot is running!'

# Cambia temporalmente el final del main.py a esto:
if __name__ == '__main__':
    print("Bot is starting with polling...")
    application.run_polling()