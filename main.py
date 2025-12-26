import os
import time
import base64
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from github import Github

# --- 配置 ---
# 从 GitHub Secrets 读取 Token，如果本地运行则需要手动设置环境变量
GITHUB_TOKEN = os.getenv("MY_GITHUB_TOKEN")
REPO_NAME = "bigbrid2023/1215"   # 你的仓库
FILE_PATH = "sub_base64.txt"     # 你的目标文件

def run_scraper():
    print(">>> 正在启动无头浏览器...")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless") # 必须：无界面模式
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    nodes = []
    
    try:
        url = "https://openproxylist.com/v2ray/"
        print(f">>> 正在访问: {url}")
        driver.get(url)
        wait = WebDriverWait(driver, 15)

        # 1. 选择 Country: United States
        # 尝试寻找国家选择框。注：如果网页ID变动，这里可能需要根据实际网页源代码调整
        print(">>> 正在筛选: United States...")
        try:
            # 这里的XPATH是查找所有包含'United States'文本的选项并点击
            country_el = wait.until(EC.element_to_be_clickable((By.XPATH, "//option[contains(text(), 'United States')]")))
            # 如果是标准的 select 元素，需要点击父级 select
            parent_select = country_el.find_element(By.XPATH, "./..")
            Select(parent_select).select_by_visible_text("United States")
        except Exception as e:
            print(f"筛选国家时遇到小问题 (可能默认已选或UI不同): {e}")

        # 2. 选择 Protocol: vless
        print(">>> 正在筛选: vless...")
        try:
            # 尝试寻找包含 vless 文本的选项
            vless_el = driver.find_element(By.XPATH, "//option[contains(text(), 'vless') or contains(@value, 'vless')]")
            parent_select_v = vless_el.find_element(By.XPATH, "./..")
            Select(parent_select_v).select_by_visible_text("vless")
        except:
            print("未找到显式的vless筛选器，将尝试直接在结果中过滤。")

        # 3. 点击 Search 按钮
        print(">>> 点击 Search...")
        try:
            # 寻找类似 "Search" 或 "Filter" 的按钮
            search_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Search') or contains(text(), 'Filter')]")
            search_btn.click()
            time.sleep(5) # 等待结果刷新
        except:
            print("未找到 Search 按钮，可能自动刷新。")

        # 4. 提取数据
        print(">>> 正在解析页面内容...")
        # 为了保险，直接获取页面源码用正则提取，这是最抗造的方法
        page_source = driver.page_source
        
        # 正则提取 vless:// 链接
        found_links = re.findall(r'(vless://[a-zA-Z0-9\-._~:/?#\[\]@!$&\'()*+,;=%]+)', page_source)
        
        # 去重
        found_links = list(set(found_links))
        print(f">>> 原始抓取到 {len(found_links)} 个节点")

        # 5. 简单的逻辑筛选 (假设网页没有帮我们完美排序)
        # 真正的 Ping 检测在 GitHub Actions 里很难做得准，这里默认取前 10 个
        # 因为通常网站都会把最新的或质量好的放在前面
        final_nodes = found_links[:10]
        
        return final_nodes

    except Exception as e:
        print(f"!!! 抓取流程出错: {e}")
        return []
    finally:
        driver.quit()

def update_github_file(nodes):
    if not nodes:
        print("没有节点，不更新。")
        return

    print(f">>> 正在处理 {len(nodes)} 个节点并上传...")
    
    # 拼接并 Base64 编码
    content_str = "\n".join(nodes)
    content_bytes = content_str.encode('utf-8')
    base64_str = base64.b64encode(content_bytes).decode('utf-8')

    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        
        try:
            # 尝试获取现有文件
            file = repo.get_contents(FILE_PATH)
            # 更新文件
            repo.update_file(file.path, "Auto Update: vless nodes", base64_str, file.sha)
            print(">>> GitHub 文件更新成功！(Update)")
        except:
            # 如果文件不存在，创建新文件
            repo.create_file(FILE_PATH, "Auto Create: vless nodes", base64_str)
            print(">>> GitHub 文件创建成功！(Create)")
            
    except Exception as e:
        print(f"!!! GitHub API 操作失败: {e}")

if __name__ == "__main__":
    if not GITHUB_TOKEN:
        print("错误: 未检测到 GITHUB_TOKEN 环境变量！")
        exit(1)
        
    nodes = run_scraper()
    if nodes:
        update_github_file(nodes)
    else:
        print("本次运行未获取到有效数据。")
