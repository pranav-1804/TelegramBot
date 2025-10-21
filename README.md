**Overview**

Develop a Telegram bot using Telethon to retrieve information about posts (new and historical), log them to the console, and save them to a CSV file.

**Prerequisites**

Python 3.8+ installed
Access to a terminal/command prompt
Git (optional, for cloning)


**Getting Telethon API Credentials**
Create a Telegram App
Go to: https://my.telegram.org
Log in with your Telegram account
Navigate to “API development tools” (or “Create new application” if prompted)
Create a new application:
App title: any name
Short name: a short identifier
After saving, you will see:
API_ID (integer)
API_HASH (32-character hex string)
Save Credentials Securely
Note down the API_ID and API_HASH and do not share them publicly.



Environment File (.env)

Create a file named .env at the project root
Add the following variables (replace with your actual values)
API_ID=your_api_id_here
API_HASH=your_api_hash_here
SESSION=session_name
INVITE_LINK=invite_link_of_channel_

Tips:

Keep .env out of version control by adding it to .gitignore.

SESSION is the session name used by Telethon (e.g., “telegram_bot”).
INVITE_LINK is a private/public invite link or join link for the target channel.


**Setting Up a Virtual Environment (venv)**


Create Virtual Environment
macOS/Linux:
python3 -m venv venv

Windows (CMD/PowerShell):
py -m venv venv

Activate the Virtual Environment
macOS/Linux:
source venv/bin/activate

Windows (CMD):
venv\Scripts\activate

Windows (PowerShell):
.\venv\Scripts\Activate.ps1

**Install Dependencies**

pip install -r requirements.txt


**Running the Project**
Ensure the virtual environment is activated
Confirm .env is present with correct values


Run the program script
python services/telegram_listener.py
Verify the Bot Is Running
Check console output for post messages (new and historical)
Confirm CSV file is created/updated with captured post data
