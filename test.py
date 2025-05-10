import curl_cffi as requests
from urllib.parse import urlencode

url = "https://drrr.com/room/?ajax=1"

headers = {
    "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.6045.160 Safari/537.36",
    "x-requested-with": "XMLHttpRequest"
}

proxies = {
    'http': 'http://127.0.0.1:7890',
    'https': 'http://127.0.0.1:7890'
}

cookies = {
    "drrr-session-1": "32mahm4saoo7k1r2l45qfivpu1",
    "cf_clearance": "6MVbt6fChVMiLbyxG4U3dhd.6qtUFElaytfKXdzH5tc-1746882111-1.2.1.1-Q15tDyfshg9ECPG8GekJQghqCEmMmAbn26NceyNn.Icre6sCuXGnnvndx14w6EjcHrwsRFO.28fMD.v_U4FPIol_Eh2AJ9hvpIyxciby.k2jL14NqJjSQ6x8TTR2PigNkeGrGbavSh6KW2C..ugznQV1GNMDNsinDHm0iuAlihr.6kv2ccUbOkmbRAuShBNCGIKD3.dhcuBwweAlsxBmPJrD6Dx2sBQbrIknPtr2g0Pv3q03WYJrStVEuBBEToL_AG12AfudK_dyyLJHXqcrKnaS3Vmu2gRp8zm.T1M3P0iFnBconlX9OEI7G6_Os3GCSTX9Jo88Zu0wYs5N5cgF5ApwKEZCbCrbgkCLc4F5pbBtn_hUn5N_P9j8NINbctUk"
}

data = {
    "message": "你好",
    "loadness": "",
    "url": "",
    "to": ""
}

try:
    response = requests.post(
        url,
        headers=headers,
        cookies=cookies,
        data=urlencode(data),
        proxies=proxies
    )
    print("状态码:", response.status_code)
    print("响应内容:", response.text)
except Exception as e:
    print("请求失败:", e)
