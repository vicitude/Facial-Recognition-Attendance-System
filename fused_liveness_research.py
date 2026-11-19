"""三随机动作融合活体研究入口；不连接考勤数据库、不保存影像。"""
import argparse
from dataclasses import asdict
import json
import sys
from time import monotonic

from attendance.active_liveness import Action
from attendance.fused_liveness import adapt_feature
from attendance.liveness_overlay import draw_chinese_overlay
from attendance.liveness_pipeline import AsyncFusionPipeline, LatestFrameCamera

CHINESE = {
    Action.BLINK.value: '请眨眼后睁眼',
    Action.TURN_LEFT.value: '请向您自己的左侧转头，然后回正',
    Action.TURN_RIGHT.value: '请向您自己的右侧转头，然后回正',
    Action.NOD.value: '请低头点头，然后回正',
}


def main():
    parser = argparse.ArgumentParser(description='三随机动作融合活体研究；Esc退出，R重新挑战，不写签到记录')
    parser.add_argument('--camera', type=int, default=0)
    parser.add_argument('--category', choices=['live', 'paper', 'phone_photo', 'phone_video'], required=True)
    args = parser.parse_args()
    sys.argv = [sys.argv[0]]  # 隔离旧YOLO模块的模块级参数解析。
    import cv2
    import numpy as np
    from PIL import Image
    import recognition
    from facenet.facenet import Facenet
    from attendance.active_liveness_landmarks import FaceLandmarkDetector
    from attendance.liveness_research import LivenessResearch, assess_quality

    from attendance.liveness_backend import Auxiliary, Landmarks

    camera = pipeline = capture = None
    counts = dict(attempts=0, passed=0, failed=0, timeout=0)
    try:
        capture = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not capture.isOpened():
            raise RuntimeError('摄像头不可用')
        camera = LatestFrameCamera(capture)
        pipeline = AsyncFusionPipeline(Landmarks(), Auxiliary(), assess_quality)
        pipeline.start()
        last_progress = None
        counted = False
        print('研究验证：正在预热模型；保持正视睁眼。预热完成后按动作提示操作。Esc退出，R重新挑战。', flush=True)
        while True:
            if camera.error:
                raise RuntimeError('无法读取摄像头帧')
            latest = camera.snapshot()
            if latest is not None:
                frame_id, timestamp, frame = latest
                pipeline.submit(frame_id, timestamp, frame)
                snapshot = pipeline.snapshot()
                for diagnostic in snapshot.get('diagnostics', []):
                    print(json.dumps(dict(event='identity_diagnostic', research_only=True, category=args.category,
                                          generation=snapshot['generation'], metrics=diagnostic), ensure_ascii=False), flush=True)
                result = snapshot['result']
                if result is not None:
                    progress = (result.status, result.action, result.phase, result.completed, result.reason)
                    if progress != last_progress:
                        payload = asdict(result)
                        payload.update(research_only=True, category=args.category, instruction=CHINESE[result.action], metrics=snapshot['metrics'])
                        print(json.dumps(payload, ensure_ascii=False), flush=True)
                        last_progress = progress
                    if result.status != 'pending' and not counted:
                        counted = True
                        counts['attempts'] += 1
                        counts[result.status] += 1
                        print(json.dumps(dict(category=args.category, counts=counts, research_only=True)), flush=True)
                preview = draw_chinese_overlay(cv2.flip(frame, 1), result, snapshot['metrics'], snapshot['warming'])
                cv2.imshow('Fused liveness RESEARCH', preview)
            key = cv2.waitKey(1) & 0xff
            if key == 27:
                break
            if latest is not None and cv2.getWindowProperty('Fused liveness RESEARCH', cv2.WND_PROP_VISIBLE) < 1:
                break
            if key in (ord('r'), ord('R')):
                pipeline.reset()
                last_progress, counted = None, False
    finally:
        if pipeline is not None:
            pipeline.close()
        if camera is not None:
            camera.close()
        elif capture is not None:
            capture.release()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'研究入口环境/推理失败：{type(exc).__name__}；未放行，请检查本机依赖和模型。', file=sys.stderr)
        raise SystemExit(1)
