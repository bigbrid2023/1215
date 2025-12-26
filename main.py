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
    """
    给节点添加国家标注
    """
    labeled_nodes = []
    for node in nodes:
        try:
            # vless链接通常格式: vless://uuid@ip:port?params#remark
            if "#" in node:
                # 如果已有备注，拆分链接
                base_part, remark = node.split("#", 1)
                # URL解码备注（防止是乱码）
                try:
                    remark = unquote(remark)
                except:
                    pass
                # 重新组合：US_原备注
                new_node = f"{base_part}#{country_prefix}_{remark}"
            else:
                # 如果没有备注，直接加上
                new_node = f"{node}#{country_prefix}_Node"
            
            labeled_nodes.append(new_node)
        except:
            # 如果处理出错，保留原样
            labeled_nodes.append(node)
            
    return labeled_nodes

def run_scraper():
    print(">>> 正在启动无头浏览器...")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        url = "https://openproxylist.com/v2ray/"
        print(f">>> 正在访问: {url}")
        driver.get(url)
        wait = WebDriverWait(driver, 15)

        # 1. 选择 Country: United States
        print(">>> 正在筛选: United States...")
        try:
            country_el = wait.until(EC.element_to_be_clickable((By.XPATH, "//option[contains(text(), 'United States')]")))
            parent_select = country_el.find_element(By.XPATH, "./..")
            Select(parent_select).select_by_visible_text("United States")
        except Exception as e:
            print(f"筛选国家时遇到小问题: {e}")

        # 2. 选择 Protocol: vless
        print(">>> 正在筛选: vless...")
        try:
            vless_el = driver.find_element(By.XPATH, "//option[contains(text(), 'vless') or contains(@value, 'vless')]")
            parent_select_v = vless_el.find_element(By.XPATH, "./..")
            Select(parent_select_v).select_by_visible_text("vless")
        except:
            pass

        # 3. 点击 Search
        print(">>> 点击 Search...")
        try:
            search_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Search') or contains(text(), 'Filter')]")
            search_btn.click()
            time.sleep(5) 
        except:
            pass

        # 4. 提取数据
        print(">>> 正在解析页面内容...")
        page_source = driver.page_source
        
        # 正则提取 vless:// 链接
        found_links = re.findall(r'(vless://[a-zA-Z0-9\-._~:/?#\[\]@!$&\'()*+,;=%]+)', page_source)
        found_links = list(set(found_links))
        
        print(f">>> 原始抓取到 {len(found_links)} 个节点")

        # 取前 10 个
        raw_nodes = found_links[:10]
        
        # === 新增步骤：添加国家标注 ===
        final_nodes = add_country_tag(raw_nodes, "US")
        
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
    
    content_str = "\n".join(nodes)
    content_bytes = content_str.encode('utf-8')
    base64_str = base64.b64encode(content_bytes).decode('utf-8')

    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        
        try:
            file = repo.get_contents(FILE_PATH)
            repo.update_file(file.path, "Auto Update: vless nodes with US tag", base64_str, file.sha)
            print(">>> GitHub 文件更新成功！(Update)")
        except:
            repo.create_file(FILE_PATH, "Auto Create: vless nodes with US tag", base64_str)
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
