import os
import json
import random
import requests
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
import asyncio
import time

load_dotenv()

# Load accounts from .env
ACCOUNTS = {}
for key in os.environ:
    if key.startswith("API_ID_"):
        prefix = key.split("_")[2]
        ACCOUNTS[prefix] = {
            "api_id": int(os.getenv(f"API_ID_{prefix}")),
            "api_hash": os.getenv(f"API_HASH_{prefix}"),
            "phone": os.getenv(f"PHONE_{prefix}"),
            "username": os.getenv(f"USERNAME_{prefix}"),
        }

# Load chat pairs
CHAT_PAIRS = os.getenv("CHAT_PAIRS", "")
CHAT_PAIRS = [pair.strip() for pair in CHAT_PAIRS.split(",") if pair.strip()]

# Show accounts
print("📦 Loaded Accounts:")
for code, acc in ACCOUNTS.items():
    print(f"  {code}: {acc['username']} ({acc['phone']})")

# Show chat pairs
print("\n📬 Chat Pairs:")
for pair in CHAT_PAIRS:
    print(f"  {pair}")

# Build sender -> receivers map
SEND_MAP = {}
for pair in CHAT_PAIRS:
    sender, receiver = pair.split("-")
    SEND_MAP.setdefault(sender, []).append(receiver)

print()
for sender_code, receiver_codes in SEND_MAP.items():
    sender_acc = ACCOUNTS[sender_code]
    print(f"🔄 {sender_code} akan mengirim ke:")
    for receiver_code in receiver_codes:
        r = ACCOUNTS[receiver_code]
        print(f"  {r['username']} ({r['phone']})")

# Load messages from local file or URL
def load_messages(source):
    try:
        if source.startswith("http"):
            response = requests.get(source)
            response.raise_for_status()
            return response.json()
        else:
            with open(source, 'r') as file:
                return json.load(file)
    except FileNotFoundError:
        print(f"⚠️ {source} not found.")
        return []
    except json.JSONDecodeError:
        print(f"⚠️ Failed to decode {source}.")
        return []
    except requests.RequestException as e:
        print(f"⚠️ Failed to load from URL {source}: {e}")
        return []

# Function to simulate a delay with randomness (natural)
def random_delay(min_delay=1.0, max_delay=3.0):
    delay = random.uniform(min_delay, max_delay)
    print(f"⏳ Waiting for {delay:.2f} seconds...")
    time.sleep(delay)

# Main logic with login code handling
async def main():
    clients = {}

    for code, acc in ACCOUNTS.items():
        session_name = f"session_{code}"
        client = TelegramClient(session_name, acc['api_id'], acc['api_hash'])

        try:
            await client.connect()
            if not await client.is_user_authorized():
                print(f"\n🔐 Login required for {acc['username']} ({acc['phone']})")
                await client.send_code_request(acc['phone'])
                code_input = input(f"📲 Enter the code sent to {acc['phone']}: ")
                try:
                    await client.sign_in(acc['phone'], code_input)
                except SessionPasswordNeededError:
                    pw = input("🔑 2FA Password required: ")
                    await client.sign_in(password=pw)
            clients[code] = client
            print(f"✅ Logged in: {acc['username']}")

        except Exception as e:
            print(f"❌ Failed to log in {acc['username']} ({acc['phone']}): {e}")

    print("\n🚀 Starting sequential chat loop...")

    sender_code = 'A'
    receiver_order = ['B', 'C', 'D']

    sender_client = clients.get(sender_code)
    if not sender_client:
        print(f"⚠️ Sender client {sender_code} is not available.")
        return

    # URLs for remote chat sources
    chat_sources = {
        "A": "https://raw.githubusercontent.com/suuf24/Telegram-Chat-Reply-Bot/refs/heads/main/A_chat.json",
        "B": "https://raw.githubusercontent.com/suuf24/Telegram-Chat-Reply-Bot/refs/heads/main/B_chat.json",
        "C": "https://raw.githubusercontent.com/suuf24/Telegram-Chat-Reply-Bot/refs/heads/main/C_chat.json",
        "D": "https://raw.githubusercontent.com/suuf24/Telegram-Chat-Reply-Bot/refs/heads/main/C_chat.json",
    }

    sender_messages = load_messages(chat_sources[sender_code])
    if not sender_messages:
        print(f"⚠️ No messages found for sender {sender_code}.")
        return

    receiver_message_iterators = {}
    receiver_current_messages = {}
    for receiver_code in receiver_order:
        messages = load_messages(chat_sources[receiver_code])
        if not messages:
            print(f"⚠️ No messages found for receiver {receiver_code}.")
            return
        receiver_message_iterators[receiver_code] = iter(messages)
        try:
            receiver_current_messages[receiver_code] = next(receiver_message_iterators[receiver_code])
        except StopIteration:
            receiver_current_messages[receiver_code] = None

    while True:
        sender_iterator = iter(sender_messages)
        try:
            sender_message = next(sender_iterator)
        except StopIteration:
            print("⚠️ No more sender messages available.")
            break

        while sender_message:
            for receiver_code in receiver_order:
                receiver_client = clients.get(receiver_code)
                if not receiver_client:
                    print(f"⚠️ Receiver client {receiver_code} is not available.")
                    continue

                try:
                    print(f"📤 Sending from {ACCOUNTS[sender_code]['username']} to {ACCOUNTS[receiver_code]['username']}: {sender_message}")
                    await sender_client.send_message(ACCOUNTS[receiver_code]["username"], sender_message)
                    print(f"✉️ Sent to {ACCOUNTS[receiver_code]['username']}")

                    random_delay(1.0, 3.0)

                    receiver_message = receiver_current_messages[receiver_code]
                    if receiver_message:
                        print(f"📥 Replying from {receiver_code} to {sender_code}: {receiver_message}")
                        await receiver_client.send_message(ACCOUNTS[sender_code]["username"], receiver_message)
                        print(f"✉️ {receiver_code} -> {sender_code}: {receiver_message}")

                        try:
                            receiver_current_messages[receiver_code] = next(receiver_message_iterators[receiver_code])
                        except StopIteration:
                            messages = load_messages(chat_sources[receiver_code])
                            receiver_message_iterators[receiver_code] = iter(messages)
                            try:
                                receiver_current_messages[receiver_code] = next(receiver_message_iterators[receiver_code])
                            except StopIteration:
                                receiver_current_messages[receiver_code] = None
                                print(f"⚠️ No more messages for {receiver_code}.")

                        random_delay(1.0, 5.0)
                    else:
                        print(f"⚠️ No reply available from {receiver_code}.")

                    try:
                        sender_message = next(sender_iterator)
                    except StopIteration:
                        sender_message = None
                        print(f"📢 No more sender messages for this cycle.")
                        break

                    random_delay(3.0, 5.0)

                except Exception as e:
                    print(f"⚠️ Failed to send message: {e}")

            if not sender_message:
                break

        print("🔁 Restarting the chat loop...")
        time.sleep(10)

    await asyncio.gather(*(client.disconnect() for client in clients.values()))

if __name__ == "__main__":
    asyncio.run(main())
