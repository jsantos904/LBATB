from enum import Enum
import json

from flask import Flask, request
import requests
import openai
import tiktoken

from config import OPENAI_API_KEY, AI_CHATBOTID

SYSTEM_PROMPT = """
Act as a Python teacher. Answer any python coding related questions as if the student is a beginner. Replace any 3 backticks with 25 dashes. 
"""
HISTORY_TOKEN_LIMIT = 2000
OUTPUT_TOKEN_LIMIT = 500
AIBOT_USERID = '879522'
AIBOT_NAME = '@ai'

class CommandType(Enum):
    PING = '!ping'
    CLEARVARS = '!clear'
    HELP = '!help'
    WHY = '!why'

class Conversation:
    def __init__(self, tokenizer):
        self.tokenizer = tokenizer
        self.history_token_limit = HISTORY_TOKEN_LIMIT
        self.conversation_history = self.load_conversation()

    def save_conversation(self):
        with open('conversation.json', 'w') as file:
            json.dump(self.conversation_history, file)

    def load_conversation(self):
        try:
            with open('conversation.json', 'r') as file:
                return json.load(file)
        except FileNotFoundError:       # If the file doesn't exist, return an empty list
            return []

    def add_message_to_history(self, role, content):
        self.conversation_history.append({'role': role, 'content': content})
        while self.count_tokens() > self.history_token_limit:
            self.conversation_history.pop(0)
        self.save_conversation()

    def count_tokens(self):
        tokens = " ".join([m['content'] for m in self.conversation_history])
        return len(self.tokenizer.encode(tokens))

class AiBot:
    def __init__(self, api_key):
        openai.api_key = api_key
        self.openai = openai
        tokenizer = tiktoken.get_encoding("cl100k_base")
        self.conversation = Conversation(tokenizer)
        self.app = Flask(__name__)
        self.output_token_limit = OUTPUT_TOKEN_LIMIT
        self.app.route('/', methods=['POST'])(self.webhook)

    def webhook(self):
        data = request.get_json()
        self.process_message(data['user_id'], data['text'])
        return "ok", 200

    def process_message(self, user_id, text):
        if user_id != AIBOT_USERID and text.strip().startswith(AIBOT_NAME):  # this code doesnt check for a @ai command
            text = text.split('@ai', 1)[1].strip()  # Remove '@ai' from the start of the message
            if text.lower() in [c.value for c in CommandType]:  
                self.handle_command(CommandType(text.lower()))  
                self.handle_text(text)

    def handle_command(self, command):
        command_handlers = {
            CommandType.CLEARVARS: self.clear_conversation,
            CommandType.PING: self.ping,
            CommandType.HELP: self.help,
            CommandType.WHY: self.why,
        }
        command_handlers[command]()

    def clear_conversation(self):
        self.conversation.conversation_history = []
        self.conversation.save_conversation()
        self.post_message('Conversation history has been cleared.')

    def ping(self):
        self.post_message('AI Chat is up and running.')

    def why(self):
        self.handle_why_command()

    def handle_why_command(self):
        with open("chat_history.json", "r") as file: # this is a file that py_chatbot.py creates
            chat_history = json.load(file)
            if self.is_last_message_error(chat_history):
                last_two_items = chat_history[-2:]
                last_two_items.append({"user" : "Could you please interpret the nature of this error message? Additionally, please illustrate an appropriate solution, including a code example demonstrating the correct approach."})
                messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
                messages.extend(last_two_items)
                response_text = self.get_response_text(messages)
                self.conversation.add_message_to_history('assistant', response_text)
                self.post_message(response_text)
            else:
                self.post_message('The last message was not an error.')

    def is_last_message_error(self, chat_history):
        last_message = chat_history[-1]['content'].lower()
        error_keywords = ['error', 'exception', 'traceback']
        for keyword in error_keywords:
            if keyword in last_message:
                return True
        return False

    def help(self):
        commands = [
            {'command':'!clear', 'description': 'Clears the conversation history.'},
            {'command':'!ping', 'description': 'Checks if the aibot server is running.'},
            {'command':'!why', 'description': 'Explains the last error.'},
            {'command':'!help', 'description': 'Displays this help message'},
            {'command':f'{AIBOT_NAME} <question>', 'description': 'ask aibot a question'}
        ]
        help_message = "Available commands for aibot:\n" + "\n".join(f"{command['command']}: {command['description']}" for command in commands)
        self.post_message(help_message)

    def handle_text(self, text):
        self.conversation.add_message_to_history('user', text)
        messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
        messages.extend([{'role': m['role'], 'content': m['content']} for m in self.conversation.conversation_history])
        response_text = self.get_response_text(messages)
        self.conversation.add_message_to_history('assistant', response_text)
        self.post_message(response_text)

    def get_response_text(self, messages):
        response = self.openai.ChatCompletion.create(
            model="gpt-3.5-turbo", 
            messages=messages,
            max_tokens=self.output_token_limit
        )
        response_text = response['choices'][0]['message']['content'].strip()
        
        # I don't think we need the below code. I was trying to force replace an indent with > for groupme
        # since it looked funky in the iphone app. Will need to import re if we want to use it.
        
        # return re.sub(r'\n( {4})*', lambda match: '\n' + '>' * (len(match.group(0)) // 4), response_text)

        return response_text

    def post_message(self, msg):
        requests.post('https://api.groupme.com/v3/bots/post', params={'bot_id': AI_CHATBOTID, 'text': msg})

    def run(self, host='0.0.0.0', port=5080):
        self.app.run(host=host, port=port, debug=True)
    
if __name__ == "__main__":
    chat_bot_app = AiBot(OPENAI_API_KEY)
    chat_bot_app.run()
    