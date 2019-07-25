# -*- coding:utf-8 -*-
from function import redis_client

'''
由于程序异常 或者 手动停止（修改程序） 会导致正在使用的 author 堆积在 tyc_author_2
在程序全部停止的情况下 ，运行该脚本，将 tyc_author_2 中的重新放入 tyc_author_1 中
'''

for i in redis_client.lrange('tyc_author_2',0,-1):
    text = i.decode('utf8')
    print(text)
    redis_client.lpush('tyc_author_1',text)

redis_client.delete('tyc_author_2')