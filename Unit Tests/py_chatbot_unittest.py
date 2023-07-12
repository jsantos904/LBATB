import unittest
from unittest.mock import patch
from ..py_chatbot import Bot  

class TestBot(unittest.TestCase):
    def setUp(self):
        self.bot = Bot('6113539', '1762a0c26e474625a192c7d09a')

    @patch('requests.post')
    def test_post_message(self, mock_post):
        # Test posting a message without a mention
        self.bot.post_message("test message")
        mock_post.assert_called_with(
            'https://api.groupme.com/v3/bots/post',
            json={'bot_id': '1762a0c26e474625a192c7d09a', 'text': 'test message'}
        )

        # Test posting a message with a mention
        self.bot.post_message("test message", mention=True)
        mock_post.assert_called_with(
            'https://api.groupme.com/v3/bots/post',
            json={
                'bot_id': '1762a0c26e474625a192c7d09a',
                'text': 'test message',
                'attachments': [{'type': 'mentions', 'user_ids': ['6113539'], 'loci': [(0, 8)]}]
            }
        )

    def test_execute_code(self):
        # Test executing code that produces an output
        code = "print('Hello, World!')"
        self.assertEqual(self.bot.execute_code(code), 'Hello, World!\n')

        # Test executing code that doesn't produce an output
        code = "x = 1"
        self.assertEqual(self.bot.execute_code(code), 'No result!')

        # Test executing code that raises an exception
        code = "1 / 0"
        self.assertTrue("ZeroDivisionError" in self.bot.execute_code(code))

    @patch('your_flask_app.Bot.post_message')
    def test_approve_code(self, mock_post_message):
        # Approve code when approval is required and code exists in pending_code
        self.bot.approval_required = True
        self.bot.pending_code = {'123': 'print("Hello, World!")'}
        self.bot.approve_code('123')
        mock_post_message.assert_called_with('Hello, World!\n')

        # Approve code when approval is not required
        self.bot.approval_required = False
        self.bot.approve_code('123')
        mock_post_message.assert_called_with("Approval not required to run code.")

        # Approve code when code doesn't exist in pending_code
        self.bot.approval_required = True
        self.bot.pending_code = {}
        self.bot.approve_code('123')
        mock_post_message.assert_called_with("No such code snippet.")

    @patch('your_flask_app.Bot.post_message')
    def test_view_queue(self, mock_post_message):
        # View queue when it's empty
        self.bot.pending_code = {}
        self.bot.view_queue()
        mock_post_message.assert_called_with("The queue is empty.")

        # View queue when it has code snippets
        self.bot.pending_code = {'123': 'print("Hello, World!")', '456': 'x = 1'}
        self.bot.view_queue()
        expected_message = "ID: 123, Code: print(\"Hello, World!\")\nID: 456, Code: x = 1"
        mock_post_message.assert_called_with(expected_message)


if __name__ == "__main__":
    unittest.main()
