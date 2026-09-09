# 业务资料

原始 CSV 统一放在项目根目录下的 `data/raw/`，只调整文件名和位置，保留原始字节、编码、表头及行顺序。

| 当前文件 | 原始文件名 | 用途 |
| --- | --- | --- |
| `data/raw/customer-qa.csv` | `电商客服Q&A_数据表_表格.csv` | 原始客服问答 |
| `data/raw/quick-phrases.csv` | `2026-09-07快捷短语.csv` | 快捷短语导出 |
| `data/raw/kefubao-phrases.csv` | `kefubao话术.csv` | 客服宝话术导出 |

“同步项目资料”优先导入 `artifacts/knowledge/knowledge-cleaned/` 整理包；不存在整理包时才扫描 `data/raw/*.csv`。首次启动且知识库为空时自动执行同样流程。

这三份 CSV 通过项目同步导入时，来源标识仍使用原始文件名，保证与既有数据库、整理包清单及行号追溯一致；整理包内的历史来源引用不随磁盘文件改名。其他 CSV 使用自身文件名。

CSV、整理包和数据库均不提交到 Git。迁移资料时另行复制 `data/raw/` 和所需整理包；迁移已有配置与聊天记录时，先停止服务再复制 `artifacts/app/`。原始问答和话术未经核实，不代表当前库存、价格或产品支持承诺。
