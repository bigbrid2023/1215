import os
import time
import base64
import re
import socket
import json
import requests
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
    print(">>> [1/5] 正在启动浏览器获取订阅源...")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    content = ""
    
    try:
        driver.get(TARGET_URL)
        time.sleep(5)
        content = driver.find_element("tag name", "body").text
        print(f">>> 获取成功，长度: {len(content)}")
    except Exception as e:
        print(f"!!! 获取失败: {e}")
    finally:
        driver.quit()
    return content

def decode_base64(content):
    try:
        content = content.strip()
        missing_padding = len(content) % 4
        if missing_padding:
            content += '=' * (4 - missing_padding)
        decoded_bytes = base64.b64decode(content)
        decoded_str = decoded_bytes.decode('utf-8', errors='ignore')
        return decoded_str.splitlines()
    except:
        return content.splitlines()

def get_ip_location(ip):
    """
    调用 ip-api.com 查询 IP 真实归属地
    """
    try:
        # 限制速率，防止 API 封禁
        time.sleep(0.6) 
        response = requests.get(f"http://ip-api.com/json/{ip}?fields=status,countryCode", timeout=5)
        data = response.json()
        if data['status'] == 'success':
            return data['countryCode'] # 返回 US, CN, JP 等
    except:
        pass
    return "Unknown"

def tcp_ping(host, port, timeout=2):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, int(port)))
        sock.close()
        return True
    except:
        return False

def process_nodes(links):
    valid_nodes = []
    print(">>> [3/5] 开始处理节点 (API 验证 IP 归属地，速度较慢请耐心等待)...")
    
    # 限制最大处理数量，防止脚本运行超时 (处理前 80 个看起来像美国的)
    count = 0
    
    for link in links:
        link = link.strip()
        if not link.startswith("vless://"):
            continue
            
        # 简单预筛选：如果备注里明显写了其他国家，先跳过，节省 API 次数
        if any(c in link.upper() for c in ["FINLAND", "RUSSIA", "GERMANY", "KOREA", "JAPAN", "HONG KONG"]):
            continue

        try:
            # 解析 IP
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

            # === 步骤 1: 验活 (连不上的直接不要，省流量) ===
            if not tcp_ping(host, port):
                continue
            
            # === 步骤 2: API 查户口 (必须是 US) ===
            country = get_ip_location(host)
            if country != "US":
                print(f"    [剔除] {host} 归属地是 {country}，非美国。")
                continue
            
            # === 步骤 3: 成功入库 ===
            print(f"    [保留] {host} 是纯正美国 IP，且存活。")
            
            # 提取并美化备注
            remark = "Node"
            if "#" in link:
                try:
                    raw_remark = link.split("#")[-1]
                    remark = unquote(raw_remark).strip()
                except:
                    pass
            
            # 统一命名格式
            new_remark = f"US_Strict_{remark[:10]}"
            new_remark = re.sub(r'[^\w\-]', '', new_remark) # 清理特殊字符
            
            base_link = link.split("#")[0]
            final_link = f"{base_link}#{new_remark}"
            
            valid_nodes.append(final_link)
            count += 1
            
            # 为了防止超时，最多只取 50 个精品
            if count >= 50:
                print(">>> 已达到 50 个精品节点上限，停止采集。")
                break
                
        except Exception as e:
            continue

    print(f">>> [4/5] 筛选完成，共找到 {len(valid_nodes)} 个【纯美国】存活节点")
    return valid_nodes

def update_github(nodes):
    if not nodes:
        print(">>> 没有节点，跳过上传。")
        return

    print(f">>> [5/5] 正在上传 {len(nodes)} 个节点...")
    content_str = "\n".join(nodes)
    content_bytes = content_str.encode('utf-8')
    base64_str = base64.b64encode(content_bytes).decode('utf-8')

    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        try:
            file = repo.get_contents(FILE_PATH)
            repo.update_file(file.path, "Auto Update: US Strict Nodes", base64_str, file.sha)
            print(">>> GitHub 更新成功！")
        except:
            repo.create_file(FILE_PATH, "Auto Create: US Strict Nodes", base64_str)
            print(">>> GitHub 创建成功！")
    except Exception as e:
        print(f"!!! GitHub API 错误: {e}")

def main():
    if not GITHUB_TOKEN:
        print("错误: 缺少 GITHUB_TOKEN")
        exit(1)
        
    raw_content = get_subscribe_content()
    links = decode_base64(raw_content)
    if links:
        valid_nodes = process_nodes(links)
        update_github(valid_nodes)

if __name__ == "__main__":
    main()
