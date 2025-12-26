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
# 目标订阅地址 (直接获取数据源)
TARGET_URL = "https://openproxylist.com/v2ray/rawlist/subscribe"
# ===========================================

def get_subscribe_content():
    """
    使用 Selenium 获取订阅源内容，以绕过潜在的 Cloudflare 浏览器检查
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
        # 等待页面加载，订阅页通常就是纯文本
        time.sleep(5)
        # 获取页面 body 的文本
        content = driver.find_element("tag name", "body").text
        print(f">>> 成功获取内容，长度: {len(content)}")
    except Exception as e:
        print(f"!!! 获取订阅源失败: {e}")
    finally:
        driver.quit()
        
    return content

def decode_base64(content):
    """
    解码 Base64 订阅内容
    """
    try:
        # 清理可能存在的空格
        content = content.strip()
        # 补全 padding，防止解码报错
        missing_padding = len(content) % 4
        if missing_padding:
            content += '=' * (4 - missing_padding)
            
        decoded_bytes = base64.b64decode(content)
        decoded_str = decoded_bytes.decode('utf-8', errors='ignore')
        
        links = decoded_str.splitlines()
        print(f">>> Base64 解码成功，共解析出 {len(links)} 行数据")
        return links
    except Exception as e:
        print(f"!!! Base64 解码失败 (尝试直接按行分割): {e}")
        return content.splitlines()

def tcp_ping(host, port, timeout=2):
    """
    对节点 IP:Port 进行 TCP 握手测速
    返回: 延迟(ms)，如果超时返回 9999
    """
    try:
        start_time = time.time()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, int(port)))
        sock.close()
        end_time = time.time()
        return (end_time - start_time) * 1000  # 毫秒
    except:
        return 9999

def parse_filter_and_test(links):
    """
    筛选美国节点并测速
    """
    valid_nodes = []
    print(">>> 开始筛选美国节点并进行 TCP 测速 (请耐心等待)...")
    
    for link in links:
        link = link.strip()
        if not link.startswith("vless://"):
            continue
            
        # 1. 提取备注信息
        remark = ""
        if "#" in link:
            remark = link.split("#")[-1]
            try:
                remark = unquote(remark)
            except:
                pass
        
        # 2. 筛选国家 (关键词: United States, USA, US)
        # 转换为大写进行比较，避免大小写问题
        upper_remark = remark.upper()
        if not any(kw in upper_remark for kw in ["UNITED STATES", "UNITEDSTATES", "USA", "AMERICA"]):
            # 特殊检查：避免把 'RUSSIA' 当成 'US'，检查独立的 'US'
            if "US" not in upper_remark.split("_") and "US" not in upper_remark.split(" "):
                 # 如果备注里完全没写国家，通常也跳过，宁缺毋滥
                 continue

        # 3. 解析 IP 和端口
        try:
            # vless://uuid@ip:port?params#remark
            # 简单解析，取 @ 后面，? 前面
            main_part = link.split("?")[0]
            if "@" in main_part:
                ip_port = main_part.split("@")[-1]
            else:
                # 兼容无 uuid@ 的情况 (少见)
                ip_port = main_part.replace("vless://", "")
            
            # 处理 IPv6 格式 [::1]:80
            if "]:" in ip_port:
                host = ip_port.split("]:")[0].replace("[", "")
                port = ip_port.split("]:")[-1]
            else:
                host = ip_port.split(":")[0]
                port = ip_port.split(":")[1]
            
            # 4. 执行真机测速
            latency = tcp_ping(host, port)
            
            if latency < 2000: # 丢弃延迟超过 2000ms (2秒) 的节点
                # 重写备注，把延迟写在最前面方便查看
                new_remark = f"US_{int(latency)}ms_{remark}"
                
                # 重新组合链接
                base_link = link.split("#")[0]
                final_link = f"{base_link}#{new_remark}"
                
                valid_nodes.append({
                    "link": final_link,
                    "latency": latency
                })
                # print(f"    [可用] {int(latency)}ms | {remark}") # 日志太多可注释掉
                
        except Exception as e:
            continue

    print(f">>> 测速完成，共找到 {len(valid_nodes)} 个可用美国节点")
    return valid_nodes

def update_github(nodes):
    if not nodes:
        print(">>> 没有可用节点，跳过上传。")
        return

    # 1. 按延迟排序 (从小到大)
    nodes.sort(key=lambda x: x["latency"])
    
    # 2. 取前 10 个
    top_nodes = nodes[:10]
    print(f">>> 选取最快的前 {len(top_nodes)} 个节点上传:")
    
    final_links = []
    for n in top_nodes:
        print(f"    {int(n['latency'])}ms -> {n['link'].split('#')[-1]}")
        final_links.append(n['link'])
        
    # 3. Base64 编码并上传
    content_str = "\n".join(final_links)
    content_bytes = content_str.encode('utf-8')
    base64_str = base64.b64encode(content_bytes).decode('utf-8')

    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        try:
            file = repo.get_contents(FILE_PATH)
            repo.update_file(file.path, "Auto Update: Top 10 Fastest US Nodes", base64_str, file.sha)
            print(">>> GitHub 文件更新成功！")
        except:
            repo.create_file(FILE_PATH, "Auto Create: Top 10 Fastest US Nodes", base64_str)
            print(">>> GitHub 文件创建成功！")
    except Exception as e:
        print(f"!!! GitHub API 操作失败: {e}")

def main():
    if not GITHUB_TOKEN:
        print("错误: 未检测到 GITHUB_TOKEN，请检查 Secrets 设置")
        exit(1)
        
    # 1. 获取 raw 内容
    raw_content = get_subscribe_content()
    if not raw_content:
        return

    # 2. 解码
    links = decode_base64(raw_content)
    if not links:
        return

    # 3. 筛选 + 测速
    valid_nodes = parse_filter_and_test(links)
    
    # 4. 排序并上传
    update_github(valid_nodes)

if __name__ == "__main__":
    main()
