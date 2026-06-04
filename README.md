For Slack bot settings see: https://docs.slack.dev/tools/bolt-python/getting-started/.

- Install uv
- `uv sync`
- Copy `.env.dist` to `.env`
- Set the env variables
- `uv run src/main.py` voor Slackbot
- `uv run src/ns.py` voor Slackbot trein notifications

**Deployen:**

- Push/merge naar master
- Wacht tot de Gitlab CD klaar is
- ```shell
  ssh vck@becky.vck.tv
  ssh dromendans
  sudo docker-manager update slackbot-py
  ````
