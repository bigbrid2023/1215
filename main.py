import os
import time
import base64
import re
import socket
from urllib.parse import unquote, urlparse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from github import Github

# --- 配置 ---
GITHUB_TOKEN = os.getenv("MY_GITHUB_TOKEN")
REPO_NAME = "bigbrid2023/1215"
FILE_PATH = "sub_base64.txt"
# 目标订阅地址
TARGET_URL = "https://openproxylist.com/v2ray/rawlist/subscribe"

def get_raw_content():
    """
    使用 Selenium 获取订阅源的原始内容 (防止 Cloudflare 拦截简单的 Python 请求)
    """
    print(">>> 正在启动浏览器获取订阅源...")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    # 伪装 User-Agent
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    content = ""
    try:
        print(f">>> 访问 URL: {TARGET_URL}")
        driver.get(TARGET_URL)
        
        # 订阅页面通常直接显示文本，都在 body 标签里
        content = driver.find_element("tag name", "body").text
        print(f">>> 成功获取内容，长度: {len(content)}")
        
    except Exception as e:
        print(f"!!! 获取订阅源失败: {e}")
    finally:
        driver.quit()
        
    return content

def decode_subscription(content):
    """
    将 Base64 编码的订阅内容解码为明文链接列表
    """
    try:
        # 清理空格
        content = content.strip()
        # Base64 解码 (处理可能缺少的 padding)
        missing_padding = len(content) % 4
        if missing_padding:
            content += '=' * (4 - missing_padding)
            
        decoded_bytes = base64.b64decode(content)
        decoded_str = decoded_bytes.decode('utf-8', errors='ignore')
        
        # 按行分割
        links = decoded_str.splitlines()
        print(f">>> Base64 解码成功，共解析出 {len(links)} 个节点")
        return links
    except Exception as e:
        print(f"!!! 解码失败 (可能内容不是Base64，尝试直接按行分割): {e}")
        return content.splitlines()

def tcp_ping(host, port, timeout=1.5):
    """
    检测 TCP 连接延迟 (真连接测试)
    返回: 延迟(ms)，如果超时或失败返回 9999
    """
    try:
        start_time = time.time()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, int(port)))
        sock.close()
        end_time = time.time()
        return (end_time - start_time) * 1000  # 转换为毫秒
    except:
        return 9999

def parse_and_filter(links):
    """
    解析 vless 链接，筛选美国节点，并进行测速
    """
    us_nodes = []
    
    print(">>> 开始筛选美国节点并测速 (这可能需要几分钟)...")
    
    for link in links:
        link = link.strip()
        if not link.startswith("vless://"):
            continue
            
        # 1. 筛选国家 (检查备注)
        # 备注通常在 # 后面
        remark = ""
        if "#" in link:
            remark = link.split("#")[-1]
            try:
                remark = unquote(remark)
            except:
                pass
        
        # 关键词匹配：United States, US, USA
        # 如果备注里没有国家信息，这个脚本目前会跳过它（为了准确性）
        if not any(kw in remark.upper() for kw in ["UNITED STATES", "UNITEDSTATES", "USA", "AMERICA", " US "]):
            # 某些节点可能写的是 [US] 或者 US_
            if not re.search(r'[^a-zA-Z]US[^a-zA-Z]', f" {remark} ", re.IGNORECASE):
                continue

        # 2. 解析 IP 和 端口 用于测速
        try:
            # vless://uuid@ip:port?params#remark
            # 简单的正则提取 ip 和 port
            # 这里的逻辑假设标准格式。如果不标准可能失败。
            main_part = link.split("?")[0] # 去掉参数
            ip_port = main_part.split("@")[-1] # 拿到 ip:port
            
            # 处理可能的 IPv6 [::1]:80
            if "]" in ip_port:
                host = ip_port.split("]:")[0].replace("[", "")
                port = ip_port.split("]:")[-1]
            else:
                host = ip_port.split(":")[0]
                port = ip_port.split(":")[1]
                
            # 3. 测速
            latency = tcp_ping(host, port)
            
            if latency < 2000: # 只保留能连上的 (
