from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import random

# Inicialización de Flask y CORS
app = Flask(__name__)

# Permitir peticiones desde cualquier origen (necesario para el frontend)
CORS(app)

# Diccionario para almacenar el estado del balance de los usuarios.
# Usamos un ID de usuario fijo ('user123') para simular un estado persistente
# en esta aplicación de demostración.
USER_ID = 'user123'
user_data = {
    USER_ID: {
        'balance': 100.00
    }
}

# ----------------------------------------------------
# 1. RUTA PARA OBTENER EL BALANCE (GET /balance)
# ----------------------------------------------------
@app.route('/balance', methods=['GET'])
def get_balance():
    """Devuelve el balance actual del usuario."""
    current_balance = user_data[USER_ID]['balance']
    return jsonify({
        "status": "success",
        "balance": current_balance
    })

# ----------------------------------------------------
# 2. RUTA PARA REINICIAR EL BALANCE (POST /reset)
# ----------------------------------------------------
@app.route('/reset', methods=['POST'])
def reset_balance():
    """Reinicia el balance del usuario a 100.00."""
    user_data[USER_ID]['balance'] = 100.00
    return jsonify({
        "status": "success",
        "new_balance": user_data[USER_ID]['balance'],
        "message": "¡Balance reiniciado a $100.00! Que corran los dados."
    })

# ----------------------------------------------------
# 3. RUTA PARA REALIZAR LA APUESTA (POST /bet)
# ----------------------------------------------------
@app.route('/bet', methods=['POST'])
def handle_bet():
    """Procesa una apuesta, tira los dados y actualiza el balance."""
    try:
        data = request.get_json()
        amount = float(data.get('amount', 0))
    except Exception:
        return jsonify({"status": "error", "error": "Monto de apuesta inválido."}), 400

    current_balance = user_data[USER_ID]['balance']

    if amount <= 0 or amount > current_balance:
        return jsonify({"status": "error", "error": "Apuesta inválida o saldo insuficiente."}), 400

    # Lógica del juego de dados: Gana si la suma es 7 u 11
    dice1 = random.randint(1, 6)
    dice2 = random.randint(1, 6)
    sum_dice = dice1 + dice2
    
    is_winner = sum_dice == 7 or sum_dice == 11
    
    if is_winner:
        profit = amount  # Ganancia igual a la apuesta (paga 1:1)
        new_balance = current_balance + profit
        result = "WIN"
    else:
        profit = -amount # Pérdida igual a la apuesta
        new_balance = current_balance + profit
        result = "LOSS"

    # Actualizar el balance
    user_data[USER_ID]['balance'] = new_balance

    return jsonify({
        "status": "success",
        "new_balance": new_balance,
        "dice1": dice1,
        "dice2": dice2,
        "sum": sum_dice,
        "result": result,
        "profit": profit
    })

# ----------------------------------------------------
# RUTAS DE DIAGNÓSTICO
# ----------------------------------------------------
@app.route('/', methods=['GET'])
def home():
    app_name = "Servicio de Casa de Apuestas"
    message = "¡Bienvenido/a al " + app_name + "! La aplicación está corriendo correctamente en Cloud Run."
    response = {
        "status": "success",
        "service": app_name,
        "message": message,
        "routes": ["/balance", "/reset", "/bet"]
    }
    return jsonify(response)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "OK"})

# ----------------------------------------------------
# INICIO DE LA APLICACIÓN (PARA CLOUD RUN)
# ----------------------------------------------------
if __name__ == "__main__":
    # Cloud Run provee el puerto como una variable de entorno
    port = int(os.environ.get("PORT", 8080))
    app.run(debug=False, host='0.0.0.0', port=port)