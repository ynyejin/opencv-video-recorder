import cv2
import datetime

# 카메라 열기
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("카메라를 열 수 없습니다.")
    exit()

# 카메라 프레임 크기 가져오기
frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = 20.0

# 현재 시간 기반 파일 이름 생성
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
filename = f"recordings/record_{timestamp}.mp4"

# 저장할 비디오 코덱 및 파일 설정
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter(filename, fourcc, fps, (frame_width, frame_height))

# 초기 모드: Preview
is_recording = False

while True:
    ret, frame = cap.read()

    if not ret:
        print("프레임을 읽을 수 없습니다.")
        break

    # 현재 모드 표시 텍스트
    mode_text = "RECORD" if is_recording else "PREVIEW"
    color = (0, 0, 255) if is_recording else (0, 255, 0)

    cv2.putText(
        frame,
        mode_text,
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        color,
        2
    )

    # Record 모드일 때 빨간 원 표시
    if is_recording:
        cv2.circle(frame, (frame_width - 30, 30), 10, (0, 0, 255), -1)
        out.write(frame)

    # 화면 출력
    cv2.imshow("Video Recorder", frame)

    key = cv2.waitKey(1) & 0xFF

    # ESC 키 종료
    if key == 27:
        break

    # Space 키로 Preview / Record 전환
    elif key == 32:
        is_recording = not is_recording

cap.release()
out.release()
cv2.destroyAllWindows()