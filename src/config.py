import os

DATABASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "users.db")

USE_SSL = True
SSL_CERT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cert.pem")
SSL_KEY = os.path.join(os.path.dirname(os.path.dirname(__file__)), "key.pem")
USERS_AMMOUNT_IF_TEST = 1000
