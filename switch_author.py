# -*- coding:utf-8 -*-
import re
import time
import redis
from time import sleep


'''
账号被封时间 大概在 24 小时左右
循环判断 将author 从 tyc_author_3  转到tyc_account_1  
auhtor 和 时间戳 的 分隔符  ^*^
'''

#被封期限
PTERM = 3600*10

redis_client = redis.Redis(host='192.168.1.157',port=6379)
while True:
    if redis_client.llen('tyc_author_3'):
        text = redis_client.rpoplpush('tyc_author_3','tyc_author_3').decode('utf8')
        #分别是13位 10位时间戳
        author,penalty_time = text.split('^*^')
        cur_time = int(time.time())

        author = re.sub(r'###\d+###', '###{}###', author)
        if cur_time-int(penalty_time) > PTERM: #该账号过了被封期限，可以使用
            if author not in redis_client.lrange('tyc_author_1',0,-1):
                redis_client.lpush('tyc_author_1',author)
            redis_client.lrem('tyc_author_3',count=1,value=text)
            print('切换成功',author)
        else:
            print('目前有{}个被封账号'.format(redis_client.llen('tyc_author_3')))
            sleep(0.5)
    else:
        print('队列为空。。。')
        sleep(60*10)