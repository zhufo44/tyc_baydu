# -*- coding:utf-8 -*-
import re
import pika
import math
import requests
import datetime
from hashlib import md5
from function import *
from judicial_sale import getcontent

# 用于所有 get 请求
def get(url):
    """
    函数返回 五种结果
    1. 正确的数据
    2. searchNone 表示在天眼查搜索不到该公司
    3. fieldError 表示--请求到 不存在数据的接口（由于天眼查统计出错）。程序跳过当前接口，接着往下执行
    4. requestError 表示 由于异常导致该公司爬取失败，公司重新放入队列
    """
    global proxy,headers,author,reqcount
    while True:
        try:
            res = sess.get(url,headers=headers,timeout=10,proxies=proxy)
            str_res = res.content.decode('utf8')
            print(str_res)

            # str格式 判断response
            if re.findall(r'Apache Tomcat',str_res):
                return 'searchNone'
            if re.findall(r'Authorization',str_res) and not re.findall('state',str_res):
                # 账号达到请求上限，把当前token封禁24小时，24小时后重新放入队列
                print('{}：请求上限'.format(author))
                author = switch_author(author)
                headers['Authorization'] = author
                reqcount = 0
                continue
            if re.findall(r'404 Not Found',str_res):
                return 'requestError'

            # json格式 判断response
            res = res.json()
            if res['message'] == 'must login':
                # token失效，获取新的token
                print('{}：账号token失效')
                reqcount = 0
                author = invalid_token(author)
                headers['Authorization'] = author
                continue
            if res['message'] == '系统异常':#再次访问可以
                return 'requestError'
            if res['message'] == '无数据':  #不存在数据
                return 'fieldError'
            if res['state'] == 'ok':
                break
            else:
                sess.close()
                proxy = getip()

        except Exception as e:
            print('get请求出错',e)
            sess.close()
            proxy = getip()

    return res


