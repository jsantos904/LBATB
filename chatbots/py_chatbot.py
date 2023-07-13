from enum import Enum
import traceback
import contextlib
import io
import json

from flask import Flask, request
import requests

from config import PY_CHATBOTID

POST_URL = 'https://api.groupme.com/v3/bots/post'
BOT_NAME = "@py"

class CommandType(Enum):
    PING = '!ping'
    CLEARVARS = '!clear'
    LISTVARS = '!list'
    HELP = '!help'

class Bot:
    def __init__(self, bot_id):
        self.bot_id = bot_id
        self.limited_locals = {}
        self.history = []
        self.command_handlers = {
            CommandType.PING: self.handle_ping_command,
            CommandType.CLEARVARS: self.clear_vars,
            CommandType.LISTVARS: self.list_vars,
            CommandType.HELP: self.help,
        }

    def post_message(self, text, mention=False):
        data = {'bot_id': self.bot_id, 'text': str(text)}
        requests.post(POST_URL, json=data)

    def execute_code(self, code):
        try:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exec(code, {"__builtins__": __builtins__}, self.limited_locals)
            output = stdout.getvalue()
            formatted_output = f"----[START OUTPUT]----\n{output or ''}\n----[END OUTPUT]----" if 'print' in code else output
            return output, formatted_output
        except Exception:
            traceback_message = traceback.format_exc()
            formatted_traceback = "\n".join(traceback_message.splitlines()[-2:])
            return traceback_message, formatted_traceback

    def process_message(self, user_id, name, message):   # name isn't being used, but might use it later
        if message.strip().startswith(BOT_NAME):
            command, args = self.parse_message(message)
            if command is None:
                self.history.append({'role': 'user', 'content': message})  
                self.handle_python_command(args, user_id)
            else:
                self.command_handlers[command]()

    def clean_code(self, code):
        return code.replace(BOT_NAME, '').strip()

    def parse_message(self, message):
        cleaned_message = self.clean_code(message)
        split_message = cleaned_message.strip().split(' ', 1)
        try:
            command = CommandType(split_message[0])
            args = split_message[1] if len(split_message) > 1 else None
        except ValueError:
            command = None
            args = cleaned_message
        return command, args

    def handle_ping_command(self):
        self.post_message('Bot is up and running!')
        
    def handle_python_command(self, args, user_id):
        output, formatted_output = self.execute_code(args)
        if formatted_output is not None:
            self.history.append({'role': 'assistant', 'content': output}) 
            self.save_chat_history()
            self.post_message(formatted_output)

    def clear_vars(self):
        self.limited_locals.clear()
        self.post_message('All variables have been cleared.')

    def list_vars(self):
        vars_list = "\n".join(f"{var}: {val}" for var, val in self.limited_locals.items())
        self.post_message(vars_list if vars_list else 'No variables.')

    def help(self):
        commands = [
            {'command': '!clear', 'description': 'Clears all variables.'},
            {'command': '!list', 'description': 'Lists all variables and their values.'},
            {'command': f"{BOT_NAME} <code>", 'description': 'Executes the Python code.'},
            {'command': '!ping', 'description': 'Checks if the bot is up and running.'},
            {'command': '!help', 'description': 'Displays this help message.'}
        ]
        help_message = "Available commands:\n" + "\n".join(f"{command['command']}: {command['description']}" for command in commands)
        self.post_message(help_message)

    def save_chat_history(self):
        with open('chat_history.json', 'w') as f:
            json.dump(self.history, f)


app = Flask(__name__)
bot = Bot(PY_CHATBOTID)

@app.route('/', methods=['POST'])
def webhook():
    data = request.get_json()
    bot.process_message(data['user_id'], data['name'], data['text'])
  
    with open('data.json', 'w') as outfile:  # for testing
        json.dump(data, outfile, indent=4)       # for testing
    
    return "ok", 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5020, debug=True)