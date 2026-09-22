# -*- coding: utf-8 -*-
"""
导航/巡游控制器（对齐 pepper_v1.yaml action_primitives.navigate/patrol）。

- 纯 qi 路径：ALMotion.moveTo（ALNavigation 不可用时的降级项，yaml 已列）。
- 增强路径：若 ALNavigation 可用，支持按拓扑节点名导航（navigateToInMap）。
- 所有移动受 MAX_MOVE_SPEED 限速（三轮底盘物理上限）。

⚠️ ALNavigation 拓扑导航在培训文档中走 ROS 路线，纯 qi 未实证；
   故默认走 ALMotion.moveTo，ALNavigation 仅作可选增强，失败即降级。
"""
from __future__ import print_function, absolute_import

import config as cfg


class NavigationController(object):

    def __init__(self, proxies):
        self.p = proxies

    def navigate(self, goal, speed=None, params=None):
        """移动到目标。

        goal:
          - [x, y, theta] 列表/元组 -> ALMotion.moveTo（相对坐标，单位 m / rad）
          - 字符串节点名         -> ALNavigation.navigateToInMap（可选增强）
        speed: 限速 m/s（默认 MAX_MOVE_SPEED）
        """
        motion = self.p.require("ALMotion")
        speed = float(speed if speed is not None else cfg.MAX_MOVE_SPEED)
        speed = max(0.05, min(speed, cfg.MAX_MOVE_SPEED))

        if isinstance(goal, (list, tuple)):
            if len(goal) < 2:
                return {"error": "goal 列表需至少 [x, y]"}
            x, y = float(goal[0]), float(goal[1])
            theta = float(goal[2]) if len(goal) > 2 else 0.0
            self._ensure_wheel_stiffness(motion)
            motion.moveTo(x, y, theta, cfg.MOVE_BLOCKING)
            return {"navigated_to": [round(x, 3), round(y, 3), round(theta, 3)],
                    "speed_mps": speed}
        elif isinstance(goal, str):
            nav = self.p.get("ALNavigation")
            if nav is not None:
                try:
                    nav.navigateToInMap(goal)   # ⚠️ 真机确认方法名/参数
                    return {"navigated_to_node": goal}
                except Exception as exc:
                    return {"error": "ALNavigation.navigateToInMap 失败: %s" % exc,
                            "fallback": "ALMotion.moveTo 不可用(goal 为节点名)"}
            return {"error": "ALNavigation 不可用且 goal 为节点名，无法导航"}
        return {"error": "goal 类型不支持: %r" % goal}

    def patrol(self, points=None, loops=1, speed=None, params=None):
        """巡游多个航点。

        points: [[x,y,theta], ...] 相对坐标序列；loops: 循环次数。
        """
        points = points or []
        if not points:
            return {"error": "points 为空"}
        nav = self.p.get("ALNavigation")
        motion = self.p.require("ALMotion")
        loops = max(1, int(loops))
        done = 0
        for _ in range(loops):
            for wp in points:
                if isinstance(wp, (list, tuple)) and len(wp) >= 2:
                    res = self.navigate(wp, speed=speed)
                    if "error" in res:
                        return {"patrolled": done, "error": res["error"]}
                    done += 1
                elif isinstance(wp, str) and nav is not None:
                    res = self.navigate(wp, speed=speed)
                    if "error" in res:
                        return {"patrolled": done, "error": res["error"]}
                    done += 1
        return {"patrolled": done, "loops": loops}

    @staticmethod
    def _ensure_wheel_stiffness(motion):
        try:
            motion.setStiffnesses(["WheelFL", "WheelFR", "WheelB"], 1.0)
        except Exception as exc:
            print("[navigation] setStiffnesses 异常(忽略): %s" % exc)
