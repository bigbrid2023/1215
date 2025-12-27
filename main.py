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

# ================= 配置区域 =================
GITHUB_TOKEN = os.getenv("MY_GITHUB_TOKEN")
REPO_NAME = "bigbrid2023/1215"
FILE_PATH = "sub_base64.txt"
# 目标是网页，不是订阅链接
TARGET_URL = "https://openproxylist.com/v2ray/"
# ===========================================

def run_scraper():
    print(">>> 正在启动浏览器 (模拟人工访问)...")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    valid_nodes = []
    
    try:
        print(f">>> 访问网页: {TARGET_URL}")
        driver.get(TARGET_URL)
        
        # 等待表格加载
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "tr")))
        print(">>> 页面已加载，开始加载更多数据...")

        # === 动作: 暴力滚动 (Scroll) ===
        # 既然筛选框难点，我们就加载足够多的数据，然后自己挑
        # 滚动 15 次，每次间隔 1.5 秒，保证加载出几百个节点
        for i in range(15):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.5)
        
        # 获取页面所有内容
        page_source = driver.page_source
        
        # 获取所有表格行
        rows = driver.find_elements(By.TAG_NAME, "tr")
        print(f">>> 扫描到 {len(rows)} 行数据，开始筛选 United States...")

        for row in rows:
            try:
                # 获取这一行的 HTML 和 文本
                inner_html = row.get_attribute('innerHTML')
                text_content = row.text

                # === 筛选条件: 必须包含 United States ===
                # 网站上通常显示为 "United States" 文本或图标alt
                if "United States" not in text_content and "USA" not in text_content:
                    continue # 不是美国，跳过
                
                # === 提取链接 ===
                # 链接通常隐藏在复制按钮的 data-clipboard-text 属性里
                # 或者直接在 HTML 里有 vless://
                
                link = ""
                # 方法1: 正则查找 data-clipboard-text="..."
                clip_match = re.search(r'data-clipboard-text="([^"]+)"', inner_html)
                if clip_match:
                    link = clip_match.group(1)
                else:
                    # 方法2: 直接查找 vless:// 字符串
                    vless_match = re.search(r'(vless://[a-zA-Z0-9\-._~:/?#\[\]@!$&\'()*+,;=%]+)', inner_html)
                    if vless_match:
                        link = vless_match.group(1)

                if link and link.startswith("vless://"):
                    # 找到了！
                    # 提取备注 (通常在 # 后面)
                    remark = "US_Node"
                    if "#" in link:
                        try:
                            raw_remark = link.split("#")[-1]
                            remark = unquote(raw_remark)
                        except:
                            pass
                    
                    # 统一重命名，加上 [WebHighQuality] 标记，让你知道这是来自网页的高质量节点
                    # 去掉原备注里的特殊字符
                    safe_remark = re.sub(r'[^\w\-]', '', remark)[:15]
                    new_remark = f"US_WebHQ_{safe_remark}"
                    
                    final_link = f"{link.split('#')[0]}#{new_remark}"
                    
                    # 去重
                    if final_link not in valid_nodes:
                        valid_nodes.append(final_link)
                        # print(f"    [捕获] {new_remark}") # 日志太多可注释

            except Exception as e:
                continue

        print(f">>> 筛选完成，共提取到 {len(valid_nodes)} 个【网页版】美国节点")
        
        # 如果没抓到，截图调试
        if len(valid_nodes) == 0:
            print(">>> 警告: 0 节点，保存截图 debug_web.png")
            driver.save_screenshot("debug_web.png")
            print(">>> 页面源码前500字:", page_source[:500])

    except Exception as e:
        print(f"!!! 抓取出错: {e}")
        driver.save_screenshot("error_web.png")
    finally:
        driver.quit()
        
    return valid_nodes

def update_github(nodes):
    if not nodes:
        print(">>> 没有节点，跳过上传。")
        return

    # 只保留前 50 个，避免太长
    final_nodes = nodes[:50]
    print(f">>> 准备上传 {len(final_nodes)} 个节点...")
    
    content_str = "\n".join(final_nodes)
    content_bytes = content_str.encode('utf-8')
    base64_str = base64.b64encode(content_bytes).decode('utf-8')

    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        try:
            file = repo.get_contents(FILE_PATH)
            repo.update_file(file.path, "Auto Update: Web High Quality Nodes", base64_str, file.sha)
            print(">>> GitHub 更新成功！")
        except:
            repo.create_file(FILE_PATH, "Auto Create: Web High Quality Nodes", base64_str)
            print(">>> GitHub 创建成功！")
    except Exception as e:
        print(f"!!! GitHub API 操作失败: {e}")

if __name__ == "__main__":
    if not GITHUB_TOKEN:
        print("错误: 缺少 GITHUB_TOKEN")
        exit(1)
        
    nodes = run_scraper()
    update_github(nodes)
