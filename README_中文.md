# CrewSupply Mobile Auto v2.0 稳定版

## 这版解决了什么

- 手机首页“补跑未完成账号”变量缺失导致的报错。
- 任务已结束但手机长期显示 `running / 启动中`。
- AWB 弹窗存在 Hold 时，程序等待错误文字或重复处理的问题。
- CrewSupply 实际返回 JSON signed URL、但程序只等待浏览器下载事件的问题。
- 在线下载与本地 ZIP 恢复使用不同 PDF 流程的问题。
- PDF 每张重复 OCR 两次导致处理缓慢的问题。
- 手机状态一直显示成功 PDF 为 0 的问题。
- `start_once.bat` 可能绕开手机锁、重复生成 AWB 的风险。

## 唯一正式运行方式

1. 双击 `start_mobile.bat`。
2. 黑色窗口保持开启。
3. 手机打开 `http://电脑局域网IP:8000`。
4. 每天只点击一次“开始今日发货”。
5. 运行中不要再点击、不要运行 Codex 命令、不要运行其他 BAT。

`start_once.bat` 已改成说明页，不会再直接访问账号。

## 正式处理流程

```text
检查账号
→ 筛选 To Ship
→ AWB Download
→ Download All（一次）
→ 解析 Hold
→ 弹窗 Download（一次）
→ 优先捕获 JSON signed URL
→ 验证 ZIP
→ 统一调用本地 ZIP 处理
→ UPS/USPS/FedEx 处理
→ Excel 与 PDF ZIP
→ 手机状态完成
```

## 出现 Hold 时

Hold 只作为单个异常记录，不会让整个账号失败。其余可下载订单继续处理：

- 成功订单进入“今日发货”。
- Hold 进入“异常订单”。
- 账号汇总显示 `PARTIAL_SUCCESS`。

## 网站下载成功但后续处理失败

不要重新生成 AWB。使用以下任一方式：

- 手机“高级工具”→“从本地ZIP继续处理”。
- 双击 `start_recovery.bat`，粘贴 ZIP 路径。

## 第一次使用

1. 双击 `install.bat`（已经安装过可跳过）。
2. 双击 `first_use_check.bat`。
3. 确认测试全部通过。
4. 双击 `start_mobile.bat`。
5. 手机页面底部确认 `APP_VERSION 2.0.0-stable`。

## 重要限制

- 一个账号每次运行 AWB 生成最多一次。
- 弹窗 Download 最多点击一次。
- 失败时不自动重新生成 AWB。
- 同一天第二次完整正式运行会被拒绝。
- 补跑只处理未完成账号。
- `private` 文件夹包含登录状态，不要转发。

## 常用文件

- `start_mobile.bat`：手机控制中心。
- `first_use_check.bat`：环境与离线测试。
- `start_recovery.bat`：本地 ZIP 恢复。
- `reset_stale_status.bat`：修复虚假的 running 状态。
- `Reports`：Excel 和处理后 PDF ZIP。
- `Label`：各账号原始、处理后和诊断文件。

## 验证结果

- Python 语法检查：通过。
- 离线单元测试：66 项通过。
- JSON signed URL 下载模拟：通过。
- 真实本地 ZIP（2张 UPS）恢复：通过。
- 账号登录与 CrewSupply 在线页面无法在离线构建环境中再次执行，因此首次正式生产仍应观察一次；失败时不要重跑，直接使用已保存 ZIP 恢复。
