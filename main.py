import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

# Cargar variables desde el archivo .env
load_dotenv()

# Obtener las variables de entorno
TOKEN = os.getenv('TELEGRAM_TOKEN')
PASSWORD = os.getenv('BOT_PASSWORD')

# Diccionario para almacenar los usuarios autorizados
authorized_users = {}

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
    chat_id = update.effective_chat.id
    message_id = update.message.message_id

    # Eliminar el mensaje del usuario
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        print(f"Error deleting message: {e}")

    # Verificar la contraseña
    if user_input == PASSWORD:
        authorized_users[user_id] = True
        await update.message.reply_text("Password correct! You now have access.")
        await update.message.reply_text("List of users authorized: " + str(authorized_users))
    else:
        await update.message.reply_text("Incorrect password. Please try again.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()

    # Añadir manejadores
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_password))

    print("Bot is running...")
    app.run_polling()
    print("Bot stopped.")
