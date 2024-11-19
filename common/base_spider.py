import asyncio
import datetime
from abc import ABCMeta, abstractmethod
import logging

from typing import Dict, List, Any, NoReturn

from common.logger.logger import logger
from common.logger.logger import log_template

logging.basicConfig(level=logging.INFO)


class BaseSpider(metaclass=ABCMeta):
    """爬虫公共基类"""

    def __init__(self, spider_params) -> NoReturn:
        """
            构造方法
            参数:
                spider_params: 爬虫配置相关参数 包括max_retry_times和download_delay_time
            返回值：
                None
        """
        self.spider_params = spider_params
        # 和爬取下来的每条记录做关联
        self.spider_page_config_id = None
        self.position_web_url = None
        # 记录当前该网站所有的岗位，就是当下最新的所有的岗位
        self.current_ids = None
        # 之前已经存在的所有岗位，就是库里边该网站的所有岗位
        self.exist_ids = []
        # 记录列表的爬取过程中是否有错误
        self.spider_page_list_results = []

    @abstractmethod
    async def _downloader(self, request_params: Dict[str, Any]) -> Dict[str, Any]:
        """
            数据爬取方法
            参数:
                request_params: 爬虫爬取相关参数
            返回值:
                下载器下载到的数据 字典类型 键为 html json 或者 bytes_stream 如果爬取失败返回 None
        """

    # 下载列表数据
    async def _downloader_page_list(self, request_params):
        """
            数据爬取方法
            参数:
                request_params: 爬虫爬取相关参数
            返回值:
                下载器下载到的数据 字典类型 键为 html json 或者 bytes_stream 如果爬取失败返回 None
        """

    @abstractmethod
    async def _parser(self, request_params: Dict[str, Any], response: Dict[str, Any]) -> List[Any]:
        """
            数据解析方法
            参数:
                response: 下载器返回的内容，字典类型
            返回值:
                解析出的数据列表 List类型 如果解析失败返回None
        """

    # 解析列表
    async def _parser_page_list(self, request_params, response) -> List[Any]:
        """
            数据解析方法
            参数:
                response: 下载器返回的内容，字典类型
            返回值:
                解析出的数据列表 List类型 如果解析失败返回None
        """

    # 爬取之前，用来判断是否要爬取
    async def _pipeline_before(self, request_params=None) -> bool:
        pass

    # 入库之前对数据进行处理
    @staticmethod
    async def _data_process(data):
        return data

    # 入库方法，全部一样，所以提取到这个地方，子类需要自己实现的话重新实现，但是大部分情况应该是不用的
    async def _pipeline(self, data) -> bool:
        """
            数据管道方法
            参数:
                data: 解析出的数据 List类型
            返回值:
                数据入库状态 已入库返回True 入库失败返回False
        """
        logger.info(
            log_template.format(self.__class__.__name__, datetime.datetime.now(), "", "更新数据：{} 条".format(1)))

        return True

    # 入库逻辑
    async def _pipeline_page_list(self, data) -> bool:
        """
            数据管道方法
            参数:
                data: 解析出的数据 List类型
            返回值:
                数据入库状态 已入库返回True 入库失败返回False
        """
        pass

    async def spider_next(self, request_params: Dict[str, Any] = None) -> NoReturn:
        """
            爬虫引擎
            参数：
                request_params: 爬虫请求参数，字典类型
            返回值：
                无
        """
        class_name = self.__class__.__name__  # 获取爬虫类名

        # 获取配置信息或设置默认参数
        max_retry_times = self.spider_params.get('max_retry_times') or 3  # 最大下载重试次数 默认3次
        download_delay_time = self.spider_params.get('download_delay_time') or 3  # 下载器休眠时间

        success = True

        while True:
            response = None
            # 下载过程
            for i in range(max_retry_times):
                logger.info(log_template.format(class_name, datetime.datetime.now(), request_params, '第{}次请求'.format(i + 1)))
                try:
                    response = await self._downloader(request_params)
                    await asyncio.sleep(download_delay_time)
                    if response:
                        break
                except Exception as e:
                    await asyncio.sleep(download_delay_time)
                    response = None
                    break

            if not response:  # 多次尝试下载均失败的情况
                logger.error(log_template.format(class_name, datetime.datetime.now(), request_params, '下载失败'))
                return False
            else:
                logger.info(log_template.format(class_name, datetime.datetime.now(), request_params, '下载成功'))

            # 解析过程
            flag, data = await self._parser(request_params, response)
            if not data:
                logger.error(log_template.format(class_name, datetime.datetime.now(), request_params, '解析失败'))
            elif len(data) == 1 and isinstance(data[0], dict) and data[0].get('error_info'):
                logger.error(log_template.format(class_name, datetime.datetime.now(), request_params, '解析失败: ' +
                                                 data[0].get('error_info')))
            else:
                logger.info(log_template.format(class_name, datetime.datetime.now(), request_params, '解析成功'))

            # 入库过程
            if data and len(data) > 0 and data[0].get('error_info') is None:
                for d in data:
                    data = await self._data_process(d)
                    await self._pipeline([data])
                success = True
            else:
                success = False

            # 标识是否继续请求
            if not flag:
                break

        return success

    async def spider_page_list(self, request_params: Dict[str, Any] = None) -> NoReturn:
        """
            爬虫引擎, 包含翻页 逻辑
            参数：
                request_params: 数据库中读取到的相关页面配置信息
            返回值：
                无
        """
        class_name = self.__class__.__name__  # 获取爬虫类名

        # 获取配置信息或设置默认参数
        max_retry_times = self.spider_params.get('max_retry_times') or 3  # 最大下载重试次数 默认3次
        download_delay_time = self.spider_params.get('download_delay_time') or 3  # 下载器休眠时间

        success = True

        while True:
            response = None
            # 下载过程
            for i in range(max_retry_times):
                logger.info(log_template.format(class_name, datetime.datetime.now(), request_params, '第{}次请求'.format(i + 1)))
                response = await self._downloader_page_list(request_params)
                await asyncio.sleep(download_delay_time)
                if response:
                    break

            if not response:  # 多次尝试下载均失败的情况
                logger.error(log_template.format(class_name, datetime.datetime.now(), request_params, '下载失败'))
                return False
            else:
                logger.info(log_template.format(class_name, datetime.datetime.now(), request_params, '下载成功'))

            # 解析过程
            flag, data = await self._parser_page_list(request_params, response)
            if not data:
                logger.error(log_template.format(class_name, datetime.datetime.now(), request_params, '解析失败'))
            elif len(data) == 1 and isinstance(data[0], dict) and data[0].get('error_info'):
                logger.error(log_template.format(class_name, datetime.datetime.now(), request_params, '解析失败: ' +
                                                 data[0].get('error_info')))
            else:
                logger.info(log_template.format(class_name, datetime.datetime.now(), request_params, '解析成功'))

            # 入库过程
            if data and len(data) > 0 and data[0].get('error_info') is None:
                await self._pipeline_page_list(data)
                success = True
            else:
                success = False

            if not flag:  # 标识是否继续请求
                break

        return success
