# Electric Stroller Intelligence Daily

每天自动收集“婴童电助力推车 / 智能婴儿车 / AI stroller / electric stroller / robotic stroller / electric baby stroller / powered stroller / e-assist stroller”相关的研发、产品和上市线索，使用 OpenAI API 生成中文日报，并通过 Gmail SMTP 发送。

## 功能

- 覆盖品牌官网、新闻、众筹、专利、论文、展会和电商页面。
- 重点跟踪 CYBEX e-Priam、CYBEX e-Gazelle S、Glüxkind Rosa、Glüxkind Ella、Bosch eStroller 相关技术。
- 自动提取产品名称、品牌、上市地区、价格、电助力、下坡制动、自动驻车、自动摇晃、App 控制、电池续航、传感器、AI/机器人功能、安全功能、来源链接和时间线索。
- 将已抓取 URL 写入 `data/seen_urls.json`，后续运行只报告新增链接。
- 生成 Markdown 日报到 `reports/YYYY-MM-DD.md`。
- GitHub Actions 每天北京时间 08:00 自动运行。

## 项目结构

```text
src/main.py
src/collect.py
src/summarize.py
src/emailer.py
src/storage.py
config/keywords.yml
config/sources.yml
data/seen_urls.json
reports/
requirements.txt
README.md
.env.example
.github/workflows/daily.yml
```

## 本地运行

1. 安装依赖：

```bash
pip install -r requirements.txt
```

2. 配置环境变量：

```bash
cp .env.example .env
```

然后填写：

- `OPENAI_API_KEY`
- `GMAIL_USER`
- `GMAIL_APP_PASSWORD`
- `REPORT_RECIPIENT`

Gmail 需要使用 App Password，而不是普通登录密码。

3. 运行：

```bash
python src/main.py
```

只生成日报、不发送邮件：

```bash
python src/main.py --skip-email
```

本地没有 OpenAI Key 时可生成备用格式报告用于调试：

```bash
python src/main.py --skip-email --allow-fallback-summary
```

## GitHub Actions 配置

在仓库的 Settings -> Secrets and variables -> Actions 中添加 Secrets：

- `OPENAI_API_KEY`
- `GMAIL_USER`
- `GMAIL_APP_PASSWORD`
- `REPORT_RECIPIENT`

可选添加 Repository variable：

- `OPENAI_MODEL`，默认使用 `gpt-4o-mini`

工作流位于 `.github/workflows/daily.yml`，定时配置为：

```yaml
- cron: "0 0 * * *"
```

这是 UTC 00:00，对应北京时间 08:00。

## 扩展采集源

- 新增关键词：编辑 `config/keywords.yml`
- 新增来源：编辑 `config/sources.yml`

来源支持：

- `type: rss`
- `type: page`

单个来源抓取失败会记录异常，但不会中断其他来源采集。

## 注意

- 部分电商、众筹或品牌页面可能启用反爬、地区跳转或动态渲染，脚本会尽力提取页面标题、正文和相关链接；失败时会继续处理其他来源。
- OpenAI 报告只基于采集到的来源材料生成，不确定内容会标记为“未披露”或“线索待核验”。
- GitHub Actions 会在日报发送成功后提交 `data/seen_urls.json` 和 `reports/` 的变化，用于跨天去重。
