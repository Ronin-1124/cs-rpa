# 历史 Windows 适配与诊断

这里保留千牛、京麦客户端和旧浏览器适配研究。当前离线复刻入口在 `mock_dongdong/`，不依赖这些模块。历史工具按用途归档，不把不同 UI 探测手段当作重复功能删除。

在项目根目录使用 `python -m ...` 运行，安装依赖：

```powershell
python -m pip install -r legacy/requirements.txt
```

`config.yaml`、可选的 `config.local.yaml`、`artifacts/` 和浏览器用户数据仍位于项目根目录。`paths.py` 统一定位根目录，`config.py` 统一读取配置。原来只读主配置的校准和基础适配入口现在也遵循相同的本地覆盖规则。

## 入口迁移

| 原入口 | 现入口 |
|---|---|
| `run_cs.py` / `run-cs.cmd` | `python -m legacy.run` |
| `run-jm.cmd` | `python -m legacy.run --platform jingmai` |
| `main.py` / `run-watch.cmd` | `python -m legacy.watch_notifications` |
| `fill_input.py` / `run-fill.cmd` | `python -m legacy.fill_input` |
| `calibrate.py` | `python -m legacy.calibrate` |
| `watch_qn_inbound.py` | `python -m legacy.watch_qn_inbound` |
| `run-restore-jm.cmd` | `python -m legacy.ui.web_jingmai restore` |
| `probe_*.py`（除下面的兼容别名） | `python -m legacy.probes.probe_...` |
| `offline_demo.py` / `probe_jm_playwright.py` / `run-jm-mock.cmd` / `run-offline-demo.cmd` | `python -m mock_dongdong demo` |
| `run-mock.cmd` | `python -m mock_dongdong serve` |

`watch_notifications` 按通知处理；`run` 遍历会话后轮询；`watch_qn_inbound` 只读观察。这三种模式用途不同，分别保留。是否发送以实际配置和适配代码为准。

`probes/` 中 `probe_qn_*` 用于千牛，`probe_jm_*`、`probe_jingmai*` 用于京麦，其余主要研究输入、粘贴、光标和菜单行为。它们需要对应 Windows 应用或已有截图，不属于自动测试，也不会被主线入口导入。

已删除仅用于停用 UIA 模拟流程的 `offline_replies.py`、旧模拟服务启动逻辑、无调用的兼容函数及空处理函数。OpenClaw 设备侧工具仍集中在根目录 `openclaw-host/`，与本机适配分开维护。
