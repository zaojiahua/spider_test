import os

user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.106 Safari/537.36'


# 爬虫默认参数
spider_params = {
    'max_retry_times': 3,  # 最小值为1
    'download_delay_time': 0.1,
    'download_timeout': 30,
}

spider_max_month = 6

