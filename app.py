import os
from flask import Flask
from threading import Thread
import telebot # This comes from the pyTelegramBotAPI package
from mistralai import Mistral

# 1. Setup Flask for Render Health Checks
# Render needs a web server to keep the "Web Service" active.
app = Flask(__name__)

@app.route('/')
def home(): 
    return "Task Manager Bot is live!", 200

def run_flask():
    # Render provides the PORT environment variable automatically
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# 2. Setup Mistral & Telegram
# These variables must be set in the "Environment" tab on Render
MISTRAL_KEY = os.environ.get("MISTRAL_API_KEY")
TELE_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
AGENT_ID = "ag_019cc2276c1d7585a32da68d0b63278b"

client = Mistral(api_key=MISTRAL_KEY)
bot = telebot.TeleBot(TELE_TOKEN)

# Simple in-memory storage for conversation history per user
# Keeps the last 10 messages so the bot remembers context
user_sessions = {}

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    
    # Initialize history for new users
    if user_id not in user_sessions:
        user_sessions[user_id] = []

    # Add user message to history
    user_sessions[user_id].append({"role": "user", "content": message.text})

    # Keep only the last 10 messages to save memory
    user_sessions[user_id] = user_sessions[user_id][-10:]

    try:
        # Send history to your Mistral Agent
        chat_response = client.agents.complete(
            agent_id=AGENT_ID,
            messages=user_sessions[user_id]
        )
        
        bot_reply = chat_response.choices[0].message.content
        
        # Add assistant response back to history
        user_sessions[user_id].append({"role": "assistant", "content": bot_reply})
        
        # Send the response to the user on Telegram
        bot.reply_to(message, bot_reply, parse_mode='Markdown')

    except Exception as e:
        print(f"Error calling Mistral: {e}")
        bot.reply_to(message, "I'm having trouble connecting to my brain (Mistral). Try again in a second!")

if __name__ == "__main__":
    # Start Flask in a background thread
    Thread(target=run_flask).start()
    
    # Start the Telegram Bot in the main thread
    print("🚀 Dwip, your Task Manager Bot is starting...")
    bot.infinity_polling()