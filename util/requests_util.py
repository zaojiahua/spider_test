import requests
import httpx

from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


class Requests:
    """
    二次封装 requests 请求
    """

    @staticmethod
    def get(
            url: str, headers: dict = {}, cookies: dict = None, timeout: int = 10, verify: bool = False,
            proxies: dict = None, params: dict = None,
            ):

        res = requests.get(url, headers=headers, cookies=cookies, verify=verify, proxies=proxies, timeout=timeout, params=params)
        return res

    @staticmethod
    def post(
             url: str, headers: dict = {}, cookies: dict = None, timeout: int = 10, verify: bool = False,
            proxies: dict = None, data: dict = None, json: dict = None, params: dict = None
             ):

        if json is not None:
            res = requests.post(url, headers=headers, json=json, cookies=cookies, verify=verify, proxies=proxies,
                                timeout=timeout, params=params)
        elif data is not None:
            res = requests.post(url, headers=headers, data=data, cookies=cookies, verify=verify, proxies=proxies,
                                timeout=timeout, params=params)

        else:
            raise Exception("POST请求，未传入数据！！！！")

        return res


class AsyncRequests:

    @staticmethod
    async def get(
            url: str, headers: dict = {}, cookies: dict = None, timeout: int = 10, verify: bool = False,
            proxies: dict = None, params: dict = None, follow_redirects=True
    ):
        # if proxies is None:
        #     proxies = await AsyncRequests.get_proxy()

        timeout_config = httpx.Timeout(timeout, connect=timeout)
        async with httpx.AsyncClient(headers=headers, cookies=cookies, verify=verify, proxies=proxies,
                                     timeout=timeout_config, follow_redirects=follow_redirects) as client:
            res = await client.get(url, params=params)

        return res

    @staticmethod
    async def post(
            url: str, headers: dict = {}, cookies: dict = None, timeout: int = 10, verify: bool = False,
            proxies: dict = None, data: dict = None, json: dict = None, params: dict = None, files: dict = None
    ):
        # if proxies is None:
        #     proxies = await AsyncRequests.get_proxy()

        timeout_config = httpx.Timeout(timeout, connect=timeout)
        async with httpx.AsyncClient(headers=headers, cookies=cookies, verify=verify, proxies=proxies,
                                     timeout=timeout_config) as client:
            if json is not None:
                res = await client.post(url, json=json, params=params)
            elif data is None and files is not None:
                res = await client.post(url, files=files)
            elif data is not None or files is not None:
                # 如果传入了files，它会和data一起被用于构建multipart/form-data请求体
                res = await client.post(url, data=data, params=params)
            else:
                raise ValueError("POST请求，未传入数据！")

        return res
