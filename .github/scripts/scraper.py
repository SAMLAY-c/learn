# 文件路径: .github/scripts/scraper.py
# 作用: 核心处理脚本，负责下载链接内容、提取正文、下载图片并格式化为 Markdown。

import os
import requests
import frontmatter
from datetime import datetime
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from readability import Document
import re
import sys

# --- 配置 ---
# 所有下载的图片都将存放在这个文件夹下
ATTACHMENT_FOLDER = "attachments/images"

def download_images_and_update_html(html_content, base_url):
    """下载HTML中的所有图片到本地，并替换链接为Obsidian内部链接。"""
    soup = BeautifulSoup(html_content, 'html.parser')
    os.makedirs(ATTACHMENT_FOLDER, exist_ok=True)
    
    for img in soup.find_all('img'):
        try:
            # 兼容普通 src 和懒加载的 data-src
            src = img.get('data-src') or img.get('src')
            if not src or src.startswith('data:'): continue

            # 构造完整的图片 URL
            if src.startswith('//'): img_url = 'https:' + src
            elif src.startswith('/'): img_url = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}{src}"
            else: img_url = src
            
            # 下载图片
            response = requests.get(img_url, stream=True, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
            if response.status_code == 200:
                # 生成安全的文件名
                img_name_base = os.path.basename(urlparse(img_url).path).split('?')[0]
                if not img_name_base: img_name_base = str(hash(img_url))
                img_ext = os.path.splitext(img_name_base)[1] or '.png'
                img_name = f"{os.path.splitext(img_name_base)[0][:50]}{img_ext}"

                img_path = os.path.join(ATTACHMENT_FOLDER, img_name)
                with open(img_path, 'wb') as f:
                    for chunk in response.iter_content(1024):
                        f.write(chunk)
                
                # 替换为 Obsidian 的内部链接格式
                new_tag = soup.new_tag("p")
                new_tag.string = f"![[{img_name}]]"
                img.replace_with(new_tag)
        except Exception as e:
            # 如果单张图片下载失败，打印错误并继续
            print(f"Skipping image {src}, error: {e}", file=sys.stderr)
            
    return str(soup)

def main(url):
    """主函数，处理单个URL。"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status() # 如果请求失败则抛出异常
        
        # 使用 Mozilla 的 readability 库提取核心内容
        doc = Document(response.text)
        title = doc.title()
        content_html = doc.summary()

        # 下载图片并替换链接
        content_with_local_images = download_images_and_update_html(content_html, url)
        
        # 从HTML中提取纯文本作为Markdown内容
        soup = BeautifulSoup(content_with_local_images, 'html.parser')
        content_md = soup.get_text(separator='\n\n', strip=True)

        # 生成安全的文件名
        safe_title = re.sub(r'[\/:*?"<>|]', '_', title)[:80]
        date_str = datetime.now().strftime("%Y-%m-%d")
        
        # 根据域名自动分类
        folder = "1. Inbox"
        if "mp.weixin.qq.com" in url: folder = "2. AI-Technology"
        
        # 使用 frontmatter 库构建 Markdown 文件
        post = frontmatter.Post(f"\n{content_md}")
        post.metadata = { 'url': url, 'title': title, 'tags': ['FromWeChat', 'Inbox'], 'created': date_str }
        
        # 写入文件
        os.makedirs(folder, exist_ok=True)
        file_path = os.path.join(folder, f"{date_str} {safe_title}.md")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(frontmatter.dumps(post))
            
        print(f"Article saved to {file_path}")
        
        # 向 GitHub Actions 输出变量，用于 commit message
        github_output_file = os.getenv('GITHUB_OUTPUT')
        if github_output_file:
            with open(github_output_file, 'a') as f:
                f.write(f"title={safe_title}\n")
            
    except Exception as e:
        print(f"Failed to process URL {url}. Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        print("No URL provided.", file=sys.stderr)
        sys.exit(1)
