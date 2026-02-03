import cv2
import numpy as np
import time

def nothing(x):
    pass

def run_amr_docking_roi():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("카메라를 열 수 없습니다.")
        return

    # 제어 인터페이스 윈도우 생성
    cv2.namedWindow('Settings', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('Settings', 400, 300)

    # 트랙바 생성 (초기값 설정)
    cv2.createTrackbar('Min Circularity', 'Settings', 85, 100, nothing)
    cv2.createTrackbar('Min Area', 'Settings', 150, 2000, nothing)
    cv2.createTrackbar('ROI Scale (%)', 'Settings', 60, 100, nothing)
    # 녹화 관련 변수 초기화
    is_recording = False
    out = None

    while True:
        ret, frame = cap.read()
        if not ret: break

        start_t = time.time()
        h, w = frame.shape[:2]
        screen_cx, screen_cy = w // 2, h // 2

        # 트랙바 값 읽기
        min_circ = cv2.getTrackbarPos('Min Circularity', 'Settings') / 100.0
        min_area = cv2.getTrackbarPos('Min Area', 'Settings')
        roi_scale = cv2.getTrackbarPos('ROI Scale (%)', 'Settings') / 100.0

        # ROI 설정: 트랙바 값에 따라 동적으로 변경
        roi_w, roi_h = int(w * roi_scale), int(h * roi_scale)
        x1 = max(0, screen_cx - (roi_w // 2))
        y1 = max(0, screen_cy - (roi_h // 2))
        x2, y2 = min(w, x1 + roi_w), min(h, y1 + roi_h)

        # ROI 영역 추출 및 전처리
        roi_img = frame[y1:y2, x1:x2]
        if roi_img.size == 0: continue # ROI 크기가 0인 경우 예외 처리

        gray_roi = cv2.cvtColor(roi_img, cv2.COLOR_BGR2GRAY)

        # 동적 파라미터 적용을 위한 Detector 생성
        params = cv2.SimpleBlobDetector_Params()
        params.filterByColor = True
        params.blobColor = 0
        params.filterByArea = True
        params.minArea = float(min_area)
        params.maxArea = 20000.0
        params.filterByCircularity = True
        params.minCircularity = min_circ

        detector = cv2.SimpleBlobDetector_create(params)
        keypoints = detector.detect(gray_roi)

        # 시각화용 ROI 가이드 박스
        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 255), 1)
        cv2.putText(frame, f"Circ: {min_circ} / Area: {min_area} / ROI: {int(roi_scale*100)}%", (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        if len(keypoints) >= 2:
            # 크기순 정렬 후 상위 2개 선택
            kp_sorted = sorted(keypoints, key=lambda x: x.size, reverse=True)[:2]

            # ROI 좌표를 전체 프레임 좌표로 변환
            pt1 = (int(kp_sorted[0].pt[0] + x1), int(kp_sorted[0].pt[1] + y1))
            pt2 = (int(kp_sorted[1].pt[0] + x1), int(kp_sorted[1].pt[1] + y1))

            # 도킹 센터 계산
            dock_cx = (pt1[0] + pt2[0]) // 2
            dock_cy = (pt1[1] + pt2[1]) // 2

            # 오프셋 계산
            dx = dock_cx - screen_cx
            dy = dock_cy - screen_cy

            # 시각화: 마커 및 연결선
            cv2.line(frame, pt1, pt2, (255, 0, 0), 2)
            cv2.circle(frame, pt1, 5, (0, 255, 255), -1)
            cv2.circle(frame, pt2, 5, (0, 255, 255), -1)
            cv2.circle(frame, (dock_cx, dock_cy), 8, (0, 0, 255), -1)

            # 정렬 상태 판별
            if abs(dx) < 15:
                hint, color = "ALIGN OK", (0, 255, 0)
            elif dx > 0:
                hint, color = "MOVE RIGHT ->", (0, 255, 255)
            else:
                hint, color = "<- MOVE LEFT", (0, 255, 255)

            # 정보 표시
            cv2.putText(frame, hint, (x1, y2 + 40), cv2.FONT_HERSHEY_DUPLEX, 0.8, color, 2)
            cv2.putText(frame, f"dx: {dx}px, dy: {dy}px", (x1, y2 + 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

        else:
            cv2.putText(frame, "ADJUST SETTINGS TO FIND MARKERS", (x1, y2 + 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 1)

        # 6. 시스템 정보 및 녹화 상태 표시
        fps = 1 / (time.time() - start_t) if (time.time() - start_t) > 0 else 0
        cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        if is_recording:
            cv2.putText(frame, "● REC", (w - 100, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            # 녹화 중일 때 프레임 저장
            if out is not None:
                out.write(frame)

        # 화면 중앙 조준점
        cv2.drawMarker(frame, (screen_cx, screen_cy), (100, 100, 100), cv2.MARKER_CROSS, 15, 1)

        cv2.imshow("AMR ROI Control View", frame)

        # 키 입력 처리
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s'):
            # 녹화 시작/중지 토글
            if not is_recording:
                # 녹화 시작
                filename = f"docking_record_{time.strftime('%Y%m%d_%H%M%S')}.avi"
                fourcc = cv2.VideoWriter_fourcc(*'XVID')
                out = cv2.VideoWriter(filename, fourcc, 20.0, (w, h))
                is_recording = True
                print(f"녹화 시작: {filename}")
            else:
                # 녹화 중지
                is_recording = False
                if out is not None:
                    out.release()
                out = None
                print("녹화 중지 및 파일 저장 완료")

    cap.release()
    if out is not None:
        out.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run_amr_docking_roi()