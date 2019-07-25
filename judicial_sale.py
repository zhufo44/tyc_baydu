from function import getip
import requests
import re
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

'''
司法拍卖详情请求脚本
'''
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/72.0.3626.121 Safari/537.36',
}
sess = requests.Session()
proxy = getip()

def getcontent(url):
    global proxy
    while True:
        try:
            res = sess.get(url,headers=headers,proxies=proxy,timeout=5,verify=False).text
            content = re.findall('<div class="notice-content">(.*?)</div>', res.replace('\n', ''))[0]
            content = content.replace(' ', '').replace(r'	', '').replace(r'\t', '')
            break
        except Exception as e:
            print('详情出错',e)
            sess.close()
            proxy = getip()
    return content