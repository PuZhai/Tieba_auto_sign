from DrissionPage import ChromiumOptions, ChromiumPage
import json
import os
import shutil
import time
import requests

# ========== 配置区 ==========
PAGE_LOAD_TIMEOUT = 2      # 页面加载等待（秒）
ELEMENT_TIMEOUT = 2        # 元素加载等待（秒）
CLICK_WAIT = 1             # 点击后等待（秒）
MAX_PAGES = 20             # 最大获取页数
# ============================

def read_cookie():
    # 本地读取模式
    # cookie_file = "tieba_cookies.json"
    # if os.path.exists(cookie_file):
    #     with open(cookie_file, 'r', encoding='utf-8') as f:
    #         cookies = json.load(f)
    #     print(f"✅ 从本地文件 {cookie_file} 读取到 {len(cookies)} 个 cookie")
    #     return cookies
    # elif "TIEBA_COOKIES" in os.environ:
    #     print("⚠️ 从环境变量读取 cookie")
    #     return json.loads(os.environ["TIEBA_COOKIES"])
    # else:
    #     print("❌ 未找到 cookie！")
    #     return []
    """读取 cookie，优先从环境变量读取"""
    if "TIEBA_COOKIES" in os.environ:
        return json.loads(os.environ["TIEBA_COOKIES"])
    else:
        print("贴吧Cookie未配置！详细请参考教程！")
        return []



def get_level_exp(page):
    """
    获取当前贴吧的等级和经验
    返回: (level, exp)
    """
    level = "未知"
    exp = "未知"
    
    try:
        import re
        html = page.html
        
        # ===== 方法1：从 "我在本吧" 区域提取（如果有） =====
        if "我在本吧" in html:
            my_bar_start = html.find('我在本吧')
            segment = html[my_bar_start:my_bar_start+3000]
            
            level_match = re.search(r'#level_(\d+)', segment)
            if level_match:
                level = f"Lv.{level_match.group(1)}"
            
            tag_match = re.search(r'experience-tag[^>]*>([^<]+)</span>', segment)
            if tag_match and level != "未知":
                tag_name = tag_match.group(1).strip()
                level = f"{level} ({tag_name})"
        
        # ===== 方法2：从整个页面提取（用于没有 "我在本吧" 的情况） =====
        if level == "未知":
            # 找所有 level-icon
            level_icons = page.eles('xpath://svg[contains(@class, "level-icon")]//use')
            for icon in level_icons:
                href = icon.attr("xlink:href") or icon.attr("href") or ""
                match = re.search(r'#level_(\d+)', href)
                if match:
                    # 排除 SVG 定义区域的 level_1 到 level_18
                    level_num = int(match.group(1))
                    if 1 <= level_num <= 18:
                        level = f"Lv.{level_num}"
                        break
            
            # 如果还是没找到，从 HTML 全局搜索
            if level == "未知":
                # 查找用户头像附近的等级（通常显示在帖子列表中）
                level_match = re.search(r'level-icon[^>]*>.*?#level_(\d+)', html)
                if level_match:
                    level = f"Lv.{level_match.group(1)}"
        
        # ===== 获取经验 =====
        exp_ele = page.ele('xpath://div[contains(@class, "progress-text")]')
        if exp_ele:
            exp = exp_ele.text.strip()
        else:
            exp_match = re.search(r'经验\s*([\d/]+)', html)
            if exp_match:
                exp = exp_match.group(1)
            else:
                exp_match2 = re.search(r'(\d+)/(\d+)', html)
                if exp_match2:
                    exp = exp_match2.group(0)
                
    except Exception as e:
        print(f"获取等级经验异常: {e}")
    
    return level, exp

def check_sign_status(page):
    try:
        page_html = page.html
        if "连签" in page_html or "连续签到" in page_html:
            return 'signed'
        sign_elements = page.eles('xpath://*[contains(text(), "签到")]')
        for elem in sign_elements:
            text = elem.text if elem else ""
            if "连签" in text or "连续" in text:
                return 'signed'
            if text.strip() == "签到":
                return 'unsign'
        return 'unknown'
    except Exception as e:
        return 'unknown'

def click_sign_button(page):
    try:
        sign_btn = page.ele('xpath://div[contains(@class, "operate-btn") and text()="签到"]')
        if not sign_btn:
            sign_btn = page.ele('xpath://div[contains(@class, "follow-sign")]')
        if not sign_btn:
            sign_btn = page.ele('xpath://*[text()="签到"]')
        if sign_btn:
            sign_btn.click()
            time.sleep(CLICK_WAIT)
            return True
        return False
    except:
        return False

def get_all_tieba_list(page):
    """
    获取所有关注的贴吧列表
    返回: [(url, name), ...]
    """
    tieba_list = []
    page_num = 0
    
    print("📖 开始获取贴吧列表...")
    
    while True:
        page_num += 1
        
        if page_num > MAX_PAGES:
            print(f"📄 已获取 {MAX_PAGES} 页，停止")
            break
        
        print(f"  📄 正在获取第 {page_num} 页...")
        page.get(f"https://tieba.baidu.com/i/i/forum?&pn={page_num}")
        page._wait_loaded(PAGE_LOAD_TIMEOUT)
        
        # 检测验证码
        if "验证" in page.html or "安全" in page.html:
            print("  ⚠️ 检测到验证码页面，暂停 30 秒后重试...")
            time.sleep(30)
            continue
        
        # 获取当前页的贴吧
        for i in range(2, 22):
            try:
                element = page.ele(
                    f'xpath://*[@id="like_pagelet"]/div[1]/div[1]/table/tbody/tr[{i}]/td[1]/a/@href'
                )
                if element:
                    tieba_url = element.attr("href")
                    name = element.attr("title")
                    if tieba_url and name:
                        if not tieba_url.startswith('http'):
                            tieba_url = 'https://tieba.baidu.com' + tieba_url
                        tieba_list.append((tieba_url, name))
            except:
                break
        
        # 检查是否有下一页
        try:
            next_btn = page.ele('xpath://*[contains(text(), "下一页")]')
            if not next_btn:
                print(f"  📄 没有下一页了，结束获取")
                break
        except:
            break
    
    print(f"📊 共获取 {len(tieba_list)} 个贴吧")
    return tieba_list


