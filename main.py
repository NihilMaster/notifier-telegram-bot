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

logging.basicConfig(level=logging.INFO)
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

def set_bot_commands():
    """Configura los comandos del bot en la barra de input"""
    set_commands_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setMyCommands"
    commands = [
        {"command": "start", "description": "Iniciar bot"},
        {"command": "help", "description": "Mostrar ayuda"},
        {"command": "status", "description": "Ver estado de verificación"},
        {"command": "listar", "description": "Listar recordatorios"},
        {"command": "eliminar", "description": "Eliminar recordatorio"}
    ]
    
    payload = {"commands": commands}
    
    try:
        response = requests.post(set_commands_url, json=payload)
        if response.status_code == 200:
            logger.info("✅ Comandos del bot configurados correctamente")
        else:
            logger.error(f"Error configurando comandos: {response.status_code}")
    except Exception as e:
        logger.error(f"Error configurando comandos: {e}")

@app.before_request
def startup():
    """Inicia el worker de recordatorios y configura comandos cuando la app arranca"""
    if not hasattr(app, 'startup_complete'):
        reminder_system.start_worker()
        set_bot_commands()
        app.startup_complete = True

@app.route('/', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        
        if data and 'message' in data:
            message = data['message']
            chat_id = message['chat']['id']
            message_id = message['message_id']
            text = message.get('text', '')
            
            if should_delete_user_message(chat_id, text):
                delete_message_after_delay(chat_id, message_id, 2)
            
            if text == '/start':
                handle_start_command(chat_id)
            else:
                handle_message(chat_id, text)
        
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        logger.error(f"ERROR: {e}")
        return jsonify({'status': 'error'}), 200

def handle_start_command(chat_id):
    """Maneja el comando /start"""
    if chat_id not in started_chats:
        started_chats[chat_id] = True
        send_telegram_message(chat_id, "Bienvenido.")
        send_telegram_message(chat_id, "Por favor, ingresa la contraseña para continuar:", delete_after=2)
    elif chat_id in verified_chats:
        send_telegram_message(chat_id, "Ya estas verificado. Puedes usar el bot normalmente.")
    else:
        send_telegram_message(chat_id, "Por favor, ingresa la contraseña para continuar:", delete_after=2)

def handle_message(chat_id, text):
    """Maneja mensajes regulares"""
    if chat_id not in started_chats:
        return
    
    if chat_id not in verified_chats:
        if text == BOT_PASSWORD:
            verified_chats[chat_id] = True
            send_telegram_message(chat_id, "Contraseña correcta. Ahora puedes usar el bot.", delete_after=2)
        else:
            send_telegram_message(chat_id, "Contraseña incorrecta. Intenta de nuevo.", delete_after=2)
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
            help_text = """🤖 *Comandos disponibles:*

/start - Iniciar bot
/help - Mostrar ayuda
/status - Ver estado de verificación
/listar - Listar recordatorios activos
/eliminar - Eliminar un recordatorio

📝 *Para crear recordatorios:*
Usa el formato: 
`Recordar en X minutos: Tu mensaje`

*Ejemplo:*
`Recordar en 30 minutos: Llamar al doctor`
`Recordar en 5 minutos: Reunión con el equipo`"""
            send_telegram_message(chat_id, help_text)
        elif text == '/status':
            send_telegram_message(chat_id, "✅ Tu chat está verificado correctamente.")
        elif text == '/listar':
            send_telegram_message(chat_id, "📋 Funcionalidad de listar recordatorios en desarrollo.")
        elif text == '/eliminar':
            send_telegram_message(chat_id, "🗑️ Funcionalidad de eliminar recordatorios en desarrollo.")
        else:
            send_telegram_message(chat_id, "❌ Comando no reconocido. Usa /help para ver opciones.")
    else:
        # Mostrar formato correcto en lugar de "Dijiste:"
        format_example = """📝 *Formato incorrecto*

Usa el formato:
`Recordar en X minutos: Tu mensaje`

*Ejemplos:*
`Recordar en 5 minutos: Reunión con el equipo`
`Recordar en 30 minutos: Llamar al doctor`
`Recordar en 60 minutos: Tomar medicamento`"""
        send_telegram_message(chat_id, format_example)

def handle_reminder_command(chat_id, minutes, message):
    """Maneja la creación de recordatorios"""
    if minutes <= 0:
        send_telegram_message(chat_id, "❌ El número de minutos debe ser mayor a 0.")
        return
    
    if minutes > 10080:  # 7 días
        send_telegram_message(chat_id, "❌ El máximo es 10080 minutos (7 días).")
        return
    
    if not message or len(message.strip()) == 0:
        send_telegram_message(chat_id, "❌ El mensaje del recordatorio no puede estar vacío.")
        return
    
    # Crear el recordatorio
    reminder_id = create_reminder(chat_id, minutes, message)
    
    if reminder_id:
        send_telegram_message(chat_id, f"📝 Ok, te recordaré en {minutes} minutos.")
    else:
        send_telegram_message(chat_id, "❌ Error al crear el recordatorio. Intenta nuevamente.")

if __name__ == '__main__':
    # Iniciar worker de recordatorios y configurar comandos
    reminder_system.start_worker()
    set_bot_commands()
    app.run(host='0.0.0.0', port=8080, debug=False)