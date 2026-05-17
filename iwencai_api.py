"""
问财选股 API Python 客户端

示例:
    python iwencai_api.py "剔除 st,剔除科创板,剔除创业板,剔除新股,连板数大于1的股票"
"""

from __future__ import annotations

import json
import re
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

import requests

_HEXIN_JS = Path(__file__).resolve().parent / "hexin-v.js"


def parse_token_server_time(html: str) -> int | None:
  m = re.search(r"TOKEN_SERVER_TIME\s*=\s*([\d.]+)", html)
  if not m:
    return None
  return int(float(m.group(1)))


def generate_hexin_v_via_js(*, server_time: int, user_agent: str) -> str:
  """调用 hexin-v.js 生成 hexin-v / cookie v。"""
  opts = json.dumps({"serverTime": server_time, "userAgent": user_agent})
  script = (
      "const { buildFingerprint, encodeHexinV } = require(process.argv[1]);"
      "const fields = buildFingerprint(JSON.parse(process.argv[2]));"
      "process.stdout.write(encodeHexinV(fields));"
  )
  proc = subprocess.run(
      ["node", "-e", script, str(_HEXIN_JS), opts],
      capture_output=True,
      text=True,
      cwd=_HEXIN_JS.parent,
      check=False,
  )
  if proc.returncode != 0:
    raise RuntimeError(
        f"hexin-v.js failed: {proc.stderr.strip() or proc.stdout.strip()}"
    )
  token = proc.stdout.strip()
  if not token:
    raise RuntimeError("hexin-v.js returned empty token")
  return token

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
)

ROBOT_DATA_URL = "https://www.iwencai.com/unifiedwap/unified-wap/v2/result/get-robot-data"
SCREENER_URL = "https://www.iwencai.com/screener"


class IwencaiClient:
  def __init__(
      self,
      user_agent: str = DEFAULT_UA,
      session: requests.Session | None = None,
      timeout: float = 30,
  ):
    self.user_agent = user_agent
    self.timeout = timeout
    self.session = session or requests.Session()
    self._server_time: int | None = None
    self._rsh: str | None = None

  def _ensure_session(self) -> None:
    if self._server_time is not None:
      return
    resp = self.session.get(
        SCREENER_URL,
        headers={"User-Agent": self.user_agent},
        timeout=self.timeout,
        verify=False,
    )
    resp.raise_for_status()
    self._server_time = parse_token_server_time(resp.text) or int(time.time())
    m = re.search(r"other_uid=([^;\"'\s]+)", resp.text)
    if m:
      self._rsh = m.group(1)
    elif "other_uid" in self.session.cookies:
      self._rsh = self.session.cookies.get("other_uid")
    else:
      self._rsh = f"Ths_iwencai_Xuangu_{uuid.uuid4().hex}"

  def generate_hexin_v(self) -> str:
    self._ensure_session()
    return generate_hexin_v_via_js(
        server_time=self._server_time or int(time.time()),
        user_agent=self.user_agent,
    )

  def _headers(self, hexin_v: str, question: str) -> dict[str, str]:
    referer = (
        "https://www.iwencai.com/screener/result?"
        f"w={quote(question)}&querytype=stock&sign={int(time.time() * 1000)}"
    )
    return {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://www.iwencai.com",
        "Referer": referer,
        "User-Agent": self.user_agent,
        "hexin-v": hexin_v,
    }

  def _body(
      self,
      question: str,
      *,
      page: int = 1,
      perpage: int = 50,
      secondary_intent: str = "stock",
  ) -> str:
    self._ensure_session()
    add_info = json.dumps(
        {
            "urp": {"scene": 1, "company": 1, "business": 1},
            "contentType": "json",
            "searchInfo": True,
        },
        separators=(",", ":"),
    )
    log_info = json.dumps({"input_type": "click"}, separators=(",", ":"))
    params = {
        "source": "Ths_iwencai_Xuangu",
        "version": "2.0",
        "query_area": "",
        "block_list": "",
        "add_info": add_info,
        "question": question,
        "perpage": str(perpage),
        "page": str(page),
        "secondary_intent": secondary_intent,
        "log_info": log_info,
        "rsh": self._rsh or "",
    }
    return urlencode(params)

  def search_stocks(
      self,
      question: str,
      *,
      page: int = 1,
      perpage: int = 50,
  ) -> dict[str, Any]:
    """
    自然语言选股查询，返回 get-robot-data 接口 JSON。
    """
    hexin_v = self.generate_hexin_v()
    self.session.cookies.set("v", hexin_v, domain=".iwencai.com")

    resp = self.session.post(
        ROBOT_DATA_URL,
        data=self._body(question, page=page, perpage=perpage),
        headers=self._headers(hexin_v, question),
        timeout=self.timeout,
        verify=False,
    )
    resp.raise_for_status()
    return resp.json()

  def extract_stock_table(self, data: dict[str, Any]) -> list[dict[str, Any]]:
    """从响应中解析 xuangu_tableV1 股票列表。"""
    rows: list[dict[str, Any]] = []
    for answer in data.get("data", {}).get("answer", []) or []:
      for block in answer.get("txt", []) or []:
        if block.get("type") != "global-result":
          continue
        for comp in block.get("content", {}).get("components", []) or []:
          if comp.get("show_type") != "xuangu_tableV1":
            continue
          table = comp.get("data", {})
          rows.extend(table.get("datas") or [])
    return rows


def main() -> None:
  import sys

  question = (
      sys.argv[1]
      if len(sys.argv) > 1
      else "剔除st,剔除科创板,剔除创业板,剔除新股,连板数大于1的股票"
  )
  client = IwencaiClient()
  result = client.search_stocks(question)
  stocks = client.extract_stock_table(result)

  print(f"查询: {question}")
  print(f"状态: {result.get('status_msg', result.get('status_code'))}")
  print(f"共 {len(stocks)} 条结果:\n")

  for i, row in enumerate(stocks, 1):
    code = row.get("股票代码") or row.get("code", "")
    name = row.get("股票简称") or row.get("name", "")
    price = row.get("最新价", "")
    ratio = row.get("最新涨跌幅", "")
    boards = row.get("连续涨停天数[20260515]") or row.get("连续涨停天数", "")
    print(f"{i:2}. {name} ({code})  价:{price}  涨跌:{ratio}%  连板:{boards}")


if __name__ == "__main__":
  main()
