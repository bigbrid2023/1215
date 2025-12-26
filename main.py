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
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
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
        missing_padding = len(content) % 4
        if missing_padding:
            content += '=' * (4 - missing_padding)
        decoded_bytes = base64.b64decode(content)
        decoded_str = decoded_bytes.decode('utf-8', errors='ignore')
        links = decoded_str.splitlines()
        print(f">>> Base64 解码成功，共解析出 {len(links)} 行数据")
        return links
    except Exception as e:
        print(f"!!! 解码失败: {e}")
        return content.splitlines()

def tcp_ping(host, port, timeout=1.5):
    """
    仅测试端口是否开放，timeout 设置短一点，快速筛选
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
    print(">>> 开始筛选美国节点 (放宽筛选数量)...")
    
    for link in links:
        link = link.strip()
        if not link.startswith("vless://"):
            continue
            
        # 1. 提取备注
        remark = ""
        if "#" in link:
            remark = link.split("#")[-1]
            try:
                remark = unquote(remark)
            except:
                pass
        
        # 2. 筛选国家 (US/USA/United States)
        upper_remark = remark.upper()
        if not any(kw in upper_remark for kw in ["UNITED STATES", "UNITEDSTATES", "USA", "AMERICA"]):
             # 再次确认：如果没有国家标识，但看起来像域名的，暂且跳过，宁缺毋滥
             if "US" not in upper_remark.split("_"):
                 continue

        # 3. 解析 IP/Port
        try:
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
            
            # 4. 简单的连通性测试 (不测具体延迟数值了，只看通不通)
            is_alive = tcp_ping(host, port)
            
            if is_alive:
                # 重新命名：US_GitHubAlive_随机字符，方便你去重
                # 去掉之前的 ms 显示，因为那个 ms 是误导
                new_remark = f"US_Node_{remark[:15]}"
                base_link = link.split("#")[0]
                final_link = f"{base_link}#{new_remark}"
                
                valid_nodes.append(final_link)
                
        except Exception as e:
            continue

    print(f">>> 筛选完成，共找到 {len(valid_nodes)} 个可用节点")
    return valid_nodes

def update_github(nodes):
    if not nodes:
        print(">>> 没有可用节点，跳过上传。")
        return

    # 这里改为取前 100 个，给你足够多的样本去本地测速
    top_nodes = nodes[:100]
    print(f">>> 上传前 {len(top_nodes)} 个节点...")
    
    content_str = "\n".join(top_nodes)
    content_bytes = content_str.encode('utf-8')
    base64_str = base64.b64encode(content_bytes).decode('utf-8')

    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        try:
            file = repo.get_contents(FILE_PATH)
            repo.update_file(file.path, "Auto Update: US Nodes Pool", base64_str, file.sha)
            print(">>> GitHub 文件更新成功！")
        except:
            repo.create_file(FILE_PATH, "Auto Create: US Nodes Pool", base64_str)
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
