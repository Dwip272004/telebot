import os
import json
import psycopg2
from flask import Flask
from threading import Thread
import telebot
from mistralai import Mistral

# --- DATABASE CONFIGURATION ---
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    # Stores conversation history as a JSON block per user
    cur.execute('''
        CREATE TABLE IF NOT EXISTS user_memory (
            user_id BIGINT PRIMARY KEY,
            history TEXT
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

def load_user_history(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT history FROM user_memory WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return json.loads(row[0]) if row else []

def save_user_history(user_id, history):
    conn = get_db_connection()
    cur = conn.cursor()
    # We keep the last 15 messages for deep natural context
    history_json = json.dumps(history[-15:])
    cur.execute('''
        INSERT INTO user_memory (user_id, history) 
        VALUES (%s, %s)
        ON CONFLICT (user_id) DO UPDATE SET history = EXCLUDED.history
    ''', (user_id, history_json))
    conn.commit()
    cur.close()
    conn.close()

# --- WEB SERVER FOR RENDER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Your personal assistant is online and remembering.", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- BOT SETUP ---
init_db()
MISTRAL_KEY = os.environ.get("MISTRAL_API_KEY")
TELE_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
AGENT_ID = "ag_019cc2276c1d7585a32da68d0b63278b"

client = Mistral(api_key=MISTRAL_KEY)
bot = telebot.TeleBot(TELE_TOKEN)

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    
    # 1. Load context from permanent Postgres DB
    history = load_user_history(user_id)
    
    # 2. Add current message
    history.append({"role": "user", "content": message.text})

    try:
        # 3. Get response from Mistral Agent
        chat_response = client.agents.complete(
            agent_id=AGENT_ID,
            messages=history
        )
        
        bot_reply = chat_response.choices[0].message.content
        
        # 4. Add reply to history and save back to DB
        history.append({"role": "assistant", "content": bot_reply})
        save_user_history(user_id, history)
        
        # 5. Reply to Dwip
        bot.reply_to(message, bot_reply, parse_mode='Markdown')

    except Exception as e:
        print(f"Error: {e}")
        bot.reply_to(message, "I'm having a quick moment to think—could you repeat that?")

if __name__ == "__main__":
    Thread(target=run_flask).start()
    print("🚀 Your human-like assistant is now live with permanent memory!")
    bot.infinity_polling()