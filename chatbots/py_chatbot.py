from enum import Enum
import traceback
import contextlib
import io
import json

from flask import Flask, request
import requests

from config import PY_CHATBOTID

POST_URL = 'https://api.groupme.com/v3/bots/post'
PYBOT_NAME = "@py"
PYBOT_USERID = "879523"

class CommandType(Enum):
    PING = '!ping'
    CLEARVARS = '!clear'
    LISTVARS = '!list'
    HELP = '!help'

class PyBot:
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
        self.app = Flask(__name__)
        self.app.route('/', methods=['POST'])(self.webhook)

    def webhook(self):
        data = request.get_json()
        self.process_message(data['user_id'], data['text'])
        return "ok", 200
    
    def process_message(self, user_id, text):   
        if text.strip().startswith(PYBOT_NAME):
            command, args = self.parse_message(text)
            if command is None:
                self.history.append({'role': 'user', 'content': text})  
                self.handle_python_command(args, user_id)
            else:
                self.command_handlers[command]()
                
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
    
    def post_message(self, text, mention=False):
        data = {'bot_id': self.bot_id, 'text': str(text)}
        requests.post(POST_URL, json=data)

    def execute_code(self, code):
        try:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.__safe_exec(code)
            output = stdout.getvalue()
            formatted_output = '-'*25 + '\n' + output + '\n' + '-'*25 if 'print' in code else output
            return output, formatted_output
        except Exception as e:
            traceback_message = traceback.format_exc()
            formatted_traceback = "\n".join(traceback_message.splitlines()[-2:])
            raise Exception(f'Error executing code: {e}')
        
    def __safe_exec(self, code):
        allowed_modules = {'math', 'json', 're', 'random', 'datetime', 
                        'time', 'collections', 'itertools', 'functools', 
                        'heapq', 'bisect', 'copy', 'enum', 'fractions', 
                        'decimal', 'statistics', 'operator'}  # The set of modules that are allowed
        disallowed_builtins = {'open','eval'}  # The set of built-in functions that are not allowed

        def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name in allowed_modules:
                return __import__(name, globals, locals, fromlist, level)
            raise ImportError(f'Importing {name} is not allowed')

        safe_builtins = {key: value for key, value in globals()["__builtins__"].__dict__.items()
                        if key not in disallowed_builtins}
        safe_builtins['__import__'] = safe_import
        try:
            exec(code, {"__builtins__": safe_builtins}, self.limited_locals)
        except Exception as e:
            raise Exception(f'Error executing code: {e}')

    def clean_code(self, code):
        return code.replace(PYBOT_NAME, '').strip()

    def handle_ping_command(self):
        self.post_message('PyBot is up and running!')

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
            {'command': f'{PYBOT_NAME} <code>', 'description': 'Executes the Python code.'},
            {'command': '!ping', 'description': 'Checks if the pybot serveris up and running.'},
            {'command': '!help', 'description': 'Displays this help message.'}
        ]
        help_message = "Available commands for pybot:\n" + "\n".join(f"{command['command']}: {command['description']}" for command in commands)
        self.post_message(help_message)

    def save_chat_history(self):
        with open('chat_history.json', 'w') as f:
            json.dump(self.history, f)

    def run(self, host='0.0.0.0', port=5020):
        self.app.run(host=host, port=port, debug=True)

if __name__ == "__main__":
    bot = PyBot(PY_CHATBOTID)
    bot.run()
    