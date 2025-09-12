from flask import Flask, request, jsonify # type: ignore
import os
import logging
import requests # type: ignore
import threading
import time
import re

app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
BOT_PASSWORD = os.environ.get('BOT_PASSWORD')

# Diccionarios para almacenar estado de usuarios
verified_chats = {}
started_chats = {}
# Diccionario para almacenar temporizadores activos
active_timers = {}

def send_telegram_message(chat_id, text, delete_after=None):
    """Envía un mensaje a través de la API de Telegram"""
    send_message_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text
    }
    
    try:
        response = requests.post(send_message_url, json=payload)
        if response.status_code == 200:
            message_id = response.json()['result']['message_id']
            logger.debug(f"Mensaje enviado: {response.status_code}, Message ID: {message_id}")
            
            # Programar eliminación si se especifica
            if delete_after is not None:
                delete_message_after_delay(chat_id, message_id, delete_after)
            
            return message_id
        else:
            logger.error(f"Error enviando mensaje: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error enviando mensaje: {e}")
        return None

def delete_message_after_delay(chat_id, message_id, delay=2):
    """Elimina un mensaje después de un delay especificado"""
    def delete_message():
        time.sleep(delay)
        delete_message_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
        payload = {
            'chat_id': chat_id,
            'message_id': message_id
        }
        try:
            response = requests.post(delete_message_url, json=payload)
            if response.status_code == 200:
                logger.debug(f"Mensaje {message_id} eliminado exitosamente")
            else:
                logger.warning(f"No se pudo eliminar mensaje {message_id}: {response.status_code}")
        except Exception as e:
            logger.error(f"Error eliminando mensaje {message_id}: {e}")
    
    # Ejecutar en un hilo separado para no bloquear
    thread = threading.Thread(target=delete_message)
    thread.daemon = True
    thread.start()

def should_delete_user_message(chat_id, text):
    """Determina si un mensaje del usuario debe eliminarse"""
    # No eliminar mensajes de usuarios verificados
    if chat_id in verified_chats:
        return False
    
    # Eliminar solo mensajes relacionados con verificación (contraseñas)
    # No eliminar el comando /start
    return text != '/start' and text != ''

def start_timer(chat_id, minutes):
    """Inicia un temporizador que enviará una alerta después de X minutos"""
    seconds = minutes * 60
    
    def timer_callback():
        # Esperar el tiempo especificado
        time.sleep(seconds)
        
        # Enviar alerta
        send_telegram_message(chat_id, f"⏰ Alerta: Han pasado {minutes} minuto(s)")
        
        # Eliminar el temporizador del diccionario
        if chat_id in active_timers:
            del active_timers[chat_id]
    
    # Cancelar temporizador anterior si existe
    if chat_id in active_timers:
        active_timers[chat_id].cancel()
    
    # Crear y guardar nuevo temporizador
    timer = threading.Thread(target=timer_callback)
    timer.daemon = True
    active_timers[chat_id] = timer
    timer.start()
    
    return timer

@app.route('/', methods=['POST'])
def webhook():
    try:
        logger.debug("=== INICIO DE WEBHOOK ===")
        data = request.get_json()
        logger.debug(f"Datos recibidos: {data}")
        
        if data and 'message' in data:
            message = data['message']
            chat_id = message['chat']['id']
            message_id = message['message_id']
            text = message.get('text', '')
            
            logger.debug(f"Chat ID: {chat_id}, Message ID: {message_id}, Text: {text}")
            
            # Eliminar mensaje del usuario solo si es relacionado con verificación
            if should_delete_user_message(chat_id, text):
                delete_message_after_delay(chat_id, message_id, 2)
            
            # Manejar comando /start
            if text == '/start':
                handle_start_command(chat_id)
            # Manejar otros mensajes
            else:
                handle_message(chat_id, text)
        
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        logger.error(f"ERROR: {e}", exc_info=True)
        return jsonify({'status': 'error'}), 200

