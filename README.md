# cs-rpa

京东咚咚网页客服的本地离线复刻与 Playwright DOM 自动化验证项目。

当前主要入口为基于真实页面 observation 重建的本地工作台 v2。服务使用合成客户和固定模板，不连接京东或 OpenClaw。旧 Windows UIA / 客户端探测代码保留用于历史研究，不属于新版模拟测试路径。

## 快速开始

Python 3.12：

```sh
python -m venv .venv
# Activate the virtual environment for your platform, then:
pip install -r requirements.txt
python -m playwright install chromium
python -m mock_dongdong serve
```

工作台：http://127.0.0.1:18766/workbench

客户控制台：http://127.0.0.1:18766/control

可在 Codex 内置浏览器打开。HTTP 服务仅依赖 Python 标准库；Playwright 用于独立 DOM 回归。

## 验证

```sh
python -m unittest discover -s tests -v
python -m mock_dongdong demo --channel chromium
```

Windows 已安装 Edge 时可以直接 `python -m mock_dongdong demo`。默认无窗口执行，测试报告与截图位于 `artifacts/replica-v2-<timestamp>/`。详情及已知限制见 [OFFLINE-DEMO.md](OFFLINE-DEMO.md)；真实页面采集依据见 [jingmai-dom-observations.md](jingmai-dom-observations.md)。

Windows 统一启动脚本为 `run.cmd`，优先使用项目 `.venv`，否则使用 PATH 中的 Python：`run.cmd serve` 启动服务，`run.cmd demo` 执行回归，`run.cmd --help` 查看所有命令。旧的 `run-*.cmd` 和根目录 Python 入口已合并，不再保留重复别名。

## 目录

- `mock_dongdong/`：离线工作台、客户控制台、HTTP 服务和合成数据。
- `mock_dongdong/rpa.py`：DOM 读取、模板匹配、输入和发送驱动。
- `mock_dongdong/demo.py`：多客户与异常场景回归，通过 `python -m mock_dongdong demo` 执行。
- `tests/`：存储层和命令入口测试。
- `legacy/`：历史 Windows 客户端 / 浏览器适配实验；`legacy/probes/` 集中保存独立 UI 探测工具。入口迁移表见 [legacy/README.md](legacy/README.md)。
- `openclaw-host/`：独立 OpenClaw 设备的历史桥接与知识配置工具。
- `guide.md`：业务需求记录，未实现功能不代表已经可用。

## 本地配置与数据

仓库不包含运行日志、截图、浏览器用户数据、聊天记录、客服 CSV 原始资料和设备配置。内部客服知识及策略文件需自行部署；`openclaw-host` 下工具引用的业务资料不随代码发布。

主线 DOM 回归依赖见 `requirements.txt`，历史 Windows 适配依赖单独放在 `legacy/requirements.txt`。使用历史入口前，将 `config.example.yaml` 复制为项目根目录的 `config.yaml` 并配置设备和服务地址；`legacy/config.py` 统一读取配置及可选的 `config.local.yaml` 浅层覆盖。默认示例关闭自动发送。新版离线服务不读取该配置。

本地复刻只验证已覆盖的 DOM 与模拟交互，不代表真实平台发送、接待、未读、分页或所有前端状态已验证。

## 第三方资源

离线分发的 Lucide 0.468.0 图标库许可证见 `mock_dongdong/web/lucide.LICENSE`。头像和开发板示意图为本项目替代资源，不包含真实客户资料。
