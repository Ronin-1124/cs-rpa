# 咚咚本地复刻 v2

基于[真实页面观测](jingmai-dom-observations.md)重建，提供独立模拟 HTTP 服务和 Playwright 模板回归。以下命令均在项目根目录执行，日常接待使用 `run.cmd serve` 启动完整应用。

## 启动

```powershell
.venv\Scripts\python.exe -m mock_dongdong serve
```

在 Codex 内打开：

- 工作台：http://127.0.0.1:18766/workbench
- 客户控制台：http://127.0.0.1:18766/control

独立模拟服务默认使用 18766 端口，与完整应用默认端口相同，不应同时启动。独立数据文件为 `artifacts/dongdong-replica-v2.json`；完整应用的模拟数据默认在 `artifacts/app/mock.json`。

## 页面验证

客户控制台可以创建客户、选择模板并发送客户消息。工作台通过轮询收到列表更新；历史咨询、联系人搜索、仅未读过滤、分组折叠、切换会话、草稿恢复、快捷话术填入、表情、Enter / Ctrl+Enter 发送菜单和发送回复可用。每个浏览器标签独立保存选中客户及草稿。

控制台不会自动回复。`mock_dongdong/rpa.py` 只通过 Playwright 定位、读取、填写、点击，代码中不调用消息 API，也不连接 OpenClaw。`mock_dongdong/demo.py` 注入两位合成客户的三次问题，并调用这个驱动回复，通过本地 API核对实际存储结果。

```powershell
.venv\Scripts\python.exe -X utf8 -m mock_dongdong demo
```

默认测试浏览器无窗口，需要独立窗口时传 `--headed`。Windows 默认使用已安装的 Edge；Linux 默认 Chromium，安装依赖：`pip install playwright`、`python -m playwright install --with-deps chromium`。跨平台部署尚未完整验证。

统一入口为 `python -m mock_dongdong demo`，Windows 也可使用 `run.cmd demo`。

## 复刻边界

已按观测复刻：五栏布局和主要尺寸、导航 div、隐藏但保留的 tabpane、最近联系人层级、异步标题/正文更新、消息方向、消息 ID、时间、正文 span、已读状态、链接、商品卡片、撤回提示、分隔线、contenteditable 编辑器、span 发送控件和快捷键菜单。

观测没有证实的行为仍为本地夹具：当前咨询行复用已确认的历史联系人结构；未读使用显式 `replica-unread` 类；网络延迟固定为 250ms；已读状态、发送确认和去重由本地服务模拟。历史一次性加载，未复刻分页/虚拟滚动；没有独立图片消息样本。未接入真实转接、图片/文件上传、团队管理及插件。对应辅助区仅保留外观。

本地产品为示意图，头像、图标及测试消息均为合成/替代资源，未复制客户个人资料。Lucide 0.468.0 已随项目保存，页面运行不需要外网。页面 CSP 禁止外部脚本、图片、网络和 iframe。窄屏保留工作台最小宽度并横向滚动，不把聊天工具缩成无法操作的小控件；这属于本地适配，不代表已采集真实移动端规则。

这是一版观测驱动的 DOM 与交互复刻，尚不宣称真实页面逐像素、所有状态一比一。通过本地测试只能证明当前覆盖的 DOM 场景可用，不能代替真实发送验证。

## 回归覆盖

每次运行将结果写到 `artifacts/replica-v2-<时间>/report.json`，附桌面和窄屏截图。覆盖多客户三次回复、刷新后不重复回复、草稿恢复、两个窗口独立选中、快速切换、发送确认丢失后重试去重、Enter 发送、文本转义、商品错误卡片/系统消息/分隔线，以及页面错误和外部请求检查。驱动直接使用 observation 的类名，未重新添加旧的 `#header`、`#wrap`、`#editor`、`#send` 或人工 ARIA role。

单元测试：`python -m unittest discover -s tests -v`，验证已读请求不清除之后到达的新消息、发送重试绑定客户且不会重复、重置保持修订号递增及命令入口可用。

2026-09-07 在 Codex 内置浏览器也实际完成了客户控制台创建客户、发送模板问题、工作台 DOM 读取问题及填入模板、点击发送，并核对控制台与工作台出现同一条回复。此项为浏览器操作验证；独立 RPA 驱动的回归结果见上述 report.json。
