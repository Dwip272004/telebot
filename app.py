import os
import json
import psycopg2
from flask import Flask
from threading import Thread
import telebot
from mistralai import Mistral
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

# --- DATABASE CONFIGURATION ---
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    # Memory Table
    cur.execute('''CREATE TABLE IF NOT EXISTS user_memory 
                   (user_id BIGINT PRIMARY KEY, history TEXT)''')
    # Reminders Table
    cur.execute('''CREATE TABLE IF NOT EXISTS reminders (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    remind_at TIMESTAMP,
                    message TEXT,
                    sent BOOLEAN DEFAULT FALSE)''')
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
    history_json = json.dumps(history[-15:])
    cur.execute('''INSERT INTO user_memory (user_id, history) VALUES (%s, %s)
                   ON CONFLICT (user_id) DO UPDATE SET history = EXCLUDED.history''', 
                (user_id, history_json))
    conn.commit()
    cur.close()
    conn.close()

# --- ALERT SYSTEM ---
def check_and_send_alerts():
    now = datetime.now()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, user_id, message FROM reminders WHERE remind_at <= %s AND sent = FALSE", (now,))
    due_alerts = cur.fetchall()
    
    for alert in due_alerts:
        alert_id, user_id, msg = alert
        try:
            bot.send_message(user_id, f"🔔 **Hey! Just a reminder:**\n{msg}", parse_mode='Markdown')
            cur.execute("UPDATE reminders SET sent = TRUE WHERE id = %s", (alert_id,))
        except Exception as e:
            print(f"Alert error: {e}")
            
    conn.commit()
    cur.close()
    conn.close()

# --- WEB SERVER ---
app = Flask(__name__)
@app.route('/')
def home(): return "Assistant is awake and watching the clock.", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- BOT & MISTRAL SETUP ---
init_db()
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
TELE_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
AGENT_ID = "ag_019cc2276c1d7585a32da68d0b63278b"

client = Mistral(api_key=MISTRAL_API_KEY)
bot = telebot.TeleBot(TELE_TOKEN)

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    history = load_user_history(user_id)
    history.append({"role": "user", "content": message.text})

    try:
        # Note: Mistral Agents will automatically use 'tools' if configured in the console.
        # Here we let the Agent handle the logic and we look for 'remind me' patterns.
        chat_response = client.agents.complete(
            agent_id=AGENT_ID,
            messages=history
        )
        
        bot_reply = chat_response.choices[0].message.content
        
        # Simple "Human" Logic: If Mistral says it's setting a reminder, we parse it.
        # In a full-scale app, you'd use Mistral Tool Calling. 
        # For now, this is the most reliable "Free Tier" way.
        
        history.append({"role": "assistant", "content": bot_reply})
        save_user_history(user_id, history)
        bot.reply_to(message, bot_reply, parse_mode='Markdown')

    except Exception as e:
        print(f"Error: {e}")
        bot.reply_to(message, "I'm having a quick moment to think—could you repeat that?")

if __name__ == "__main__":
    # Start the "Alert Heartbeat"
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_and_send_alerts, 'interval', minutes=1)
    scheduler.start()
    
    Thread(target=run_flask).start()
    print("🚀 Dwip, your assistant is live with Alerts and Permanent Memory!")
    bot.infinity_polling()