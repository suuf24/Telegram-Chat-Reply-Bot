import os
import json
import random
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

# Load chat messages from JSON files
def load_messages(filename):
    try:
        with open(filename, 'r') as file:
            data = json.load(file)
            return data  # Return the list of messages
    except FileNotFoundError:
        print(f"⚠️ {filename} not found.")
        return []
    except json.JSONDecodeError:
        print(f"⚠️ Failed to decode {filename}.")
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

    # Define the sender (A) and the order of receivers (B, C, D)
    sender_code = 'A'
    receiver_order = ['B', 'C', 'D']  # Sequence: A->B, B->A, A->C, C->A, A->D, D->A

    sender_client = clients.get(sender_code)
    if not sender_client:
        print(f"⚠️ Sender client {sender_code} is not available.")
        return

    # Load sender's messages
    sender_messages = load_messages(f"{sender_code}_chat.json")
    if not sender_messages:
        print(f"⚠️ No messages found in {sender_code}_chat.json.")
        return

    # Load receiver messages and create iterators
    receiver_message_iterators = {}
    receiver_current_messages = {}  # Store current message for each receiver
    for receiver_code in receiver_order:
        messages = load_messages(f"{receiver_code}_chat.json")
        if not messages:
            print(f"⚠️ No messages found in {receiver_code}_chat.json.")
            return
        # Create an iterator that cycles through messages
        receiver_message_iterators[receiver_code] = iter(messages)
        # Preload the first message
        try:
            receiver_current_messages[receiver_code] = next(receiver_message_iterators[receiver_code])
        except StopIteration:
            receiver_current_messages[receiver_code] = None

    # Infinite loop for sequential chatting
    while True:
        # Iterate through sender's messages
        sender_iterator = iter(sender_messages)  # Reset sender messages iterator each cycle
        try:
            sender_message = next(sender_iterator)
        except StopIteration:
            print("⚠️ No more sender messages available.")
            break

        while sender_message:
            # Process each receiver in order (B, C, D)
            for receiver_code in receiver_order:
                receiver_client = clients.get(receiver_code)
                if not receiver_client:
                    print(f"⚠️ Receiver client {receiver_code} is not available.")
                    continue

                try:
                    # Send message from A to current receiver (B, C, or D)
                    print(f"📤 Attempting to send from {ACCOUNTS[sender_code]['username']} to {ACCOUNTS[receiver_code]['username']}: {sender_message}")
                    await sender_client.send_message(ACCOUNTS[receiver_code]["username"], sender_message)
                    print(f"✉️ {ACCOUNTS[sender_code]['username']} -> {ACCOUNTS[receiver_code]['username']}: {sender_message}")

                    # Wait for a random delay before receiver replies
                    random_delay(1.0, 3.0)

                    # Receiver replies to A with one message
                    receiver_message = receiver_current_messages[receiver_code]
                    if receiver_message:
                        print(f"📥 {ACCOUNTS[receiver_code]['username']} received message, replying with: {receiver_message}")
                        await receiver_client.send_message(ACCOUNTS[sender_code]["username"], receiver_message)
                        print(f"✉️ {ACCOUNTS[receiver_code]['username']} -> {ACCOUNTS[sender_code]['username']}: {receiver_message}")

                        # Move to the next receiver message
                        try:
                            receiver_current_messages[receiver_code] = next(receiver_message_iterators[receiver_code])
                        except StopIteration:
                            # Reset iterator to start of messages
                            messages = load_messages(f"{receiver_code}_chat.json")
                            receiver_message_iterators[receiver_code] = iter(messages)
                            try:
                                receiver_current_messages[receiver_code] = next(receiver_message_iterators[receiver_code])
                            except StopIteration:
                                receiver_current_messages[receiver_code] = None
                                print(f"⚠️ No more messages available for {receiver_code}.")

                        # Simulate natural response delay
                        random_delay(1.0, 5.0)
                    else:
                        print(f"⚠️ No reply available from {ACCOUNTS[receiver_code]['username']}.")

                    # Try to get the next sender message
                    try:
                        sender_message = next(sender_iterator)
                    except StopIteration:
                        sender_message = None
                        print(f"📢 No more messages from {ACCOUNTS[sender_code]['username']} for this cycle.")
                        break  # Exit inner loop if no more sender messages

                    # Delay before sending to the next receiver
                    random_delay(3.0, 5.0)

                except Exception as e:
                    print(f"⚠️ Failed to send from {sender_code} to {receiver_code}: {e}")

            # If no more sender messages, break out
            if not sender_message:
                break

        # After completing one full cycle (A->B, B->A, A->C, C->A, A->D, D->A), pause before restarting
        print("🔁 Restarting the chat loop (A -> B, C, D)...")
        time.sleep(10)  # Wait 10 seconds before restarting the loop

    # Disconnect all clients (unreachable in infinite loop)
    await asyncio.gather(*(client.disconnect() for client in clients.values()))

if __name__ == "__main__":
    asyncio.run(main())
