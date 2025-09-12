from flask import Flask, request, jsonify # type: ignore
import os
import logging
import requests # type: ignore
import threading
import time
import re
from google.cloud import firestore
import schedule # type: ignore

app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
BOT_PASSWORD = os.environ.get('BOT_PASSWORD')

# Inicializar Firestore
db = firestore.Client()

# Diccionarios para almacenar estado de usuarios
verified_chats = {}
started_chats = {}

class ReminderSystem:
    def __init__(self):
        self.running = True
    
    def check_pending_reminders(self):
        """Verifica recordatorios pendientes en Firestore"""
        try:
            now = time.time()
            logger.debug("🔍 Buscando recordatorios pendientes...")
            
            # Buscar recordatorios cuyo trigger_time sea <= ahora y estén pendientes
            reminders_ref = db.collection('reminders')
            query = reminders_ref.where('status', '==', 'pending').where('trigger_time', '<=', now)
            reminders = query.stream()
            
            for reminder in reminders:
                reminder_data = reminder.to_dict()
                self.process_reminder(reminder.id, reminder_data)
                
        except Exception as e:
            logger.error(f"Error checking reminders: {e}")
    
    def process_reminder(self, reminder_id, reminder_data):
        """Procesa un recordatorio pendiente"""
        try:
            chat_id = reminder_data['chat_id']
            message = reminder_data['message']
            
            # Enviar el recordatorio
            send_telegram_message(chat_id, f"🔔 Recordatorio: {message}")
            
            # Marcar como completado en Firestore
            db.collection('reminders').document(reminder_id).update({
                'status': 'completed',
                'completed_time': time.time()
            })
            
            logger.debug(f"Recordatorio {reminder_id} enviado a chat {chat_id}")
            
        except Exception as e:
            logger.error(f"Error processing reminder {reminder_id}: {e}")
    
    def start_worker(self):
        """Inicia el worker que verifica recordatorios cada 30 segundos"""
        def worker_loop():
            while self.running:
                try:
                    self.check_pending_reminders()
                except Exception as e:
                    logger.error(f"Error en worker loop: {e}")
                time.sleep(30)  # Verificar cada 30 segundos
        
        thread = threading.Thread(target=worker_loop)
        thread.daemon = True
        thread.start()
        logger.debug("✅ Worker de recordatorios iniciado")
    
    def stop_worker(self):
        self.running = False

# Inicializar el sistema de recordatorios
reminder_system = ReminderSystem()

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
    
    thread = threading.Thread(target=delete_message)
    thread.daemon = True
    thread.start()

def should_delete_user_message(chat_id, text):
    """Determina si un mensaje del usuario debe eliminarse"""
    if chat_id in verified_chats:
        return False
    return text != '/start' and text != ''

def parse_reminder_message(text):
    """Parsea el mensaje en formato 'Recordar en X minutos: Mensaje'"""
    pattern = r'^Recordar en (\d+) minutos: (.+)$'
    match = re.match(pattern, text.strip())
    
    if match:
        minutes = int(match.group(1))
        message = match.group(2).strip()
        return minutes, message
    return None, None

def create_reminder(chat_id, minutes, message):
    """Crea un nuevo recordatorio en Firestore"""
    try:
        trigger_time = time.time() + (minutes * 60)
        
        reminder_data = {
            'chat_id': chat_id,
            'minutes': minutes,
            'message': message,
            'trigger_time': trigger_time,
            'created_time': time.time(),
            'status': 'pending'
        }
        
        # Guardar en Firestore
        doc_ref = db.collection('reminders').document()
        doc_ref.set(reminder_data)
        
        return doc_ref.id
    except Exception as e:
        logger.error(f"Error creating reminder: {e}")
        return None

