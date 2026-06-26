from __future__ import annotations

import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent
LOGIN_URL = "https://crewsupply-web-gi7me3n4rq-de.a.run.app"

parser = argparse.ArgumentParser()
parser.add_argument("account", help="Example: account_YOUT")
args = parser.parse_args()
state_path = BASE_DIR / "private" / f"{args.account}.json"
state_path.parent.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto(LOGIN_URL)
    input("登录完成并进入后台后，回到此窗口按回车：")
    context.storage_state(path=str(state_path))
    browser.close()
print("登录状态已保存：", state_path)
