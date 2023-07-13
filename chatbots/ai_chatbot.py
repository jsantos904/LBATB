import json
import requests
import re

from flask import Flask, request
import openai
import tiktoken

from config import OPENAI_API_KEY, AI_CHATBOTID

SYSTEM_PROMPT = """
Act as a Python teacher. Answer any python coding related questions as if the student is a beginner. Replace any 3 backticks with 25 dashes. 
"""
HISTORY_TOKEN_LIMIT = 2000
OUTPUT_TOKEN_LIMIT = 500
AIBOT_USERID = '879522'

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

class ChatBotApp:
    def __init__(self, openai, conversation):
        self.app = Flask(__name__)
        self.openai = openai
        self.conversation = conversation
        self.output_token_limit = OUTPUT_TOKEN_LIMIT
        self.app.route('/', methods=['POST'])(self.webhook)

    def webhook(self):
        data = request.get_json()
        text = data['text']
        if data['user_id'] != AIBOT_USERID:
            text = text.split('@ai', 1)[1].strip()  # Remove '@ai' from the start of the message
            if text.lower() in ['!clear', '!ping', '!why', '!help']:
                self.handle_command(text.lower())
            else:
                self.handle_text(text)
        
        return "ok", 200

    def handle_command(self, command):
        if command == '!clear':
            self.conversation.conversation_history = []
            self.conversation.save_conversation()
            self.send_message('Conversation history has been cleared.')

        elif command == '!ping':
            self.send_message('AI Chat is up and running.')

        elif command == '!why':
            self.handle_why_command()

        elif command == '!help':
            help_text = """
            Here are the commands you can use:
            - `!clear`: Clears the conversation history.
            - `!ping`: Checks if the server is running.
            - `!why`: Explains the last error.
            """
            self.send_message(help_text)

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
                self.send_message(response_text)
            else:
                self.send_message('The last message was not an error.')
            
    def is_last_message_error(self, chat_history):
        last_message = chat_history[-1]['content'].lower()
        error_keywords = ['error', 'exception', 'traceback']
        for keyword in error_keywords:
            if keyword in last_message:
                return True
        return False

    def handle_text(self, text):
        self.conversation.add_message_to_history('user', text)
        messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
        messages.extend([{'role': m['role'], 'content': m['content']} for m in self.conversation.conversation_history])
        response_text = self.get_response_text(messages)
        self.conversation.add_message_to_history('assistant', response_text)
        self.send_message(response_text)

    def get_response_text(self, messages):
        response = self.openai.ChatCompletion.create(
            model="gpt-3.5-turbo", 
            messages=messages,
            max_tokens=self.output_token_limit
        )
        response_text = response['choices'][0]['message']['content'].strip()
        
        # I don't think we need the below code. I was trying to force replace an indent with > for groupme
        # since it looked funky in the iphone app.
        
        # return re.sub(r'\n( {4})*', lambda match: '\n' + '>' * (len(match.group(0)) // 4), response_text)

        return response_text
    
    def send_message(self, msg):
        requests.post('https://api.groupme.com/v3/bots/post', params={'bot_id': AI_CHATBOTID, 'text': msg})

    def run(self, host='0.0.0.0', port=5080):
        self.app.run(host=host, port=port, debug=True)

if __name__ == "__main__":
    openai.api_key = OPENAI_API_KEY
    tokenizer = tiktoken.get_encoding("cl100k_base")
    conversation = Conversation(tokenizer)
    chat_bot_app = ChatBotApp(openai, conversation)
    chat_bot_app.run()