@app.before_request
def startup():
    """Inicia el worker de recordatorios cuando la app arranca"""
    if not hasattr(app, 'startup_complete'):
        reminder_system.start_worker()
        app.startup_complete = True

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
            
            if should_delete_user_message(chat_id, text):
                delete_message_after_delay(chat_id, message_id, 2)
            
            if text == '/start':
                handle_start_command(chat_id)
            else:
                handle_message(chat_id, text)
        
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        logger.error(f"ERROR: {e}", exc_info=True)
        return jsonify({'status': 'error'}), 200

def handle_start_command(chat_id):
    """Maneja el comando /start"""
    if chat_id not in started_chats:
        started_chats[chat_id] = True
        send_telegram_message(chat_id, "Bienvenido.")
        send_telegram_message(chat_id, "Por favor, ingresa la contraseña para continuar:", delete_after=2)
        logger.debug(f"Nuevo chat {chat_id} iniciado, pidiendo contraseña")
    elif chat_id in verified_chats:
        send_telegram_message(chat_id, "Ya estas verificado. Puedes usar el bot normalmente.")
        logger.debug(f"Chat {chat_id} ya verificado, informando")
    else:
        send_telegram_message(chat_id, "Por favor, ingresa la contraseña para continuar:", delete_after=2)
        logger.debug(f"Chat {chat_id} no verificado, pidiendo contraseña nuevamente")

def handle_message(chat_id, text):
    """Maneja mensajes regulares"""
    if chat_id not in started_chats:
        logger.debug(f"Ignorando mensaje de chat {chat_id} que no ha iniciado con /start")
        return
    
    if chat_id not in verified_chats:
        if text == BOT_PASSWORD:
            verified_chats[chat_id] = True
            send_telegram_message(chat_id, "Contraseña correcta. Ahora puedes usar el bot.", delete_after=2)
            logger.debug(f"Chat {chat_id} verificado correctamente")
        else:
            send_telegram_message(chat_id, "Contraseña incorrecta. Intenta de nuevo.", delete_after=2)
            logger.debug(f"Intento fallido de contraseña para chat {chat_id}")
    else:
        process_verified_message(chat_id, text)

def process_verified_message(chat_id, text):
    """Procesa mensajes de chats verificados"""
    # Verificar si es un recordatorio
    minutes, reminder_message = parse_reminder_message(text)
    
    if minutes is not None:
        handle_reminder_command(chat_id, minutes, reminder_message)
    elif text.startswith('/'):
        if text == '/help':
            help_text = """Comandos disponibles:
/start - Iniciar bot
/help - Mostrar ayuda
/status - Ver estado de verificacion

Para crear recordatorios:
"Recordar en X minutos: Tu mensaje"
Ejemplo: "Recordar en 30 minutos: Llamar al doctor"
"""
            send_telegram_message(chat_id, help_text)
        elif text == '/status':
            send_telegram_message(chat_id, "Tu chat esta verificado correctamente.")
        else:
            send_telegram_message(chat_id, "Comando no reconocido. Usa /help para ver opciones.")
    else:
        response_text = f"Dijiste: {text}"
        send_telegram_message(chat_id, response_text)

def handle_reminder_command(chat_id, minutes, message):
    """Maneja la creación de recordatorios"""
    if minutes <= 0:
        send_telegram_message(chat_id, "El número de minutos debe ser mayor a 0.")
        return
    
    if minutes > 10080:  # 7 días
        send_telegram_message(chat_id, "El máximo es 10080 minutos (7 días).")
        return
    
    if not message or len(message.strip()) == 0:
        send_telegram_message(chat_id, "El mensaje del recordatorio no puede estar vacío.")
        return
    
    # Crear el recordatorio
    reminder_id = create_reminder(chat_id, minutes, message)
    
    if reminder_id:
        send_telegram_message(chat_id, f"Ok, te recordaré en {minutes} minutos.")
        logger.debug(f"Recordatorio creado: {reminder_id} para chat {chat_id}")
    else:
        send_telegram_message(chat_id, "Error al crear el recordatorio. Intenta nuevamente.")

if __name__ == '__main__':
    # Iniciar worker de recordatorios
    reminder_system.start_worker()
    app.run(host='0.0.0.0', port=8080, debug=False)