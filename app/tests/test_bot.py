import unittest
from app.routes import generate_post

class BotTestCase(unittest.TestCase):
    def test_generate_length(self):
        post=generate_post("teste")
        self.assertLessEqual(len(post),280)
        self.assertIn("teste",post.lower())

if __name__ == '__main__':
    unittest.main()