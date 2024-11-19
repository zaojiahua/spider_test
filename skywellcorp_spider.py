# -*- coding:utf-8 -*-
import asyncio
import datetime
import traceback

from typing import Dict, NoReturn, Any

from common.config import spider_max_month
from util.requests_util import AsyncRequests as requests
from common.logger.logger import logger, log_template
from common import config
from common.base_spider import BaseSpider
from util.utils import parse_date


class SkyWellCorpSpider(BaseSpider):

    def __init__(self, model=None, spider_params=None) -> NoReturn:
        super().__init__(spider_params or config.spider_params)

        self.spider_params = spider_params or config.spider_params
        self.page_index = 0
        self.page_size = 100
        self.position_web_url = None
        self.position_url = None
        self.post_id = None
        self.cls = None
        self.spider_page_config_id = None
        self.position_list_req_data = None
        self.position_web_url_format = None

    # 解析单个岗位信息
    def parse_item(self, position_data):
        data = {
            # 代表岗位名称
            'job_title': position_data['title'],
            # 类型 0 校招 1 实习 2 社招
            'class': self.cls,
            # 工资
            'salary': None,
            # 职责
            'responsibility': position_data['description'],
            # 要求
            'raw_position_require': position_data['requirements'],
            # 解析以后的要求
            'position_require': {
                # 有的可以解析出来学历
                'degree': position_data.get('degree'),
                # 有的可以解析出来专业
                'major': None
            },
            # 发布日期
            'publish_date': position_data.get('createTime'),
            # 截止时间
            'expire_date': None,
            # 工作地点
            'address': position_data.get('workAddress'),
            # 爬取时间，不动
            'spider_time': datetime.datetime.now(),
            # 请求单个的那个数据 url
            'position_url': self.position_url,
            # 工作类型
            'job_type': None,
            # 岗位 id
            'post_id': position_data['id'],
            # 公司名称或者是部门名称或者是项目名称
            'company_name': position_data.get('departName'),
            # 该条数据对应的网页 url，别人点开这个链接，能打开这个岗位
            'position_web_url': self.position_web_url,
            # 招聘人数
            'num_hire': None,
            # 不用动
            'page_list_config_id': self.spider_page_config_id
        }

        for item_key in data:
            try:
                if item_key == 'publish_date' or item_key == 'expire_date':
                    data[item_key] = parse_date(data[item_key])
            except Exception:
                pass

        return data

    # 解析单个数据
    async def _parser(self, request_params: Dict[str, Any], response: Dict[str, Any]):
        flag = False

        try:
            if response:
                data = self.parse_item(response)
            else:
                data = {'error_info': response}
        except Exception as e:
            traceback.print_exc()
            data = {'error_info': str(e)}

        return flag, [data]

    # 下载单个数据
    async def _downloader(self, request_params: Dict[str, Any],) -> Dict[str, Any]:
        # res = await requests.post(self.position_url,
        #                           json={
        #                               'id': self.post_id
        #                           },
        #                           proxies=request_params["proxies"],
        #                           timeout=60)
        #
        # return res.json()
        return self.position_data

    # 对列表进行解析，解析的过程中，去爬取单个的数据
    async def _parser_page_list(self, request_params, response):
        flag = False

        try:
            resume_url = self.position_url

            if response.get('code') == 200:
                for position_data in (response.get('result', {}).get('records', []) or []):
                    flag = True

                    # 只爬取 6 个月之内的数据 无相关数据
                    if position_data.get('createTime'):
                        six_months_ago = datetime.datetime.now() - datetime.timedelta(days=30 * spider_max_month)
                        if six_months_ago > parse_date(position_data['createTime']):
                            continue

                    # 请求单个页面
                    self.post_id = position_data['id']
                    # 这里必须写，因为是根据这个来判断是否爬取过
                    self.position_web_url = self.position_web_url_format.format(position_data)
                    # self.position_url = f'https://hr.cctc.cc/prod-api/post/info?id={self.post_id}'
                    self.position_data = position_data
                    await self.spider_next(request_params)

                self.position_url = resume_url
                self.page_index += 1
                data = [{'success_info': f'第 {self.page_index} 页解析成功！'}]
            else:
                data = [{'error_info': response.get('message')}]
        except Exception as e:
            traceback.print_exc()
            data = [{'error_info': str(e)}]

        return flag, data

    # 这个地方是下载列表
    async def _downloader_page_list(self, request_params):
        logger.info(f'当前处理的页数是：{self.page_index}')

        self.position_list_req_data['pageNo'] = self.page_index + 1
        res = await requests.post(self.position_url,
                                  json=self.position_list_req_data,
                                  proxies=request_params.get('proxies'),
                                  timeout=60)

        return res.json()

    # 这个函数是入口函数
    async def run_page_list(self, page_config={}):
        # 分别爬取 3 类数据。 0 校招 1 实习 2 社招 分页爬取
        # 这个地方需要构建好，爬取这三类数据时候的请求参数
        for position_info in [({
                                   'type': "2",
                                   'pageNo': 1,
                                   'pageSize': self.page_size
                               }, 0, 'https://www.skywellcorp.com/jobDetail?detail={}'),
                              ({
                                   'type': "1",
                                   'pageNo': 1,
                                   'pageSize': self.page_size
                              }, 2, 'https://www.skywellcorp.com/jobDetail?detail={}')]:

            self.position_url = page_config.get('page_list_url') or 'https://www.skywellcorp.com/api/recruit/list'
            self.position_list_req_data = position_info[0]
            self.cls = position_info[1]
            self.position_web_url_format = position_info[2]

            self.page_index = 0

            spider_result = await super().spider_page_list(page_config)
            if spider_result:
                logger.info(f'爬取列表完成：{position_info[0]}')


if __name__ == '__main__':
    spider = SkyWellCorpSpider()

    asyncio.run(spider.run_page_list())
