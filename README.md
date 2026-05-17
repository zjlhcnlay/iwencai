# 问财选股 API 客户端

基于 [同花顺问财](https://www.iwencai.com/) 网页端接口的自然语言选股工具。通过 Python 调用问财 `get-robot-data` 接口，使用 Node.js 运行 `hexin-v.js` 生成反爬请求头 `hexin-v`（与 cookie `v` 相同）。

## 功能

- 自然语言选股查询（与问财网页输入条件一致）
- 自动生成 `hexin-v` 指纹（chameleon 算法，见 `hexin-v.js`）
- 解析返回 JSON 中的 `xuangu_tableV1` 股票表格
- 支持命令行与 Python 模块两种用法

## 环境要求

| 依赖 | 说明 |
|------|------|
| Python 3.10+ | 运行 `iwencai_api.py` |
| Node.js | 调用 `hexin-v.js` 生成 token |
| 网络 | 可访问 `www.iwencai.com` |

## 安装

```bash
git clone <你的仓库地址>
cd mxbc
pip install -r requirements.txt
```

确认 Node 可用：

```bash
node -v
```

## 快速开始

### 命令行

```bash
# 使用默认查询条件
python iwencai_api.py

# 自定义自然语言条件
python iwencai_api.py "剔除st,剔除科创板,剔除创业板,剔除新股,连板数大于1的股票"
```

### 作为模块

```python
from iwencai_api import IwencaiClient

client = IwencaiClient()
result = client.search_stocks("连板数大于1的股票")
stocks = client.extract_stock_table(result)

for row in stocks:
    print(row.get("股票简称"), row.get("股票代码"), row.get("最新价"))
```

## hexin-v 工具（Node）

单独加解密 token：

```bash
# 解密已有 hexin-v / cookie v
node hexin-v.js <token>
```

在代码中引用：

```javascript
const { buildFingerprint, encodeHexinV, decodeHexinV } = require('./hexin-v.js');

const fields = buildFingerprint({
  serverTime: 1715900000,
  userAgent: 'Mozilla/5.0 ...',
});
const token = encodeHexinV(fields);
```

算法参考：[chameleon.1.9.min.js](https://s.thsi.cn/js/chameleon/chameleon.1.9.min.js)

## 项目结构

```
mxbc/
├── iwencai_api.py    # 问财 API 客户端（主入口）
├── hexin-v.js        # hexin-v 加解密与指纹生成
├── requirements.txt  # Python 依赖
├── chameleon.js      # 问财前端脚本（参考）
├── index-*.js        # 问财前端打包文件（参考）
└── vendor-*.js
```

## 工作流程

```
访问 screener 页（预热）
    → 获取 TOKEN_SERVER_TIME、other_uid(rsh)、Cookie
    → Node 执行 hexin-v.js 生成 hexin-v
    → POST get-robot-data
    → 解析 xuangu_tableV1
```

真正返回选股数据的是 `get-robot-data`；访问 `/screener` 主要用于对齐服务器时间、会话标识与 Cookie，提高请求成功率。

## API 说明

| 类 / 函数 | 说明 |
|-----------|------|
| `IwencaiClient` | 客户端，维护 Session |
| `search_stocks(question, page=1, perpage=50)` | 发起选股查询，返回原始 JSON |
| `extract_stock_table(data)` | 从 JSON 中提取股票行列表 |
| `generate_hexin_v()` | 生成当前请求的 hexin-v |

## 注意事项

- 本项目仅供学习与研究，请遵守问财/同花顺服务条款，勿用于高频爬取或商业用途。
- 问财接口与风控策略可能变更，导致请求失败，需自行维护。
- 当前 HTTPS 校验为 `verify=False`，仅便于调试；生产环境建议配置证书校验。
- 字段名（如 `连续涨停天数[20260515]`）可能随交易日变化，解析时请做兼容。

## License

未指定许可证时，默认保留所有权利；如需开源请自行添加 LICENSE 文件。
