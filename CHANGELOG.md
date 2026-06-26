# Changelog

## 2.0.0-stable

- 修复手机首页 `pending_disabled` / `pending_title` 未定义。
- 新增任务 PID 与僵死状态校正。
- 手机页面显示版本、服务启动时间和主程序修改时间。
- AWB Download 按钮稳定可用时不再无限等待可选结果文案。
- 下载逻辑改为一次点击后同时监听：JSON signed URL、download 事件、ZIP response 和新文件。
- JSON signed URL 成为主要下载路径，`expect_download` 不再作为主路径。
- 在线流程与 `--resume-zip` 共用 `process_zip_records()`。
- PDF 文本/OCR不再重复执行两次；OCR调用从约10次降至3次，并增加超时。
- 恢复与正式任务写入完整成功、异常、承运商和账号状态。
- `start_once.bat` 停止直接运行，避免绕过生产锁重复生成AWB。
- 新增 `start_recovery.bat`、`reset_stale_status.bat`、`first_use_check.bat`。
- 新增 signed URL 下载与僵死状态离线测试。
