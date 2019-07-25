# -*- coding:utf-8 -*-
from mitmproxy import ctx
import redis
import re

'''
命令 mitmproxy -s mitm_proxy.py
'''

redis_client = redis.Redis(host='192.168.1.157',port=6379)

def request(flow):
    #打印信息
    info = ctx.log.info

    if flow.request.url.startswith('https://api9.tianyancha.com/services/v3/search/sNor'):
        author = flow.request.headers['Authorization']
        info(author)

        author = re.sub(r'###\d+###','###{}###',author)
        # 需要判断 author 是否已经存在
        if not redis_client.sismember('tyc_author_all',author):

            redis_client.sadd('tyc_author_all',author)
            redis_client.lpush('tyc_author_1',author)

