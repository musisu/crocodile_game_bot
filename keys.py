import os

TOKEN = os.getenv("TOKEN")

if TOKEN is None:
    raise RuntimeError("TOKEN не задано")