if __name__ == "__main__":
    print("🚀 程序开始运行")
    notice = ''

    # 配置浏览器（暂时关闭无头模式方便调试）
    # co = ChromiumOptions()
    co = ChromiumOptions().headless()
    chromium_path = shutil.which("chromium-browser")
    if chromium_path:
        co.set_browser_path(chromium_path)
    else:
        print("⚠️ 未找到 chromium-browser，将使用默认浏览器")

    page = ChromiumPage(co)

    print("📡 正在访问百度贴吧...")
    url = "https://tieba.baidu.com/"
    page.get(url)
    
    cookies = read_cookie()
    if cookies:
        page.set.cookies(cookies)
        print("✅ Cookie 设置成功")
    else:
        print("❌ Cookie 设置失败，程序退出")
        try:
            page.close()
        except:
            pass
        exit(1)

    # ===== 第一步：获取全部贴吧列表 =====
    tieba_list = get_all_tieba_list(page)
    
    if not tieba_list:
        print("❌ 没有获取到任何贴吧，请检查 Cookie 是否有效")
        try:
            page.close()
        except:
            pass
        exit(1)
    
    print(f"📊 共找到 {len(tieba_list)} 个关注的贴吧")
    print("🚀 开始签到...")
    print("-" * 50)

    # ===== 第二步：循环签到 =====
    signed_count = 0
    failed_count = 0
    total = len(tieba_list)
    
    for idx, (tieba_url, name) in enumerate(tieba_list, 1):
        try:
            print(f"📍 [{idx}/{total}] 正在处理：{name}吧")
            page.get(tieba_url)
            page._wait_loaded(PAGE_LOAD_TIMEOUT)
            
            # 等待签到相关元素出现
            try:
                page.wait.eles_loaded(
                    'xpath://*[contains(text(), "签到") or contains(text(), "连签")]', 
                    timeout=ELEMENT_TIMEOUT
                )
            except:
                pass

            # 检查签到状态
            status = check_sign_status(page)
            
            if status == 'signed':
                level, exp = get_level_exp(page)
                msg = f"✅ {name}吧：已签到过！等级：{level}，经验：{exp}"
                print(msg)
                notice += msg + '\n\n'
                signed_count += 1
                
            elif status == 'unsign':
                print(f"🔄 {name}吧：尝试签到...")
                if click_sign_button(page):
                    time.sleep(CLICK_WAIT)
                    page.refresh()
                    page._wait_loaded(PAGE_LOAD_TIMEOUT)
                    
                    new_status = check_sign_status(page)
                    if new_status == 'signed':
                        level, exp = get_level_exp(page)
                        msg = f"🎉 {name}吧：签到成功！等级：{level}，经验：{exp}"
                        print(msg)
                        notice += msg + '\n\n'
                        signed_count += 1
                    else:
                        msg = f"❌ {name}吧：点击后仍未签到成功"
                        print(msg)
                        notice += msg + '\n\n'
                        failed_count += 1
                else:
                    msg = f"❌ {name}吧：找不到签到按钮"
                    print(msg)
                    notice += msg + '\n\n'
                    failed_count += 1
                    
            else:
                # 兜底判断
                if "连签" in page.html or "连续签到" in page.html:
                    level, exp = get_level_exp(page)
                    msg = f"✅ {name}吧：已签到过！等级：{level}，经验：{exp}"
                    print(msg)
                    notice += msg + '\n\n'
                    signed_count += 1
                else:
                    msg = f"⚠️ {name}吧：无法判断签到状态，跳过"
                    print(msg)
                    notice += msg + '\n\n'
                    failed_count += 1

            print("-" * 50)
            
        except Exception as e:
            msg = f"❌ {name}吧：签到异常 - {str(e)}"
            print(msg)
            notice += msg + '\n\n'
            failed_count += 1
            print("-" * 50)

    # ===== 第三步：发送通知 =====
    print("\n" + "=" * 50)
    print(f"📊 签到完成！")
    print(f"   ✅ 成功：{signed_count} 个")
    print(f"   ❌ 失败：{failed_count} 个")
    print(f"   📊 总计：{total} 个")
    print("=" * 50)


    send_key = os.environ["SendKey"]
    
    if send_key:
        api = f'https://sc.ftqq.com/{send_key}.send'
        title = "📢 贴吧签到信息"
        summary = f"签到成功 {signed_count} 个，失败 {failed_count} 个，共 {total} 个"
        data = {
            "text": title,
            "desp": f"## {summary}\n\n{notice}"
        }
        try:
            req = requests.post(api, data=data, timeout=60)
            if req.status_code == 200:
                print("✅ Server酱通知发送成功")
            else:
                print(f"❌ 通知失败，状态码：{req.status_code}")
        except Exception as e:
            print(f"❌ 通知发送异常：{e}")
    else:
        print("ℹ️ 未配置 SendKey，跳过通知发送")

    try:
        page.close()
    except:
        pass