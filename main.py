import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

# Obtener la contraseña desde las variables de entorno
PASSWORD = os.getenv('BOT_PASSWORD')

# Diccionario para almacenar qué usuarios han introducido la contraseña correcta
authorized_users = {}

# Función que se ejecuta cuando el bot recibe el comando /start
async def start(update: Update, context):
    user_id = update.effective_user.id

    if user_id in authorized_users:
        await update.message.reply_text(f"Welcome back, {update.effective_user.first_name}!")
    else:
        await update.message.reply_text("Please provide the password to continue.")

# Función para verificar la contraseña
async def check_password(update: Update, context):
    user_id = update.effective_user.id
    user_input = update.message.text

    if user_input == PASSWORD:
        authorized_users[user_id] = True
        await update.message.reply_text("Password correct! You now have access.")
    else:
        await update.message.reply_text("Incorrect password. Please try again.")

if __name__ == '__main__':
    TOKEN = os.getenv('TELEGRAM_TOKEN')

    app = ApplicationBuilder().token(TOKEN).build()

    # Añadir manejadores para el comando /start y la verificación de contraseña
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_password))

    print("Bot is running...")
    app.run_polling()

