import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Cargar variables desde el archivo .env
load_dotenv()

# Obtener las variables de entorno
TOKEN = os.getenv('TELEGRAM_TOKEN')
PASSWORD = os.getenv('BOT_PASSWORD')

# Diccionario para almacenar los usuarios autorizados
authorized_users = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id in authorized_users:
        await update.message.reply_text(f"Welcome back, {update.effective_user.first_name}!")
    else:
        await update.message.reply_text("Please provide the password to continue.")
        # Guardar el estado de la conversación para que el bot sepa que espera la contraseña
        context.user_data['awaiting_password'] = True

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Verificar si el bot está esperando la contraseña
    if context.user_data.get('awaiting_password'):
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
            context.user_data['awaiting_password'] = False  # Restablecer el estado
        else:
            await update.message.reply_text("Incorrect password. Please try again.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()

    # Añadir manejadores
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running...")
    app.run_polling()
    print("Bot stopped.")
