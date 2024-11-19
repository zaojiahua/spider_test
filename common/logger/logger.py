import os
from loguru import logger
import datetime

log_path = '/Users/Admin/Desktop/spider_log'
# if not os.path.exists(log_path):
#     os.mkdir(log_path)
log_template = '[spider] {0}  [time] {1}  [params] {2}  [info] {3}'  # 日志模板

log_file = '{0}/spider_{1}_log.log'.format(log_path, datetime.datetime.now().strftime('%Y-%m-%d'))

logger.add(log_file, rotation="06:00", retention="7 days", enqueue=True, encoding='utf-8')
