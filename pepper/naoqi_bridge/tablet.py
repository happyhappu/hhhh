# -*- coding: utf-8 -*-
"""
平板渲染控制器（对齐 pepper_v1.yaml action_primitives.tablet + channels: [screen]）。

- tablet_render(url)：ALTabletService.showWebview 加载远端/本地 Web UI
  （问候语/字幕/表情/陪伴内容）。URL 由主网关或云端托管。
- tablet_clear()：hide() 收起平板。

⚠️ Pepper 平板为 Android WebView；data: URL 可能不被支持，
   建议传 http(s) 或 file:// 路径（file 需先落到 Pepper 可访问位置）。
"""
from __future__ import print_function, absolute_import


class TabletController(object):

    def __init__(self, proxies):
        self.p = proxies

    def render(self, url=None, params=None):
        """在平板加载 Web UI。

        params: {url(str)} 或 {html(str) 内联 -> 当前仅支持已托管 URL}
        """
        tablet = self.p.require("ALTabletService")
        target = url or (params or {}).get("url")
        if not target:
            return {"error": "缺少 url"}
        if target.startswith(("http://", "https://", "file://")):
            tablet.showWebview(target)
            return {"tablet": "rendered", "url": target}
        # 内联 HTML：本桥不内嵌 Web 服务器，要求主网关先托管再传 URL
        return {"error": "内联 html 需主网关托管后传 URL；收到: %s" % target[:40]}

    def clear(self, params=None):
        """收起平板。"""
        tablet = self.p.require("ALTabletService")
        tablet.hide()
        return {"tablet": "hidden"}
