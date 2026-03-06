import os
from flask import Flask
from threading import Thread
from telebot import TeleBot
from mistralai import Mistral

# 1. Setup Flask for Render Health Checks
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is alive!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# 2. Setup Mistral & Telegram
client = Mistral(api_key=os.environ.get("MISTRAL_API_KEY"))
bot = TeleBot(os.environ.get("TELEGRAM_BOT_TOKEN"))
AGENT_ID = "ag_019cc2276c1d7585a32da68d0b63278b"

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        # Send user message to your Mistral Agent
        # Note: In a real app, you'd manage 'inputs' history per user
        chat_response = client.agents.complete(
            agent_id=AGENT_ID,
            messages=[{"role": "user", "content": message.text}]
        )
        
        bot_reply = chat_response.choices[0].message.content
        bot.reply_to(message, bot_reply, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"Error: {str(e)}")

if __name__ == "__main__":
    Thread(target=run_flask).start()
    print("Bot is polling...")
    bot.infinity_polling()