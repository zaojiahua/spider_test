import base64
import os
import re
import html
import time
import uuid
from datetime import datetime
from urllib.parse import urlparse
import hmac
import urllib.parse

from PIL import Image
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from lxml import etree
import hashlib
import json
import random
from pymongo import UpdateOne
from gmssl import sm3, func
from playwright.sync_api import sync_playwright

from util.requests_util import AsyncRequests as requests


# 使用 AES CBC PKCS7 PADDING 解密
def aes_cbc_decrypt(ciphertext, key, iv):
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    plaintext = decryptor.update(ciphertext) + decryptor.finalize()
    return plaintext


# 从包含 json 的文本中提取 json 格式的字符串
def extract_json(json_text):
    json_pattern = r"\{.*\}"
    json_match = re.search(json_pattern, json_text)

    if json_match:
        extracted_json = json_match.group()
    else:
        extracted_json = None

    return extracted_json


# 定义一些常用的工具函数
def parse_date(date_string):
    # 也有可能是时间戳
    if str(date_string).isdigit():
        if len(str(date_string)) == 11:
            timestamp = int(date_string)
        elif len(str(date_string)) == 13:
            timestamp = int(date_string) / 1000
        elif len(str(date_string)) == 14:
            return datetime.strptime(date_string, "%Y%m%d%H%M%S")
        else:
            return None
        return datetime.fromtimestamp(timestamp)

    # f 最多能匹配 6 位，代表微妙
    if 'T' in date_string and '.' in date_string and '+' not in date_string:
        date_string = date_string[:26]
    else:
        date_string = date_string[:29]

    # 定义可能的日期格式
    date_formats = ["%Y-%m-%d",
                    "%d-%m-%Y",
                    "%m/%d/%Y",
                    "%Y/%m/%d",
                    "%Y-%m-%dT%H:%M:%S.%f",
                    "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%dT%H:%M:%S.%f+08:00",
                    "%Y-%m-%dT%H:%M:%S.%f+0800",
                    "%Y-%m-%dT%H:%M:%S.%f+00:00",
                    "%Y-%m-%d %H:%M:%S",
                    '%Y-%m-%dT%H:%M:%S.%f',
                    '%Y年%m月%d日',
                    "%Y-%m-%d %H:%M",
                    "%Y-%m-%dT%H:%M",
                    ]

    if date_string == '' or date_string == '-':
        return None

    for date_format in date_formats:
        try:
            return datetime.strptime(date_string, date_format)
        except ValueError:
            continue

    # 如果没有格式匹配，返回 None 或抛出异常
    return None


# 获取时间区间
def get_publish_time_range(begin_date, end_date):
    publish_date = None
    publish_end_date = None

    if begin_date:
        try:
            publish_date = datetime.strptime(begin_date.replace('Z', ''),
                                             '%Y-%m-%dT%H:%M:%S.%f')
        except Exception:
            publish_date = datetime.strptime(begin_date.replace('Z', ''),
                                             '%Y-%m-%d %H:%M:%S')

    if end_date:
        try:
            publish_end_date = datetime.strptime(end_date.replace('Z', ''),
                                                 '%Y-%m-%dT%H:%M:%S.%f')
        except Exception:
            publish_end_date = datetime.strptime(end_date.replace('Z', ''),
                                                 '%Y-%m-%d %H:%M:%S')

    return publish_date, publish_end_date


# 将字典中具有相同健的值合并一下
def merge_dicts_values(dict1, dict2):
    # 创建一个新的字典来存储结果
    merged_dict = {}

    # 获取两个字典中所有键的唯一集合
    all_keys = set(dict1.keys()).union(dict2.keys())

    # 遍历所有的键
    for key in all_keys:
        # 如果键在两个字典中都存在，则合并它们的值
        if key in dict1 and key in dict2:
            if dict1[key] is not None and dict2[key] is not None:
                merged_dict[key] = f"{dict1[key]} {dict2[key]}"
        # 如果键只在一个字典中存在，则保持原样
        elif key in dict1:
            merged_dict[key] = dict1[key]
        else:
            merged_dict[key] = dict2[key]

    return merged_dict


# 把文件转换为 base64 编码
def convert_excel_to_base64(file_path):
    with open(file_path, "rb") as file:
        encoded_string = base64.b64encode(file.read())
        return encoded_string.decode()


# 分割包含多种字符和符号的文本，包括但不限于中英文混合的文本
def extract_segments_generic(text):
    # 使用正则表达式匹配任何非字母数字的字符序列作为分隔符
    segments = re.split(r'\W+', text)
    # 移除空字符串
    segments = [segment for segment in segments if segment]
    return segments


def md5(value):
    return hashlib.md5(value.encode()).hexdigest()


# 根据 url 下载文件
async def download_file(url):
    # 先下载到本地
    random_str = str(uuid.uuid1())
    file_path = os.environ.get('IMAGE_PATH', f'temp/{random_str}/')
    if not os.path.exists(file_path):
        os.makedirs(file_path)

    response = await requests.get(url)

    filename = os.path.join(file_path, '1.jpg')
    with open(filename, "wb") as file:
        file.write(response.content)

    return filename


# 合并2张图像为一张
async def merge_two_images(url_1, url_2):
    files = []
    for url in [url_1, url_2]:
        if url.startswith('http'):
            filename = await download_file(url)
        else:
            filename = url
        files.append(filename)

    # 打开图像文件
    image1 = Image.open(files[0])
    image2 = Image.open(files[1])

    # 获取图像的尺寸
    image1_size = image1.size
    image2_size = image2.size

    # 创建一个新的图像，尺寸等于两个图像宽度的和以及最高的高度
    new_image = Image.new('RGB', (image1_size[0] + image2_size[0], max(image1_size[1], image2_size[1])),
                          (250, 250, 250))

    # 将两个图像粘贴到新图像中
    new_image.paste(image1, (0, 0))
    new_image.paste(image2, (image1_size[0], 0))

    # 保存新图像
    new_file_path = os.environ.get('IMAGE_PATH', f'temp/{str(uuid.uuid1())}/new.jpg')
    if not os.path.exists(os.path.dirname(new_file_path)):
        os.makedirs(os.path.dirname(new_file_path))
    new_image.save(new_file_path)

    return new_file_path


# 去重文本中的 html 标签
def remove_html_tags(text):
    text = html.unescape(text)
    clean_text = re.sub('<.*?>', '', text)
    return clean_text


def sm3_new(text=""):
    hex_hash = sm3.sm3_hash(func.bytes_to_list(bytes(text, encoding='utf-8')))
    hash_bytes = bytes.fromhex(hex_hash)
    base64_hash = base64.b64encode(hash_bytes).decode('utf-8')
    return base64_hash


# 通过无头浏览器获取 Cookie 值
def get_cookie_value(url, cookie_name):
    with sync_playwright() as playwright:
        # 启动浏览器
        browser = playwright.chromium.launch()
        # 打开一个新页面
        page = browser.new_page()
        # 导航到指定的URL
        page.goto(url)
        # 获取所有的cookies
        cookies = page.context.cookies()
        # 关闭浏览器
        browser.close()
        # 遍历cookies以找到对应的cookie值
        for cookie in cookies:
            if cookie['name'] == cookie_name:
                return cookie['value']
        return None


# 让字符串中间的几位变成 *
def mask_string(s, start, end, mask_char='*'):
    return s[:start] + mask_char * (end - start) + s[end:]


if __name__ == '__main__':
    pass