def handle_start_command(chat_id):
    """Maneja el comando /start"""
    if chat_id not in started_chats:
        # Primera vez que usa /start - Mensaje de bienvenida permanente
        started_chats[chat_id] = True
        send_telegram_message(chat_id, "Bienvenido.")  # Este NO se elimina
        # Mensaje de solicitud de contraseña que SÍ se eliminará después
        send_telegram_message(chat_id, "Por favor, ingresa la contraseña para continuar:", delete_after=2)
        logger.debug(f"Nuevo chat {chat_id} iniciado, pidiendo contraseña")
    elif chat_id in verified_chats:
        # Ya está verificado - NO ELIMINAR este mensaje
        send_telegram_message(chat_id, "Ya estas verificado. Puedes usar el bot normalmente.")
        logger.debug(f"Chat {chat_id} ya verificado, informando")
    else:
        # Ya inició pero no verificado - ELIMINAR después de 2 segundos
        send_telegram_message(chat_id, "Por favor, ingresa la contraseña para continuar:", delete_after=2)
        logger.debug(f"Chat {chat_id} no verificado, pidiendo contraseña nuevamente")

def handle_message(chat_id, text):
    """Maneja mensajes regulares"""
    if chat_id not in started_chats:
        # Ignorar mensajes si no ha usado /start primero
        logger.debug(f"Ignorando mensaje de chat {chat_id} que no ha iniciado con /start")
        return
    
    if chat_id not in verified_chats:
        # Verificar contraseña - ELIMINAR estos mensajes después de 2 segundos
        if text == BOT_PASSWORD:
            verified_chats[chat_id] = True
            send_telegram_message(chat_id, "Contraseña correcta. Ahora puedes usar el bot.", delete_after=2)
            logger.debug(f"Chat {chat_id} verificado correctamente")
        else:
            send_telegram_message(chat_id, "Contraseña incorrecta. Intenta de nuevo.", delete_after=2)
            logger.debug(f"Intento fallido de contraseña para chat {chat_id}")
    else:
        # Si está verificado, procesar el mensaje normalmente
        process_verified_message(chat_id, text)

def process_verified_message(chat_id, text):
    """Procesa mensajes de chats verificados - SIN ELIMINAR"""
    if text.startswith('/'):
        if text == '/help':
            send_telegram_message(chat_id, "Comandos disponibles:\n/start - Iniciar bot\n/help - Mostrar ayuda\n/status - Ver estado de verificacion\n/minutos X - Alerta en X minutos")
        elif text == '/status':
            send_telegram_message(chat_id, "Tu chat esta verificado correctamente.")
        elif text.startswith('/minutos'):
            handle_minutos_command(chat_id, text)
        else:
            send_telegram_message(chat_id, "Comando no reconocido. Usa /help para ver opciones.")
    # else:
        # response_text = f"Dijiste: {text}"
        # send_telegram_message(chat_id, response_text) # Repetir el mensaje del usuario

def handle_minutos_command(chat_id, text):
    """Maneja el comando /minutos"""
    # Extraer el número de minutos usando expresión regular
    match = re.search(r'/minutos\s+(\d+)', text)
    
    if match:
        try:
            minutes = int(match.group(1))
            
            # Validar que sea un número razonable
            if minutes <= 0:
                send_telegram_message(chat_id, "El número de minutos debe ser mayor a 0.")
            elif minutes > 1440:  # 24 horas
                send_telegram_message(chat_id, "El número máximo es 1440 minutos (24 horas).")
            else:
                # Iniciar el temporizador
                start_timer(chat_id, minutes)
                send_telegram_message(chat_id, f"⏰ Alerta programada para {minutes} minuto(s). Te avisaré cuando termine el tiempo.")
        
        except ValueError:
            send_telegram_message(chat_id, "Formato incorrecto. Usa: /minutos X (donde X es un número)")
    else:
        send_telegram_message(chat_id, "Formato incorrecto. Usa: /minutos X\nEjemplo: /minutos 5 para 5 minutos")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)