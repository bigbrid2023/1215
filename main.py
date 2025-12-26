import os
import time
import base64
import re
from urllib.parse import unquote
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from github import Github

# --- 配置 ---
GITHUB_TOKEN = os.getenv("MY_GITHUB_TOKEN")
REPO_NAME = "bigbrid2023/1215"
FILE_PATH = "sub_base64.txt"

def run_scraper():
    print(">>> 正在启动浏览器...")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    # 伪装 User-Agent，防止部分反爬
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    valid_nodes = []
    
    try:
        url = "https://openproxylist.com/v2ray/"
        print(f">>> 正在访问: {url}")
        driver.get(url)
        
        # 等待表格加载
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "tr")))
        print(">>> 页面已加载，准备抓取数据...")

        # === 动作 1: 暴力滚动 (加载更多数据) ===
        # 我们不依赖网页的筛选，而是加载足够多的数据，然后自己挑
        print(">>> 正在向下滚动加载更多节点 (执行 10 次)...")
        for i in range(10):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2) # 每次滚动等待2秒加载
        
        # === 动作 2: 获取所有行并逐行分析 ===
        # 找到所有表格行 (通常是 tr 或者具有 row 样式的 div)
        rows = driver.find_elements(By.TAG_NAME, "tr")
        print(f">>> 扫描到 {len(rows)} 行数据，开始 Python 级筛选...")
        
        for row in rows:
            try:
                text = row.text
                inner_html = row.get_attribute('innerHTML')
                
                # --- 筛选条件 1: 必须包含 United States ---
                if "United States" not in text:
                    continue # 跳过非美国节点
                
                # --- 筛选条件 2: 必须包含 Vless (或者 V2Ray Vless) ---
                # 注意：忽略大小写
                if "vless" not in text.lower():
                    continue # 跳过非 vless 协议
                
                # --- 筛选条件 3: 简单的速度判断 (可选) ---
                # 如果你想严格 100ms，可以解析 text 中的 "xxxms"
                # 这里我们先只做简单的文本匹配，确保拿到数据再说
                
                # === 动作 3: 提取隐藏的链接 ===
                # 链接通常在 data-clipboard-text 属性里，或者 href 里
                # 我们在这一行的 HTML 代码里找 vless:// 开头的字符串
                
                # 正则查找 vless://... (忽略大小写)
                # 匹配直到遇到双引号、单引号、空格或尖括号结束
                link_match = re.search(r'(vless://[a-zA-Z0-9\-._~:/?#\[\]@!$&\'()*+,;=%]+)', inner_html, re.IGNORECASE)
                
                if link_match:
                    raw_link = link_match.group(1)
                    # 添加标注 (US_Tag)
                    final_link = add_tag(raw_link, "US")
                    valid_nodes.append(final_link)
                    print(f"    [成功] 找到一个美国 Vless 节点: {final_link[:30]}...")
                else:
                    # 如果这行符合条件但没找到链接，可能是加密了或者通过点击触发
                    # 尝试找 data-clipboard-text
                    if "data-clipboard-text" in inner_html:
                         clip_match = re.search(r'data-clipboard-text="([^"]+)"', inner_html)
                         if clip_match and "vless" in clip_match.group(1):
                             final_link = add_tag(clip_match.group(1), "US")
                             valid_nodes.append(final_link)
            
            except Exception as e:
                continue # 这一行解析出错，跳过

        print(f">>> 筛选完成，共找到 {len(valid_nodes)} 个符合要求的节点。")
        
        # 如果还是没找到，截图看看为什么
        if len(valid_nodes) == 0:
            print(">>> 警告: 0 节点，保存截图 debug_filter.png")
            driver.save_screenshot("debug_filter.png")
            # 打印第一行的 HTML 供调试
            if rows:
                print(">>> 首行 HTML 示例:", rows[0].get_attribute('outerHTML')[:300])

        return valid_nodes[:10] # 只取前10个

    except Exception as e:
        print(f"!!! 流程出错: {e}")
        driver.save_screenshot("error_screenshot.png")
        return []
    finally:
        driver.quit()

def add_tag(link, tag):
    """给链接添加备注 tag"""
    try:
        if "#" in link:
            base, remark = link.split("#", 1)
            try:
                remark = unquote(remark)
            except:
                pass
            return f"{base}#{tag}_{remark}"
        else:
            return f"{link}#{tag}_Node"
    except:
        return link

def update_github_file(nodes):
    if not nodes:
        print("没有节点，跳过上传。")
        return

    print(f">>> 正在上传 {len(nodes)} 个节点...")
    content_str = "\n".join(nodes)
    content_bytes = content_str.encode('utf-8')
    base64_str = base64.b64encode(content_bytes).decode('utf-8')

    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        try:
            file = repo.get_contents(FILE_PATH)
            repo.update_file(file.path, "Auto Update: US Vless Nodes", base64_str, file.sha)
            print(">>> GitHub 文件更新成功！")
        except:
            repo.create_file(FILE_PATH, "Auto Create: US Vless Nodes", base64_str)
            print(">>> GitHub 文件创建成功！")
    except Exception as e:
        print(f"!!! GitHub API 失败: {e}")

if __name__ == "__main__":
    if not GITHUB_TOKEN:
        print("错误: 缺少 GITHUB_TOKEN")
        exit(1)
    nodes = run_scraper()
    if nodes:
        update_github_file(nodes)
    else:
        print("本次未获取有效数据。")
