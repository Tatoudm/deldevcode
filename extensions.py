import pymongo
from flask_limiter import Limiter
from flask_sock import Sock
from flask import request

mongo_client = None
db = None

sock = Sock()


def get_client_ip():
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip

    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()

    return request.remote_addr


limiter = Limiter(
    key_func=get_client_ip,
    default_limits=["200 per hour"],
)


def init_db(uri: str):
    global mongo_client, db
    mongo_client = pymongo.MongoClient(uri)
    db = mongo_client.get_default_database()
