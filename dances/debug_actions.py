"""
Quét GetActionList + (tùy chọn) thử PlayAction / StartBehavior — khớp mini SDK trong venv.

Chạy từ thư mục AlphaMiniServer, bật venv:

  set PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
  .\\venv\\Scripts\\python.exe debug_actions.py --ip 10.55.121.163

Hoặc quét serial trên LAN:

  .\\venv\\Scripts\\python.exe debug_actions.py --serial 00018 --robot-type edu

Thử thêm các tên/mã ứng viên (robot sẽ cử động):

  .\\venv\\Scripts\\python.exe debug_actions.py --ip ... --probe

Nhảy lần lượt 7 bài (dance_0001…0005 + dance_0001en/0002en), không chạy probe dài:

  .\\venv\\Scripts\\python.exe debug_actions.py --ip ... --dance-all

Biến môi trường (tuỳ chọn): ROBOT_IP, ROBOT_TYPE=mini|edu|dedu|kor
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

import ws_mini_compat

ws_mini_compat.apply_mini_websocket_compat()

import mini.mini_sdk as MiniSdk
from mini import MiniApiResultType, RobotType
from mini.apis.api_action import GetActionList, PlayAction, RobotActionType, StopAllAction
from mini.apis.api_behavior import StartBehavior
from mini.dns.dns_browser import WiFiDevice

# 7 behavior nhảy mẫu (StartBehavior) — firmware Alpha Mini thường có dance_0001…0005 + bản en.
def _ensure_utf8_stdio() -> None:
    """Windows: tránh UnicodeEncodeError khi in emoji (cp1252)."""
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


DANCE_BEHAVIORS_7 = [
    "dance_0001",
    "dance_0002",
    "dance_0003",
    "dance_0004",
    "dance_0005",
    "dance_0001en",
    "dance_0002en",
]


def _set_robot_type(name: str) -> None:
    m = (name or "mini").strip().lower()
    if m in ("mini", "min"):
        MiniSdk.set_robot_type(RobotType.MINI)
    elif m == "edu":
        MiniSdk.set_robot_type(RobotType.EDU)
    elif m in ("dedu", "cn", "china"):
        MiniSdk.set_robot_type(RobotType.DEDU)
    elif m in ("kor", "kr"):
        MiniSdk.set_robot_type(RobotType.KOR)
    else:
        raise SystemExit(f"robot-type không hỗ trợ: {name!r} (mini|edu|dedu|kor)")


async def _resolve_device(args: argparse.Namespace) -> WiFiDevice | None:
    if args.ip:
        return WiFiDevice(name="AlphaMini", address=args.ip.strip())
    if args.serial:
        dev = await MiniSdk.get_device_by_name(args.serial.strip(), args.scan_timeout)
        return dev
    print("Cần --ip hoặc --serial.", file=sys.stderr)
    return None


def _format_action_item(item) -> str:
    i = getattr(item, "id", None) or ""
    cn = getattr(item, "cnName", None) or ""
    en = getattr(item, "enName", None) or ""
    t = int(getattr(item, "type", 0) or 0)
    return f"id={i!r} cn={cn!r} en={en!r} type={t}"


async def _get_action_list_with_retry(
    action_type, retries: int, pause: float
) -> tuple[MiniApiResultType | None, object | None]:
    last_rt, last_resp = None, None
    for attempt in range(max(1, retries)):
        block = GetActionList(True, action_type)
        last_rt, last_resp = await block.execute()
        if (
            last_rt == MiniApiResultType.Success
            and last_resp
            and last_resp.isSuccess
            and list(last_resp.actionList or [])
        ):
            return last_rt, last_resp
        if attempt < retries - 1:
            logging.warning("GetActionList rỗng / lỗi — retry %s/%s …", attempt + 1, retries)
            await asyncio.sleep(pause)
    return last_rt, last_resp


async def _run_startbehavior_dance_list(
    args: argparse.Namespace,
    bnames: list[str],
    *,
    title: str,
) -> None:
    """Chạy StartBehavior lần lượt; giữa các bài gọi StopAllAction (nhiều firmware cần reset trước behavior tiếp theo)."""
    print(f"\n{title} — {len(bnames)} bài (robot sẽ cử động)")
    settle = float(getattr(args, "stop_before_next_dance_sec", None) or 0.25)
    for idx, b in enumerate(bnames):
        if idx > 0:
            try:
                await StopAllAction(False).execute()
                await asyncio.sleep(max(0.0, settle))
            except Exception as e:
                print(f"  ⚠️ StopAllAction trước {b!r}: {e}")
        try:
            rtb, rb = await StartBehavior(True, b).execute()
            okb = (
                rtb == MiniApiResultType.Success
                and rb is not None
                and getattr(rb, "isSuccess", False)
            )
            code = getattr(rb, "resultCode", "N/A") if rb else "N/A"
            if okb:
                print(f"  ✅ StartBehavior OK: {b!r}")
                await asyncio.sleep(max(0.0, args.pause_after_ok))
            else:
                print(f"  ❌ StartBehavior: {b!r} (resultCode={code})")
        except Exception as e:
            print(f"  ⚠️ StartBehavior exception {b!r}: {e}")
        await asyncio.sleep(max(0.0, args.pause_between))


async def main_async(args: argparse.Namespace) -> int:
    MiniSdk.set_log_level(getattr(logging, args.log_level.upper(), logging.INFO))
    _set_robot_type(args.robot_type)

    device = await _resolve_device(args)
    if not device:
        return 1

    ok = await MiniSdk.connect(device)
    if not ok:
        print("❌ connect() thất bại", file=sys.stderr)
        return 1

    enter_ok = await MiniSdk.enter_program()
    if not enter_ok:
        print("⚠️ enter_program() không báo Success — vẫn thử GetActionList …")
    await asyncio.sleep(max(0.0, args.extra_wait_after_program))

    print(f"✅ Đã connect: {device!s}\n")

    if args.dance_all:
        await _run_startbehavior_dance_list(
            args,
            list(DANCE_BEHAVIORS_7),
            title="TEST dance-all: StartBehavior (7 bài)",
        )
        await MiniSdk.release()
        return 0

    # --- Test 1: INNER ---
    print("=" * 55)
    print("TEST 1: GetActionList INNER")
    rt, resp = await _get_action_list_with_retry(
        RobotActionType.INNER, args.list_retries, args.list_retry_pause
    )
    print(f"  resultType: {rt}")
    if resp is None:
        print("  ❌ Không có response")
    else:
        print(f"  isSuccess : {resp.isSuccess}")
        print(f"  resultCode: {resp.resultCode}")
        items = list(resp.actionList or [])
        if items:
            print(f"  ✅ {len(items)} action(s):")
            for it in items:
                print(f"     - {_format_action_item(it)}")
        else:
            print("  ❌ actionList rỗng")

    # --- Test 2: CUSTOM ---
    print("\nTEST 2: GetActionList CUSTOM")
    rt2, resp2 = await _get_action_list_with_retry(
        RobotActionType.CUSTOM, args.list_retries, args.list_retry_pause
    )
    print(f"  resultType: {rt2}")
    if resp2 is None:
        print("  ❌ Không có response")
    else:
        print(f"  isSuccess : {resp2.isSuccess}")
        print(f"  resultCode: {resp2.resultCode}")
        items2 = list(resp2.actionList or [])
        if items2:
            print(f"  ✅ {len(items2)} custom action(s):")
            for it in items2:
                print(f"     - {_format_action_item(it)}")
        else:
            print("  ❌ actionList rỗng")

    if args.probe:
        candidates = [
            *[f"{i:03d}" for i in range(1, 41)],
            *[str(i) for i in range(1, 21)],
            "stand",
            "stand_up",
            "StandUp",
            "get_up",
            "GetUp",
            "SquatUp",
            "squat_up",
            "sit_down",
            "squat",
            "reset",
            "idle",
            "dance_0001",
            "dance_0002",
            "dance_0003",
            "dance_0004",
            "dance_0005",
            "dance_0001en",
            "dance_0002en",
        ]

        print("\nTEST 3: PlayAction — từng ứng viên (robot sẽ cử động)")
        working: list[str] = []
        for name in candidates:
            try:
                rt3, r3 = await PlayAction(True, name).execute()
                ok3 = (
                    rt3 == MiniApiResultType.Success
                    and r3 is not None
                    and getattr(r3, "isSuccess", False)
                )
                code = getattr(r3, "resultCode", "N/A") if r3 else "N/A"
                if ok3:
                    working.append(name)
                    print(f"  ✅ PlayAction OK: {name!r}")
                    await asyncio.sleep(args.pause_after_ok)
                else:
                    print(f"  ❌ PlayAction: {name!r} (resultCode={code})")
            except Exception as e:
                print(f"  ⚠️ PlayAction exception {name!r}: {e}")
            await asyncio.sleep(args.pause_between)

        await _run_startbehavior_dance_list(
            args,
            list(DANCE_BEHAVIORS_7),
            title="TEST 4: StartBehavior (7 bài nhảy)",
        )

        print("\n" + "=" * 55)
        print("TỔNG KẾT PlayAction thành công:", ", ".join(repr(w) for w in working) or "(không có)")

    await MiniSdk.release()
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Debug GetActionList + tùy chọn probe PlayAction (mini SDK).")
    p.add_argument("--ip", default=os.getenv("ROBOT_IP", "").strip() or None, help="IP robot (như ROBOT_IP trong .env)")
    p.add_argument("--serial", default=None, help="Serial robot — quét mDNS trên LAN")
    p.add_argument("--scan-timeout", type=int, default=15, help="Timeout quét khi dùng --serial (giây)")
    p.add_argument(
        "--robot-type",
        default=os.getenv("ROBOT_TYPE", "mini").strip(),
        help="mini | edu | dedu | kor (SDK không có ORIGINAL; Alpha Mini server dùng mini)",
    )
    p.add_argument(
        "--extra-wait-after-program",
        type=float,
        default=0.0,
        help="Thêm giây chờ sau enter_program (enter_program đã sleep ~6s sẵn trong SDK)",
    )
    p.add_argument("--list-retries", type=int, default=3, help="Retry GetActionList khi rỗng")
    p.add_argument("--list-retry-pause", type=float, default=2.0, help="Pause giữa các lần retry (giây)")
    p.add_argument(
        "--probe",
        action="store_true",
        help="Chạy vòng thử PlayAction + StartBehavior (robot cử động — mặc định chỉ liệt kê)",
    )
    p.add_argument(
        "--dance-all",
        action="store_true",
        help="Chỉ chạy StartBehavior lần lượt 7 bài: dance_0001…0005 + dance_0001en/0002en (bỏ qua GetActionList & PlayAction)",
    )
    p.add_argument(
        "--stop-before-next-dance-sec",
        type=float,
        default=0.25,
        help="Chờ sau StopAllAction giữa hai bài nhảy (giây)",
    )
    p.add_argument("--pause-between", type=float, default=0.5, help="Pause giữa mỗi lệnh probe (giây)")
    p.add_argument("--pause-after-ok", type=float, default=2.0, help="Pause sau mỗi lệnh probe thành công (giây)")
    p.add_argument("--log-level", default="INFO", help="DEBUG|INFO|WARNING|ERROR")
    return p


def main() -> None:
    _ensure_utf8_stdio()
    os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
    args = build_arg_parser().parse_args()
    if not args.ip and not args.serial:
        print("Thiếu --ip hoặc --serial. Gợi ý: --ip từ .env hoặc ROBOT_IP.", file=sys.stderr)
        raise SystemExit(2)
    try:
        raise SystemExit(asyncio.run(main_async(args)))
    except KeyboardInterrupt:
        print("\nĐã dừng.", file=sys.stderr)
        raise SystemExit(130)


if __name__ == "__main__":
    main()
