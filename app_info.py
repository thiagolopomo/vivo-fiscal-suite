#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
from pathlib import Path

_cfg_path = Path(__file__).with_name("release_config.json")
_cfg = json.loads(_cfg_path.read_text(encoding="utf-8"))

APP_NAME = "VIVO Fiscal Suite"
APP_VERSION = _cfg["version"]
UPDATE_MANIFEST_URL = (
    f"https://raw.githubusercontent.com/"
    f"{_cfg['repo_owner']}/{_cfg['repo_name']}/main/version.json"
)