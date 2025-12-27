import os
import time
import base64
import re
from urllib.parse import unquote
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from github import Github

# ================= 配置区域 =================
GITHUB_TOKEN = os.getenv("MY_GITHUB_TOKEN")
REPO_NAME = "bigbrid2023/1215"
FILE_PATH = "sub_base64.txt"
# 依然使用订阅源，这是最全的数据库
TARGET_URL = "https://openproxylist.com/v2ray/rawlist/subscribe"
# ===========================================

def get_subscribe_content():
    print(">>> [1/4] 启动浏览器获取原始数据...")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    # 使用最新的 User-Agent 模拟真实用户
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    content = ""
    
    try:
        driver.get(TARGET_URL)
        # 给足时间加载
        time.sleep(8)
        content = driver.find_element("tag name", "body").text
        print(f">>> 数据获取成功，长度: {len(content)}")
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
        lines = decoded_str.splitlines()
        print(f">>> [2/4] 解码成功，原始节点库共 {len(lines)} 个")
        return lines
    except:
        return content.splitlines()

def filter_us_nodes(links):
    valid_nodes = []
    print(">>> [3/4] 开始执行离线筛选 (只保留 United States)...")
    
    for link in links:
        link = link.strip()
        if not link.startswith("vless://"):
            continue
            
        try:
            # === 核心逻辑：解码备注，文本匹配 ===
            # 我们不查 IP，不测速，完全信任节点自己的标注，避免误杀
            
            # 1. 提取备注信息 (Url Decode)
            # vless://...?#备注
            remark = "Node"
            raw_remark = ""
            
            if "#" in link:
                raw_remark = link.split("#")[-1]
                try:
                    remark = unquote(raw_remark)
                except:
                    remark = raw_remark

            # 2. 构造完整的搜索字符串 (包含链接本身和备注)
            # 这样如果 IP 库信息写在链接参数里也能被发现
            full_search_str = (link + remark).upper()
            
            # 3. 严格匹配美国关键词
            keywords = ["UNITED STATES", "UNITEDSTATES", "USA", "AMERICA"]
            
            # 排除关键词 (防止匹配到 RUSSIA 等)
            exclude_keywords = ["RUSSIA", "BELARUS", "AUSTRALIA", "AUSTRIA"]
            
            if any(k in full_search_str for k in exclude_keywords):
                continue
                
            # 必须包含美国关键词
            # 或者 备注里明确写着 US (利用正则匹配独立的 US 单词)
            is_us = False
            if any(k in full_search_str for k in keywords):
                is_us = True
            elif re.search(r'[^A-Z]US[^A-Z]', full_search_str): # 匹配 _US_ , [US] 等
                is_us = True
                
            if is_us:
                # 重新美化备注
                # 去除乱七八糟的符号，保留关键信息
                clean_remark = re.sub(r'[^\w\-\.]', '', remark)[:20]
                new_remark = f"US_Node_{clean_remark}"
                
                base_link = link.split("#")[0]
                final_link = f"{base_link}#{new_remark}"
                
                valid_nodes.append(final_link)
                
        except Exception as e:
            continue

    # 去重
    valid_nodes = list(set(valid_nodes))
    print(f">>> 筛选结束，共提取到 {len(valid_nodes)} 个【标记为美国】的节点")
    return valid_nodes

def update_github(nodes):
    if not nodes:
        print(">>> 没有节点，跳过上传。")
        return

    # 既然是离线筛选，可能数量较多，我们只取前 200 个，足够用了
    final_nodes = nodes[:200]
    
    print(f">>> [4/4] 正在上传 {len(final_nodes)} 个节点...")
    content_str = "\n".join(final_nodes)
    content_bytes = content_str.encode('utf-8')
    base64_str = base64.b64encode(content_bytes).decode('utf-8')

    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        try:
            file = repo.get_contents(FILE_PATH)
            repo.update_file(file.path, "Auto Update: US Nodes Offline Filter", base64_str, file.sha)
            print(">>> GitHub 更新成功！")
        except:
            repo.create_file(FILE_PATH, "Auto Create: US Nodes Offline Filter", base64_str)
            print(">>> GitHub 创建成功！")
    except Exception as e:
        print(f"!!! GitHub API 操作失败: {e}")

if __name__ == "__main__":
    if not GITHUB_TOKEN:
        print("错误: 缺少 GITHUB_TOKEN")
        exit(1)
        
    raw_content = get_subscribe_content()
    links = decode_base64(raw_content)
    if links:
        valid_nodes = filter_us_nodes(links)
        update_github(valid_nodes)
