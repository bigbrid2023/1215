import os
import time
import base64
import re
from urllib.parse import unquote
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from github import Github

# --- 配置 ---
GITHUB_TOKEN = os.getenv("MY_GITHUB_TOKEN")
REPO_NAME = "bigbrid2023/1215"
FILE_PATH = "sub_base64.txt"

def add_country_tag(nodes, country_prefix="US"):
    labeled_nodes = []
    for node in nodes:
        try:
            if "#" in node:
                base_part, remark = node.split("#", 1)
                try:
                    remark = unquote(remark)
                except:
                    pass
                new_node = f"{base_part}#{country_prefix}_{remark}"
            else:
                new_node = f"{node}#{country_prefix}_Node"
            labeled_nodes.append(new_node)
        except:
            labeled_nodes.append(node)
    return labeled_nodes

def run_scraper():
    print(">>> 正在启动浏览器...")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    # 伪装 User-Agent，防止被轻易识别为机器人
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        url = "https://openproxylist.com/v2ray/"
        print(f">>> 正在访问: {url}")
        driver.get(url)
        
        # 打印一下标题，看看是否被 Cloudflare 拦截
        print(f">>> 当前页面标题: {driver.title}")

        wait = WebDriverWait(driver, 20)

        # 1. 选择 Country
        print(">>> 尝试筛选: United States...")
        try:
            country_el = wait.until(EC.element_to_be_clickable((By.XPATH, "//option[contains(text(), 'United States')]")))
            parent_select = country_el.find_element(By.XPATH, "./..")
            Select(parent_select).select_by_visible_text("United States")
        except Exception as e:
            print(f"筛选国家遇到问题 (可能无需筛选): {e}")

        # 2. 点击 Search
        print(">>> 点击 Search...")
        try:
            search_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Search') or contains(text(), 'Filter')]")
            search_btn.click()
        except:
            print("未找到 Search 按钮，跳过点击")

        # === 关键修改：模拟滚动 + 增加等待 ===
        print(">>> 正在等待数据加载 (15秒)...")
        # 模拟人手滚动页面，触发懒加载
        for i in range(3):
            driver.execute_script("window.scrollBy(0, 500);")
            time.sleep(5) # 分段等待，共15秒
        
        # 3. 提取数据
        print(">>> 正在解析页面内容...")
        page_source = driver.page_source
        
        found_links = re.findall(r'(vless://[a-zA-Z0-9\-._~:/?#\[\]@!$&\'()*+,;=%]+)', page_source)
        found_links = list(set(found_links))
        
        print(f">>> 抓取结果: 找到 {len(found_links)} 个节点")

        # === 关键修改：如果没抓到，截图保存，方便调试 ===
        if len(found_links) == 0:
            print(">>> 警告: 未找到节点，正在截图保存为 debug_screenshot.png ...")
            driver.save_screenshot("debug_screenshot.png")
            # 同时打印一部分源码看看是不是 Cloudflare
            print(">>> 页面源码前500字符: ", page_source[:500])

        final_nodes = found_links[:10]
        return add_country_tag(final_nodes, "US")

    except Exception as e:
        print(f"!!! 流程出错: {e}")
        driver.save_screenshot("error_screenshot.png")
        return []
    finally:
        driver.quit()

def update_github_file(nodes):
    if not nodes:
        print("没有节点，不执行 GitHub 更新。")
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
            repo.update_file(file.path, "Auto Update (Fixed)", base64_str, file.sha)
            print(">>> GitHub 文件更新成功！")
        except:
            repo.create_file(FILE_PATH, "Auto Create (Fixed)", base64_str)
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
        print("本次未获取有效数据，请检查 Artifacts 中的截图。")
