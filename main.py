import os
import time
import base64
import re
import socket
from urllib.parse import unquote
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from github import Github

# ================= 配置区域 =================
GITHUB_TOKEN = os.getenv("MY_GITHUB_TOKEN")
REPO_NAME = "bigbrid2023/1215"
FILE_PATH = "sub_base64.txt"
TARGET_URL = "https://openproxylist.com/v2ray/rawlist/subscribe"
# ===========================================

def get_subscribe_content():
    print(">>> 正在启动浏览器获取订阅源...")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    content = ""
    
    try:
        print(f">>> 访问 URL: {TARGET_URL}")
        driver.get(TARGET_URL)
        time.sleep(5)
        content = driver.find_element("tag name", "body").text
        print(f">>> 成功获取内容，长度: {len(content)}")
    except Exception as e:
        print(f"!!! 获取订阅源失败: {e}")
    finally:
        driver.quit()
        
    return content

def decode_base64(content):
    try:
        content = content.strip()
        # 自动补全 Base64 padding
        missing_padding = len(content) % 4
        if missing_padding:
            content += '=' * (4 - missing_padding)
            
        decoded_bytes = base64.b64decode(content)
        decoded_str = decoded_bytes.decode('utf-8', errors='ignore')
        links = decoded_str.splitlines()
        print(f">>> Base64 解码成功，共解析出 {len(links)} 行数据")
        return links
    except Exception as e:
        print(f"!!! Base64 解码异常 (将尝试直接按行处理): {e}")
        return content.splitlines()

def tcp_ping(host, port, timeout=3):
    """
    TCP 端口连通性测试
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, int(port)))
        sock.close()
        return True
    except:
        return False

def parse_filter_and_test(links):
    valid_nodes = []
    print(">>> 开始宽松筛选与测速 (Scanning)...")
    
    # 调试计数器
    debug_count = 0
    
    for link in links:
        link = link.strip()
        if not link.startswith("vless://"):
            continue
            
        # 调试：打印前3个原始链接，看看长什么样
        if debug_count < 3:
            print(f"[DEBUG] 扫描节点样本: {link[:60]}...")
            debug_count += 1
            
        # === 核心逻辑修改：全字符串匹配 ===
        # 不再依赖备注位置，只要这行字里有 US 信息就算
        upper_link = link.upper()
        
        # 1. 关键词检测
        is_us = False
        if "UNITED STATES" in upper_link or "UNITEDSTATES" in upper_link or "AMERICA" in upper_link:
            is_us = True
        # 检测独立的 "US" (避免匹配到 RUSSIA 或 STATUS)
        # 正则含义：US前后不是字母
        elif re.search(r'[^A-Z]US[^A-Z]', upper_link) or upper_link.endswith("US") or "US_" in upper_link:
            is_us = True
            
        if not is_us:
            continue # 不是美国节点，跳过

        # 2. 提取信息用于测速
        try:
            # 提取备注以便后续命名 (尝试取 # 后面的)
            remark = "US_Node"
            if "#" in link:
                try:
                    raw_remark = link.split("#")[-1]
                    remark = unquote(raw_remark).strip()
                except:
                    pass
            
            # 解析 IP 和 端口
            main_part = link.split("?")[0]
            if "@" in main_part:
                ip_port = main_part.split("@")[-1]
            else:
                ip_port = main_part.replace("vless://", "")
            
            if "]:" in ip_port:
                host = ip_port.split("]:")[0].replace("[", "")
                port = ip_port.split("]:")[-1]
            else:
                host = ip_port.split(":")[0]
                port = ip_port.split(":")[1]
            
            # 3. 连通性测试
            if tcp_ping(host, port):
                # 重新构造成带有 US 标签的节点
                # 移除旧备注，加上新备注
                base_link = link.split("#")[0]
                # 构造新备注：US_GitHubAlive_原备注前10位
                new_remark = f"US_GitHubAlive_{remark[:15]}"
                # 去除备注里可能的非法字符
                new_remark = re.sub(r'[^\w\-_]', '', new_remark)
                
                final_link = f"{base_link}#{new_remark}"
                valid_nodes.append(final_link)
                
        except Exception as e:
            # 解析出错跳过
            continue

    print(f">>> 筛选完成，共找到 {len(valid_nodes)} 个可用节点")
    return valid_nodes

def update_github(nodes):
    if not nodes:
        print(">>> 没有可用节点，跳过上传。")
        return

    # 只要有节点就传，不限制数量，方便你本地筛选
    print(f">>> 准备上传 {len(nodes)} 个节点...")
    
    content_str = "\n".join(nodes)
    content_bytes = content_str.encode('utf-8')
    base64_str = base64.b64encode(content_bytes).decode('utf-8')

    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        try:
            file = repo.get_contents(FILE_PATH)
            repo.update_file(file.path, "Auto Update: US Nodes", base64_str, file.sha)
            print(">>> GitHub 文件更新成功！")
        except:
            repo.create_file(FILE_PATH, "Auto Create: US Nodes", base64_str)
            print(">>> GitHub 文件创建成功！")
    except Exception as e:
        print(f"!!! GitHub API 操作失败: {e}")

def main():
    if not GITHUB_TOKEN:
        print("错误: 未检测到 GITHUB_TOKEN")
        exit(1)
        
    raw_content = get_subscribe_content()
    if not raw_content:
        return

    links = decode_base64(raw_content)
    if not links:
        return

    valid_nodes = parse_filter_and_test(links)
    
    update_github(valid_nodes)

if __name__ == "__main__":
    main()
