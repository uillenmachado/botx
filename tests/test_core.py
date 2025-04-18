
import unittest
from app import create_app, db
from app.models import User
class CoreTest(unittest.TestCase):
    def setUp(self):
        self.app=create_app()
        self.app.config['SQLALCHEMY_DATABASE_URI']='sqlite:///:memory:'
        self.app.config['TESTING']=True
        with self.app.app_context():
            db.create_all()
        self.client=self.app.test_client()
    def test_generate(self):
        r=self.client.post('/generate',data={'context':'teste'})
        self.assertEqual(r.status_code,200)
if __name__=='__main__':unittest.main()
