# coding:utf8
import uiautomator2 as u2
from time import sleep
import redis


# 点击小程序 获取token
def get_token():
    d(resourceId="com.baidu.searchbox:id/person_center_item_icon").click()
    sleep(3)
    d.click(0.212, 0.276)  # 打开搜索框
    input('调整输入法')
    while True:
        if d(className="android.widget.EditText").exists:
            d(className="android.widget.EditText").set_text('哈哈')
            break

    # 搜索
    d.click(0.919, 0.893)
    # 等待搜索结果
    sleep(5)
    # 关闭小程序
    d(resourceId="com.baidu.searchbox:id/titlebar_right_menu_exit").click()


# 退出登陆
def login_out():
    sleep(1)
    d(scrollable=True).fling.toEnd()
    d(className="android.widget.RelativeLayout", instance=23).click()  # 进入设置
    sleep(0.5)
    d(scrollable=True).fling.toEnd()
    d(className="android.widget.RelativeLayout", instance=13).click()  # 退出登录
    d(text="退出登录").wait(timeout=3.0)
    d(resourceId="com.baidu.searchbox:id/positive_button").click()  # 确认退出
    sleep(0.5)

    d(scrollable=True).fling.vert.backward()
    # d.app_stop("com.baidu.searchbox")


def main(bname,bpwd):
    # d.app_start("com.baidu.searchbox")
    # while 1:
    #     if d(resourceId="com.baidu.searchbox:id/home_tab_item_textview", text=u"未登录").exists:
    #         d(resourceId="com.baidu.searchbox:id/home_tab_item_textview", text=u"未登录").click()
    #         break  # 个人中心（未登录状态）

    # 短信登录
    d(resourceId="com.baidu.searchbox:id/a8l").click()

    # 登陆其他账号
    sleep(5)
    d(description="登录其他帐号").click()

    # 输入用户名
    # d.click(0.443, 0.46)
    d.xpath('//*[@content-desc="登录百度帐号"]/android.view.View[1]/android.view.View[2]/android.view.View[1]/android.view.View[1]') \
        .set_text(bname)
    # d.click(0.909, 0.536)
    d(description="下一步").click()

    # 选择账号密码登陆
    sleep(1)
    d(description="帐号密码登录")

    # 输入密码
    sleep(1)
    d.xpath('//*[@content-desc="登录百度帐号"]/android.view.View[1]/android.view.View[2]/android.view.View[1]/android.view.View[2]/android.widget.EditText[1]') \
        .set_text(bpwd)
    d(resourceId="com.android.systemui:id/back").click()

    # 点击登陆
    d.click(0.478, 0.693)

    # 发送邮箱验证
    # 获取验证码
    messcode = str(input('请输入验证码：'))
    for string in messcode:
        sleep(0.1)
        if string == '0':
            d.click(0.5, 0.808)
        elif string == '1':
            d.click(0.198, 0.563)
        elif string == '2':
            d.click(0.492, 0.559)
        elif string == '3':
            d.click(0.812, 0.567)
        elif string == '4':
            d.click(0.166, 0.663)
        elif string == '5':
            d.click(0.503, 0.635)
        elif string == '6':
            d.click(0.822, 0.655)
        elif string == '7':
            d.click(0.163, 0.721)
        elif string == '8':
            d.click(0.51, 0.727)
        elif string == '9':
            d.click(0.833, 0.733)

        d(description=string).click()

    # 等待 跳转
    while True:
        if d(resourceId="com.baidu.searchbox:id/person_center_item_icon").exists():
            break

    # 获取token
    get_token()

    # 退出登陆
    login_out()


if __name__ == '__main__':
    d = u2.connect('192.168.1.162')
    redis_client = redis.Redis(host='192.168.1.157',port=6379)

    alist = redis_client.lrange('syy_baidu_email_account',0,-1)
    count = 0
    for text in alist[173:-49]:
        count+=1
        text = text.decode('utf8')
        print(count,text)
        bname,bpwd,ename,epwd = text.split('^')

        main(bname,bpwd)


