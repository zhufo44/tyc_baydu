# -*- coding:utf-8 -*-
from pymongo import MongoClient
import redis
import time
import re

# mongodb连接
def conMongo():
    conMongo = MongoClient(host='192.168.1.170',port=27017,)
    return conMongo

# redis连接
def conRedis():
    return redis.Redis(host='192.168.1.157',port=6379)

redis_client = conRedis()
def getip():
    ip = redis_client.brpop('tianyan_proxy',0)[1].decode('utf8')
    proxy = {"http": "http://user:passwd@"+ip,"https": "https://user:passwd@"+ip}
    # proxy = {"http": 'http://' + ip, "https": 'https://' + ip}
    print('ip地址：', ip)
    return proxy

# 获取author
def get_author():
    print('获取author中')
    author = redis_client.brpoplpush('tyc_author_1','tyc_author_2').decode('utf8')
    time_stamp = int(time.time())
    author = author.format(time_stamp)
    return author

# 失效author ，将当前 author 从tyc_author_2 删除 ，再获取一个新的author返回
#  并从 tyc_author_all 中删除
def invalid_token(author):
    print('token 失效')
    author  = re.sub(r'###\d+###','###{}###',author)
    redis_client.lrem('tyc_author_2',count=1,value=author)
    redis_client.spop('tyc_author_all',author)
    author = get_author()
    return author

#切换author--把author从 tyc_author_2 移到 tyc_author_3 并加上当前时间戳
def switch_author(author):
    author  = re.sub(r'###\d+###','###{}###',author)
    redis_client.lrem('tyc_author_2',count=1,value=author)
    cur_time = int(time.time())
    redis_client.lpush('tyc_author_3',author+'^*^'+str(cur_time))
    author = get_author()
    return author