# orgid -- 组织机构代码
def spider(orgid):
    global proxy,ipcount,reqcount,headers,author
    ipcount+=1
    reqcount +=1
    # 文档存储
    doclist = {}

    print('已经请求',reqcount)
    #切换author，每次切换账号 reqcount 都要重置为0
    if reqcount>1500:
        author  = switch_author(author)
        headers['Authorization'] = author
        reqcount = 0
    # 每个ip使用20次
    if ipcount>20:
        sess.close()
        proxy = getip()
        ipcount = 0


    # 搜索 =============================================================================================================
    url = 'https://api9.tianyancha.com/services/v3/search/sNorV3/{}?pageNum=1&pageSize=10&sortType=0'.format(orgid)
    res = get(url)
    print('搜索',res)

    # 每次使用 get函数后 都需要判断 返回结果
    if res == 'requestError':
        return 'requestError'
    if res=='searchNone' or res['data']=={} or res['data']['companyList']==[]:
        return 'searchNone'
    # 在搜索返回中 存在经纬度信息 （可能还有其他有用的信息）
    doclist['search_res'] = res['data']['companyList']

    # 公司匹配 -- 结果唯一匹配（要么没有，要么就是）
    # 得到一些参数 用于后面的 请求和判断
    searchdata = res['data']['companyList'][0]
    search_id = str(searchdata['id'])
    search_name = searchdata['name']
    enttype = searchdata['companyOrgType']

    # 工商信息 股东信息 主要人员 变更记录 分支机构 <<<------ 该接口返回这些数据
    url = 'https://api9.tianyancha.com/services/v3/t/details/appComIcV4/{}?pageSize=1000'.format(search_id)
    res = get(url)
    if res == 'requestError' or res == 'searchNone':
        return res
    print('工商信息', res)
    doclist['baseinfo'] = res['data']

    # 得到每个字段的数量================================================================================================
    url = 'https://api9.tianyancha.com/services/v3/expanse/allCountV3?id='+search_id
    res = get(url)
    print('字段统计',res)
    if res == 'requestError' or res == 'searchNone':
        return res
    fieldcount = res['data']
    doclist['fieldcount'] = fieldcount

    anninfo = []
    # 企业年报==========================================================================================================
    if fieldcount.get('reportCount'):
        if int(fieldcount['reportCount']):
            # 获取所有年报链接
            url = 'https://api9.tianyancha.com/services/v3/expanse/annu?id={}&pageNum=1&pageSize=20'.format(search_id)
            res = get(url)
            print('年报',res)

            for item in res['data']:
                # 获取每一份年报
                url = 'https://api9.tianyancha.com/services/v3/ar/anre/'+str(item['id'])
                annres = get(url)
                print(annres['data']['baseInfo']['reportYear'],annres)
                anninfo.append(annres)
    doclist['anninfo'] = anninfo


    shixin = []
    # 失信信息==========================================================================================================
    if fieldcount.get('dishonest'):
        if int(fieldcount['dishonest']):
            page = 1
            while True:
                url = 'https://api9.tianyancha.com/services/v3/t/dishonest/app?keyWords={}&pageNum={}&pageSize=20'.format(search_name, page)
                res = get(url)
                if res == 'fieldError':
                    break
                print('失信信息%d' % page, res)
                shixin += res['data']['items']

                total = int(res['data']['total'])
                pages = math.ceil(total / 20)
                if page == pages:
                    break
                page += 1
    doclist['shixin'] = shixin

    zhixing = []
    # 被执行人==========================================================================================================
    if fieldcount.get('zhixing'):
        if int(fieldcount['zhixing']):
            page = 1
            while True:
                url = 'https://api9.tianyancha.com/services/v3/ar/zhixing?id={}&pageNum={}&pageSize=20'.format(search_id,page)
                res = get(url)
                if res == 'fieldError':
                    break
                print('被执行人%d' % page, res)
                zhixing += res['data']['items']

                total = int(res['data']['count'])
                pages = math.ceil(total / 20)
                if page == pages:
                    break
                page += 1
    doclist['zhixing'] = zhixing

    assist = []
    # 司法协助==========================================================================================================
    if fieldcount.get('judicialaAidCount'):
        if int(fieldcount['judicialaAidCount']):
            page = 1
            while True:
                url = 'https://api9.tianyancha.com/services/v3/aboutCompany/getJudicialList?cId={}&pageSize=20&pageNum={}'.format(search_id, page)
                res = get(url)
                print('司法协助%d' % page, res)
                if res == 'fieldError':
                    break
                for item in res['data']['list']:
                    info = {}
                    assId = item['assId']
                    suburl = 'https://api9.tianyancha.com/services/v3/aboutCompany/getJudicialDetail?assId={}'.format(assId)
                    detailres = get(suburl)
                    print('司法协助详情', detailres)
                    info['head'] = item
                    info['detail'] = detailres['data']
                    assist.append(info)
                total = int(res['data']['totalCount'])
                pages = math.ceil(total / 20)
                if page == pages:
                    break
                page += 1
    doclist['assist'] = assist

    # 行政处罚========数据分为工商数据和信用中国数据======================================================================
    gspunish = []
    if fieldcount.get('punishment'):
        if int(fieldcount['punishment']):
            page = 1
            while True:
                url = 'https://api9.tianyancha.com/services/v3/ar/punishment?name={}&pageNum={}&pageSize=20'.format(search_name, page)
                res = get(url)
                if res == 'fieldError':
                    break
                print('工商行政处罚%d' % page, res)
                gspunish += res['data']['items']

                total = int(res['data']['count'])
                pages = math.ceil(total / 20)
                if page == pages:
                    break
                page += 1
    doclist['gspunish'] = gspunish

    xypunish = []
    # 信用中国
    if fieldcount.get('punishmentCreditchina'):
        if int(fieldcount['punishmentCreditchina']):
            page = 1
            while True:
                url = 'https://api9.tianyancha.com/services/v3/aboutCompany/getCreditChina?cId={}&pageNum={}&pageSize=20'.format(search_id, page)
                res = get(url)
                if res == 'fieldError':
                    break
                print('信用中国行政处罚%d' % page, res)
                xypunish += res['data']['list']

                total = int(res['data']['totalCount'])
                pages = math.ceil(total / 20)
                if page == pages:
                    break
                page += 1
    doclist['xypunish'] = xypunish

    illegal = []
    # 严重违法==========================================================================================================
    if fieldcount.get('illegalCount'):
        if int(fieldcount['illegalCount']):
            page = 1
            while True:
                url = 'https://api9.tianyancha.com/services/v3/ar/Illegal?name={}&pageNum={}&pageSize=20'.format(search_name,page)
                res = get(url)
                if res == 'fieldError':
                    break
                print('严重违法%d' % page, res)
                illegal += res['data']['items']

                total = int(res['data']['count'])
                pages = math.ceil(total / 20)
                if page == pages:
                    break
                page += 1
    doclist['illegal'] = illegal

    pledge = []
    # 股权出质==========================================================================================================
    if fieldcount.get('equityCount'):
        if int(fieldcount['equityCount']):
            page = 1
            while True:
                url = 'https://api9.tianyancha.com/services/v3/ar/companyEquity?name={}&pageNum={}&pageSize=20'.format(search_name, page)
                res = get(url)
                if res == 'fieldError':
                    break
                print('股权出质%d' % page, res)
                pledge += res['data']['items']

                total = int(res['data']['count'])
                pages = math.ceil(total / 20)
                if page == pages:
                    break
                page += 1
    doclist['pledge'] = pledge

    mortage = []
    # 动产抵押==========================================================================================================
    if fieldcount.get('mortgageCount'):
        if int(fieldcount['mortgageCount']):
            page = 1
            while True:
                url = 'https://api9.tianyancha.com/services/v3/ar/companyMortgageV2?name={}&pageNum={}&pageSize=20'.format(search_name, page)
                res = get(url)
                if res == 'fieldError':
                    break
                print('动产抵押%d' % page, res)
                mortage += res['data']['items']

                total = int(res['data']['count'])
                pages = math.ceil(total / 20)
                if page == pages:
                    break
                page += 1
    doclist['mortage'] = mortage

    owntax = []
    # 欠税公告==========================================================================================================
    if fieldcount['ownTaxCount']:
        if int(fieldcount['ownTaxCount']):
            page = 1
            while True:
                url = 'https://api9.tianyancha.com/services/v3/ar/companyowntax?pageNum={}&id={}&pageSize=20'.format(page,search_id)
                res = get(url)
                if res == 'fieldError':
                    break
                print('欠税公告%d' % page, res)
                owntax += res['data']['items']

                total = int(res['data']['count'])
                pages = math.ceil(total / 20)
                if page == pages:
                    break
                page += 1
    doclist['owntax'] = owntax

    abnormal = []
    # 经营异常==========================================================================================================
    if fieldcount.get('abnormalCount'):
        if int(fieldcount['abnormalCount']):
            page = 1
            while True:
                url = 'https://api9.tianyancha.com/services/v3/expanse/abnormal?id={}&pageNum={}&pageSize=20'.format(search_id, page)
                res = get(url)
                if res == 'fieldError':
                    break
                print('经营异常%d' % page, res)
                abnormal += res['data']['result']

                total = int(res['data']['total'])
                pages = math.ceil(total / 20)
                if page == pages:
                    break
                page += 1
    doclist['abnormal'] = abnormal

    # 司法拍卖==========================================================================================================
    # 数据较大 一篇文档放不下 ，爬取一条，存储一条
    if fieldcount.get('judicialSaleCount'):
        if int(fieldcount['judicialSaleCount']):
            page = 1
            while True:
                url = 'https://api9.tianyancha.com/services/v3/expanse/judicialSale?pageNum={}&id={}&pageSize=20'.format(page, search_id)
                res = get(url)
                if res == 'fieldError' or res == 'requestError':
                    break
                print('司法拍卖%d' % page, res)
                for item in res['data']['resultList']:
                    info = {}
                    purl = item['url']
                    print(purl)
                    content = getcontent(purl)

                    info['head'] = item
                    info['text'] = content
                    print('详细信息', info)
                    # 避免公司的重复爬取出现的数据重复
                    mongoId = md5((orgid + purl).encode('utf8')).hexdigest()
                    mongo170.new_tyc_bd.paimai.save({'_id': mongoId, 'orgid': orgid, 'data': info})

                total = int(res['data']['count'])
                pages = math.ceil(total / 20)
                if page == pages:
                    break
                page += 1

    liquid = []
    # 清算信息==========================================================================================================
    if fieldcount.get('clearingCount'):
        if int(fieldcount['clearingCount']):
            url = 'https://api9.tianyancha.com/services/v3/aboutCompany/getLiquidating?cId={}'.format(search_id)
            res = get(url)
            print('清算信息', res)
            liquid = res['data']
    doclist['liquid'] = liquid

    intellect = []
    # 知识产权出质登记==================================================================================================
    if fieldcount.get('intellectualProperty'):
        if int(fieldcount['intellectualProperty']):
            page = 1
            while True:
                url = 'https://api9.tianyancha.com/services/v3/aboutCompany/getPledgeReg?cId={}&pageNum={}&pageSize=10'.format(search_id, page)
                res = get(url)
                if res == 'fieldError':
                    break
                print('知识产权出质登记%d' % page, res)
                intellect += res['data']['list']

                total = int(res['data']['totalCount'])
                pages = math.ceil(total / 10)
                if page == pages:
                    break
                page += 1
    doclist['intellect'] = intellect


    # 行政许可===数据分为：信用中国 工商数据============================================================================
    # 工商行政许可
    gslicense = []
    if fieldcount.get('licenseCount'):
        if int(fieldcount['licenseCount']):
            page = 1
            while True:
                url = 'https://api9.tianyancha.com/services/v3/aboutCompany/getLicense?cId={}&pageNum={}&pageSize=20'.format(search_id,page)
                res = get(url)
                if res == 'fieldError':
                    break
                print('工商行政许可%d'%page,res)
                gslicense+=res['data']['list']

                total = int(res['data']['totalCount'])
                pages = math.ceil(total / 20)
                if page == pages:
                    break
                page += 1
    doclist['gslicense'] = gslicense

    xylicense = []
    # 信用中国
    if fieldcount.get('licenseCreditchina'):
        if int(fieldcount['licenseCreditchina']):
            page = 1
            while True:
                url = 'https://api9.tianyancha.com/services/v3/aboutCompany/getLicenseCreditchina?cId={}&pageNum={}&pageSize=20'.format(search_id,page)
                res = get(url)
                if res == 'fieldError' or res == 'requestError':
                    break
                print('信用中国行政许可%d'%page,res)
                xylicense += res['data']['list']

                total = int(res['data']['totalCount'])
                pages = math.ceil(total / 20)
                if page == pages:
                    break
                page += 1
    doclist['xylicense'] =xylicense

    taxrating = []
    # 税务评级==========================================================================================================
    if fieldcount.get('taxCreditCount'):
        if int(fieldcount['taxCreditCount']):
            page = 1
            while True:
                url = 'https://api9.tianyancha.com/services/v3/ar/taxcred?id={}&pageNum={}&pageSize=20'.format(search_id, page)
                res = get(url)
                if res == 'fieldError':
                    break
                print('税务评级%d'%page, res)
                taxrating += res['data']['items']

                total = int(res['data']['count'])
                pages = math.ceil(total / 20)
                if page == pages:
                    break
                page += 1
    doclist['taxrating'] = taxrating

    checkspot = []
    # 抽查检查==========================================================================================================
    if fieldcount.get('checkCount'):
        if int(fieldcount['checkCount']):
            page = 1
            while True:
                url = 'https://api9.tianyancha.com/services/v3/ar/checkInfoList?name={}&pageNum={}&pageSize=20'.format(search_name, page)
                res = get(url)
                if res == 'fieldError':
                    break
                print('抽查检查%d'%page, res)
                checkspot += res['data']['items']

                total = int(res['data']['count'])
                pages = math.ceil(total / 20)
                if page == pages:
                    break
                page += 1
    doclist['checkspot'] = checkspot

    certificate = []
    # 资质证书==========================================================================================================
    if fieldcount.get('certificateCount'):
        if int(fieldcount['certificateCount']):
            page = 1
            while True:
                url = 'https://api9.tianyancha.com/services/v3/expanse/certificate?id={}&pageNum={}&pageSize=20'.format(search_id,page)
                res = get(url)
                if res == 'fieldError':
                    break
                print('资质证书%d'%page,res)

                # 详情请求
                for item in res['data']['resultList']:
                    info = {}
                    pid = item['id']
                    url = 'https://api9.tianyancha.com/services/v3/expanse/certificateDetail?id={}'.format(pid)
                    detailres = get(url)
                    info['head'] = item
                    info['content'] = detailres['data']['detail']
                    certificate.append(info)

                total = int(res['data']['count'])
                pages = math.ceil(total / 20)
                if page == pages:
                    break
                page += 1
    doclist['certificate'] = certificate

    wechat = []
    # 微信公众号========================================================================================================
    if fieldcount.get('weChatCount'):
        if int(fieldcount['weChatCount']):
            page = 1
            while True:
                url = 'https://api9.tianyancha.com/services/v3/expanse/publicWeChat?id={}&pageSize=10&pageNum={}'.format(search_id, page)
                res = get(url)
                if res == 'fieldError':
                    break
                print('微信公众号%d'%page, res)
                wechat += res['data']['resultList']

                total = int(res['data']['count'])
                pages = math.ceil(total / 10)
                if page == pages:
                    break
                page += 1
    doclist['wechat'] = wechat

    import_and_export = []
    # 进出口信用========================================================================================================
    if fieldcount.get('importAndExportCount'):
        if int(fieldcount['importAndExportCount']):
            page = 1
            while True:
                url = 'https://api9.tianyancha.com/services/v3/expanse/importAndExport?id={}'.format(search_id)
                res = get(url)
                if res == 'fieldError':
                    break
                print('进出口信用', res)
                import_and_export = res['data']
                break
    doclist['import_and_export'] = import_and_export

    bondinfo = []
    # 债券信息==========================================================================================================
    # 铜陵市建设投资控股有限责任公司
    if fieldcount.get('bondCount'):
        if int(fieldcount['bondCount']):
            page = 1
            while True:
                url = 'https://api9.tianyancha.com/services/v3/cSearch/bond?keyword={}&pageSize=10&pageNum={}'.format(search_name, page)
                res = get(url)
                if res == 'fieldError':
                    break
                print('债券信息%d'%page, res)
                bondinfo += res['data']['items']

                total = int(res['data']['total'])
                pages = math.ceil(total / 10)
                if page == pages:
                    break
                page += 1
    doclist['bondinfo'] = bondinfo


    purchaseland = []
    # 购地信息==========================================================================================================
    if fieldcount.get('goudiCountV2'):
        if int(fieldcount['goudiCountV2']):
            page = 1
            while True:
                url = 'https://api9.tianyancha.com/services/v3/e/comPurchaseLand/purchaseLandV2?name={}&pageNum={}&pageSize=10'.format(search_name, page)
                res = get(url)
                if res == 'fieldError':
                    break
                print('购地信息%d'%page, res)
                purchaseland += res['data']['companyPurchaseLandList']

                total = int(res['data']['totalRows'])
                pages = math.ceil(total / 10)
                if page == pages:
                    break
                page += 1
    doclist['purchaseland'] = purchaseland

    # 商标信息==========================================================================================================
    if fieldcount.get('tmCount'):
        if int(fieldcount['tmCount']):
            page = 1
            while True:
                url = 'https://api9.tianyancha.com/services/v3/cSearch/trademark?keyword={}&pageNum={}&pageSize=20'.format(search_name, page)
                res = get(url)
                if res == 'fieldError':
                    break
                print('商标%d' % page, res)

                for item in res['data']['items']:
                    info = {}
                    regno = item['regNo']
                    tmclass = item['intCls']
                    url = 'https://api9.tianyancha.com/services/v3/trademark/detail?regNo={}&tmClass={}'.format(regno,tmclass)

                    tmdata = get(url)
                    imurl = tmdata['data']['detail']['tmPic']
                    mongoId = re.findall(r'tm/(.*?)\.jpg', imurl)
                    if mongoId:
                        info['head'] = item
                        info['detail'] = tmdata['data']
                        mongoId = mongoId[0]
                        mongo170.new_tyc_bd.shangbiao.save({'_id': mongoId, 'orgid': orgid, 'data': info})
                    else:
                        print('图片没有url')
                        raise ValueError
                    print(tmdata)

                total = int(res['data']['total'])
                pages = math.ceil(total / 20)
                if page == pages:
                    break
                page += 1

    # 专利信息=========================================================================================================
    if fieldcount.get('patentCount'):
        if int(fieldcount['patentCount']):
            page = 1
            while True:
                url = 'https://api9.tianyancha.com/services/v3/expanse/patent?id={}&pageSize=10&pageNum={}'.format(search_id,page)
                res = get(url)
                if res == 'fieldError':
                    break
                print('专利%d' % page, res)

                # 存储一个列表的数据
                info = res['data']['items']
                mongoId = md5((orgid+'^'+str(page)).encode('utf8')).hexdigest()
                mongo170.new_tyc_bd.patent.save({'_id':mongoId,'orgid': orgid, 'data': info})
                total = res['data']['viewtotal']
                pages = int(math.ceil(total / 10))
                if page == pages:
                    break
                page += 1

    # 著作权========分为 软件著作权 和 作品著作权========================================================================
    # 作品著作权
    works = []
    if fieldcount.get('copyrightWorks'):
        if int(fieldcount['copyrightWorks']):
            page = 1
            while True:
                url = 'https://api9.tianyancha.com/services/v3/expanse/copyrightWorks?id={}&pageSize=10&pageNum={}'.format(search_id, page)
                res = get(url)
                if res == 'fieldError':
                    break
                print('作品著作权%d' % page, res)

                works.append(res)
                total = int(res['data']['count'])
                pages = int(math.ceil(total / 10))
                if page == pages:
                    break
                page += 1
    doclist['works'] = works


    # 软件著作权
    software = []
    if fieldcount.get('cpoyRCount'):
        if int(fieldcount['cpoyRCount']):
            page = 1
            while True:
                url = 'https://api9.tianyancha.com/services/v3/expanse/copyReg?id={}&pageSize=10&pageNum={}'.format(search_id, page)
                res = get(url)
                if res == 'fieldError':
                    break
                print('软件著作权%d' % page, res)

                software.append(res)
                total = int(res['data']['viewtotal'])
                pages = int(math.ceil(total / 10))
                if page == pages:
                    break
                page += 1
    doclist['software'] = software

    icps = []
    # 网站备案==========================================================================================================
    if fieldcount.get('icpCount'):
        if int(fieldcount['icpCount']):
            page = 1
            while True:
                url = 'https://api9.tianyancha.com/services/v3/cSearch/icp?keyword={}&pageNum={}&pageSize=20'.format(search_name, page)
                res = get(url)
                if res == 'fieldError':
                    break
                print('网站备案%d' % page, res)
                icps.append(res['data']['items'])

                total = int(res['data']['total'])
                pages = int(math.ceil(total / 20))
                if page == pages:
                    break
                page += 1
    doclist['icps'] = icps


    # 数据存储 --------- 商标，专利，司法拍卖，数据偏大，已在上面处理（爬取一篇存储一篇）
    nowtime = datetime.datetime.now()
    nowtime = nowtime.strftime('%Y-%m-%d')
    mongo170.new_tyc_bd[nowtime].update({'_id':orgid},{'$set':doclist},True)

