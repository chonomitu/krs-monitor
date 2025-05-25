
import os
from dotenv import load_dotenv

load_dotenv()

RPC_URL = os.getenv("ARBITRUM_RPC_URL")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
