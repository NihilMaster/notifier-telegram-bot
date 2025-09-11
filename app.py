from flask import Flask, request, jsonify
import os
import logging
import requests

app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG)  # DEBUG para ver TODO
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')

@app.route('/', methods=['POST'])
def webhook():
    try:
        logger.debug("=== INICIO DE WEBHOOK ===")
        data = request.get_json()
        logger.debug(f"Datos recibidos: {data}")
        
        if data and 'message' in data:
            message = data['message']
            chat_id = message['chat']['id']
            text = message.get('text', '')
            
            logger.debug(f"Chat ID: {chat_id}, Text: {text}")
            
            # SOLO LOGUEAR POR AHORA
            logger.debug("Solo logueando, no enviando respuesta aún")
        
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        logger.error(f"ERROR: {e}", exc_info=True)
        return jsonify({'status': 'error'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)