if __name__ == '__main__':
    # 控制IP使用次数
    ipcount = 0
    reqcount = 0
    headers = {
        'version': 'TYC-XCX-BD',
        'content-type': 'application/json',
        'Host': 'api9.tianyancha.com',
        'Connection': 'Keep-Alive',
        'Accept-Encoding': 'gzip',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0.1; HTC M8St Build/MMB29M; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/63.0.3239.83 Mobile Safari/537.36 T7/11.0 swan/1.6 baiduboxapp/11.0.5.12 (Baidu; P1 6.0.1)',
    }
    # 初始化
    author = get_author()
    headers['Authorization'] = author

    sess = requests.Session()
    proxy = getip()
    mongo170 = conMongo()

    # rabbit 调度 ====================================================================================================
    queue = 'tjc_fj_orgid'
    credentials = pika.PlainCredentials('guest', 'guest')
    connection = pika.BlockingConnection(pika.ConnectionParameters('192.168.1.157', 5672, '/', credentials, heartbeat=65530))
    channel = connection.channel()
    channel.queue_declare(queue=queue, durable=True)

    def callback(ch, method, properties, body):
        orgid = body.decode('utf-8')
        print('查询信息：', orgid)


        check = spider(orgid)

        if check == 'searchNone':
            # 搜索不到 记录在
            mongo170.new_tyc_bd.search_none.update({'orgid':orgid},{'orgid':orgid},True)
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return
        elif check == 'requestError':
            ch.basic_nack(delivery_tag=method.delivery_tag)
            return
        else:
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

    # 公平调度
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(on_message_callback=callback,queue=queue)
    channel.start_consuming()
