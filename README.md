TelegramBot Project
A Python-based Telegram bot leveraging Telethon. This project uses a virtual environment (venv) and a .env file to store sensitive configuration like API credentials.

**Prerequisites**
Python 3.8+ installed
Access to a terminal/command prompt
Git (optional, for cloning)

**Getting Telethon API credentials**
To use Telethon, you need:

API_ID (an integer)
API_HASH (a 32-character hex string)
Follow these steps to obtain them:

**Create a Telegram App**
Go to: https://my.telegram.org
Log in with your Telegram account
Navigate to "API development tools" (or "Create new application" if prompted)
Create a new application:
App title: any name
Short name: a short identifier
After saving, you will see:
API development tools: API_ID
API_HASH
Save credentials securely
Note down the API_ID (integer) and API_HASH (string).


**Environment file (env)**
Create a file named .env at the project root.
Add the following variables (replace with your actual values):

API_ID=your_api_id_here
API_HASH=your_api_hash_here
BOT_TOKEN=your_bot_token_if_you_use_one (optional, if applicable)

**Setting up a virtual environment (venv)** 

1) Create Virtual Enviroment
python3 -m venv venv

2) Activate the virtual environment
source .venv/bin/activate

3)Install dependencies
pip install -r requirements.txt

**Running the project**
Ensure the environment is loaded
On activation, you should see the venv name in your shell prompt.
Run the program script 

python services/telegram_listener.py

**Verify the bot is running**
Check console output for post messages

